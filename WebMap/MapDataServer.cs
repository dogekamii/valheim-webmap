using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using UnityEngine;
using WebSocketSharp;
using WebSocketSharp.Net;
using WebSocketSharp.Server;
using static WebMap.WebMapConfig;

namespace WebMap
{
    internal class PublicIdentityView
    {
        internal long Id;
        internal string Alias;
    }

    internal static class PublicIdentity
    {
        private const ulong MaxSafeInteger = 9007199254740991UL;
        private static readonly object Sync = new object();
        private static readonly RandomNumberGenerator Random = RandomNumberGenerator.Create();
        private static readonly Dictionary<string, PublicIdentityView> Identities = new Dictionary<string, PublicIdentityView>();
        private static readonly HashSet<long> IssuedIds = new HashSet<long>();
        private static int nextAliasNumber = 1;

        internal static PublicIdentityView ForPeer(long rawId)
        {
            return Get("peer:" + rawId.ToString(CultureInfo.InvariantCulture));
        }

        internal static PublicIdentityView ForOwner(string rawId)
        {
            return Get("owner:" + (rawId ?? string.Empty));
        }

        private static PublicIdentityView Get(string identityKey)
        {
            lock (Sync)
            {
                if (Identities.TryGetValue(identityKey, out PublicIdentityView existing))
                {
                    return existing;
                }

                long publicId = NextOpaqueId();
                int aliasNumber = nextAliasNumber++;
                PublicIdentityView identity = new PublicIdentityView
                {
                    Id = publicId,
                    Alias = $"Player {aliasNumber}"
                };
                Identities.Add(identityKey, identity);
                IssuedIds.Add(publicId);
                return identity;
            }
        }

        private static long NextOpaqueId()
        {
            byte[] bytes = new byte[sizeof(long)];
            long candidate;
            do
            {
                Random.GetBytes(bytes);
                candidate = (long)(BitConverter.ToUInt64(bytes, 0) & MaxSafeInteger);
            }
            while (candidate == 0 || IssuedIds.Contains(candidate));

            return candidate;
        }
    }

    [Serializable]
    public struct MapMessage
    {
        public long id;
        public int type;
        public string name;
        public string message;
        public string ts;

        public MapMessage(long id, int type, string name, string message)
        {
            PublicIdentityView identity = PublicIdentity.ForPeer(id);
            this.id = identity.Id;
            this.type = type;
            this.name = name == "Server" ? "Server" : identity.Alias;
            this.message = message;
            this.ts = DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture);
        }

        public string ToJson()
        {
            return JsonUtility.ToJson(this);
        }
    }

    public class WebSocketHandler : WebSocketBehavior
    {
        protected override void OnMessage(MessageEventArgs e)
        {
            if (e.Data.ToString() == "players")
            {
                Send(MapDataServer.getInstance().getPlayerResponse(true));
            }
            base.OnMessage(e);
        }
    }

    public class MapDataServer
    {
        private static readonly Dictionary<string, string> contentTypes = new Dictionary<string, string> {
            {"html", "text/html"},
            {"js", "text/javascript"},
            {"css", "text/css"},
            {"png", "image/png"},
            {"jpg", "image/jpeg"},
            {"webp", "image/webp"}
        };
        private static readonly string[] PublicPinTypes = { "dot", "fire", "mine", "house", "cave" };

        private readonly System.Threading.Timer broadcastTimer;
        private readonly Dictionary<string, byte[]> fileCache;
        public Texture2D fogTexture;
        private readonly HttpServer httpServer;

        public byte[] mapImageData;
        public List<string> pins = new List<string>();
        public List<MapMessage> sentMessages = new List<MapMessage>();
        public List<MapMessage> newMessages = new List<MapMessage>();
        public List<ZNetPeer> players = new List<ZNetPeer>();
        public string lastPlayerResponse = "";
        private bool forceReload = false;
        private readonly string publicRoot;
        private readonly WebSocketServiceHost webSocketHandler;
        private static MapDataServer __instance;

        public MapDataServer()
        {
            __instance = this;

            httpServer = new HttpServer(SERVER_PORT);
            httpServer.AddWebSocketService<WebSocketHandler>("/");
            httpServer.KeepClean = true;

            webSocketHandler = httpServer.WebSocketServices["/"];

            broadcastTimer = new System.Threading.Timer(e =>
            {
                string dataString = "";
                if (forceReload)
                {
                    webSocketHandler.Sessions.Broadcast("reload\n");
                    forceReload = false;
                }
                else
                {
                    dataString = getPlayerResponse(false);
                    if (dataString != lastPlayerResponse)
                    {
                        webSocketHandler.Sessions.Broadcast(dataString);
                        lastPlayerResponse = dataString;
                    }

                    if (newMessages.Count > 0)
                    {
                        List<string> tosend = new List<string>();

                        newMessages.ForEach(message =>
                        {
                            if (WebMapConfig.MAX_MESSAGES < sentMessages.Count) sentMessages.RemoveAt(0);
                            tosend.Add(message.ToJson());
                            sentMessages.Add(message);
                        });
                        if (tosend.Count > 0) webSocketHandler.Sessions.Broadcast("messages\n[" + string.Join(",", tosend) + "]");
                        newMessages.Clear();
                        newMessages.TrimExcess();
                    }
                }
            }, null, TimeSpan.Zero, TimeSpan.FromSeconds(PLAYER_UPDATE_INTERVAL));

            publicRoot = Path.Combine(Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location) ?? string.Empty, "web");

            fileCache = new Dictionary<string, byte[]>();

            httpServer.OnGet += (sender, e) =>
            {
                if (ProcessSpecialRoutes(e)) return;

                ServeStaticFiles(e);
            };
        }

        public string getPlayerResponse(bool sendLast)
        {
            if (sendLast && lastPlayerResponse.Length > 0)
            {
                return lastPlayerResponse;
            }

            string dataString = "players\n";

            players.ForEach(player =>
            {
                ZDO zdoData = null;
                try
                {
                    zdoData = ZDOMan.instance.GetZDO(player.m_characterID);
                }
                catch { }

                if (zdoData != null)
                {
                    Vector3 pos = zdoData.GetPosition();
                    int maxHealth = (int)Math.Ceiling(zdoData.GetFloat("max_health", 25));
                    int health = (int)Math.Ceiling(zdoData.GetFloat("health", maxHealth));
                    int dead = zdoData.GetBool("dead") ? 1 : 0;
                    int pvp = zdoData.GetBool("pvp") ? 1 : 0;
                    int inbed = zdoData.GetBool("inBed") ? 1 : 0;
                    PublicIdentityView identity = PublicIdentity.ForPeer(player.m_uid);

                    maxHealth = Math.Max(maxHealth, health);

                    dataString += $"{identity.Id}\n{identity.Alias}\n{health}\n{maxHealth}\n";
                    if (!player.m_publicRefPos)
                        dataString += "hidden\n";
                    if (player.m_publicRefPos || WebMapConfig.ALWAYS_VISIBLE || WebMapConfig.ALWAYS_MAP)
                        dataString += FormattableString.Invariant($"{pos.x:0.##},{pos.z:0.##}\n");
                    dataString += $"{dead}{pvp}{inbed}\n\n";
                }

            });
            return dataString.Trim();
        }

        public static MapDataServer getInstance()
        {
            return __instance;
        }

        public void Stop()
        {
            broadcastTimer.Dispose();
            httpServer.Stop();
        }

        private void ServeStaticFiles(HttpRequestEventArgs e)
        {
            HttpListenerRequest req = e.Request;
            HttpListenerResponse res = e.Response;

            string rawRequestPath = req.RawUrl;
            if (rawRequestPath == "/") rawRequestPath = "/index.html";

            string[] pathParts = rawRequestPath.Split('/');
            string requestedFile = pathParts[pathParts.Length - 1];
            string[] fileParts = requestedFile.Split('.');
            string fileExt = fileParts[fileParts.Length - 1];

            if (contentTypes.ContainsKey(fileExt))
            {
                byte[] requestedFileBytes = new byte[0];
                if (fileCache.ContainsKey(requestedFile))
                {
                    requestedFileBytes = fileCache[requestedFile];
                }
                else
                {
                    string filePath = Path.Combine(publicRoot, requestedFile);
                    try
                    {
                        requestedFileBytes = File.ReadAllBytes(filePath);
                        if (CACHE_SERVER_FILES) fileCache.Add(requestedFile, requestedFileBytes);
                    }
                    catch (Exception ex)
                    {
                        ZLog.LogError("WebMap: FAILED TO READ FILE! " + ex.Message);
                    }
                }

                if (requestedFileBytes.Length > 0)
                {
                    res.Headers.Add(HttpResponseHeader.CacheControl, "public, max-age=604800, immutable");
                    res.ContentType = contentTypes[fileExt];
                    res.StatusCode = 200;
                    res.ContentLength64 = requestedFileBytes.Length;
                    res.Close(requestedFileBytes, true);
                }
                else
                {
                    res.StatusCode = 404;
                    res.Close();
                }
            }
            else
            {
                res.StatusCode = 404;
                res.Close();
            }
        }

        private bool ProcessSpecialRoutes(HttpRequestEventArgs e)
        {
            HttpListenerRequest req = e.Request;
            HttpListenerResponse res = e.Response;
            string rawRequestPath = req.RawUrl;
            byte[] textBytes;

            switch (rawRequestPath)
            {
                case "/config":
                    res.Headers.Add(HttpResponseHeader.CacheControl, "no-cache");
                    res.ContentType = "application/json";
                    res.StatusCode = 200;
                    textBytes = Encoding.UTF8.GetBytes(MakeClientConfigJson());
                    res.ContentLength64 = textBytes.Length;
                    res.Close(textBytes, true);
                    return true;
                case "/map":
                    // Doing things this way to make the full map harder to accidentally see.
                    res.Headers.Add(HttpResponseHeader.CacheControl, "public, max-age=604800, immutable");
                    res.ContentType = "application/octet-stream";
                    res.StatusCode = 200;
                    res.ContentLength64 = mapImageData.Length;
                    res.Close(mapImageData, true);
                    return true;
                case "/fog":
                    res.Headers.Add(HttpResponseHeader.CacheControl, "no-cache");
                    res.ContentType = "image/png";
                    res.StatusCode = 200;
                    byte[] fogBytes = WebMap.EncodeTextureToPng(fogTexture);
                    res.ContentLength64 = fogBytes.Length;
                    res.Close(fogBytes, true);
                    return true;
                case "/messages":
                    res.Headers.Add(HttpResponseHeader.CacheControl, "no-cache");
                    res.ContentType = "application/json";
                    res.StatusCode = 200;
                    List<string> tosend = new List<string>();
                    sentMessages.ForEach(message =>
                    {
                        tosend.Add(message.ToJson());
                    });
                    textBytes = Encoding.UTF8.GetBytes("[" + string.Join(", ", tosend) + "]");
                    res.ContentLength64 = textBytes.Length;
                    res.Close(textBytes, true);
                    return true;
                case "/pins":
                    res.Headers.Add(HttpResponseHeader.CacheControl, "no-cache");
                    res.ContentType = "text/csv";
                    res.StatusCode = 200;
                    string text = SerializePublicPins();
                    textBytes = Encoding.UTF8.GetBytes(text);
                    res.ContentLength64 = textBytes.Length;
                    res.Close(textBytes, true);
                    return true;
            }

            return false;
        }

        public void Reload()
        {
            forceReload = true;
        }

        public void ListenAsync()
        {
            httpServer.Start();

            if (httpServer.IsListening)
                ZLog.Log($"WebMap: HTTP Server Listening on port {SERVER_PORT}");
            else
                ZLog.LogError("WebMap: HTTP Server Failed To Start !!!");
        }

        public void BroadcastPing(long id, string name, Vector3 position)
        {
            PublicIdentityView identity = PublicIdentity.ForPeer(id);
            webSocketHandler.Sessions.Broadcast($"ping\n{identity.Id}\n{identity.Alias}\n{FixedValue(position.x)},{FixedValue(position.z)}");
        }

        public void BroadcastMessage(long id, int type, string name, string message)
        {
            PublicIdentityView identity = PublicIdentity.ForPeer(id);
            webSocketHandler.Sessions.Broadcast($"message\n{identity.Id}\n{type}\n{identity.Alias}\n{message}");
        }

        public void AddPin(string id, string pinId, string type, string name, Vector3 position, string pinText)
        {
            string privatePin = $"{id},{pinId},{type},{name},{FixedValue(position.x)},{FixedValue(position.z)},{pinText}";
            pins.Add(privatePin);
            if (TrySerializePublicPin(privatePin, out string publicCsv, out string publicSocket))
            {
                webSocketHandler.Sessions.Broadcast(publicSocket);
            }
        }

        public void RemovePin(int idx)
        {
            if (idx < 0 || idx >= pins.Count)
            {
                return;
            }

            string pin = pins[idx];
            pins.RemoveAt(idx);
            if (TrySerializePublicPin(pin, out string publicCsv, out string publicSocket))
            {
                string[] publicParts = publicCsv.Split(',');
                webSocketHandler.Sessions.Broadcast($"rmpin\n{publicParts[1]}");
            }
        }

        public void AddMessage(long id, int type, string name, string message)
        {
            newMessages.Add(new MapMessage(id, type, name, message));
        }

        private string SerializePublicPins()
        {
            List<string> publicPins = new List<string>();
            pins.ForEach(pin =>
            {
                if (TrySerializePublicPin(pin, out string publicCsv, out string publicSocket))
                {
                    publicPins.Add(publicCsv);
                }
            });
            return string.Join("\n", publicPins);
        }

        private static bool TrySerializePublicPin(string privatePin, out string publicCsv, out string publicSocket)
        {
            publicCsv = string.Empty;
            publicSocket = string.Empty;
            if (string.IsNullOrEmpty(privatePin))
            {
                return false;
            }

            string[] pinParts = privatePin.Split(',');
            if (pinParts.Length != 7 || string.IsNullOrWhiteSpace(pinParts[0]) || string.IsNullOrWhiteSpace(pinParts[3]))
            {
                return false;
            }
            if (!Regex.IsMatch(pinParts[1], "^[0-9]+-[0-9]+$") ||
                !Array.Exists(PublicPinTypes, pinType => pinType == pinParts[2]) ||
                !Regex.IsMatch(pinParts[6], "^[a-zA-Z0-9 ]{0,20}$"))
            {
                return false;
            }
            if (!float.TryParse(pinParts[4], NumberStyles.Float, CultureInfo.InvariantCulture, out float x) ||
                !float.TryParse(pinParts[5], NumberStyles.Float, CultureInfo.InvariantCulture, out float z) ||
                float.IsNaN(x) || float.IsInfinity(x) || float.IsNaN(z) || float.IsInfinity(z))
            {
                return false;
            }

            PublicIdentityView identity = PublicIdentity.ForOwner(pinParts[0]);
            string xValue = FixedValue(x);
            string zValue = FixedValue(z);
            publicCsv = $"{identity.Id},{pinParts[1]},{pinParts[2]},{identity.Alias},{xValue},{zValue},{pinParts[6]}";
            publicSocket = $"pin\n{identity.Id}\n{pinParts[1]}\n{pinParts[2]}\n{identity.Alias}\n{xValue},{zValue}\n{pinParts[6]}";
            return true;
        }

        private static string FixedValue(float f)
        {
            return f.ToString("F2", CultureInfo.InvariantCulture);
        }
    }
}

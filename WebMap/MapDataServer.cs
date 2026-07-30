using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;
using WebSocketSharp;
using WebSocketSharp.Net;
using WebSocketSharp.Server;
using static WebMap.WebMapConfig;

namespace WebMap
{
    internal readonly struct PublicIdentityValue
    {
        internal readonly long Id;
        internal readonly string Alias;
        internal PublicIdentityValue(long id, string alias) { Id = id; Alias = alias; }
    }

    internal static class PublicIdentity
    {
        private const long MaxJavaScriptInteger = 9007199254740991L;
        private static readonly object Sync = new object();
        private static readonly Dictionary<string, PublicIdentityValue> Identities = new Dictionary<string, PublicIdentityValue>(StringComparer.Ordinal);
        private static readonly HashSet<long> UsedIds = new HashSet<long>();
        private static readonly RandomNumberGenerator Generator = RandomNumberGenerator.Create();
        private static int nextAlias = 1;

        internal static PublicIdentityValue ForOwner(string owner)
        {
            lock (Sync)
            {
                PublicIdentityValue existing;
                if (Identities.TryGetValue(owner, out existing)) return existing;
                long id;
                byte[] bytes = new byte[8];
                do
                {
                    Generator.GetBytes(bytes);
                    id = (long)(BitConverter.ToUInt64(bytes, 0) & (ulong)MaxJavaScriptInteger);
                } while (id == 0 || !UsedIds.Add(id));
                int aliasNumber = nextAlias++;
                PublicIdentityValue identity = new PublicIdentityValue(id, $"Player {aliasNumber}");
                Identities.Add(owner, identity);
                return identity;
            }
        }
    }

    public class WebSocketHandler : WebSocketBehavior
    {
        private bool playersSent;
        protected override void OnMessage(MessageEventArgs e)
        {
            if (!e.IsText || e.RawData == null || e.RawData.Length > 32 || playersSent ||
                !string.Equals(e.Data, "players", StringComparison.Ordinal))
            {
                Close(CloseStatusCode.PolicyViolation, "invalid request");
                return;
            }
            MapDataServer server = MapDataServer.getInstance();
            if (server == null)
            {
                Close(CloseStatusCode.Away, "unavailable");
                return;
            }
            playersSent = true;
            Send(server.GetPlayerSnapshot());
        }
    }

    public class MapDataServer
    {
        private const string ContentSecurityPolicy = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'";
        private const int MaxPublicOnlineCount = 10000;
        private const int MaxPrivatePinRecordLength = 512;
        private const int MaxOwnerKeyLength = 128;
        private const int MaxPinIdLength = 64;
        private const int MaxPinTypeLength = 32;
        private const int MaxLegacyNameLength = 64;
        private const int MaxPublicPinTextLength = 80;
        private const int MaxCoordinateTextLength = 32;
        private const float MaxPinCoordinate = 12000f;
        private static readonly Dictionary<string, string> contentTypes = new Dictionary<string, string> {
            {"html", "text/html"}, {"js", "text/javascript"}, {"css", "text/css"},
            {"png", "image/png"}, {"jpg", "image/jpeg"}, {"webp", "image/webp"}
        };
        private static MapDataServer __instance;
        private readonly object fileCacheSync = new object();
        private readonly object lifecycleSync = new object();
        private readonly object pinSync = new object();
        private readonly Dictionary<string, byte[]> fileCache = new Dictionary<string, byte[]>(StringComparer.Ordinal);
        private readonly List<string> privatePins = new List<string>();
        private readonly HttpServer httpServer;
        private readonly WebSocketServiceHost webSocketHandler;
        private readonly WebMap owner;
        private readonly string publicRoot;
        private Coroutine publicationCoroutine;
        private bool stopping;
        private volatile bool forceReload;
        private volatile string playerSnapshot = "players\n{\"online\":0}";
        private volatile byte[] configSnapshot = Encoding.UTF8.GetBytes("{}");
        private volatile byte[] mapSnapshot = new byte[0];
        private volatile byte[] pinSnapshot = new byte[0];
        private volatile byte[] fogSnapshot = new byte[0];
        public Texture2D fogTexture;
        public List<ZNetPeer> players = new List<ZNetPeer>();

        public MapDataServer(WebMap owner)
        {
            this.owner = owner;
            __instance = this;
            publicRoot = Path.Combine(Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location) ?? string.Empty, "web");
            httpServer = new HttpServer(SERVER_PORT);
            httpServer.AddWebSocketService<WebSocketHandler>("/");
            httpServer.KeepClean = true;
            webSocketHandler = httpServer.WebSocketServices["/"];
            httpServer.OnGet += (sender, e) =>
            {
                ApplySecurityHeaders(e.Response);
                if (!ProcessSpecialRoutes(e)) ServeStaticFiles(e);
            };
            publicationCoroutine = owner.StartCoroutine(PublishSnapshotsOnMainThread());
        }

        private static void ApplySecurityHeaders(HttpListenerResponse res)
        {
            res.Headers.Add("X-Content-Type-Options", "nosniff");
            res.Headers.Add("Referrer-Policy", "no-referrer");
            res.Headers.Add("X-Frame-Options", "DENY");
            res.Headers.Add("Content-Security-Policy", ContentSecurityPolicy);
        }
        private static void SetNoStore(HttpListenerResponse res) => res.Headers.Add(HttpResponseHeader.CacheControl, "no-store");

        private string BuildPlayerSnapshot(int count)
        {
            int boundedCount = Math.Min(MaxPublicOnlineCount, Math.Max(0, count));
            return "players\n{\"online\":" + boundedCount.ToString(CultureInfo.InvariantCulture) + "}";
        }

        public IEnumerator PublishSnapshotsOnMainThread()
        {
            while (!stopping)
            {
                playerSnapshot = BuildPlayerSnapshot(players == null ? 0 : players.Count);
                configSnapshot = Encoding.UTF8.GetBytes(MakeClientConfigJson());
                PublishPinSnapshot();
                if (fogTexture != null) fogSnapshot = WebMap.EncodeTextureToPng(fogTexture);
                if (forceReload)
                {
                    forceReload = false;
                    webSocketHandler.Sessions.Broadcast("reload");
                }
                yield return new WaitForSeconds(Mathf.Max(0.1f, PLAYER_UPDATE_INTERVAL));
            }
        }

        public static MapDataServer getInstance() => __instance;
        public string GetPlayerSnapshot() => playerSnapshot;

        public void Stop()
        {
            Coroutine coroutine;
            lock (lifecycleSync)
            {
                if (stopping) return;
                stopping = true;
                coroutine = publicationCoroutine;
                publicationCoroutine = null;
                if (ReferenceEquals(__instance, this)) __instance = null;
            }
            if (coroutine != null && owner != null) owner.StopCoroutine(coroutine);
            try
            {
                foreach (string id in new List<string>(webSocketHandler.Sessions.IDs)) webSocketHandler.Sessions.CloseSession(id);
            }
            catch { ZLog.LogWarning("WebMap: websocket shutdown failed"); }
            try { httpServer.Stop(); }
            catch { ZLog.LogWarning("WebMap: HTTP shutdown failed"); }
        }

        private void ServeStaticFiles(HttpRequestEventArgs e)
        {
            HttpListenerRequest req = e.Request;
            HttpListenerResponse res = e.Response;
            string requestPath = req.Url.AbsolutePath;
            if (requestPath == "/") requestPath = "/index.html";
            string requestedFile = Path.GetFileName(requestPath);
            string fileExt = Path.GetExtension(requestedFile).TrimStart('.');
            if (!contentTypes.ContainsKey(fileExt))
            {
                SetNoStore(res); res.StatusCode = 404; res.Close(); return;
            }
            byte[] requestedFileBytes = null;
            lock (fileCacheSync) fileCache.TryGetValue(requestedFile, out requestedFileBytes);
            if (requestedFileBytes == null)
            {
                try
                {
                    requestedFileBytes = File.ReadAllBytes(Path.Combine(publicRoot, requestedFile));
                    CacheStaticFile(requestedFile, requestedFileBytes);
                }
                catch { ZLog.LogError("WebMap: static file read failed"); requestedFileBytes = new byte[0]; }
            }
            if (requestedFileBytes.Length == 0)
            {
                SetNoStore(res); res.StatusCode = 404; res.Close(); return;
            }
            res.Headers.Add(HttpResponseHeader.CacheControl, "public, max-age=604800, immutable");
            res.ContentType = contentTypes[fileExt];
            res.StatusCode = 200;
            res.ContentLength64 = requestedFileBytes.Length;
            res.Close(requestedFileBytes, true);
        }

        private void CacheStaticFile(string name, byte[] contents)
        {
            if (!CACHE_SERVER_FILES) return;
            lock (fileCacheSync) if (!fileCache.ContainsKey(name)) fileCache.Add(name, contents);
        }

        private bool ProcessSpecialRoutes(HttpRequestEventArgs e)
        {
            HttpListenerRequest req = e.Request;
            HttpListenerResponse res = e.Response;
            string requestPath = req.Url.AbsolutePath;
            byte[] bytes;
            switch (requestPath)
            {
                case "/config": bytes = configSnapshot; SetNoStore(res); res.ContentType = "application/json"; break;
                case "/map": bytes = mapSnapshot; res.Headers.Add(HttpResponseHeader.CacheControl, "public, max-age=604800, immutable"); res.ContentType = "application/octet-stream"; break;
                case "/fog": bytes = fogSnapshot; SetNoStore(res); res.ContentType = "image/png"; break;
                case "/pins": bytes = pinSnapshot; SetNoStore(res); res.ContentType = "text/csv"; break;
                default: return false;
            }
            if (bytes == null || bytes.Length == 0)
            {
                SetNoStore(res); res.StatusCode = 404; res.Close(); return true;
            }
            res.StatusCode = 200;
            res.ContentLength64 = bytes.Length;
            res.Close(bytes, true);
            return true;
        }

        public void Reload() => forceReload = true;
        public void ListenAsync()
        {
            httpServer.Start();
            if (httpServer.IsListening) ZLog.Log("WebMap: HTTP server started");
            else ZLog.LogError("WebMap: HTTP server failed");
        }
        public void PublishMap(byte[] bytes) => mapSnapshot = bytes ?? new byte[0];

        public void ReplacePins(IEnumerable<string> pins)
        {
            lock (pinSync)
            {
                privatePins.Clear();
                if (pins != null)
                {
                    foreach (string pin in pins)
                    {
                        string[] parsed;
                        if (TryParsePrivatePin(pin, out parsed)) privatePins.Add(pin);
                    }
                }
            }
            PublishPinSnapshot();
        }
        public string[] GetPrivatePinsSnapshot() { lock (pinSync) return privatePins.ToArray(); }

        public int CountPinsForOwner(string owner)
        {
            int count = 0;
            lock (pinSync)
            {
                foreach (string pin in privatePins)
                {
                    string parsedOwner;
                    if (TryGetPinOwner(pin, out parsedOwner) && string.Equals(parsedOwner, owner, StringComparison.Ordinal)) count++;
                }
            }
            return count;
        }

        public int FindFirstPinIndex(string owner)
        {
            lock (pinSync)
            {
                for (int i = 0; i < privatePins.Count; i++)
                {
                    string parsedOwner;
                    if (TryGetPinOwner(privatePins[i], out parsedOwner) && string.Equals(parsedOwner, owner, StringComparison.Ordinal)) return i;
                }
            }
            return -1;
        }

        public int FindLastPinIndex(string owner, string text = null)
        {
            lock (pinSync)
            {
                for (int i = privatePins.Count - 1; i >= 0; i--)
                {
                    string[] parts;
                    if (!TryParsePrivatePin(privatePins[i], out parts) || !string.Equals(parts[0], owner, StringComparison.Ordinal)) continue;
                    if (text == null || string.Equals(parts[6], text, StringComparison.Ordinal)) return i;
                }
            }
            return -1;
        }

        public void AddPin(string owner, string pinId, string type, Vector3 position, string pinText)
        {
            string record = $"{owner},{pinId},{type},,{FixedValue(position.x)},{FixedValue(position.z)},{pinText ?? string.Empty}";
            string[] parsed;
            if (!TryParsePrivatePin(record, out parsed)) return;
            lock (pinSync) privatePins.Add(record);
            PublishPinSnapshot();
            string publicPin;
            if (TrySerializePublicPin(record, out publicPin))
            {
                string[] parts = publicPin.Split(',');
                webSocketHandler.Sessions.Broadcast($"pin\n{parts[0]}\n{parts[1]}\n{parts[2]}\n{parts[3]}\n{parts[4]},{parts[5]}\n{parts[6]}");
            }
        }

        public void RemovePin(int idx)
        {
            string pinId = null;
            lock (pinSync)
            {
                if (idx < 0 || idx >= privatePins.Count) return;
                string[] parts;
                if (TryParsePrivatePin(privatePins[idx], out parts)) pinId = parts[1];
                privatePins.RemoveAt(idx);
            }
            PublishPinSnapshot();
            if (!string.IsNullOrEmpty(pinId)) webSocketHandler.Sessions.Broadcast("rmpin\n" + pinId);
        }

        private void PublishPinSnapshot()
        {
            string[] source;
            lock (pinSync) source = privatePins.ToArray();
            List<string> serialized = new List<string>();
            foreach (string pin in source)
            {
                string publicPin;
                if (TrySerializePublicPin(pin, out publicPin)) serialized.Add(publicPin);
            }
            pinSnapshot = Encoding.UTF8.GetBytes(string.Join("\n", serialized));
        }

        internal static bool IsValidOwnerKey(string owner) => !string.IsNullOrWhiteSpace(owner) && IsSafeRecordField(owner, MaxOwnerKeyLength, false);
        private static bool IsSafeRecordField(string value, int maxLength, bool allowEmpty)
        {
            if (value == null || value.Length > maxLength || (!allowEmpty && value.Length == 0)) return false;
            for (int i = 0; i < value.Length; i++) if (value[i] == ',' || char.IsControl(value[i])) return false;
            return true;
        }
        private static bool IsSafePinToken(string value, int maxLength)
        {
            if (string.IsNullOrEmpty(value) || value.Length > maxLength) return false;
            for (int i = 0; i < value.Length; i++)
            {
                char c = value[i];
                if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.')) return false;
            }
            return true;
        }
        private static bool IsSafeLegacyName(string value) => IsSafeRecordField(value, MaxLegacyNameLength, true);
        private static bool IsSafePublicPinText(string value) => IsSafeRecordField(value, MaxPublicPinTextLength, true);
        private static bool TryParseCoordinate(string value, out float coordinate)
        {
            coordinate = 0f;
            if (string.IsNullOrEmpty(value) || value.Length > MaxCoordinateTextLength || !string.Equals(value, value.Trim(), StringComparison.Ordinal)) return false;
            NumberStyles style = NumberStyles.AllowLeadingSign | NumberStyles.AllowDecimalPoint;
            if (!float.TryParse(value, style, CultureInfo.InvariantCulture, out coordinate) || float.IsNaN(coordinate) || float.IsInfinity(coordinate) || Math.Abs(coordinate) > MaxPinCoordinate)
            {
                coordinate = 0f; return false;
            }
            return true;
        }
        private static bool TryGetPinOwner(string record, out string owner)
        {
            string[] parts;
            if (!TryParsePrivatePin(record, out parts)) { owner = null; return false; }
            owner = parts[0]; return true;
        }
        private static bool TryParsePrivatePin(string record, out string[] pinParts)
        {
            pinParts = null;
            if (string.IsNullOrWhiteSpace(record) || record.Length > MaxPrivatePinRecordLength || record.IndexOf('\r') >= 0 || record.IndexOf('\n') >= 0) return false;
            string[] parts = record.Split(',');
            if (parts.Length != 7 || !IsValidOwnerKey(parts[0]) || !IsSafePinToken(parts[1], MaxPinIdLength) || !IsSafePinToken(parts[2], MaxPinTypeLength) || !IsSafeLegacyName(parts[3]) || !IsSafePublicPinText(parts[6])) return false;
            float x;
            float z;
            if (!TryParseCoordinate(parts[4], out x) || !TryParseCoordinate(parts[5], out z)) return false;
            pinParts = parts; return true;
        }
        private static bool TrySerializePublicPin(string record, out string serialized)
        {
            serialized = null;
            string[] pinParts;
            if (!TryParsePrivatePin(record, out pinParts) || pinParts.Length != 7) return false;
            PublicIdentityValue identity = PublicIdentity.ForOwner(pinParts[0]);
            serialized = string.Join(",", new[] { identity.Id.ToString(CultureInfo.InvariantCulture), pinParts[1], pinParts[2], identity.Alias, pinParts[4], pinParts[5], pinParts[6] });
            return true;
        }
        private static string FixedValue(float value) => value.ToString("F2", CultureInfo.InvariantCulture);
    }
}

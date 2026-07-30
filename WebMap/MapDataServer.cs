using System;
using System.Collections;
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
    internal readonly struct PublicIdentityValue
    {
        internal readonly long Id;
        internal readonly string Alias;
        internal PublicIdentityValue(long id, string alias) { Id = id; Alias = alias; }
    }

    internal static class PublicIdentity
    {
        internal const int MaxPublicIdentities = 5000;
        private const long MaxJavaScriptInteger = 9007199254740991L;
        private static readonly object Sync = new object();
        private static readonly Dictionary<string, PublicIdentityValue> Identities = new Dictionary<string, PublicIdentityValue>(StringComparer.Ordinal);
        private static readonly HashSet<long> UsedIds = new HashSet<long>();
        private static readonly RandomNumberGenerator Generator = RandomNumberGenerator.Create();
        private static int nextAlias = 1;

        internal static bool TryForOwner(string owner, out PublicIdentityValue identity)
        {
            identity = default(PublicIdentityValue);
            if (owner == null) return false;
            lock (Sync)
            {
                if (Identities.TryGetValue(owner, out identity)) return true;
                if (Identities.Count >= MaxPublicIdentities) return false;
                long id;
                byte[] bytes = new byte[8];
                do
                {
                    Generator.GetBytes(bytes);
                    id = (long)(BitConverter.ToUInt64(bytes, 0) & (ulong)MaxJavaScriptInteger);
                } while (id == 0 || !UsedIds.Add(id));
                int aliasNumber = nextAlias++;
                string alias = $"Player {aliasNumber}";
                identity = new PublicIdentityValue(id, alias);
                Identities.Add(owner, identity);
                return true;
            }
        }

        internal static void ReconcileOwners(ISet<string> retainedOwners)
        {
            lock (Sync)
            {
                if (Identities.Count == 0) return;
                List<string> staleOwners = new List<string>();
                foreach (KeyValuePair<string, PublicIdentityValue> pair in Identities)
                    if (retainedOwners == null || !retainedOwners.Contains(pair.Key)) staleOwners.Add(pair.Key);
                foreach (string owner in staleOwners)
                {
                    PublicIdentityValue identity;
                    if (!Identities.TryGetValue(owner, out identity)) continue;
                    Identities.Remove(owner);
                    UsedIds.Remove(identity.Id);
                }
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
        private sealed class MapPublication
        {
            internal readonly byte[] Bytes;
            internal readonly string Digest;
            internal MapPublication(byte[] bytes, string digest) { Bytes = bytes; Digest = digest; }
        }

        private const string ContentSecurityPolicy = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'";
        private const string ImmutableCacheControl = "public, max-age=604800, immutable";
        private const int MaxPublicOnlineCount = 10000;
        private const int MaxPrivatePins = 5000;
        private const int MaxPrivatePinRecordLength = 512;
        private const int MaxOwnerKeyLength = 128;
        private const int MaxPinIdLength = 64;
        private const int MaxPinTypeLength = 32;
        private const int MaxLegacyNameLength = 64;
        private const int MaxPublicPinTextLength = 80;
        private const int MaxCoordinateTextLength = 32;
        private const float MaxPinCoordinate = 12000f;
        private static readonly Regex HashedMainScript = new Regex("^main\\.[0-9a-f]{16}\\.js$", RegexOptions.CultureInvariant);
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
        private volatile byte[] pinSnapshot = new byte[0];
        private volatile byte[] fogSnapshot = new byte[0];
        private volatile MapPublication mapPublication;
        public Texture2D fogTexture;
        public List<ZNetPeer> players = new List<ZNetPeer>();

        public MapDataServer(WebMap owner)
        {
            this.owner = owner;
            publicRoot = Path.Combine(Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location) ?? string.Empty, "web");
            configSnapshot = Encoding.UTF8.GetBytes(MakeClientConfigJson(string.Empty));
            httpServer = new HttpServer(SERVER_PORT);
            httpServer.AddWebSocketService<WebSocketHandler>("/");
            httpServer.KeepClean = true;
            webSocketHandler = httpServer.WebSocketServices["/"];
            httpServer.OnGet += (sender, e) =>
            {
                ApplySecurityHeaders(e.Response);
                SetNoStore(e.Response);
                try
                {
                    if (!ProcessSpecialRoutes(e)) ServeStaticFiles(e);
                }
                catch
                {
                    ZLog.LogError("WebMap: HTTP request failed");
                    SetNoStore(e.Response);
                    e.Response.StatusCode = 500;
                    e.Response.Close();
                }
            };
            publicationCoroutine = owner.StartCoroutine(PublishSnapshotsOnMainThread());
            __instance = this;
        }

        private static void ApplySecurityHeaders(HttpListenerResponse res)
        {
            res.Headers.Set("X-Content-Type-Options", "nosniff");
            res.Headers.Set("Referrer-Policy", "no-referrer");
            res.Headers.Set("X-Frame-Options", "DENY");
            res.Headers.Set("Content-Security-Policy", ContentSecurityPolicy);
        }
        private static void SetNoStore(HttpListenerResponse res) => res.Headers.Set(HttpResponseHeader.CacheControl, "no-store");
        private static void SetImmutable(HttpListenerResponse res) => res.Headers.Set(HttpResponseHeader.CacheControl, ImmutableCacheControl);

        private string BuildPlayerSnapshot(int count)
        {
            int boundedCount = Math.Min(MaxPublicOnlineCount, Math.Max(0, count));
            return "players\n{" + '"' + "online" + '"' + ":" + boundedCount.ToString(CultureInfo.InvariantCulture) + "}";
        }

        public IEnumerator PublishSnapshotsOnMainThread()
        {
            while (!stopping)
            {
                playerSnapshot = BuildPlayerSnapshot(players == null ? 0 : players.Count);
                MapPublication publication = mapPublication;
                configSnapshot = Encoding.UTF8.GetBytes(MakeClientConfigJson(publication == null ? string.Empty : publication.Digest));
                PublishPinSnapshot();
                if (fogTexture != null) fogSnapshot = WebMap.EncodeTextureToPng(fogTexture);
                if (forceReload)
                {
                    forceReload = false;
                    webSocketHandler.Sessions.Broadcast("reload");
                }
                yield return new WaitForSeconds(PLAYER_UPDATE_INTERVAL);
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
            try
            {
                if (coroutine != null && owner != null) owner.StopCoroutine(coroutine);
            }
            catch { ZLog.LogWarning("WebMap: publication coroutine shutdown failed"); }
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
                catch (IOException) { ZLog.LogError("WebMap: static file read failed"); requestedFileBytes = new byte[0]; }
                catch (UnauthorizedAccessException) { ZLog.LogError("WebMap: static file read failed"); requestedFileBytes = new byte[0]; }
            }
            if (requestedFileBytes.Length == 0)
            {
                SetNoStore(res); res.StatusCode = 404; res.Close(); return;
            }
            if (requestedFile == "index.html" || !IsHashedMainScript(requestedFile)) SetNoStore(res);
            else SetImmutable(res);
            res.ContentType = contentTypes[fileExt];
            res.StatusCode = 200;
            res.ContentLength64 = requestedFileBytes.Length;
            res.Close(requestedFileBytes, true);
        }

        private static bool IsHashedMainScript(string requestedFile) => HashedMainScript.IsMatch(requestedFile ?? string.Empty);

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
                case "/config":
                    bytes = configSnapshot;
                    SetNoStore(res);
                    res.ContentType = "application/json";
                    break;
                case "/map":
                    MapPublication publication = mapPublication;
                    string[] values = req.QueryString.GetValues("v");
                    if (publication == null || req.QueryString.Count != 1 ||
                        !string.Equals(req.QueryString.AllKeys[0], "v", StringComparison.Ordinal) ||
                        values == null || values.Length != 1 || !IsValidMapDigest(values[0]) ||
                        !FixedTimeEquals(values[0], publication.Digest))
                    {
                        SetNoStore(res); res.StatusCode = 404; res.Close(); return true;
                    }
                    bytes = publication.Bytes;
                    SetImmutable(res);
                    res.ContentType = "application/octet-stream";
                    break;
                case "/fog":
                    bytes = fogSnapshot;
                    SetNoStore(res);
                    res.ContentType = "image/png";
                    break;
                case "/pins":
                    bytes = pinSnapshot;
                    SetNoStore(res);
                    res.ContentType = "text/csv";
                    break;
                default:
                    return false;
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

        private static bool IsValidMapDigest(string value)
        {
            if (value == null || value.Length != 64) return false;
            for (int i = 0; i < value.Length; i++)
            {
                char c = value[i];
                if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
            }
            return true;
        }

        private static bool FixedTimeEquals(string left, string right)
        {
            if (left == null || right == null || left.Length != right.Length) return false;
            int difference = 0;
            for (int i = 0; i < left.Length; i++) difference |= left[i] ^ right[i];
            return difference == 0;
        }

        public void Reload() => forceReload = true;
        public void ListenAsync()
        {
            try
            {
                httpServer.Start();
                if (!httpServer.IsListening) throw new InvalidOperationException();
                ZLog.Log("WebMap: HTTP server started");
            }
            catch
            {
                Stop();
                if (ReferenceEquals(WebMap.mapDataServer, this)) WebMap.mapDataServer = null;
                throw;
            }
        }

        public void PublishMap(byte[] bytes)
        {
            if (bytes == null || bytes.Length == 0)
            {
                mapPublication = null;
                configSnapshot = Encoding.UTF8.GetBytes(MakeClientConfigJson(string.Empty));
                return;
            }
            byte[] ownedBytes = (byte[])bytes.Clone();
            string mapDigest;
            using (SHA256 algorithm = SHA256.Create())
                mapDigest = BitConverter.ToString(algorithm.ComputeHash(ownedBytes)).Replace("-", string.Empty).ToLowerInvariant();
            mapPublication = new MapPublication(ownedBytes, mapDigest);
            configSnapshot = Encoding.UTF8.GetBytes(MakeClientConfigJson(mapDigest));
        }

        public void ReplacePins(IEnumerable<string> pins)
        {
            lock (pinSync)
            {
                privatePins.Clear();
                if (pins != null)
                {
                    foreach (string pin in pins)
                    {
                        if (privatePins.Count >= MaxPrivatePins) break;
                        string[] parsed;
                        if (TryParsePrivatePin(pin, out parsed)) privatePins.Add(pin);
                    }
                }
                PublicIdentity.ReconcileOwners(GetRetainedOwnersLocked());
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
            string publicPin;
            lock (pinSync)
            {
                if (privatePins.Count >= MaxPrivatePins) return;
                PublicIdentity.ReconcileOwners(GetRetainedOwnersLocked());
                PublicIdentityValue identity;
                if (!PublicIdentity.TryForOwner(parsed[0], out identity)) return;
                privatePins.Add(record);
                publicPin = SerializePublicPin(parsed, identity);
            }
            PublishPinSnapshot();
            string[] parts = publicPin.Split(',');
            webSocketHandler.Sessions.Broadcast($"pin\n{parts[0]}\n{parts[1]}\n{parts[2]}\n{parts[3]}\n{parts[4]},{parts[5]}\n{parts[6]}");
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
                PublicIdentity.ReconcileOwners(GetRetainedOwnersLocked());
            }
            PublishPinSnapshot();
            if (!string.IsNullOrEmpty(pinId)) webSocketHandler.Sessions.Broadcast("rmpin\n" + pinId);
        }

        private HashSet<string> GetRetainedOwnersLocked()
        {
            HashSet<string> owners = new HashSet<string>(StringComparer.Ordinal);
            foreach (string pin in privatePins)
            {
                string owner;
                if (TryGetPinOwner(pin, out owner)) owners.Add(owner);
            }
            return owners;
        }

        private void PublishPinSnapshot()
        {
            lock (pinSync)
            {
                List<string> serialized = new List<string>(Math.Min(privatePins.Count, MaxPrivatePins));
                foreach (string pin in privatePins)
                {
                    string publicPin;
                    if (TrySerializePublicPin(pin, out publicPin)) serialized.Add(publicPin);
                }
                pinSnapshot = Encoding.UTF8.GetBytes(string.Join("\n", serialized));
            }
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
            PublicIdentityValue identity;
            if (!PublicIdentity.TryForOwner(pinParts[0], out identity)) return false;
            serialized = SerializePublicPin(pinParts, identity);
            return true;
        }
        private static string SerializePublicPin(string[] pinParts, PublicIdentityValue identity) =>
            string.Join(",", new[] { identity.Id.ToString(CultureInfo.InvariantCulture), pinParts[1], pinParts[2], identity.Alias, pinParts[4], pinParts[5], pinParts[6] });
        private static string FixedValue(float value) => value.ToString("F2", CultureInfo.InvariantCulture);
    }
}

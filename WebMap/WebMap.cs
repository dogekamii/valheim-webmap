using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text.RegularExpressions;
using BepInEx;
using HarmonyLib;
using UnityEngine;
using WebMap.Patches;
using static ZRoutedRpc;
using Random = UnityEngine.Random;

namespace WebMap
{
    [BepInPlugin(GUID, NAME, VERSION)]
    public class WebMap : BaseUnityPlugin
    {
        public const string GUID = "com.github.h0tw1r3.valheim.webmap";
        public const string NAME = "WebMap";
        public const string VERSION = "2.7.4";
        private static readonly string[] ALLOWED_PINS = { "dot", "fire", "mine", "house", "cave" };

        public DiscordWebHook discordWebHook;
        public static MapDataServer mapDataServer;
        public static string worldDataPath;
        public static string mapDataPath;
        public static string pluginPath;
        public static int sayMethodHash;
        public static int chatMessageMethodHash;
        public static bool fogTextureNeedsSaving;
        public static string currentWorldName;
        public static Dictionary<string, object> serverInfo;
        public static WebMap instance;
        private static Harmony harmony;
        private bool mapServerStarted;

        private enum PinCommand { None, Add, Undo, Delete }

        public void Awake()
        {
            instance = this;
            harmony = new Harmony(GUID);
            harmony.PatchAll(Assembly.GetExecutingAssembly());
            pluginPath = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
            mapDataPath = Path.Combine(pluginPath ?? string.Empty, "map_data");
            Directory.CreateDirectory(mapDataPath);
            WebMapConfig.ReadConfigFile(Config);
            discordWebHook = new DiscordWebHook(WebMapConfig.DISCORD_WEBHOOK);
        }

        public void OnDestroy()
        {
            mapDataServer?.Stop();
            mapDataServer = null;
            discordWebHook?.Dispose();
            discordWebHook = null;
            Config.Save();
            if (ReferenceEquals(instance, this)) instance = null;
        }

        public void Online()
        {
            StartCoroutine(SaveFogTextureLoop());
            StartCoroutine(UpdateFogTextureLoop());
            NotifyOnline();
        }

        public static byte[] EncodeTextureToPng(Texture2D texture)
        {
            MethodInfo legacyMethod = AccessTools.Method(typeof(Texture2D), "EncodeToPNG", Type.EmptyTypes);
            if (legacyMethod != null) return (byte[])legacyMethod.Invoke(texture, null);
            Type imageConversionType = AccessTools.TypeByName("UnityEngine.ImageConversion");
            MethodInfo currentMethod = AccessTools.Method(imageConversionType, "EncodeToPNG", new[] { typeof(Texture2D) });
            if (currentMethod != null) return (byte[])currentMethod.Invoke(null, new object[] { texture });
            throw new MissingMethodException("Unity image encoding API is unavailable");
        }

        public static void LoadTextureFromImage(Texture2D texture, byte[] imageData)
        {
            MethodInfo legacyMethod = AccessTools.Method(typeof(Texture2D), "LoadImage", new[] { typeof(byte[]) });
            if (legacyMethod != null)
            {
                legacyMethod.Invoke(texture, new object[] { imageData });
                return;
            }
            Type imageConversionType = AccessTools.TypeByName("UnityEngine.ImageConversion");
            MethodInfo currentMethod = AccessTools.Method(imageConversionType, "LoadImage", new[] { typeof(Texture2D), typeof(byte[]) });
            if (currentMethod != null)
            {
                currentMethod.Invoke(null, new object[] { texture, imageData });
                return;
            }
            throw new MissingMethodException("Unity image decoding API is unavailable");
        }

        public void SetServerInfo(bool openServer, bool publicServer, string serverName, string password, string worldName, string worldSeed)
        {
            serverInfo = new Dictionary<string, object>();
            serverInfo.Add("serverName", serverName ?? string.Empty);
        }

        public void NotifyOnline() => discordWebHook?.SendMessage("Server is online");
        public void NotifyOffline() => discordWebHook?.SendMessage("Server is offline");

        public void NotifyJoin(ZNetPeer peer)
        {
            QuorumActivityJournal.AppendJoin(peer);
            discordWebHook?.SendMessage("A player joined");
        }

        public void NotifyLeave(ZNetPeer peer)
        {
            QuorumActivityJournal.AppendLeave(peer);
            discordWebHook?.SendMessage("A player left");
        }

        public void NewWorld()
        {
            string worldName = WebMapConfig.GetWorldName();
            bool forceReload = currentWorldName != worldName;
            worldDataPath = Path.Combine(mapDataPath, worldName);
            Directory.CreateDirectory(worldDataPath);

            if (mapDataServer == null)
            {
                ZLog.Log("WebMap: world data loading");
                mapDataServer = new MapDataServer(this);
            }
            else if (forceReload)
            {
                ZLog.Log("WebMap: world data changed");
            }
            currentWorldName = worldName;

            try
            {
                mapDataServer.PublishMap(File.ReadAllBytes(Path.Combine(worldDataPath, "map.png")));
            }
            catch
            {
                ZLog.LogWarning("WebMap: map image unavailable");
            }

            try
            {
                Texture2D loadedFog = new Texture2D(WebMapConfig.TEXTURE_SIZE, WebMapConfig.TEXTURE_SIZE);
                LoadTextureFromImage(loadedFog, File.ReadAllBytes(Path.Combine(worldDataPath, "fog.png")));
                mapDataServer.fogTexture = loadedFog;
            }
            catch
            {
                ZLog.LogWarning("WebMap: fog image unavailable; creating blank fog");
                Texture2D blankFog = new Texture2D(WebMapConfig.TEXTURE_SIZE, WebMapConfig.TEXTURE_SIZE, TextureFormat.R8, false);
                Color32[] colors = new Color32[WebMapConfig.TEXTURE_SIZE * WebMapConfig.TEXTURE_SIZE];
                for (int i = 0; i < colors.Length; i++) colors[i] = Color.black;
                blankFog.SetPixels32(colors);
                mapDataServer.fogTexture = blankFog;
                try { File.WriteAllBytes(Path.Combine(worldDataPath, "fog.png"), EncodeTextureToPng(blankFog)); }
                catch { ZLog.LogError("WebMap: fog image write failed"); }
            }

            try { mapDataServer.ReplacePins(File.ReadAllLines(Path.Combine(worldDataPath, "pins.csv"))); }
            catch { mapDataServer.ReplacePins(Array.Empty<string>()); }
            if (forceReload) mapDataServer.Reload();
        }

        public IEnumerator UpdateFogTextureLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(WebMapConfig.UPDATE_FOG_TEXTURE_INTERVAL);
                UpdateFogTexture();
            }
        }

        public void UpdateFogTexture()
        {
            if (mapDataServer == null || mapDataServer.fogTexture == null ||
                (!WebMapConfig.ALWAYS_MAP && !WebMapConfig.ALWAYS_VISIBLE)) return;
            int radius = (int)Mathf.Ceil(WebMapConfig.EXPLORE_RADIUS / WebMapConfig.PIXEL_SIZE);
            int radiusSquared = radius * radius;
            int half = WebMapConfig.TEXTURE_SIZE / 2;
            foreach (ZNetPeer player in mapDataServer.players)
            {
                ZDO zdo = null;
                try { zdo = ZDOMan.instance.GetZDO(player.m_characterID); } catch { }
                if (zdo == null) continue;
                Vector3 position = zdo.GetPosition();
                int pixelX = Mathf.RoundToInt(position.x / WebMapConfig.PIXEL_SIZE + half);
                int pixelY = Mathf.RoundToInt(position.z / WebMapConfig.PIXEL_SIZE + half);
                for (int y = pixelY - radius; y <= pixelY + radius; y++)
                for (int x = pixelX - radius; x <= pixelX + radius; x++)
                {
                    if (y < 0 || x < 0 || y >= WebMapConfig.TEXTURE_SIZE || x >= WebMapConfig.TEXTURE_SIZE) continue;
                    int dx = pixelX - x;
                    int dy = pixelY - y;
                    if (dx * dx + dy * dy >= radiusSquared) continue;
                    if (mapDataServer.fogTexture.GetPixel(x, y) != Color.white)
                    {
                        fogTextureNeedsSaving = true;
                        mapDataServer.fogTexture.SetPixel(x, y, Color.white);
                    }
                }
            }
        }

        public IEnumerator SaveFogTextureLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(WebMapConfig.SAVE_FOG_TEXTURE_INTERVAL);
                SaveFogTexture();
            }
        }

        public void SaveFogTexture()
        {
            if (mapDataServer == null || mapDataServer.players.Count == 0 || !fogTextureNeedsSaving) return;
            byte[] bytes = EncodeTextureToPng(mapDataServer.fogTexture);
            try
            {
                File.WriteAllBytes(Path.Combine(worldDataPath, "fog.png"), bytes);
                fogTextureNeedsSaving = false;
            }
            catch { ZLog.LogError("WebMap: fog image write failed"); }
        }

        public static void SavePins()
        {
            try { File.WriteAllLines(Path.Combine(worldDataPath, "pins.csv"), mapDataServer.GetPrivatePinsSnapshot()); }
            catch { ZLog.LogError("WebMap: pin file write failed"); }
        }

        [HarmonyPatch(typeof(ZoneSystem), nameof(ZoneSystem.Start))]
        private class ZoneSystemPatch
        {
            private static readonly Color DeepWaterColor = new Color(0.36105883f, 0.36105883f, 0.43137255f);
            private static readonly Color ShallowWaterColor = new Color(0.574f, 0.50709206f, 0.47892025f);
            private static readonly Color ShoreColor = new Color(0.1981132f, 0.12241901f, 0.1503943f);

            private static Color GetMaskColor(float wx, float wy, float height, Heightmap.Biome biome)
            {
                Color empty = new Color(0f, 0f, 0f, 0f);
                Color forest = new Color(1f, 0f, 0f, 0f);
                if (height < ZoneSystem.instance.m_waterLevel) return empty;
                if (biome == Heightmap.Biome.Meadows) return WorldGenerator.InForest(new Vector3(wx, 0f, wy)) ? forest : empty;
                if (biome == Heightmap.Biome.Plains) return WorldGenerator.GetForestFactor(new Vector3(wx, 0f, wy)) < 0.8f ? forest : empty;
                return biome == Heightmap.Biome.BlackForest || biome == Heightmap.Biome.Mistlands ? forest : empty;
            }

            private static Color GetPixelColor(Heightmap.Biome biome)
            {
                switch (biome)
                {
                    case Heightmap.Biome.Meadows: return new Color(0.573f, 0.655f, 0.361f);
                    case Heightmap.Biome.Swamp: return new Color(0.639f, 0.447f, 0.345f);
                    case Heightmap.Biome.BlackForest: return new Color(0.420f, 0.455f, 0.247f);
                    case Heightmap.Biome.Plains: return new Color(0.906f, 0.671f, 0.470f);
                    case Heightmap.Biome.AshLands: return new Color(0.690f, 0.192f, 0.192f);
                    case Heightmap.Biome.Mistlands: return new Color(0.36f, 0.22f, 0.4f);
                    default: return Color.white;
                }
            }

            private static void Postfix()
            {
                WebMap.instance.NewWorld();
                if (mapDataServer == null) return;
                try
                {
                    int size = WebMapConfig.TEXTURE_SIZE;
                    int half = size / 2;
                    float offset = WebMapConfig.PIXEL_SIZE / 2f;
                    Color mask;
                    Color32[] baseColors = new Color32[size * size];
                    float[] heights = new float[size * size];
                    for (int y = 0; y < size; y++)
                    for (int x = 0; x < size; x++)
                    {
                        float wx = (x - half) * WebMapConfig.PIXEL_SIZE + offset;
                        float wy = (y - half) * WebMapConfig.PIXEL_SIZE + offset;
                        Heightmap.Biome biome = WorldGenerator.instance.GetBiome(wx, wy);
                        heights[y * size + x] = WorldGenerator.instance.GetBiomeHeight(biome, wx, wy, out mask);
                        baseColors[y * size + x] = GetPixelColor(biome);
                        GetMaskColor(wx, wy, heights[y * size + x], biome);
                    }
                    float water = ZoneSystem.instance.m_waterLevel;
                    Vector3 sun = new Vector3(-0.57735f, 0.57735f, 0.57735f);
                    Color[] colors = new Color[baseColors.Length];
                    for (int i = 0; i < baseColors.Length; i++)
                    {
                        int up = i - size < 0 ? i : i - size;
                        int down = i + size >= baseColors.Length ? i : i + size;
                        int left = i - 1 < 0 ? i : i - 1;
                        int right = i + 1 >= baseColors.Length ? i : i + 1;
                        Vector3 a = new Vector3(2f, 0f, heights[right] - heights[left]).normalized;
                        Vector3 b = new Vector3(0f, 2f, heights[up] - heights[down]).normalized;
                        float light = Vector3.Dot(Vector3.Cross(a, b), sun) * 0.25f + 0.75f;
                        float shore = Mathf.Clamp(heights[i] - water, 0, 1);
                        float shallow = Mathf.Clamp((heights[i] - water + 2.5f) * 0.5f, 0, 1);
                        float deep = Mathf.Clamp((heights[i] - water + 12.5f) * 0.1f, 0, 1);
                        Color value = Color.Lerp(ShoreColor, baseColors[i], shore);
                        value = Color.Lerp(ShallowWaterColor, value, shallow);
                        value = Color.Lerp(DeepWaterColor, value, deep);
                        colors[i] = new Color(value.r * light, value.g * light, value.b * light, value.a);
                    }
                    Texture2D texture = new Texture2D(size, size, TextureFormat.RGBA32, false);
                    texture.SetPixels(colors);
                    byte[] bytes = EncodeTextureToPng(texture);
                    mapDataServer.PublishMap(bytes);
                    File.WriteAllBytes(Path.Combine(worldDataPath, "map.png"), bytes);
                    ZLog.Log("WebMap: map image ready");
                }
                catch { ZLog.LogError("WebMap: map image build failed"); }
            }
        }

        public void StartMapServerOnce()
        {
            if (mapServerStarted) return;
            if (mapDataServer == null)
            {
                ZLog.LogError("WebMap: map server unavailable");
                return;
            }
            ZoneSystem.LocationInstance location;
            if (ZoneSystem.instance.FindClosestLocation("StartTemple", Vector3.zero, out location))
                WebMapConfig.WORLD_START_POS = location.m_position;
            try
            {
                mapDataServer.ListenAsync();
                mapServerStarted = true;
            }
            catch
            {
                ZLog.LogError("WebMap: HTTP server start failed");
                return;
            }
            try { Online(); } catch { ZLog.LogError("WebMap: online initialization failed"); }
        }

        [HarmonyPatch(typeof(ZNet), "WorldSetup")]
        private class ZNetWorldSetupPatch { private static void Postfix() => WebMap.instance.StartMapServerOnce(); }

        [HarmonyPatch(typeof(ZNet), nameof(ZNet.Start))]
        private class ZNetPatchStart
        {
            private static void Postfix(List<ZNetPeer> ___m_peers)
            {
                if (mapDataServer != null) mapDataServer.players = ___m_peers;
            }
        }

        [HarmonyPatch(typeof(ZNet), nameof(ZNet.Shutdown))]
        private class ZNetPatchShutdown
        {
            private static void Postfix()
            {
                mapDataServer?.Stop();
                WebMap.instance?.NotifyOffline();
            }
        }

        [HarmonyPatch(typeof(ZNet), nameof(ZNet.SetServer))]
        private class ZNetPatchSetServer
        {
            private static void Postfix(bool server, bool openServer, bool publicServer, string serverName, string password, World world)
            {
                WebMap.instance.SetServerInfo(openServer, publicServer, serverName, password, world.m_name, world.m_seedName);
            }
        }

        [HarmonyPatch(typeof(ZNet), nameof(ZNet.Disconnect))]
        private class ZNetPatchDisconnect
        {
            private static void Prefix(ref ZNetPeer peer)
            {
                if (peer != null && !peer.m_server && peer.m_uid != 0L) WebMap.instance.NotifyLeave(peer);
            }
        }

        [HarmonyPatch(typeof(ZRoutedRpc), nameof(ZRoutedRpc.AddPeer))]
        private class ZRoutedRpcAddPeerPatch
        {
            private static void Postfix(ZNetPeer peer)
            {
                if (peer != null && !peer.m_server && peer.m_uid != 0L) WebMap.instance.NotifyJoin(peer);
            }
        }

        private static bool TryParseCommand(string message, out PinCommand command, out string arguments)
        {
            command = PinCommand.None;
            arguments = string.Empty;
            if (string.IsNullOrWhiteSpace(message)) return false;
            string[] tokens = { "!PIN", "!UNDOPIN", "!DELETEPIN" };
            PinCommand[] commands = { PinCommand.Add, PinCommand.Undo, PinCommand.Delete };
            for (int i = 0; i < tokens.Length; i++)
            {
                string token = tokens[i];
                if (message.Length < token.Length || !message.StartsWith(token, StringComparison.OrdinalIgnoreCase)) continue;
                if (message.Length > token.Length && !char.IsWhiteSpace(message[token.Length])) continue;
                command = commands[i];
                arguments = message.Substring(token.Length).Trim();
                return true;
            }
            return false;
        }

        [HarmonyPatch(typeof(ZRoutedRpc), nameof(ZRoutedRpc.HandleRoutedRPC))]
        private class ZRoutedRpcPatch
        {
            private static readonly string[] ignoreRpc = { "DestroyZDO", "SetEvent", "OnTargeted", "Step" };

            private static void Postfix(ref ZRoutedRpc __instance, ref RoutedRPCData data)
            {
                string methodName = StringExtensionMethods_Patch.GetStableHashName(data?.m_methodHash ?? 0);
                if (Array.Exists(ignoreRpc, x => x == methodName)) return;
                ZNetPeer peer = ZNet.instance.GetPeer(data.m_senderPeerID);
                if (peer == null || mapDataServer == null) return;
                if (data?.m_methodHash != sayMethodHash && data?.m_methodHash != "Say".GetStableHashCode()) return;
                sayMethodHash = data.m_methodHash;
                try
                {
                    ZPackage package = data.m_parameters;
                    package.ReadInt();
                    UserInfo userInfo = new UserInfo();
                    userInfo.Deserialize(ref package);
                    string message = (package.ReadString() ?? string.Empty).Trim();
                    PinCommand command;
                    string arguments;
                    if (!TryParseCommand(message, out command, out arguments)) return;
                    string ownerKey = peer.m_rpc.GetSocket().GetHostName();
                    if (!MapDataServer.IsValidOwnerKey(ownerKey)) return;

                    if (command == PinCommand.Undo)
                    {
                        int index = mapDataServer.FindLastPinIndex(ownerKey);
                        if (index >= 0) { mapDataServer.RemovePin(index); SavePins(); }
                        return;
                    }
                    if (command == PinCommand.Delete)
                    {
                        int index = mapDataServer.FindLastPinIndex(ownerKey, arguments);
                        if (index >= 0) { mapDataServer.RemovePin(index); SavePins(); }
                        return;
                    }

                    ZDO zdo = ZDOMan.instance.GetZDO(peer.m_characterID);
                    if (zdo == null) return;
                    string[] parts = arguments.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
                    string type = "dot";
                    int textStart = 0;
                    if (parts.Length > 0 && Array.Exists(ALLOWED_PINS, value => string.Equals(value, parts[0], StringComparison.OrdinalIgnoreCase)))
                    {
                        type = parts[0].ToLowerInvariant();
                        textStart = 1;
                    }
                    string text = textStart < parts.Length ? string.Join(" ", parts, textStart, parts.Length - textStart) : string.Empty;
                    if (text.Length > 20) text = text.Substring(0, 20);
                    text = Regex.Replace(text, "[^a-zA-Z0-9 ]", string.Empty);
                    long timestamp = new DateTimeOffset(DateTime.UtcNow).ToUnixTimeSeconds();
                    string pinId = $"{timestamp}-{Random.Range(1000, 9999)}";
                    mapDataServer.AddPin(ownerKey, pinId, type, zdo.GetPosition(), text);
                    while (mapDataServer.CountPinsForOwner(ownerKey) > WebMapConfig.MAX_PINS_PER_USER)
                    {
                        int index = mapDataServer.FindFirstPinIndex(ownerKey);
                        if (index < 0) break;
                        mapDataServer.RemovePin(index);
                    }
                    SavePins();
                }
                catch { ZLog.LogWarning("WebMap: pin command ignored"); }
            }
        }
    }
}

using System;
using System.Collections.Generic;
using BepInEx.Configuration;
using UnityEngine;

namespace WebMap
{
    internal static class WebMapConfig
    {
        public static int TEXTURE_SIZE = 2048;
        public static int PIXEL_SIZE = 12;
        public static float EXPLORE_RADIUS = 100f;
        public static float UPDATE_FOG_TEXTURE_INTERVAL = 2f;
        public static float SAVE_FOG_TEXTURE_INTERVAL = 30f;
        public static int MAX_PINS_PER_USER = 50;
        public static bool ALWAYS_MAP = true;
        public static bool ALWAYS_VISIBLE = false;
        public static string WORLD_VISIBILITY_MODE = "fogged";
        public static bool DEBUG = false;
        public static bool TEST = false;
        public static bool QUORUM_ACTIVITY_JOURNAL_ENABLED = false;
        public static int SERVER_PORT = 3000;
        public static float PLAYER_UPDATE_INTERVAL = 1f;
        public static bool CACHE_SERVER_FILES = true;
        public static string WORLD_NAME = "";
        public static Vector3 WORLD_START_POS = Vector3.zero;
        public static int DEFAULT_ZOOM = 100;
        public static string DISCORD_WEBHOOK = "";
        public static string DISCORD_INVITE_URL = "";
        public static string URL = "";

        private static readonly HashSet<string> WORLD_VISIBILITY_MODES = new HashSet<string> { "fogged", "hybrid", "full" };

        public static void ReadConfigFile(ConfigFile config)
        {
            TEXTURE_SIZE = config.Bind("Texture", "texture_size", TEXTURE_SIZE, "Map texture size.").Value;
            PIXEL_SIZE = config.Bind("Texture", "pixel_size", PIXEL_SIZE, "World units per map pixel.").Value;
            EXPLORE_RADIUS = config.Bind("Texture", "explore_radius", EXPLORE_RADIUS, "Fog reveal radius.").Value;
            UPDATE_FOG_TEXTURE_INTERVAL = config.Bind("Interval", "update_fog_texture_interval", UPDATE_FOG_TEXTURE_INTERVAL, "Fog update interval.").Value;
            SAVE_FOG_TEXTURE_INTERVAL = config.Bind("Interval", "save_fog_texture_interval", SAVE_FOG_TEXTURE_INTERVAL, "Fog save interval.").Value;
            MAX_PINS_PER_USER = config.Bind("User", "max_pins_per_user", MAX_PINS_PER_USER, "Maximum pins per user.").Value;
            SERVER_PORT = config.Bind("Server", "server_port", SERVER_PORT, "HTTP port.").Value;
            PLAYER_UPDATE_INTERVAL = config.Bind("Interval", "player_update_interval", PLAYER_UPDATE_INTERVAL, "Aggregate snapshot interval.").Value;
            CACHE_SERVER_FILES = config.Bind("Server", "cache_server_files", CACHE_SERVER_FILES, "Cache static files.").Value;
            DEFAULT_ZOOM = config.Bind("Texture", "default_zoom", DEFAULT_ZOOM, "Initial map zoom.").Value;
            ALWAYS_MAP = config.Bind("User", "always_map", ALWAYS_MAP, "Reveal traveled fog.").Value;
            ALWAYS_VISIBLE = config.Bind("User", "always_visible", ALWAYS_VISIBLE, "Legacy visibility option.").Value;
            WORLD_VISIBILITY_MODE = config.Bind("World", "world_visibility_mode", WORLD_VISIBILITY_MODE,
                new ConfigDescription("Browser fog policy.", new AcceptableValueList<string>("fogged", "hybrid", "full"))).Value;
            DEBUG = config.Bind("Server", "debug", DEBUG, "Enable constant diagnostic categories.").Value;
            TEST = config.Bind("Server", "test", TEST, "Enable test features.").Value;
            QUORUM_ACTIVITY_JOURNAL_ENABLED = config.Bind("Quorum Bot", "activity_journal_enabled", QUORUM_ACTIVITY_JOURNAL_ENABLED, "Append private local activity records.").Value;
            DISCORD_WEBHOOK = config.Bind("Server", "discord_webhook", DISCORD_WEBHOOK, "Discord webhook URL.").Value;
            DISCORD_INVITE_URL = config.Bind("Server", "discord_invite_url", DISCORD_INVITE_URL, "Optional Discord invite URL.").Value;
            URL = config.Bind("Server", "webmap_url", URL, "Web map URL.").Value;
            ValidateSettings();
        }

        private static void ValidateSettings()
        {
            TEXTURE_SIZE = ClampInt(TEXTURE_SIZE, 256, 2048);
            PIXEL_SIZE = ClampInt(PIXEL_SIZE, 2, 100);
            EXPLORE_RADIUS = ClampFinite(EXPLORE_RADIUS, 100f, 0f, 500f);
            UPDATE_FOG_TEXTURE_INTERVAL = ClampFinite(UPDATE_FOG_TEXTURE_INTERVAL, 2f, 0.25f, 3600f);
            SAVE_FOG_TEXTURE_INTERVAL = ClampFinite(SAVE_FOG_TEXTURE_INTERVAL, 30f, 1f, 86400f);
            PLAYER_UPDATE_INTERVAL = ClampFinite(PLAYER_UPDATE_INTERVAL, 1f, 0.25f, 60f);
            SERVER_PORT = ClampInt(SERVER_PORT, 1024, 65535);
            MAX_PINS_PER_USER = ClampInt(MAX_PINS_PER_USER, 0, 200);
            DEFAULT_ZOOM = ClampInt(DEFAULT_ZOOM, 50, 800);
            WORLD_VISIBILITY_MODE = NormalizeWorldVisibilityMode(WORLD_VISIBILITY_MODE);
        }

        private static int ClampInt(int value, int minimum, int maximum) => Math.Min(maximum, Math.Max(minimum, value));

        private static float ClampFinite(float value, float fallback, float minimum, float maximum)
        {
            if (float.IsNaN(value) || float.IsInfinity(value)) value = fallback;
            return Math.Min(maximum, Math.Max(minimum, value));
        }

        internal static string NormalizeWorldVisibilityMode(string value)
        {
            string normalized = value?.ToLowerInvariant();
            return normalized != null && WORLD_VISIBILITY_MODES.Contains(normalized) ? normalized : "fogged";
        }

        public static string GetWorldName()
        {
            if (ZNet.instance != null) WORLD_NAME = ZNet.instance.GetWorldName();
            return WORLD_NAME;
        }

        [Serializable]
        private sealed class ClientConfig
        {
            public string map_digest;
            public float world_start_x;
            public float world_start_z;
            public int default_zoom;
            public int texture_size;
            public int pixel_size;
            public float update_interval;
            public float explore_radius;
            public bool always_map;
            public bool always_visible;
            public string world_visibility_mode;
        }

        public static string MakeClientConfigJson(string mapDigest)
        {
            ClientConfig config = new ClientConfig
            {
                map_digest = mapDigest ?? string.Empty,
                world_start_x = WORLD_START_POS.x,
                world_start_z = WORLD_START_POS.z,
                default_zoom = DEFAULT_ZOOM,
                texture_size = TEXTURE_SIZE,
                pixel_size = PIXEL_SIZE,
                update_interval = PLAYER_UPDATE_INTERVAL,
                explore_radius = EXPLORE_RADIUS,
                always_map = ALWAYS_MAP,
                always_visible = ALWAYS_VISIBLE,
                world_visibility_mode = WORLD_VISIBILITY_MODE
            };
            return JsonUtility.ToJson(config);
        }
    }
}

using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
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
            WORLD_VISIBILITY_MODE = NormalizeWorldVisibilityMode(config.Bind("World", "world_visibility_mode", WORLD_VISIBILITY_MODE,
                new ConfigDescription("Browser fog policy.", new AcceptableValueList<string>("fogged", "hybrid", "full"))).Value);
            DEBUG = config.Bind("Server", "debug", DEBUG, "Enable constant diagnostic categories.").Value;
            TEST = config.Bind("Server", "test", TEST, "Enable test features.").Value;
            QUORUM_ACTIVITY_JOURNAL_ENABLED = config.Bind("Quorum Bot", "activity_journal_enabled", QUORUM_ACTIVITY_JOURNAL_ENABLED, "Append private local activity records.").Value;
            DISCORD_WEBHOOK = config.Bind("Server", "discord_webhook", DISCORD_WEBHOOK, "Discord webhook URL.").Value;
            DISCORD_INVITE_URL = config.Bind("Server", "discord_invite_url", DISCORD_INVITE_URL, "Optional Discord invite URL.").Value;
            URL = config.Bind("Server", "webmap_url", URL, "Web map URL.").Value;
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

        public static string MakeClientConfigJson()
        {
            Dictionary<string, object> config = new Dictionary<string, object>();
            config["world_name"] = GetWorldName();
            config["world_start_pos"] = WORLD_START_POS;
            config["default_zoom"] = DEFAULT_ZOOM;
            config["texture_size"] = TEXTURE_SIZE;
            config["pixel_size"] = PIXEL_SIZE;
            config["update_interval"] = PLAYER_UPDATE_INTERVAL;
            config["explore_radius"] = EXPLORE_RADIUS;
            config["always_map"] = ALWAYS_MAP;
            config["always_visible"] = ALWAYS_VISIBLE;
            config["world_visibility_mode"] = WORLD_VISIBILITY_MODE;
            return DictionaryToJson(config);
        }

        private static string DictionaryToJson(Dictionary<string, object> dict)
        {
            IEnumerable<string> entries = dict.Select(d =>
            {
                if (d.Value is float) return $"\"{d.Key}\": {((float)d.Value).ToString("F2", CultureInfo.InvariantCulture)}";
                if (d.Value is string) return $"\"{d.Key}\": \"{d.Value}\"";
                if (d.Value is bool) return $"\"{d.Key}\": {d.Value.ToString().ToLowerInvariant()}";
                if (d.Value is Vector3)
                {
                    Vector3 value = (Vector3)d.Value;
                    return $"\"{d.Key}\": \"{value.x.ToString("F2", CultureInfo.InvariantCulture)},{value.y.ToString("F2", CultureInfo.InvariantCulture)},{value.z.ToString("F2", CultureInfo.InvariantCulture)}\"";
                }
                return $"\"{d.Key}\": {d.Value}";
            });
            return "{\n    " + string.Join(",\n    ", entries) + "\n}\n";
        }
    }
}

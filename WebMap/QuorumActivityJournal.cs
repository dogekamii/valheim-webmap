using System;
using System.IO;
using UnityEngine;

namespace WebMap
{
    internal static class QuorumActivityJournal
    {
        [Serializable]
        private class ActivityEvent
        {
            public string type;
            public string player_id;
            public string player_name;
            public long occurred_at_unix;
        }

        internal static void AppendJoin(ZNetPeer peer)
        {
            Append("join", peer);
        }

        internal static void AppendLeave(ZNetPeer peer)
        {
            Append("leave", peer);
        }

        private static void Append(string type, ZNetPeer peer)
        {
            if (!WebMapConfig.QUORUM_ACTIVITY_JOURNAL_ENABLED)
            {
                return;
            }

            try
            {
                string path = Path.Combine(WebMap.worldDataPath, "quorum_activity.jsonl");
                ActivityEvent activityEvent = new ActivityEvent
                {
                    type = type,
                    player_id = peer.m_uid.ToString(),
                    player_name = peer.m_playerName ?? string.Empty,
                    occurred_at_unix = DateTimeOffset.UtcNow.ToUnixTimeSeconds()
                };
                File.AppendAllText(path, JsonUtility.ToJson(activityEvent) + Environment.NewLine);
            }
            catch (Exception exception)
            {
                ZLog.LogWarning("WebMap: quorum activity journal append failed: " + exception.Message);
            }
        }
    }
}

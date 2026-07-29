using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
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

        [Serializable]
        private class LinkClaimEvent
        {
            public string type;
            public string player_id;
            public string code_sha256;
            public long occurred_at_unix;
        }

        internal static void AppendJoin(ZNetPeer peer) => Append("join", peer);
        internal static void AppendLeave(ZNetPeer peer) => Append("leave", peer);

        internal static void AppendLinkClaim(ZNetPeer peer, string code)
        {
            if (!WebMapConfig.QUORUM_ACTIVITY_JOURNAL_ENABLED)
            {
                return;
            }

            try
            {
                LinkClaimEvent linkClaimEvent = new LinkClaimEvent
                {
                    type = "link_claim",
                    player_id = peer.m_uid.ToString(),
                    code_sha256 = Sha256(code),
                    occurred_at_unix = DateTimeOffset.UtcNow.ToUnixTimeSeconds()
                };
                AppendJson(JsonUtility.ToJson(linkClaimEvent));
            }
            catch
            {
                ZLog.LogWarning("WebMap: quorum link claim journal append failed");
            }
        }

        private static void Append(string type, ZNetPeer peer)
        {
            if (!WebMapConfig.QUORUM_ACTIVITY_JOURNAL_ENABLED)
            {
                return;
            }

            try
            {
                ActivityEvent activityEvent = new ActivityEvent
                {
                    type = type,
                    player_id = peer.m_uid.ToString(),
                    player_name = peer.m_playerName ?? string.Empty,
                    occurred_at_unix = DateTimeOffset.UtcNow.ToUnixTimeSeconds()
                };
                AppendJson(JsonUtility.ToJson(activityEvent));
            }
            catch (Exception exception)
            {
                ZLog.LogWarning("WebMap: quorum activity journal append failed: " + exception.Message);
            }
        }

        private static void AppendJson(string json)
        {
            string path = Path.Combine(WebMap.worldDataPath, "quorum_activity.jsonl");
            File.AppendAllText(path, json + Environment.NewLine);
        }

        private static string Sha256(string value)
        {
            using (SHA256 hash = SHA256.Create())
            {
                byte[] bytes = hash.ComputeHash(Encoding.UTF8.GetBytes(value));
                StringBuilder result = new StringBuilder(bytes.Length * 2);
                foreach (byte valueByte in bytes)
                {
                    result.Append(valueByte.ToString("x2"));
                }
                return result.ToString();
            }
        }
    }
}

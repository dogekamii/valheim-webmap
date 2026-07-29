using System;
using System.Text.RegularExpressions;
using HarmonyLib;

namespace WebMap
{
    [HarmonyPatch(typeof(ZRoutedRpc), nameof(ZRoutedRpc.HandleRoutedRPC))]
    internal static class QuorumLinkClaimPatch
    {
        private static readonly Regex LinkCommand = new Regex(
            "^!LINK\\s+(?<code>[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8})\\s*$",
            RegexOptions.Compiled | RegexOptions.IgnoreCase);
        private static readonly int IgnoredLinkClaimMethodHash = "DestroyZDO".GetStableHashCode();

        private static bool Prefix(ref ZRoutedRpc.RoutedRPCData data)
        {
            if (!WebMapConfig.QUORUM_ACTIVITY_JOURNAL_ENABLED)
            {
                return true;
            }

            if (data == null || (data.m_methodHash != "Say".GetStableHashCode() && data.m_methodHash != WebMap.sayMethodHash))
            {
                return true;
            }

            try
            {
                ZPackage package = new ZPackage(data.m_parameters.GetArray());
                package.ReadInt();
                UserInfo userInfo = new UserInfo();
                userInfo.Deserialize(ref package);
                string message = (package.ReadString() ?? string.Empty).Trim();
                Match match = LinkCommand.Match(message);
                if (!match.Success)
                {
                    return true;
                }

                // Harmony postfixes still run after a false prefix. Divert this private
                // command to the existing ignored-RPC path before they inspect chat data.
                data.m_methodHash = IgnoredLinkClaimMethodHash;
                string code = match.Groups["code"].Value.ToUpperInvariant();
                try
                {
                    ZNetPeer peer = ZNet.instance == null ? null : ZNet.instance.GetPeer(data.m_senderPeerID);
                    if (peer != null && !peer.m_server)
                    {
                        QuorumActivityJournal.AppendLinkClaim(peer, code);
                    }
                }
                catch
                {
                    // A recognized private command is never released into normal chat.
                }

                return false;
            }
            catch
            {
                // Packet parsing did not recognize a command; preserve ordinary chat.
                return true;
            }
        }
    }
}

using System;
using System.Text.RegularExpressions;
using HarmonyLib;

namespace WebMap
{
    [HarmonyPatch(typeof(ZRoutedRpc), nameof(ZRoutedRpc.HandleRoutedRPC))]
    internal static class QuorumLinkClaimPatch
    {
        private static readonly Regex LinkCode = new Regex("^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8}$", RegexOptions.Compiled);

        private static bool Prefix(ref ZRoutedRpc.RoutedRPCData data)
        {
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
                if (!message.StartsWith("!LINK", StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }

                // This command is private: do not route it to normal Valheim/WebMap chat.
                string code = message.Substring("!LINK".Length).Trim().ToUpperInvariant();
                ZNetPeer peer = ZNet.instance.GetPeer(data.m_senderPeerID);
                if (peer != null && !peer.m_server && LinkCode.IsMatch(code))
                {
                    QuorumActivityJournal.AppendLinkClaim(peer, code);
                }

                return false;
            }
            catch
            {
                // Preserve ordinary chat if packet parsing was not possible.
                return true;
            }
        }
    }
}

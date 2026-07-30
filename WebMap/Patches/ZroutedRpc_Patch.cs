using HarmonyLib;
using System;
using static ZRoutedRpc;

namespace WebMap.Patches
{
    [HarmonyPatch]
    internal class ZRoutedRpc_Patch
    {
        [HarmonyPatch(typeof(ZRoutedRpc), "InvokeRoutedRPC", new Type[] { typeof(long), typeof(ZDOID), typeof(string), typeof(object[]) })]
        [HarmonyPrefix]
        private static void InvokeRoutedRPC(ref ZRoutedRpc __instance, ref long targetPeerID, ZDOID targetZDO, string methodName, params object[] parameters)
        {
            if (WebMapConfig.TEST && methodName == "DiscoverLocationRespons") targetPeerID = ZRoutedRpc.Everybody;
        }
    }
}

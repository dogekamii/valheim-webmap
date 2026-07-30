using System;
using System.IO;
using HarmonyLib;
using WebSocketSharp.Net;
using WebSocketSharp.Server;

namespace WebMap.Patches
{
    [HarmonyPatch(typeof(MapDataServer), "ServeStaticFiles")]
    internal static class FrontendCacheHeadersPatch
    {
        [HarmonyPrefix]
        private static bool ServeUncachedIndex(HttpRequestEventArgs e, string ___publicRoot)
        {
            string requestPath = e.Request.Url.AbsolutePath;
            if (requestPath != "/" && requestPath != "/index.html") return true;
            try
            {
                byte[] bytes = File.ReadAllBytes(Path.Combine(___publicRoot, "index.html"));
                e.Response.Headers.Add(HttpResponseHeader.CacheControl, "no-store");
                e.Response.ContentType = "text/html";
                e.Response.StatusCode = 200;
                e.Response.ContentLength64 = bytes.Length;
                e.Response.Close(bytes, true);
            }
            catch
            {
                ZLog.LogError("WebMap: index read failed");
                e.Response.Headers.Add(HttpResponseHeader.CacheControl, "no-store");
                e.Response.StatusCode = 404;
                e.Response.Close();
            }
            return false;
        }
    }
}

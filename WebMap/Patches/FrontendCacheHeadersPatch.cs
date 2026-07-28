using System;
using System.IO;
using HarmonyLib;
using WebSocketSharp.Net;
using WebSocketSharp.Server;

namespace WebMap.Patches
{
    // The document chooses the content-addressed application bundle, so a
    // shared cache must fetch it from the current WebMap release every time.
    // Handle it before MapDataServer's immutable static-file path.
    [HarmonyPatch(typeof(MapDataServer), "ServeStaticFiles")]
    internal static class FrontendCacheHeadersPatch
    {
        [HarmonyPrefix]
        private static bool ServeUncachedIndex(HttpRequestEventArgs e, string ___publicRoot)
        {
            string rawRequestPath = e.Request.RawUrl;
            if (rawRequestPath != "/" && rawRequestPath != "/index.html")
            {
                return true;
            }

            try
            {
                byte[] indexBytes = File.ReadAllBytes(Path.Combine(___publicRoot, "index.html"));
                e.Response.Headers.Add(HttpResponseHeader.CacheControl, "no-store");
                e.Response.ContentType = "text/html";
                e.Response.StatusCode = 200;
                e.Response.ContentLength64 = indexBytes.Length;
                e.Response.Close(indexBytes, true);
            }
            catch (Exception ex)
            {
                ZLog.LogError("WebMap: FAILED TO READ INDEX FILE! " + ex.Message);
                e.Response.StatusCode = 404;
                e.Response.Close();
            }

            return false;
        }
    }
}

using System;
using System.Collections.Specialized;
using System.Net;
using WebSocketSharp;

namespace WebMap
{
    public class DiscordWebHook : IDisposable
    {
        private readonly WebClient webClient = new WebClient();
        private readonly string webHookUrl;
        private bool disposed;

        public DiscordWebHook(string url)
        {
            webHookUrl = url;
        }

        public void SendMessage(string message)
        {
            if (disposed || webHookUrl.IsNullOrEmpty()) return;
            try
            {
                NameValueCollection values = new NameValueCollection { { "content", message } };
                webClient.UploadValues(webHookUrl, values);
            }
            catch
            {
                ZLog.LogWarning("WebMap: webhook delivery failed");
            }
        }

        public void Dispose()
        {
            if (disposed) return;
            disposed = true;
            webClient.Dispose();
        }
    }
}

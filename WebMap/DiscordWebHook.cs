using System;
using System.Collections.Specialized;
using System.Net;
using WebSocketSharp;

namespace WebMap
{
    public class DiscordWebHook : IDisposable
    {
        private readonly WebClient webClient;
        private readonly string webHookUrl;

        public bool IsEnabled => !webHookUrl.IsNullOrEmpty();

        public DiscordWebHook(string url)
        {
            webHookUrl = url;
            if (IsEnabled)
            {
                webClient = new WebClient();
            }
        }

        public void SendMessage(string msgSend)
        {
            if (!IsEnabled)
            {
                return;
            }

            NameValueCollection values = new NameValueCollection
            {
                { "content", msgSend }
            };
            webClient.UploadValues(webHookUrl, values);
        }

        public void Dispose()
        {
            webClient?.Dispose();
        }
    }
}

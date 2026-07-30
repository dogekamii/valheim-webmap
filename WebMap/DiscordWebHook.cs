using System;
using System.Collections.Concurrent;
using System.IO;
using System.Net;
using System.Text;
using System.Threading;

namespace WebMap
{
    public sealed class DiscordWebHook : IDisposable
    {
        private const int QueueCapacity = 32;
        private const int MaxPayloadLength = 64;
        private const int MaxPayloadBytes = 256;
        private const int RequestTimeoutMilliseconds = 5000;
        private const int ShutdownWaitMilliseconds = 2000;

        private readonly Uri webHookUri;
        private readonly BlockingCollection<string> queue;
        private readonly CancellationTokenSource cancellation;
        private readonly Thread worker;
        private int disposed;

        public DiscordWebHook(string url)
        {
            if (string.IsNullOrWhiteSpace(url)) return;
            Uri parsedUri;
            if (!Uri.TryCreate(url, UriKind.Absolute, out parsedUri) ||
                !string.Equals(parsedUri.Scheme, Uri.UriSchemeHttps, StringComparison.OrdinalIgnoreCase) ||
                string.IsNullOrEmpty(parsedUri.Host) || !string.IsNullOrEmpty(parsedUri.UserInfo))
            {
                ZLog.LogWarning("WebMap: invalid webhook configuration");
                return;
            }

            webHookUri = parsedUri;
            queue = new BlockingCollection<string>(new ConcurrentQueue<string>(), boundedCapacity: QueueCapacity);
            cancellation = new CancellationTokenSource();
            worker = new Thread(WorkerLoop) { IsBackground = true, Name = "WebMap webhook" };
            worker.Start();
        }

        public void SendMessage(string message)
        {
            if (Volatile.Read(ref disposed) != 0 || queue == null || message == null ||
                message.Length == 0 || message.Length > MaxPayloadLength || !IsAllowedEvent(message)) return;
            try { queue.TryAdd(message); }
            catch (ObjectDisposedException) { }
            catch (InvalidOperationException) { }
        }

        private static bool IsAllowedEvent(string message)
        {
            return string.Equals(message, "Server is online", StringComparison.Ordinal) ||
                   string.Equals(message, "Server is offline", StringComparison.Ordinal) ||
                   string.Equals(message, "A player joined", StringComparison.Ordinal) ||
                   string.Equals(message, "A player left", StringComparison.Ordinal);
        }

        private void WorkerLoop()
        {
            try
            {
                foreach (string message in queue.GetConsumingEnumerable(cancellation.Token)) Deliver(message);
            }
            catch (OperationCanceledException) { }
            catch (ObjectDisposedException) { }
        }

        private void Deliver(string message)
        {
            try
            {
                byte[] payload = Encoding.UTF8.GetBytes("content=" + Uri.EscapeDataString(message));
                if (payload.Length > MaxPayloadBytes) return;
                HttpWebRequest request = (HttpWebRequest)WebRequest.Create(webHookUri);
                request.Method = "POST";
                request.ContentType = "application/x-www-form-urlencoded";
                request.ContentLength = payload.Length;
                request.AllowAutoRedirect = false;
                request.Timeout = RequestTimeoutMilliseconds;
                request.ReadWriteTimeout = RequestTimeoutMilliseconds;
                using (CancellationTokenRegistration registration = cancellation.Token.Register(request.Abort))
                {
                    using (Stream requestStream = request.GetRequestStream())
                    {
                        requestStream.Write(payload, 0, payload.Length);
                    }
                    using (HttpWebResponse response = (HttpWebResponse)request.GetResponse()) { }
                }
            }
            catch (WebException)
            {
                if (!cancellation.IsCancellationRequested) ZLog.LogWarning("WebMap: webhook delivery failed");
            }
            catch (IOException)
            {
                if (!cancellation.IsCancellationRequested) ZLog.LogWarning("WebMap: webhook delivery failed");
            }
            catch (ObjectDisposedException) { }
        }

        public void Dispose()
        {
            if (Interlocked.Exchange(ref disposed, 1) != 0) return;
            if (queue == null || cancellation == null) return;
            try { queue.CompleteAdding(); }
            catch (InvalidOperationException) { }
            cancellation.Cancel();
            if (worker != null && Thread.CurrentThread != worker && !worker.Join(ShutdownWaitMilliseconds))
                ZLog.LogWarning("WebMap: webhook shutdown timed out");
            queue.Dispose();
            cancellation.Dispose();
        }
    }
}

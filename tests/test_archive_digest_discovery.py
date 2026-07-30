"""One-shot RED evidence helper; removed after the archive digest is captured."""
import hashlib
import urllib.request

COMMIT = "4cbd1e0ccdbf9f5cb322a7c14e3c84e19db5dee1"
URL = f"https://codeload.github.com/sta/websocket-sharp/tar.gz/{COMMIT}"


class RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        raise AssertionError(f"archive redirect rejected: {code} {new_url}")


def test_report_exact_archive_digest_for_the_hash_locked_contract():
    request = urllib.request.Request(URL, headers={"Accept": "application/x-gzip"})
    with urllib.request.build_opener(RejectRedirects).open(request, timeout=60) as response:
        archive = response.read()
    digest = hashlib.sha256(archive).hexdigest()
    print(f"::error file=Dockerfile,line=1::exact upstream archive sha256={digest}")
    assert digest == "0000000000000000000000000000000000000000000000000000000000000000"

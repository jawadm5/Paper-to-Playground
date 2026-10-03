"""Deterministic public-source retrieval boundaries; no live network requests."""
import socket
import unittest
from unittest.mock import MagicMock, patch

from playground_v2.retrieval import SourceError, _arxiv_identity, _fetch, _public_destination


MODULE = "playground_v2.retrieval"
PUBLIC_IP = "93.184.216.34"


def addresses(*ips):
    return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM,
             socket.IPPROTO_TCP, "", (ip, 443)) for ip in ips]


def response(status=200, headers=None, chunks=(b"paper",)):
    result = MagicMock()
    result.status = status
    result.headers = headers or {}
    result.stream.return_value = iter(chunks)
    return result


class V2RetrievalTests(unittest.TestCase):
    def test_invalid_scheme_credentials_private_names_and_ports_fail_before_dns(self):
        urls = [
            "file:///paper.pdf", "ftp://example.org/paper", "https://user:secret@example.org/paper",
            "http://localhost/paper", "http://service.local/paper", "http://service.internal/paper",
            "http://service.localhost/paper", "https://example.org:8080/paper",
            "https://example.org:invalid/paper",
        ]
        with patch(MODULE + ".socket.getaddrinfo") as dns:
            for url in urls:
                with self.subTest(url=url), self.assertRaises(SourceError):
                    _public_destination(url)
            dns.assert_not_called()

    def test_every_resolved_address_must_be_public_and_public_results_are_deduplicated(self):
        for ips in ((), ("127.0.0.1",), ("10.0.0.1",), ("169.254.169.254",),
                    ("::1",), ("fe80::1",), (PUBLIC_IP, "192.168.1.2")):
            with self.subTest(ips=ips), patch(MODULE + ".socket.getaddrinfo", return_value=addresses(*ips)):
                with self.assertRaisesRegex(SourceError, "non-public"):
                    _public_destination("https://example.org/paper")
        with patch(MODULE + ".socket.getaddrinfo", return_value=addresses(PUBLIC_IP, PUBLIC_IP, "2606:4700:4700::1111")):
            self.assertEqual(_public_destination("https://example.org/paper"),
                             ("example.org", 443, [PUBLIC_IP, "2606:4700:4700::1111"]))
        with patch(MODULE + ".socket.getaddrinfo", side_effect=socket.gaierror("unavailable")):
            with self.assertRaisesRegex(SourceError, "could not be resolved"):
                _public_destination("https://example.org/paper")

    def test_arxiv_identity_requires_exact_known_domain_and_valid_paper_path(self):
        self.assertEqual(_arxiv_identity("https://arxiv.org/html/1706.03762v7"), ("1706.03762v7", "v7"))
        self.assertEqual(_arxiv_identity("https://export.arxiv.org/pdf/hep-th/9901001.pdf"),
                         ("hep-th/9901001", None))
        for url in ("https://arxiv.org.example.org/abs/1706.03762",
                    "https://example.org/arxiv.org/abs/1706.03762",
                    "https://arxiv.org/search/1706.03762"):
            with self.subTest(url=url):
                self.assertEqual(_arxiv_identity(url), (None, None))

    def test_https_connects_to_validated_ip_with_original_tls_and_host_names(self):
        page = response(headers={"Content-Type": "text/html; charset=utf-8"})
        with patch(MODULE + ".socket.getaddrinfo", return_value=addresses(PUBLIC_IP)) as dns, \
                patch(MODULE + ".urllib3.HTTPSConnectionPool") as constructor, \
                patch(MODULE + ".time.monotonic", return_value=100):
            pool = constructor.return_value
            pool.urlopen.return_value = page
            body, url, mime = _fetch("https://example.org/paper?q=one#section", 110)
        self.assertEqual((body, mime), (b"paper", "text/html"))
        self.assertEqual(url, "https://example.org/paper?q=one#section")
        dns.assert_called_once()
        options = constructor.call_args.kwargs
        self.assertEqual(options["host"], PUBLIC_IP)
        self.assertEqual(options["server_hostname"], "example.org")
        self.assertEqual(options["assert_hostname"], "example.org")
        self.assertEqual(options["cert_reqs"], "CERT_REQUIRED")
        request = pool.urlopen.call_args
        self.assertEqual(request.args, ("GET", "/paper?q=one"))
        self.assertEqual(request.kwargs["headers"]["Host"], "example.org")
        self.assertFalse(request.kwargs["redirect"])
        self.assertFalse(request.kwargs["retries"])
        page.close.assert_called_once()
        pool.close.assert_called_once()

    def test_redirect_to_private_address_is_rejected_before_connecting(self):
        redirect = response(302, {"Location": "http://metadata.example/internal"})
        with patch(MODULE + ".socket.getaddrinfo",
                   side_effect=[addresses(PUBLIC_IP), addresses("169.254.169.254")]) as dns, \
                patch(MODULE + ".urllib3.HTTPSConnectionPool") as https_pool, \
                patch(MODULE + ".urllib3.HTTPConnectionPool") as http_pool, \
                patch(MODULE + ".time.monotonic", return_value=100):
            https_pool.return_value.urlopen.return_value = redirect
            with self.assertRaisesRegex(SourceError, "non-public"):
                _fetch("https://example.org/paper", 110)
        self.assertEqual(dns.call_count, 2)
        http_pool.assert_not_called()
        redirect.close.assert_called_once()
        https_pool.return_value.close.assert_called_once()

    def test_relative_redirect_rechecks_destination_and_returns_final_url(self):
        pages = [response(302, {"Location": "../final.pdf"}), response(headers={"Content-Type": "application/pdf"})]
        pools = [MagicMock(), MagicMock()]
        for pool, page in zip(pools, pages):
            pool.urlopen.return_value = page
        with patch(MODULE + ".socket.getaddrinfo", return_value=addresses(PUBLIC_IP)) as dns, \
                patch(MODULE + ".urllib3.HTTPSConnectionPool", side_effect=pools), \
                patch(MODULE + ".time.monotonic", return_value=100):
            self.assertEqual(_fetch("https://example.org/start/paper", 110),
                             (b"paper", "https://example.org/final.pdf", "application/pdf"))
        self.assertEqual(dns.call_count, 2)
        for pool, page in zip(pools, pages):
            pool.close.assert_called_once()
            page.close.assert_called_once()

    def test_redirect_count_and_missing_location_are_bounded(self):
        for location, expected, count in (("/again", "five redirects", 6), (None, "no destination", 1)):
            page = response(302, {"Location": location} if location else {})
            with self.subTest(location=location), \
                    patch(MODULE + ".socket.getaddrinfo", return_value=addresses(PUBLIC_IP)), \
                    patch(MODULE + ".urllib3.HTTPSConnectionPool") as constructor, \
                    patch(MODULE + ".time.monotonic", return_value=100):
                constructor.return_value.urlopen.return_value = page
                with self.assertRaisesRegex(SourceError, expected):
                    _fetch("https://example.org/paper", 110)
                self.assertEqual(constructor.call_count, count)
                self.assertEqual(page.close.call_count, count)

    def test_declared_and_decoded_size_limits_and_deadline_stop_retrieval(self):
        for page in (response(headers={"Content-Length": "5"}), response(chunks=(b"abc", b"de"))):
            with self.subTest(headers=page.headers), patch(MODULE + ".MAX_BYTES", 4), \
                    patch(MODULE + ".socket.getaddrinfo", return_value=addresses(PUBLIC_IP)), \
                    patch(MODULE + ".urllib3.HTTPSConnectionPool") as constructor, \
                    patch(MODULE + ".time.monotonic", return_value=100):
                constructor.return_value.urlopen.return_value = page
                with self.assertRaisesRegex(SourceError, "larger than"):
                    _fetch("https://example.org/paper", 110)
                page.close.assert_called_once()
        with patch(MODULE + ".socket.getaddrinfo") as dns, patch(MODULE + ".time.monotonic", return_value=110):
            with self.assertRaisesRegex(SourceError, "time allowance"):
                _fetch("https://example.org/paper", 110)
            dns.assert_not_called()


if __name__ == "__main__":
    unittest.main()

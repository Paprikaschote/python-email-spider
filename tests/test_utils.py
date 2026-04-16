import argparse

import pytest

from src.utils import check_max_depth, check_url, decode_email, get_domain, slugify, strip_protocol


class TestSlugify:
    def test_simple_domain(self):
        assert slugify("example.com") == "examplecom"

    def test_domain_with_subdomain(self):
        assert slugify("www.example.com") == "wwwexamplecom"

    def test_domain_with_special_chars(self):
        assert slugify("my-site.co.uk") == "my-sitecouk"

    def test_empty_string(self):
        assert slugify("") == ""

    def test_unicode(self):
        assert slugify("über.de") == "uberde"


class TestDecodeEmail:
    def test_decode_cloudflare_email(self):
        # "test@example.com" encoded with Cloudflare key 0x2A
        encoded = "2a5e4f595e6a4f524b475a464f04494547"
        result = decode_email(encoded)
        assert result == "test@example.com"

    def test_decode_different_key(self):
        # "a@b.c" encoded with key 0x11
        email = "a@b.c"
        key = 0x11
        encoded = format(key, '02x')
        for ch in email:
            encoded += format(ord(ch) ^ key, '02x')
        result = decode_email(encoded)
        assert result == email


class TestStripProtocol:
    def test_strip_https(self):
        assert strip_protocol("https://example.com") == "example.com"

    def test_strip_http(self):
        assert strip_protocol("http://example.com") == "example.com"

    def test_strip_trailing_slash(self):
        assert strip_protocol("https://example.com/") == "example.com"

    def test_no_protocol(self):
        assert strip_protocol("example.com") == "example.com"


class TestGetDomain:
    def test_simple_domain(self):
        assert get_domain("example.com") == "example.com"

    def test_subdomain(self):
        assert get_domain("www.example.com") == "example.com"

    def test_regex_mode(self):
        result = get_domain("example.com", regex=True)
        assert result == r"example\.com"

    def test_stimmenwandler(self):
        assert get_domain("stimmenwandler.de") == "stimmenwandler.de"


class TestCheckUrl:
    def test_valid_https(self):
        assert check_url("https://example.com") == "https://example.com"

    def test_valid_http(self):
        assert check_url("http://example.com") == "http://example.com"

    def test_valid_without_protocol(self):
        assert check_url("example.com") == "example.com"

    def test_invalid_url(self):
        with pytest.raises(argparse.ArgumentTypeError):
            check_url("not a valid url!!!")


class TestCheckMaxDepth:
    def test_valid_depth(self):
        assert check_max_depth("3") == 3

    def test_zero_depth(self):
        assert check_max_depth("0") == 0

    def test_negative_depth(self):
        with pytest.raises(argparse.ArgumentTypeError):
            check_max_depth("-1")

    def test_non_integer(self):
        with pytest.raises(argparse.ArgumentTypeError):
            check_max_depth("abc")
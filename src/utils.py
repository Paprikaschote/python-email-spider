import platform
import re
import subprocess
import unicodedata
from urllib.parse import urlparse

from tldextract import extract


def slugify(value, allow_unicode=False):
    """
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
    else:
        value = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-_")


def decode_email(e):
    de = ""
    k = int(e[:2], 16)

    for i in range(2, len(e) - 1, 2):
        de += chr(int(e[i : i + 2], 16) ^ k)

    return de


def strip_protocol(domain):
    return re.sub(r"https?://", "", domain).rstrip("/")


def get_domain(url, regex=False):
    domain = extract(url).registered_domain
    # domain = td + "." + tsu
    if regex:
        return domain.replace(".", r"\.")
    return domain


def check_url(url):
    regex = re.compile(
        r"^(https?://)?"  # http:// or https:// or nothing
        r"((?:(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,6})"  # domain
        r"|localhost)"  # or localhost
        r"(:\d+)?"  # optional port
        r"(\/[-a-zA-Z0-9@:%._\+~#=]*)*"  # path
        r"(\?[;&a-zA-Z0-9%_.~+=-]*)?"  # query string
        r"(#[-a-zA-Z0-9_]*)?$"  # fragment locator
    )
    if not re.match(regex, url):
        raise argparse.ArgumentTypeError("invalid url: %s" % url)
    return url


def check_max_depth(md):
    try:
        md = int(md)
        if md < 0:
            raise argparse.ArgumentTypeError("invalid value: %s" % md)
    except ValueError:
        raise argparse.ArgumentTypeError("invalid value. Must be an integer")
    return md


# def check_max_depth(max_depth):
#     return re.match(r"^\d+$", max_depth)

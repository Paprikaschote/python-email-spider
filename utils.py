import re
import unicodedata


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
    return re.sub(r"https?://", "", domain)


def check_domain(domain):
    return re.match(r"^(https?://)?(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$", domain)


def check_max_depth(max_depth):
    return re.match(r"^\d+$", max_depth)

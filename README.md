# Email Spider for Websites and PDFs
![Static Badge](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)

A Python script that crawls every email address of a given website and saves the result in a nosql file. The search also includs pdf files. This script should be used for educational purposes only. I am not responsible for any misuse of this script. My intention is to help finding mail addresses on websites and explain how to secure them from spam [Preventation and solutions](#preventation-and-solutions).

### Advantages:
- crawling pdf files
- finding `(at)` mail addresses
- decryption of cloudflare's mail encryption
- threading for faster results
- sending every request with a valid browser user agent


# Table of contents
- [Email Spider for Websites and PDFs](#email-spider-for-websites-and-pdfs)
    - [Advantages:](#advantages)
- [Table of contents](#table-of-contents)
- [Usage](#usage)
  - [Flags](#flags)
- [Installation](#installation)
- [Possible false positives](#possible-false-positives)
- [Preventation and solutions](#preventation-and-solutions)
  - [Solution 1](#solution-1)
  - [Solution 2](#solution-2)
- [License](#license)

# Usage

[(Back to top)](#email-spider-for-websites-and-pdfs)

First run the script with the `crawl` command and the domain you want to crawl.
```bash
./main.py crawl -d https://example.com -m 2 -v
```

After that you can run the script with the `read` command to display the result.
```bash
./main.py read
```

## Flags

- With `-d` (or) `--domain`: domain or url to crawl

- With `-m` (or) `--maxdepth` : maximum depth to crawl (default: 2)

- With `-v` (or) `--verbose` : increase verbosity

- With `-vd` (or) `--verifydomains` verify mail addresses when reading from database

# Installation

[(Back to top)](#email-spider-for-websites-and-pdfs)

1. Install Python (at least, version >= 3.10)
2. Install all requirements from `requirements.txt` via pip
3. Start executing `./main.py` or `python main.py`


# Possible false positives

[(Back to top)](#email-spider-for-websites-and-pdfs)

Strings within a website could still be recognized as an email by the email regex pattern, when there is a `@` in a name. That could be the case for example if the `@` is in an image title, alt text or within the src path itself. After collecting possible mail addresses, there is a check with popular media suffixes, to exclude these entries from the result.

# Preventation and solutions

[(Back to top)](#email-spider-for-websites-and-pdfs)

So how can I prevent my own website from crawling mail addresses by a bot and what are the pitfalls. One of many solutions is not to hide your mail address with an `(at)`. As you can see in my script it's not a big deal to decrypt it.

## Solution 1
Set a rate limit in your webserver, so that a bot can't crawl your website in a short amount of time. For example, you can use the `limit_req` module in nginx and set a rate limit of 1 request per second for an ip address.
```
limit_req_zone $binary_remote_addr zone=one:10m rate=1r/s;

server {
    #...

    location / {
        limit_req zone=one;
    }
}
```

## Solution 2
Hiding an email address with javascript by encoding it. This is a common solution, but it has a big disadvantage. The email address is encoded with javascript, so screen-readers aren't able to read the correct mailto link. Especially with the new directive the European Accessibility Act (EAA), it is not the best solution for all.
```html
<a href="mailto:user@domain@@com"
   onmouseover="this.href=this.href.replace('@@','.')">
   Send email
</a>
```

# License

[(Back to top)](#email-spider-for-websites-and-pdfs)

The GNU GENERAL PUBLIC LICENSE. Please have a look at the [LICENSE](LICENSE) for more details.

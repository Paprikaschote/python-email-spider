#!/usr/bin/env python3

import sys
from pathlib import Path

if __package__ is None:
    DIR = Path(__file__).resolve().parent
    sys.path.insert(0, str(DIR.parent))
    __package__ = DIR.name

import re
import sqlite3
import unicodedata
from collections import deque
from datetime import datetime
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

from .utils import check_domain, check_max_depth, decode_email, slugify, strip_protocol


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


class EmailSpider:
    def __init__(self, domain, max_depth):
        self.domain = domain
        self.max_depth = max_depth
        self.start_url = f"https://{domain}"
        self.visited_urls = set()
        self.db_name = self.generate_db_name(domain)
        self.conn = sqlite3.connect(f"db/{self.db_name}")
        self.cursor = self.conn.cursor()
        self.setup_database()
        self.skip_extensions = [
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".svg",
            ".ico",
            ".webp",
            ".mp3",
            ".mp4",
            ".avi",
            ".mkv",
            ".wav",
            ".flv",
            ".mov",
            ".woff",
            ".woff2",
            ".ttf",
            ".eot",
            ".otf",
            ".pdf",
        ]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        }

    def generate_db_name(self, domain):
        date_str = datetime.now().strftime("%Y%m%d-%H%M")
        slugified_domain = slugify(domain)
        return f"{slugified_domain}_{date_str}.db"

    def setup_database(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY,
                email TEXT UNIQUE,
                created_at TEXT
            )
        """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY,
                url TEXT UNIQUE,
                created_at TEXT
            )
        """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS email_page (
                email_id INTEGER,
                page_id INTEGER,
                created_at TEXT,
                FOREIGN KEY(email_id) REFERENCES emails(id),
                FOREIGN KEY(page_id) REFERENCES pages(id),
                PRIMARY KEY (email_id, page_id)
            )
        """
        )

    def save_email_page_relation(self, email, url):
        now = datetime.now().isoformat()
        self.cursor.execute(
            "INSERT OR IGNORE INTO emails (email, created_at) VALUES (?, ?)",
            (email, now),
        )
        self.cursor.execute(
            "INSERT OR IGNORE INTO pages (url, created_at) VALUES (?, ?)", (url, now)
        )
        self.cursor.execute("SELECT id FROM emails WHERE email=?", (email,))
        email_id = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT id FROM pages WHERE url=?", (url,))
        page_id = self.cursor.fetchone()[0]
        self.cursor.execute(
            "INSERT OR IGNORE INTO email_page (email_id, page_id, created_at) VALUES (?, ?, ?)",
            (email_id, page_id, now),
        )
        self.conn.commit()

    def save_visited_url(self, url):
        now = datetime.now().isoformat()
        self.cursor.execute(
            "INSERT OR IGNORE INTO pages (url, created_at) VALUES (?, ?)", (url, now)
        )
        self.conn.commit()

    def is_valid_link(self, url):
        parsed = urlparse(url)
        if any(parsed.path.endswith(ext) for ext in self.skip_extensions):
            return False
        return True

    def content_type_is_pdf(self, response):
        content_type = response.headers.get("content-type")
        if "application/pdf" in content_type:
            return True
        return False

    def content_type_is_html(self, response):
        content_type = response.headers.get("content-type")
        if "text/html" in content_type:
            return True
        return False

    def read_pdf(self, response):
        my_raw_data = response.content

        with open("tmp.pdf", "wb") as my_data:
            my_data.write(my_raw_data)

        reader = PdfReader("tmp.pdf")

        return " ".join([page.extract_text() for page in reader.pages])

    def fetch_url(self, url):
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response
        except requests.RequestException:
            # Fallback to HTTP if HTTPS request fails
            if url.startswith("https://"):
                try:
                    url = url.replace("https://", "http://")
                    response = requests.get(url)
                    response.raise_for_status()
                    return response
                except requests.RequestException:
                    pass
        return None

    def find_emails(self, text):
        # Corrected regex with alternatives for @ or (at), including optional spaces
        pattern = r"[a-zA-Z0-9._%+-]+[ ]?(?:@|\(at\))[ ]?[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        return set(re.findall(pattern, text))

    def crawl(self):
        queue = deque([(self.start_url, 0)])

        while queue:
            url, depth = queue.popleft()

            clean_url, _ = urldefrag(url)  # Remove the anchor part of the URL

            if (
                clean_url in self.visited_urls
                or depth > self.max_depth
                or not self.is_valid_link(clean_url)
            ):
                continue

            print(f"Crawling: {clean_url} at depth {depth}")

            response = self.fetch_url(clean_url)
            if response is None:
                continue

            self.visited_urls.add(clean_url)
            self.save_visited_url(clean_url)

            emails = set()

            if self.content_type_is_html(response):
                soup = BeautifulSoup(response.content, "html.parser")
                page_text = soup.get_text()

                # Extract email addresses from the request
                emails.update(self.find_emails(response.text))

                # Extract email addresses from the beautiful soup
                emails.update(self.find_emails(page_text))

                # Extract protected email addresses that Cloudflare has secured
                for link in soup.find_all("a", {"class": "__cf_email__"}):
                    emails.add(decode_email(link.get("data-cfemail")))
            elif self.content_type_is_pdf(response):
                pdf_content = self.read_pdf(response)

                # Extract email addresses from pdf content
                emails.update(self.find_emails(pdf_content))

            for email in emails:
                self.save_email_page_relation(email, clean_url)
                print(f"Found email: {email}")

            # Extract internal links
            for link in soup.find_all("a", href=True):
                absolute_link = urljoin(clean_url, link["href"])
                absolute_clean_link, _ = urldefrag(absolute_link)

                if not self.is_valid_link(absolute_clean_link):
                    continue

                url_parts = urlparse(absolute_clean_link)

                if url_parts.hostname and self.domain in url_parts.hostname:
                    new_depth = depth + 1
                    if absolute_clean_link not in self.visited_urls:
                        queue.append((absolute_clean_link, new_depth))

        self.conn.close()


if __name__ == "__main__":
    while True:
        domain = input("Enter a domain: ")
        if check_domain(domain):
            break
        print("Invalid domain. Please enter a valid domain.")

    while True:
        max_depth = input("Max depth: ")
        if check_max_depth(max_depth):
            break
        print("Invalid max depth. Please enter a valid integer.")

    domain = strip_protocol(domain)
    spider = EmailSpider(domain, int(max_depth))
    spider.crawl()

import concurrent.futures
import io
import re
import sqlite3
import threading
import time
from datetime import datetime
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

from .utils import check_url, decode_email, get_domain, slugify, strip_protocol

SKIP_EXTENSIONS = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".ico", ".webp",
    ".mp3", ".mp4", ".avi", ".mkv", ".wav", ".flv", ".mov", ".wmv",
    ".mpg", ".mpeg", ".ogv", ".ogg", ".aiff", ".flac", ".m4a", ".m4v",
    ".webm",
})


class EmailSpider:
    def __init__(self, url, max_depth):
        self.url = url
        self.max_depth = max_depth
        self.start_url = f"https://{url}"
        self.visited_urls = set()
        self.visited_lock = threading.Lock()
        self.db_lock = threading.Lock()
        self.db_name = self._generate_db_name(url)
        self.conn = self._get_db_connection()
        self._setup_database()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        }
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20, pool_maxsize=20, max_retries=2
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _generate_db_name(self, domain):
        date_str = datetime.now().strftime("%Y%m%d-%H%M%S")
        slugified_domain = slugify(domain)
        return f"{slugified_domain}_{date_str}.db"

    def _setup_database(self):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY,
                email TEXT UNIQUE,
                created_at TEXT,
                valid INTEGER DEFAULT 0
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY,
                url TEXT UNIQUE,
                created_at TEXT
            )
        """
        )
        cursor.execute(
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
        self.conn.commit()

    def _get_db_connection(self):
        return sqlite3.connect(f"db/{self.db_name}", check_same_thread=False)

    def save_email_page_relation(self, email, url):
        now = datetime.now().isoformat()
        with self.db_lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO emails (email, created_at) VALUES (?, ?)",
                (email, now),
            )
            cursor.execute(
                "INSERT OR IGNORE INTO pages (url, created_at) VALUES (?, ?)",
                (url, now),
            )
            cursor.execute("SELECT id FROM emails WHERE email=?", (email,))
            email_id = cursor.fetchone()[0]
            cursor.execute("SELECT id FROM pages WHERE url=?", (url,))
            page_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT OR IGNORE INTO email_page (email_id, page_id, created_at) VALUES (?, ?, ?)",
                (email_id, page_id, now),
            )
            self.conn.commit()

    def _save_visited_url(self, url):
        now = datetime.now().isoformat()
        with self.db_lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO pages (url, created_at) VALUES (?, ?)",
                (url, now),
            )
            self.conn.commit()

    @staticmethod
    def _is_valid_link(url):
        path = urlparse(url).path.lower()
        ext_start = path.rfind(".")
        if ext_start != -1 and path[ext_start:] in SKIP_EXTENSIONS:
            return False
        return True

    @staticmethod
    def _content_type_is_pdf(response):
        content_type = response.headers.get("content-type", "")
        return "application/pdf" in content_type

    @staticmethod
    def _content_type_is_html(response):
        content_type = response.headers.get("content-type", "")
        return "text/html" in content_type

    @staticmethod
    def _read_pdf(response):
        reader = PdfReader(io.BytesIO(response.content))
        parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                parts.append(page_text)
        return "\n".join(parts)

    def _fetch_url(self, url):
        try:
            response = self.session.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response
        except requests.RequestException:
            if url.startswith("https://"):
                try:
                    url = url.replace("https://", "http://")
                    response = self.session.get(url, timeout=30)
                    response.raise_for_status()
                    return response
                except requests.RequestException:
                    pass
        return None

    def find_emails(self, text):
        domain = get_domain(self.url, regex=True)
        pattern = r"(?:[a-zA-Z0-9_.+-]+(?:@|\(at\)){domain}|[a-zA-Z0-9_.+-]+(?:@|\(at\))[a-zA-Z0-9-]+\.[a-z.]{{2,}})".format(
            domain=domain
        )

        emails = set(re.findall(pattern, text))

        return {
            email
            for email in emails
            if not any(email.endswith(suffix) for suffix in SKIP_EXTENSIONS)
        }

    def _parse(self, clean_url, depth, verbose=False):
        if depth > self.max_depth:
            return []

        with self.visited_lock:
            if clean_url in self.visited_urls:
                return []
            self.visited_urls.add(clean_url)

        response = self._fetch_url(clean_url)
        if response is None:
            return []

        if verbose:
            print(f"Crawling: {clean_url} at depth {depth}")

        self._save_visited_url(clean_url)

        emails = set()
        soup = None

        if self._content_type_is_html(response):
            emails.update(self.find_emails(response.text))
            soup = BeautifulSoup(response.content, "html.parser")
            for link in soup.find_all("a", {"class": "__cf_email__"}):
                emails.add(decode_email(link.get("data-cfemail")))
        elif self._content_type_is_pdf(response):
            pdf_content = self._read_pdf(response)
            emails.update(self.find_emails(pdf_content))

        for email in emails:
            self.save_email_page_relation(email, clean_url)
            if verbose:
                print(f"Found email: {email}")

        links = []
        if soup:
            next_depth = depth + 1
            for link in soup.find_all("a", href=True):
                absolute_link = urljoin(clean_url, link["href"])
                absolute_clean_link, _ = urldefrag(absolute_link)
                if self._is_valid_link(absolute_clean_link):
                    url_parts = urlparse(absolute_clean_link)
                    if url_parts.hostname and self.url in url_parts.hostname:
                        with self.visited_lock:
                            if absolute_clean_link not in self.visited_urls:
                                links.append((absolute_clean_link, next_depth))
        return links

    def normalize_at(self):
        with self.db_lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE emails
                SET email = REPLACE(email, '(at)', '@')
                WHERE email LIKE '%(at)%';
                """
            )
            self.conn.commit()

    def crawl(self, verbose=False, max_workers=10):
        pending = set()
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future = executor.submit(self._parse, self.start_url, 0, verbose)
            pending.add(future)

            while pending:
                done, pending = concurrent.futures.wait(
                    pending, return_when=concurrent.futures.FIRST_COMPLETED
                )
                for future in done:
                    links = future.result()
                    for url, depth in links:
                        new_future = executor.submit(self._parse, url, depth, verbose)
                        pending.add(new_future)

        self.normalize_at()
        self.conn.close()


def run(config):
    domain = config["domain"]
    max_depth = config["maxdepth"]
    verbose = config["verbose"]

    if not domain:
        while True:
            domain = input("Enter a domain: ")
            if check_url(domain):
                break
            print("Invalid domain. Please enter a valid domain.")

    domain = strip_protocol(domain)
    print(domain)
    spider = EmailSpider(domain, max_depth)

    start = time.time()
    spider.crawl(verbose)
    delta = time.time() - start
    if verbose:
        print(f"run time: {delta} seconds")
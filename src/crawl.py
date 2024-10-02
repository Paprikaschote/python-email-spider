import concurrent.futures
import re
import sqlite3
import threading
import time
from collections import deque
from datetime import datetime
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pdfreader import SimplePDFViewer

from .utils import check_url, decode_email, get_domain, slugify, strip_protocol

lock = threading.Lock()
thread_local = threading.local()


class EmailSpider:
    def __init__(self, url, max_depth):
        self.url = url
        self.max_depth = max_depth
        self.start_url = f"https://{url}"
        self.visited_urls = set()
        self.db_name = self.generate_db_name(url)
        self.conn = self.get_db_connection()
        self.setup_database()
        self.skip_extensions = [
            ".jpg",  # JPEG image
            ".jpeg",  # JPEG image (alternative extension)
            ".png",  # Portable Network Graphics image
            ".gif",  # Graphics Interchange Format (animated/static)
            ".bmp",  # Bitmap image
            ".svg",  # Scalable Vector Graphics (vector image)
            ".ico",  # Icon file (typically for website icons)
            ".webp",  # WebP image (highly compressed)
            ".mp3",  # MPEG Layer 3 Audio
            ".mp4",  # MPEG-4 Video
            ".avi",  # Audio Video Interleave (Microsoft)
            ".mkv",  # Matroska Video format (supports multiple streams)
            ".wav",  # Waveform Audio File
            ".flv",  # Flash Video
            ".mov",  # QuickTime Movie (Apple)
            ".wmv",  # Windows Media Video
            ".mpg",  # MPEG Video
            ".mpeg",  # MPEG Video (alternative extension)
            ".ogv",  # Ogg Video
            ".ogg",  # Ogg Audio (alternative to MP3)
            ".aiff",  # Audio Interchange File Format (Apple)
            ".flac",  # Free Lossless Audio Codec (high-quality audio)
            ".m4a",  # MPEG-4 Audio (often used in iTunes)
            ".m4v",  # MPEG-4 Video (Apple format)
            ".webm",  # WebM Video (optimized for web use)
        ]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        }
        self.session = requests.Session()

    def generate_db_name(self, domain):
        date_str = datetime.now().strftime("%Y%m%d-%H%M%S")
        slugified_domain = slugify(domain)
        return f"{slugified_domain}_{date_str}.db"

    def setup_database(self):
        with lock:
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

    def get_db_connection(self):
        if not hasattr(thread_local, "connection"):
            thread_local.connection = sqlite3.connect(
                f"db/{self.db_name}", check_same_thread=False
            )
        return thread_local.connection

    def save_email_page_relation(self, email, url):
        now = datetime.now().isoformat()
        with lock:
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

    def save_visited_url(self, url):
        now = datetime.now().isoformat()
        with lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO pages (url, created_at) VALUES (?, ?)",
                (url, now),
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
        viewer = SimplePDFViewer(response.content)
        text = ""
        for canvas in viewer:
            text += "".join(canvas.strings) + "\n"
        return text

    def fetch_url(self, url):
        try:
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            return response
        except requests.RequestException:
            if url.startswith("https://"):
                try:
                    url = url.replace("https://", "http://")
                    response = self.session.get(url)
                    response.raise_for_status()
                    return response
                except requests.RequestException:
                    pass
        return None

    def find_emails(self, text):
        domain = get_domain(self.url, regex=True)
        # possible false positives by crawling pdf files due to pdf text extraction
        # so that first we only look for email addresses that contain the domain
        pattern = r"(?:[a-zA-Z0-9_.+-]+(?:@|\(at\)){domain}|[a-zA-Z0-9_.+-]+(?:@|\(at\))[a-zA-Z0-9-]+\.[a-z.]{{2,}})".format(
            domain=domain
        )

        emails = set(re.findall(pattern, text))

        return {
            email
            for email in emails
            if not any(email.endswith(suffix) for suffix in self.skip_extensions)
        }

    def parse(self, clean_url, depth, verbose=False):
        if depth > self.max_depth:  # Check for max depth
            return []

        with lock:
            if clean_url in self.visited_urls:
                return []
            self.visited_urls.add(clean_url)

        response = self.fetch_url(clean_url)
        if response is None:
            return []

        print(f"Crawling: {clean_url} at depth {depth}")

        self.save_visited_url(clean_url)

        emails = set()
        soup = None

        if self.content_type_is_html(response):
            emails.update(self.find_emails(response.text))
            soup = BeautifulSoup(response.content, "html.parser")
            for link in soup.find_all("a", {"class": "__cf_email__"}):
                emails.add(decode_email(link.get("data-cfemail")))
        elif self.content_type_is_pdf(response):
            pdf_content = self.read_pdf(response)
            emails.update(self.find_emails(pdf_content))

        for email in emails:
            self.save_email_page_relation(email, clean_url)
            if verbose:
                print(f"Found email: {email}")

        links = []
        if soup:
            for link in soup.find_all("a", href=True):
                absolute_link = urljoin(clean_url, link["href"])
                absolute_clean_link, _ = urldefrag(absolute_link)
                if self.is_valid_link(absolute_clean_link):
                    url_parts = urlparse(absolute_clean_link)
                    if url_parts.hostname and self.url in url_parts.hostname:
                        new_depth = depth + 1
                        with lock:
                            if absolute_clean_link not in self.visited_urls:
                                links.append((absolute_clean_link, new_depth))
        return links

    def normalize_at(self):
        with lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE emails
                SET email = REPLACE(email, '(at)', '@')
                WHERE email LIKE '%(at)%';
                """
            )
            self.conn.commit()

    def crawl(self, verbose=False):
        queue = deque([(self.start_url, 0)])
        with concurrent.futures.ThreadPoolExecutor() as executor:
            while queue:
                futures = [
                    executor.submit(self.parse, url, depth, verbose)
                    for url, depth in queue
                ]
                queue.clear()
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        queue.extend(result)
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

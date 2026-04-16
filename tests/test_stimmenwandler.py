import os
import sqlite3

import pytest

from src.crawl import EmailSpider

EXPECTED_EMAIL = "carlo@stimmenwandler.de"
EXPECTED_PAGES = {
    "https://stimmenwandler.de",
    "https://stimmenwandler.de/impressum",
    "https://stimmenwandler.de/datenschutz",
    "https://stimmenwandler.de/kontakt",
}


@pytest.fixture(scope="class")
def crawl_result():
    spider = EmailSpider("stimmenwandler.de", 2)
    spider.crawl(verbose=True)
    db_path = f"db/{spider.db_name}"
    conn = sqlite3.connect(db_path)
    yield conn, db_path
    conn.close()
    os.remove(db_path)


class TestStimmenwandlerCrawl:
    def test_finds_expected_email(self, crawl_result):
        """The crawl must find carlo@stimmenwandler.de."""
        conn, _ = crawl_result
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM emails")
        emails = {row[0] for row in cursor.fetchall()}
        assert EXPECTED_EMAIL in emails

    def test_email_found_on_expected_pages(self, crawl_result):
        """carlo@stimmenwandler.de must appear on at least the known pages."""
        conn, _ = crawl_result
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.url
            FROM pages p
            JOIN email_page ep ON p.id = ep.page_id
            JOIN emails e ON e.id = ep.email_id
            WHERE e.email = ?
            """,
            (EXPECTED_EMAIL,),
        )
        found_pages = {row[0] for row in cursor.fetchall()}
        missing = EXPECTED_PAGES - found_pages
        assert not missing, f"Email not found on expected pages: {missing}"

    def test_crawled_multiple_pages(self, crawl_result):
        """The spider must have visited more than just the start page."""
        conn, _ = crawl_result
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM pages")
        page_count = cursor.fetchone()[0]
        assert page_count >= 4, f"Expected at least 4 pages, found {page_count}"

    def test_no_false_positive_domains(self, crawl_result):
        """All found emails must belong to stimmenwandler.de."""
        conn, _ = crawl_result
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM emails")
        emails = [row[0] for row in cursor.fetchall()]
        for email in emails:
            assert email.endswith("@stimmenwandler.de"), (
                f"Unexpected email domain: {email}"
            )

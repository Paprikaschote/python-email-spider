import os
import sqlite3

import pytest

from src.crawl import EmailSpider


@pytest.fixture
def spider():
    s = EmailSpider("example.com", 1)
    yield s
    s.conn.close()
    os.remove(f"db/{s.db_name}")


class TestEmailSpider:
    def test_generate_db_name(self, spider):
        assert spider.db_name.startswith("examplecom_")
        assert spider.db_name.endswith(".db")

    def test_is_valid_link(self, spider):
        assert EmailSpider._is_valid_link("https://example.com/page") is True
        assert EmailSpider._is_valid_link("https://example.com/image.jpg") is False
        assert EmailSpider._is_valid_link("https://example.com/video.mp4") is False
        assert EmailSpider._is_valid_link("https://example.com/doc.pdf") is True

    def test_find_emails(self, spider):
        text = "Contact us at info@example.com or support@example.com for help."
        emails = spider.find_emails(text)
        assert "info@example.com" in emails
        assert "support@example.com" in emails

    def test_find_emails_with_at_notation(self, spider):
        text = "Write to info(at)example.com"
        emails = spider.find_emails(text)
        assert "info(at)example.com" in emails

    def test_find_emails_excludes_media(self, spider):
        text = "image@example.com.jpg user@example.com"
        emails = spider.find_emails(text)
        assert "user@example.com" in emails

    def test_database_setup(self, spider):
        cursor = spider.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        assert "emails" in tables
        assert "pages" in tables
        assert "email_page" in tables

    def test_save_email_page_relation(self, spider):
        spider.save_email_page_relation("test@example.com", "https://example.com")
        cursor = spider.conn.cursor()
        cursor.execute("SELECT email FROM emails")
        emails = [row[0] for row in cursor.fetchall()]
        assert "test@example.com" in emails
        cursor.execute("SELECT url FROM pages")
        pages = [row[0] for row in cursor.fetchall()]
        assert "https://example.com" in pages

    def test_normalize_at(self, spider):
        spider.save_email_page_relation("info(at)example.com", "https://example.com")
        spider.normalize_at()
        cursor = spider.conn.cursor()
        cursor.execute("SELECT email FROM emails")
        emails = [row[0] for row in cursor.fetchall()]
        assert "info@example.com" in emails

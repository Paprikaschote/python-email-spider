import os
import sqlite3

from .utils import slugify


class DatabaseReader:
    def __init__(self, db_name=None):
        self.db_name = db_name

    def fetch_emails_and_pages(self):
        conn = sqlite3.connect(f"db/{self.db_name}")
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT emails.email, pages.url
            FROM emails
            JOIN email_page ON emails.id = email_page.email_id
            JOIN pages ON pages.id = email_page.page_id
            ORDER BY emails.email
        """
        )

        results = cursor.fetchall()
        conn.close()
        return results

    def output(self):
        results = self.fetch_emails_and_pages()

        if results:
            email_to_pages = {}
            for email, url in results:
                if email not in email_to_pages:
                    email_to_pages[email] = []
                email_to_pages[email].append(url)

            print("Found mail addresses:")
            for email, urls in email_to_pages.items():
                print(f"\nemail: {email} \npages: {', '.join(urls)}")
        else:
            print("No email addresses found in the selected database.")


def get_all_databases():
    databases = [f for f in os.listdir("db") if f.endswith(".db")]
    return sorted([f.lower() for f in databases])


def display_databases(databases):
    print("Choose a database:")
    for idx, db_name in enumerate(databases, start=1):
        print(f"{idx}: {db_name}")


def select_database(databases):
    while True:
        try:
            choice = int(input("Which database do you want: "))
            if 1 <= choice <= len(databases):
                return databases[choice - 1]
            else:
                print("incorrect number.")
        except ValueError:
            print("Please enter a valid interger.")


def run():
    databases = get_all_databases()
    display_databases(databases)
    db_name = select_database(databases)
    DatabaseReader(db_name).output()

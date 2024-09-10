#!/usr/bin/env python3

import sys
from pathlib import Path

if __package__ is None:
    DIR = Path(__file__).resolve().parent
    sys.path.insert(0, str(DIR.parent))
    __package__ = DIR.name

import os
import sqlite3

from .utils import slugify


def list_databases(domain_slug):
    databases = [
        f for f in os.listdir(".") if f.startswith(domain_slug) and f.endswith(".db")
    ]
    return databases


def display_databases(databases):
    print("Wählen Sie eine Datenbank:")
    for idx, db_name in enumerate(databases, start=1):
        print(f"{idx}: {db_name}")


def select_database(databases):
    while True:
        try:
            choice = int(input("Geben Sie die Nummer der gewünschten Datenbank ein: "))
            if 1 <= choice <= len(databases):
                return databases[choice - 1]
            else:
                print("Ungültige Wahl, bitte erneut eingeben.")
        except ValueError:
            print("Bitte eine gültige Zahl eingeben.")


def fetch_emails_and_pages(database):
    conn = sqlite3.connect(database)
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


def main():
    domain = input("Bitte geben Sie die Domain ein: ")
    domain_slug = slugify(domain)  # Slugify the domain

    databases = list_databases(domain_slug)
    if len(databases) == 0:
        print(f"Keine Datenbanken für die Domain '{domain}' gefunden.")
        return

    if len(databases) == 1:
        selected_db = databases[0]
    else:
        display_databases(databases)
        selected_db = select_database(databases)

    results = fetch_emails_and_pages(selected_db)

    if results:
        email_to_pages = {}
        for email, url in results:
            if email not in email_to_pages:
                email_to_pages[email] = []
            email_to_pages[email].append(url)

        print("Gefundene E-Mail-Adressen und die zugehörigen Seiten:")
        for email, urls in email_to_pages.items():
            print(f"E-Mail: {email} - Seiten: {', '.join(urls)}")
    else:
        print("Keine E-Mail-Adressen in der ausgewählten Datenbank gefunden.")


if __name__ == "__main__":
    main()

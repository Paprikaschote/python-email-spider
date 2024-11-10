#!/usr/bin/env python3
import argparse
import sys

from src.crawl import run as run_crawl
from src.read import run as run_read
from src.utils import check_max_depth, check_url

operations = [
    "crawl mail addresses from a given url or domain",
    "output the mail addresses and the pages on which they were found",
]


def arguments():
    parser = argparse.ArgumentParser(
        prog="Email Spider",
        description="A simple email spider that crawls a given url or domain for email addresses.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-d", "--domain", type=check_url, help="domain or url to crawl")
    parser.add_argument(
        "-m",
        "--maxdepth",
        type=check_max_depth,
        default=2,
        help="maximum depth to crawl (default: 2)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="increase verbosity"
    )
    parser.add_argument("op", choices=["crawl", "read"], help="Operation to perform")
    args = parser.parse_args()
    return vars(args)


if __name__ == "__main__":
    config = arguments()

    match config["op"]:
        case "crawl":
            run_crawl(config)
        case "read":
            run_read()
        case _:
            print("Invalid operation. Exiting.")
            sys.exit(1)

"""Smoke test for Scrapling.

Run from backend:
    venv\\Scripts\\python.exe test_scrapling.py
"""

from scrapling import Fetcher


def main():
    url = "https://example.com"
    page = Fetcher.get(url, timeout=20)

    title = page.css("title")
    heading = page.css("h1")

    print(f"URL: {url}")
    print(f"Status: {page.status}")
    print(f"Title: {title[0].text if title else None}")
    print(f"Heading: {heading[0].text if heading else None}")


if __name__ == "__main__":
    main()

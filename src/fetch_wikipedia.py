from __future__ import annotations

import json
import time

import requests

from config import ARTICLE_DIR, ARTICLE_TITLES_PATH


API_URL = "https://en.wikipedia.org/w/api.php"
REQUEST_DELAY_SECONDS = 1.2
MAX_RETRIES = 5


def safe_filename(title: str) -> str:
    return "".join(char if char.isalnum() or char in " ._-" else "_" for char in title).strip()


def fetch_article(title: str) -> dict:
    params = {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "explaintext": "1",
        "redirects": "1",
        "titles": title,
    }
    headers = {
        "User-Agent": "Day19-GraphRAG-Lab/1.0 (student lab; contact: local@example.com)"
    }

    for attempt in range(1, MAX_RETRIES + 1):
        response = requests.get(API_URL, params=params, timeout=30, headers=headers)
        if response.status_code != 429:
            response.raise_for_status()
            break

        retry_after = response.headers.get("Retry-After")
        wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else min(60, 2 ** attempt)
        print(f"Rate limited on '{title}'. Waiting {wait_seconds}s before retry {attempt}/{MAX_RETRIES}.")
        time.sleep(wait_seconds)
    else:
        raise RuntimeError(f"Failed to fetch '{title}' after {MAX_RETRIES} retries due to rate limiting.")

    pages = response.json()["query"]["pages"]
    page = next(iter(pages.values()))
    return {
        "title": page.get("title", title),
        "extract": page.get("extract", ""),
        "pageid": page.get("pageid"),
    }


def already_downloaded(title: str) -> bool:
    expected_path = ARTICLE_DIR / f"{safe_filename(title)}.json"
    if expected_path.exists():
        return True

    title_lower = title.lower()
    for path in ARTICLE_DIR.glob("*.json"):
        try:
            article = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if article.get("title", "").lower() == title_lower:
            return True
    return False


def main():
    ARTICLE_DIR.mkdir(parents=True, exist_ok=True)
    titles = [line.strip() for line in ARTICLE_TITLES_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    fetched = 0
    skipped = 0

    for title in titles:
        if already_downloaded(title):
            skipped += 1
            continue

        article = fetch_article(title)
        if article["extract"]:
            output_path = ARTICLE_DIR / f"{safe_filename(article['title'])}.json"
            output_path.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
            fetched += 1
            print(f"Fetched: {article['title']}")
        else:
            print(f"No extract found: {title}")
        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"Fetched {fetched}, skipped {skipped}, total titles {len(titles)}. Output: {ARTICLE_DIR}")


if __name__ == "__main__":
    main()

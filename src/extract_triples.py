from __future__ import annotations

import json
import re

import pandas as pd

from config import ARTICLE_DIR, DATA_WIKI_DIR, TRIPLES_PATH


SEED_TRIPLES_PATH = DATA_WIKI_DIR / "seed_triples.csv"
COMPANY_HINTS = {
    "Amazon",
    "Anthropic",
    "Apple",
    "Character.ai",
    "DeepMind",
    "Google",
    "Hugging Face",
    "Meta",
    "Microsoft",
    "Nvidia",
    "OpenAI",
    "Salesforce",
}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def sentence_split(text: str) -> list[str]:
    return [clean(sentence) for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]


def add_triple(rows: list[dict], source: str, relation: str, target: str, evidence: str, source_type="Company", target_type="Entity"):
    source = clean(source)
    target = clean(target)
    if not source or not target or source == target:
        return
    rows.append(
        {
            "source": source,
            "relation": relation,
            "target": target,
            "source_type": source_type,
            "target_type": target_type,
            "evidence": evidence[:500],
        }
    )


def clean_target(text: str) -> str:
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.split(r",|;|\.|\s+and\s+|\s+as\s+", text, maxsplit=1)[0]
    return clean(text.strip(" -:"))


def extract_people(text: str) -> list[str]:
    names = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b", text)
    blocked = {
        "Artificial Intelligence",
        "Chief Executive Officer",
        "Google",
        "OpenAI",
        "Microsoft",
        "Amazon Web Services",
        "United States",
    }
    return [name for name in names if name not in blocked]


def extract_company_names(text: str) -> list[str]:
    names = []
    for company in COMPANY_HINTS:
        if re.search(rf"\b{re.escape(company)}\b", text):
            names.append(company)
    return names


def extract_from_article(title: str, text: str) -> list[dict]:
    rows = []
    intro = " ".join(sentence_split(text)[:8])

    if intro:
        add_triple(rows, title, "HAS_SUMMARY", intro[:280], intro, "Company", "Text")

    for sentence in sentence_split(text):
        lower = sentence.lower()

        if " is an " in lower or " is a " in lower:
            match = re.search(rf"{re.escape(title)}\s+is\s+(?:an?|the)\s+([^.;]+)", sentence, re.IGNORECASE)
            if match:
                add_triple(rows, title, "IS_A", match.group(1), sentence, "Company", "Concept")

        founded_match = re.search(r"(?:founded|co-founded)\s+by\s+([^.;]+)", sentence, re.IGNORECASE)
        if founded_match and title.lower() in lower:
            names = re.split(r",| and | with ", founded_match.group(1))
            for name in names:
                name = re.sub(r"\([^)]*\)", "", name).strip()
                if 2 <= len(name.split()) <= 5:
                    add_triple(rows, title, "CO_FOUNDED_BY", name, sentence, "Company", "Person")

        former_google_match = re.search(r"former\s+Google\s+(?:employee|employees|engineer|engineers|researcher|researchers)[^.;]*", sentence, re.IGNORECASE)
        if former_google_match:
            person_candidates = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b", sentence)
            for person in person_candidates:
                if person not in {"Google"}:
                    add_triple(rows, person, "FORMER_EMPLOYEE_OF", "Google", sentence, "Person", "Company")

        acquired_match = re.search(r"acquired\s+by\s+([^.;,]+)", sentence, re.IGNORECASE)
        if acquired_match and title.lower() in lower:
            buyer = acquired_match.group(1).strip()
            add_triple(rows, title, "ACQUIRED_BY", buyer, sentence, "Company", "Company")
            add_triple(rows, buyer, "ACQUIRED", title, sentence, "Company", "Company")

        acquired_object_match = re.search(rf"{re.escape(title)}[^.;]*acquired\s+([^.;,]+)", sentence, re.IGNORECASE)
        if acquired_object_match:
            target = clean_target(acquired_object_match.group(1))
            if target:
                add_triple(rows, title, "ACQUIRED", target, sentence, "Company", "Company")
                add_triple(rows, target, "ACQUIRED_BY", title, sentence, "Company", "Company")

        headquarters_match = re.search(r"headquartered\s+in\s+([^.;,]+)", sentence, re.IGNORECASE)
        if headquarters_match and title.lower() in lower:
            add_triple(rows, title, "HEADQUARTERED_IN", headquarters_match.group(1), sentence, "Company", "Location")

        subsidiary_match = re.search(r"(?:subsidiary|division|unit)\s+of\s+([^.;,]+)", sentence, re.IGNORECASE)
        if subsidiary_match and title.lower() in lower:
            parent = clean_target(subsidiary_match.group(1))
            add_triple(rows, title, "SUBSIDIARY_OF", parent, sentence, "Company", "Company")
            add_triple(rows, parent, "PARENT_ORG_OF", title, sentence, "Company", "Company")

        owned_by_match = re.search(r"(?:owned|operated)\s+by\s+([^.;,]+)", sentence, re.IGNORECASE)
        if owned_by_match and title.lower() in lower:
            owner = clean_target(owned_by_match.group(1))
            add_triple(rows, title, "OWNED_BY", owner, sentence, "Company", "Company")
            add_triple(rows, owner, "OWNS", title, sentence, "Company", "Company")

        for verb, relation in [
            ("develops", "DEVELOPS"),
            ("developed", "DEVELOPED"),
            ("created", "CREATED"),
            ("creates", "CREATES"),
            ("launched", "LAUNCHED"),
            ("released", "RELEASED"),
            ("operates", "OPERATES"),
        ]:
            match = re.search(rf"{re.escape(title)}[^.;]*\b{verb}\b\s+([^.;]+)", sentence, re.IGNORECASE)
            if match:
                target = clean_target(match.group(1))
                if target and len(target) <= 80:
                    add_triple(rows, title, relation, target, sentence, "Company", "Product")
                    add_triple(rows, target, "PRODUCT_OF", title, sentence, "Product", "Company")

        developed_by_match = re.search(r"([^.;,]+)\s+(?:was|were)?\s*(?:developed|created|launched|released)\s+by\s+([^.;,]+)", sentence, re.IGNORECASE)
        if developed_by_match:
            product = clean_target(developed_by_match.group(1))
            creator = clean_target(developed_by_match.group(2))
            if title.lower() in creator.lower() and product and len(product) <= 80:
                add_triple(rows, product, "PRODUCT_OF", title, sentence, "Product", "Company")
                add_triple(rows, title, "DEVELOPS", product, sentence, "Company", "Product")

        investment_match = re.search(r"([^.;,]+)\s+invested\s+in\s+([^.;,]+)", sentence, re.IGNORECASE)
        if investment_match:
            investor = clean_target(investment_match.group(1))
            investee = clean_target(investment_match.group(2))
            if title.lower() in investor.lower() or title.lower() in investee.lower():
                add_triple(rows, investor, "INVESTED_IN", investee, sentence, "Company", "Company")
                add_triple(rows, investee, "RECEIVED_INVESTMENT_FROM", investor, sentence, "Company", "Company")

        partnership_match = re.search(r"([^.;,]+)\s+(?:partnered|collaborated)\s+with\s+([^.;,]+)", sentence, re.IGNORECASE)
        if partnership_match:
            left = clean_target(partnership_match.group(1))
            right = clean_target(partnership_match.group(2))
            if title.lower() in left.lower() or title.lower() in right.lower():
                add_triple(rows, left, "PARTNERED_WITH", right, sentence, "Company", "Company")
                add_triple(rows, right, "PARTNERED_WITH", left, sentence, "Company", "Company")

        for company in extract_company_names(sentence):
            if company != title and title.lower() in lower:
                add_triple(rows, title, "MENTIONS", company, sentence, "Company", "Company")

    return rows


def main():
    rows = []
    for path in ARTICLE_DIR.glob("*.json"):
        article = json.loads(path.read_text(encoding="utf-8"))
        rows.extend(extract_from_article(article["title"], article.get("extract", "")))

    df = pd.DataFrame(rows)
    if SEED_TRIPLES_PATH.exists():
        seed = pd.read_csv(SEED_TRIPLES_PATH)
        df = pd.concat([df, seed], ignore_index=True)

    df = df.drop_duplicates(subset=["source", "relation", "target"])
    TRIPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(TRIPLES_PATH, index=False)
    print(f"Wrote {len(df)} triples to {TRIPLES_PATH}")


if __name__ == "__main__":
    main()

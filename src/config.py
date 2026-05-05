from pathlib import Path
from dotenv import load_dotenv
import os


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_WIKI_DIR = ROOT_DIR / "data" / "wiki"
ARTICLE_TITLES_PATH = ROOT_DIR / "data" / "wiki_article_titles.txt"
ARTICLE_DIR = DATA_WIKI_DIR / "articles"
TRIPLES_PATH = DATA_WIKI_DIR / "triples.csv"
OUTPUT_DIR = ROOT_DIR / "outputs"

load_dotenv(ROOT_DIR / ".env")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import json

from config import ARTICLE_DIR
from llm import LLMNotConfiguredError, generate_answer


class FlatRAG:
    def __init__(self):
        self.documents = self._load_documents()
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = self.vectorizer.fit_transform(self.documents) if self.documents else None

    def _load_documents(self) -> list[str]:
        docs = []
        for path in ARTICLE_DIR.glob("*.json"):
            article = json.loads(path.read_text(encoding="utf-8"))
            title = article.get("title", path.stem)
            text = article.get("extract", "")
            for paragraph in text.split("\n"):
                paragraph = paragraph.strip()
                if len(paragraph) > 80:
                    docs.append(f"{title}: {paragraph}")

        return docs

    def retrieve_context(self, question: str, top_k: int = 5) -> str:
        if not self.documents or self.matrix is None:
            return "No Wikipedia article documents loaded. Run src/fetch_wikipedia.py first."
        query_vector = self.vectorizer.transform([question])
        scores = cosine_similarity(query_vector, self.matrix).flatten()
        top_indexes = scores.argsort()[::-1][:top_k]
        return "\n".join(self.documents[index] for index in top_indexes if scores[index] > 0)

    def answer(self, question: str, top_k: int = 5) -> str:
        context = self.retrieve_context(question, top_k=top_k)
        try:
            return generate_answer(question, context, mode="Flat RAG")
        except LLMNotConfiguredError as error:
            return str(error)


if __name__ == "__main__":
    rag = FlatRAG()
    print(rag.answer("Which companies did Google acquire?"))

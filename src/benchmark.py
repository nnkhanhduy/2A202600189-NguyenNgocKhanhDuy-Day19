from __future__ import annotations

import time

import pandas as pd

from config import OUTPUT_DIR, ROOT_DIR
from flat_rag import FlatRAG
from graph_rag import GraphRAG


def main():
    questions_path = ROOT_DIR / "data" / "benchmark_questions.csv"
    questions = pd.read_csv(questions_path)
    OUTPUT_DIR.mkdir(exist_ok=True)

    flat_rag = FlatRAG()
    graph_rag = GraphRAG()
    rows = []

    try:
        for _, item in questions.iterrows():
            question = item["question"]

            flat_started = time.perf_counter()
            flat_context = flat_rag.retrieve_context(question)
            flat_result = flat_rag.answer_with_context(question, flat_context)
            flat_seconds = time.perf_counter() - flat_started

            graph_started = time.perf_counter()
            graph_context = graph_rag.retrieve_context(question)
            graph_result = graph_rag.answer_with_context(question, graph_context)
            graph_seconds = time.perf_counter() - graph_started

            rows.append(
                {
                    "question": question,
                    "query_type": item.get("query_type", ""),
                    "entity": item.get("entity", ""),
                    "expected_answer": item["expected_answer"],
                    "flat_rag_context": flat_context,
                    "flat_rag_answer": flat_result.answer,
                    "flat_prompt_tokens": flat_result.prompt_tokens,
                    "flat_completion_tokens": flat_result.completion_tokens,
                    "flat_total_tokens": flat_result.total_tokens,
                    "graph_rag_context": graph_context,
                    "graph_rag_answer": graph_result.answer,
                    "graph_prompt_tokens": graph_result.prompt_tokens,
                    "graph_completion_tokens": graph_result.completion_tokens,
                    "graph_total_tokens": graph_result.total_tokens,
                    "llm_model": graph_result.model,
                    "flat_rag_seconds": round(flat_seconds, 4),
                    "graph_rag_seconds": round(graph_seconds, 4),
                    "flat_rag_correct": "",
                    "graph_rag_correct": "",
                    "notes": "",
                }
            )
    finally:
        graph_rag.close()

    output_path = OUTPUT_DIR / "benchmark_results.csv"
    pd.DataFrame(rows).to_csv(output_path, index=False)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()

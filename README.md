# Day 19 GraphRAG with Wikipedia + Neo4j

Goal: build a GraphRAG system from a real text corpus.

Pipeline:

```text
100 Wikipedia articles about AI companies
  -> entity and relation extraction
  -> triples.csv
  -> Neo4j graph
  -> GraphRAG multi-hop query
  -> compare with Flat RAG
```

## Setup

```bash
pip install -r requirements.txt
copy .env.example .env
```

Add your OpenAI API key to `.env`:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
```

Start Neo4j:

```bash
docker run --name neo4j-graphrag -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password123 neo4j:latest
```

Open Neo4j Browser at:

```text
http://localhost:7474
```

## Run Pipeline

Download Wikipedia articles listed in `data/wiki_article_titles.txt`:

```bash
python src/fetch_wikipedia.py
```

Extract triples from articles:

```bash
python src/extract_triples.py
```

The extractor creates graph facts such as:

```text
CO_FOUNDED_BY
FORMER_EMPLOYEE_OF
ACQUIRED / ACQUIRED_BY
INVESTED_IN / RECEIVED_INVESTMENT_FROM
PARTNERED_WITH
DEVELOPS / PRODUCT_OF
OWNED_BY / OWNS
SUBSIDIARY_OF / PARENT_ORG_OF
HEADQUARTERED_IN
MENTIONS
```

Import triples into Neo4j:

```bash
python src/import_wiki_triples.py
```

Run Flat RAG vs GraphRAG benchmark:

```bash
python src/benchmark.py
```

Both pipelines use an LLM for final answer generation:

```text
Flat RAG: question -> TF-IDF Wikipedia paragraphs -> LLM answer
GraphRAG: question -> Neo4j graph facts/path -> LLM answer
```

Results are written to:

```text
outputs/benchmark_results.csv
```

The benchmark CSV includes timing and OpenAI token usage:

```text
flat_rag_seconds
graph_rag_seconds
flat_prompt_tokens
flat_completion_tokens
flat_total_tokens
graph_prompt_tokens
graph_completion_tokens
graph_total_tokens
```

Deliverable notes, screenshot queries, and cost analysis are in:

```text
report/DELIVERABLES.md
```

Final lab report:

```text
report/FINAL_REPORT.md
```

## Demo Queries

Flat RAG should work for a simple factual question:

```text
What is OpenAI?
```

GraphRAG should be stronger for multi-hop graph questions:

```text
Which AI companies were co-founded by former Google employees?
```

Useful Neo4j Browser query for visualization:

```cypher
MATCH path = (:Company)<-[:CO_FOUNDED]-(p:Person)-[:FORMER_EMPLOYEE_OF]->(:Company {name: "Google"})
RETURN path
```

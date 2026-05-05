# Day 19 Lab Report: GraphRAG with an AI Company Corpus

## 1. What I Built

In this lab, I built a small GraphRAG pipeline around AI companies. I used Wikipedia articles as the text corpus, extracted entities and relationships into triples, loaded those triples into Neo4j, and compared two retrieval pipelines:

- **Flat RAG**: retrieve relevant Wikipedia paragraphs with TF-IDF, then send the context to an LLM.
- **GraphRAG**: retrieve structured facts or graph paths from Neo4j, then send the graph context to an LLM.

I wanted to see where a normal text-based RAG pipeline is enough, and where a graph-based approach becomes more useful, especially for questions that require multiple hops across companies, people, and relationships.

## 2. Data and Processing Flow

I started with 100 Wikipedia article titles related to AI companies, research labs, AI products, and technology companies.

The final dataset statistics are:

```text
Downloaded Wikipedia articles: 92 / 100
Extracted triples: 1,625
Neo4j nodes: 936
Neo4j relationships: 1,672
```

The pipeline is:

```text
data/wiki_article_titles.txt
  -> src/fetch_wikipedia.py
  -> data/wiki/articles/*.json
  -> src/extract_triples.py
  -> data/wiki/triples.csv
  -> src/import_wiki_triples.py
  -> Neo4j graph
  -> Flat RAG and GraphRAG benchmark
```

The graph contains these main node labels:

```text
Company
Person
Product
Concept
Location
Text
Entity
```

The main relationship types are:

```text
CO_FOUNDED
CO_FOUNDED_BY
FORMER_EMPLOYEE_OF
ACQUIRED
ACQUIRED_BY
INVESTED_IN
PARTNERED_WITH
DEVELOPS
PRODUCT_OF
OWNED_BY
OWNS
SUBSIDIARY_OF
PARENT_ORG_OF
HEADQUARTERED_IN
```

## 3. Neo4j Graph Visualization

For the screenshot, I used this Neo4j query because it shows the main multi-hop case clearly:

```cypher
MATCH path = (company:Company)<-[:CO_FOUNDED]-(person:Person)-[:FORMER_EMPLOYEE_OF]->(:Company {name: "Google"})
RETURN path
```

This query visualizes paths like:

```text
AI Company <- CO_FOUNDED - Person - FORMER_EMPLOYEE_OF -> Google
```

The important answer nodes in this subgraph are:

```text
Adept AI
Character.ai
Inflection AI
Ashish Vaswani
David Luan
Noam Shazeer
Daniel De Freitas
Mustafa Suleyman
Google
```

This is a better screenshot than showing the whole graph because the full graph has hundreds of nodes and becomes too noisy in Neo4j Browser.

## 4. Benchmark Setup

I used 20 benchmark questions:

| Query Type | Count |
|---|---:|
| Simple | 8 |
| One-hop | 4 |
| Multi-hop | 8 |

Each question was sent through both pipelines:

```text
Flat RAG: question -> TF-IDF Wikipedia paragraphs -> LLM answer
GraphRAG: question -> Neo4j graph context -> LLM answer
```

The benchmark output is saved in:

```text
outputs/benchmark_results.csv
```

The LLM model used in the benchmark run was:

```text
gpt-4o-mini
```

## 5. Benchmark Results

### Time

| Metric | Flat RAG | GraphRAG |
|---|---:|---:|
| Total time | 53.12s | 52.03s |
| Average time per question | 2.66s | 2.60s |

The two pipelines had almost the same runtime. GraphRAG was slightly faster overall, but the difference was small.

The reason is that GraphRAG is very fast for some multi-hop questions because it retrieves short graph paths. However, for some simple questions, my current GraphRAG retrieval still pulls too many 2-hop neighbors, so the context can become larger than necessary.

### Token Usage

| Metric | Flat RAG | GraphRAG |
|---|---:|---:|
| Total tokens | 8,408 | 14,024 |
| Share | 37.5% | 62.5% |

Total benchmark token usage:

```text
22,432 tokens
```

GraphRAG used more tokens in this run. This surprised me at first, because graph context is usually expected to be compact. After checking the CSV, the reason was clear: some GraphRAG simple-question contexts included many nearby facts, especially around OpenAI, Microsoft, Anthropic, and Google-related entities.

For the focused multi-hop questions, GraphRAG context was much shorter and cleaner.

## 6. Answer Quality

I manually checked the answers against the expected answers in the benchmark file.

| Query Type | Flat RAG | GraphRAG | My Observation |
|---|---:|---:|---|
| Simple | ~7/8 | ~7/8 | Flat RAG works well when the answer appears directly in a Wikipedia paragraph. |
| One-hop | ~2-3/4 | ~2/4 | Both pipelines still miss some founder/acquisition questions. |
| Multi-hop | ~2/8 | ~7-8/8 | GraphRAG is much better for path-based questions. |
| Overall | ~11-12/20 | ~16-17/20 | GraphRAG performs better mainly because of the multi-hop questions. |

## 7. Examples

### Flat RAG Works Well for Simple Questions

Question:

```text
What is Hugging Face?
```

Flat RAG answered correctly because the Wikipedia paragraph directly describes Hugging Face as a company that builds machine learning tools and hosts models/datasets.

For this type of question, a graph is not strictly necessary. A good paragraph is enough.

### GraphRAG Works Better for Multi-hop Questions

Question:

```text
Which AI companies were co-founded by former Google employees?
```

GraphRAG answered:

```text
Adept AI - Ashish Vaswani, David Luan
Character.ai - Daniel De Freitas, Noam Shazeer
Inflection AI - Mustafa Suleyman
```

This is exactly the kind of question where the graph helps. The answer requires connecting multiple facts:

```text
Company <- CO_FOUNDED - Person - FORMER_EMPLOYEE_OF -> Google
```

Flat RAG struggled with this because the information is spread across multiple articles and is not always written in one paragraph.

### Where GraphRAG Failed

Question:

```text
What is OpenAI?
```

GraphRAG did not answer well. It retrieved facts about Microsoft investing in OpenAI, but it did not retrieve a clean definition of OpenAI itself.

This showed me that GraphRAG is not automatically better. The graph retrieval step still needs to understand the question intent. For a `What is X?` question, it should prioritize relations like:

```text
IS_A
HAS_SUMMARY
```

For a `Who founded X?` question, it should prioritize:

```text
CO_FOUNDED_BY
CO_FOUNDED
```

## 8. Cost Analysis

The following steps did not use LLM tokens:

- Downloading Wikipedia articles.
- Regex-based entity and relation extraction.
- Importing triples into Neo4j.
- TF-IDF retrieval.
- Cypher retrieval from Neo4j.

The LLM was only used for final answer generation in the benchmark.

Number of LLM calls:

```text
20 questions x 2 pipelines = 40 LLM calls
```

Actual token usage from the OpenAI API:

```text
Flat RAG total tokens: 8,408
GraphRAG total tokens: 14,024
Total tokens: 22,432
```

The cost can be calculated with:

```text
cost = input_tokens * input_price + output_tokens * output_price
```

I did not hard-code a dollar amount in the report because model prices can change. The important part is that the benchmark CSV now stores the actual token usage columns:

```text
flat_prompt_tokens
flat_completion_tokens
flat_total_tokens
graph_prompt_tokens
graph_completion_tokens
graph_total_tokens
```

## 9. Limitations

The biggest limitation is the extraction quality. I used regex-based extraction plus some manual seed triples. This is cheap and easy to run, but it creates noise.

Some noisy nodes appeared because long noun phrases were captured as entities. For example, instead of extracting only a company or product name, the extractor sometimes captured a whole phrase from a sentence.

Another limitation is retrieval strategy. GraphRAG worked well when I wrote specific Cypher logic for multi-hop questions, but the general 2-hop retrieval is still too broad for some simple questions.

If I improved this project, I would do three things:

1. Use an LLM-based triple extractor instead of only regex.
2. Add relation-aware retrieval for different question types.
3. Replace TF-IDF with embedding retrieval for the Flat RAG baseline.

## 10. Conclusion

From this lab, I found that Flat RAG is good for direct factual questions when the answer is already present in one retrieved paragraph. It is simple and works well for definition-style questions.

GraphRAG is more useful when the question requires connecting multiple pieces of information. The best example in this project was finding AI companies co-founded by former Google employees. Neo4j made that answer easy to retrieve as a graph path, while Flat RAG often missed the connection.

The current version is not perfect. The graph still has noisy entities, and the retrieval logic should be more relation-aware. Still, the benchmark shows the main lesson clearly: structured graph context helps most when the question needs multi-hop reasoning.

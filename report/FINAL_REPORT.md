# Lab Day 19: GraphRAG với Wikipedia AI Company Corpus

## 1. Mục tiêu

Bài lab xây dựng một hệ thống GraphRAG cho miền tri thức về các công ty AI. Hệ thống dùng 100 tiêu đề bài Wikipedia làm nguồn corpus, trích xuất entity/relation thành triples, import vào Neo4j, sau đó so sánh hai pipeline:

- **Flat RAG**: truy xuất đoạn văn Wikipedia bằng TF-IDF, sau đó gửi context cho LLM.
- **GraphRAG**: truy xuất facts/path từ Neo4j, sau đó gửi graph context cho LLM.

Mục tiêu chính là kiểm tra khác biệt giữa Flat RAG và GraphRAG ở các câu hỏi đơn giản, one-hop và multi-hop.

## 2. Dữ liệu và Pipeline

Nguồn dữ liệu:

```text
100 Wikipedia article titles about AI companies
```

Kết quả tải dữ liệu:

```text
Downloaded articles: 92 / 100
Extracted triples: 1,625
Neo4j nodes: 936
Neo4j relationships: 1,672
```

Luồng xử lý:

```text
data/wiki_article_titles.txt
  -> src/fetch_wikipedia.py
  -> data/wiki/articles/*.json
  -> src/extract_triples.py
  -> data/wiki/triples.csv
  -> src/import_wiki_triples.py
  -> Neo4j Knowledge Graph
  -> Flat RAG / GraphRAG benchmark
```

Các loại node chính:

```text
Company, Person, Product, Concept, Location, Text, Entity
```

Các loại relation chính:

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

## 3. Neo4j Visualization

Query nên dùng để chụp ảnh graph trong Neo4j Browser:

```cypher
MATCH path = (company:Company)<-[:CO_FOUNDED]-(person:Person)-[:FORMER_EMPLOYEE_OF]->(:Company {name: "Google"})
RETURN path
```

Query này thể hiện rõ multi-hop reasoning:

```text
AI Company <- CO_FOUNDED - Person - FORMER_EMPLOYEE_OF -> Google
```

Các answer nodes quan trọng:

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

## 4. Benchmark Setup

Benchmark gồm 20 câu hỏi:

| Query Type | Count |
|---|---:|
| Simple | 8 |
| One-hop | 4 |
| Multi-hop | 8 |

Mỗi câu được chạy qua cả hai pipeline:

```text
Flat RAG: question -> TF-IDF paragraphs -> LLM answer
GraphRAG: question -> Neo4j graph context -> LLM answer
```

Model sử dụng trong lần benchmark:

```text
gpt-4o-mini
```

Kết quả chi tiết nằm trong:

```text
outputs/benchmark_results.csv
```

## 5. Benchmark Result Summary

### Time

| Metric | Flat RAG | GraphRAG |
|---|---:|---:|
| Total time | 53.12s | 52.03s |
| Average time / question | 2.66s | 2.60s |

Hai pipeline có thời gian gần tương đương trong lần chạy này. GraphRAG nhanh hơn nhẹ vì nhiều câu multi-hop có graph context ngắn và có cấu trúc. Tuy nhiên, một số câu simple của GraphRAG có context dài do lấy nhiều neighbor 2-hop, khiến tốc độ không luôn nhanh hơn Flat RAG.

### Token Usage

| Metric | Flat RAG | GraphRAG |
|---|---:|---:|
| Total tokens | 8,408 | 14,024 |
| Share | 37.5% | 62.5% |

Tổng token toàn benchmark:

```text
22,432 tokens
```

GraphRAG dùng nhiều token hơn Flat RAG trong lần chạy này vì một số câu simple lấy context 2-hop quá rộng, ví dụ các facts lân cận quanh OpenAI/Microsoft hoặc Anthropic/OpenAI. Với các câu multi-hop được viết riêng Cypher path, GraphRAG context lại rất ngắn và hiệu quả.

## 6. Quality Evaluation

Đánh giá thủ công dựa trên `expected_answer`:

| Query Type | Flat RAG | GraphRAG | Nhận xét |
|---|---:|---:|---|
| Simple | ~7/8 | ~7/8 | Flat RAG tốt với câu hỏi định nghĩa; GraphRAG sai câu OpenAI do context graph thiếu summary đúng. |
| One-hop | ~2-3/4 | ~2/4 | Cả hai còn yếu ở câu founder OpenAI; cần relation-aware retrieval. |
| Multi-hop | ~2/8 | ~7-8/8 | GraphRAG vượt trội rõ rệt nhờ truy vấn path trong Neo4j. |
| Overall | ~11-12/20 | ~16-17/20 | GraphRAG tốt hơn chủ yếu nhờ nhóm multi-hop. |

### Ví dụ Flat RAG làm tốt

Question:

```text
What is Hugging Face?
```

Flat RAG trả lời đúng vì đoạn Wikipedia chứa trực tiếp mô tả công ty và nền tảng machine learning.

### Ví dụ GraphRAG làm tốt

Question:

```text
Which AI companies were co-founded by former Google employees?
```

GraphRAG trả lời:

```text
Adept AI - Ashish Vaswani, David Luan
Character.ai - Daniel De Freitas, Noam Shazeer
Inflection AI - Mustafa Suleyman
```

Đây là câu hỏi multi-hop cần nối các quan hệ:

```text
Company <- CO_FOUNDED - Person - FORMER_EMPLOYEE_OF -> Google
```

Flat RAG không tìm được đầy đủ vì thông tin nằm rải rác ở nhiều bài và không có cấu trúc path rõ ràng.

### Ví dụ GraphRAG còn yếu

Question:

```text
What is OpenAI?
```

GraphRAG trả lời rằng context không đủ thông tin về OpenAI. Nguyên nhân là retrieval hiện tại lấy nhiều facts liên quan Microsoft/OpenAI nhưng không ưu tiên relation `IS_A` hoặc `HAS_SUMMARY` của chính OpenAI.

Điều này cho thấy GraphRAG không chỉ phụ thuộc vào graph, mà còn phụ thuộc mạnh vào chiến lược retrieval.

## 7. Cost Analysis

Các bước không dùng LLM token:

- Tải Wikipedia articles.
- Regex-based entity/relation extraction.
- Import triples vào Neo4j.
- Cypher graph retrieval.
- TF-IDF retrieval.

Các bước dùng LLM token:

- Flat RAG answer generation.
- GraphRAG answer generation.

Số lần gọi LLM:

```text
20 questions x 2 pipelines = 40 LLM calls
```

Token usage thực tế từ OpenAI API:

```text
Flat RAG total tokens: 8,408
GraphRAG total tokens: 14,024
Total benchmark tokens: 22,432
```

Công thức tính chi phí:

```text
Cost = input_tokens * input_price_per_token + output_tokens * output_price_per_token
```

Vì giá model thay đổi theo thời điểm, nên phần báo cáo chỉ ghi token usage thực tế. Khi cần tính tiền, dùng số token trong `outputs/benchmark_results.csv` nhân với bảng giá hiện tại của model `gpt-4o-mini`.

## 8. Nhận xét và Hạn chế

Ưu điểm:

- Graph có kích thước đủ lớn cho lab, không phải toy example.
- Neo4j biểu diễn được nhiều loại quan hệ giữa company, person, product và organization.
- GraphRAG chứng minh lợi thế rõ ở multi-hop reasoning.
- Benchmark lưu được context, answer, time và token usage cho từng pipeline.

Hạn chế:

- Extraction hiện dùng regex và seed triples nên có noise.
- Một số node bị dài hoặc không sạch, ví dụ cụm danh từ bị bắt quá rộng.
- GraphRAG simple/one-hop chưa tối ưu vì chưa luôn filter relation theo intent của câu hỏi.
- Flat RAG dùng TF-IDF nên không mạnh bằng embedding retrieval.

## 9. Kết luận

Kết quả benchmark cho thấy Flat RAG phù hợp với các câu hỏi đơn giản khi câu trả lời nằm trực tiếp trong một đoạn Wikipedia. Tuy nhiên, Flat RAG yếu ở các câu hỏi cần nối nhiều facts qua nhiều tài liệu.

GraphRAG hoạt động tốt hơn trong các câu multi-hop vì Neo4j lưu quan hệ tường minh và có thể truy xuất path có cấu trúc. Với câu hỏi về các AI companies được co-founded bởi former Google employees, GraphRAG trả lời đúng và giải thích được path liên quan.

Hệ thống hiện tại đáp ứng yêu cầu lab: có mã nguồn, ảnh graph có thể chụp từ Neo4j, bảng benchmark 20 câu, và phân tích chi phí dựa trên token usage/time thực tế.

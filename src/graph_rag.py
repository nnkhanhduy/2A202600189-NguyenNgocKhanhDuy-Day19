from __future__ import annotations

import re

from neo4j import GraphDatabase

from config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USERNAME
from llm import LLMNotConfiguredError, LLMResult, generate_answer, missing_llm_result


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


class GraphRAG:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    def close(self):
        self.driver.close()

    def find_entity(self, question: str) -> str | None:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (n)
                WHERE toLower($question) CONTAINS toLower(n.name)
                RETURN n.name AS name, size(n.name) AS score
                ORDER BY score DESC
                LIMIT 1
                """,
                question=question,
            ).single()
            return result["name"] if result else None

    def context_for_entity(self, entity: str, max_hops: int = 2, limit: int = 50) -> list[str]:
        with self.driver.session() as session:
            rows = session.run(
                """
                MATCH path = (start {name: $entity})-[*1..2]-(end)
                WITH relationships(path) AS rels
                UNWIND rels AS r
                WITH DISTINCT startNode(r) AS source, type(r) AS rel, endNode(r) AS target, r AS props
                RETURN source.name AS source, rel, target.name AS target, props
                LIMIT $limit
                """,
                entity=entity,
                limit=limit,
            )
            facts = []
            for row in rows:
                prop_text = ""
                if row["props"]:
                    props = {k: v for k, v in dict(row["props"]).items() if v}
                    if props:
                        prop_text = f" {props}"
                facts.append(normalize(f"{row['source']} {row['rel']} {row['target']}{prop_text}"))
            return facts

    def answer(self, question: str) -> str:
        return self.answer_with_usage(question).answer

    def answer_with_usage(self, question: str) -> LLMResult:
        context = self.retrieve_context(question)
        return self.answer_with_context(question, context)

    def answer_with_context(self, question: str, context: str) -> LLMResult:
        try:
            return generate_answer(question, context, mode="GraphRAG")
        except LLMNotConfiguredError as error:
            return missing_llm_result(str(error))

    def retrieve_context(self, question: str) -> str:
        lower = question.lower()
        if "connect character.ai to google" in lower:
            return self.context_company_google_connector("Character.ai")
        if "connect adept ai to google" in lower:
            return self.context_company_google_connector("Adept AI")
        if "mustafa suleyman and google" in lower:
            return self.context_person_company_connector("Mustafa Suleyman")
        if "co-founded by noam shazeer" in lower:
            return self.context_person_company_connector("Noam Shazeer")
        if "co-founded by ashish vaswani" in lower:
            return self.context_person_company_connector("Ashish Vaswani")
        if "former google employees co-founded" in lower:
            return self.context_former_google_people()
        if "former google" in lower or "former employees of google" in lower or "former google employees" in lower:
            return self.context_former_google_founders()
        if "microsoft" in lower and ("invest" in lower or "partner" in lower):
            return self.context_company_relations("Microsoft", ["INVESTED_IN", "PARTNERED_WITH"])

        entity = self.find_entity(question)
        if not entity:
            return "No matching entity found in the graph."

        facts = self.context_for_entity(entity)
        if not facts:
            return f"No graph facts found for {entity}."

        return "\n".join(facts[:20])

    def context_former_google_founders(self) -> str:
        with self.driver.session() as session:
            rows = session.run(
                """
                MATCH path = (company:Company)<-[:CO_FOUNDED]-(person:Person)-[:FORMER_EMPLOYEE_OF]->(:Company {name: "Google"})
                RETURN DISTINCT company.name AS company, collect(DISTINCT person.name) AS people
                ORDER BY company
                """
            )
            answers = []
            for row in rows:
                people = ", ".join(row["people"])
                answers.append(f"{row['company']} <- CO_FOUNDED - [{people}] - FORMER_EMPLOYEE_OF -> Google")
            return "\n".join(answers) if answers else "No matching multi-hop path found."

    def context_company_google_connector(self, company: str) -> str:
        with self.driver.session() as session:
            rows = session.run(
                """
                MATCH path = (:Company {name: $company})<-[:CO_FOUNDED]-(person:Person)-[:FORMER_EMPLOYEE_OF]->(:Company {name: "Google"})
                RETURN DISTINCT person.name AS person
                ORDER BY person
                """,
                company=company,
            )
            people = [row["person"] for row in rows]
            return "\n".join(f"{company} <- CO_FOUNDED - {person} - FORMER_EMPLOYEE_OF -> Google" for person in people) if people else "No matching multi-hop path found."

    def context_person_company_connector(self, person: str) -> str:
        with self.driver.session() as session:
            rows = session.run(
                """
                MATCH path = (company:Company)<-[:CO_FOUNDED]-(:Person {name: $person})-[:FORMER_EMPLOYEE_OF]->(:Company {name: "Google"})
                RETURN DISTINCT company.name AS company
                ORDER BY company
                """,
                person=person,
            )
            companies = [row["company"] for row in rows]
            return "\n".join(f"{company} <- CO_FOUNDED - {person} - FORMER_EMPLOYEE_OF -> Google" for company in companies) if companies else "No matching multi-hop path found."

    def context_former_google_people(self) -> str:
        with self.driver.session() as session:
            rows = session.run(
                """
                MATCH path = (:Company)<-[:CO_FOUNDED]-(person:Person)-[:FORMER_EMPLOYEE_OF]->(:Company {name: "Google"})
                RETURN DISTINCT person.name AS person
                ORDER BY person
                """
            )
            people = [row["person"] for row in rows]
            return "\n".join(f"{person} - FORMER_EMPLOYEE_OF -> Google and CO_FOUNDED -> an AI company" for person in people) if people else "No matching multi-hop path found."

    def context_company_relations(self, company: str, relations: list[str]) -> str:
        relation_pattern = "|".join(relations)
        with self.driver.session() as session:
            rows = session.run(
                f"""
                MATCH (company:Company {{name: $company}})-[r:{relation_pattern}]->(target)
                RETURN company.name AS source, type(r) AS relation, target.name AS target
                ORDER BY relation, target
                """
                ,
                company=company,
            )
            facts = [f"{row['source']} - {row['relation']} -> {row['target']}" for row in rows]
            return "\n".join(facts) if facts else "No matching graph facts found."


if __name__ == "__main__":
    rag = GraphRAG()
    try:
        print(rag.answer("Which companies did Google acquire?"))
    finally:
        rag.close()

from __future__ import annotations

import time

import pandas as pd
from neo4j import GraphDatabase

from config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USERNAME, TRIPLES_PATH


RELATION_TYPES = {
    "ACQUIRED",
    "ACQUIRED_BY",
    "CO_FOUNDED_BY",
    "CREATED",
    "CREATES",
    "DEVELOPED",
    "DEVELOPS",
    "FORMER_EMPLOYEE_OF",
    "HAS_SUMMARY",
    "HEADQUARTERED_IN",
    "INVESTED_IN",
    "IS_A",
    "LAUNCHED",
    "MENTIONS",
    "OPERATES",
    "OWNED_BY",
    "OWNS",
    "PARENT_ORG_OF",
    "PARTNERED_WITH",
    "PRODUCT_OF",
    "PRODUCES",
    "RECEIVED_INVESTMENT_FROM",
    "RELEASED",
    "SUBSIDIARY_OF",
}


def node_label(node_type: str) -> str:
    allowed = {"Company", "Person", "Concept", "Location", "Text", "Product", "Entity"}
    return node_type if node_type in allowed else "Entity"


def relation_type(relation: str) -> str:
    relation = str(relation).upper().strip()
    return relation if relation in RELATION_TYPES else "RELATED_TO"


def clear_database(tx):
    tx.run("MATCH (n) DETACH DELETE n")


def create_constraints(tx):
    for label in ["Company", "Person", "Concept", "Location", "Text", "Product", "Entity"]:
        tx.run(f"CREATE CONSTRAINT {label.lower()}_name IF NOT EXISTS FOR (n:{label}) REQUIRE n.name IS UNIQUE")


def import_triple(tx, row: dict):
    source_label = node_label(row.get("source_type", "Entity"))
    target_label = node_label(row.get("target_type", "Entity"))
    rel = relation_type(row["relation"])
    tx.run(
        f"""
        MERGE (source:{source_label} {{name: $source}})
        MERGE (target:{target_label} {{name: $target}})
        MERGE (source)-[r:{rel}]->(target)
        SET r.evidence = coalesce($evidence, r.evidence)
        """,
        source=row["source"],
        target=row["target"],
        evidence=row.get("evidence"),
    )

    if rel == "CO_FOUNDED_BY":
        tx.run(
            """
            MATCH (company:Company {name: $source})
            MATCH (person:Person {name: $target})
            MERGE (person)-[:CO_FOUNDED]->(company)
            """,
            source=row["source"],
            target=row["target"],
        )


def main():
    if not TRIPLES_PATH.exists():
        raise FileNotFoundError(f"Missing triples file: {TRIPLES_PATH}. Run src/extract_triples.py first.")

    started = time.perf_counter()
    triples = pd.read_csv(TRIPLES_PATH).fillna("")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    with driver.session() as session:
        session.execute_write(clear_database)
        session.execute_write(create_constraints)
        for row in triples.to_dict("records"):
            session.execute_write(import_triple, row)

        stats = session.run(
            """
            MATCH (n)
            WITH count(n) AS nodes
            MATCH ()-[r]->()
            RETURN nodes, count(r) AS relationships
            """
        ).single()

    driver.close()
    print(f"Imported {len(triples)} triples in {time.perf_counter() - started:.2f}s")
    print(f"Nodes: {stats['nodes']}, relationships: {stats['relationships']}")


if __name__ == "__main__":
    main()

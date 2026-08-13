
import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
from groq import Groq

load_dotenv()

NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USERNAME = os.environ["NEO4J_USERNAME"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
TENANT_ID = "demo-tenant-1"

embed_model = SentenceTransformer("all-MiniLM-L6-v2")
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
GROQ_MODEL = "llama-3.3-70b-versatile"

neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
chroma_client = chromadb.PersistentClient(path="./chroma_db")
raptor_collection = chroma_client.get_collection(name="raptor_tree")


def retrieve_graph_facts():
    """
    Generic retrieval: all overdue invoices for this tenant, with vendor and
    parent company info where it exists. This is deliberately broad (not
    tailored to one specific question) since we're skipping the router -
    the finance agent decides what's relevant from here.
    """
    query = """
    MATCH (i:Invoice {tenant_id: $tenant_id, status: "overdue"})-[:ISSUED_BY]->(v:Vendor)
    OPTIONAL MATCH (v)-[:SUBSIDIARY_OF]->(pc:ParentCompany)
    RETURN i.id AS invoice_id, i.amount AS amount, i.due_date AS due_date,
           v.name AS vendor, pc.name AS parent_company
    """
    with neo4j_driver.session() as session:
        result = session.run(query, tenant_id=TENANT_ID)
        facts = [dict(record) for record in result]
    return facts


def retrieve_raptor_context(question, n_results=3):
    """Embeds the question and pulls the closest matching nodes from ANY
    level of the RAPTOR tree (leaf, level-1 summary, or root)."""
    query_embedding = embed_model.encode([question]).tolist()
    results = raptor_collection.query(query_embeddings=query_embedding, n_results=n_results)
    return list(zip(results["documents"][0], results["metadatas"][0], results["distances"][0]))


def fuse_context(graph_facts, raptor_results):
    """Merges both retrieval sources into one text block for the finance agent."""
    graph_section = "GRAPH FACTS (structured, from the ledger):\n"
    if graph_facts:
        for f in graph_facts:
            parent = f["parent_company"] or "no parent company on record"
            graph_section += (
                f"- Invoice {f['invoice_id']}: ${f['amount']} from vendor {f['vendor']} "
                f"(parent: {parent}), due {f['due_date']}, status: overdue\n"
            )
    else:
        graph_section += "- No overdue invoices found.\n"

    raptor_section = "\nDOCUMENT FACTS (from contracts, via RAPTOR retrieval):\n"
    for text, metadata, distance in raptor_results:
        raptor_section += f"- (relevance distance {distance:.3f}, tree level {metadata['level']}): {text}\n"

    return graph_section + raptor_section


def generate_draft_answer(question, retry_feedback=None):
    """
    Runs graph + RAPTOR retrieval, fuses them, and asks the finance agent
    to draft an answer. If retry_feedback is provided (from a rejected
    previous attempt), it's included so the agent can correct itself.

    Returns (draft_answer, context, graph_facts, raptor_results) so the
    reviewer agent can check the answer against the same context it was
    generated from.
    """
    graph_facts = retrieve_graph_facts()
    raptor_results = retrieve_raptor_context(question)
    context = fuse_context(graph_facts, raptor_results)

    feedback_block = ""
    if retry_feedback:
        feedback_block = (
            f"\nNOTE: a previous attempt at this answer was rejected for the "
            f"following reason(s), do not repeat these mistakes:\n{retry_feedback}\n"
        )

    prompt = f"""You are a finance assistant. Answer the question using ONLY the facts below.
If the facts don't fully answer the question, say what's missing rather than guessing.
{feedback_block}
{context}

QUESTION: {question}

Answer concisely, citing which invoice IDs or contract sections your answer relies on."""

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    draft_answer = response.choices[0].message.content.strip()
    return draft_answer, context, graph_facts, raptor_results


def ask_finance_agent(question):
    """Standalone demo entry point - just prints the draft answer, no review."""
    draft_answer, context, _, _ = generate_draft_answer(question)
    print("=" * 70)
    print(f"QUESTION: {question}\n")
    print("--- FUSED CONTEXT SENT TO THE AGENT ---")
    print(context)
    print("--- ANSWER ---")
    print(draft_answer)
    print("=" * 70)


if __name__ == "__main__":
    # Q1-style + Q2-style combined question, to test both retrieval paths at once
    ask_finance_agent(
        "Are any subsidiaries of Acme Holdings overdue, and what's the late payment penalty?"
    )
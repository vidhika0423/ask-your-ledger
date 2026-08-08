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
    generic retrieval :
    all overdue invoice for this tenant, with vendor and parent company info if exists
    """
    query = """
    MATCH (i:Invoice{tenant_id: $tenant_id, status: "overdue"})-[:ISSUED_BY]->(v:Vendor)
    OPTIONAL MATCH (V)-[:SUBSIDIARY_OF]->(pc:ParentCompany)
    RETURN i.id as invoice_id, i.amount AS amount, i.due_date AS due_date,
    v.name AS vendor, pc.name AS parent_company
    """

    with neo4j_driver.session() as session:
        result = session.run(query, tenant_id = TENANT_ID)
        facts = [dict(record) for record in result]
    return facts

def retrieve_raptor_context(question, n_results=3):
    """
    Embeds the question and pulls the closest matching nodes from ANY
    level of raptor tree (leaf, level-1 summary, or root).
    """
    query_embedding = embed_model.encode([question]).tolist()
    results = raptor_collection.query(query_embeddings=query_embedding, n_results = n_results)
    return list(zip(results["documents"][0], results["metadatas"][0], results['distances'][0]))

def fuse_context(graph_facts, raptor_results):
    """
    merges both retrieval sources into one text block
    """
    graph_section = "GRAPH FACTS (structured, from the ledger):\n"
    if graph_facts:
        for f in graph_facts:
            parent = f["parent_company"] or "no parent company on record"
            graph_section += (
                f"- Invoice {f["invoice_id"]}: ${f["amount"]} from vendor {f['vendor']}"
                f"(parent: {parent}), due {f['due_date']}, status: overdue \n'"
            )
    else:
        graph_section += "- No overdue invoices found.\n"

    raptor_section = "\nDOCUMENT FACTS (from contracts, via RAPTOR retrival):\n"
    for text, metadata,distance in raptor_results:
        raptor_section += f"- (relevance distance {distance:.3f}, tree level {metadata['level']}): {text}\n"
    return graph_section + raptor_section

def ask_finance_agent(question):
    graph_facts = retrieve_graph_facts()
    raptor_results= retrieve_raptor_context(question)
    context = fuse_context(graph_facts,raptor_results)

    prompt = f"""
    You are a finance assistant. Answer the question using ONLY the facts below.
    If the facts don't fully answer the question, say what's missing rather than guessing.
    {context}
    Question: {question}
    Answer concisely, citing which invoice IDs or contract sections your answer relies on.
    """

    response = groq_client.chat.completions.create(
        model = GROQ_MODEL,
        max_tokens = 300,
        messages = [{"role":"user", "content":prompt}]
    )

    print(f"QUESTION: {question}\n")
    print("--- FUSED CONTEXT SENT TO THE AGENT ---")
    print(context)
    print("--- ANSWER ---")
    print(response.choices[0].message.content.strip())
    print("=" * 70)


if __name__ == "__main__":
    ask_finance_agent(
        "Are any subsidiaries of Acme Holdings overdue, and what's the late payment penalty?"
    )
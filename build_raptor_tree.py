"""
Builds a RAPTOR tree over the two contract files in seed_data/contracts/.

Pipeline:
  1. Chunk each contract by its SECTION headers (leaf level)
  2. Embed every chunk
  3. Cluster chunks with GaussianMixture (soft/probabilistic clustering)
  4. Summarize each cluster with an LLM -> becomes a level-1 node
  5. Summarize the level-1 summaries together -> becomes the root (level-2) node
  6. Store every node (leaves + level-1 + root), at every level, into Chroma
     so retrieval can pull from whichever level actually answers a question

Install first:
    pip install chromadb sentence-transformers scikit-learn groq python-dotenv

Requires a Groq API key set as an environment variable:
    GROQ_API_KEY=gsk_...
(add this to your .env file alongside your Neo4j credentials - get a key at
https://console.groq.com/keys)

Run:
    python build_raptor_tree.py
"""

import os
import re
from pathlib import Path

import numpy as np
import chromadb
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from sklearn.mixture import GaussianMixture
from groq import Groq

load_dotenv()

CONTRACTS_DIR = Path(__file__).parent / "seed_data" / "contracts"
embed_model = SentenceTransformer("all-MiniLM-L6-v2")
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])

# llama-3.3-70b-versatile is a solid default on Groq for summarization quality.
# Swap to a smaller/faster model (e.g. llama-3.1-8b-instant) if you want lower latency.
GROQ_MODEL = "llama-3.3-70b-versatile"


def summarize(text, instruction="Summarize the following contract text in 2-3 sentences, preserving specific numbers, dates, and defined terms exactly:"):
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": f"{instruction}\n\n{text}"}],
    )
    return response.choices[0].message.content.strip()


def chunk_contracts():
    """Splits each contract file into chunks by its SECTION headers."""
    chunks = []
    for filepath in CONTRACTS_DIR.glob("*.txt"):
        text = filepath.read_text()
        # Split on "SECTION N — TITLE" headers, keeping the header with its content
        sections = re.split(r"\n(?=SECTION \d+)", text)
        for section in sections:
            section = section.strip()
            if section and len(section) > 20:  # skip empty/tiny fragments
                chunks.append({"source": filepath.name, "text": section})
    return chunks


def build_tree():
    # --- Level 0: leaf chunks ---
    leaf_chunks = chunk_contracts()
    print(f"Level 0: {len(leaf_chunks)} leaf chunks from {len(list(CONTRACTS_DIR.glob('*.txt')))} documents.\n")

    leaf_texts = [c["text"] for c in leaf_chunks]
    leaf_embeddings = embed_model.encode(leaf_texts)

    # --- Cluster leaf chunks with GMM ---
    # With ~10 chunks, 3 clusters is a reasonable manual choice for this demo scale.
    # In production, you'd select this with BIC instead of a fixed number.
    n_clusters = min(3, len(leaf_chunks))
    gmm = GaussianMixture(n_components=n_clusters, random_state=0, n_init=5)
    gmm.fit(leaf_embeddings)
    labels = gmm.predict(leaf_embeddings)
    probs = gmm.predict_proba(leaf_embeddings)

    print("Cluster assignments (hard label + soft probabilities):")
    for i, chunk in enumerate(leaf_chunks):
        prob_str = ", ".join(f"{p:.2f}" for p in probs[i])
        preview = chunk["text"][:50].replace("\n", " ")
        print(f"  [{labels[i]}] probs=({prob_str}) - {preview}...")
    print()

    # --- Level 1: summarize each cluster ---
    level1_nodes = []
    for cluster_id in range(n_clusters):
        cluster_texts = [leaf_chunks[i]["text"] for i in range(len(leaf_chunks)) if labels[i] == cluster_id]
        if not cluster_texts:
            continue
        combined = "\n\n".join(cluster_texts)
        summary = summarize(combined)
        level1_nodes.append({"cluster_id": cluster_id, "text": summary, "source_count": len(cluster_texts)})
        print(f"Level 1 summary (cluster {cluster_id}, from {len(cluster_texts)} chunks):\n  {summary}\n")

    # --- Level 2: root summary of all level-1 summaries ---
    combined_summaries = "\n\n".join(node["text"] for node in level1_nodes)
    root_summary = summarize(
        combined_summaries,
        instruction="Combine the following section summaries into a single overall summary of the whole contract, in 2-3 sentences:",
    )
    print(f"Level 2 (root) summary:\n  {root_summary}\n")

    return leaf_chunks, level1_nodes, root_summary


def store_in_chroma(leaf_chunks, level1_nodes, root_summary):
    client = chromadb.PersistentClient(path="./chroma_db")
    collection = client.get_or_create_collection(name="raptor_tree")

    ids, texts, metadatas = [], [], []

    for i, chunk in enumerate(leaf_chunks):
        ids.append(f"leaf_{i}")
        texts.append(chunk["text"])
        metadatas.append({"level": 0, "source": chunk["source"]})

    for node in level1_nodes:
        ids.append(f"level1_{node['cluster_id']}")
        texts.append(node["text"])
        metadatas.append({"level": 1, "source_count": node["source_count"]})

    ids.append("root")
    texts.append(root_summary)
    metadatas.append({"level": 2})

    embeddings = embed_model.encode(texts).tolist()
    collection.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)

    print(f"Stored {len(ids)} nodes total (leaves + level-1 + root) in Chroma collection 'raptor_tree'.")


if __name__ == "__main__":
    leaf_chunks, level1_nodes, root_summary = build_tree()
    store_in_chroma(leaf_chunks, level1_nodes, root_summary)
import chromadb
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

client = chromadb.PersistentClient(path="./chroma_db")

collection = client.get_or_create_collection(name = "sanity_check")

documents = {
    "chunk_a": "LAte payment incur a penalty of 1.5% per month on the outstanding balance.",
    "chunk_b": "the net-30 payment window and 1.5% monthly late penalty on overdue balances remain in effect.",
    "chunk_c": "this agreement renews automatically each year on the anniversary of the effective date.", 
}

ids = list(documents.keys())
texts = list(documents.values())
embeddings = model.encode(texts).tolist()

collection.add(ids = ids, documents = texts, embeddings = embeddings)
print(f"Stored {len(ids)} chunks in chroma\n")

query_test = "What happens if payment is late?"
query_embedding = model.encode([query_test]).tolist()

results = collection.query(query_embeddings=query_embedding, n_results = 3)

print("Results, ranked by similariyt")
for doc_id,doc_test, doc_distance in zip(
    results["ids"][0], results["documents"][0], results["distances"][0]
):
    print(f"  {doc_id} (distance={doc_distance:.4f}): {doc_test}")
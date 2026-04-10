import chromadb
from chromadb.utils import embedding_functions
from config import VECTOR_DB_PATH

EMBED_FN = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

def get_collection():
    client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
    return client.get_or_create_collection(
        name="company_knowledge",
        embedding_function=EMBED_FN
    )

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    words  = text.split()
    chunks = []
    i      = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return [c for c in chunks if c.strip()]

def index_documents(docs: list):
    collection = get_collection()

    existing = collection.get()
    if existing["ids"]:
        collection.delete(ids=existing["ids"])
        print(f"  🗑️  Cleared {len(existing['ids'])} old chunks")

    all_chunks = []
    all_ids    = []
    all_metas  = []

    for doc in docs:
        chunks = chunk_text(doc["text"])
        for i, chunk in enumerate(chunks):
            safe_name = doc["name"].replace(" ", "_").replace("/", "_")[:50]
            all_chunks.append(chunk)
            all_ids.append(f"{safe_name}_{i}")
            all_metas.append({"source": doc["name"], "chunk": i})

    if all_chunks:
        batch_size = 100
        for i in range(0, len(all_chunks), batch_size):
            collection.add(
                documents=all_chunks[i:i + batch_size],
                ids=all_ids[i:i + batch_size],
                metadatas=all_metas[i:i + batch_size]
            )
        print(f"  ✅ Indexed {len(all_chunks)} chunks from {len(docs)} documents")
    else:
        print("  ⚠️  No content to index")

def search(query: str, n_results: int = 5) -> list:
    collection = get_collection()
    count = collection.count()
    if count == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, count)
    )

    output = []
    for i, doc in enumerate(results["documents"][0]):
        output.append({
            "content": doc,
            "source":  results["metadatas"][0][i]["source"]
        })
    return output

def get_stats() -> dict:
    collection = get_collection()
    return {"total_chunks": collection.count()}

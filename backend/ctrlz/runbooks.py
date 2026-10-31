import hashlib
import math
import re
from pathlib import Path


def embedding(text):
    """Offline feature hashing: repeatable lexical retrieval, no embedding API/secret."""
    vector = [0.0] * 256
    for token in re.findall(r"[a-z]+", text.lower()):
        index = int.from_bytes(hashlib.sha256(token.encode()).digest()[:4], "big") % 256
        vector[index] += 1
    norm = math.sqrt(sum(v*v for v in vector)) or 1
    return [v/norm for v in vector]


class Runbooks:
    def __init__(self, source: Path, persistence: Path):
        import chromadb
        self.client = chromadb.PersistentClient(path=str(persistence))
        self.collection = self.client.get_or_create_collection("recovery-runbooks", embedding_function=None, metadata={"hnsw:space": "cosine"})
        paths = sorted(source.glob("*.md"))
        if paths:
            docs = [p.read_text() for p in paths]
            self.collection.upsert(ids=[p.name for p in paths], documents=docs, embeddings=[embedding(d) for d in docs])

    def search(self, query: str):
        if self.collection.count() == 0:
            return []
        result = self.collection.query(query_embeddings=[embedding(query)], n_results=min(3, self.collection.count()))
        return [{"id": i, "text": d, "distance": distance, "retrieval": "ChromaDB lexical hash cosine"} for i, d, distance in zip(result["ids"][0], result["documents"][0], result["distances"][0])]

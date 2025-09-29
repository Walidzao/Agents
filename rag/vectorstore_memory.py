import numpy as np
from rag.vectorstore import VectorStore

class InMemoryVectorStore(VectorStore):
    def __init__(self):
        self.chunks = []

    def add_chunk(self, chunk):
        self.chunks.append(chunk)

    def cosine_similarity(self, a, b):
        a = np.array(a)
        b = np.array(b)
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def search(self, query_embedding, top_k=5):
        scores = [(self.cosine_similarity(query_embedding, chunk.embedding), chunk) for chunk in self.chunks]
        scores.sort(key=lambda x: x[0], reverse=True)
        return [chunk for score, chunk in scores[:top_k]]

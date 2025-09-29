from abc import ABC, abstractmethod

class VectorStore(ABC):
    @abstractmethod
    def add_chunk(self, chunk):
        pass

    @abstractmethod
    def search(self, query_embedding, top_k=5):
        pass

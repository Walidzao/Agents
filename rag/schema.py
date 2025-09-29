from dataclasses import dataclass

@dataclass
class Document:
    id: str
    content: str
    metadata: dict

@dataclass
class Chunk:
    id: str
    document_id: str
    content: str
    embedding: list[float]

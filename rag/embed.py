import hashlib

def embed_text(text, embedding_dimension=10):
    hasher = hashlib.sha256()
    hasher.update(text.encode('utf-8'))
    hash_value = int(hasher.hexdigest(), 16)
    embedding = [(hash_value % (i + 1)) / (i + 1) for i in range(embedding_dimension)]
    return embedding

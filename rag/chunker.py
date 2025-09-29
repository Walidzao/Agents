def chunk_document(document, chunk_size=100, max_document_size_kb=200):
    if len(document.content.encode('utf-8')) > max_document_size_kb * 1024:
        print(f"Skipping document {document.id} because it exceeds the size limit.")
        return []

    chunks = []
    text = document.content
    for i in range(0, len(text), chunk_size):
        chunk_content = text[i:i + chunk_size]
        chunk_id = f"{document.id}_chunk_{i // chunk_size}"
        chunk = Chunk(id=chunk_id, document_id=document.id, content=chunk_content, embedding=[])
        chunks.append(chunk)
    return chunks

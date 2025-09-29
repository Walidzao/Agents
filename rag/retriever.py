def retrieve_relevant_chunks(query, vector_store, embed_function, top_k=5):
    query_embedding = embed_function(query)
    relevant_chunks = vector_store.search(query_embedding, top_k=top_k)
    return relevant_chunks

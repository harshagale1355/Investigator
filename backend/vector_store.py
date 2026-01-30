from backend.chunking import splitter
from backend.embedding import embedding_data
from langchain_community.vectorstores import Chroma

def vector(loaded_log):
    splits = splitter(loaded_log)
    embeddings = embedding_data()

    vector_store = Chroma.from_documents(
        documents=splits,
        embedding=embeddings,
        persist_directory="./chroma_db"
    )
    return vector_store


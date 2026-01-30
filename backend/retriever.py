from backend.vector_store import vector
from backend.LLM import llm_model
from langchain_classic.chains import RetrievalQA


def retriever(doc):
    vectordb = vector(doc)
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm_model(),
        chain_type="stuff",
        retriever=vectordb.as_retriever(
            search_kwargs={
                "k": 5,
            }
        ),
        return_source_documents=True,
    )
    return qa_chain
from backend.retriever import retriever

def query(qa_chain,question: str):
    result = qa_chain.invoke({"query":question})
    return {
        "answer": result["result"]
    }

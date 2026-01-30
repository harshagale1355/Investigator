import streamlit as st
from langchain_core.documents import Document

from dotenv import load_dotenv

from backend.retriever import retriever

# Load env variables (OPENROUTER_API_KEY etc.)
load_dotenv()

st.set_page_config(page_title="AI System Log Investigator", page_icon="🤖", layout="wide")

st.title("🤖 AI System Log Investigator")
st.caption("Upload system logs and ask questions like: *Why did it crash? What is the root cause?*")

uploaded_file = st.file_uploader(
    "Upload your system log file",
    type=["log", "txt"]
)

if uploaded_file:
    # Read file
    log_text = uploaded_file.read().decode("utf-8", errors="ignore")

    # Preview
    st.subheader("📄 Log Preview")
    st.code(log_text[:3000])

    # Create LangChain Document
    doc = Document(
        page_content=log_text,
        metadata={"source": uploaded_file.name}
    )

    # Create QA chain only once per uploaded file
    if "qa_chain" not in st.session_state:
        st.session_state.qa_chain = retriever(doc)

    # Store chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    st.subheader("💬 Ask Questions About Your Logs")

    # Display old messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    user_question = st.chat_input("Ask something like: Why did the server crash?")

    if user_question:
        # Show user message
        st.session_state.messages.append({"role": "user", "content": user_question})
        with st.chat_message("user"):
            st.markdown(user_question)

        # Get assistant response
        with st.chat_message("assistant"):
            with st.spinner("Analyzing logs..."):
                try:
                    result = st.session_state.qa_chain.invoke({"query": user_question})

                    # RetrievalQA returns dict like:
                    # {"result": "...", "source_documents": [...]}
                    answer = result.get("result", "No answer generated.")
                    sources = result.get("source_documents", [])

                    st.markdown(answer)

                    # Show evidence (sources)
                    if sources:
                        with st.expander("🧾 Evidence (retrieved log chunks)"):
                            for i, doc in enumerate(sources, start=1):
                                st.markdown(f"**Chunk {i}:**")
                                st.code(doc.page_content[:1500])

                    # Save assistant response
                    st.session_state.messages.append({"role": "assistant", "content": answer})

                except Exception as e:
                    st.error(f"Error: {e}")

else:
    st.info("Upload a `.log` or `.txt` file to start.")

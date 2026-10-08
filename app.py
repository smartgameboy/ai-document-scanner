import asyncio
import hashlib
import os
import streamlit as st
from dotenv import load_dotenv
from manager import ManagerAgent, RAGIndex
from providers import Provider

load_dotenv()
st.set_page_config(page_title="AI Document Scanner", page_icon="📄", layout="wide")
st.title("📄 AI Document Scanner")
st.caption("Shreya Baidya · Final Project · MCP tools + RAG with Python")
st.write("Upload documents, build a searchable index, and ask questions with source references.")
with st.sidebar:
    st.header("LLM settings")
    name = st.selectbox("Provider", ["Gemini", "OpenAI"])
    env = "GEMINI_API_KEY" if name == "Gemini" else "OPENAI_API_KEY"
    key = st.text_input("API key", value=os.getenv(env, ""), type="password")
    model = st.text_input("Answer model", value="gemini-2.5-flash" if name == "Gemini" else "gpt-4.1-mini")
    embedding = st.text_input("Embedding model", value="gemini-embedding-001" if name == "Gemini" else "text-embedding-3-small")
    k = st.slider("Retrieved excerpts", 1, 10, 5)
    st.caption("Document text is sent to the selected provider for embeddings and answers. Models are editable; access depends on your account.")
    if st.button("Clear documents and chat"):
        st.session_state.pop("bundle", None)
        st.session_state.pop("messages", None)
        st.rerun()
files = st.file_uploader("PDF, CSV, Excel or Word files", type=["pdf", "csv", "xlsx", "docx"], accept_multiple_files=True)
blobs = [(f.name, f.getvalue()) for f in files]
fingerprint = hashlib.sha256(repr((name, model, embedding, hashlib.sha256(key.encode()).hexdigest(),
    [(n, hashlib.sha256(b).hexdigest()) for n, b in blobs])).encode()).hexdigest()
bundle = st.session_state.get("bundle")
if bundle and bundle["fingerprint"] != fingerprint:
    st.info("Files or settings changed. Build the index again to ask questions.")
if st.button("Build document index", type="primary", disabled=not files):
    if not key.strip():
        st.error("Enter an API key first.")
    elif len(files) > 10 or any(len(data) > 20*1024*1024 for _, data in blobs):
        st.error("Upload up to 10 files, each at most 20 MB.")
    else:
        st.session_state.pop("bundle", None)
        st.session_state["messages"] = []
        try:
            with st.spinner("Manager agent is reading files through MCP and creating embeddings…"):
                chunks, trace, errors = asyncio.run(ManagerAgent().ingest(blobs))
                for error in errors:
                    st.warning(error)
                provider = Provider(name, key, model, embedding)
                index = RAGIndex(chunks, provider)
                st.session_state["bundle"] = {"fingerprint": fingerprint, "index": index, "trace": trace}
            st.success(f"Indexed {len(chunks)} excerpts from {len(trace)} documents.")
        except Exception as exc:
            st.error(f"Indexing failed ({type(exc).__name__}). Check file formats, model access, API quota and network connection.")
bundle = st.session_state.get("bundle")
ready = bundle is not None and bundle["fingerprint"] == fingerprint
if ready:
    with st.expander("Manager agent routing log"):
        st.dataframe(bundle["trace"], use_container_width=True)
for message in st.session_state.get("messages", []):
    with st.chat_message(message["role"]):
        st.markdown(message["text"])
        if message.get("hits"):
            with st.expander("Retrieved evidence"):
                for hit in message["hits"]:
                    st.markdown(f"**[{hit['citation']}] {hit['source']} · {hit['location']}**")
                    st.text(hit["text"])
question = st.chat_input("Ask about your documents", disabled=not ready)
if question:
    st.session_state.setdefault("messages", []).append({"role": "user", "text": question})
    try:
        with st.spinner("Retrieving evidence and generating an answer…"):
            answer, hits = bundle["index"].ask(question, Provider(name, key, model, embedding), k)
        st.session_state["messages"].append({"role": "assistant", "text": answer, "hits": hits})
        st.rerun()
    except Exception as exc:
        st.error(f"Answer failed ({type(exc).__name__}). Check API quota, model access and connection; retry your question.")

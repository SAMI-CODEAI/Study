import os
import streamlit as st
from PyPDF2 import PdfReader

# LangChain imports (new style)
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate

# --- Streamlit App Config ---
st.set_page_config(page_title="📚 Study Gen RAG Assistant", layout="wide")

# --- API Key ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    st.error("❌ Please set your OPENAI_API_KEY environment variable before running the app.")
    st.stop()

# --- Initialize LLM ---
llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, model_name="gpt-4o-mini")

# --- Session State ---
if "vectorstore" not in st.session_state:
    st.session_state.vectorstore = None
if "sources" not in st.session_state:
    st.session_state.sources = []

# --- Sidebar ---
st.sidebar.title("📂 Sources")
uploaded_files = st.sidebar.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    for file in uploaded_files:
        pdf = PdfReader(file)
        text = ""
        for page in pdf.pages:
            text += page.extract_text()

        # Create embeddings
        embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
        vectorstore = FAISS.from_texts([text], embeddings)

        # Save in session
        st.session_state.vectorstore = vectorstore
        st.session_state.sources.append(file.name)

    st.sidebar.success(f"✅ Uploaded: {', '.join([f.name for f in uploaded_files])}")
    st.rerun()  # 🔄 Fixed rerun call

# --- Main Page ---
st.title("📖 Study Gen – RAG + Agentic Assistant")

if st.session_state.vectorstore is None:
    st.info("👆 Upload PDFs in the sidebar to start.")
else:
    tab1, tab2, tab3, tab4 = st.tabs(["Ask Questions", "Generate Notes", "Flashcards", "Quiz"])

    # --- Tab 1: Ask Questions ---
    with tab1:
        st.subheader("❓ Ask a Question")
        query = st.text_input("Enter your question")
        if query:
            retriever = st.session_state.vectorstore.as_retriever()
            qa = RetrievalQA.from_chain_type(llm=llm, retriever=retriever)
            answer = qa.run(query)
            st.write("### Answer:")
            st.write(answer)

    # --- Tab 2: Notes ---
    with tab2:
        st.subheader("📝 Generate Notes")
        topic = st.text_input("Enter topic for notes")
        if st.button("Generate Notes"):
            retriever = st.session_state.vectorstore.as_retriever()
            qa = RetrievalQA.from_chain_type(llm=llm, retriever=retriever)
            notes = qa.run(f"Generate structured, concise study notes on {topic}")
            st.write(notes)

    # --- Tab 3: Flashcards ---
    with tab3:
        st.subheader("🎴 Flashcards")
        if st.button("Generate Flashcards"):
            retriever = st.session_state.vectorstore.as_retriever()
            qa = RetrievalQA.from_chain_type(llm=llm, retriever=retriever)
            flashcards = qa.run("Generate 5 Q&A style flashcards from the study material.")
            st.write(flashcards)

    # --- Tab 4: Quiz ---
    with tab4:
        st.subheader("🧠 Quiz Generator")
        if st.button("Generate Quiz"):
            retriever = st.session_state.vectorstore.as_retriever()
            qa = RetrievalQA.from_chain_type(llm=llm, retriever=retriever)
            quiz = qa.run("Generate a short quiz with 5 multiple-choice questions and answers.")
            st.write(quiz)

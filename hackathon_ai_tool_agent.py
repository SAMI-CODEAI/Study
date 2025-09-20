import os
import streamlit as st
from PyPDF2 import PdfReader
import json
from datetime import datetime
import docx
from io import BytesIO

# LangChain imports
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain.agents import initialize_agent, Tool, AgentType
from langchain.memory import ConversationBufferMemory
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

# --- Streamlit Config ---
st.set_page_config(
    page_title="📚 AI Study Assistant", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS ---
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .nav-button {
        background: linear-gradient(45deg, #667eea, #764ba2);
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        margin: 0.2rem;
        cursor: pointer;
    }
    .nav-button:hover {
        opacity: 0.8;
    }
    .active-tab {
        background: #28a745 !important;
    }
    .tool-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #667eea;
        margin: 0.5rem 0;
    }
    .response-container {
        background: #ffffff;
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .document-item {
        background: #f8f9fa;
        padding: 0.8rem;
        margin: 0.3rem 0;
        border-radius: 5px;
        border-left: 3px solid #667eea;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .flashcard {
        background: #fff;
        border: 2px solid #667eea;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .quiz-question {
        background: #f8f9fa;
        border-left: 4px solid #28a745;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# --- API Key Setup ---
@st.cache_data
def check_api_key():
    return os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", "")

OPENAI_API_KEY = check_api_key()
if not OPENAI_API_KEY:
    st.error("❌ Please set your OPENAI_API_KEY environment variable or add it to Streamlit secrets.")
    st.stop()

# --- Initialize LLM ---
@st.cache_resource
def get_llm():
    return ChatOpenAI(
        openai_api_key=OPENAI_API_KEY, 
        model_name="gpt-4",
        temperature=0.3
    )

llm = get_llm()

# --- Session State Initialization ---
if "vectorstore" not in st.session_state:
    st.session_state.vectorstore = None
if "documents" not in st.session_state:
    st.session_state.documents = {}  # {filename: {text, upload_time, size}}
if "current_tab" not in st.session_state:
    st.session_state.current_tab = "chat"
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "memory" not in st.session_state:
    st.session_state.memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True
    )
if "current_flashcards" not in st.session_state:
    st.session_state.current_flashcards = []
if "current_quiz" not in st.session_state:
    st.session_state.current_quiz = []
if "current_notes" not in st.session_state:
    st.session_state.current_notes = ""

# --- Helper Functions ---
def process_pdf(uploaded_file):
    """Extract text from PDF with better error handling"""
    try:
        pdf = PdfReader(uploaded_file)
        text = ""
        for page_num, page in enumerate(pdf.pages):
            page_text = page.extract_text()
            if page_text:
                text += f"\n--- Page {page_num + 1} ---\n{page_text}"
        return text
    except Exception as e:
        st.error(f"Error processing {uploaded_file.name}: {str(e)}")
        return ""

def process_txt(uploaded_file):
    """Process text files"""
    try:
        content = uploaded_file.read().decode('utf-8')
        return content
    except Exception as e:
        st.error(f"Error processing {uploaded_file.name}: {str(e)}")
        return ""

def process_docx(uploaded_file):
    """Process Word documents"""
    try:
        doc = docx.Document(uploaded_file)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        st.error(f"Error processing {uploaded_file.name}: {str(e)}")
        return ""

def create_vectorstore(all_documents):
    """Create FAISS vectorstore from multiple documents"""
    try:
        all_text = ""
        for filename, doc_data in all_documents.items():
            all_text += f"\n\n=== {filename} ===\n{doc_data['text']}"
        
        if not all_text.strip():
            return None
            
        # Split text into chunks for better retrieval
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " "]
        )
        
        chunks = text_splitter.split_text(all_text)
        embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
        
        return FAISS.from_texts(chunks, embeddings)
    except Exception as e:
        st.error(f"Error creating vectorstore: {str(e)}")
        return None

def parse_flashcards(text):
    """Parse flashcard text into structured format"""
    cards = []
    lines = text.split('\n')
    current_card = {}
    
    for line in lines:
        line = line.strip()
        if line.startswith('**Card') and ':' in line:
            if current_card:
                cards.append(current_card)
            current_card = {'question': '', 'answer': ''}
        elif line.startswith('Q:'):
            current_card['question'] = line[2:].strip()
        elif line.startswith('A:'):
            current_card['answer'] = line[2:].strip()
    
    if current_card:
        cards.append(current_card)
    
    return cards

def parse_quiz(text):
    """Parse quiz text into structured format"""
    questions = []
    lines = text.split('\n')
    current_question = {}
    
    for line in lines:
        line = line.strip()
        if line.startswith('**Question') and ':' in line:
            if current_question:
                questions.append(current_question)
            current_question = {'question': line.split(':', 1)[1].strip(), 'options': [], 'answer': ''}
        elif line.startswith(('A)', 'B)', 'C)', 'D)')):
            current_question['options'].append(line)
        elif line.startswith('**Correct Answer:**'):
            current_question['answer'] = line.replace('**Correct Answer:**', '').strip()
    
    if current_question:
        questions.append(current_question)
    
    return questions

# --- Sidebar: Document Management ---
with st.sidebar:
    st.title("📂 Document Library")
    
    # File Upload Section
    st.subheader("📤 Upload Documents")
    uploaded_files = st.file_uploader(
        "Select files to upload", 
        type=["pdf", "txt", "docx"], 
        accept_multiple_files=True,
        help="Supported formats: PDF, TXT, DOCX"
    )
    
    if uploaded_files:
        for file in uploaded_files:
            if file.name not in st.session_state.documents:
                with st.spinner(f"Processing {file.name}..."):
                    # Process based on file type
                    if file.name.endswith('.pdf'):
                        text = process_pdf(file)
                    elif file.name.endswith('.txt'):
                        text = process_txt(file)
                    elif file.name.endswith('.docx'):
                        text = process_docx(file)
                    else:
                        continue
                    
                    if text:
                        st.session_state.documents[file.name] = {
                            'text': text,
                            'upload_time': datetime.now(),
                            'size': len(text),
                            'type': file.name.split('.')[-1].upper()
                        }
        
        # Recreate vectorstore with all documents
        if st.session_state.documents:
            with st.spinner("Updating knowledge base..."):
                st.session_state.vectorstore = create_vectorstore(st.session_state.documents)
            st.success(f"✅ Processed {len(uploaded_files)} new document(s)")
            st.rerun()
    
    # Document Library Display
    if st.session_state.documents:
        st.subheader("📚 Current Library")
        total_docs = len(st.session_state.documents)
        total_size = sum([doc['size'] for doc in st.session_state.documents.values()])
        
        st.metric("Documents", total_docs)
        st.metric("Total Characters", f"{total_size:,}")
        
        # Document list with individual delete buttons
        for filename, doc_data in st.session_state.documents.items():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"""
                <div class="document-item">
                    <div>
                        <strong>{filename}</strong><br>
                        <small>{doc_data['type']} • {doc_data['size']:,} chars</small>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                if st.button("🗑️", key=f"del_{filename}", help=f"Delete {filename}"):
                    del st.session_state.documents[filename]
                    if st.session_state.documents:
                        st.session_state.vectorstore = create_vectorstore(st.session_state.documents)
                    else:
                        st.session_state.vectorstore = None
                    st.rerun()
        
        # Clear all button
        if st.button("🗑️ Clear All Documents", type="secondary"):
            st.session_state.documents = {}
            st.session_state.vectorstore = None
            st.session_state.conversation_history = []
            st.session_state.current_flashcards = []
            st.session_state.current_quiz = []
            st.session_state.current_notes = ""
            st.rerun()

# --- Main Navigation ---
st.markdown('<div class="main-header"><h1>🤖 AI Study Assistant</h1><p>Your intelligent companion for learning and revision</p></div>', unsafe_allow_html=True)

# Navigation Tabs
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    if st.button("💬 Chat Assistant", key="nav_chat", type="primary" if st.session_state.current_tab == "chat" else "secondary"):
        st.session_state.current_tab = "chat"
        st.rerun()
with col2:
    if st.button("📝 Study Notes", key="nav_notes", type="primary" if st.session_state.current_tab == "notes" else "secondary"):
        st.session_state.current_tab = "notes"
        st.rerun()
with col3:
    if st.button("🎯 Flashcards", key="nav_flashcards", type="primary" if st.session_state.current_tab == "flashcards" else "secondary"):
        st.session_state.current_tab = "flashcards"
        st.rerun()
with col4:
    if st.button("🧠 Quiz Mode", key="nav_quiz", type="primary" if st.session_state.current_tab == "quiz" else "secondary"):
        st.session_state.current_tab = "quiz"
        st.rerun()
with col5:
    if st.button("❓ Q&A Mode", key="nav_qa", type="primary" if st.session_state.current_tab == "qa" else "secondary"):
        st.session_state.current_tab = "qa"
        st.rerun()

st.markdown("---")

# Check if documents are loaded
if not st.session_state.documents:
    st.info("👆 Upload your study materials in the sidebar to get started!")
    
    # Show example of what can be done
    st.subheader("📝 What I can help you with:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="tool-card"><strong>📚 Question Answering</strong><br>Ask specific questions about your materials</div>', unsafe_allow_html=True)
        st.markdown('<div class="tool-card"><strong>📋 Study Notes</strong><br>Generate structured notes for revision</div>', unsafe_allow_html=True)
        st.markdown('<div class="tool-card"><strong>🎯 Flashcards</strong><br>Create cards for active recall practice</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="tool-card"><strong>🧠 Interactive Quizzes</strong><br>Test your knowledge with MCQs</div>', unsafe_allow_html=True)
        st.markdown('<div class="tool-card"><strong>💬 Smart Chat</strong><br>Natural conversation about your materials</div>', unsafe_allow_html=True)
        st.markdown('<div class="tool-card"><strong>📚 Multi-Document Support</strong><br>Upload PDF, TXT, DOCX files</div>', unsafe_allow_html=True)

else:
    # Create retriever and tools
    retriever = st.session_state.vectorstore.as_retriever(search_kwargs={"k": 5})
    
    # --- Enhanced Tool Functions ---
    def answer_question(query):
        """Enhanced Q&A with source context"""
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm, 
            retriever=retriever,
            return_source_documents=True
        )
        result = qa_chain({"query": query})
        return f"**Answer:** {result['result']}\n\n**Sources:** Based on {len(result['source_documents'])} document sections"
    
    def generate_notes(topic):
        """Generate structured study notes"""
        enhanced_query = f"""Generate comprehensive, well-structured study notes on '{topic}'. 
        Format as:
        ## {topic}
        
        ### Key Concepts:
        - [List main concepts with brief explanations]
        
        ### Important Details:
        - [Detailed explanations of complex points]
        - [Include formulas, definitions, examples where relevant]
        
        ### Summary:
        [Concise summary for quick review]
        
        ### Review Questions:
        - [3-4 questions to test understanding]"""
        
        result = RetrievalQA.from_chain_type(llm=llm, retriever=retriever).run(enhanced_query)
        return result
    
    def create_flashcards(topic="the uploaded material"):
        """Generate flashcards in Q&A format"""
        query = f"""Create 10 flashcards from {topic}. Format each as:
        
        **Card X:**
        Q: [Clear, specific question]
        A: [Concise but complete answer]
        
        Focus on key concepts, definitions, formulas, and important facts that students need to memorize."""
        
        result = RetrievalQA.from_chain_type(llm=llm, retriever=retriever).run(query)
        return result
    
    def generate_quiz(topic="the uploaded material"):
        """Generate multiple choice quiz"""
        query = f"""Create an 8-question multiple choice quiz from {topic}.
        
        Format each question as:
        **Question X:** [Question text]
        A) [Option A]
        B) [Option B] 
        C) [Option C]
        D) [Option D]
        
        **Correct Answer:** [Letter] - [Brief explanation why this is correct]
        
        Make questions progressively harder. Include a mix of factual recall and conceptual understanding."""
        
        result = RetrievalQA.from_chain_type(llm=llm, retriever=retriever).run(query)
        return result
    
    # Define tools for the agent
    tools = [
        Tool(
            name="Question Answering",
            func=answer_question,
            description="Answers specific questions from the study material with source references"
        ),
        Tool(
            name="Notes Generator", 
            func=generate_notes,
            description="Creates structured, comprehensive study notes on any topic from the material"
        ),
        Tool(
            name="Flashcard Creator",
            func=create_flashcards,
            description="Generates flashcards for active recall and memorization practice"
        ),
        Tool(
            name="Quiz Generator",
            func=generate_quiz,
            description="Creates multiple choice quizzes to test knowledge and understanding"
        )
    ]
    
    # Initialize agent with memory
    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
        memory=st.session_state.memory,
        verbose=False,
        handle_parsing_errors=True
    )
    
    # --- Tab Content ---
    
    if st.session_state.current_tab == "chat":
        st.subheader("💬 Chat with Your Study Assistant")
        
        # Example queries
        with st.expander("💡 Example Questions"):
            example_col1, example_col2 = st.columns(2)
            with example_col1:
                st.write("• 'Create study notes for Chapter 5'")
                st.write("• 'Make flashcards for biology terms'")
                st.write("• 'What is photosynthesis?'")
            with example_col2:
                st.write("• 'Generate a quiz on quantum mechanics'")
                st.write("• 'Explain the main concepts simply'")
                st.write("• 'Summarize the key takeaways'")
        
        # Chat interface
        user_query = st.text_area(
            "Ask me anything about your study materials:",
            placeholder="e.g., 'Create a quiz on photosynthesis' or 'Explain the main concepts in Chapter 3'",
            height=100
        )
        
        col1, col2 = st.columns([1, 4])
        with col1:
            ask_button = st.button("🚀 Ask", type="primary")
        
        if ask_button and user_query.strip():
            with st.spinner("🤔 Your AI assistant is thinking..."):
                try:
                    response = agent.run(user_query)
                    
                    # Add to conversation history
                    st.session_state.conversation_history.append({
                        "query": user_query,
                        "response": response,
                        "timestamp": datetime.now().strftime("%H:%M")
                    })
                    
                except Exception as e:
                    response = f"I encountered an error: {str(e)}. Please try rephrasing your question."
            
            # Display current response
            st.markdown('<div class="response-container">', unsafe_allow_html=True)
            st.write("### ✨ Response:")
            st.write(response)
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Display conversation history
        if st.session_state.conversation_history:
            st.subheader("📜 Recent Conversations")
            
            for i, conv in enumerate(reversed(st.session_state.conversation_history[-3:])):
                with st.expander(f"💭 {conv['timestamp']} - {conv['query'][:50]}..."):
                    st.write(f"**You asked:** {conv['query']}")
                    st.write(f"**Assistant:** {conv['response']}")
    
    elif st.session_state.current_tab == "notes":
        st.subheader("📝 Study Notes Generator")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            notes_topic = st.text_input("Enter topic for study notes:", placeholder="e.g., 'Photosynthesis', 'Chapter 3', 'Quantum Mechanics'")
        with col2:
            generate_notes_btn = st.button("📝 Generate Notes", type="primary")
        
        if generate_notes_btn and notes_topic:
            with st.spinner("📚 Creating your study notes..."):
                try:
                    notes = generate_notes(notes_topic)
                    st.session_state.current_notes = notes
                except Exception as e:
                    st.error(f"Error generating notes: {str(e)}")
        
        if st.session_state.current_notes:
            st.markdown('<div class="response-container">', unsafe_allow_html=True)
            st.markdown(st.session_state.current_notes)
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Download button
            st.download_button(
                label="📥 Download Notes as Text",
                data=st.session_state.current_notes,
                file_name=f"study_notes_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain"
            )
    
    elif st.session_state.current_tab == "flashcards":
        st.subheader("🎯 Interactive Flashcards")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            flashcard_topic = st.text_input("Create flashcards for:", placeholder="e.g., 'Biology terms', 'Math formulas', 'History dates'")
        with col2:
            create_flashcards_btn = st.button("🎯 Create Flashcards", type="primary")
        
        if create_flashcards_btn and flashcard_topic:
            with st.spinner("🎯 Creating your flashcards..."):
                try:
                    flashcard_text = create_flashcards(flashcard_topic)
                    st.session_state.current_flashcards = parse_flashcards(flashcard_text)
                except Exception as e:
                    st.error(f"Error creating flashcards: {str(e)}")
        
        if st.session_state.current_flashcards:
            st.write(f"**📊 {len(st.session_state.current_flashcards)} Flashcards Created**")
            
            # Flashcard navigator
            if 'current_card_index' not in st.session_state:
                st.session_state.current_card_index = 0
            
            col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
            
            with col1:
                if st.button("⬅️ Previous") and st.session_state.current_card_index > 0:
                    st.session_state.current_card_index -= 1
                    st.rerun()
            
            with col2:
                st.write(f"Card {st.session_state.current_card_index + 1} of {len(st.session_state.current_flashcards)}")
            
            with col4:
                if st.button("Next ➡️") and st.session_state.current_card_index < len(st.session_state.current_flashcards) - 1:
                    st.session_state.current_card_index += 1
                    st.rerun()
            
            with col5:
                if st.button("🔄 Shuffle"):
                    import random
                    random.shuffle(st.session_state.current_flashcards)
                    st.session_state.current_card_index = 0
                    st.rerun()
            
            # Display current flashcard
            current_card = st.session_state.current_flashcards[st.session_state.current_card_index]
            
            # Show/hide answer functionality
            if 'show_answer' not in st.session_state:
                st.session_state.show_answer = False
            
            st.markdown('<div class="flashcard">', unsafe_allow_html=True)
            st.write("### 🤔 Question:")
            st.write(current_card['question'])
            
            if st.button("👁️ Show Answer" if not st.session_state.show_answer else "🙈 Hide Answer"):
                st.session_state.show_answer = not st.session_state.show_answer
                st.rerun()
            
            if st.session_state.show_answer:
                st.write("### ✅ Answer:")
                st.write(current_card['answer'])
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    elif st.session_state.current_tab == "quiz":
        st.subheader("🧠 Interactive Quiz Mode")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            quiz_topic = st.text_input("Create quiz on:", placeholder="e.g., 'Cell biology', 'World War II', 'Calculus'")
        with col2:
            create_quiz_btn = st.button("🧠 Create Quiz", type="primary")
        
        if create_quiz_btn and quiz_topic:
            with st.spinner("🧠 Creating your quiz..."):
                try:
                    quiz_text = generate_quiz(quiz_topic)
                    st.session_state.current_quiz = parse_quiz(quiz_text)
                    if 'user_answers' not in st.session_state:
                        st.session_state.user_answers = {}
                    if 'show_results' not in st.session_state:
                        st.session_state.show_results = False
                except Exception as e:
                    st.error(f"Error creating quiz: {str(e)}")
        
        if st.session_state.current_quiz:
            st.write(f"**📊 Quiz: {len(st.session_state.current_quiz)} Questions**")
            
            # Initialize user answers if needed
            if 'user_answers' not in st.session_state:
                st.session_state.user_answers = {}
            
            # Display quiz questions
            for i, question in enumerate(st.session_state.current_quiz):
                st.markdown(f'<div class="quiz-question">', unsafe_allow_html=True)
                st.write(f"**Question {i+1}:** {question['question']}")
                
                # Radio buttons for options
                if question['options']:
                    selected = st.radio(
                        f"Choose your answer for Question {i+1}:",
                        question['options'],
                        key=f"q_{i}",
                        index=None
                    )
                    if selected:
                        st.session_state.user_answers[i] = selected[0]  # Store just the letter (A, B, C, D)
                
                st.markdown('</div>', unsafe_allow_html=True)
            
            # Submit quiz button
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("📊 Submit Quiz", type="primary"):
                    st.session_state.show_results = True
                    st.rerun()
            
            with col2:
                if st.button("🔄 Reset Quiz"):
                    st.session_state.user_answers = {}
                    st.session_state.show_results = False
                    st.rerun()
            
            # Show results
            if st.session_state.show_results and st.session_state.user_answers:
                st.subheader("📊 Quiz Results")
                
                correct = 0
                total = len(st.session_state.current_quiz)
                
                for i, question in enumerate(st.session_state.current_quiz):
                    user_answer = st.session_state.user_answers.get(i, "Not answered")
                    correct_answer = question['answer'].split('-')[0].strip() if question['answer'] else "N/A"
                    
                    if user_answer == correct_answer:
                        correct += 1
                        st.success(f"✅ Question {i+1}: Correct! ({user_answer})")
                    else:
                        st.error(f"❌ Question {i+1}: Your answer: {user_answer}, Correct: {correct_answer}")
                        if question['answer']:
                            st.info(f"💡 Explanation: {question['answer']}")
                
                score_percentage = (correct / total) * 100
                st.metric("Final Score", f"{correct}/{total} ({score_percentage:.1f}%)")
                
                if score_percentage >= 80:
                    st.balloons()
                    st.success("🎉 Excellent work!")
                elif score_percentage >= 60:
                    st.success("👍 Good job! Keep studying!")
                else:
                    st.warning("📚 Keep studying! You'll get there!")
    
    elif st.session_state.current_tab == "qa":
        st.subheader("❓ Question & Answer Mode")
        
        st.info("💡 Ask specific questions about your uploaded documents for detailed answers with source references.")
        
        qa_question = st.text_area(
            "What would you like to know?",
            placeholder="e.g., 'What are the main causes of climate change?', 'Explain the process of photosynthesis', 'What is mentioned about quantum entanglement?'",
            height=100)
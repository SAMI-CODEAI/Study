# hackathon_ai_tool_full_ui.py
import streamlit as st
from PyPDF2 import PdfReader
import openai
import os
import re
import json


st.set_page_config(page_title="NotebookLM Clone", layout="wide")


# --- API Key ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    st.error("❌ Please set your OPENAI_API_KEY environment variable before running the app.")
    st.stop()
client = openai.OpenAI(api_key=OPENAI_API_KEY)


# --- Helper: AI Content Generation ---
def generate_content(prompt):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an AI that generates educational content."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content or ""


# --- Session State ---
if "page" not in st.session_state:
    st.session_state.page = "courses"
if "courses" not in st.session_state:
    st.session_state.courses = {}
if "selected_course" not in st.session_state:
    st.session_state.selected_course = None
if "selected_module" not in st.session_state:
    st.session_state.selected_module = None
if "active_view" not in st.session_state:
    st.session_state.active_view = "chat"
if "quiz_answers" not in st.session_state:
    st.session_state.quiz_answers = {}
if "quiz_submitted" not in st.session_state:
    st.session_state.quiz_submitted = False
if "flash_index" not in st.session_state:
    st.session_state.flash_index = 0
if "flash_flipped" not in st.session_state:
    st.session_state.flash_flipped = False


# ================= PAGE 1: COURSE LIST =================
if st.session_state.page == "courses":
    st.title("🎓 Courses")


    if st.session_state.courses:
        st.subheader("Your Courses")
        for course in st.session_state.courses.keys():
            if st.button(course, use_container_width=True):
                st.session_state.selected_course = course
                st.session_state.page = "modules"
                st.rerun()


    st.write("---")
    new_course = st.text_input("➕ Create a new course")
    if st.button("Add Course"):
        if new_course.strip():
            if new_course not in st.session_state.courses:
                st.session_state.courses[new_course] = {}
                st.success(f"✅ Course '{new_course}' created!")
            else:
                st.warning("Course already exists.")


# ================= PAGE 2: MODULE LIST =================
elif st.session_state.page == "modules":
    st.title(f"📘 {st.session_state.selected_course}")
    st.subheader("Modules")


    modules = st.session_state.courses[st.session_state.selected_course]
    if modules:
        for module in modules.keys():
            if st.button(module, use_container_width=True):
                st.session_state.selected_module = module
                st.session_state.page = "content"
                st.session_state.active_view = "chat"
                st.rerun()


    st.write("---")
    new_module = st.text_input("➕ Create a new module")
    if st.button("Add Module"):
        if new_module.strip():
            if new_module not in st.session_state.courses[st.session_state.selected_course]:
                st.session_state.courses[st.session_state.selected_course][new_module] = {
                    "text": "", "notes": "", "flashcards": [], "quiz": [], "mindmap": ""
                }
                st.success(f"✅ Module '{new_module}' created!")
            else:
                st.warning("Module already exists.")


    if st.button("⬅ Back to Courses"):
        st.session_state.page = "courses"
        st.rerun()


# ================= PAGE 3: MODULE CONTENT =================
elif st.session_state.page == "content":
    course = st.session_state.selected_course
    module = st.session_state.selected_module
    module_data = st.session_state.courses[course][module]


    # Layout
    left, center, right = st.columns([2, 4, 2])


    # --- LEFT: Sources ---
    with left:
        st.header("📂 Sources")
        uploaded_file = st.file_uploader("Upload PDF", type="pdf")
        pasted_text = st.text_area("Or paste text here", value=module_data["text"])


        if uploaded_file:
            pdf_reader = PdfReader(uploaded_file)
            module_data["text"] = "".join(page.extract_text() or "" for page in pdf_reader.pages)
        elif pasted_text.strip():
            module_data["text"] = pasted_text.strip()


    # --- CENTER: Dynamic View ---
    with center:
        st.header(f"💬 {course} → {module}")


        if st.session_state.active_view == "chat":
            q_text = st.text_input("Ask a question")
            if st.button("Ask"):
                if q_text.strip():
                    q_prompt = f"Answer this based on:\n\n{module_data['text']}\n\nQ: {q_text}"
                    ans = generate_content(q_prompt)
                    st.markdown(f"**Answer:** {ans}")
                else:
                    st.warning("Enter a question first.")


        elif st.session_state.active_view == "notes":
            st.subheader("📝 Notes")
            st.markdown(module_data["notes"])


        elif st.session_state.active_view == "mindmap":
            st.subheader("🧠 Mindmap")
            if module_data["mindmap"]:
                try:
                    # Clean the mindmap data to ensure it's valid DOT syntax
                    mindmap_content = module_data["mindmap"]
                    
                    # If the AI response contains extra text, extract just the DOT code
                    if "digraph" in mindmap_content or "graph" in mindmap_content:
                        dot_match = re.search(r'(digraph.*?}|graph.*?})', mindmap_content, re.DOTALL | re.IGNORECASE)
                        if dot_match:
                            mindmap_content = dot_match.group(1)
                    
                    # Display the mindmap
                    st.graphviz_chart(mindmap_content)
                except Exception as e:
                    st.error(f"Error displaying mindmap: {e}")
                    st.text("Raw mindmap content:")
                    st.code(module_data["mindmap"])
            else:
                st.info("No mindmap available. Click '🧠 Generate Mindmap' to create one.")


        elif st.session_state.active_view == "quiz":
            st.subheader("🎯 Quiz")


            if not module_data["quiz"]:
                st.info("No quiz available. Click '🎯 Generate Quiz' in the Studio to create one.")
            else:
                for i, q in enumerate(module_data["quiz"]):
                    st.write(f"**Q{i+1}: {q['question']}**")
                    if i not in st.session_state.quiz_answers:
                        st.session_state.quiz_answers[i] = []


                    correct_ans = q["answer"]
                    if not isinstance(correct_ans, list):
                        correct_ans = [correct_ans]


                    if len(correct_ans) == 1:
                        selected = st.radio("Select an option:", q["options"], index=0, key=f"quiz_{i}")
                        st.session_state.quiz_answers[i] = [selected]
                    else:
                        selected_opts = []
                        for opt in q["options"]:
                            if st.checkbox(opt, key=f"quiz_{i}_{opt}"):
                                selected_opts.append(opt)
                        st.session_state.quiz_answers[i] = selected_opts


                if st.button("Submit Quiz"):
                    st.session_state.quiz_submitted = True


                if st.session_state.quiz_submitted:
                    score = 0
                    st.write("---")
                    for i, q in enumerate(module_data["quiz"]):
                        user_ans = st.session_state.quiz_answers.get(i, [])
                        correct_ans = q["answer"]
                        if not isinstance(correct_ans, list):
                            correct_ans = [correct_ans]


                        if set(user_ans) == set(correct_ans):
                            score += 1
                            st.success(f"Q{i+1}: ✅ Correct")
                        else:
                            st.error(f"Q{i+1}: ❌ Wrong (Your: {user_ans}, Correct: {correct_ans})")


                    st.info(f"Final Score: {score}/{len(module_data['quiz'])}")


        elif st.session_state.active_view == "flashcards":
            st.subheader("📖 Flashcards")


            if module_data["flashcards"]:
                i = st.session_state.flash_index
                q, a = module_data["flashcards"][i]


                st.write(f"Card {i+1}/{len(module_data['flashcards'])}")


                if not st.session_state.flash_flipped:
                    st.info(f"Q: {q.strip()}")
                else:
                    st.success(f"A: {a.strip()}")


                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("⬅ Prev") and i > 0:
                        st.session_state.flash_index -= 1
                        st.session_state.flash_flipped = False
                        st.rerun()
                with col2:
                    if st.button("🔄 Flip"):
                        st.session_state.flash_flipped = not st.session_state.flash_flipped
                        st.rerun()
                with col3:
                    if st.button("➡ Next") and i < len(module_data["flashcards"]) - 1:
                        st.session_state.flash_index += 1
                        st.session_state.flash_flipped = False
                        st.rerun()


    # --- RIGHT: Studio ---
    with right:
        st.header("🎬 Studio")


        if st.button("💬 Ask"):
            st.session_state.active_view = "chat"
            st.rerun()


        if st.button("📝 Generate Notes"):
            prompt = f"Summarize into study notes:\n\n{module_data['text']}"
            module_data["notes"] = generate_content(prompt)
            st.session_state.active_view = "notes"
            st.rerun()


        if st.button("🧠 Generate Mindmap"):
            prompt = f"Create a mindmap in Graphviz DOT format. Use 'digraph' syntax. Only return the DOT code. Content: {module_data['text'][:500]}"
            mindmap_response = generate_content(prompt)
            
            # Clean and validate the response
            dot_match = re.search(r'(digraph.*?})', mindmap_response, re.DOTALL | re.IGNORECASE)
            if dot_match:
                module_data["mindmap"] = dot_match.group(1)
            else:
                # Fallback simple mindmap
                module_data["mindmap"] = """digraph G {
    rankdir=TB;
    node [shape=box, style=rounded];
    "Main Topic" -> "Concept 1";
    "Main Topic" -> "Concept 2";
    "Main Topic" -> "Concept 3";
    "Concept 1" -> "Detail 1";
    "Concept 2" -> "Detail 2";
    "Concept 3" -> "Detail 3";
}"""
            
            st.session_state.active_view = "mindmap"
            st.rerun()


        if st.button("🎯 Generate Quiz"):
            prompt = f"Generate 5 MCQs in JSON list with fields: question, options, answer. Use this text:\n\n{module_data['text']}"
            raw = generate_content(prompt)
            try:
                raw_json = re.search(r"\[.*\]", raw, re.S)
                module_data["quiz"] = json.loads(raw_json.group()) if raw_json else []
            except:
                module_data["quiz"] = []


            if not module_data["quiz"]:
                st.warning("Failed to generate valid quiz. Try again or check AI output.")


            st.session_state.active_view = "quiz"
            st.session_state.quiz_submitted = False
            st.session_state.quiz_answers = {}
            st.rerun()


        if st.button("📖 Generate Flashcards"):
            prompt = f"Generate 5 flashcards as Q&A pairs:\n\n{module_data['text']}"
            output = generate_content(prompt)
            module_data["flashcards"] = re.findall(r"Q:(.*?)A:(.*?)(?=Q:|$)", output, re.S)
            st.session_state.active_view = "flashcards"
            st.session_state.flash_index = 0
            st.session_state.flash_flipped = False
            st.rerun()


    if st.button("⬅ Back to Modules"):
        st.session_state.page = "modules"
        st.rerun()
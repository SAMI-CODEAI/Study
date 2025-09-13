# hackathon_ai_tool_full.py
import streamlit as st
from PyPDF2 import PdfReader
import openai
import os
import streamlit.components.v1 as components
import re

st.set_page_config(page_title="AI Course Builder", layout="wide")
st.title("🎓 AI Course & Module Builder")
st.write("Create courses with modules, generate learning content, ask questions, view Mindmaps, and take interactive quizzes!")

# --- API Key ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    st.error("❌ Please set your OPENAI_API_KEY environment variable before running the app.")
    st.stop()

client = openai.OpenAI(api_key=OPENAI_API_KEY)

# --- Session State ---
if "courses" not in st.session_state:
    st.session_state.courses = {}  # course_name -> module_name -> {text, history}

# --- Course & Module Management ---
st.sidebar.header("Course & Module Management")
course_name = st.sidebar.text_input("Course Name")
module_name = st.sidebar.text_input("Module Name")

if st.sidebar.button("Add Course & Module"):
    if course_name and module_name:
        if course_name not in st.session_state.courses:
            st.session_state.courses[course_name] = {}
        st.session_state.courses[course_name][module_name] = {"text": "", "history": []}
        st.success(f"Added course '{course_name}' with module '{module_name}'")
    else:
        st.warning("Please provide both course and module names.")

# --- Select Course & Module ---
selected_course = st.sidebar.selectbox("Select Course", list(st.session_state.courses.keys()) if st.session_state.courses else [])
selected_module = st.sidebar.selectbox(
    "Select Module",
    list(st.session_state.courses[selected_course].keys()) if selected_course else []
)

if selected_course and selected_module:
    module_data = st.session_state.courses[selected_course][selected_module]

    # --- Module Content Input ---
    uploaded_file = st.file_uploader("Upload a PDF for this module", type="pdf", key="file")
    text_input = st.text_area("Or paste text here", value=module_data.get("text", ""), key="text_input")

    if uploaded_file:
        pdf_reader = PdfReader(uploaded_file)
        text_input = "".join(page.extract_text() for page in pdf_reader.pages)
    
    module_data["text"] = text_input

    # --- Content Options ---
    mode = st.selectbox("Choose Output Type", ["Notes", "Flashcards", "Quiz", "Mindmap"])
    user_question = st.text_input("Ask a question about this module:")

    # --- AI Content Generation ---
    def generate_content(prompt):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an AI that generates educational content."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content or ""

    # --- Generate Main Content ---
    if st.button("Generate Content"):
        if not text_input.strip():
            st.warning("Module content is empty!")
        else:
            output = ""
            if mode == "Notes":
                prompt = f"Summarize the following text into detailed study notes:\n\n{text_input}"
                output = generate_content(prompt)
                st.subheader("📌 Notes")
                st.write(output)

            elif mode == "Flashcards":
                prompt = f"Generate flashcards (Q&A format) from the following text:\n\n{text_input}"
                output = generate_content(prompt)
                st.subheader("📌 Flashcards")
                st.write(output)

            elif mode == "Quiz":
                prompt = f"""
                Generate 5 multiple-choice questions with 4 options each (A-D) based on the text below.
                Indicate the correct answer with "Answer: X".
                Format:
                Q1: Question?
                A. Option1
                B. Option2
                C. Option3
                D. Option4
                Answer: B

                Text: {text_input}
                """
                quiz_text = generate_content(prompt)
                quiz_text = str(quiz_text)

                # --- Parse Quiz ---
                questions_raw = re.split(r"Q\d+:", quiz_text)
                questions = []
                correct_answers = []

                for q in questions_raw[1:]:
                    lines = q.strip().split("\n")
                    if len(lines) < 6:
                        continue
                    question_text = lines[0].strip()
                    options = [line.strip() for line in lines[1:5]]
                    answer_line = [line for line in lines if line.startswith("Answer:")][0]
                    correct_answer = answer_line.replace("Answer:", "").strip()
                    questions.append({"question": question_text, "options": options, "user_choice": None})
                    correct_answers.append(correct_answer)

                st.session_state.quiz_questions = questions
                st.session_state.quiz_answers = correct_answers

            elif mode == "Mindmap":
                prompt = f"""
                Generate a mindmap/flowchart in Mermaid v10 syntax for the following text.
                - Use 'flowchart TD'
                - Ensure unique node IDs
                - Keep labels concise
                Text: {text_input}
                """
                output = generate_content(prompt)

                # --- Sanitize Mermaid ---
                output = re.sub(r'[\?:"<>]', '', output)
                output = re.sub(r'\s+', ' ', output)
                if not output.startswith("flowchart"):
                    output = f"flowchart TD\n{output}"

                st.subheader("🧠 Mindmap / Flowchart")
                components.html(f"""
                <div class="mermaid">{output}</div>
                <script type="module">
                    import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
                    mermaid.initialize({{ startOnLoad: true, theme: "forest" }});
                </script>
                """, height=600)

            # Save history
            module_data["history"].append({"mode": mode, "output": output if mode!="Quiz" else quiz_text})

            # Download
            if output:
                st.download_button(
                    "Download Result as .txt",
                    data=output,
                    file_name=f"{selected_module}_{mode}.txt"
                )

    # --- Display Quiz with Scoring ---
    if "quiz_questions" in st.session_state and mode == "Quiz":
        st.subheader("📝 Take the Quiz")
        for i, q in enumerate(st.session_state.quiz_questions):
            user_choice = st.radio(
                q["question"],
                options=q["options"],
                index=-1,
                key=f"q{i}"
            )
            if user_choice:
                st.session_state.quiz_questions[i]["user_choice"] = user_choice.split(".")[0]

        if st.button("Submit Quiz"):
            correct = 0
            wrong = 0
            unanswered = 0
            for i, q in enumerate(st.session_state.quiz_questions):
                if q["user_choice"] is None:
                    unanswered += 1
                elif q["user_choice"] == st.session_state.quiz_answers[i]:
                    correct += 1
                else:
                    wrong += 1
            st.success(f"✅ Correct: {correct}")
            st.error(f"❌ Wrong: {wrong}")
            st.warning(f"⚠️ Unanswered: {unanswered}")
            st.info(f"🏆 Score: {correct}/{len(st.session_state.quiz_questions)}")

    # --- Ask Question Section ---
    st.subheader("❓ Ask a Question About the Content")
    user_question = st.text_input("Type your question here:", key="question_input")
    if st.button("Ask Question"):
        if user_question.strip():
            q_prompt = f"Answer the following question based on the text:\n\nText: {text_input}\nQuestion: {user_question}"
            answer = generate_content(q_prompt)
            module_data["history"].append({"mode": "Q&A", "question": user_question, "answer": answer})
            st.markdown(f"**Answer:** {answer}")
        else:
            st.warning("Please type a question before clicking 'Ask Question'.")

    # --- Display Module History ---
    if module_data["history"]:
        st.subheader("📜 Module History")
        for i, h in enumerate(module_data["history"]):
            if h["mode"] == "Q&A":
                st.markdown(f"**Q{i+1}:** {h['question']}")
                st.markdown(f"**A{i+1}:** {h['answer']}")
            else:
                st.markdown(f"**{h['mode']} {i+1}:** {h.get('output', '')[:200]}{'...' if len(h.get('output', ''))>200 else ''}")

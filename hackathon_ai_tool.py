# hackathon_ai_tool_full_ui.py
import streamlit as st
from PyPDF2 import PdfReader
import openai
import os
import streamlit.components.v1 as components
import re
import html

st.set_page_config(page_title="AI Course Builder", layout="wide")

# --- API Key ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    st.error("❌ Please set your OPENAI_API_KEY environment variable before running the app.")
    st.stop()
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# --- Session State ---
if "page" not in st.session_state:
    st.session_state.page = "courses"   # navigation: courses → modules → content
if "courses" not in st.session_state:
    st.session_state.courses = {}       # course_name -> { module_name -> {text, history} }
if "selected_course" not in st.session_state:
    st.session_state.selected_course = None
if "selected_module" not in st.session_state:
    st.session_state.selected_module = None

# --- Helper: AI Content Generation ---
def generate_content(prompt):
    """
    Wrapper for OpenAI chat completion that returns a string.
    Keeps your original client usage (gpt-4o-mini).
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an AI that generates educational content."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=1500,
        temperature=0.2,
    )
    # Defensive access for compatibility
    try:
        return response.choices[0].message.content or ""
    except Exception:
        # Fallback for older/other response shapes
        return getattr(response.choices[0], "text", "") or ""

# ------------------------------
# UI: Courses / Modules / Content
# ------------------------------
# PAGE 1: COURSE LIST
if st.session_state.page == "courses":
    st.markdown(
        """
        <style>
        .big-title {font-size:30px; font-weight:700; margin-bottom:6px;}
        .sub {color: #6b7280; margin-top: -6px;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="big-title">🎓 AI Course Builder</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub">📚 Your Courses</div>', unsafe_allow_html=True)
    st.write("")

    if st.session_state.courses:
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

# PAGE 2: MODULE LIST
elif st.session_state.page == "modules":
    st.title(f"📘 Course: {st.session_state.selected_course}")
    st.subheader("Modules")

    modules = st.session_state.courses[st.session_state.selected_course]
    if modules:
        for module in modules.keys():
            if st.button(module, use_container_width=True):
                st.session_state.selected_module = module
                st.session_state.page = "content"
                st.rerun()

    st.write("---")
    new_module = st.text_input("➕ Create a new module")
    if st.button("Add Module"):
        if new_module.strip():
            if new_module not in st.session_state.courses[st.session_state.selected_course]:
                st.session_state.courses[st.session_state.selected_course][new_module] = {"text": "", "history": []}
                st.success(f"✅ Module '{new_module}' created!")
            else:
                st.warning("Module already exists.")

    if st.button("⬅ Back to Courses"):
        st.session_state.page = "courses"
        st.rerun()

# PAGE 3: MODULE CONTENT
elif st.session_state.page == "content":
    course = st.session_state.selected_course
    module = st.session_state.selected_module
    module_data = st.session_state.courses[course][module]

    # Header area to mimic NotebookLM style
    left_col, right_col = st.columns([3, 1])
    with left_col:
        st.markdown(f"## 📖 {course} → {module}")
        st.write("Upload materials, generate notes, quizzes, mindmaps, or ask questions.")
    with right_col:
        st.markdown("**Module quick actions**")
        if st.button("Export Notes (copy)"):
            st.write("You can copy generated notes from the Notes panel.")
        if st.button("Clear Module Text"):
            module_data["text"] = ""
            st.success("Cleared module text.")

    uploaded_file = st.file_uploader("Upload a PDF", type="pdf")
    text_input = st.text_area("Or paste text", value=module_data.get("text", ""), height=200)

    if uploaded_file:
        pdf_reader = PdfReader(uploaded_file)
        text_input = "".join(page.extract_text() or "" for page in pdf_reader.pages)

    module_data["text"] = text_input
    st.write("---")

    mode = st.selectbox("Choose what to generate", ["Notes", "Flashcards", "Quiz", "Mindmap"])

    if st.button("🚀 Generate"):
        if not text_input.strip():
            st.warning("Please upload or paste text first.")
        else:
            if mode == "Notes":
                prompt = f"Summarize the following text into detailed study notes:\n\n{text_input}"
                output = generate_content(prompt)
                st.subheader("📌 Notes")
                st.write(output)

            elif mode == "Flashcards":
                prompt = f"Generate 5-10 flashcards in Q&A format from the following text:\n\n{text_input}\nFormat each as 'Q: ... A: ...'."
                output = generate_content(prompt)
                st.subheader("📌 Flashcards")

                # Parse Q&A pairs
                cards = re.findall(r"Q:(.*?)A:(.*?)(?=Q:|$)", output, re.S)
                st.session_state.flashcards = [{"q": q.strip(), "a": a.strip()} for q, a in cards]
                st.session_state.flash_index = 0
                st.session_state.show_answer = False

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
                st.session_state.quiz_raw = quiz_text
                st.subheader("📝 Quiz Generated")
                st.write("Go ahead and take the quiz below!")

            elif mode == "Mindmap":
                # We ask the model to produce a hierarchical flowchart suitable for mermaid.
                prompt = (
                    "Generate a hierarchical mindmap in Mermaid flowchart TD syntax using concise nodes. "
                    "Aim for a tree layout with labels only. "
                    "Example format:\n\n"
                    "flowchart TD\n"
                    "  A[Root] --> B[Child 1]\n"
                    "  A --> C[Child 2]\n"
                    "  C --> D[Grandchild]\n\n"
                    "Now generate such a mindmap for the following text. Keep nodes short (<= 6 words) and ensure unique labels:\n\n"
                    f"{text_input}"
                )
                output = generate_content(prompt)
                output = output.strip()

                # sanitize and ensure flowchart TD exists
                output = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', output)  # remove control chars
                output = re.sub(r'[\?:"<>]', '', output)
                if not output.lower().startswith("flowchart"):
                    output = "flowchart TD\n" + output

                st.subheader("🧠 Interactive Mindmap")

                # We'll render a NotebookLM-like layout: left = mindmap, right = inspector panel.
                # Build the interactive HTML/JS/CSS with mermaid + d3 zoom + click handlers + right panel.
                safe_output = html.escape(output)

                components.html(
                    f"""
                    <!doctype html>
                    <html>
                    <head>
                      <meta charset="utf-8">
                      <style>
                        :root {{
                          --bg: #0f172a;
                          --panel: #0b1220;
                          --muted: #94a3b8;
                          --card: #0b1220;
                        }}
                        body {{
                          margin: 0;
                          font-family: Inter, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial;
                          background: linear-gradient(180deg,#0b1220 0%, #061025 100%);
                          color: #e6eef8;
                        }}
                        .container {{
                          display: grid;
                          grid-template-columns: 1fr 360px;
                          gap: 16px;
                          height: 650px;
                          padding: 16px;
                        }}
                        .left {{
                          background: linear-gradient(180deg,#071023 0%, #091828 100%);
                          border-radius: 10px;
                          padding: 12px;
                          box-shadow: 0 6px 24px rgba(2,6,23,0.6);
                          overflow: hidden;
                        }}
                        .right {{
                          background: linear-gradient(180deg,#071021 0%, #071821 100%);
                          border-radius: 10px;
                          padding: 12px;
                          box-shadow: 0 6px 24px rgba(2,6,23,0.6);
                          overflow: auto;
                        }}
                        .toolbar {{
                          display:flex;
                          gap:8px;
                          margin-bottom:8px;
                        }}
                        .btn {{
                          background: rgba(255,255,255,0.06);
                          color: #dbeafe;
                          padding:8px 10px;
                          border-radius:8px;
                          border: none;
                          cursor:pointer;
                          font-size:14px;
                        }}
                        .btn:active {{ transform: translateY(1px) }}
                        .mermaid-wrap {{
                          width:100%;
                          height:560px;
                          border-radius:8px;
                          background: transparent;
                          overflow: hidden;
                          position: relative;
                          display:flex;
                          align-items:center;
                          justify-content:center;
                        }}
                        /* inspector */
                        .inspector h3 {{ margin:0 0 8px 0; }}
                        .inspector .node-title {{
                          font-size:18px;
                          font-weight:700;
                          margin-bottom:6px;
                        }}
                        .muted {{ color: #9fb0cc; }}
                        .meta {{ font-size:13px; color:#9fb0cc; margin-top:8px; }}
                        .hint {{ font-size:13px; color:#7b8794; margin-top:10px; }}
                        .node-content {{
                          margin-top:10px;
                          background: rgba(255,255,255,0.02);
                          padding:8px;
                          border-radius:6px;
                          line-height:1.45;
                        }}
                      </style>
                    </head>
                    <body>
                      <div class="container">
                        <div class="left">
                          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                            <div style="font-weight:700; font-size:16px;">Mindmap</div>
                            <div style="font-size:13px; color:#9fb0cc;">Interactive • Click nodes to inspect</div>
                          </div>

                          <div class="toolbar">
                            <button class="btn" id="btn-reset">Reset Zoom</button>
                            <button class="btn" id="btn-fit">Fit</button>
                            <button class="btn" id="btn-focus-clear">Clear Focus</button>
                          </div>

                          <div class="mermaid-wrap" id="mermaid-wrap">
                            <div class="mermaid" id="mermaid-area">{safe_output}</div>
                          </div>
                        </div>

                        <div class="right">
                          <div class="inspector">
                            <h3>Inspector</h3>
                            <div class="hint">Click a node on the map to view its details and related nodes.</div>
                            <div style="height:12px;"></div>
                            <div id="inspector-body">
                              <div class="muted">No node selected</div>
                            </div>
                            <div class="meta">Tip: Use mouse wheel or touchpad to zoom. Drag to pan.</div>
                          </div>
                        </div>
                      </div>

                      <script type="module">
                        import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
                        import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7/+esm";

                        mermaid.initialize({{ startOnLoad: true, theme: "forest", securityLevel: "loose" }});

                        // After mermaid renders, apply d3-zoom and attach node click handlers.
                        const container = document.getElementById("mermaid-wrap");
                        const mermaidArea = document.getElementById("mermaid-area");
                        const inspector = document.getElementById("inspector-body");
                        let svgEl = null;
                        let gEl = null;
                        let zoomBehavior = null;

                        // Utility: sanitize text for panel
                        function esc(s) {{
                          const div = document.createElement('div');
                          div.textContent = s;
                          return div.innerHTML;
                        }}

                        function applyZoom() {{
                          svgEl = container.querySelector("svg");
                          if (!svgEl) return;
                          gEl = svgEl.querySelector("g");
                          if (!gEl) return;

                          // Wrap with a foreignGroup to ensure we can transform the group content
                          // Use d3 zoom
                          const d3svg = d3.select(svgEl);

                          zoomBehavior = d3.zoom()
                            .scaleExtent([0.25, 5])
                            .on("zoom", (event) => {{
                              gEl.setAttribute("transform", event.transform);
                            }});

                          d3svg.call(zoomBehavior);

                          // set initial transform to center and fit
                          fitToContainer();
                        }}

                        // Fit function: scale & center graph inside container
                        function fitToContainer() {{
                          if (!svgEl || !gEl) return;
                          const bbox = gEl.getBBox();
                          const cw = container.clientWidth;
                          const ch = container.clientHeight;
                          const scale = Math.min((cw - 40) / bbox.width, (ch - 40) / bbox.height);
                          const clampedScale = Math.max(0.25, Math.min(3, scale));
                          const tx = (cw - bbox.width * clampedScale) / 2 - bbox.x * clampedScale;
                          const ty = (ch - bbox.height * clampedScale) / 2 - bbox.y * clampedScale;
                          const t = d3.zoomIdentity.translate(tx, ty).scale(clampedScale);
                          d3.select(svgEl).transition().duration(350).call(zoomBehavior.transform, t);
                        }}

                        // Focus on a node: dim others, highlight neighbors
                        function focusNode(targetId) {{
                          if (!svgEl) return;
                          const nodes = svgEl.querySelectorAll("[id^='node-'], .node");
                          const links = svgEl.querySelectorAll("path, line");

                          // Remove any previous dim
                          nodes.forEach(n => n.style.opacity = "0.12");
                          links.forEach(l => l.style.opacity = "0.08");

                          // Highlight the chosen node and immediate neighbors (based on 'title' attributes inside labels)
                          const target = svgEl.querySelector(`[id='${targetId}']`);
                          if (!target) return;

                          // Bring target to full opacity
                          target.style.opacity = "1.0";
                          target.style.filter = "drop-shadow(0 6px 12px rgba(2,6,23,0.6))";

                          // Neighbors: find elements that have a title text matching edges
                          // We try to detect connected nodes by scanning for edges that contain the label text.
                          // Simpler: inspect <title> inside nodes to get node labels, then look for text elements in the SVG that contain those labels and edges connecting nearby positions.

                          // Make close-by nodes slightly more visible
                          const allTextElems = svgEl.querySelectorAll("g[class*='node'] text, g[class*='node'] tspan, text");
                          let clickedLabel = null;
                          // get label inside target group
                          const labelElem = target.querySelector("text");
                          if (labelElem) {{
                            clickedLabel = labelElem.innerText || labelElem.textContent;
                          }}

                          // Make neighbors (nodes with edges near the same y or x) more visible by measuring distances along bbox center
                          const targetBBox = target.getBBox();
                          const tCx = targetBBox.x + targetBBox.width/2;
                          const tCy = targetBBox.y + targetBBox.height/2;

                          const groups = svgEl.querySelectorAll("g[class*='node']");
                          groups.forEach(g => {{
                            if (g === target) return;
                            const b = g.getBBox();
                            const gCx = b.x + b.width/2;
                            const gCy = b.y + b.height/2;
                            const dist = Math.hypot(gCx - tCx, gCy - tCy);
                            if (dist < Math.max(b.width, b.height) * 8) {{
                              g.style.opacity = "0.9";
                            }}
                          }});

                          // Also reveal edges that are near the target
                          links.forEach(l => {{
                            const rect = l.getBoundingClientRect();
                            // If line bounding box intersects target's bbox, make it visible
                            const lb = l.getBBox ? l.getBBox() : {{x:0,y:0,width:0,height:0}};
                            if (Math.abs(lb.x - targetBBox.x) < 200 || Math.abs(lb.y - targetBBox.y) < 200) {{
                              l.style.opacity = "0.9";
                              l.style.strokeWidth = "2";
                            }}
                          }});
                        }}

                        function clearFocus() {{
                          if (!svgEl) return;
                          const nodes = svgEl.querySelectorAll("[id^='node-'], .node");
                          const links = svgEl.querySelectorAll("path, line");
                          nodes.forEach(n => {{
                            n.style.opacity = "1.0";
                            n.style.filter = "none";
                          }});
                          links.forEach(l => {{
                            l.style.opacity = "1.0";
                            l.style.strokeWidth = null;
                          }});
                        }}

                        // After mermaid renders, mermaid replaces the .mermaid inner HTML with an <svg>.
                        const mo = new MutationObserver((mutations) => {{
                          // wait until an svg appears inside the mermaid wrapper
                          const svg = container.querySelector("svg");
                          if (svg) {{
                            applyZoom();
                            attachNodeClicks();
                            mo.disconnect();
                          }}
                        }});
                        mo.observe(mermaidArea, {{ childList: true, subtree: true }});

                        // Attach clicks to nodes
                        function attachNodeClicks() {{
                          if (!svgEl) svgEl = container.querySelector("svg");
                          if (!svgEl) return;
                          gEl = svgEl.querySelector("g");
                          // Node groups often have class 'node' in mermaid generated output
                          const nodeGroups = svgEl.querySelectorAll("g.node, g[class*='node']");
                          nodeGroups.forEach((g, idx) => {{
                            // Give each node a stable id if not present
                            if (!g.id) g.id = "node-" + idx;
                            // add click handler
                            g.style.cursor = "pointer";
                            g.addEventListener("click", (ev) => {{
                              ev.stopPropagation();
                              const labelEl = g.querySelector("text");
                              const label = labelEl ? labelEl.textContent.trim() : g.id;
                              inspector.innerHTML = `
                                <div class="node-title">${{esc(label)}}</div>
                                <div class="node-content">
                                  <strong>Summary</strong>
                                  <div id="node-summary">Loading summary...</div>
                                </div>
                                <div style="margin-top:8px;">
                                  <button class="btn" id="btn-expand">Expand siblings</button>
                                  <button class="btn" id="btn-center">Center</button>
                                </div>
                              `;
                              // focus mode visuals
                              focusNode(g.id);

                              // center on node
                              document.getElementById("btn-center").addEventListener("click", () => {{
                                centerOnElement(g);
                              }});

                              // Expand siblings doesn't truly collapse/expand mermaid graph;
                              // instead we briefly highlight near nodes (already handled by focusNode).
                              document.getElementById("btn-expand").addEventListener("click", () => {{
                                // simply re-run focus to emphasize neighborhood
                                focusNode(g.id);
                              }});

                              // Ask the model (in the embed) to produce a short summary for the clicked node.
                              // We cannot call your Python function from here; instead we simulate by extracting text from node label
                              // and generating a short summary heuristically (you could hook this to server-side if needed).
                              const labelText = label;
                              // Basic local pseudo-summary: split label into tokens and echo
                              const pseudoSummary = `This node represents: ${{labelText}}. Use this as a quick note.`;
                              document.getElementById("node-summary").innerText = pseudoSummary;
                            }});
                          }});

                          // click on background to clear focus
                          container.querySelectorAll("svg, .mermaid-wrap").forEach(el => {{
                            el.addEventListener("click", (ev) => {{
                              clearFocus();
                              inspector.innerHTML = '<div class="muted">No node selected</div>';
                            }});
                          }});
                        }}

                        // center on element inside svg
                        function centerOnElement(el) {{
                          if (!svgEl || !gEl) return;
                          const bbox = gEl.getBBox();
                          const nodeB = el.getBBox();
                          const cw = container.clientWidth;
                          const ch = container.clientHeight;
                          const scale = Math.min((cw - 40) / bbox.width, (ch - 40) / bbox.height);
                          const clampedScale = Math.max(0.25, Math.min(3, scale));
                          const tx = (cw/2) - (nodeB.x + nodeB.width/2) * clampedScale;
                          const ty = (ch/2) - (nodeB.y + nodeB.height/2) * clampedScale;
                          const t = d3.zoomIdentity.translate(tx, ty).scale(clampedScale);
                          d3.select(svgEl).transition().duration(450).call(zoomBehavior.transform, t);
                        }}

                        // Buttons
                        document.getElementById("btn-reset").addEventListener("click", () => {{
                          d3.select(svgEl).transition().duration(350).call(zoomBehavior.transform, d3.zoomIdentity);
                          clearFocus();
                        }});
                        document.getElementById("btn-fit").addEventListener("click", () => {{
                          fitToContainer();
                          clearFocus();
                        }});
                        document.getElementById("btn-focus-clear").addEventListener("click", () => {{
                          clearFocus();
                          inspector.innerHTML = '<div class="muted">No node selected</div>';
                        }});

                        // Re-apply fit when window resizes
                        window.addEventListener("resize", () => {{
                          setTimeout(() => {{
                            fitToContainer();
                          }}, 200);
                        }});
                      </script>
                    </body>
                    </html>
                    """,
                    height=700,
                    scrolling=True,
                )

    # --- Flashcards Display ---
    if "flashcards" in st.session_state and st.session_state.flashcards:
        card = st.session_state.flashcards[st.session_state.flash_index]
        st.write("---")
        st.subheader(f"📖 Flashcard {st.session_state.flash_index+1}/{len(st.session_state.flashcards)}")

        # Flip card
        if not st.session_state.show_answer:
            st.info(f"**Q:** {card['q']}")
        else:
            st.success(f"**A:** {card['a']}")

        if st.button("🔄 Flip"):
            st.session_state.show_answer = not st.session_state.show_answer
            st.rerun()

        col1, col2 = st.columns(2)
        with col1:
            if st.session_state.flash_index > 0 and st.button("⬅ Prev"):
                st.session_state.flash_index -= 1
                st.session_state.show_answer = False
                st.rerun()
        with col2:
            if st.session_state.flash_index < len(st.session_state.flashcards) - 1 and st.button("Next ➡"):
                st.session_state.flash_index += 1
                st.session_state.show_answer = False
                st.rerun()

    # --- Quiz Taking ---
    if "quiz_raw" in st.session_state:
        st.write("---")
        st.subheader("🎯 Take Quiz")
        raw = st.session_state.quiz_raw
        questions_raw = re.split(r"Q\d+:", raw)
        questions, answers = [], []
        for q in questions_raw[1:]:
            lines = q.strip().split("\n")
            if len(lines) >= 6:
                question_text = lines[0]
                options = [line for line in lines[1:5]]
                try:
                    answer = [line for line in lines if line.startswith("Answer:")][0].replace("Answer:", "").strip()
                except Exception:
                    answer = None
                questions.append({"q": question_text, "opts": options})
                answers.append(answer)

        user_choices = []
        for i, q in enumerate(questions):
            choice = st.radio(q["q"], q["opts"], index=None, key=f"quiz{i}")
            user_choices.append(choice.split(".")[0] if choice else None)

        if st.button("Submit Quiz"):
            correct = sum(1 for i, c in enumerate(user_choices) if c == answers[i])
            wrong = sum(1 for i, c in enumerate(user_choices) if c and c != answers[i])
            missed = sum(1 for c in user_choices if c is None)
            st.success(f"✅ Correct: {correct}")
            st.error(f"❌ Wrong: {wrong}")
            st.warning(f"⚠️ Skipped: {missed}")
            st.info(f"🏆 Score: {correct}/{len(questions)}")

            # Show correct answers
            st.write("### ✅ Correct Answers")
            for i, ans in enumerate(answers, 1):
                st.write(f"Q{i}: {ans}")

    # --- Q&A ---
    st.write("---")
    st.subheader("❓ Ask a Question")
    q_text = st.text_input("Type your question")
    if st.button("Ask"):
        if q_text.strip():
            q_prompt = f"Answer the following based on this module:\n\n{text_input}\n\nQ: {q_text}"
            ans = generate_content(q_prompt)
            st.markdown(f"**Answer:** {ans}")
        else:
            st.warning("Enter a question first.")

    if st.button("⬅ Back to Modules"):
        st.session_state.page = "modules"
        st.rerun()

import html
from io import BytesIO

import streamlit as st
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, Preformatted, SimpleDocTemplate, Spacer

from chat_controller import ChatController

st.set_page_config(page_title="AI Clinical Intake Assistant", layout="wide")

# --- STYLING (Kept your professional purple theme) ---
st.markdown(
    """
    <style>
        :root {
            --bg-top: #f8f3ff;
            --bg-bottom: #efe4ff;
            --panel: rgba(255, 255, 255, 0.86);
            --panel-strong: #ffffff;
            --primary: #6d3df2;
            --primary-dark: #4f22c8;
            --secondary: #8f66ff;
            --text: #24143f;
            --muted: #65597d;
            --border: rgba(109, 61, 242, 0.14);
            --shadow: 0 18px 45px rgba(78, 34, 200, 0.12);
            --shadow-soft: 0 10px 24px rgba(78, 34, 200, 0.08);
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(159, 106, 255, 0.18), transparent 30%),
                radial-gradient(circle at top right, rgba(109, 61, 242, 0.16), transparent 28%),
                linear-gradient(180deg, var(--bg-top) 0%, var(--bg-bottom) 100%);
            color: var(--text);
        }

        .hero-card, .glass-card, .report-card, .chat-shell, .report-section {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 24px;
            box-shadow: var(--shadow);
            backdrop-filter: blur(14px);
            padding: 1.2rem 1.3rem;
            margin-bottom: 1rem;
        }

        .hero-card {
            background: linear-gradient(135deg, rgba(109, 61, 242, 0.95), rgba(161, 104, 255, 0.88));
            color: white;
        }

        .metric-chip {
            display: inline-block;
            padding: 0.4rem 0.7rem;
            margin: 0 0.5rem 0.5rem 0;
            border-radius: 999px;
            background: rgba(109, 61, 242, 0.09);
            color: var(--primary-dark);
            font-size: 0.86rem;
            font-weight: 600;
        }

        .bubble.user {
            background: linear-gradient(135deg, var(--primary), #875eff);
            color: white;
            border-radius: 22px 22px 8px 22px;
        }

        .bubble.assistant {
            background: white;
            color: var(--text);
            border: 1px solid rgba(109, 61, 242, 0.1);
            border-radius: 22px 22px 22px 8px;
        }

        .history-item {
            padding: 0.8rem 0.9rem;
            background: rgba(109, 61, 242, 0.05);
            border: 1px solid rgba(109, 61, 242, 0.09);
            border-radius: 16px;
            margin-bottom: 0.7rem;
        }
        
        /* Fixed scrolling for chat */
        .chat-scroll {
            max-height: 500px;
            overflow-y: auto;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- UTILS ---
INTAKE_STEPS = ["demographics", "complaint", "duration", "context", "clarification", "medications", "allergies", "past_history", "summary", "done"]

def get_progress_value(step: str | None) -> tuple[float, str]:
    step = step or "demographics"
    idx = INTAKE_STEPS.index(step) if step in INTAKE_STEPS else 0
    progress = (idx + 1) / len(INTAKE_STEPS)
    labels = {"demographics": "Details", "complaint": "Concern", "summary": "Finalizing", "done": "Ready"}
    return progress, labels.get(step, "Intake in progress")

def generate_pdf(summary_text: str):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    elements = [Paragraph("<b>AI Clinical Case Summary</b>", styles["Heading1"]), Spacer(1, 0.3 * inch), Preformatted(summary_text, styles["Normal"])]
    doc.build(elements)
    buffer.seek(0)
    return buffer

def render_message(role: str, content: str) -> None:
    bubble_class = "user" if role == "user" else "assistant"
    label = "Patient" if role == "user" else "AI Intake"
    st.markdown(f"""
        <div style="display: flex; justify-content: {'flex-end' if role=='user' else 'flex-start'}; margin-bottom: 10px;">
            <div class="bubble {bubble_class}" style="max-width: 80%; padding: 15px;">
                <small style="font-weight: bold; display: block; margin-bottom: 5px;">{label}</small>
                {content}
            </div>
        </div>
    """, unsafe_allow_html=True)

# --- CORE RENDERING ---
def render_sidebar_snapshot(state: dict):
    progress, label = get_progress_value(state.get("step"))
    st.write(f"**Progress: {label}**")
    st.progress(progress)

    st.markdown(f"""
        <div class="glass-card">
            <div style="font-weight: bold; margin-bottom: 10px;">Patient Info</div>
            <span class="metric-chip">{state.get('age_gender', 'Pending')}</span>
        </div>
    """, unsafe_allow_html=True)

    # --- THE FIX FOR MEDICAL HISTORY ---
    history_html = ""
    history_map = [
        ("Medications", state.get("medications")),
        ("Allergies", state.get("allergies")),
        ("History", state.get("past_history"))
    ]
    for title, val in history_map:
        history_html += f"""
        <div class="history-item">
            <strong>{title}</strong><br>
            <span style="color: #65597d; font-size: 0.9em;">{val or "Not reported"}</span>
        </div>"""
    
    st.markdown(f"""
        <div class="glass-card">
            <div style="font-weight: bold; margin-bottom: 10px;">Medical Snapshot</div>
            {history_html}
        </div>
    """, unsafe_allow_html=True)

def render_final_report(chat, state):
    st.markdown('<div class="hero-card"><h2>Clinical Report Ready</h2></div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([1.5, 1])
    
    with col1:
        # Displaying the Markdown summary properly
        st.markdown("### 📋 Case Summary")
        st.info(state.get("summary", "Generating..."))
        
        st.markdown("### 🧠 AI Clinical Context (RAG)")
        st.success(state.get("clinical_context", "Context unavailable."))

    with col2:
        render_sidebar_snapshot(state)
        pdf = generate_pdf(state.get("summary", ""))
        st.download_button("Download PDF Report", data=pdf, file_name="report.pdf", use_container_width=True)
        if st.button("Start New Case", use_container_width=True):
            st.session_state.chat = ChatController()
            st.session_state.messages = []
            st.rerun()

# --- APP LOGIC ---
if "chat" not in st.session_state: st.session_state.chat = ChatController()
if "messages" not in st.session_state: st.session_state.messages = []

chat = st.session_state.chat
state = chat.state

if state["step"] == "demographics":
    st.markdown('<div class="hero-card"><h1>New Patient Intake</h1></div>', unsafe_allow_html=True)
    age = st.number_input("Age", 0, 120, 25)
    gender = st.selectbox("Gender", ["Female", "Male", "Other"])
    if st.button("Begin Consultation", use_container_width=True):
        state["age_gender"] = f"{age}, {gender}"
        state["step"] = "complaint"
        st.session_state.messages = [{"role": "assistant", "content": "Hello. What symptoms are you experiencing today?"}]
        st.rerun()

elif state["step"] in ["summary", "done"]:
    render_final_report(chat, state)

else:
    col_chat, col_side = st.columns([1.5, 1])
    with col_chat:
        for m in st.session_state.messages: render_message(m["role"], m["content"])
        
        user_input = st.chat_input("Enter response...")
        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            reply = chat.handle_text(user_input)
            st.session_state.messages.append({"role": "assistant", "content": reply})
            st.rerun()
            
    with col_side:
        render_sidebar_snapshot(state)
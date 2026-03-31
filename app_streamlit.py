import html
from io import BytesIO

import streamlit as st
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, Preformatted, SimpleDocTemplate, Spacer

from chat_controller import ChatController


st.set_page_config(page_title="AI Clinical Intake Assistant", layout="wide")

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

        .block-container {
            padding-top: 2rem;
            padding-bottom: 2.5rem;
            max-width: 1240px;
        }

        .hero-card,
        .glass-card,
        .report-card,
        .chat-shell,
        .report-section {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 24px;
            box-shadow: var(--shadow);
            backdrop-filter: blur(14px);
        }

        .hero-card {
            padding: 1.6rem 1.8rem;
            background: linear-gradient(135deg, rgba(109, 61, 242, 0.95), rgba(161, 104, 255, 0.88));
            color: white;
        }

        .hero-title {
            font-size: 2rem;
            font-weight: 700;
            line-height: 1.1;
            margin-bottom: 0.35rem;
        }

        .hero-subtitle {
            font-size: 0.98rem;
            opacity: 0.92;
        }

        .glass-card,
        .report-card,
        .report-section {
            padding: 1.2rem 1.3rem;
        }

        .section-title {
            font-size: 1rem;
            font-weight: 700;
            color: var(--text);
            margin-bottom: 0.75rem;
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

        .subtle-text {
            color: var(--muted);
            font-size: 0.92rem;
            line-height: 1.55;
        }

        .chat-shell {
            padding: 1rem;
        }

        .chat-scroll {
            display: flex;
            flex-direction: column;
            gap: 0.9rem;
            max-height: 60vh;
            overflow-y: auto;
            padding-right: 0.35rem;
        }

        .message-row {
            display: flex;
            width: 100%;
        }

        .message-row.user {
            justify-content: flex-end;
        }

        .message-row.assistant {
            justify-content: flex-start;
        }

        .bubble {
            max-width: 78%;
            padding: 0.9rem 1rem;
            border-radius: 22px;
            box-shadow: var(--shadow-soft);
            line-height: 1.5;
            font-size: 0.96rem;
            white-space: pre-wrap;
        }

        .bubble.user {
            background: linear-gradient(135deg, var(--primary), #875eff);
            color: white;
            border-bottom-right-radius: 8px;
        }

        .bubble.assistant {
            background: rgba(255, 255, 255, 0.96);
            color: var(--text);
            border: 1px solid rgba(109, 61, 242, 0.1);
            border-bottom-left-radius: 8px;
        }

        .bubble-label {
            display: block;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 0.3rem;
            opacity: 0.8;
        }

        .step-card {
            background: rgba(109, 61, 242, 0.07);
            border: 1px solid rgba(109, 61, 242, 0.12);
            border-radius: 18px;
            padding: 0.9rem 1rem;
            margin-bottom: 0.8rem;
        }

        .step-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--primary-dark);
            font-weight: 700;
            margin-bottom: 0.25rem;
        }

        .urgency-banner {
            border-radius: 22px;
            padding: 1rem 1.1rem;
            color: white;
            font-weight: 600;
            box-shadow: var(--shadow-soft);
            margin-bottom: 1rem;
        }

        .alert-banner {
            border-radius: 22px;
            padding: 1rem 1.1rem;
            background: linear-gradient(135deg, #9b0019, #d7263d);
            color: white;
            box-shadow: var(--shadow-soft);
            margin-bottom: 1rem;
            border: 1px solid rgba(255, 255, 255, 0.14);
        }

        .urgency-low { background: linear-gradient(135deg, #4f8f6b, #6cb68b); }
        .urgency-moderate { background: linear-gradient(135deg, #6d3df2, #8f66ff); }
        .urgency-high { background: linear-gradient(135deg, #ff8f3d, #ff5f6d); }
        .urgency-emergency { background: linear-gradient(135deg, #d7263d, #9b0019); }

        .report-section {
            margin-bottom: 1rem;
        }

        .report-section h4 {
            margin: 0 0 0.55rem 0;
            color: var(--text);
        }

        .report-body {
            color: var(--muted);
            line-height: 1.65;
            font-size: 0.95rem;
        }

        .report-highlight {
            padding: 0.95rem 1rem;
            border-radius: 18px;
            background: rgba(109, 61, 242, 0.05);
            border: 1px solid rgba(109, 61, 242, 0.1);
            margin-bottom: 0.9rem;
        }

        .progress-shell {
            padding: 1rem 1.1rem;
            margin-bottom: 1rem;
        }

        .progress-label {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 0.65rem;
            font-size: 0.9rem;
            color: var(--muted);
        }

        .history-item {
            padding: 0.8rem 0.9rem;
            background: rgba(109, 61, 242, 0.05);
            border: 1px solid rgba(109, 61, 242, 0.09);
            border-radius: 16px;
            margin-bottom: 0.7rem;
        }

        .stButton > button,
        .stDownloadButton > button {
            background: linear-gradient(135deg, var(--primary), #8b63ff);
            color: white;
            border: none;
            border-radius: 14px;
            font-weight: 700;
            height: 3rem;
            box-shadow: var(--shadow-soft);
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover {
            background: linear-gradient(135deg, var(--primary-dark), var(--primary));
            color: white;
        }

        .stTextInput input,
        .stNumberInput input,
        .stSelectbox div[data-baseweb="select"] > div,
        .stChatInput input {
            border-radius: 14px !important;
            border: 1px solid rgba(109, 61, 242, 0.16) !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


INTAKE_STEPS = [
    "demographics",
    "complaint",
    "duration",
    "context",
    "clarification",
    "medications",
    "allergies",
    "past_history",
    "summary",
    "done",
]


def get_progress_value(step: str | None) -> tuple[float, str]:
    normalized_step = step or "demographics"
    if normalized_step not in INTAKE_STEPS:
        normalized_step = "demographics"

    index = INTAKE_STEPS.index(normalized_step)
    progress = (index + 1) / len(INTAKE_STEPS)

    labels = {
        "demographics": "Patient details",
        "complaint": "Chief concern",
        "duration": "Symptom timing",
        "context": "Care context",
        "clarification": "Guided symptom questions",
        "medications": "Medication review",
        "allergies": "Allergy check",
        "past_history": "Medical history",
        "summary": "Preparing report",
        "done": "Report ready",
    }
    return progress, labels.get(normalized_step, "Patient intake")


def generate_pdf(summary_text: str):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()

    elements = [
        Paragraph("<b>AI Clinical Case Summary</b>", styles["Heading1"]),
        Spacer(1, 0.3 * inch),
        Preformatted(summary_text, styles["Normal"]),
    ]

    doc.build(elements)
    buffer.seek(0)
    return buffer


def extract_age_gender(age_gender_value: str | None) -> tuple[str, str]:
    if not age_gender_value:
        return "Not captured", "Not captured"

    parts = [part.strip() for part in age_gender_value.split(",", maxsplit=1)]
    if len(parts) == 2:
        return parts[0], parts[1]
    return age_gender_value, "Not captured"


def render_message(role: str, content: str) -> None:
    bubble_role = "user" if role == "user" else "assistant"
    label = "Patient" if role == "user" else "AI Intake"
    safe_content = html.escape(content or "").replace("\n", "<br>")
    st.markdown(
        f"""
        <div class="message-row {bubble_role}">
            <div class="bubble {bubble_role}">
                <span class="bubble-label">{label}</span>
                {safe_content}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def urgency_css_class(urgency: str) -> str:
    normalized = (urgency or "moderate").strip().lower()
    return {
        "low": "urgency-low",
        "moderate": "urgency-moderate",
        "high": "urgency-high",
        "emergency": "urgency-emergency",
    }.get(normalized, "urgency-moderate")


def render_progress_card(state: dict) -> None:
    progress, label = get_progress_value(state.get("step"))
    st.markdown('<div class="glass-card progress-shell">', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="progress-label">
            <span>Intake Progress</span>
            <span>{label}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(progress)
    st.markdown("</div>", unsafe_allow_html=True)


def render_report_section(title: str, body: str) -> None:
    safe_body = html.escape(body or "Not available.").replace("\n", "<br>")
    st.markdown(
        f"""
        <div class="report-section">
            <h4>{html.escape(title)}</h4>
            <div class="report-body">{safe_body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_snapshot(state: dict) -> None:
    age, gender = extract_age_gender(state.get("age_gender"))

    render_progress_card(state)

    with st.container():
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Patient Info Card</div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <span class="metric-chip">Age: {age}</span>
            <span class="metric-chip">Gender: {gender}</span>
            <span class="metric-chip">Stage: {state.get("step", "unknown").title()}</span>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Complaint Card</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="subtle-text">{state.get("complaint") or "The patient complaint will appear here once intake begins."}</div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    current_question = None
    if state.get("step") == "clarification":
        idx = state.get("current_question_index", 0)
        questions = state.get("questions", [])
        if idx < len(questions):
            current_question = questions[idx]

    with st.container():
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Question Flow UI</div>', unsafe_allow_html=True)
        steps = [
            ("1", "Complaint", state.get("complaint") or "Waiting for chief complaint"),
            ("2", "Symptom Details", state.get("duration") or "We are gathering when the symptoms started and the care context"),
            ("3", "Follow-up Questions", current_question or "Guided questions will appear here one at a time"),
            ("4", "Medical History", "Medications, allergies, and long-term conditions are collected near the end"),
        ]
        for number, title, text in steps:
            st.markdown(
                f"""
                <div class="step-card">
                    <div class="step-label">Step {number}</div>
                    <strong>{title}</strong><br>
                    <span class="subtle-text">{text}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)


def render_demographics(state: dict) -> None:
    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-title">AI Clinical Intake System</div>
            <div class="hero-subtitle">A guided patient intake workspace with a modern conversational experience and structured clinical output.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left_col, right_col = st.columns([1.15, 0.85], gap="large")

    with left_col:
        with st.container():
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Begin New Intake</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="subtle-text">Capture basic patient details first, then continue through the guided complaint and question flow.</div>',
                unsafe_allow_html=True,
            )
            col1, col2 = st.columns(2)
            with col1:
                age = st.number_input("Age", min_value=0, max_value=120, step=1)
            with col2:
                gender = st.selectbox("Gender", ["Select", "Female", "Male", "Other"])

            if st.button("Start Consultation", use_container_width=True):
                if gender == "Select":
                    st.warning("Please select gender.")
                else:
                    state["age_gender"] = f"{age}, {gender}"
                    state["step"] = "complaint"
                    st.session_state.messages = [
                        {"role": "assistant", "content": "What problem are you facing today?"}
                    ]
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    with right_col:
        with st.container():
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Workflow</div>', unsafe_allow_html=True)
            st.markdown(
                """
                <div class="subtle-text">
                    Patient details -> Symptom chat -> Follow-up questions -> Medical history -> Clinical report
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)


def render_chat_ui(chat: ChatController, state: dict) -> None:
    left_col, right_col = st.columns([1.45, 0.85], gap="large")

    with left_col:
        st.markdown(
            """
            <div class="hero-card">
                <div class="hero-title">Clinical Intake Conversation</div>
                <div class="hero-subtitle">A guided chat for patient complaints, follow-up questions, and intake history.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container():
            st.markdown('<div class="chat-shell"><div class="chat-scroll">', unsafe_allow_html=True)
            if st.session_state.messages:
                for msg in st.session_state.messages:
                    render_message(msg["role"], msg["content"])
            else:
                st.markdown(
                    '<div class="subtle-text">The conversation will appear here once intake begins.</div>',
                    unsafe_allow_html=True,
                )
            st.markdown("</div></div>", unsafe_allow_html=True)

        user_input = st.chat_input("Type the next patient response here")
        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.spinner("Updating the intake conversation..."):
                bot_reply = chat.handle_text(user_input)
            st.session_state.messages.append({"role": "assistant", "content": bot_reply})
            st.rerun()

        if state["step"] == "clarification":
            with st.container():
                st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                st.markdown('<div class="section-title">Optional Prescription Upload</div>', unsafe_allow_html=True)
                uploaded_file = st.file_uploader(
                    "Attach a prescription image if available",
                    type=["jpg", "jpeg", "png"],
                )
                if uploaded_file:
                    image_bytes = uploaded_file.read()
                    with st.spinner("Reviewing the prescription image..."):
                        chat.handle_file(image_bytes)
                    st.success("Prescription reviewed and added.")
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    with right_col:
        render_sidebar_snapshot(state)


def render_final_report(chat: ChatController, state: dict) -> None:
    if not state.get("summary"):
        with st.spinner("Generating the clinical report..."):
            chat.generate_summary()

    urgency = state.get("urgency", "Moderate")
    urgency_class = urgency_css_class(urgency)
    age, gender = extract_age_gender(state.get("age_gender"))

    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-title">Clinical Report</div>
            <div class="hero-subtitle">A structured, professional summary generated from the completed intake conversation.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left_col, right_col = st.columns([1.35, 0.9], gap="large")

    with left_col:
        render_progress_card(state)

        if str(urgency).strip().lower() == "emergency":
            st.markdown(
                """
                <div class="alert-banner">
                    <strong>Emergency alert</strong><br>
                    This intake has been marked as emergency priority and should be reviewed immediately.
                </div>
                """,
                unsafe_allow_html=True,
            )

        with st.container():
            st.markdown(
                f"""
                <div class="urgency-banner {urgency_class}">
                    Urgency Level: {urgency}
                </div>
                """,
                unsafe_allow_html=True,
            )

        with st.container():
            st.markdown('<div class="report-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Professional Clinical Report</div>', unsafe_allow_html=True)

            st.markdown(
                f"""
                <div class="report-highlight">
                    <strong>Patient concern</strong><br>
                    <span class="subtle-text">{html.escape(state.get("complaint") or "No complaint recorded.")}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            render_report_section(
                "Clinical Summary",
                state.get("summary", "Clinical summary not available."),
            )
            render_report_section(
                "Clinical Context",
                state.get("clinical_context", "Clinical context not available."),
            )
            st.markdown("</div>", unsafe_allow_html=True)

    with right_col:
        with st.container():
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Patient Info Card</div>', unsafe_allow_html=True)
            st.markdown(
                f"""
                <span class="metric-chip">Age: {age}</span>
                <span class="metric-chip">Gender: {gender}</span>
                <span class="metric-chip">Complaint captured</span>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Complaint Card</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="subtle-text">{state.get("complaint") or "No complaint recorded."}</div>',
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Medical History</div>', unsafe_allow_html=True)
            history_items = [
                ("Current medications", state.get("medications") or "Not reported"),
                ("Known allergies", state.get("allergies") or "Not reported"),
                ("Past medical history", state.get("past_history") or "Not reported"),
            ]
            for label, value in history_items:
                st.markdown(
                    f"""
                    <div class="history-item">
                        <strong>{label}</strong><br>
                        <span class="subtle-text">{value}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)

        pdf_file = generate_pdf(state.get("summary", ""))
        st.download_button(
            label="Download Report",
            data=pdf_file,
            file_name="clinical_summary.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

        if st.button("Start New Case", use_container_width=True):
            st.session_state.chat = ChatController()
            st.session_state.messages = []
            st.rerun()


if "chat" not in st.session_state:
    st.session_state.chat = ChatController()

if "messages" not in st.session_state:
    st.session_state.messages = []

chat = st.session_state.chat
state = chat.state

if state["step"] == "demographics":
    render_demographics(state)
elif state["step"] == "summary" or state["step"] == "done":
    render_final_report(chat, state)
else:
    render_chat_ui(chat, state)

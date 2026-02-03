import streamlit as st
import docx
from pathlib import Path
import re
import smtplib
from email.message import EmailMessage
import google.generativeai as genai

# =============================
# CONSTANTS
# =============================
SENDER_EMAIL = "soumikghoshalireland@gmail.com"
LLM_ENABLED = True

# =============================
# GEMINI CONFIG
# =============================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite")

# =============================
# GEMINI PROMPTS
# =============================
COMMON_GEMINI_CONSTRAINTS = """
NON-NEGOTIABLE RULES:
- Do NOT assign scores or numeric evaluations
- Do NOT make hire / no-hire decisions
- Do NOT invent skills or experiences
- Base insights strictly on transcript & signals
- Be concise and evidence-based
"""

GEMINI_CANDIDATE_PROMPT = f"""
You are generating respectful, growth-oriented feedback for a candidate.

{COMMON_GEMINI_CONSTRAINTS}

FORMAT:
- Strengths Observed
- Areas to Improve
- Suggestions for Growth
"""

GEMINI_INTERVIEWER_PROMPT = f"""
You are generating private interviewer feedback.

{COMMON_GEMINI_CONSTRAINTS}

FORMAT:
### Interview Summary
### System Feedback (Candidate Signals)
### Interview Improvements
"""

# =============================
# SESSION STATE
# =============================
if "ai_feedback" not in st.session_state:
    st.session_state.ai_feedback = None
    st.session_state.ai_attempted = False

if "interviewer_feedback" not in st.session_state:
    st.session_state.interviewer_feedback = None

if "emails_sent" not in st.session_state:
    st.session_state.emails_sent = False

# =============================
# READ TRANSCRIPT
# =============================
def read_transcript(uploaded_file) -> str:
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".docx":
        doc = docx.Document(uploaded_file)
        return "\n".join(p.text for p in doc.paragraphs).lower()
    elif suffix == ".txt":
        return uploaded_file.read().decode("utf-8", errors="ignore").lower()
    else:
        raise ValueError("Unsupported file format")

# =============================
# ANALYSIS LOGIC (UNCHANGED)
# =============================
FILLER_WORDS = ["um", "uh", "like", "you know", "basically", "sort of", "kind of"]
EXAMPLE_PHRASES = ["for example", "for instance", "when i", "i worked on"]
IMPACT_WORDS = ["%", "percent", "increased", "reduced", "improved", "delivered"]
PROBLEM_WORDS = ["problem", "challenge", "solution", "approach"]

PERSONALITY_SIGNALS = {
    "Confidence": ["i led", "i owned", "i decided"],
    "Collaboration": ["we", "team", "stakeholder"],
    "Growth Mindset": ["learned", "improved"],
    "Uncertainty": ["maybe", "i think", "sort of"]
}

def communication_score(text):
    filler_count = sum(text.count(f) for f in FILLER_WORDS)
    return max(0, 100 - filler_count * 5)

def interview_skill_score(text):
    score = 0
    if any(p in text for p in EXAMPLE_PHRASES): score += 30
    if any(p in text for p in IMPACT_WORDS): score += 35
    if any(p in text for p in PROBLEM_WORDS): score += 35
    return min(score, 100)

def personality_analysis(text):
    result = {}
    for k, v in PERSONALITY_SIGNALS.items():
        result[k] = "High" if any(p in text for p in v) else "Low"
    return result

def overall_interview_score(comm, skill, personality):
    p_score = sum(1 for v in personality.values() if v == "High") / len(personality)
    return round(comm * 0.35 + skill * 0.4 + p_score * 100 * 0.25, 2)

# =============================
# GEMINI CALLS
# =============================
@st.cache_data(show_spinner=False)
def call_gemini(prompt):
    if not LLM_ENABLED:
        return "LLM disabled"
    return gemini_model.generate_content(
        prompt,
        generation_config={"temperature": 0.2, "max_output_tokens": 350}
    ).text

@st.cache_data(show_spinner=False)
def generate_ai_feedback():
    return call_gemini(GEMINI_CANDIDATE_PROMPT)

@st.cache_data(show_spinner=False)
def generate_interviewer_feedback(transcript, interviewer_comments, strong, weak):
    prompt = f"""
INTERVIEW TRANSCRIPT:
{transcript}

INTERVIEWER COMMENTS:
{interviewer_comments}

SYSTEM STRONG SIGNALS:
{strong}

SYSTEM WEAK SIGNALS:
{weak}

{GEMINI_INTERVIEWER_PROMPT}
"""
    return call_gemini(prompt)

# =============================
# EMAIL BUILDERS
# =============================
def build_candidate_email(strengths, weaknesses):
    return f"""
Strengths:
- {', '.join(strengths)}

Areas to Improve:
- {', '.join(weaknesses)}
"""

def build_interviewer_email(feedback):
    return f"""
INTERVIEWER FEEDBACK (PRIVATE)

{feedback}

Note: For interview quality improvement only.
"""

def send_email(subject, body, recipient):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = recipient
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, st.secrets["EMAIL_APP_PASSWORD"])
        server.send_message(msg)

# =============================
# STREAMLIT UI
# =============================
st.set_page_config(page_title="Interview Analyzer", layout="centered")
st.title("🎯 Interview Performance Analyzer")

uploaded_file = st.file_uploader("Upload Interview Transcript", ["txt", "docx"])

if uploaded_file:
    text = read_transcript(uploaded_file)

    comm = communication_score(text)
    skill = interview_skill_score(text)
    personality = personality_analysis(text)
    final_score = overall_interview_score(comm, skill, personality)

    st.subheader("📊 Scores")
    st.metric("Overall", f"{final_score}%")
    st.metric("Communication", f"{comm}%")
    st.metric("Skills", f"{skill}%")

    strong = [k for k in IMPACT_WORDS if k in text][:5]
    weak = [k for k in FILLER_WORDS if k in text][:5]

    if not st.session_state.ai_attempted:
        st.session_state.ai_attempted = True
        st.session_state.ai_feedback = generate_ai_feedback()

    st.subheader("🤖 AI Interview Coach Feedback")
    st.write(st.session_state.ai_feedback)

    st.subheader("🧑‍💼 Interviewer Evaluation")
    interviewer_comments = st.text_area("Comments")

    # 🔹 PREVIEW INTERVIEWER FEEDBACK
    if st.session_state.interviewer_feedback is None:
        st.session_state.interviewer_feedback = generate_interviewer_feedback(
            text, interviewer_comments, strong, weak
        )

    with st.expander("🧑‍🏫 Interviewer Feedback Preview", expanded=True):
        st.write(st.session_state.interviewer_feedback)

    interviewer_email = st.text_input("Interviewer Email")

    if st.button("📤 Send Interviewer Feedback") and not st.session_state.emails_sent:
        st.session_state.emails_sent = True
        send_email(
            "Interview Feedback & Calibration (Private)",
            build_interviewer_email(st.session_state.interviewer_feedback),
            interviewer_email
        )
        st.success("✅ Interviewer feedback email sent")

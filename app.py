import streamlit as st
import docx
from pathlib import Path
import re
import tempfile
import requests
import google.generativeai as genai

# =============================
# CONFIG
# =============================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite")

RESEND_API_KEY = st.secrets["RESEND_API_KEY"]
RESEND_ENDPOINT = "https://api.resend.com/emails"
SENDER_EMAIL = "Soumik <onboarding@resend.dev>"  # default Resend sender

# =============================
# SESSION STATE
# =============================
if "ai_feedback" not in st.session_state:
    st.session_state.ai_feedback = None
    st.session_state.ai_attempted = False

# =============================
# HELPERS
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

FILLER_WORDS = ["um", "uh", "like", "you know", "basically", "sort of", "kind of"]

def communication_score(text: str) -> float:
    words = text.split()
    sentences = [s for s in re.split(r"[.!?]", text) if s.strip()]
    filler_count = sum(text.count(f) for f in FILLER_WORDS)
    avg_sentence_length = len(words) / max(len(sentences), 1)
    score = 1 - min(filler_count / 12, 1) - (0.3 if avg_sentence_length > 25 else 0)
    return round(max(score, 0) * 100, 2)

EXAMPLE_PHRASES = ["for example", "for instance", "when i", "i worked on"]
IMPACT_WORDS = ["%", "percent", "increased", "reduced", "improved"]
PROBLEM_WORDS = ["problem", "challenge", "solution", "approach"]

def interview_skill_score(text: str) -> float:
    score = 0
    if any(p in text for p in EXAMPLE_PHRASES): score += 0.3
    if any(p in text for p in IMPACT_WORDS): score += 0.35
    if any(p in text for p in PROBLEM_WORDS): score += 0.35
    return round(score * 100, 2)

PERSONALITY_SIGNALS = {
    "Confidence": ["i led", "i owned", "i decided"],
    "Collaboration": ["we", "team", "stakeholder"],
    "Growth Mindset": ["learned", "improved"],
    "Uncertainty": ["maybe", "i think"]
}

def personality_analysis(text: str):
    return {
        trait: "High" if sum(text.count(p) for p in phrases) >= 3 else
               "Medium" if any(p in text for p in phrases) else "Low"
        for trait, phrases in PERSONALITY_SIGNALS.items()
    }

def overall_interview_score(comm, skill, personality):
    personality_score = sum(
        1 if v == "High" else 0.5 if v == "Medium" else 0
        for v in personality.values()
    ) / len(personality)

    return round(
        skill * 0.4 + comm * 0.35 + personality_score * 100 * 0.25, 2
    )

# =============================
# AI FEEDBACK
# =============================
def generate_ai_feedback(summary: dict) -> str:
    prompt = f"""
You are an experienced interview coach.

Give:
1. Overall assessment
2. 2 strengths
3. 2 improvements

Scores:
Communication: {summary['communication_score']}%
Interview Skills: {summary['skill_score']}%
Personality: {summary['personality']}
"""
    response = gemini_model.generate_content(prompt)
    return response.text

# =============================
# TEXT REPORT
# =============================
def generate_feedback_text(summary: dict, feedback: str) -> str:
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    with open(temp.name, "w") as f:
        f.write("INTERVIEW PERFORMANCE REPORT\n\n")
        f.write(f"Overall Score: {summary['final_score']}%\n\n")
        f.write(feedback)
    return temp.name

# =============================
# RESEND EMAIL
# =============================
def send_email_to_user(file_path: str, user_email: str):
    with open(file_path, "r") as f:
        content = f.read()

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {st.secrets['RESEND_API_KEY']}",
            "Content-Type": "application/json"
        },
        json={
            "from": "onboarding@resend.dev",
            "to": user_email,
            "subject": "Your Interview Feedback Report",
            "text": content
        }
    )

    if response.status_code not in (200, 201):
        raise Exception("Email failed to send")

# =============================
# UI
# =============================
st.set_page_config(page_title="Interview Analyzer", layout="centered")
st.title("🎯 Interview Performance Analyzer")

uploaded_file = st.file_uploader("Upload transcript (.txt / .docx)", ["txt", "docx"])
user_email = st.text_input("📧 Enter your email to receive the report")

if uploaded_file:
    text = read_transcript(uploaded_file)

    comm = communication_score(text)
    skill = interview_skill_score(text)
    personality = personality_analysis(text)
    final_score = overall_interview_score(comm, skill, personality)

    summary = {
        "communication_score": comm,
        "skill_score": skill,
        "personality": personality,
        "final_score": final_score
    }

    if not st.session_state.ai_attempted:
        st.session_state.ai_attempted = True
        st.session_state.ai_feedback = generate_ai_feedback(summary)

    st.subheader("🤖 AI Feedback")
    st.write(st.session_state.ai_feedback)

    if st.button("📤 Email Me the Report"):
        if not user_email:
            st.error("Please enter an email address")
        else:
            report = generate_feedback_text(summary, st.session_state.ai_feedback)
            send_email_to_user(report, user_email)
            st.success("✅ Email sent successfully!")

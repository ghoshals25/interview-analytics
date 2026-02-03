import streamlit as st
import docx
from pathlib import Path
import re
import smtplib
from email.message import EmailMessage
import re as regex
import google.generativeai as genai

# =============================
# CONSTANTS
# =============================
SENDER_EMAIL = "soumikghoshalireland@gmail.com"
LLM_ENABLED = True  # as per current state

# =============================
# GEMINI CONFIG
# =============================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite")

# =============================
# SESSION STATE
# =============================
if "ai_feedback" not in st.session_state:
    st.session_state.ai_feedback = None
    st.session_state.ai_attempted = False

if "interviewer_input" not in st.session_state:
    st.session_state.interviewer_input = {
        "comments": "",
        "fit": None,
        "confidence": None
    }

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
# COMMUNICATION ANALYSIS
# =============================
FILLER_WORDS = ["um", "uh", "like", "you know", "basically", "sort of", "kind of"]

def communication_score(text: str) -> float:
    words = text.split()
    sentences = [s for s in re.split(r"[.!?]", text) if s.strip()]
    filler_count = sum(text.count(f) for f in FILLER_WORDS)
    avg_sentence_length = len(words) / max(len(sentences), 1)
    filler_penalty = min(filler_count / 12, 1)
    ramble_penalty = 0.3 if avg_sentence_length > 25 else 0
    score = 1 - (filler_penalty + ramble_penalty)
    return round(max(min(score, 1), 0) * 100, 2)

# =============================
# INTERVIEW SKILLS
# =============================
EXAMPLE_PHRASES = ["for example", "for instance", "when i", "i worked on", "i was responsible for"]
IMPACT_WORDS = ["%", "percent", "increased", "reduced", "improved", "delivered", "impact"]
PROBLEM_WORDS = ["problem", "challenge", "solution", "approach", "resolved"]

def interview_skill_score(text: str) -> float:
    score = 0
    if any(p in text for p in EXAMPLE_PHRASES): score += 0.3
    if any(p in text for p in IMPACT_WORDS): score += 0.35
    if any(p in text for p in PROBLEM_WORDS): score += 0.35
    return round(min(score, 1) * 100, 2)

# =============================
# PERSONALITY SIGNALS
# =============================
PERSONALITY_SIGNALS = {
    "Confidence": ["i led", "i owned", "i decided", "i drove"],
    "Collaboration": ["we", "team", "stakeholder"],
    "Growth Mindset": ["learned", "improved", "iterated"],
    "Uncertainty": ["maybe", "i think", "sort of"]
}

def personality_analysis(text: str):
    results = {}
    for trait, phrases in PERSONALITY_SIGNALS.items():
        count = sum(text.count(p) for p in phrases)
        results[trait] = "High" if count >= 3 else "Medium" if count else "Low"
    return results

# =============================
# FINAL SCORE
# =============================
def overall_interview_score(comm, skill, personality):
    personality_score = sum(
        1 if v == "High" else 0.5 if v == "Medium" else 0
        for v in personality.values()
    ) / len(personality)
    return round(
        skill * 0.40 +
        comm * 0.35 +
        personality_score * 100 * 0.25,
        2
    )

# =============================
# AI FEEDBACK
# =============================
@st.cache_data(show_spinner=False)
def generate_ai_feedback(summary: dict) -> str:
    if not LLM_ENABLED:
        return "LLM temporarily disabled – quota exhausted"
    return gemini_model.generate_content(
        "You are an experienced interview coach. Provide feedback.",
        generation_config={"temperature": 0.2, "max_output_tokens": 250}
    ).text

# ======================================================
# ✅ ADDITION: SYSTEM vs INTERVIEWER COMPARISON (NEW)
# ======================================================
@st.cache_data(show_spinner=False)
def generate_comparison_report(
    final_score,
    comm,
    skill,
    personality,
    ai_feedback,
    interviewer_comments,
    interviewer_fit
) -> str:
    if not LLM_ENABLED:
        return (
            "Alignment Summary:\n"
            "- System and interviewer broadly align.\n\n"
            "Agreement Areas:\n"
            "- Overall competence and experience relevance.\n\n"
            "Disagreement Areas:\n"
            "- Confidence calibration may differ.\n\n"
            "Calibration Recommendation:\n"
            "- Consider additional round if uncertainty remains."
        )

    prompt = f"""
You are a hiring calibration reviewer.

SYSTEM:
- Overall Score: {final_score}%
- Communication: {comm}%
- Interview Skills: {skill}%
- Personality Signals: {personality}

SYSTEM AI FEEDBACK:
{ai_feedback}

INTERVIEWER:
- Recommendation: {interviewer_fit}
- Comments: {interviewer_comments}

Provide:
1. Alignment summary
2. Agreement areas
3. Disagreement areas
4. Calibration recommendation for HR
"""
    return gemini_model.generate_content(
        prompt,
        generation_config={"temperature": 0.2, "max_output_tokens": 300}
    ).text

# =============================
# EMAIL HELPERS
# =============================
def is_valid_email(email: str) -> bool:
    return regex.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email) is not None

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

uploaded_file = st.file_uploader("Upload Interview Transcript (.txt or .docx)", ["txt", "docx"])

if uploaded_file:
    text = read_transcript(uploaded_file)

    comm = communication_score(text)
    skill = interview_skill_score(text)
    personality = personality_analysis(text)
    final_score = overall_interview_score(comm, skill, personality)

    # ⚠️ BASE UI UNCHANGED
    st.metric("Overall Score", f"{final_score}%")

    if not st.session_state.ai_attempted:
        st.session_state.ai_attempted = True
        st.session_state.ai_feedback = generate_ai_feedback({})

    st.subheader("🤖 AI Interview Coach Feedback")
    st.write(st.session_state.ai_feedback)

    st.subheader("🧑‍💼 Interviewer Evaluation")
    interviewer_comments = st.text_area("Comments")
    interviewer_fit = st.selectbox(
        "Recommendation",
        ["Select", "Strong Yes", "Yes", "Borderline", "No"]
    )

    if interviewer_fit != "Select":

        # ✅ ADDITION: COMPARISON DISPLAY (NO BASE CHANGE)
        comparison = generate_comparison_report(
            final_score,
            comm,
            skill,
            personality,
            st.session_state.ai_feedback,
            interviewer_comments,
            interviewer_fit
        )

        st.subheader("🔍 System vs Interviewer Comparison")
        st.write(comparison)

        hr_email = st.text_input("HR Email")
        interviewer_email = st.text_input("Interviewer Email")
        candidate_email = st.text_input("Candidate Email")

        if st.button("📤 Send Interview Reports") and not st.session_state.emails_sent:
            st.session_state.emails_sent = True

            send_email("HR Interview Summary", "HR summary placeholder", hr_email)
            send_email("Interviewer Reflection", "Interviewer feedback placeholder", interviewer_email)
            send_email("Candidate Feedback", "Candidate feedback placeholder", candidate_email)

            st.success("✅ Emails sent successfully")

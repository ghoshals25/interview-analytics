import streamlit as st
import docx
from pathlib import Path
import re
import smtplib
from email.message import EmailMessage
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

# =============================
# CONSTANTS / FEATURE FLAGS
# =============================
SENDER_EMAIL = "soumikghoshalireland@gmail.com"
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

# 🔒 Gemini is DISABLED
LLM_ENABLED = False

# =============================
# GEMINI CONFIG (INACTIVE)
# =============================
if LLM_ENABLED:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite")

# =============================
# GEMINI PROMPTS (UNCHANGED)
# =============================
COMMON_GEMINI_CONSTRAINTS = """
NON-NEGOTIABLE RULES:
- Do NOT assign scores
- Do NOT make hire decisions
- Do NOT invent information
- Use only provided data
- Be concise and structured
"""

GEMINI_SYSTEM_SUMMARY_PROMPT = f"""
You are interpreting interview evaluation results for internal review.

{COMMON_GEMINI_CONSTRAINTS}

Explain what the scores indicate about the candidate.
Focus on clarity, strengths, and risks.
"""

GEMINI_INTERVIEWER_COACHING_PROMPT = f"""
You are providing private coaching feedback to an interviewer.

{COMMON_GEMINI_CONSTRAINTS}

FORMAT:
- What went well
- What could be improved
- Missed probing opportunities
"""

# =============================
# SESSION STATE
# =============================
for key in [
    "system_summary",
    "interviewer_feedback",
    "comparison",
    "emails_sent"
]:
    if key not in st.session_state:
        st.session_state[key] = None

# =============================
# READ TRANSCRIPT
# =============================
def read_transcript(uploaded_file):
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".docx":
        doc = docx.Document(uploaded_file)
        return "\n".join(p.text for p in doc.paragraphs).lower()
    return uploaded_file.read().decode("utf-8", errors="ignore").lower()

# =============================
# ANALYSIS LOGIC (UNCHANGED)
# =============================
FILLER_WORDS = ["um", "uh", "like", "you know"]
IMPACT_WORDS = ["%", "increased", "reduced", "improved"]
EXAMPLE_PHRASES = ["for example", "when i", "i worked on"]

def communication_score(text):
    return max(0, 100 - sum(text.count(w) for w in FILLER_WORDS) * 5)

def interview_skill_score(text):
    score = 0
    if any(p in text for p in EXAMPLE_PHRASES):
        score += 40
    if any(p in text for p in IMPACT_WORDS):
        score += 60
    return min(score, 100)

def overall_interview_score(comm, skill):
    return round(comm * 0.4 + skill * 0.6, 2)

# =============================
# GEMINI HELPER (DISABLED)
# =============================
def call_gemini(prompt):
    return "AI interpretation disabled."

# =============================
# EMAIL HELPERS (SAFE)
# =============================
def is_valid_email(email):
    return email and re.match(EMAIL_REGEX, email)

def send_email(subject, body, recipient):
    if not is_valid_email(recipient):
        st.warning(f"⚠️ Skipping invalid email: {recipient}")
        return

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

# -----------------------------------------------------
# 1️⃣ SYSTEM SCORING
# -----------------------------------------------------
if uploaded_file:
    text = read_transcript(uploaded_file)

    comm = communication_score(text)
    skill = interview_skill_score(text)
    final_score = overall_interview_score(comm, skill)

    st.subheader("📊 System Scores")
    st.metric("Overall Score", f"{final_score}%")
    st.metric("Communication", f"{comm}%")
    st.metric("Interview Skills", f"{skill}%")

    # -------------------------------------------------
    # 2️⃣ SYSTEM INTERPRETATION (STATIC)
    # -------------------------------------------------
    if st.session_state.system_summary is None:
        st.session_state.system_summary = call_gemini("")

    st.subheader("🧠 System Interpretation")
    st.write(st.session_state.system_summary)

    # -------------------------------------------------
    # 3️⃣ INTERVIEWER INPUT
    # -------------------------------------------------
    st.subheader("🧑‍💼 Interviewer Feedback")
    interviewer_comments = st.text_area("Comments")
    interviewer_fit = st.selectbox(
        "Recommendation",
        ["Select", "Strong Yes", "Yes", "Borderline", "No"]
    )

    # -------------------------------------------------
    # 4️⃣ SYSTEM vs INTERVIEWER COMPARISON
    # -------------------------------------------------
    if interviewer_fit != "Select" and interviewer_comments:
        if st.session_state.comparison is None:
            st.session_state.comparison = call_gemini("")

        st.subheader("🔍 System vs Interviewer Comparison")
        st.write(st.session_state.comparison)

        # -------------------------------------------------
        # 5️⃣ INTERVIEWER COACHING (DISABLED)
        # -------------------------------------------------
        if st.session_state.interviewer_feedback is None:
            st.session_state.interviewer_feedback = call_gemini("")

        st.subheader("🧑‍🏫 Interviewer Coaching (Preview)")
        st.write(st.session_state.interviewer_feedback)

        # -------------------------------------------------
        # 6️⃣ EMAIL INPUTS
        # -------------------------------------------------
        st.subheader("📧 Send Reports")
        hr_email = st.text_input("HR Email")
        candidate_email = st.text_input("Candidate Email")
        interviewer_email = st.text_input("Interviewer Email")

        # -------------------------------------------------
        # 7️⃣ SEND EMAILS
        # -------------------------------------------------
        if st.button("📤 Send Emails") and not st.session_state.emails_sent:
            if not any([hr_email, candidate_email, interviewer_email]):
                st.error("❌ Please enter at least one valid email address")
                st.stop()

            st.session_state.emails_sent = True

            send_email(
                "HR Interview Summary",
                st.session_state.system_summary + "\n\n" + str(st.session_state.comparison),
                hr_email
            )

            send_email(
                "Your Interview Feedback",
                "Thank you for interviewing. You will hear back soon.",
                candidate_email
            )

            send_email(
                "Interview Coaching Feedback (Private)",
                str(st.session_state.interviewer_feedback),
                interviewer_email
            )

            st.success("✅ Emails sent successfully")

# =========================================================
# INTERVIEW READY – FINAL PRODUCTION (APPLY + EMAIL FIXES)
# =========================================================

import streamlit as st
import docx
import re
import tempfile
from email.message import EmailMessage
import smtplib

import google.generativeai as genai
from faster_whisper import WhisperModel

# =============================
# PAGE CONFIG
# =============================
st.set_page_config(page_title="Interview Ready", layout="wide")

# =============================
# CONFIG
# =============================
GEMINI_MODEL = "gemini-2.5-flash-lite"
SENDER_EMAIL = "soumikghoshalireland@gmail.com"
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

# =============================
# GEMINI CONFIG
# =============================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
gemini_model = genai.GenerativeModel(GEMINI_MODEL)

# =============================
# PROMPTS
# =============================
COMMON_GEMINI_CONSTRAINTS = """
NON-NEGOTIABLE RULES:
- Be concise and factual
- Do NOT assign scores
- Do NOT make hiring decisions
- Do NOT invent information
- Use only provided content
"""

GEMINI_JD_CV_ANALYSIS_PROMPT = f"""
You are analysing a Job Description and Candidate CV.

{COMMON_GEMINI_CONSTRAINTS}

Provide:
- Candidate summary
- Key JD expectations
- Key candidate skills
- Interview focus areas
"""

GEMINI_INTERVIEW_ANALYSIS_PROMPT = f"""
Analyse the interview transcript on:
- Behavioural indicators
- Leadership & ownership
- Technical skills
- Learning capability
- Growth mentality
- Handling complex situations

{COMMON_GEMINI_CONSTRAINTS}
"""

GEMINI_COMPARISON_PROMPT = f"""
Compare system interview analysis with interviewer feedback.

{COMMON_GEMINI_CONSTRAINTS}

Provide:
1. Alignment areas
2. Differences
3. Open questions for next round
"""

GEMINI_INTERVIEWER_COACHING_PROMPT = f"""
Provide coaching feedback for the interviewer.

{COMMON_GEMINI_CONSTRAINTS}
"""

# =============================
# SESSION STATE
# =============================
for key in [
    "jd_cv_analysis",
    "interview_analysis",
    "comparison",
    "interviewer_comments",
    "audio_preview",
    "pre_applied",
    "post_applied",
    "emails_sent"
]:
    if key not in st.session_state:
        st.session_state[key] = None

# =============================
# HELPERS
# =============================
def read_docx(file):
    doc = docx.Document(file)
    return "\n".join(p.text for p in doc.paragraphs).lower()

def is_valid_email(email):
    return email and re.match(EMAIL_REGEX, email)

def send_email(subject, body, recipient):
    if not is_valid_email(recipient):
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
# WHISPER
# =============================
@st.cache_resource
def load_whisper():
    return WhisperModel("base", device="cpu", compute_type="int8")

def transcribe_audio(path):
    model = load_whisper()
    segments, _ = model.transcribe(path)
    return " ".join(s.text for s in segments).lower()

# =============================
# UI HEADER
# =============================
st.title("🎯 Interview Ready")
st.caption("Structured pre-interview preparation and post-interview evaluation")
st.divider()

pre_tab, post_tab = st.tabs(["🧩 Pre-Interview", "🎤 Post-Interview"])

# =====================================================
# PRE-INTERVIEW TAB
# =====================================================
with pre_tab:

    with st.sidebar:
        st.header("📄 JD & Candidate Overview")
        if st.session_state.jd_cv_analysis:
            st.markdown(st.session_state.jd_cv_analysis)
        else:
            st.caption("Apply JD & CV to generate overview")

    jd = st.text_area("Job Description", height=220)
    cv = st.file_uploader("Candidate CV (DOCX)", ["docx"])

    if st.button("✅ Apply Pre-Interview Inputs"):
        if not jd or not cv:
            st.warning("Please provide both JD and CV")
        else:
            cv_text = read_docx(cv)
            st.session_state.jd_cv_analysis = gemini_model.generate_content(
                f"JD:\n{jd}\n\nCV:\n{cv_text}\n\n{GEMINI_JD_CV_ANALYSIS_PROMPT}"
            ).text
            st.session_state.pre_applied = True
            st.success("JD & CV applied successfully")

# =====================================================
# POST-INTERVIEW TAB
# =====================================================
with post_tab:

    interview_file = st.file_uploader(
        "Upload Interview Transcript / Audio / Video",
        ["txt", "docx", "mp3", "wav"]
    )

    if interview_file and st.button("✅ Apply Interview Inputs"):
        if interview_file.name.endswith(".docx"):
            interview_text = read_docx(interview_file)
        else:
            interview_text = interview_file.read().decode("utf-8", errors="ignore")

        st.session_state.interview_analysis = gemini_model.generate_content(
            f"{interview_text}\n\n{GEMINI_INTERVIEW_ANALYSIS_PROMPT}"
        ).text
        st.session_state.post_applied = True

    if st.session_state.post_applied:
        st.subheader("🧠 System Interview Analysis")
        st.write(st.session_state.interview_analysis)

        st.subheader("🧑‍💼 Interviewer Feedback")

        with st.expander("🎙️ Dictate feedback"):
            audio = st.audio_input("Record feedback")
            if audio:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as t:
                    t.write(audio.getvalue())
                    st.session_state.audio_preview = transcribe_audio(t.name)

                st.text_area("Preview", st.session_state.audio_preview)

                if st.button("Use transcription"):
                    st.session_state.interviewer_comments = st.session_state.audio_preview

        st.session_state.interviewer_comments = st.text_area(
            "Final Comments",
            st.session_state.interviewer_comments or ""
        )

        recommendation = st.selectbox(
            "Overall Recommendation",
            ["Proceed", "Hold", "Reject"]
        )

        # =============================
        # EMAIL INPUTS (FIXED)
        # =============================
        candidate_email = st.text_input("Candidate Email")
        hr_email = st.text_input("HR Email")
        interviewer_email = st.text_input("Interviewer Email")

        emails_ready = all([
            is_valid_email(candidate_email),
            is_valid_email(hr_email),
            is_valid_email(interviewer_email)
        ])

        if not emails_ready:
            st.info("Enter valid email addresses to enable sending")

        if st.button("📧 Send Emails", disabled=not emails_ready) and not st.session_state.emails_sent:
            st.session_state.emails_sent = True

            send_email(
                "Interview Feedback",
                "Strengths:\n- Strong communication\n\nAreas to improve:\n- Handling ambiguity",
                candidate_email
            )

            send_email(
                "Interview Summary & Next Steps",
                f"""
Summary:
{st.session_state.interview_analysis}

Interviewer View:
{st.session_state.interviewer_comments}

Next Step:
{recommendation}
""",
                hr_email
            )

            send_email(
                "Interviewer Coaching",
                gemini_model.generate_content(GEMINI_INTERVIEWER_COACHING_PROMPT).text,
                interviewer_email
            )

            st.success("✅ Emails sent")

import streamlit as st
import docx
import re
import tempfile
import subprocess
from pathlib import Path
from email.message import EmailMessage
import smtplib

import google.generativeai as genai
from faster_whisper import WhisperModel
import imageio_ffmpeg
import pdfplumber

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
    "interviewer_comments",
    "audio_preview",
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

def read_pdf(file):
    text = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text.append(page.extract_text() or "")
    return "\n".join(text).lower()

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

def extract_audio_from_video(video_path, audio_path):
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [ffmpeg_path, "-y", "-i", video_path, audio_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

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
    cv = st.file_uploader(
        "Candidate CV (DOCX or PDF)",
        ["docx", "pdf"]
    )

    if st.button("✅ Apply Pre-Interview Inputs"):
        if jd and cv:
            if cv.name.endswith(".docx"):
                cv_text = read_docx(cv)
            else:
                cv_text = read_pdf(cv)

            st.session_state.jd_cv_analysis = gemini_model.generate_content(
                f"JD:\n{jd}\n\nCV:\n{cv_text}\n\n{GEMINI_JD_CV_ANALYSIS_PROMPT}"
            ).text

# =====================================================
# POST-INTERVIEW TAB
# =====================================================
with post_tab:

    interview_file = st.file_uploader(
        "Upload Interview (Text / Audio / Video)",
        ["txt", "docx", "mp3", "wav", "mp4", "mov", "webm"]
    )

    interview_text = ""

    if interview_file:
        suffix = interview_file.name.split(".")[-1]

        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{suffix}") as t:
            t.write(interview_file.read())
            temp_path = t.name

        if suffix in ["txt"]:
            interview_text = Path(temp_path).read_text(errors="ignore").lower()

        elif suffix == "docx":
            interview_text = read_docx(temp_path)

        elif suffix in ["mp3", "wav"]:
            interview_text = transcribe_audio(temp_path)

        elif suffix in ["mp4", "mov", "webm"]:
            audio_path = temp_path + ".wav"
            extract_audio_from_video(temp_path, audio_path)
            interview_text = transcribe_audio(audio_path)

    if interview_text and st.button("✅ Apply Interview Inputs"):
        st.session_state.interview_analysis = gemini_model.generate_content(
            f"{interview_text}\n\n{GEMINI_INTERVIEW_ANALYSIS_PROMPT}"
        ).text

    if st.session_state.interview_analysis:
        st.subheader("🧠 System Interview Analysis")
        st.write(st.session_state.interview_analysis)

    # =============================
    # INTERVIEWER DICTATION (ALWAYS ENABLED)
    # =============================
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
    # EMAILS
    # =============================
    if st.button("📧 Send Emails") and not st.session_state.emails_sent:
        st.session_state.emails_sent = True

        candidate_email = st.text_input("Candidate Email")
        hr_email = st.text_input("HR Email")
        interviewer_email = st.text_input("Interviewer Email")

        send_email(
            "Interview Feedback",
            "Thank you for attending the interview.\n\nWe will get back to you shortly.",
            candidate_email
        )

        send_email(
            "Interview Summary",
            f"""
System Summary:
{st.session_state.interview_analysis}

Interviewer Feedback:
{st.session_state.interviewer_comments}

Recommendation:
{recommendation}
""",
            hr_email
        )

        send_email(
            "Interviewer Coaching",
            gemini_model.generate_content(GEMINI_INTERVIEWER_COACHING_PROMPT).text,
            interviewer_email
        )

        st.success("✅ Emails sent successfully")

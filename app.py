# =========================================================
# INTERVIEW READY – FINAL PRODUCTION VERSION (APPLY CONTROL)
# =========================================================

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
# PROMPTS (UNCHANGED)
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
You are analyzing a Job Description and a Candidate CV.

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

# =============================
# SESSION STATE
# =============================
for key in [
    "jd_cv_analysis",
    "interview_system_analysis",
    "interviewer_comments",
    "audio_preview",
    "pre_applied",
    "post_applied",
    "emails_sent"
]:
    if key not in st.session_state:
        st.session_state[key] = False if "applied" in key else None

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

def build_candidate_feedback_email(system_analysis, interviewer_comments):
    return f"""
Thank you for taking the time to interview with us.

Based on the interview discussion, here is some high-level feedback to support your development:

Strengths observed:
- Clear communication and articulation of experience
- Demonstrated ownership and accountability in past roles
- Structured approach to problem-solving

Areas for improvement:
- Handling ambiguous or open-ended scenarios
- Providing deeper technical examples when discussing complex problems

This feedback is shared to support your growth and reflection.

Best regards,
Hiring Team
"""

# =============================
# WHISPER (UNCHANGED)
# =============================
@st.cache_resource
def load_whisper():
    return WhisperModel("base", device="cpu", compute_type="int8")

def transcribe_audio(path):
    model = load_whisper()
    segments, _ = model.transcribe(path)
    return " ".join(s.text for s in segments).lower()

def extract_audio_from_video(uploaded_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as v:
        v.write(uploaded_file.read())
        video_path = v.name
    audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [ffmpeg, "-y", "-i", video_path, "-ac", "1", "-ar", "16000", audio_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True
    )
    return audio_path

# =============================
# HEADER
# =============================
st.title("🎯 Interview Ready")
st.caption("Pre-interview preparation and post-interview evaluation")
st.divider()

pre_tab, post_tab = st.tabs(["🧩 Pre-Interview", "🎤 Post-Interview"])

# =====================================================
# PRE-INTERVIEW
# =====================================================
with pre_tab:

    with st.sidebar:
        st.header("📄 JD & Candidate Overview")
        if st.session_state.pre_applied:
            st.markdown(st.session_state.jd_cv_analysis)
        else:
            st.caption("Apply JD & CV to see overview")

    jd = st.text_area("Job Description", height=220)
    cv = st.file_uploader("Candidate CV (DOCX)", ["docx"])

    if st.button("✅ Apply Pre-Interview"):
        if jd and cv:
            cv_text = read_docx(cv)
            st.session_state.jd_cv_analysis = gemini_model.generate_content(
                f"JD:\n{jd}\n\nCV:\n{cv_text}\n\n{GEMINI_JD_CV_ANALYSIS_PROMPT}"
            ).text
            st.session_state.pre_applied = True
            st.success("Pre-interview context applied")

# =====================================================
# POST-INTERVIEW
# =====================================================
with post_tab:

    interview_file = st.file_uploader(
        "Upload Interview Transcript / Audio / Video",
        ["txt", "docx", "mp3", "wav", "mp4", "mov"]
    )

    if interview_file and st.button("✅ Apply Interview"):
        interview_text = transcribe_audio(
            extract_audio_from_video(interview_file)
        ) if interview_file.name.endswith((".mp4", ".mov")) else (
            read_docx(interview_file)
            if interview_file.name.endswith(".docx")
            else interview_file.read().decode("utf-8", errors="ignore")
        )

        st.session_state.interview_system_analysis = gemini_model.generate_content(
            f"{interview_text}\n\n{GEMINI_INTERVIEW_ANALYSIS_PROMPT}"
        ).text
        st.session_state.post_applied = True

    if st.session_state.post_applied:
        st.subheader("🧠 System Interview Analysis")
        st.markdown(st.session_state.interview_system_analysis)

        st.session_state.interviewer_comments = st.text_area(
            "Interviewer Comments",
            st.session_state.interviewer_comments or ""
        )

        candidate_email = st.text_input("Candidate Email")
        hr_email = st.text_input("HR Email")

        if st.button("📧 Send Emails") and not st.session_state.emails_sent:
            st.session_state.emails_sent = True

            send_email(
                "Interview Feedback",
                build_candidate_feedback_email(
                    st.session_state.interview_system_analysis,
                    st.session_state.interviewer_comments
                ),
                candidate_email
            )

            send_email(
                "Interview Summary – Internal",
                st.session_state.interview_system_analysis,
                hr_email
            )

            st.success("✅ Emails sent")

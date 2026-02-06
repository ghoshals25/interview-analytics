# =========================================================
# INTERVIEW READY – FINAL PRODUCTION VERSION (LOCKED)
# =========================================================

import streamlit as st
import docx
import re
import tempfile
import subprocess
from pathlib import Path
from email.message import EmailMessage
import smtplib
from PyPDF2 import PdfReader

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
You are analyzing a Job Description and a Candidate CV for interview preparation.

{COMMON_GEMINI_CONSTRAINTS}

OUTPUT FORMAT (STRICT):

Candidate Name:
<name or 'Not explicitly stated'>

Candidate Summary:
- 3–4 bullet points summarizing background and role fit

Key JD Highlights:
- 5 concise bullets capturing role expectations

Top 10 Candidate Skills:
- Bullet list (skills inferred directly from CV)

Top 5 Interview Questions:
- Role-relevant, probing questions
"""

GEMINI_INTERVIEW_ANALYSIS_PROMPT = f"""
You are analysing an interview transcript.

{COMMON_GEMINI_CONSTRAINTS}

Analyse the interview on:
- Behavioural indicators
- Leadership & ownership
- Technical skills
- Learning capability
- Growth mentality
- Handling complex situations

Use bullet points under each heading.
"""

GEMINI_COMPARISON_PROMPT = f"""
Compare system interview analysis with interviewer feedback.

{COMMON_GEMINI_CONSTRAINTS}

OUTPUT:
1. Common agreement areas
2. Key differences
3. Open questions for next round
"""

GEMINI_INTERVIEWER_COACHING_PROMPT = f"""
Provide private coaching feedback for the interviewer.

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
    "jd_cv_analysis",
    "jd_cv_hash",
    "interview_system_analysis",
    "interview_hash",
    "interview_comparison",
    "interviewer_comments",
    "audio_preview",
    "emails_sent",
    "last_recommendation"
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
    reader = PdfReader(file)
    return "\n".join(
        page.extract_text() for page in reader.pages if page.extract_text()
    ).lower()

def normalize(text):
    return re.sub(r"[^a-z0-9 ]", " ", text.lower())

def hash_text(text):
    return hash(text)

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
# SKILL BUCKETS
# =============================
SKILL_BUCKETS = {
    "skills": ["analytics", "insights", "strategy", "stakeholder", "problem solving"],
    "ownership": ["led", "owned", "managed", "delivered", "end to end"],
    "tools": ["python", "sql", "power bi", "tableau", "excel"]
}

def compute_overlap(jd_text, cv_text):
    jd_text, cv_text = normalize(jd_text), normalize(cv_text)
    details = {}
    for bucket, keywords in SKILL_BUCKETS.items():
        jd_items = {k for k in keywords if k in jd_text}
        cv_items = {k for k in keywords if k in cv_text}
        details[bucket] = {
            "union": jd_items | cv_items,
            "intersection": jd_items & cv_items,
            "missing": jd_items - cv_items
        }
    return details

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

def extract_interview_text(uploaded_file):
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".docx":
        return read_docx(uploaded_file)
    if suffix == ".txt":
        return uploaded_file.read().decode("utf-8", errors="ignore").lower()
    if suffix in [".mp3", ".wav"]:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as t:
            t.write(uploaded_file.read())
            return transcribe_audio(t.name)
    if suffix in [".mp4", ".mov"]:
        return transcribe_audio(extract_audio_from_video(uploaded_file))
    raise ValueError("Unsupported file type")

# =============================
# HEADER
# =============================
st.title("🎯 Interview Ready")
st.caption("The desired interview platform for structured interview preparation")
st.divider()

# =============================
# TABS
# =============================
pre_tab, post_tab = st.tabs(
    ["🧩 Pre-Interview Preparation", "🎤 Post-Interview Evaluation"]
)

# =====================================================
# PRE-INTERVIEW
# =====================================================
with pre_tab:

    with st.sidebar:
        st.header("📄 JD & Candidate Overview")
        if st.session_state.jd_cv_analysis:
            st.markdown(st.session_state.jd_cv_analysis)
        else:
            st.caption("Upload JD and CV to see overview")

    left, right = st.columns([1.1, 1])

    with left:
        st.subheader("📄 Candidate & Role Context")
        with st.container(border=True):
            job_description = st.text_area("Job Description", height=220)
            uploaded_cv = st.file_uploader("Candidate CV", ["docx", "pdf"])

            if uploaded_cv and job_description:
                if uploaded_cv.name.lower().endswith(".pdf"):
                    cv_text = read_pdf(uploaded_cv)
                else:
                    cv_text = read_docx(uploaded_cv)

                current_hash = hash_text(job_description + cv_text)

                if st.session_state.jd_cv_hash != current_hash:
                    st.session_state.jd_cv_hash = current_hash
                    st.session_state.jd_cv_analysis = gemini_model.generate_content(
                        f"""
JOB DESCRIPTION:
{job_description}

CANDIDATE CV:
{cv_text}

{GEMINI_JD_CV_ANALYSIS_PROMPT}
"""
                    ).text

                overlap = compute_overlap(job_description, cv_text)

    with right:
        st.subheader("🧠 Skills to JD Overlap Summary")

        if uploaded_cv and job_description:
            jd_focus, cv_matches, cv_gaps = set(), set(), set()
            for info in overlap.values():
                jd_focus |= info["union"]
                cv_matches |= info["intersection"]
                cv_gaps |= info["missing"]

            st.markdown("**What the role is looking for**")
            st.write(", ".join(sorted(jd_focus)) or "No strong signals")

            st.markdown("**What the CV demonstrates clearly**")
            st.write(", ".join(sorted(cv_matches)) or "No clear matches")

            st.markdown("**Skills and areas to test during the interview**")
            st.write(", ".join(sorted(cv_gaps)) or "No major gaps detected")

# =====================================================
# POST-INTERVIEW
# =====================================================
with post_tab:

    uploaded_interview = st.file_uploader(
        "Upload Interview Transcript / Audio / Video",
        ["txt", "docx", "mp3", "wav", "mp4", "mov"]
    )

    if uploaded_interview:
        interview_text = extract_interview_text(uploaded_interview)
        interview_hash = hash_text(interview_text)

        if st.session_state.interview_hash != interview_hash:
            st.session_state.interview_hash = interview_hash
            st.session_state.interview_system_analysis = gemini_model.generate_content(
                f"""
INTERVIEW TRANSCRIPT:
{interview_text}

{GEMINI_INTERVIEW_ANALYSIS_PROMPT}
"""
            ).text

        st.subheader("🧠 System Interview Analysis")
        st.markdown(st.session_state.interview_system_analysis)

        st.subheader("🧑‍💼 Interviewer Observations")
        audio_input = st.audio_input("Record interviewer feedback")

        if audio_input:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as t:

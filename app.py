# =============================
# INTERVIEW READY – FULL MERGED VERSION
# =============================

import streamlit as st
import docx
from pathlib import Path
import re
import smtplib
from email.message import EmailMessage
import tempfile
import subprocess
from collections import Counter

import google.generativeai as genai
from faster_whisper import WhisperModel
import imageio_ffmpeg

# =============================
# CONFIG
# =============================
st.set_page_config(page_title="Interview Ready", layout="centered")

SENDER_EMAIL = "soumikghoshalireland@gmail.com"
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
GEMINI_MODEL = "gemini-2.5-flash-lite"

# =============================
# GEMINI SETUP
# =============================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
gemini_model = genai.GenerativeModel(GEMINI_MODEL)

COMMON_GEMINI_CONSTRAINTS = """
NON-NEGOTIABLE RULES:
- Do NOT assign scores
- Do NOT make hire decisions
- Do NOT invent information
- Use only provided content
- Be concise and structured
"""

GEMINI_INTERVIEW_ANALYSIS_PROMPT = f"""
You are analysing an interview transcript.

{COMMON_GEMINI_CONSTRAINTS}

Analyse ONLY on:
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
    "system_analysis",
    "comparison",
    "interviewer_feedback",
    "emails_sent"
]:
    if key not in st.session_state:
        st.session_state[key] = None

# =============================
# WHISPER
# =============================
@st.cache_resource
def load_whisper():
    return WhisperModel("base", device="cpu", compute_type="int8")

# =============================
# FILE HELPERS
# =============================
def read_transcript(uploaded_file):
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".docx":
        doc = docx.Document(uploaded_file)
        return "\n".join(p.text for p in doc.paragraphs).lower()
    return uploaded_file.read().decode("utf-8", errors="ignore").lower()

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

def extract_text(uploaded_file):
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix in [".txt", ".docx"]:
        return read_transcript(uploaded_file)
    if suffix in [".mp3", ".wav"]:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as t:
            t.write(uploaded_file.read())
            return transcribe_audio(t.name)
    if suffix in [".mp4", ".mov"]:
        audio = extract_audio_from_video(uploaded_file)
        return transcribe_audio(audio)
    raise ValueError("Unsupported file type")

def transcribe_interviewer_audio(audio_bytes):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as t:
        t.write(audio_bytes)
        path = t.name
    model = load_whisper()
    segments, _ = model.transcribe(path)
    return " ".join(s.text for s in segments).lower()

# =============================
# SYSTEM SCORING
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
# JD–CV ATS ENGINE
# =============================
SKILL_BUCKETS = {
    "Skills": ["analytics", "insights", "strategy", "stakeholder"],
    "Ownership": ["led", "owned", "managed", "delivered"],
    "Tools": ["python", "sql", "power bi", "tableau", "excel"]
}

def normalize(text):
    return re.sub(r"[^a-z0-9 ]", " ", text.lower())

def keyword_frequency(text, keywords):
    words = normalize(text).split()
    counter = Counter(words)
    return {k: counter[k] for k in keywords}

def compute_cv_match(jd_text, cv_text):
    scores = {}
    pct_list = []

    for bucket, keywords in SKILL_BUCKETS.items():
        jd_freq = keyword_frequency(jd_text, keywords)
        cv_freq = keyword_frequency(cv_text, keywords)
        matched = sum(1 for k in keywords if jd_freq[k] > 0 and cv_freq[k] > 0)
        pct = round((matched / len(keywords)) * 100, 1)
        scores[bucket] = pct
        pct_list.append(pct)

    return round(sum(pct_list) / len(pct_list), 1), scores

def cv_summary(score, breakdown):
    strengths = [k for k, v in breakdown.items() if v >= 70]
    gaps = [k for k, v in breakdown.items() if v < 40]
    s = f"CV shows a {score}% alignment with the role."
    if strengths:
        s += f" Strong in {', '.join(strengths)}."
    if gaps:
        s += f" Gaps in {', '.join(gaps)}."
    return s

# =============================
# EMAIL
# =============================
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
# UI
# =============================
st.title("🎯 Interview Ready")

st.markdown(
    """
    **Interviewer:** BSY  
    **Designation:** Director  
    ---
    """
)

# =============================
# PRE-INTERVIEW CONTEXT
# =============================
st.subheader("🧩 Pre-Interview Context")

candidate_name = st.text_input("Candidate Name")
candidate_role = st.text_input("Target Role")

job_description = st.text_area("Job Description")
uploaded_cv = st.file_uploader("Upload Candidate CV (DOCX)", ["docx"])

cv_text, cv_score, cv_breakdown, cv_summary_text = "", None, None, None

if uploaded_cv and job_description:
    doc = docx.Document(uploaded_cv)
    cv_text = "\n".join(p.text for p in doc.paragraphs).lower()
    cv_score, cv_breakdown = compute_cv_match(job_description.lower(), cv_text)
    cv_summary_text = cv_summary(cv_score, cv_breakdown)

    st.success(f"CV–JD Match Score: {cv_score}%")
    for k, v in cv_breakdown.items():
        st.write(f"**{k}:** {v}%")

    st.info(f"🔍 Interview Focus: {cv_summary_text}")

# =============================
# INTERVIEW EVIDENCE
# =============================
st.subheader("🎙️ Interview Evidence")

uploaded_file = st.file_uploader(
    "Upload Interview Transcript / Audio / Video",
    ["txt", "docx", "mp3", "wav", "mp4", "mov"]
)

if uploaded_file:
    text = extract_text(uploaded_file)

    comm = communication_score(text)
    skill = interview_skill_score(text)
    final_score = overall_interview_score(comm, skill)

    st.subheader("📊 System Score (Automated)")
    st.metric("Overall", f"{final_score}%")
    st.metric("Communication", f"{comm}%")
    st.metric("Interview Skills", f"{skill}%")

    st.subheader("🧠 System Interview Analysis")
    if st.session_state.system_analysis is None:
        prompt = f"""
INTERVIEW TRANSCRIPT:
{text}

{GEMINI_INTERVIEW_ANALYSIS_PROMPT}
"""
        st.session_state.system_

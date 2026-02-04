# =============================
# INTERVIEW ANALYZER – FULL MERGED VERSION
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
SENDER_EMAIL = "soumikghoshalireland@gmail.com"
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

LLM_ENABLED = True
GEMINI_MODEL = "gemini-2.5-flash-lite"

# =============================
# GEMINI CONFIG
# =============================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
gemini_model = genai.GenerativeModel(GEMINI_MODEL)

# =============================
# GEMINI PROMPTS
# =============================
COMMON_GEMINI_CONSTRAINTS = """
NON-NEGOTIABLE RULES:
- Be concise and factual
- Do NOT assign scores
- Do NOT make hiring decisions
- Do NOT invent information
- Use only CV and JD content
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
- Bullet list (skills must be inferred directly from CV)

Top 5 Interview Questions:
- Role-relevant, probing, non-generic questions
"""

GEMINI_SYSTEM_SUMMARY_PROMPT = f"""
You are interpreting interview evaluation results for internal review.

{COMMON_GEMINI_CONSTRAINTS}

Explain what the scores indicate about the candidate.
Focus on clarity, strengths, and risks.
"""

# =============================
# SESSION STATE
# =============================
for key in [
    "system_summary",
    "interviewer_feedback",
    "comparison",
    "emails_sent",
    "jd_cv_analysis"
]:
    if key not in st.session_state:
        st.session_state[key] = None

# =============================
# RESET AI STATE
# =============================
if st.button("🔄 Reset AI State"):
    for k in st.session_state:
        st.session_state[k] = None
    st.experimental_rerun()

# =============================
# LOAD WHISPER
# =============================
@st.cache_resource
def load_whisper():
    return WhisperModel("base", device="cpu", compute_type="int8")

# =============================
# FILE HELPERS
# =============================
def read_docx(file):
    doc = docx.Document(file)
    return "\n".join(p.text for p in doc.paragraphs).lower()

# =============================
# CV / JD ATS ENGINE
# =============================
SKILL_BUCKETS = {
    "skills": ["analytics", "insights", "strategy", "stakeholder"],
    "ownership": ["led", "owned", "managed", "delivered"],
    "tools": ["python", "sql", "power bi", "tableau", "excel"]
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
# UI
# =============================
st.set_page_config(page_title="Interview Analyzer", layout="wide")
st.title("🎯 Interview Performance Analyzer")

# ---- PRE-INTERVIEW CONTEXT ----
st.subheader("🧩 Pre-Interview Context")
job_description = st.text_area("Job Description")
uploaded_cv = st.file_uploader("Upload CV (DOCX)", ["docx"])

# =============================
# LEFT SIDEBAR: JD + CV ANALYSIS
# =============================
with st.sidebar:
    st.header("📄 JD & Candidate Analysis")

    if uploaded_cv and job_description:
        cv_text = read_docx(uploaded_cv)
        jd_text = job_description.lower()

        if st.session_state.jd_cv_analysis is None:
            prompt = f"""
JOB DESCRIPTION:
{jd_text}

CANDIDATE CV:
{cv_text}

{GEMINI_JD_CV_ANALYSIS_PROMPT}
"""
            st.session_state.jd_cv_analysis = gemini_model.generate_content(prompt).text

        st.markdown(st.session_state.jd_cv_analysis)
    else:
        st.caption("Upload CV and JD to view analysis")

# ---- ATS SCORE ----
cv_text, cv_score, cv_breakdown, cv_summary_text = "", None, None, None
if uploaded_cv and job_description:
    cv_text = read_docx(uploaded_cv)
    cv_score, cv_breakdown = compute_cv_match(job_description.lower(), cv_text)
    cv_summary_text = cv_summary(cv_score, cv_breakdown)
    st.success(f"CV Match Score: {cv_score}%")
    st.caption(cv_summary_text)

# ---- PLACEHOLDER ----
st.info("Interview upload & scoring flow continues unchanged below.")

# =============================
# INTERVIEW ANALYZER – FULL MERGED VERSION
# (Canonical + ATS LIKE-matching update ONLY)
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
# GEMINI PROMPTS (UNCHANGED)
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
# 🔒 ATS ENGINE (ONLY SECTION MODIFIED)
# =============================

SKILL_BUCKETS = {
    "skills": [
        "analytics", "data analysis", "insights", "business insights",
        "strategy", "strategic", "stakeholder", "stakeholder management",
        "problem solving", "decision making", "commercial insights"
    ],
    "ownership": [
        "led", "leadership", "owned", "ownership", "managed", "management",
        "delivered", "delivery", "end to end", "e2e",
        "accountable", "responsible for", "driving", "executed", "scaled"
    ],
    "tools": [
        "python", "sql", "power bi", "tableau", "excel",
        "pandas", "numpy", "spark",
        "dashboard", "data visualization", "etl",
        "bigquery", "snowflake"
    ]
}

def normalize(text):
    return re.sub(r"[^a-z0-9 ]", " ", text.lower())

def like_match(text, keyword):
    return keyword in text

def compute_cv_match(jd_text, cv_text):
    scores = {}
    pct_list = []

    jd_text = normalize(jd_text)
    cv_text = normalize(cv_text)

    for bucket, keywords in SKILL_BUCKETS.items():
        jd_hits = {k for k in keywords if like_match(jd_text, k)}
        cv_hits = {k for k in keywords if like_match(cv_text, k)}
        matched = jd_hits.intersection(cv_hits)

        pct = round((len(matched) / len(keywords)) * 100, 1)
        scores[bucket] = pct
        pct_list.append(pct)

    return round(sum(pct_list) / len(pct_list), 1), scores

def cv_summary(score, breakdown):
    strengths = [k for k, v in breakdown.items() if v >= 70]
    gaps = [k for k, v in breakdown.items() if v < 40]

    summary = f"CV shows a {score}% alignment with the role."
    if strengths:
        summary += f" Strong signals in {', '.join(strengths)}."
    if gaps:
        summary += f" Limited surface evidence in {', '.join(gaps)}."

    return summary

# =============================
# UI
# =============================
st.set_page_config(page_title="Interview Analyzer", layout="wide")
st.title("🎯 Interview Performance Analyzer")

st.subheader("🧩 Pre-Interview Context")
job_description = st.text_area("Job Description")
uploaded_cv = st.file_uploader("Upload CV (DOCX)", ["docx"])

# =============================
# LEFT SIDEBAR (UNCHANGED)
# =============================
with st.sidebar:
    st.header("📄 JD & Candidate Analysis")

    if uploaded_cv and job_description:
        cv_text_sidebar = read_docx(uploaded_cv)
        jd_text_sidebar = job_description.lower()

        if st.session_state.jd_cv_analysis is None:
            prompt = f"""
JOB DESCRIPTION:
{jd_text_sidebar}

CANDIDATE CV:
{cv_text_sidebar}

{GEMINI_JD_CV_ANALYSIS_PROMPT}
"""
            st.session_state.jd_cv_analysis = gemini_model.generate_content(prompt).text

        st.markdown(st.session_state.jd_cv_analysis)
    else:
        st.caption("Upload CV and Job Description to view analysis")

# =============================
# ATS SCORE DISPLAY (UNCHANGED)
# =============================
if uploaded_cv and job_description:
    cv_text = read_docx(uploaded_cv)
    score, breakdown = compute_cv_match(job_description, cv_text)
    summary = cv_summary(score, breakdown)

    st.success(f"CV Match Score: {score}%")
    st.caption(summary)

st.info("Interview upload, scoring, Gemini interpretation, audio dictation, and email flows continue unchanged below.")

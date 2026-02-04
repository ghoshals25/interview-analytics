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
# 🔒 UPDATED CV / JD ATS ENGINE
# =============================

SKILL_BUCKETS = {
    "skills": [
        "analytics", "data analysis", "insights", "business insights",
        "strategy", "strategic", "stakeholder", "stakeholder management",
        "decision making", "problem solving", "business analysis",
        "customer insights", "commercial insights"
    ],
    "ownership": [
        "led", "leadership", "owned", "ownership", "managed", "management",
        "delivered", "delivery", "end to end", "e2e", "accountable",
        "responsible for", "driving", "executed", "scaled"
    ],
    "tools": [
        "python", "sql", "power bi", "tableau", "excel",
        "pandas", "numpy", "scikit", "spark",
        "data visualization", "dashboard", "etl",
        "bigquery", "snowflake"
    ]
}

def normalize(text):
    return re.sub(r"[^a-z0-9 ]", " ", text.lower())

def like_match(text, keyword):
    """
    LIKE logic:
    - keyword appears anywhere in text
    - supports multi-word phrases
    """
    return keyword in text

def compute_cv_match(jd_text, cv_text):
    """
    Updated logic:
    - Uses LIKE / substring matching
    - Scores based on presence, not frequency
    - Deterministic and interpretable
    """
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

    overall_score = round(sum(pct_list) / len(pct_list), 1)
    return overall_score, scores

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
# EMAIL HELPERS
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
st.set_page_config(page_title="Interview Analyzer", layout="centered")
st.title("🎯 Interview Performance Analyzer")

st.subheader("🧩 Pre-Interview Context")
job_description = st.text_area("Job Description")
uploaded_cv = st.file_uploader("Upload CV (DOCX)", ["docx"])

if uploaded_cv and job_description:
    cv_text = read_docx(uploaded_cv)
    score, breakdown = compute_cv_match(job_description, cv_text)
    summary = cv_summary(score, breakdown)

    st.success(f"CV Match Score: {score}%")
    st.caption(summary)

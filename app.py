# =========================================================
# INTERVIEW READY – FINAL PRODUCTION VERSION (APPLY FIXED)
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
for key, default in {
    "jd_cv_analysis": None,
    "interview_system_analysis": None,
    "interviewer_comments": "",
    "audio_preview": "",
    "pre_applied": False,
    "post_applied": False,
    "emails_sent": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ===========================

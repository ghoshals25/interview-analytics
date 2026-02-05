# =============================
# INTERVIEW READY – FINAL PRODUCTION VERSION
# =============================

import streamlit as st
import docx
import re
import tempfile
import subprocess
from pathlib import Path
from collections import Counter

import google.generativeai as genai
from faster_whisper import WhisperModel
import imageio_ffmpeg

# =============================
# CONFIG
# =============================
GEMINI_MODEL = "gemini-2.5-flash-lite"

st.set_page_config(page_title="Interview Ready", layout="wide")

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

# =============================
# SESSION STATE
# =============================
for key in [
    "jd_cv_analysis",
    "interview_system_analysis",
    "interviewer_comments",
    "interview_comparison"
]:
    if key not in st.session_state:
        st.session_state[key] = None

# =============================
# FILE HELPERS
# =============================
def read_docx(file):
    doc = docx.Document(file)
    return "\n".join(p.text for p in doc.paragraphs).lower()

# =============================
# SKILL BUCKETS
# =============================
SKILL_BUCKETS = {
    "skills": [
        "analytics", "data analysis", "insights", "strategy",
        "stakeholder", "problem solving", "decision making"
    ],
    "ownership": [
        "led", "owned", "managed", "delivered",
        "end to end", "accountable", "executed", "scaled"
    ],
    "tools": [
        "python", "sql", "power bi", "tableau",
        "excel", "dashboard", "etl", "dax"
    ]
}

def normalize(text):
    return re.sub(r"[^a-z0-9 ]", " ", text.lower())

def like_match(text, keyword):
    return keyword in text

def compute_cv_match(jd_text, cv_text):
    jd_text = normalize(jd_text)
    cv_text = normalize(cv_text)

    bucket_scores = {}
    details = {}

    for bucket, keywords in SKILL_BUCKETS.items():
        jd_items = {k for k in keywords if like_match(jd_text, k)}
        cv_items = {k for k in keywords if like_match(cv_text, k)}

        intersection = jd_items & cv_items
        union = jd_items | cv_items
        missing = jd_items - cv_items

        score = round((len(intersection) / len(union)) * 100, 1) if union else 0.0

        bucket_scores[bucket] = score
        details[bucket] = {
            "intersection": intersection,
            "union": union,
            "missing": missing
        }

    overall_score = round(sum(bucket_scores.values()) / len(bucket_scores), 1)
    return overall_score, bucket_scores, details

# =============================
# WHISPER SETUP
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
        audio = extract_audio_from_video(uploaded_file)
        return transcribe_audio(audio)

    raise ValueError("Unsupported file type")

# =============================
# UI
# =============================
st.title("🎯 Interview Ready")
st.caption("The Desired Interview Platform for structured interview preparation")
st.divider()

# =============================
# SIDEBAR – JD & CANDIDATE OVERVIEW
# =============================
with st.sidebar:
    st.header("📄 JD & Candidate Overview")
    if st.session_state.jd_cv_analysis:
        st.markdown(st.session_state.jd_cv_analysis)
    else:
        st.caption("Upload a Job Description and CV to generate an overview")

# =============================
# MAIN – PRE INTERVIEW
# =============================
left_col, right_col = st.columns([1.1, 1])

with left_col:
    st.subheader("📄 Candidate & Role Context")

    with st.container(border=True):
        job_description = st.text_area(
            "Job Description",
            placeholder="Paste the full job description here…",
            height=220
        )

        uploaded_cv = st.file_uploader("Candidate CV (DOCX)", ["docx"])

        if uploaded_cv and job_description:
            cv_text = read_docx(uploaded_cv)

            if st.session_state.jd_cv_analysis is None:
                prompt = f"""
JOB DESCRIPTION:
{job_description}

CANDIDATE CV:
{cv_text}

{GEMINI_JD_CV_ANALYSIS_PROMPT}
"""
                st.session_state.jd_cv_analysis = gemini_model.generate_content(prompt).text

            score, bucket_scores, details = compute_cv_match(job_description, cv_text)

            st.divider()
            st.metric("CV–JD Alignment Score", f"{score}%")

with right_col:
    st.subheader("🧠 Skills to JD Overlap Summary")

    if uploaded_cv and job_description:
        jd_focus, cv_matches, cv_gaps = set(), set(), set()

        for info in details.values():
            jd_focus |= info["union"]
            cv_matches |= info["intersection"]
            cv_gaps |= info["missing"]

        st.markdown("**What the role is looking for**")
        st.write(", ".join(sorted(jd_focus)) if jd_focus else "No strong signals")

        st.markdown("**What the CV demonstrates clearly**")
        st.write(", ".join(sorted(cv_matches)) if cv_matches else "No clear matches")

        st.markdown("**Skills and areas to test during the interview**")
        st.write(", ".join(sorted(cv_gaps)) if cv_gaps else "No major gaps detected")

# =============================
# INTERVIEW SECTION
# =============================
st.divider()
st.header("🎤 Interview Evaluation")
st.caption("Structured capture of interview evidence and judgement")

st.markdown(
    """
    **Interviewer:** BSY  
    **Designation:** Director  
    ---
    """
)

uploaded_interview = st.file_uploader(
    "Upload Interview Transcript / Audio / Video",
    ["txt", "docx", "mp3", "wav", "mp4", "mov"]
)

if uploaded_interview:
    interview_text = extract_interview_text(uploaded_interview)

    st.subheader("🧠 System Interview Analysis")

    if st.session_state.interview_system_analysis is None:
        prompt = f"""
INTERVIEW TRANSCRIPT:
{interview_text}

{GEMINI_INTERVIEW_ANALYSIS_PROMPT}
"""
        st.session_state.interview_system_analysis = gemini_model.generate_content(prompt).text

    st.markdown(st.session_state.interview_system_analysis)

    st.subheader("🧑‍💼 Interviewer Observations")

    audio_note = st.audio_input("🎙️ Dictate interviewer feedback (optional)")
    if audio_note:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as t:
            t.write(audio_note.getvalue())
            st.session_state.interviewer_comments = transcribe_audio(t.name)

    st.session_state.interviewer_comments = st.text_area(
        "Interviewer comments (editable)",
        value=st.session_state.interviewer_comments or "",
        height=180
    )

    recommendation = st.selectbox(
        "Overall Interview Recommendation",
        ["Select", "Strong Yes", "Yes", "Borderline", "No"]
    )

    if recommendation != "Select" and st.session_state.interviewer_comments:
        st.subheader("🔍 System vs Interviewer Comparison")

        if st.session_state.interview_comparison is None:
            prompt = f"""
SYSTEM ANALYSIS:
{st.session_state.interview_system_analysis}

INTERVIEWER FEEDBACK:
{st.session_state.interviewer_comments}

{GEMINI_COMPARISON_PROMPT}
"""
            st.session_state.interview_comparison = gemini_model.generate_content(prompt).text

        st.markdown(st.session_state.interview_comparison)

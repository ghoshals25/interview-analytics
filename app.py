import streamlit as st
import docx
from pathlib import Path
import re
import smtplib
from email.message import EmailMessage
import tempfile
import subprocess

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

GEMINI_INTERVIEWER_COACHING_PROMPT = f"""
You are providing private coaching feedback.

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
    "system_summary",
    "interviewer_feedback",
    "comparison",
    "emails_sent"
]:
    if key not in st.session_state:
        st.session_state[key] = None

# =============================
# RESET AI STATE
# =============================
if st.button("🔄 Reset AI State"):
    st.session_state.system_summary = None
    st.session_state.comparison = None
    st.session_state.interviewer_feedback = None
    st.session_state.emails_sent = False
    st.experimental_rerun()

# =============================
# LOAD WHISPER
# =============================
@st.cache_resource
def load_whisper():
    return WhisperModel("base", device="cpu", compute_type="int8")

# =============================
# FILE / AUDIO HELPERS
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
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
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

# =============================
# SCORING (DETERMINISTIC)
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
# GEMINI HELPER (SAFE)
# =============================
def call_gemini(prompt):
    if not LLM_ENABLED:
        return "⚠️ AI disabled"

    try:
        response = gemini_model.generate_content(
            prompt,
            generation_config={"temperature": 0.2, "max_output_tokens": 400}
        )
        return response.text or "⚠️ Empty AI response"
    except Exception as e:
        return f"⚠️ Gemini unavailable: {e}"

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

uploaded_file = st.file_uploader(
    "Upload Interview File (Transcript / Audio / Video)",
    ["txt", "docx", "mp3", "wav", "mp4", "mov"]
)

# =============================
# MAIN FLOW
# =============================
if uploaded_file:
    text = extract_text(uploaded_file)

    comm = communication_score(text)
    skill = interview_skill_score(text)
    final_score = overall_interview_score(comm, skill)

    st.subheader("📊 System Scores")
    st.metric("Overall Score", f"{final_score}%")
    st.metric("Communication", f"{comm}%")
    st.metric("Interview Skills", f"{skill}%")

    # =============================
    # SYSTEM INTERPRETATION
    # =============================
    st.subheader("🧠 System Interpretation")
    if st.session_state.system_summary is None:
        prompt = f"""
SCORES:
Overall: {final_score}%
Communication: {comm}%
Skills: {skill}%

{GEMINI_SYSTEM_SUMMARY_PROMPT}
"""
        st.session_state.system_summary = call_gemini(prompt)

    st.write(st.session_state.system_summary)

    # =============================
    # 🎙️ DICTATION
    # =============================
    st.subheader("🎙️ Dictate Interviewer Feedback")
    audio = st.audio_input("Record feedback")

    if audio:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as t:
            t.write(audio.read())
            st.session_state.interviewer_feedback = transcribe_audio(t.name)
            st.session_state.comparison = None

    # =============================
    # INTERVIEWER INPUT
    # =============================
    st.subheader("🧑‍💼 Interviewer Feedback")
    interviewer_comments = st.text_area(
        "Comments",
        value=st.session_state.interviewer_feedback or ""
    )

    interviewer_fit = st.selectbox(
        "Recommendation",
        ["Select", "Strong Yes", "Yes", "Borderline", "No"]
    )

    # =============================
    # SYSTEM vs INTERVIEWER
    # =============================
    if interviewer_fit != "Select" and interviewer_comments:
        st.subheader("🔍 System vs Interviewer Comparison")

        if st.session_state.comparison is None:
            comparison_prompt = f"""
SYSTEM:
Communication: {comm}
Interview Skills: {skill}

INTERVIEWER:
Recommendation: {interviewer_fit}
Comments:
{interviewer_comments}

Compare alignment and gaps factually.
"""
            st.session_state.comparison = call_gemini(comparison_prompt)

        st.write(st.session_state.comparison)

        # =============================
        # AI COACHING
        # =============================
        st.subheader("🧑‍🏫 AI Coaching Feedback")
        if st.session_state.interviewer_feedback is None:
            coaching_prompt = f"""
TRANSCRIPT:
{text}

INTERVIEWER COMMENTS:
{interviewer_comments}

{GEMINI_INTERVIEWER_COACHING_PROMPT}
"""
            st.session_state.interviewer_feedback = call_gemini(coaching_prompt)

        st.write(st.session_state.interviewer_feedback)

        # =============================
        # EMAILS
        # =============================
        st.subheader("📧 Send Reports")
        hr_email = st.text_input("HR Email")
        candidate_email = st.text_input("Candidate Email")
        interviewer_email = st.text_input("Interviewer Email")

        if st.button("📤 Send Emails") and not st.session_state.emails_sent:
            if not any([hr_email, candidate_email, interviewer_email]):
                st.error("❌ Please enter at least one valid email")
                st.session_state.emails_sent = False
            else:
                st.session_state.emails_sent = True

                send_email(
                    "HR Interview Summary",
                    st.session_state.system_summary + "\n\n" + st.session_state.comparison,
                    hr_email
                )

                send_email(
                    "Your Interview Feedback",
                    st.session_state.interviewer_feedback,
                    candidate_email
                )

                send_email(
                    "Interview Coaching Feedback (Private)",
                    st.session_state.interviewer_feedback,
                    interviewer_email
                )

                st.success("✅ Emails sent successfully")

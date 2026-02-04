import streamlit as st
import docx
from pathlib import Path
import re
import smtplib
from email.message import EmailMessage
import tempfile
import subprocess

from faster_whisper import WhisperModel
import imageio_ffmpeg
import google.generativeai as genai

# =============================
# CONFIG
# =============================
SENDER_EMAIL = "soumikghoshalireland@gmail.com"
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

LLM_ENABLED = True

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

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
# RESET AI STATE (SAFE)
# =============================
if st.button("🔄 Reset AI State"):
    st.session_state.system_summary = None
    st.session_state.comparison = None
    st.experimental_rerun()

# =============================
# LOAD FASTER-WHISPER
# =============================
@st.cache_resource
def load_whisper_model():
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

def transcribe_audio(audio_path):
    model = load_whisper_model()
    segments, _ = model.transcribe(audio_path)
    return " ".join(segment.text for segment in segments).lower()

def extract_audio_from_video(uploaded_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as video_tmp:
        video_tmp.write(uploaded_file.read())
        video_path = video_tmp.name

    audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    ffmpeg_binary = imageio_ffmpeg.get_ffmpeg_exe()

    subprocess.run(
        [ffmpeg_binary, "-y", "-i", video_path, "-ac", "1", "-ar", "16000", audio_path],
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
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.read())
            return transcribe_audio(tmp.name)
    if suffix in [".mp4", ".mov"]:
        audio_path = extract_audio_from_video(uploaded_file)
        return transcribe_audio(audio_path)
    raise ValueError("Unsupported file format")

# =============================
# SCORING (UNCHANGED)
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
# GEMINI CALL (FIXED)
# =============================
def gemini_generate(prompt):
    response = gemini_model.generate_content(prompt)
    if not response or not response.text:
        raise RuntimeError("Empty Gemini response")
    return response.text

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
    "Upload Interview File (Transcript, Audio, or Video)",
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
    # SYSTEM INTERPRETATION (AI)
    # =============================
    st.subheader("🧠 System Interpretation")
    if st.session_state.system_summary is None:
        try:
            st.session_state.system_summary = gemini_generate(
                f"""
Interpret these interview scores professionally.
Do NOT recommend hire/no-hire.

Communication: {comm}
Interview Skills: {skill}
"""
            )
        except Exception as e:
            st.warning(f"Gemini unavailable: {e}")

    if st.session_state.system_summary:
        st.write(st.session_state.system_summary)

    # =============================
    # 🎙️ DICTATION
    # =============================
    st.subheader("🎙️ Dictate Interviewer Feedback")
    audio_file = st.audio_input("Click to record your feedback")

    if audio_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_file.read())
            audio_path = tmp.name
        st.session_state.interviewer_feedback = transcribe_audio(audio_path)

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
            try:
                st.session_state.comparison = gemini_generate(
                    f"""
Compare system evaluation and interviewer feedback.
Be neutral and factual.

System:
Communication: {comm}
Interview Skills: {skill}

Interviewer Feedback:
{interviewer_comments}
"""
                )
            except Exception as e:
                st.warning(f"Gemini unavailable: {e}")

        if st.session_state.comparison:
            st.write(st.session_state.comparison)

        # =============================
        # AI COACHING
        # =============================
        st.subheader("🧑‍🏫 AI Coaching Feedback")
        try:
            ai_coaching = gemini_generate(
                f"""
You are a career coach.
Give constructive, actionable feedback to the candidate.
Do not mention scores or hiring decisions.

Interviewer Comments:
{interviewer_comments}
"""
            )
            st.write(ai_coaching)
        except Exception as e:
            st.warning(f"Gemini unavailable: {e}")

        # =============================
        # EMAILS
        # =============================
        st.subheader("📧 Send Reports")
        hr_email = st.text_input("HR Email")
        candidate_email = st.text_input("Candidate Email")
        interviewer_email = st.text_input("Interviewer Email")

        if st.button("📤 Send Emails") and not st.session_state.emails_sent:
            st.session_state.emails_sent = True

            send_email(
                "HR Interview Summary",
                (st.session_state.system_summary or "") + "\n\n" + (st.session_state.comparison or ""),
                hr_email
            )

            send_email(
                "Your Interview Feedback",
                ai_coaching,
                candidate_email
            )

            send_email(
                "Interview Coaching Feedback (Private)",
                ai_coaching,
                interviewer_email
            )

            st.success("✅ Emails sent successfully")

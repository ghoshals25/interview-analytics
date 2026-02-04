import os
import imageio_ffmpeg

# Inject ffmpeg into PATH first
ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
os.environ["PATH"] = os.path.dirname(ffmpeg_path) + os.pathsep + os.environ.get("PATH", "")

import streamlit as st
import docx
from pathlib import Path
import re
import smtplib
from email.message import EmailMessage
import tempfile
import subprocess

import whisper

# =============================
# CONSTANTS
# =============================
SENDER_EMAIL = "soumikghoshalireland@gmail.com"
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

# Gemini / GenAI fully disabled
LLM_ENABLED = False

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
# LOAD WHISPER MODEL (CACHED)
# =============================
@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base")

# =============================
# READ TEXT TRANSCRIPT
# =============================
def read_transcript(uploaded_file):
    suffix = Path(uploaded_file.name).suffix.lower()

    if suffix == ".docx":
        doc = docx.Document(uploaded_file)
        return "\n".join(p.text for p in doc.paragraphs).lower()

    return uploaded_file.read().decode("utf-8", errors="ignore").lower()

# =============================
# TRANSCRIBE AUDIO
# =============================
def transcribe_audio(audio_path):
    model = load_whisper_model()
    result = model.transcribe(audio_path)
    return result["text"].lower()

# =============================
# EXTRACT AUDIO FROM VIDEO (FIXED)
# =============================
def extract_audio_from_video(uploaded_file):
    # Save uploaded video
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as video_tmp:
        video_tmp.write(uploaded_file.read())
        video_path = video_tmp.name

    # Output audio path
    audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name

    # Get bundled ffmpeg binary
    ffmpeg_binary = imageio_ffmpeg.get_ffmpeg_exe()

    # Run ffmpeg directly (Streamlit Cloud safe)
    subprocess.run(
        [
            ffmpeg_binary,
            "-y",                 # overwrite
            "-i", video_path,     # input video
            "-ac", "1",           # mono
            "-ar", "16000",       # 16kHz
            audio_path
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return audio_path

# =============================
# NORMALIZE INPUT → TEXT
# =============================
def extract_text(uploaded_file):
    suffix = Path(uploaded_file.name).suffix.lower()

    if suffix in [".txt", ".docx"]:
        return read_transcript(uploaded_file)

    if suffix in [".mp3", ".wav"]:
        st.info("Audio interviews are transcribed automatically before analysis.")
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.read())
            return transcribe_audio(tmp.name)

    if suffix in [".mp4", ".mov"]:
        st.info("Video interviews are converted to audio and transcribed automatically.")
        audio_path = extract_audio_from_video(uploaded_file)
        return transcribe_audio(audio_path)

    raise ValueError("Unsupported file format")

# =============================
# ANALYSIS LOGIC (UNCHANGED)
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
# EMAIL HELPERS
# =============================
def is_valid_email(email):
    return email and re.match(EMAIL_REGEX, email)

def send_email(subject, body, recipient):
    if not is_valid_email(recipient):
        st.warning(f"⚠️ Skipping invalid email: {recipient}")
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
# STREAMLIT UI
# =============================
st.set_page_config(page_title="Interview Analyzer", layout="centered")
st.title("🎯 Interview Performance Analyzer")

uploaded_file = st.file_uploader(
    "Upload Interview File (Transcript, Audio, or Video)",
    ["txt", "docx", "mp3", "wav", "mp4", "mov"]
)

# =============================
# MAIN PIPELINE
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

    if st.session_state.system_summary is None:
        st.session_state.system_summary = "System-generated scores based on deterministic rules."

    st.subheader("🧠 System Interpretation")
    st.write(st.session_state.system_summary)

    st.subheader("🧑‍💼 Interviewer Feedback")
    interviewer_comments = st.text_area("Comments")
    interviewer_fit = st.selectbox(
        "Recommendation",
        ["Select", "Strong Yes", "Yes", "Borderline", "No"]
    )

    if interviewer_fit != "Select" and interviewer_comments:
        if st.session_state.comparison is None:
            st.session_state.comparison = "Comparison based on system scores and interviewer judgment."

        st.subheader("🔍 System vs Interviewer Comparison")
        st.write(st.session_state.comparison)

        if st.session_state.interviewer_feedback is None:
            st.session_state.interviewer_feedback = "Interviewer coaching feedback unavailable (AI disabled)."

        st.subheader("🧑‍🏫 Interviewer Coaching (Preview)")
        st.write(st.session_state.interviewer_feedback)

        st.subheader("📧 Send Reports")
        hr_email = st.text_input("HR Email")
        candidate_email = st.text_input("Candidate Email")
        interviewer_email = st.text_input("Interviewer Email")

        if st.button("📤 Send Emails") and not st.session_state.emails_sent:
            if not any([hr_email, candidate_email, interviewer_email]):
                st.error("❌ Please enter at least one valid email address")
                st.stop()

            st.session_state.emails_sent = True

            send_email(
                "HR Interview Summary",
                st.session_state.system_summary + "\n\n" + st.session_state.comparison,
                hr_email
            )

            send_email(
                "Your Interview Feedback",
                "Thank you for interviewing. You will hear back soon.",
                candidate_email
            )

            send_email(
                "Interview Coaching Feedback (Private)",
                st.session_state.interviewer_feedback,
                interviewer_email
            )

            st.success("✅ Emails sent successfully")

import streamlit as st
import docx
from pathlib import Path
import re
import tempfile
import re as regex
import requests

import google.generativeai as genai

# =============================
# CONSTANTS
# =============================
EMAIL_SENDER = "Soumik <onboarding@resend.dev>"

# =============================
# GEMINI CONFIG (FREE TIER SAFE)
# =============================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite")

# =============================
# SESSION STATE
# =============================
if "ai_feedback" not in st.session_state:
    st.session_state.ai_feedback = None
    st.session_state.ai_attempted = False

# =============================
# READ TRANSCRIPT
# =============================
def read_transcript(uploaded_file) -> str:
    suffix = Path(uploaded_file.name).suffix.lower()

    if suffix == ".docx":
        doc = docx.Document(uploaded_file)
        return "\n".join(p.text for p in doc.paragraphs).lower()

    elif suffix == ".txt":
        return uploaded_file.read().decode("utf-8", errors="ignore").lower()

    else:
        raise ValueError("Unsupported file format")

# =============================
# COMMUNICATION ANALYSIS
# =============================
FILLER_WORDS = ["um", "uh", "like", "you know", "basically", "sort of", "kind of"]

def communication_score(text: str) -> float:
    words = text.split()
    sentences = [s for s in re.split(r"[.!?]", text) if s.strip()]

    filler_count = sum(text.count(f) for f in FILLER_WORDS)
    avg_sentence_length = len(words) / max(len(sentences), 1)

    filler_penalty = min(filler_count / 12, 1)
    ramble_penalty = 0.3 if avg_sentence_length > 25 else 0

    score = 1 - (filler_penalty + ramble_penalty)
    return round(max(min(score, 1), 0) * 100, 2)

# =============================
# INTERVIEW SKILLS
# =============================
EXAMPLE_PHRASES = ["for example", "for instance", "when i", "i worked on", "i was responsible for"]
IMPACT_WORDS = ["%", "percent", "increased", "reduced", "improved", "delivered", "impact"]
PROBLEM_WORDS = ["problem", "challenge", "solution", "approach", "resolved"]

def interview_skill_score(text: str) -> float:
    score = 0
    if any(p in text for p in EXAMPLE_PHRASES): score += 0.3
    if any(p in text for p in IMPACT_WORDS): score += 0.35
    if any(p in text for p in PROBLEM_WORDS): score += 0.35
    return round(min(score, 1) * 100, 2)

# =============================
# PERSONALITY SIGNALS
# =============================
PERSONALITY_SIGNALS = {
    "Confidence": ["i led", "i owned", "i decided", "i drove"],
    "Collaboration": ["we", "team", "stakeholder"],
    "Growth Mindset": ["learned", "improved", "iterated"],
    "Uncertainty": ["maybe", "i think", "sort of"]
}

def personality_analysis(text: str):
    results = {}
    for trait, phrases in PERSONALITY_SIGNALS.items():
        count = sum(text.count(p) for p in phrases)
        results[trait] = "High" if count >= 3 else "Medium" if count else "Low"
    return results

# =============================
# FINAL SCORE
# =============================
def overall_interview_score(comm, skill, personality):
    personality_score = sum(
        1 if v == "High" else 0.5 if v == "Medium" else 0
        for v in personality.values()
    ) / len(personality)

    return round(
        skill * 0.40 +
        comm * 0.35 +
        personality_score * 100 * 0.25,
        2
    )

# =============================
# AI FEEDBACK
# =============================
def generate_ai_feedback(summary: dict) -> str:
    prompt = f"""
You are an experienced interview coach.

Based on the analysis below, provide:
1. Overall assessment (2–3 sentences)
2. 2–3 strengths
3. 2 concrete, actionable improvements

Interview Analysis:
- Communication: {summary['communication_score']}%
- Interview Skills: {summary['skill_score']}%
- Personality: {summary['personality']}
- Strong signals: {summary['strong_signals']}
- Weak signals: {summary['weak_signals']}
"""

    response = gemini_model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.3,
            "max_output_tokens": 400
        }
    )
    return response.text

# =============================
# TEXT REPORT GENERATION
# =============================
def generate_feedback_text(summary: dict, ai_feedback: str) -> str:
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    path = temp_file.name

    with open(path, "w") as f:
        f.write("INTERVIEW PERFORMANCE REPORT\n")
        f.write("=" * 32 + "\n\n")
        f.write(f"Overall Score: {summary['final_score']}%\n\n")

        f.write("Scores:\n")
        f.write(f"- Communication: {summary['communication_score']}%\n")
        f.write(f"- Interview Skills: {summary['skill_score']}%\n\n")

        f.write("Personality Signals:\n")
        for k, v in summary["personality"].items():
            f.write(f"- {k}: {v}\n")

        f.write("\nAI Coach Feedback:\n")
        f.write(ai_feedback)

    return path

# =============================
# EMAIL VIA RESEND
# =============================
def send_email_to_user(file_path: str, user_email: str):
    with open(file_path, "r") as f:
        content = f.read()

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {st.secrets['RESEND_API_KEY']}",
            "Content-Type": "application/json"
        },
        json={
            "from": EMAIL_SENDER,
            "to": user_email,
            "subject": "Your Interview Feedback Report",
            "text": content
        }
    )

    if response.status_code != 200:
        raise Exception(f"Resend error: {response.text}")

# =============================
# EMAIL VALIDATION
# =============================
def is_valid_email(email: str) -> bool:
    return regex.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email) is not None

# =============================
# STREAMLIT UI
# =============================
st.set_page_config(page_title="Interview Analyzer", layout="centered")
st.title("🎯 Interview Performance Analyzer")

uploaded_file = st.file_uploader(
    "Upload Interview Transcript (.txt or .docx)",
    type=["txt", "docx"]
)

if uploaded_file:
    text = read_transcript(uploaded_file)

    comm = communication_score(text)
    skill = interview_skill_score(text)
    personality = personality_analysis(text)
    final_score = overall_interview_score(comm, skill, personality)

    strong = [k for k in IMPACT_WORDS + EXAMPLE_PHRASES + PROBLEM_WORDS if k in text][:5]
    weak = [k for k in FILLER_WORDS + PERSONALITY_SIGNALS["Uncertainty"] if k in text][:5]

    st.subheader("📊 Scores")
    st.progress(final_score / 100)
    st.caption(f"Overall Score: {final_score}%")
    st.metric("Communication", f"{comm}%")
    st.metric("Interview Skills", f"{skill}%")

    st.subheader("🧠 Personality Signals")
    for k, v in personality.items():
        st.write(f"**{k}**: {v}")

    st.subheader("🤖 AI Interview Coach Feedback")

    if not st.session_state.ai_attempted:
        st.session_state.ai_attempted = True
        with st.spinner("Generating AI feedback..."):
            st.session_state.ai_feedback = generate_ai_feedback({
                "communication_score": comm,
                "skill_score": skill,
                "personality": personality,
                "strong_signals": strong,
                "weak_signals": weak
            })

    if st.session_state.ai_feedback:
        st.write(st.session_state.ai_feedback)

        st.subheader("📧 Email this report to me")
        user_email = st.text_input("Enter your email address")

        if st.button("Send Email"):
            if not is_valid_email(user_email):
                st.error("Please enter a valid email address.")
            else:
                with st.spinner("Sending email..."):
                    report_path = generate_feedback_text(
                        summary={
                            "communication_score": comm,
                            "skill_score": skill,
                            "personality": personality,
                            "final_score": final_score
                        },
                        ai_feedback=st.session_state.ai_feedback
                    )
                    send_email_to_user(report_path, user_email)
                    st.success(f"Report sent to {user_email} 📬")

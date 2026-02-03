import streamlit as st
import docx
from pathlib import Path
import re
import smtplib
from email.message import EmailMessage
import re as regex
import google.generativeai as genai

# =============================
# CONSTANTS
# =============================
SENDER_EMAIL = "soumikghoshalireland@gmail.com"
LLM_ENABLED = True

# =============================
# GEMINI CONFIG
# =============================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite")

# =============================
# 🔹 ADDED: GEMINI PROMPTS (ALL PERSONAS)
# =============================

COMMON_GEMINI_CONSTRAINTS = """
NON-NEGOTIABLE RULES:
- Do NOT assign scores or numeric evaluations
- Do NOT make hire / no-hire decisions
- Do NOT invent skills or experiences
- Base insights strictly on transcript & signals
- Be concise and evidence-based
"""

GEMINI_HR_PROMPT = f"""
You are generating a concise interview summary for HR.

{COMMON_GEMINI_CONSTRAINTS}

FORMAT:
- Key Strengths
- Key Concerns
- Readiness Indicators
- Suggested Next Steps

Use bullets only.
"""

GEMINI_CANDIDATE_PROMPT = f"""
You are generating respectful, growth-oriented feedback for a candidate.

{COMMON_GEMINI_CONSTRAINTS}

FORMAT:
- Strengths Observed
- Areas to Improve
- Suggestions for Growth

Avoid judgmental language.
"""

GEMINI_INTERVIEWER_PROMPT = f"""
You are generating private interviewer feedback.

{COMMON_GEMINI_CONSTRAINTS}

FORMAT:
### Interview Summary
### System Feedback (Candidate Signals)
### Interview Improvements

Use bullets only.
"""

# =============================
# SESSION STATE
# =============================
if "ai_feedback" not in st.session_state:
    st.session_state.ai_feedback = None
    st.session_state.ai_attempted = False

if "emails_sent" not in st.session_state:
    st.session_state.emails_sent = False

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
# 🔹 ADDED: GEMINI FEEDBACK HELPERS
# =============================
@st.cache_data(show_spinner=False)
def call_gemini(prompt):
    if not LLM_ENABLED:
        return "LLM disabled"
    return gemini_model.generate_content(
        prompt,
        generation_config={"temperature": 0.2, "max_output_tokens": 300}
    ).text

# =============================
# AI FEEDBACK (UNCHANGED FLOW)
# =============================
@st.cache_data(show_spinner=False)
def generate_ai_feedback(summary: dict) -> str:
    return call_gemini(GEMINI_CANDIDATE_PROMPT)

# =============================
# SYSTEM vs INTERVIEWER COMPARISON
# =============================
@st.cache_data(show_spinner=False)
def generate_comparison_report(
    final_score, comm, skill, personality, ai_feedback, interviewer_comments, interviewer_fit
):
    prompt = f"""
SYSTEM:
Overall: {final_score}%
Communication: {comm}%
Skills: {skill}%
Personality: {personality}

AI Feedback:
{ai_feedback}

INTERVIEWER:
Recommendation: {interviewer_fit}
Comments: {interviewer_comments}

Compare alignment and gaps.
"""
    return call_gemini(prompt)

# =============================
# EMAIL BUILDERS (UNCHANGED)
# =============================
def build_hr_email(final_score, comm, skill, personality, ai_feedback, interviewer_comments, interviewer_fit, comparison):
    return f"""
SYSTEM SUMMARY
Overall: {final_score}%
Communication: {comm}%
Skills: {skill}%
Personality: {personality}

AI FEEDBACK
{ai_feedback}

INTERVIEWER INPUT
Recommendation: {interviewer_fit}
Comments: {interviewer_comments}

SYSTEM vs INTERVIEWER
{comparison}
"""

def build_candidate_email(strengths, weaknesses):
    return f"""
Strengths:
- {', '.join(strengths)}

Areas to Improve:
- {', '.join(weaknesses)}

Next Step:
Practice structured answers and quantify impact.
"""

# =============================
# EMAIL HELPERS
# =============================
def send_email(subject, body, recipient):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = recipient
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, st.secrets["EMAIL_APP_PASSWORD"])
        server.send_message(msg)

# =============================
# STREAMLIT UI (UNCHANGED)
# =============================
st.set_page_config(page_title="Interview Analyzer", layout="centered")
st.title("🎯 Interview Performance Analyzer")

uploaded_file = st.file_uploader("Upload Interview Transcript (.txt or .docx)", ["txt", "docx"])

if uploaded_file:
    text = read_transcript(uploaded_file)

    comm = communication_score(text)
    skill = interview_skill_score(text)
    personality = personality_analysis(text)
    final_score = overall_interview_score(comm, skill, personality)

    st.subheader("📊 Scores")
    st.progress(final_score / 100)
    st.caption(f"Overall Score: {final_score}%")
    st.metric("Communication", f"{comm}%")
    st.metric("Interview Skills", f"{skill}%")

    st.subheader("🧠 Personality Signals")
    for k, v in personality.items():
        st.write(f"**{k}**: {v}")

    strong = [k for k in IMPACT_WORDS + EXAMPLE_PHRASES + PROBLEM_WORDS if k in text][:5]
    weak = [k for k in FILLER_WORDS + PERSONALITY_SIGNALS["Uncertainty"] if k in text][:5]

    if not st.session_state.ai_attempted:
        st.session_state.ai_attempted = True
        st.session_state.ai_feedback = generate_ai_feedback({})

    st.subheader("🤖 AI Interview Coach Feedback")
    st.write(st.session_state.ai_feedback)

    st.subheader("🧑‍💼 Interviewer Evaluation")
    interviewer_comments = st.text_area("Comments")
    interviewer_fit = st.selectbox("Recommendation", ["Select", "Strong Yes", "Yes", "Borderline", "No"])

    if interviewer_fit != "Select":
        comparison = generate_comparison_report(
            final_score, comm, skill, personality,
            st.session_state.ai_feedback,
            interviewer_comments,
            interviewer_fit
        )

        st.subheader("🔍 System vs Interviewer Comparison")
        st.write(comparison)

        hr_email = st.text_input("HR Email")
        candidate_email = st.text_input("Candidate Email")

        if st.button("📤 Send Interview Reports") and not st.session_state.emails_sent:
            st.session_state.emails_sent = True

            send_email(
                "HR Interview Summary",
                build_hr_email(final_score, comm, skill, personality,
                               st.session_state.ai_feedback,
                               interviewer_comments,
                               interviewer_fit,
                               comparison),
                hr_email
            )

            send_email(
                "Your Interview Feedback & Next Steps",
                build_candidate_email(strong, weak),
                candidate_email
            )

            st.success("✅ Emails sent successfully")

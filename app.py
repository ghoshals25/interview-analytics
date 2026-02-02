import streamlit as st
import docx
from pathlib import Path
import re
from groq import Groq

# =============================
# GROQ CLIENT (FREE TIER)
# =============================
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# =============================
# SESSION STATE GUARD
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
FILLER_WORDS = [
    "um", "uh", "like", "you know",
    "basically", "sort of", "kind of"
]

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
EXAMPLE_PHRASES = [
    "for example", "for instance",
    "when i", "i worked on", "i was responsible for"
]

IMPACT_WORDS = [
    "%", "percent", "increased",
    "reduced", "improved", "delivered", "impact"
]

PROBLEM_WORDS = [
    "problem", "challenge", "solution",
    "approach", "resolved"
]

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
# EVIDENCE EXTRACTION
# =============================
def extract_keyword_hits(text, keywords, max_hits=5):
    return [k for k in keywords if k in text][:max_hits]

SIGNAL_EXPLANATIONS = {
    "percent": "Shows quantified impact",
    "reduced": "Demonstrates efficiency",
    "improved": "Continuous improvement",
    "impact": "Outcome-focused language",
    "for example": "Structured explanation",
    "um": "Verbal filler",
    "like": "Informal filler",
    "maybe": "Signals uncertainty"
}

# =============================
# GENAI (GROQ)
# =============================
def generate_ai_feedback(summary: dict) -> str:
    prompt = f"""
You are an experienced interview coach.

Provide:
1. Overall assessment (2–3 sentences)
2. 2–3 strengths
3. 2 actionable improvements

Interview Analysis:
- Communication: {summary['communication_score']}%
- Interview Skills: {summary['skill_score']}%
- Personality: {summary['personality']}
- Strong signals: {summary['strong_signals']}
- Weak signals: {summary['weak_signals']}
"""

    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {"role": "system", "content": "You are a helpful interview coach."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4
    )

    return response.choices[0].message.content.strip()

# =============================
# STREAMLIT UI
# =============================
st.set_page_config("Interview Analyzer", layout="centered")
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

    strong = extract_keyword_hits(text, IMPACT_WORDS + EXAMPLE_PHRASES + PROBLEM_WORDS)
    weak = extract_keyword_hits(text, FILLER_WORDS + PERSONALITY_SIGNALS["Uncertainty"])

    # Scores
    st.subheader("📊 Scores")
    st.progress(final_score / 100)
    st.caption(f"Overall Score: {final_score}%")
    st.metric("Communication", f"{comm}%")
    st.metric("Interview Skills", f"{skill}%")

    # Personality
    st.subheader("🧠 Personality Signals")
    for k, v in personality.items():
        st.write(f"**{k}**: {v}")

    # Evidence
    st.subheader("🔍 Evidence from Your Answers")
    for s in strong:
        st.write(f"✅ **{s}** — {SIGNAL_EXPLANATIONS.get(s, '')}")
    for w in weak:
        st.write(f"⚠️ **{w}** — {SIGNAL_EXPLANATIONS.get(w, '')}")

    # AI Feedback (single-call only)
    st.subheader("🤖 AI Interview Coach Feedback")

    if not st.session_state.ai_attempted:
        st.session_state.ai_attempted = True
        try:
            with st.spinner("Generating AI feedback..."):
                st.session_state.ai_feedback = generate_ai_feedback({
                    "communication_score": comm,
                    "skill_score": skill,
                    "personality": personality,
                    "strong_signals": strong,
                    "weak_signals": weak
                })
        except Exception:
            st.session_state.ai_feedback = None

    if st.session_state.ai_feedback:
        st.write(st.session_state.ai_feedback)
    else:
        st.warning("AI feedback temporarily unavailable (free API limit). Try again later.")

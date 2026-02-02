import streamlit as st
import docx
from pathlib import Path
import re

# =============================
# READ TRANSCRIPT
# =============================
def read_transcript(uploaded_file) -> str:
    suffix = Path(uploaded_file.name).suffix.lower()

    if suffix == ".docx":
        doc = docx.Document(uploaded_file)
        text = "\n".join(p.text for p in doc.paragraphs)
        return text.lower()

    elif suffix == ".txt":
        return uploaded_file.read().decode("utf-8", errors="ignore").lower()

    else:
        raise ValueError("Unsupported file format")

# =============================
# COMMUNICATION ANALYSIS
# =============================
FILLER_WORDS = [
    "um", "uh", "like", "you know", "basically",
    "sort of", "kind of"
]

def communication_score(text: str) -> float:
    words = text.split()
    sentences = re.split(r"[.!?]", text)
    sentences = [s for s in sentences if s.strip()]

    filler_count = sum(text.count(f) for f in FILLER_WORDS)
    avg_sentence_length = len(words) / max(len(sentences), 1)

    filler_penalty = min(filler_count / 12, 1)
    ramble_penalty = 0.3 if avg_sentence_length > 25 else 0

    score = 1 - (filler_penalty + ramble_penalty)
    score = max(min(score, 1), 0)

    return round(score * 100, 2)

# =============================
# INTERVIEW SKILL ANALYSIS
# =============================
EXAMPLE_PHRASES = [
    "for example", "for instance", "when i",
    "i worked on", "i was responsible for"
]

IMPACT_WORDS = [
    "%", "percent", "increased", "reduced",
    "improved", "delivered", "impact"
]

PROBLEM_WORDS = [
    "problem", "challenge", "solution",
    "approach", "resolved"
]

def interview_skill_score(text: str) -> float:
    score = 0

    if any(p in text for p in EXAMPLE_PHRASES):
        score += 0.3
    if any(p in text for p in IMPACT_WORDS):
        score += 0.35
    if any(p in text for p in PROBLEM_WORDS):
        score += 0.35

    return round(min(score, 1) * 100, 2)

# =============================
# PERSONALITY ANALYSIS
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
        results[trait] = (
            "High" if count >= 3 else
            "Medium" if count >= 1 else
            "Low"
        )
    return results

# =============================
# FINAL SCORE
# =============================
def overall_interview_score(comm, skill, personality):
    personality_score = sum(
        1 if v == "High" else 0.5 if v == "Medium" else 0
        for v in personality.values()
    ) / len(personality)

    final_score = (
        skill * 0.40 +
        comm * 0.35 +
        personality_score * 100 * 0.25
    )

    return round(final_score, 2)

# =============================
# FEATURE 1: KEYWORD EVIDENCE
# =============================
def extract_keyword_hits(text, keywords, max_hits=5):
    hits = [k for k in keywords if k in text]
    return hits[:max_hits]

# =============================
# STREAMLIT UI
# =============================
st.set_page_config(page_title="Interview Analyzer", layout="centered")

st.title("🎯 Interview Performance Analyzer")
st.write("Upload an interview transcript to get structured feedback and an overall score.")

uploaded_file = st.file_uploader(
    "Upload Interview Transcript (.txt or .docx)",
    type=["txt", "docx"]
)

if uploaded_file:
    with st.spinner("Analyzing interview..."):
        text = read_transcript(uploaded_file)

        comm = communication_score(text)
        skill = interview_skill_score(text)
        personality = personality_analysis(text)
        final_score = overall_interview_score(comm, skill, personality)

    # -----------------------------
    # Scores
    # -----------------------------
    st.subheader("📊 Scores")
    st.metric("Overall Interview Score", f"{final_score}%")
    st.metric("Communication", f"{comm}%")
    st.metric("Interview Skills", f"{skill}%")

    # -----------------------------
    # Personality
    # -----------------------------
    st.subheader("🧠 Personality Signals")
    for k, v in personality.items():
        st.write(f"**{k}**: {v}")

    # -----------------------------
    # FEATURE 1 OUTPUT
    # -----------------------------
    st.subheader("🔍 Evidence from Your Answers")

    strong_signals = extract_keyword_hits(
        text,
        IMPACT_WORDS + EXAMPLE_PHRASES + PROBLEM_WORDS
    )

    weak_signals = extract_keyword_hits(
        text,
        FILLER_WORDS + PERSONALITY_SIGNALS["Uncertainty"]
    )

    st.write("✅ **Strong signals detected**")
    st.write(strong_signals if strong_signals else "No strong evidence detected")

    st.write("⚠️ **Potential improvement areas**")
    st.write(weak_signals if weak_signals else "No major issues detected")

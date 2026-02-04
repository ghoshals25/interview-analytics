# =============================
# INTERVIEW ANALYZER – FULL MERGED VERSION
# =============================

import streamlit as st
import docx
import re
from pathlib import Path
from collections import Counter

import google.generativeai as genai

# =============================
# CONFIG
# =============================
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
- Be concise and factual
- Do NOT assign scores
- Do NOT make hiring decisions
- Do NOT invent information
- Use only CV and JD content
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

# =============================
# SESSION STATE
# =============================
for key in ["jd_cv_analysis"]:
    if key not in st.session_state:
        st.session_state[key] = None

# =============================
# FILE HELPERS
# =============================
def read_docx(file):
    doc = docx.Document(file)
    return "\n".join(p.text for p in doc.paragraphs).lower()

# =============================
# ATS ENGINE (LIKE MATCHING)
# =============================
SKILL_BUCKETS = {
    "skills": [
        "analytics", "data analysis", "insights", "business insights",
        "strategy", "strategic", "stakeholder", "stakeholder management",
        "problem solving", "decision making", "commercial insights"
    ],
    "ownership": [
        "led", "leadership", "owned", "ownership", "managed", "management",
        "delivered", "delivery", "end to end", "e2e",
        "accountable", "responsible for", "driving", "executed", "scaled"
    ],
    "tools": [
        "python", "sql", "power bi", "tableau", "excel",
        "pandas", "numpy", "spark",
        "dashboard", "data visualization", "etl",
        "bigquery", "snowflake"
    ]
}

def normalize(text):
    return re.sub(r"[^a-z0-9 ]", " ", text.lower())

def like_match(text, keyword):
    return keyword in text

def compute_cv_match(jd_text, cv_text):
    scores = {}
    pct_list = []
    details = {}

    jd_text = normalize(jd_text)
    cv_text = normalize(cv_text)

    for bucket, keywords in SKILL_BUCKETS.items():
        jd_hits = {k for k in keywords if like_match(jd_text, k)}
        cv_hits = {k for k in keywords if like_match(cv_text, k)}

        matched = jd_hits.intersection(cv_hits)
        missing = jd_hits.difference(cv_hits)

        pct = round((len(matched) / len(keywords)) * 100, 1)
        scores[bucket] = pct
        pct_list.append(pct)

        details[bucket] = {
            "matched": matched,
            "missing": missing
        }

    overall = round(sum(pct_list) / len(pct_list), 1)
    return overall, scores, details

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
# UI
# =============================
st.set_page_config(page_title="Interview Analyzer", layout="wide")
st.title("🎯 Interview Performance Analyzer")

st.subheader("🧩 Pre-Interview Context")
job_description = st.text_area("Job Description")
uploaded_cv = st.file_uploader("Upload CV (DOCX)", ["docx"])

# =============================
# LEFT SIDEBAR: JD + CV ANALYSIS
# =============================
with st.sidebar:
    st.header("📄 JD & Candidate Analysis")

    if uploaded_cv and job_description:
        cv_text_sidebar = read_docx(uploaded_cv)
        jd_text_sidebar = job_description.lower()

        if st.session_state.jd_cv_analysis is None:
            prompt = f"""
JOB DESCRIPTION:
{jd_text_sidebar}

CANDIDATE CV:
{cv_text_sidebar}

{GEMINI_JD_CV_ANALYSIS_PROMPT}
"""
            st.session_state.jd_cv_analysis = gemini_model.generate_content(prompt).text

        st.markdown(st.session_state.jd_cv_analysis)
    else:
        st.caption("Upload CV and Job Description to view analysis")

# =============================
# ATS SCORE + CONCISE EXPLANATION
# =============================
if uploaded_cv and job_description:
    cv_text = read_docx(uploaded_cv)

    score, breakdown, details = compute_cv_match(job_description, cv_text)
    summary = cv_summary(score, breakdown)

    st.success(f"CV Match Score: {score}%")
    st.caption(summary)

    # ---- Concise interviewer-facing explanation ----
    st.subheader("🔍 Why this score?")

    jd_expectations = set()
    cv_missing = set()

    for info in details.values():
        jd_expectations.update(info["matched"])
        cv_missing.update(info["missing"])

    explanation = []

    if jd_expectations:
        explanation.append(
            f"The role emphasises {', '.join(sorted(jd_expectations))}."
        )

    if cv_missing:
        explanation.append(
            f"The CV does not clearly demonstrate {', '.join(sorted(cv_missing))}, which are explicitly mentioned in the job description."
        )
    else:
        explanation.append(
            "The CV broadly covers the key areas highlighted in the job description."
        )

    explanation.append(
        "These areas should be probed further during the interview to assess depth and hands-on experience."
    )

    st.caption(" ".join(explanation)[:700])

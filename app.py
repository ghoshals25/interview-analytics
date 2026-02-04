# =============================
# INTERVIEW ANALYZER – FINAL PRODUCTION VERSION
# =============================

import streamlit as st
import docx
import re
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
if "jd_cv_analysis" not in st.session_state:
    st.session_state.jd_cv_analysis = None

# =============================
# FILE HELPERS
# =============================
def read_docx(file):
    doc = docx.Document(file)
    return "\n".join(p.text for p in doc.paragraphs).lower()

# =============================
# CAPABILITY KEYWORDS (FINAL)
# =============================
SKILL_BUCKETS = {
    "skills": [
        "analytics", "data analysis", "insights", "business insights",
        "strategy", "strategic", "stakeholder", "stakeholder management",
        "problem solving", "decision making", "scenario analysis"
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
        "bigquery", "snowflake", "vba", "dax"
    ]
}

# =============================
# NORMALISATION
# =============================
def normalize(text):
    return re.sub(r"[^a-z0-9 ]", " ", text.lower())

def like_match(text, keyword):
    return keyword in text

# =============================
# FINAL SCORING LOGIC (OVERLAP-BASED)
# =============================
def compute_cv_match(jd_text, cv_text):
    jd_text = normalize(jd_text)
    cv_text = normalize(cv_text)

    bucket_scores = {}
    details = {}

    for bucket, keywords in SKILL_BUCKETS.items():
        jd_items = {k for k in keywords if like_match(jd_text, k)}
        cv_items = {k for k in keywords if like_match(cv_text, k)}

        intersection = jd_items.intersection(cv_items)
        union = jd_items.union(cv_items)
        missing = jd_items - cv_items

        score = round((len(intersection) / len(union)) * 100, 1) if union else 0.0

        bucket_scores[bucket] = score
        details[bucket] = {
            "intersection": intersection,
            "union": union,
            "missing": missing
        }

    overall_score = round(sum(bucket_scores.values()) / 3, 1)
    overall_score = min(overall_score, 100)

    return overall_score, bucket_scores, details

# =============================
# PAGE CONFIG
# =============================
st.set_page_config(
    page_title="Interview Analyzer",
    layout="wide",
)

st.title("🎯 Interview Performance Analyzer")
st.caption("Decision-support tool for structured interview preparation")

st.divider()

# =============================
# SIDEBAR – JD & CV ANALYSIS
# =============================
with st.sidebar:
    st.header("📄 JD & Candidate Overview")

    if st.session_state.jd_cv_analysis:
        st.markdown(st.session_state.jd_cv_analysis)
    else:
        st.caption("Upload a Job Description and CV to generate an overview")

# =============================
# MAIN LAYOUT
# =============================
left_col, right_col = st.columns([1.1, 1])

# -----------------------------
# LEFT: INPUTS + SCORE
# -----------------------------
with left_col:
    st.subheader("🧩 Pre-Interview Context")

    job_description = st.text_area(
        "Job Description",
        placeholder="Paste the full job description here…",
        height=220
    )

    uploaded_cv = st.file_uploader(
        "Candidate CV (DOCX)",
        type=["docx"]
    )

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

        st.metric(
            label="CV–JD Alignment Score",
            value=f"{score}%",
            help="Overlap-based alignment between Job Description and CV"
        )

# -----------------------------
# RIGHT: EXPLANATION
# -----------------------------
with right_col:
    st.subheader("🔍 Interviewer Insight")

    if uploaded_cv and job_description:
        jd_focus = set()
        cv_matches = set()
        cv_gaps = set()

        for info in details.values():
            jd_focus.update(info["union"])
            cv_matches.update(info["intersection"])
            cv_gaps.update(info["missing"])

        explanation = []

        if jd_focus:
            explanation.append(
                f"The role emphasises {', '.join(sorted(jd_focus))}."
            )

        if cv_matches:
            explanation.append(
                f"The CV demonstrates clear experience in {', '.join(sorted(cv_matches))}."
            )

        if cv_gaps:
            explanation.append(
                f"However, the CV does not clearly surface evidence of {', '.join(sorted(cv_gaps))}, which are explicitly referenced in the job description."
            )

        explanation.append(
            "These areas should be explored further during the interview to validate depth, ownership, and hands-on involvement."
        )

        st.write(" ".join(explanation))
    else:
        st.caption("Upload both the Job Description and CV to view interviewer insights")


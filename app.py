# ============================================================
# PRE-INTERVIEW + CV INTELLIGENCE ADD-ON (SAFE EXTENSION)
# DOES NOT MODIFY EXISTING INTERVIEW ANALYZER LOGIC
# ============================================================

import re
from collections import Counter

# -----------------------------
# STEP 0: PRE-INTERVIEW CONTEXT
# -----------------------------
st.subheader("Pre-Interview Context")

ROLE_OPTIONS = ["Analytics and Insights Lead"]

selected_role = st.selectbox(
    "Role applied for",
    ROLE_OPTIONS,
    index=0
)

job_description = st.text_area(
    "Paste the Job Description",
    height=220
)

uploaded_cv = st.file_uploader(
    "Upload Candidate CV (PDF / DOCX)",
    type=["docx", "pdf"]
)

cv_text = ""

if uploaded_cv and uploaded_cv.name.endswith(".docx"):
    doc = docx.Document(uploaded_cv)
    cv_text = "\n".join([p.text for p in doc.paragraphs])

# -----------------------------
# ATS CONFIGURATION
# -----------------------------
SKILL_BUCKETS = {
    "skills": [
        "analytics", "insights", "strategy",
        "stakeholder", "decision", "growth"
    ],
    "ownership": [
        "led", "owned", "delivered",
        "scaled", "managed", "built"
    ],
    "tools": [
        "python", "sql", "power bi",
        "tableau", "excel"
    ]
}

# -----------------------------
# TEXT UTILITIES
# -----------------------------
def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", text.lower())

def keyword_frequency(text, keywords):
    words = normalize(text).split()
    counter = Counter(words)
    return {k: counter[k] for k in keywords}

# -----------------------------
# CV ↔ JD MATCH ENGINE
# -----------------------------
def compute_cv_match(jd_text, cv_text):
    breakdown = {}
    percentages = []

    for bucket, keywords in SKILL_BUCKETS.items():
        jd_freq = keyword_frequency(jd_text, keywords)
        cv_freq = keyword_frequency(cv_text, keywords)

        matched = sum(
            1 for k in keywords
            if jd_freq[k] > 0 and cv_freq[k] > 0
        )

        pct = round((matched / len(keywords)) * 100, 1)

        breakdown[bucket] = {
            "matched": matched,
            "total": len(keywords),
            "percentage": pct
        }

        percentages.append(pct)

    overall_score = round(sum(percentages) / len(percentages), 1)
    return overall_score, breakdown

# -----------------------------
# CV SUMMARY (CONCISE)
# -----------------------------
def generate_cv_summary(cv_score, breakdown):
    strengths = []
    gaps = []

    for bucket, data in breakdown.items():
        if data["percentage"] >= 70:
            strengths.append(bucket)
        elif data["percentage"] < 40:
            gaps.append(bucket)

    summary = f"CV shows a {cv_score}% alignment with the role requirements."

    if strengths:
        summary += f" Strong alignment in {', '.join(strengths)}."

    if gaps:
        summary += f" Gaps observed in {', '.join(gaps)}."

    return summary

# -----------------------------
# EXECUTE CV MATCH
# -----------------------------
cv_match_score = None
cv_breakdown = None
cv_summary = None

if job_description and cv_text:
    cv_match_score, cv_breakdown = compute_cv_match(
        job_description, cv_text
    )
    cv_summary = generate_cv_summary(
        cv_match_score, cv_breakdown
    )

    st.info(f"CV Match Score: {cv_match_score}%")

# -----------------------------
# CV ↔ INTERVIEW CORRELATION
# -----------------------------
def correlate_cv_with_interview(
    cv_breakdown,
    interview_text,
    interviewer_comments
):
    insights = []
    interview_text = normalize(interview_text or "")
    interviewer_comments = normalize(interviewer_comments or "")

    if cv_breakdown["tools"]["percentage"] >= 70:
        if not any(t in interview_text for t in SKILL_BUCKETS["tools"]):
            insights.append(
                "Tools strongly listed in CV were not clearly evidenced during the interview."
            )

    if cv_breakdown["ownership"]["percentage"] < 40:
        if any(w in interview_text for w in ["led", "owned", "managed"]):
            insights.append(
                "Leadership and ownership demonstrated in interview beyond CV evidence."
            )

    if not insights:
        insights.append(
            "CV claims and interview discussion appear largely consistent."
        )

    return insights

def cv_interview_alignment_status(insights):
    if any("not" in i.lower() for i in insights):
        return "Partially Validated"
    return "Validated"

# -----------------------------
# RUN CORRELATION (USES EXISTING VARIABLES)
# -----------------------------
cv_interview_insights = []
alignment_status = None

if cv_breakdown:
    cv_interview_insights = correlate_cv_with_interview(
        cv_breakdown,
        interview_transcript_text,    # EXISTING VARIABLE
        interviewer_comments_text     # EXISTING VARIABLE
    )

    alignment_status = cv_interview_alignment_status(
        cv_interview_insights
    )

# -----------------------------
# EMAIL BLOCKS (APPEND ONLY)
# -----------------------------
cv_hr_block = f"""
CV FIT SNAPSHOT
---------------
CV Match Score: {cv_match_score}%
Summary: {cv_summary}

CV ↔ Interview Validation:
Status: {alignment_status}
""" + "\n".join([f"- {i}" for i in cv_interview_insights])


cv_interviewer_block = f"""
CV CONTEXT
----------
CV Match Score: {cv_match_score}%

Key Observations:
""" + "\n".join([f"- {i}" for i in cv_interview_insights])

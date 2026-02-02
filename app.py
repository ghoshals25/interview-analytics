import streamlit as st
import tempfile
import requests
import google.generativeai as genai

# =============================
# CONFIG
# =============================
st.set_page_config(page_title="Interview Review (Manual)", layout="centered")

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite")

RESEND_API_KEY = st.secrets["RESEND_API_KEY"]
RESEND_ENDPOINT = "https://api.resend.com/emails"
SENDER_EMAIL = "Soumik <onboarding@resend.dev>"

# =============================
# SESSION STATE
# =============================
if "ai_feedback" not in st.session_state:
    st.session_state.ai_feedback = None

# =============================
# AI INTERPRETATION (NO SCORING)
# =============================
def generate_ai_interpretation(scores: dict) -> str:
    prompt = f"""
You are an interview feedback interpreter.

IMPORTANT:
- You did NOT score this interview
- Scores were entered manually by a reviewer
- You must ONLY interpret the numbers provided

Manual Scores:
- Communication: {scores['communication']}%
- Problem Solving: {scores['problem_solving']}%
- Confidence: {scores['confidence']}%
- Structure & Clarity: {scores['structure']}%
- Overall Score: {scores['overall']}%

Your task:
1. Overall interpretation
2. 2 strengths based strictly on high scores
3. 2 improvements based strictly on low scores
"""
    response = gemini_model.generate_content(prompt)
    return response.text

# =============================
# REPORT GENERATION
# =============================
def generate_report(scores: dict, feedback: str) -> str:
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    with open(temp.name, "w") as f:
        f.write("INTERVIEW PERFORMANCE REPORT\n")
        f.write("=" * 30 + "\n\n")

        for k, v in scores.items():
            f.write(f"{k.replace('_',' ').title()}: {v}%\n")

        f.write("\nAI Interpretation\n")
        f.write("-" * 20 + "\n")
        f.write(feedback)

    return temp.name

# =============================
# EMAIL SENDER
# =============================
def send_email(report_path: str, user_email: str):
    with open(report_path, "r") as f:
        content = f.read()

    response = requests.post(
        RESEND_ENDPOINT,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": SENDER_EMAIL,
            "to": user_email,
            "subject": "Your Interview Feedback Report",
            "text": content,
        },
    )

    if response.status_code not in (200, 201):
        raise Exception(response.text)

# =============================
# UI
# =============================
st.title("🧑‍💼 Interview Review — Manual Scoring")

st.caption(
    "ℹ️ Scores are entered manually. AI only interprets the scores."
)

st.subheader("🔢 Manual Interview Scores")

communication = st.slider("Communication", 0, 100, 70)
problem_solving = st.slider("Problem Solving", 0, 100, 70)
confidence = st.slider("Confidence", 0, 100, 70)
structure = st.slider("Structure & Clarity", 0, 100, 70)

overall = round(
    (communication + problem_solving + confidence + structure) / 4, 2
)

scores = {
    "communication": communication,
    "problem_solving": problem_solving,
    "confidence": confidence,
    "structure": structure,
    "overall": overall,
}

st.markdown(f"### ✅ Overall Score: **{overall}%**")

# =============================
# AI INTERPRETATION
# =============================
if st.button("🤖 Generate AI Interpretation"):
    st.session_state.ai_feedback = generate_ai_interpretation(scores)

if st.session_state.ai_feedback:
    st.subheader("📋 AI Interpretation")
    st.write(st.session_state.ai_feedback)

# =============================
# EMAIL
# =============================
st.subheader("📧 Email Report")
user_email = st.text_input("Enter recipient email")

if st.button("📤 Send Email"):
    if not user_email:
        st.error("Please enter an email address")
    elif not st.session_state.ai_feedback:
        st.error("Generate AI interpretation first")
    else:
        report = generate_report(scores, st.session_state.ai_feedback)
        send_email(report, user_email)
        st.success("✅ Report emailed successfully!")

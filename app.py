import streamlit as st
from openai import OpenAI
import requests
import base64
from PIL import Image
import re
import os
import toml
import time
import json
import logging

if os.path.exists("/etc/secrets/secrets.toml"):
    st_secrets = toml.load("/etc/secrets/secrets.toml")
else:
    st_secrets = st.secrets

# === CONFIG ===
MATHPIX_APP_ID = st_secrets["MATHPIX_APP_ID"]
MATHPIX_APP_KEY = st_secrets["MATHPIX_APP_KEY"]
client = OpenAI(api_key=st_secrets["OPENAI_API_KEY"])
HISTORY_DIR = ".history"
os.makedirs(HISTORY_DIR, exist_ok=True)

# === Load Logo ===
logo = Image.open("mathmandala_logo.png")
col1, col2 = st.columns([1, 8])
with col1:
    st.image(logo, width=90)
with col2:
    st.markdown("<h1 style='padding-top: 10px;'>Math Mandala</h1>", unsafe_allow_html=True)

# === Sidebar History ===
with st.sidebar:
    st.header("📚 History")
    history_files = sorted([f for f in os.listdir(HISTORY_DIR) if f.endswith(".json")])
    selected = st.selectbox("View Past Session", ["None"] + history_files[::-1])
    if selected != "None":
        with open(os.path.join(HISTORY_DIR, selected), "r") as f:
            past = json.load(f)
        st.session_state.selected_history = past
    else:
        st.session_state.selected_history = None

# === Main Execution ===
if st.session_state.selected_history:
    data = st.session_state.selected_history
    st.subheader(f"📖 Review: {data['timestamp']} - {data['subject']}")
    st.image(data["image"], caption="Past Submission", use_container_width=True)
    if data['subject'] == "Math":
        for q_num, question in data["problems"].items():
            st.markdown(f"---\n### Q{q_num}. {question}")
            st.markdown(data["feedback"].get(str(q_num), ""))
    elif data['subject'] == "Story Mountain":
        st.markdown("### ✍️ Story Task")
        st.markdown(data["task"], unsafe_allow_html=True)
        st.markdown("### 📖 Feedback")
        st.markdown(data["feedback"], unsafe_allow_html=True)
    elif data['subject'] == "Biology":
        st.markdown("### ✍️ Biology Task")
        st.markdown(data["task"], unsafe_allow_html=True)
        st.markdown("### 📖 Feedback")
        st.markdown(data["feedback"], unsafe_allow_html=True)
else:
    subject = st.selectbox("Select Subject", ["Math", "Story Mountain", "Biology"])
    if st.button("🚀 Generate Task"):
        image_file = st.camera_input("Take a photo of your work")
        if image_file is not None:
            with open("camera_capture.jpg", "wb") as f:
                f.write(image_file.getbuffer())
            image_path = "camera_capture.jpg"

            def ocr_with_mathpix_full(image_path):
                with open(image_path, "rb") as image_file:
                    img_base64 = base64.b64encode(image_file.read()).decode()
                headers = {
                    "app_id": MATHPIX_APP_ID,
                    "app_key": MATHPIX_APP_KEY,
                    "Content-type": "application/json"
                }
                data = {
                    "src": f"data:image/jpeg;base64,{img_base64}",
                    "formats": ["text"],
                    "ocr": ["math", "text"]
                }
                response = requests.post("https://api.mathpix.com/v3/text", json=data, headers=headers)
                return response.json().get("text", "")

            if subject == "Math":
                def generate_dynamic_problems():
                    text = """
Q1. Solve for x: 5x - 3(2x - 7) = 11.
Q2. The base of a triangle is 8 cm and the height is 15 cm. What is the area of the triangle?
Q3. If you subtract 3.75 from 7.5, what is the result?
Q4. In a bag of red and blue marbles, the ratio of red to blue marbles is 3:7. If there are 40 marbles in total, how many are blue?
Q5. A bag contains 4 red balls, 5 blue balls, and 3 green balls. If you pick one ball without looking, what is the probability that it is not green?
Q6. The following are the test scores of seven students: 85, 90, 88, 92, 95, 88, 90. What is the median score?
                    """
                    problems = {}
                    for line in text.strip().split("\n"):
                        match = re.match(r'^Q?(\d+)\.\s*(.+)', line.strip())
                        if match:
                            number = int(match.group(1))
                            problems[number] = match.group(2)
                    return problems

                def get_openai_math_feedback_full(questions_dict, ocr_text):
                    import json, re
                    prompt = f"""
You are a math tutor reviewing a student's worksheet. You will receive:
1. The full OCR text extracted from the image.
2. The list of 6 original questions.
Your task:
- For each question Q1 to Q6, find the student’s answer.
- Review it.
- Return feedback as JSON with keys 1 to 6.

OCR Text:
{ocr_text}

Questions:
{json.dumps(questions_dict, indent=2)}
                    """
                    response = client.chat.completions.create(
                        model="gpt-4",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.2,
                        max_tokens=1500
                    )
                    raw = response.choices[0].message.content
                    match = re.search(r"\{.*\}", raw, re.DOTALL)
                    return json.loads(match.group(0)) if match else {"error": "No JSON", "raw": raw}

                PROBLEMS = generate_dynamic_problems()
                ocr_text = ocr_with_mathpix_full(image_path)
                feedback_json = get_openai_math_feedback_full(PROBLEMS, ocr_text)
                for q_num, question in PROBLEMS.items():
                    st.markdown(f"---\n### Q{q_num}. {question}")
                    data = feedback_json.get(f"{q_num}")
                    if not data:
                        st.warning("No feedback.")
                        continue
                    st.markdown("**✍️ Student Answer:**")
                    st.code(data.get("student_answer", ""))
                    st.markdown("**🎓 Feedback:**")
                    st.markdown(data.get("feedback", ""))

            elif subject == "Story Mountain":
                task = "Draw a fantasy story arc set in a mythical world with a young hero facing a magical dilemma."
                st.markdown("### 🧠 Creative Writing Prompt")
                st.markdown(task)
                ocr_text = ocr_with_mathpix_full(image_path)
                prompt = f"""
Evaluate this Story Mountain:
{ocr_text}
Give structured feedback on each part.
                """
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}]
                )
                st.success("📖 Feedback")
                st.markdown(response.choices[0].message.content)

            elif subject == "Biology":
                task = "Draw and label the human respiratory system with clear function descriptions."
                st.markdown("### 🧬 Biology Drawing Task")
                st.markdown(task)
                ocr_text = ocr_with_mathpix_full(image_path)
                prompt = f"""
Assess this biology diagram:
{ocr_text}
Check if key labels are present and accurate. Provide feedback.
                """
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}]
                )
                st.success("🧬 Feedback")
                st.markdown(response.choices[0].message.content)

            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            Image.open(image_path).save(os.path.join(HISTORY_DIR, f"{timestamp}.jpg"))
            with open(os.path.join(HISTORY_DIR, f"{timestamp}.json"), "w") as f:
                json.dump({
                    "timestamp": timestamp,
                    "subject": subject,
                    "ocr_text": ocr_text,
                    "feedback": feedback_json if subject == "Math" else response.choices[0].message.content,
                    "problems": PROBLEMS if subject == "Math" else None,
                    "image": os.path.join(HISTORY_DIR, f"{timestamp}.jpg")
                }, f)
            os.remove(image_path)

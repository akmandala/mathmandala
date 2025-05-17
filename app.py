import streamlit as st
from openai import OpenAI
import requests
import base64
import tempfile
from PIL import Image
import re
import os
import glob
import time

# === CONFIG ===
# Load from st.secrets
MATHPIX_APP_ID = st.secrets["MATHPIX_APP_ID"]
MATHPIX_APP_KEY = st.secrets["MATHPIX_APP_KEY"]
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Load logo
logo = Image.open("mathmandala_logo.png")
col1, col2 = st.columns([1, 8])
with col1:
    st.image(logo, width=90)
with col2:
    st.markdown("<h1 style='padding-top: 10px;'>Math Mandala</h1>", unsafe_allow_html=True)

# === Select Subject ===
subject = st.selectbox("Select Subject", ["Math", "Story Mountain"])

# === Dynamic Content ===
if subject == "Math":
    def generate_dynamic_problems():
        prompt = """
Generate 6 challenging and diverse Year 7 math problems. Each should come from a different area:
Q1. Algebra
Q2. Geometry
Q3. Fractions or Decimals
Q4. Ratio or Proportion
Q5. Probability
Q6. Statistics or Averages
Number them from 1 to 6 in this format:
Q1. [question text]
...etc
Do not include answers.
"""
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )
        text = response.choices[0].message.content
        problems = {}
        for line in text.strip().split("\n"):
            match = re.match(r'^Q?(\d+)\.\s*(.+)', line.strip())
            if match:
                number = int(match.group(1))
                problems[number] = match.group(2)
        return problems

    PROBLEMS = generate_dynamic_problems()

    def ocr_with_mathpix_retry(image_path, expected_questions=6):
        for attempt in range(2):
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
            text = response.json().get("text", "")
            answers = parse_numbered_answers(text)

            if len(answers) >= expected_questions:
                return answers
            time.sleep(1.5)
        return answers

    def parse_numbered_answers(text):
        answers = {}
        current = None
        for line in text.splitlines():
            match = re.match(r'^Q(\d+)\.', line.strip())
            if match:
                current = int(match.group(1))
                answers[current] = []
            elif current:
                answers[current].append(line)
        return {k: '\n'.join(v).strip() for k, v in answers.items()}

    def get_openai_feedback(problem, user_solution):
        prompt = f"""
A student is solving this math problem: {problem}

Here is the student's handwritten solution:
{user_solution}

Please identify any mistakes, if any, and explain how to solve the problem step by step.
"""
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return response.choices[0].message.content

    DOWNLOADS_DIR = os.path.expanduser("~/Downloads")
    PATTERN = os.path.join(DOWNLOADS_DIR, "mathmandala_*_math_*.jpg")

    def get_latest_mathmandala_image():
        files = glob.glob(PATTERN)
        if not files:
            return None
        return max(files, key=os.path.getmtime)

    def delete_file(path):
        if os.path.exists(path):
            os.remove(path)

    st.markdown("Students should answer all 6 questions on **one sheet**, label them `Q1.`, `Q2.`, etc.")
    with st.expander("📝 Questions"):
        for i in range(1, 7):
            st.markdown(f"**Q{i}.** {PROBLEMS[i]}")

    st.info("Waiting for scan from Math Mandala extension...")
    placeholder = st.empty()
    while True:
        latest_file = get_latest_mathmandala_image()
        if latest_file:
            placeholder.image(latest_file, caption="Captured by Math Mandala Extension", use_container_width=True)
            with st.spinner("Reading sheet with MathPix..."):
                answers = ocr_with_mathpix_retry(latest_file, expected_questions=6)
            for q_num, question in PROBLEMS.items():
                st.markdown(f"---\n### Q{q_num}. {question}")
                solution = answers.get(q_num, "")
                if not solution:
                    st.warning("No solution detected for this question.")
                    continue
                with st.spinner("Tutoring in progress..."):
                    feedback = get_openai_feedback(question, solution)
                st.success("🎓 Feedback")
                st.markdown(feedback)
            delete_file(latest_file)
            break
        time.sleep(5)

elif subject == "Story Mountain":
    def generate_story_task():
        prompt = """
Create a Story Mountain writing task for a Year 7 student.
Provide the following only:

* Genre
* Main setting
* Central character
* Conflict or challenge

Make it imaginative, challenging, and age-appropriate.

Do not include the Story Mountain structure, summary, or plot outline.
"""
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        return response.choices[0].message.content

    st.markdown("Students should complete their Story Mountain using the printable template.")
    st.subheader("🧠 Creative Writing Prompt")
    st.markdown(generate_story_task())

    DOWNLOADS_DIR = os.path.expanduser("~/Downloads")
    PATTERN = os.path.join(DOWNLOADS_DIR, "mathmandala_*_story_*.jpg")

    def get_latest_story_image():
        files = glob.glob(PATTERN)
        if not files:
            return None
        return max(files, key=os.path.getmtime)

    def delete_file(path):
        if os.path.exists(path):
            os.remove(path)

    def feedback_on_story(text):
        prompt = f"""
Evaluate this Story Mountain plan written by a Year 7 student. Give feedback on whether each part is present (Opening, Build-up, Climax, Falling Action, Ending), the creativity of the story, and how well it fits the assigned challenge.

Student's Story Mountain:
{text}
"""
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content

    st.info("Waiting for Story Mountain scan from extension...")
    placeholder = st.empty()
    while True:
        latest_file = get_latest_story_image()
        if latest_file:
            placeholder.image(latest_file, caption="Captured Story Mountain", use_container_width=True)
            with open(latest_file, "rb") as image_file:
                img_base64 = base64.b64encode(image_file.read()).decode()
            headers = {
                "app_id": MATHPIX_APP_ID,
                "app_key": MATHPIX_APP_KEY,
                "Content-type": "application/json"
            }
            data = {
                "src": f"data:image/jpeg;base64,{img_base64}",
                "formats": ["text"],
                "ocr": ["text"]
            }
            response = requests.post("https://api.mathpix.com/v3/text", json=data, headers=headers)
            text = response.json().get("text", "")
            if text:
                with st.spinner("Providing feedback on your story..."):
                    feedback = feedback_on_story(text)
                st.success("📖 Feedback on Story Plan")
                st.markdown(feedback)
            delete_file(latest_file)
            break
        time.sleep(5)


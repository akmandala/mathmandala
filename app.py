import streamlit as st
from openai import OpenAI
import requests
import base64
from PIL import Image
import re
import os
import time
import json
import logging

# === CONFIG ===
MATHPIX_APP_ID = st.secrets["MATHPIX_APP_ID"]
MATHPIX_APP_KEY = st.secrets["MATHPIX_APP_KEY"]
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
RENDER_UPLOADS_URL = "https://mathmandala-upload.onrender.com/uploads"
RENDER_FILE_BASE = "https://mathmandala-upload.onrender.com/files"
RENDER_DELETE_ALL = "https://mathmandala-upload.onrender.com/delete-all"
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

# === Helper: Download Latest File from Render ===
def fetch_latest_image(prefix="mathmandala_", timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        try:
            res = requests.get(RENDER_UPLOADS_URL)
            if res.status_code == 200:
                files = sorted([f for f in res.json().get("files", []) if f.startswith(prefix) and f.endswith(".jpg")])
                if files:
                    latest = files[-1]
                    image_url = f"{RENDER_FILE_BASE}/{latest}"
                    img_data = requests.get(image_url).content
                    with open("temp_upload.jpg", "wb") as f:
                        f.write(img_data)
                    try:
                        Image.open("temp_upload.jpg").verify()
                        return "temp_upload.jpg", latest
                    except:
                        os.remove("temp_upload.jpg")
        except Exception as e:
            st.warning(f"Error checking uploads: {e}")
        time.sleep(2)
    return None, None

# === Main Execution ===
if st.session_state.selected_history:
    data = st.session_state.selected_history
    st.subheader(f"📖 Review: {data['timestamp']} - {data['subject']}")
    st.image(data["image"], caption="Past Submission", use_container_width=True)
    if data['subject'] == "Math":
        for q_num, question in data["problems"].items():
            st.markdown(f"---\n### Q{q_num}. {question}")
            #st.markdown(data["answers"].get(str(q_num), ""))
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
                #response = client.chat.completions.create(
                #    model="gpt-4",
                #    messages=[{"role": "user", "content": prompt}],
                #    temperature=0.4
                #)
                #text = response.choices[0].message.content
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
                full_text = response.json().get("text", "")
                return full_text
        
            def get_openai_math_feedback_full(questions_dict, ocr_text, image_path):
                with open(image_path, "rb") as img_file:
                    image_b64 = base64.b64encode(img_file.read()).decode()
                    
                import json, re
                prompt = f"""
You are a math tutor reviewing a scanned student worksheet. You will receive:

1. The full OCR text extracted from the image (including all workings).
2. The list of 6 original questions.

Your task:
- For each question Q1 to Q6, match the student's corresponding handwritten answer from the OCR.
- Review the student's solution using the OCR text.
- Provide detailed feedback per question, including any mistakes and detailed steps how to correct them.
- Return a JSON object with keys 1 to 6.

OCR Text:
{ocr_text}

Questions:
{json.dumps(questions_dict, indent=2)}

Reply with JSON:
"""
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=1500
                )
        
                try:
                    raw = response.choices[0].message.content
                    match = re.search(r"\{.*\}", raw, re.DOTALL)
                    if match:
                        return json.loads(match.group(0))
                    else:
                        return {"error": "No JSON detected", "raw": raw}
                except Exception as e:
                    return {"error": str(e), "raw": response.choices[0].message.content}
        
            PROBLEMS = generate_dynamic_problems()
        
            st.markdown("Students should answer all 6 questions on **one sheet**, label them `Q1.`, `Q2.`, etc.")
            with st.expander("📝 Questions"):
                for i in range(1, 7):
                    st.markdown(f"**Q{i}.** {PROBLEMS[i]}")
        
            st.info("Waiting for image upload from extension via Render server...")
            placeholder = st.empty()
            image_path, image_name = fetch_latest_image()
            if image_path:
                placeholder.image(image_path, caption="Captured by Math Mandala Extension", use_container_width=True)
                with st.spinner("Reading sheet with MathPix and sending to AI..."):
                    ocr_text = ocr_with_mathpix_full(image_path)
                    feedback_json = get_openai_math_feedback_full(PROBLEMS, ocr_text, image_path)
        
                feedback_list = feedback_json if isinstance(feedback_json, dict) else {}
                for q_num, question in PROBLEMS.items():
                    st.markdown(f"---\n### Q{q_num}. {question}")
                    if str(q_num) not in feedback_list:
                        st.warning("No feedback received for this question.")
                    else:
                        st.success("🎓 Feedback")
                        st.markdown(feedback_list[str(q_num)])
        
                timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
                json_path = os.path.join(HISTORY_DIR, f"{timestamp}.json")
                Image.open(image_path).convert("RGB").save(os.path.join(HISTORY_DIR, f"{timestamp}.jpg"))
                with open(json_path, "w") as f:
                    json.dump({
                        "timestamp": timestamp,
                        "subject": subject,
                        "problems": PROBLEMS,
                        "ocr_text": ocr_text,
                        "feedback": feedback_list,
                        "image": os.path.join(HISTORY_DIR, f"{timestamp}.jpg")
                    }, f)
        
                os.remove(image_path)
                try:
                    requests.delete(RENDER_DELETE_ALL)
                except:
                    st.warning("Could not delete uploaded files from server.")
            else:
                st.warning("No new image received in time. Please try again.")

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
                #response = client.chat.completions.create(
                #    model="gpt-4",
                #    messages=[{"role": "user", "content": prompt}],
                #    temperature=0.5
                #)
                text = """
* Genre: Fantasy
* Main setting: A mystical forest filled with magical creatures and hidden realms.
* Central character: A timid, 12-year-old girl who discovers she has the ability to communicate with animals.
* Conflict or challenge: The girl must find and return a stolen artifact to its rightful place in order to restore peace and balance in the forest. She must overcome her shyness, build friendships with the forest creatures, and outwit the cunning thief who is determined to keep the artifact for their own selfish gains.
                """
                #return response.choices[0].message.content
                return text
            
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

            st.markdown("Students should complete their Story Mountain using the printable template.")
            st.subheader("🧠 Creative Writing Prompt")
            task = generate_story_task()
            st.markdown(task)

            st.info("Waiting for Story Mountain scan from extension via Render...")
            placeholder = st.empty()
            image_path, image_name = fetch_latest_image()
            if image_path:
                placeholder.image(image_path, caption="Captured Story Mountain", use_container_width=True)
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
                    "ocr": ["text"]
                }
                response = requests.post("https://api.mathpix.com/v3/text", json=data, headers=headers)
                text = response.json().get("text", "")
                if text:
                    with st.spinner("Providing feedback on your story..."):
                        feedback = feedback_on_story(text)
                    st.success("📖 Feedback on Story Plan")
                    st.markdown(feedback)

                    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
                    json_path = os.path.join(HISTORY_DIR, f"{timestamp}.json")
                    Image.open(image_path).convert("RGB").save(os.path.join(HISTORY_DIR, f"{timestamp}.jpg"))
                    with open(json_path, "w") as f:
                        json.dump({
                            "timestamp": timestamp,
                            "subject": subject,
                            "task": task,
                            "text": text,
                            "feedback": feedback,
                            "image": os.path.join(HISTORY_DIR, f"{timestamp}.jpg")
                        }, f)

                os.remove(image_path)
                try:
                    requests.delete(RENDER_DELETE_ALL)
                except:
                    st.warning("Could not delete uploaded files from server.")
            else:
                st.warning("No story image received in time. Please try again.")
                
        elif subject == "Biology":
            def generate_biology_task():
                prompt = """
Generate a high-difficulty Year 8 biology drawing assignment.

The assignment should ask the student to:
- Draw and clearly label a biological system or structure
- Include 5–8 correct labels
- Challenge understanding of form and function

Do not include the drawing or labels — only the instruction.
"""
                #response = client.chat.completions.create(
                #    model="gpt-4",
                #    messages=[{"role": "user", "content": prompt}],
                #    temperature=0.5
                #)
                text = """
Assignment:

Draw and label a detailed illustration of the human respiratory system. Your drawing should include the following structures: nasal cavity, pharynx, larynx, trachea, bronchi, lungs, and alveoli.

Each label should not only identify the part, but also include a brief description of its function within the system. Make sure to accurately depict the relative size and location of each structure to demonstrate your understanding of their interrelationships within the system.

To further challenge your understanding of form and function, include a smaller, zoomed-in illustration of an alveolus, showing its structure and how it facilitates the exchange of oxygen and carbon dioxide.

Remember, accuracy and attention to detail are crucial for this assignment. Your drawing should be neat and the labels should be clearly legible.
                """
                #return response.choices[0].message.content
                return text

            def feedback_on_biology_drawing(text):
                prompt = f"""
This is a student's labeled biology diagram:
{text}

Evaluate the drawing based on:
- Whether all expected parts are present
- The accuracy of the labels
- Biological correctness
- Any missing or mislabeled structures

Then provide constructive feedback for improvement.
"""
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3
                )

                return response.choices[0].message.content

            st.markdown("Students should draw and label the assigned biological system.")
            st.subheader("🧪 Biology Drawing Task")
            task = generate_biology_task()
            st.markdown(task)

            st.info("Waiting for drawing upload from extension via Render...")
            placeholder = st.empty()
            image_path, image_name = fetch_latest_image()
            if image_path:
                placeholder.image(image_path, caption="Captured Biology Drawing", use_container_width=True)
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
                    "ocr": ["text"]
                }
                response = requests.post("https://api.mathpix.com/v3/text", json=data, headers=headers)
                text = response.json().get("text", "")
                if text:
                    with st.spinner("Providing feedback on your diagram..."):
                        feedback = feedback_on_biology_drawing(text)
                    st.success("🧬 Feedback on Biology Diagram")
                    st.markdown(feedback)

                    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
                    json_path = os.path.join(HISTORY_DIR, f"{timestamp}.json")
                    Image.open(image_path).convert("RGB").save(os.path.join(HISTORY_DIR, f"{timestamp}.jpg"))
                    with open(json_path, "w") as f:
                        json.dump({
                            "timestamp": timestamp,
                            "subject": subject,
                            "task": task,
                            "text": text,
                            "feedback": feedback,
                            "image": os.path.join(HISTORY_DIR, f"{timestamp}.jpg")
                        }, f)

                os.remove(image_path)
                try:
                    requests.delete(RENDER_DELETE_ALL)
                except:
                    st.warning("Could not delete uploaded files from server.")
            else:
                st.warning("No biology drawing received in time. Please try again.")

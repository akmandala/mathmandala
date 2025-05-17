import streamlit as st
from openai import OpenAI
import requests
import base64
from PIL import Image
import re
import os
import time
import json

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
else:
    subject = st.selectbox("Select Subject", ["Math", "Story Mountain"])
    if st.button("🚀 Generate Task"):
        if subject == "Math":
            # existing math logic (unchanged)
            ...

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

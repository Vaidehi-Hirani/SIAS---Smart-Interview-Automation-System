# Smart Interview Automation System (SIAS)

SIAS is an intelligent, automated interview platform designed to streamline the initial screening process for HR teams. By replacing the need for human presence during the first round of interviews, SIAS reduces HR involvement by ~99%, automates candidate assessment, and provides structured, actionable insights.

## 🚀 Why SIAS?

**Problem:** Traditional screening interviews are time-consuming, repetitive, and resource-intensive. HR professionals spend countless hours scheduling and conducting basic introductory calls.

**Solution:** SIAS automates the entire flow—from candidate check-in to interview completion and summary generation—allowing HR to focus only on the final decision-making process.

## ✨ Key Features

-   **Automated Session Management:** Auto-start and auto-stop functionality based on candidate presence (camera & voice activity).
-   **Full Audio Recording:** Captures the entire interview session for review.
-   **Intelligent Summarization:** Uses OpenAI Whisper for accurate Hinglish transcription and NLTK-based NLP for extracting structured data (Skills, Projects, Education).
-   **Smart HR Dashboard:** A centralized view for HR to monitor sessions, play back audio, and view detailed candidate profiles.
-   **Cost-Effective & Secure:** Runs locally with lightweight dependencies; ensures privacy by allowing audio deletion.
-   **Structured Data Extraction:** Automatically parses unstructured speech into JSON fields (Name, Experience, Availability, etc.).

## 🛠 Tech Stack

-   **Frontend:** HTML5, CSS3, Vanilla JavaScript (Lightweight & Fast)
-   **Backend:** Python (FastAPI) for RESTful API & Async Task Management
-   **AI & ML:**
    -   **OpenCV:** Real-time camera motion detection.
    -   **OpenAI Whisper:** robust Speech-to-Text (supports English & Hindi/Hinglish).
    -   **NLTK:** Natural Language Processing for entity extraction.
-   **Database:** SQLite (Embedded, Zero-configuration)
-   **Storage:** Local File System (Audio chunks & Final recordings)

## 🏗 Project Architecture

SIAS follows a modular Client-Server architecture:
1.  **Frontend Client:** Handles UI, Audio Capture (MediaRecorder API), and Polling.
2.  **FastAPI Server:** Manages endpoints for session control, audio uploads, and configuration.
3.  **Background Workers:** Handle heavy tasks like Audio Merging and AI Transcription asynchronously to keep the UI responsive.
4.  **Database:** Stores session metadata and structured analysis results.

## 💻 How to Run Locally

### Prerequisites
-   **Python 3.8+** installed.
-   **FFmpeg** installed and added to system PATH (Required for audio processing).

### Step 1: Clone or Download
Ensure you have the project files in a local directory.

### Step 2: Install Dependencies
Navigate to the project root (where `requirements.txt` is located) and run:
```bash
pip install -r backend/requirements.txt
```

### Step 3: Start the Server
Run the FastAPI server using Uvicorn:
```bash
uvicorn backend.main:app --reload
```

### Step 4: Access the Application
Open your browser and navigate to:
```
http://127.0.0.1:8000
```

## 📝 Usage Guide
1.  **Candidate View:** Select your role (Intern/Fresher) -> Allow Permissions -> Start Interview.
2.  **Interview Mode:** Speak clearly. The system records audio and monitors presence.
3.  **Completion:** The session ends automatically after 10 seconds of silence/absence, or manually via "Finish".
4.  **HR Dashboard:** Navigate to the Dashboard to view the table of candidates. Click **"View Full"** to see the detailed AI analysis.

## ⚠️ Notes & Limitations
-   **Local Execution:** This prototype runs locally. For production, deploy the backend to a cloud server (AWS/GCP).
-   **Model Download:** The first run may take a moment to download the Whisper model (approx. 150MB).
-   **Browser Permissions:** Requires Camera & Microphone access permissions.

## 🎥 Demo Video

[![SIAS Demo Video](https://img.youtube.com/vi/gzTI75nD8ms/0.jpg)](https://www.youtube.com/watch?v=gzTI75nD8ms)



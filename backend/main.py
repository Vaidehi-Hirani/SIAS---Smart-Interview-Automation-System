from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
import uvicorn
import shutil
import os
import datetime
import asyncio
import database
import ai_service
import camera_service
from pydub import AudioSegment
import json

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constants
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
TIMEOUT_MINUTES = 30

# Global State
SYSTEM_STATE = {
    "status": "SLEEP", # SLEEP, IDLE, RECORDING
    "last_activity": datetime.datetime.now(),
    "current_session_id": None,
    "candidate_type": None
}

# Initialize DB
database.init_db()

# --- Helpers ---
def update_activity():
    SYSTEM_STATE["last_activity"] = datetime.datetime.now()

def wake_up_callback():
    # Called from Camera Thread
    update_activity()
    if SYSTEM_STATE["status"] == "SLEEP":
        print("Camera detected motion. Waking up...")
        SYSTEM_STATE["status"] = "IDLE"

# Initialize Camera
camera_monitor = camera_service.CameraMonitor(callback_on_motion=wake_up_callback)

def finalize_session_logic(session_id: int):
    """
    Finalizes the session. 
    Now primarily checks if the full audio file exists (uploaded by frontend).
    If not found, it waits briefly or fails.
    """
    final_file_path = os.path.join(UPLOAD_DIR, f"session_{session_id}.wav")
    
    # In the new flow, Frontend uploads the full file BEFORE calling end-session.
    # So we just check if it exists.
    
    if os.path.exists(final_file_path):
        database.set_processing_status(session_id)
        return final_file_path

    # Fallback: Check for chunks (Old logic, or if frontend upload failed but chunks were sent?)
    # But we removed chunk upload in frontend. So just fail if file missing.
    
    # Wait a moment in case filesystem is slow?
    # No, strictly follow logic.
    
    print(f"No full audio found for session {session_id}")
    database.update_session(session_id, "No audio recorded", "None", "", "N/A", "N/A", None)
    return None

@app.post("/api/upload-full-audio")
async def upload_full_audio(file: UploadFile = File(...), session_id: int = Form(...)):
    """
    Receives the full audio blob from the frontend at the end of the session.
    Saves it as the official session audio.
    """
    # update_activity() REMOVED.
    
    file_path = os.path.join(UPLOAD_DIR, f"session_{session_id}.webm") # Browser sends webm
    wav_path = os.path.join(UPLOAD_DIR, f"session_{session_id}.wav")
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        print(f"Full audio uploaded for session {session_id}. Converting to WAV...")
        
        # Convert to WAV for Whisper
        audio = AudioSegment.from_file(file_path)
        audio.export(wav_path, format="wav")
        
        # Cleanup webm
        os.remove(file_path)
        
        print(f"Conversion complete: {wav_path}")
        return {"message": "Audio uploaded successfully"}
        
    except Exception as e:
        print(f"Error uploading full audio: {e}")
        return {"error": str(e)}

# --- Background Tasks ---
async def auto_stop_monitor():
    while True:
        await asyncio.sleep(60) # Check every minute
        now = datetime.datetime.now()
        diff = now - SYSTEM_STATE["last_activity"]
        
        # Check for Presence Timeout (Absence)
        if diff.total_seconds() > TIMEOUT_MINUTES * 60:
            if SYSTEM_STATE["status"] != "SLEEP":
                print("Auto-Stop triggered due to inactivity (Presence Lost).")
                
                # If currently recording, we must finalize the session!
                if SYSTEM_STATE["status"] == "RECORDING" and SYSTEM_STATE["current_session_id"]:
                    session_id = SYSTEM_STATE["current_session_id"]
                    print(f"Auto-finalizing session {session_id} due to presence loss...")
                    
                    file_path = finalize_session_logic(session_id)
                    if file_path:
                        # Run processing in background without blocking the loop
                        loop = asyncio.get_running_loop()
                        loop.run_in_executor(None, process_session_background, session_id, file_path)

                SYSTEM_STATE["status"] = "SLEEP"
                SYSTEM_STATE["current_session_id"] = None

def process_session_background(session_id: int, file_path: str):
    print(f"Processing session {session_id}...")
    try:
        # Run AI
        text = ai_service.transcribe_audio(file_path)
        result, english_text = ai_service.generate_summary(text)
        
        summary = result["summary"]
        skills = ", ".join(result["skills"])
        availability = result["availability"]
        experience = result["experience"]
        
        # Serialize full result for detailed view
        json_data_str = json.dumps(result)
        
        # Save to DB
        # Note: audio_path is saved. 
        # Requirement: "Audio must be deleted after summarization" WAS ORIGINAL.
        # NEW FIX 2: "Audio must be saved TEMPORARILY... Audio deletion control must be Explicit HR action"
        # So we KEEP the file.
        
        database.update_session(
            session_id, summary, skills, english_text, 
            availability, experience, file_path, json_data_str
        )
        print(f"Session {session_id} processing complete.")
        
    except Exception as e:
        print(f"Error processing session {session_id}: {e}")
        database.update_session(session_id, "Error processing", "", "", "N/A", "N/A", file_path, None)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(auto_stop_monitor())
    camera_monitor.start()

@app.on_event("shutdown")
def shutdown_event():
    camera_monitor.stop()

# --- API Endpoints ---

@app.get("/api/status")
def get_status():
    return SYSTEM_STATE

@app.post("/api/wake-up")
def wake_up():
    update_activity()
    if SYSTEM_STATE["status"] == "SLEEP":
        SYSTEM_STATE["status"] = "IDLE"
        return {"message": "System Woken Up", "status": "IDLE"}
    return {"message": "System already awake", "status": SYSTEM_STATE["status"]}

@app.post("/api/detect-presence")
def detect_presence(source: str = Form(...)):
    # Called by frontend motion detection or voice trigger
    update_activity()
    if SYSTEM_STATE["status"] == "SLEEP":
        SYSTEM_STATE["status"] = "IDLE"
        return {"message": "Presence Detected. Waking up.", "state": "IDLE"}
    return {"message": "Presence confirmed.", "state": SYSTEM_STATE["status"]}

@app.post("/api/config-camera")
def config_camera(camera_id: int = Form(...)):
    try:
        camera_monitor.set_camera_id(camera_id)
        return {"message": f"Camera set to ID {camera_id}"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/start-session")
def start_session(candidate_type: str = Form(...)):
    update_activity()
    
    # Requirement: If Visitor/Employee -> STOP immediately
    if candidate_type in ["Visitor", "Internal Employee"]:
        SYSTEM_STATE["status"] = "SLEEP"
        SYSTEM_STATE["current_session_id"] = None
        return {"action": "SLEEP", "message": "Visitor detected. System going to sleep."}

    # Start new session
    session_id = database.create_session(candidate_type)
    SYSTEM_STATE["status"] = "RECORDING"
    SYSTEM_STATE["current_session_id"] = session_id
    SYSTEM_STATE["candidate_type"] = candidate_type
    
    return {"action": "START_INTERVIEW", "session_id": session_id}

@app.post("/api/upload-audio-chunk")
async def upload_audio_chunk(file: UploadFile = File(...), session_id: int = Form(...)):
    # update_activity() REMOVED: Audio chunks do not count as "Presence".
    # Only Camera Motion or VAD (via detect-presence) counts as Presence.
    if SYSTEM_STATE["status"] != "RECORDING" or SYSTEM_STATE["current_session_id"] != int(session_id):
        return {"error": "System not recording or session mismatch"}

    # Save chunk securely for later merging
    # We use a timestamp to ensure order
    try:
        timestamp = datetime.datetime.now().timestamp()
        temp_chunk_path = os.path.join(UPLOAD_DIR, f"chunk_{session_id}_{timestamp}.webm")
        
        with open(temp_chunk_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {"message": "Chunk received"}
    except Exception as e:
        print(f"Error saving audio chunk: {e}")
        return {"error": str(e)}

@app.post("/api/end-session")
def end_session(session_id: int = Form(...), background_tasks: BackgroundTasks = None):
    update_activity()
    
    # If session mismatch, we still process if valid ID provided, but warn
    if SYSTEM_STATE["current_session_id"] == int(session_id):
        SYSTEM_STATE["status"] = "IDLE"
        SYSTEM_STATE["current_session_id"] = None
    
    file_path = finalize_session_logic(session_id)
    
    if not file_path:
        return {"message": "Session ended, no audio."}
    
    # Schedule background processing
    background_tasks.add_task(process_session_background, int(session_id), file_path)
    
    return {"message": "Session finalized. Processing in background."}

@app.get("/api/sessions")
def get_sessions():
    return database.get_all_sessions()

@app.get("/api/audio/{session_id}")
def get_audio(session_id: int):
    session = database.get_session(session_id)
    if not session or not session['audio_path'] or not os.path.exists(session['audio_path']):
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(session['audio_path'], media_type="audio/wav")

@app.post("/api/delete-audio/{session_id}")
def delete_audio(session_id: int):
    session = database.get_session(session_id)
    if session and session['audio_path'] and os.path.exists(session['audio_path']):
        try:
            os.remove(session['audio_path'])
            database.delete_audio_path(session_id)
            return {"message": "Audio deleted"}
        except Exception as e:
            return {"error": str(e)}
    return {"message": "Audio not found or already deleted"}

# Serve Frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

import sqlite3
import datetime
import json
import os

DB_PATH = "sias.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_type TEXT,
            start_time TEXT,
            end_time TEXT,
            summary TEXT,
            skills TEXT,
            status TEXT,
            raw_text TEXT,
            audio_path TEXT,
            availability TEXT,
            experience TEXT,
            json_data TEXT
        )
    ''')
    
    # Simple migration for existing tables
    try:
        c.execute("ALTER TABLE sessions ADD COLUMN audio_path TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE sessions ADD COLUMN availability TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE sessions ADD COLUMN experience TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE sessions ADD COLUMN json_data TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

def create_session(candidate_type):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    start_time = datetime.datetime.now().isoformat()
    c.execute('INSERT INTO sessions (candidate_type, start_time, status) VALUES (?, ?, ?)', 
              (candidate_type, start_time, "active"))
    session_id = c.lastrowid
    conn.commit()
    conn.close()
    return session_id

def update_session(session_id, summary, skills, raw_text, availability, experience, audio_path, json_data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    end_time = datetime.datetime.now().isoformat()
    c.execute('''
        UPDATE sessions 
        SET summary = ?, skills = ?, raw_text = ?, end_time = ?, status = 'completed',
            availability = ?, experience = ?, audio_path = ?, json_data = ?
        WHERE id = ?
    ''', (summary, skills, raw_text, end_time, availability, experience, audio_path, json_data, session_id))
    conn.commit()
    conn.close()

def set_processing_status(session_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE sessions SET status = 'processing' WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()

def delete_audio_path(session_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE sessions SET audio_path = NULL WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()

def get_all_sessions():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM sessions ORDER BY id DESC')
    rows = c.fetchall()
    sessions = []
    for row in rows:
        d = dict(row)
        # Parse JSON data if it exists
        if d.get("json_data"):
            try:
                d["json_data"] = json.loads(d["json_data"])
            except:
                d["json_data"] = None
        sessions.append(d)
    conn.close()
    return sessions

def get_session(session_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM sessions WHERE id = ?', (session_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

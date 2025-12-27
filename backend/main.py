from fastapi import FastAPI, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
import whisper
import sys
from loguru import logger

# Professional Logging Configuration
logger.remove()
logger.add(sys.stderr, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

from services.tts import tts_service
from fastapi.responses import FileResponse
import uuid
import os
import shutil

app = FastAPI()

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import sqlite3
from datetime import datetime

# Database Setup
DB_PATH = "data.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recordings (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            audio_path TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Load Whisper model (base for better accuracy)
model = whisper.load_model("base")

last_audio_path = None
last_audio_text = ""

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    global last_audio_path, last_audio_text
    # Save temporary file with unique Name to avoid collisions
    temp_path = f"temp_{uuid.uuid4()}_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # Transcribe (Forcing French)
        result = model.transcribe(temp_path, language="fr")
        text = result["text"]
        
        # Log the words as requested
        logger.info(f"STT Transcribed: {text}")
        
        # Keep this as a potential reference for TTS (Voice Cloning)
        # Convert to wav for F5-TTS compatibility
        ref_path = "last_voice_ref.wav"
        try:
            os.system(f"ffmpeg -y -i {temp_path} -ar 16000 -ac 1 {ref_path} > /dev/null 2>&1")
            last_audio_path = os.path.abspath(ref_path)
            last_audio_text = text
            logger.debug(f"Saved new voice reference: {last_audio_path}")
        except Exception as e:
            logger.error(f"Error preparing voice ref: {e}")

        return {"transcript": text}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.post("/recordings")
async def save_recording(request: Request):
    data = await request.json()
    text = data.get("text", "")
    id = str(uuid.uuid4())
    
    if not text:
        return {"error": "No text provided"}
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO recordings (id, text, audio_path) VALUES (?, ?, ?)', (id, text, last_audio_path))
    conn.commit()
    conn.close()
    
    logger.success(f"Backend | Saved recording {id}: {text[:30]}...")
    return {"status": "success", "id": id}

@app.get("/recordings")
async def get_recordings():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, text, created_at FROM recordings ORDER BY created_at DESC')
    rows = cursor.fetchall()
    conn.close()
    
    recordings = [{"id": r[0], "text": r[1], "created_at": r[2]} for r in rows]
    return recordings

@app.post("/synthesize")
async def synthesize(request: Request):
    data = await request.json()
    text = data.get("text", "")
    use_standard = data.get("use_standard", False)
    use_basic = data.get("basic", False) # New flag for ultra-fast gTTS
    
    if not text:
        return {"error": "No text provided"}

    output_path = f"output_{uuid.uuid4()}.wav"
    
    try:
        if use_basic:
            logger.info("Main | API Synthesis | Mode: BASIC (gTTS)")
            path = tts_service.synthesize_basic(text, output_path)
        else:
            logger.info(f"Main | API Synthesis | Mode: {'STANDARD' if use_standard else 'CLONE'} (F5-TTS)")
            path = tts_service.synthesize(
                text, 
                output_path, 
                ref_audio_path=last_audio_path, 
                ref_text=last_audio_text,
                use_standard=use_standard
            )
        
        if path and os.path.exists(path):
            return FileResponse(path, media_type="audio/wav")
        else:
            return {"error": "Synthesis failed"}
    except Exception as e:
        logger.error(f"Synthesis endpoint error: {e}")
        return {"error": str(e)}

@app.get("/")
def read_root():
    return {"status": "Backend is running with Whisper base and F5-TTS ready..."}

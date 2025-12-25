from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import whisper
from loguru import logger
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

# Load Whisper model (base for better accuracy)
model = whisper.load_model("base")

last_audio_path = None

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    global last_audio_path
    # Save temporary file with unique Name to avoid collisions
    import uuid
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
            logger.debug(f"Saved new voice reference: {last_audio_path}")
        except Exception as e:
            logger.error(f"Error preparing voice ref: {e}")

        return {"transcript": text}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.post("/synthesize")
async def synthesize_text(data: dict):
    text = data.get("text", "")
    if not text:
        return {"error": "No text provided"}
    
    output_filename = f"synth_{uuid.uuid4()}.wav"
    output_path = os.path.join(os.getcwd(), output_filename)
    
    try:
        # Use the last recorded voice as reference for Zero-Shot Voice Cloning!
        tts_service.synthesize(text, output_path, ref_audio_path=last_audio_path)
        return FileResponse(output_path, media_type="audio/wav", filename="speech.wav")
    except Exception as e:
        return {"error": str(e)}

@app.get("/")
def read_root():
    return {"status": "Backend is running with Whisper base and F5-TTS ready..."}

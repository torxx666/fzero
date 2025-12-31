import whisper
import os

try:
    model = whisper.load_model("base")
    path = "backend/standard_ref.wav"
    if os.path.exists(path):
        result = model.transcribe(path)
        print(f"TRANSCRIPTION_RESULT: {result['text'].strip()}")
    else:
        print("File not found.")
except Exception as e:
    print(f"Error: {e}")

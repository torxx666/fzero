from fastapi import FastAPI, UploadFile, File, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool # Pour exécuter les tâches lourdes sans bloquer
import whisper
import sys
from loguru import logger
import torch # Import de torch pour vérifier CUDA

# Configuration du logging professionnel (Loguru)
# On supprime le logger par défaut pour en ajouter un personnalisé
# qui affiche le temps, le niveau de log, le module, la fonction et la ligne.
logger.remove()
logger.add(sys.stderr, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

from services.tts import tts_service
from tasks import synthesize_task # Nouveau : Import de la tâche Celery
from celery.result import AsyncResult
from fastapi.responses import FileResponse
import uuid
import os
import shutil
import asyncio
import sqlite3
import shutil

app = FastAPI()

# --- WebSocket Management ---

class ConnectionManager:
    """
    Gère les connexions WebSocket actives pour envoyer des notifications
    en temps réel au frontend (ex: statut de la synthèse).
    """
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket: Client {client_id} connected.")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"WebSocket: Client {client_id} disconnected.")

    async def send_personal_message(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)

manager = ConnectionManager()

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Respond to ping if needed
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}")
        manager.disconnect(client_id)

# Configuration CORS (Cross-Origin Resource Sharing)
# Permet au frontend React (ou autre origine) de communiquer avec ce backend.
# Ici, on autorise tout ("*") pour le développement, ce qui est permissif.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import sqlite3
from datetime import datetime

# Configuration de la base de données SQLite
# C'est ici qu'on stockera l'historique des enregistrements.
DB_PATH = "data.db"

def init_db():
    """
    Initialise la base de données en créant la table 'recordings' si elle n'existe pas.
    Crée aussi la table 'voice_profiles' pour sauvegarder des voix.
    """
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
    
    # Nouvelle table pour les profil vocaux
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voice_profiles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            audio_path TEXT NOT NULL,
            ref_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# Appel de l'initialisation au démarrage du script
init_db()

# Chargement du modèle Whisper
# On utilise le modèle "base" qui offre un bon compromis vitesse/précision.
model = whisper.load_model("base")

# Variables globales pour garder en mémoire la dernière référence vocale
# Cela permet d'utiliser la voix de la dernière personne qui a parlé pour le TTS (clonage de voix).
last_audio_path = None
last_audio_text = ""
last_cleaned_path = None # Nouveau : pour stocker le chemin du fichier nettoyé pour écoute

# --- Fonctions Bloquantes (CPU Bound) déplacées ici pour être appelées via threadpool ---

def process_audio_cleaning(input_path: str, output_path: str) -> bool:
    """
    Applique le nettoyage FFmpeg (Haut-passe + Suppression silence).
    Retourne True si succès.
    """
    logger.info("Preprocessing | Cleaning audio (HighPass + Silence Removal)...")
    ffmpeg_cmd = (
        f"ffmpeg -y -i {input_path} "
        f"-af \"highpass=f=200, silenceremove=start_periods=1:stop_periods=-1:start_threshold=-50dB:stop_threshold=-50dB:stop_duration=0.5\" "
        f"{output_path} > /dev/null 2>&1"
    )
    exit_code = os.system(ffmpeg_cmd)
    return exit_code == 0 and os.path.exists(output_path)

def process_transcription(audio_path: str) -> str:
    """
    Exécute la transcription Whisper (lourd CPU/GPU).
    """
    result = model.transcribe(audio_path, language="fr")
    return result["text"]

def process_voice_ref_conversion(input_path: str, output_path: str):
    """
    Convertit l'audio en format compatible F5-TTS (16kHz mono).
    """
    os.system(f"ffmpeg -y -i {input_path} -ar 16000 -ac 1 {output_path} > /dev/null 2>&1")

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Endpoint pour transcrire un fichier audio envoyé par le client.
    Optimisé avec run_in_threadpool pour ne pas bloquer l'event loop.
    """
    global last_audio_path, last_audio_text, last_cleaned_path
    
    # Création d'un nom de fichier temporaire unique
    temp_path = f"temp_{uuid.uuid4()}_{file.filename}"
    cleaned_path = f"cleaned_{uuid.uuid4()}.wav"
    
    # Écriture du fichier reçu sur le disque (IO bound, mais rapide en local, on garde en async)
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # 1. Nettoyage audio (BLOQUANT -> THREAD)
        cleaning_success = await run_in_threadpool(process_audio_cleaning, temp_path, cleaned_path)
        
        # Si le nettoyage a échoué (ex: fichier vide), on utilise l'original
        final_input = cleaned_path if cleaning_success else temp_path
        if final_input == cleaned_path:
             last_cleaned_path = os.path.abspath(cleaned_path)
             logger.debug(f"Audio cleaning successful: {last_cleaned_path}")

        # 2. Transcription Whisper (BLOQUANT -> THREAD)
        text = await run_in_threadpool(process_transcription, final_input)
        
        logger.info(f"STT Transcribed: {text}")
        
        # 3. Préparation référence vocale (BLOQUANT -> THREAD)
        ref_path = "last_voice_ref.wav"
        try:
            await run_in_threadpool(process_voice_ref_conversion, final_input, ref_path)
            
            last_audio_path = os.path.abspath(ref_path)
            last_audio_text = text
            logger.debug(f"Saved new voice reference: {last_audio_path}")
        except Exception as e:
            logger.error(f"Error preparing voice ref: {e}")

        return {"transcript": text, "cleaned_available": (final_input == cleaned_path)}
    finally:
        # Nettoyage : suppression du fichier temporaire reçu
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.get("/listen_cleaned")
async def listen_cleaned():
    """
    Endpoint pour écouter la dernière version nettoyée de l'audio.
    """
    global last_cleaned_path
    if last_cleaned_path and os.path.exists(last_cleaned_path):
        return FileResponse(last_cleaned_path, media_type="audio/wav")
    else:
        return {"error": "No cleaned audio available yet."}

@app.post("/recordings")
async def save_recording(request: Request):
    """
    Endpoint pour sauvegarder un enregistrement.
    """
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
    """
    Endpoint pour récupérer l'historique des enregistrements.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, text, created_at FROM recordings ORDER BY created_at DESC')
    rows = cursor.fetchall()
    conn.close()
    
    recordings = [{"id": r[0], "text": r[1], "created_at": r[2]} for r in rows]
    return recordings

# --- Gestion des Profils Vocaux ---

@app.post("/voices")
async def save_voice(request: Request):
    """
    Sauvegarde la voix courante (last_audio_path) comme un nouveau profil.
    """
    global last_audio_path, last_audio_text
    
    data = await request.json()
    name = data.get("name", "Ma Voix")
    
    if not last_audio_path or not os.path.exists(last_audio_path):
        return {"error": "No voice to save. Record or upload audio first."}
    
    id = str(uuid.uuid4())
    # On copie le fichier temporaire vers un stockage permanent
    saved_path = f"voice_{id}.wav"
    shutil.copy2(last_audio_path, saved_path)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO voice_profiles (id, name, audio_path, ref_text) VALUES (?, ?, ?, ?)', 
                   (id, name, os.path.abspath(saved_path), last_audio_text))
    conn.commit()
    conn.close()
    
    return {"status": "success", "id": id, "name": name}

@app.get("/voices")
async def get_voices():
    """
    Listening all saved voice profiles.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM voice_profiles ORDER BY created_at DESC')
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1]} for r in rows]

@app.delete("/voices/{voice_id}")
async def delete_voice(voice_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Récupérer le chemin du fichier pour le supprimer
    cursor.execute('SELECT audio_path FROM voice_profiles WHERE id = ?', (voice_id,))
    row = cursor.fetchone()
    
    if row:
        path = row[0]
        if os.path.exists(path):
            os.remove(path)
            
    cursor.execute('DELETE FROM voice_profiles WHERE id = ?', (voice_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}

@app.post("/synthesize")
async def synthesize_text(request: Request):
    """
    Point d'entrée principal pour la synthèse vocale (TTS).
    MODE DECOUPLE : Utilise Celery pour déléguer le travail aux workers.
    """
    logger.info("Synthesis | Incoming request received")
    data = await request.json()
    text = data.get("text")
    use_basic = data.get("use_basic", False)
    use_standard = data.get("use_standard", False)
    voice_id = data.get("voice_id")
    client_id = data.get("client_id")

    async def notify_status(status: str):
        """Envoie une mise à jour de statut au client via WebSocket."""
        if client_id:
            await manager.send_personal_message({"status": status}, client_id)

    if not text:
        return {"error": "No text provided"}

    output_path = f"output_{uuid.uuid4()}.wav"
    
    # Sélection de la voix (Logique simplifiée pour l'exemple)
    ref_audio = last_audio_path
    ref_text = last_audio_text
    
    if voice_id:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT audio_path, ref_text FROM voice_profiles WHERE id = ?', (voice_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            ref_audio, ref_text = row[0], row[1]

    engine = data.get("engine", "f5")
    if use_basic: engine = "basic"

    try:
        # --- DELEGATION A CELERY ---
        logger.info(f"Synthesis | Queuing task for engine: {engine}")
        await notify_status(f"Mise en file d'attente ({engine})...")
        
        task = synthesize_task.delay(
            engine, text, os.path.abspath(output_path), 
            ref_audio, ref_text, use_standard
        )
        
        # --- SURVEILLANCE DE LA TACHE (Status Relay) ---
        # On surveille la tâche Celery et on renvoie les infos via WebSocket
        # Dès que c'est fini, on renvoie le fichier.
        
        last_status = ""
        while not task.ready():
            # On récupère l'état 'meta' défini dans synthesize_task
            result = AsyncResult(task.id)
            if result.info and isinstance(result.info, dict):
                current_status = result.info.get('status', "")
                if current_status != last_status:
                    await notify_status(current_status)
                    last_status = current_status
            
            await asyncio.sleep(0.5) # Ne pas saturer Redis
        
        # Récupération du résultat final
        final_result = task.get()
        
        if final_result.get('status') == 'Terminé':
            path = final_result.get('path')
            if path and os.path.exists(path):
                logger.success(f"Synthesis | Worker success: {path}")
                await notify_status("Synthèse terminée ! Envoi de l'audio...")
                return FileResponse(path, media_type="audio/wav")
        
        error_msg = final_result.get('error', 'Unknown worker error')
        logger.error(f"Synthesis | Worker failure: {error_msg}")
        await notify_status(f"Erreur Worker : {error_msg}")
        return {"error": error_msg}

    except Exception as e:
        logger.error(f"Synthesis | Gateway Error: {e}")
        await notify_status(f"Erreur : {str(e)}")
        return {"error": str(e)}

@app.get("/")
def read_root():
    """
    Endpoint de santé pour vérifier que le backend tourne.
    Renvoie maintenant les infos sur CUDA.
    """
    cuda_available = torch.cuda.is_available()
    device_name = torch.cuda.get_device_name(0) if cuda_available else "CPU"
    return {
        "status": "Backend is running",
        "cuda_available": cuda_available,
        "device_name": device_name
    }

import os
import time
from celery_app import celery
from services.tts import tts_service
from loguru import logger

@celery.task(bind=True)
def synthesize_task(self, engine, text, output_path, ref_audio_path, ref_text, use_standard):
    """
    Tâche Celery pour exécuter la synthèse vocale en arrière-plan.
    """
    logger.info(f"Celery Task | Starting {engine} synthesis...")
    
    # Callback pour envoyer des mises à jour de statut (simulé via Celery state)
    # L'API FastAPI pourra lire cet état ou on pourra utiliser Redis directement.
    self.update_state(state='PROGRESS', meta={'status': f'Démarrage avec {engine}'})
    
    try:
        if engine == "f5":
             self.update_state(state='PROGRESS', meta={'status': 'Préparation du modèle IA...'})

        # Appel au service TTS (identique à l'ancien code mais dans un worker)
        path = tts_service.synthesize_with_engine(
            engine=engine,
            text=text,
            output_path=output_path,
            ref_audio_path=ref_audio_path,
            ref_text=ref_text,
            use_standard=use_standard
        )
        
        if path and os.path.exists(path):
            logger.success(f"Celery Task | Success: {path}")
            return {'status': 'Terminé', 'path': path}
        else:
            logger.error(f"Celery Task | {engine} failed")
            return {'status': 'Erreur', 'error': 'Synthesis failed'}
            
    except Exception as e:
        logger.error(f"Celery Task | Critical Failure: {e}")
        return {'status': 'Erreur', 'error': str(e)}

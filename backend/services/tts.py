import torch
import torchaudio
from f5_tts.model import DiT
from f5_tts.infer.utils_infer import load_model, infer_process
import os

from loguru import logger
import time

class TTSService:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_name = "F5-TTS"
        self.model_ckpt = "hf://SWivid/F5-TTS/model_1200000.safetensors"
        self.model = None
        self.vocoder = None
        self.is_loading = False
        
    def _ensure_model_loaded(self):
        if self.model is None and not self.is_loading:
            self.is_loading = True
            logger.info(f"Starting to load {self.model_name}...")
            logger.info(f"Device: {self.device}")
            logger.info(f"Checkpoint: {self.model_ckpt}")
            logger.warning("Initial download is ~2GB. Progress may not show in logs but is happening...")
            
            start_time = time.time()
            try:
                self.model, self.vocoder = load_model(
                    model_name=self.model_name,
                    ckpt_path=self.model_ckpt,
                    device=self.device
                )
                end_time = time.time()
                logger.success(f"Successfully loaded in {end_time - start_time:.2f} seconds.")
            except Exception as e:
                logger.critical(f"CRITICAL ERROR loading model: {e}")
                self.is_loading = False
                raise
            finally:
                self.is_loading = False

    def synthesize(self, text: str, output_path: str, ref_audio_path: str = None, ref_text: str = ""):
        self._ensure_model_loaded()
        
        # F5-TTS needs a reference audio for voice cloning. 
        # If none provided, synthesis won't work well or at all.
        if not ref_audio_path or not os.path.exists(ref_audio_path):
             logger.warning("No reference audio provided for synthesis. F5-TTS requires a voice to clone.")
             return None

        logger.info(f"Synthesizing with reference: {ref_audio_path}")
        try:
            audio, sr, _ = infer_process(
                ref_audio_path, 
                ref_text, 
                text, 
                self.model, 
                self.vocoder,
                device=self.device
            )
            torchaudio.save(output_path, audio.unsqueeze(0), sr)
            return output_path
        except Exception as e:
            logger.error(f"Synthesis error: {e}")
            raise

tts_service = TTSService()

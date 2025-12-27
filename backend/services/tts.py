import torch
import torchaudio
from f5_tts.model import DiT
from f5_tts.infer.utils_infer import load_model, load_vocoder, infer_process
from huggingface_hub import hf_hub_download
import os

from loguru import logger
import time

class TTSService:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_name = "F5-TTS"
        self.repo_id = "SWivid/F5-TTS"
        self.model_ckpt = "F5TTS_Base/model_1200000.safetensors"
        self.model = None
        self.vocoder = None
        self.is_loading = False
        
    def _ensure_model_loaded(self):
        if self.model is None and not self.is_loading:
            self.is_loading = True
            logger.info("Initializing F5-TTS Service (Low-Level mode)...")
            
            try:
                # 1. Download/Cache Checkpoint
                logger.info(f"Checking checkpoint: {self.model_ckpt}")
                ckpt_path = hf_hub_download(repo_id=self.repo_id, filename=self.model_ckpt)
                
                # 2. Setup DiT Model Config
                model_cfg = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)
                
                # 3. Load Model
                logger.info(f"Loading DiT model on {self.device}...")
                self.model = load_model(
                    model_cls=DiT,
                    model_cfg=model_cfg,
                    ckpt_path=ckpt_path,
                    device=self.device,
                    mel_spec_type="vocos"
                )
                
                # 4. Load Vocoder separately (load_model only returns the model)
                logger.info("Loading Vocoder (Vocos)...")
                self.vocoder = load_vocoder(vocoder_name="vocos", device=self.device)
                
                logger.success(f"F5-TTS Service ready for voice cloning. CUDA: {torch.cuda.is_available()}")
            except Exception as e:
                logger.critical(f"TTS Initialization failed: {e}")
                import traceback
                logger.error(traceback.format_exc())
                self.model = None
                raise
            finally:
                self.is_loading = False

    def _clean_text(self, text: str) -> str:
        """F5-TTS is sensitive to symbols and numbers. Basic cleaning helps."""
        import re
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text)
        # Ensure punctuation is followed by a space
        text = re.sub(r'([.,!?])(?=[^\s])', r'\1 ', text)
        cleaned = text.strip()
        if not cleaned:
            return " "
        return cleaned

    def synthesize_basic(self, text: str, output_path: str):
        """Ultra-fast concatenative TTS using gTTS for instant testing."""
        logger.info(f"Synthesizing Basic (gTTS) | Text: '{text[:50]}'")
        try:
            from gtts import gTTS
            tts = gTTS(text, lang='fr')
            tts.save(output_path)
            return output_path
        except Exception as e:
            logger.error(f"Basic TTS Failure: {e}")
            return None

    def synthesize(self, text: str, output_path: str, ref_audio_path: str = None, ref_text: str = "", use_standard: bool = False):
        self._ensure_model_loaded()
        
        # 1. Clean input text
        text = self._clean_text(text)
        
        # 2. Determine reference audio and text
        final_ref_audio = ref_audio_path
        final_ref_text = ref_text
        
        # Check for standard voice availability (HQ gTTS-generated wav)
        standard_path = "/app/standard_ref.wav"
        has_standard = os.path.exists(standard_path) and os.path.getsize(standard_path) > 1000
        
        if use_standard:
            if has_standard:
                final_ref_audio = standard_path
                final_ref_text = "La qualité de la voix est primordiale pour une expérience utilisateur réussie."
                logger.debug(f"Synthesis | Mode: Standard | Using '{standard_path}'")
            else:
                logger.warning("Standard Voice requested but not found. Falling back to User-Shot.")
                use_standard = False

        if not use_standard:
            if not final_ref_audio or not os.path.exists(final_ref_audio):
                fallback_user_ref = "/app/last_voice_ref.wav"
                if os.path.exists(fallback_user_ref):
                    final_ref_audio = fallback_user_ref
                    logger.debug(f"Synthesis | Mode: Clone | Using fallback '{fallback_user_ref}'")

        if not final_ref_audio or not os.path.exists(final_ref_audio):
             logger.error("TRANS-FATAL: No reference audio available.")
             return None

        final_ref_text = self._clean_text(final_ref_text)

        # 0.8 is a balanced speed for CPU stability (1.0 was buggy, 0.6 was too slow).
        speed = 0.8
        # 32 steps is necessary for stable convergence on CPU (16 caused 'Chinese' effect).
        nfe = 32

        logger.info(f"Synthesizing | Mode: {'Standard' if use_standard else 'Clone'} | Speed: {speed} | NFE: {nfe}")
        
        try:
            audio, sr, _ = infer_process(
                ref_audio=final_ref_audio, 
                ref_text=final_ref_text, 
                gen_text=text, 
                model_obj=self.model, 
                vocoder=self.vocoder,
                device=self.device,
                speed=speed,
                nfe_step=nfe
            )
            
            if not torch.is_tensor(audio):
                audio = torch.from_numpy(audio)
            
            if audio.ndim == 1:
                audio = audio.unsqueeze(0)
            
            torchaudio.save(output_path, audio, sr)
            return output_path
        except Exception as e:
            logger.exception(f"Synthesis Engine Failure: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Synthesis error: {e}")
            raise

tts_service = TTSService()

import torch
import torchaudio
from f5_tts.model import DiT
from f5_tts.infer.utils_infer import load_model, load_vocoder, infer_process
from huggingface_hub import hf_hub_download
import os

from loguru import logger
import time

class TTSService:
    """
    Service gérant la synthèse vocale (Text-to-Speech).
    Il supporte deux modes :
    1. Basique (concaténatif) via gTTS pour la rapidité.
    2. Avancé (génératif) via F5-TTS pour le clonage de voix et la haute qualité.
    """
    def __init__(self):
        # Détection automatique du GPU (CUDA) ou CPU
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Configuration du modèle F5-TTS
        self.model_name = "F5-TTS"
        self.repo_id = "SWivid/F5-TTS"
        self.model_ckpt = "F5TTS_Base/model_1200000.safetensors"
        
        # Le modèle et le vocodeur sont chargés à la demande (lazy loading)
        self.model = None
        self.vocoder = None
        self.xtts_model = None
        self.is_loading = False
        
    def _ensure_model_loaded(self):
        """
        Vérifie si le modèle F5-TTS est chargé. Si non, le charge en mémoire.
        Cette méthode est appelée avant chaque synthèse 'avancée'.
        """
        if self.model is None and not self.is_loading:
            self.is_loading = True
            logger.info("Initializing F5-TTS Service (Low-Level mode)...")
            
            try:
                # 1. Téléchargement ou vérification du cache du checkpoint du modèle
                logger.info(f"Checking checkpoint: {self.model_ckpt}")
                ckpt_path = hf_hub_download(repo_id=self.repo_id, filename=self.model_ckpt)
                
                # 2. Configuration de l'architecture du modèle DiT (Diffusion Transformer)
                # Ces paramètres doivent correspondre à ceux utilisés lors de l'entraînement
                model_cfg = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)
                
                # 3. Chargement du modèle principal (DiT)
                logger.info(f"Loading DiT model on {self.device}...")
                self.model = load_model(
                    model_cls=DiT,
                    model_cfg=model_cfg,
                    ckpt_path=ckpt_path,
                    device=self.device,
                    mel_spec_type="vocos"
                )
                
                # 4. Chargement du Vocodeur (Vocos) séparément
                # Le vocodeur transforme les spectrogrammes générés par le DiT en forme d'onde audio
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

    def _ensure_xtts_loaded(self):
        if self.xtts_model is None:
            logger.info("Initializing Coqui XTTS-v2 (Lazy Load)...")
            from TTS.api import TTS
            try:
                # model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
                self.xtts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)
                logger.success(f"XTTS-v2 Ready. CUDA: {torch.cuda.is_available()}")
            except Exception as e:
                logger.error(f"XTTS-v2 Load failed: {e}")
                raise

    def _clean_text(self, text: str) -> str:
        """
        Nettoie le texte d'entrée.
        F5-TTS peut être sensible aux symboles et nombres, un nettoyage basique aide.
        """
        import re
        # Remplace les espaces multiples par un seul
        text = re.sub(r'\s+', ' ', text)
        # S'assure que la ponctuation est suivie d'un espace
        text = re.sub(r'([.,!?])(?=[^\s])', r'\1 ', text)
        cleaned = text.strip()
        if not cleaned:
            return " "
        return cleaned

    def synthesize_basic(self, text: str, output_path: str):
        """
        Synthèse ultra-rapide utilisant gTTS (Google TTS).
        Utile pour des tests rapides ou si le GPU n'est pas disponible.
        """
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
        """
        Synthèse avancée utilisant F5-TTS pour le clonage de voix.
        
        Args:
            text: Le texte à synthétiser.
            output_path: Où sauvegarder le fichier wav généré.
            ref_audio_path: Chemin vers l'audio de référence (la voix à cloner).
            ref_text: Transcription de l'audio de référence (pour guider le modèle).
            use_standard: Si True, utilise une voix standard pré-enregistrée au lieu du clonage.
        """
        self._ensure_model_loaded()
        
        # 1. Nettoyage du texte cible
        text = self._clean_text(text)
        
        # 2. Détermination de l'audio et du texte de référence
        final_ref_audio = ref_audio_path
        final_ref_text = ref_text
        
        # Vérification si la voix standard est demandée et disponible
        # La voix standard est un fichier wav de haute qualité pré-généré
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

        # Si pas de mode standard ou standard non trouvé, on tente d'utiliser la voix de l'utilisateur
        if not use_standard:
            if not final_ref_audio or not os.path.exists(final_ref_audio):
                fallback_user_ref = "/app/last_voice_ref.wav"
                if os.path.exists(fallback_user_ref):
                    final_ref_audio = fallback_user_ref
                    logger.debug(f"Synthesis | Mode: Clone | Using fallback '{fallback_user_ref}'")

        # Si toujours aucune référence audio, on ne peut pas cloner -> Erreur
        if not final_ref_audio or not os.path.exists(final_ref_audio):
             logger.error("TRANS-FATAL: No reference audio available.")
             return None

        final_ref_text = self._clean_text(final_ref_text)

        # Paramètres d'inférence
        # speed: Vitesse de la parole (0.8 est un bon équilibre, 1.0 peut être instable)
        speed = 0.8
        # nfe (Number of Function Evaluations): Nombre d'étapes de diffusion.
        # 32 étapes sont nécessaires pour une bonne convergence sur CPU sans artefacts.
        nfe = 32

        logger.info(f"Synthesizing | Mode: {'Standard' if use_standard else 'Clone'} | Speed: {speed} | NFE: {nfe}")
        
        try:
            # Appel au processus d'inférence de F5-TTS
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
            
            # Conversion du résultat en tenseur si nécessaire
            if not torch.is_tensor(audio):
                audio = torch.from_numpy(audio)
            
            # Ajustement des dimensions pour torchaudio (C, T)
            if audio.ndim == 1:
                audio = audio.unsqueeze(0)
            
            # Sauvegarde du fichier audio généré
            torchaudio.save(output_path, audio, sr)
            return output_path
        except Exception as e:
            logger.exception(f"Synthesis Engine Failure: {str(e)}")
            raise

    def synthesize_xtts(self, text: str, output_path: str, ref_audio_path: str):
        """
        Synthèse avancée via Coqui XTTS-v2.
        Offre un clonage de voix très performant et multilingue.
        """
        self._ensure_xtts_loaded()
        logger.info(f"Synthesis XTTS-v2 | Start | Text: '{text[:50]}...'")
        start_time = time.time()
        try:
            self.xtts_model.tts_to_file(
                text=text,
                speaker_wav=ref_audio_path,
                language="fr",
                file_path=output_path
            )
            duration = time.time() - start_time
            logger.success(f"Synthesis XTTS-v2 | Complete in {duration:.2f}s")
            return output_path
        except Exception as e:
            logger.error(f"Synthesis XTTS-v2 | Failure: {e}")
            return None

    def synthesize_with_engine(self, engine: str, text: str, output_path: str, **kwargs):
        """
        Point d'entrée universel pour choisir le moteur de synthèse.
        Gère le dispatching vers F5, XTTS ou gTTS.
        """
        logger.debug(f"TTS Dispatcher | Engine: {engine} | Target: {output_path}")
        if engine == "xtts":
            ref_path = kwargs.get("ref_audio_path")
            if not ref_path or not os.path.exists(ref_path):
                # Try fallback
                ref_path = "/app/last_voice_ref.wav"
            
            if not os.path.exists(ref_path):
                logger.error("XTTS Error: No voice reference available.")
                return None
            return self.synthesize_xtts(text, output_path, ref_path)
        
        elif engine == "basic":
            return self.synthesize_basic(text, output_path)
        
        else: # Default F5-TTS
            return self.synthesize(
                text, 
                output_path, 
                ref_audio_path=kwargs.get("ref_audio_path"),
                ref_text=kwargs.get("ref_text", ""),
                use_standard=kwargs.get("use_standard", False)
            )

tts_service = TTSService()

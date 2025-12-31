# F-Zero: Voice Cloning Studio

Une application locale de clonage de voix haute qualité utilisant F5-TTS et Whisper.

## Fonctionnalités Clés

*   **Clonage de Voix Instantané** : Enregistrez 5 secondes, l'IA clone votre voix.
*   **Qualité Studio (24kHz)** : Traitement audio haute définition pour éviter l'effet "téléphone".
*   **Optimisation GPU Low-VRAM** : Utilise le **Half Precision (FP16)** pour tourner rapidement même sur des cartes 4GB (GTX 1650 Super).
*   **Modes de Synthèse** :
    *   **Mode Ma Voix** : Clone votre voix basée sur votre dernier enregistrement.
    *   **Mode Pro** : Utilise également votre voix comme référence (pour garantir la qualité) mais force les paramètres de qualité maximale (64 steps) pour un rendu ultra-clair.
    *   **Lecture Instantanée** : Synthèse basique (rapide, voix robotique).

## Installation & Démarrage

Nécessite [Docker Desktop](https://www.docker.com/products/docker-desktop/) installé avec le support WSL2.

```powershell
# Démarrer l'application (et compiler si besoin)
docker-compose up --build
```

L'application sera accessible sur : `http://localhost (Port 80/5173)`

## Troubleshooting / Problèmes Fréquents

### "L'audio est incompréhensible / baragouine"
*   **Cause** : L'enregistrement de référence est trop court ou de mauvaise qualité.
*   **Solution** : Enregistrez une phrase de **plus de 5 secondes**. L'IA a besoin de contexte pour poser sa voix.

### "C'est très lent (20s+ par phrase)"
*   **Cause** : L'application tourne sur le CPU ou la VRAM est saturée.
*   **Solution** :
    1.  Vérifiez que votre GPU est bien détecté (`nvidia-smi` dans le container).
    2.  L'application est configurée pour utiliser FP16 automatiquement si un GPU Nvidia est détecté.
    3.  Sur les cartes 4GB, fermez les autres applications gourmandes (navigateurs, jeux).

### "Je ne vois pas l'activité GPU dans le Task Manager"
*   **Info** : Windows affiche par défaut le graphique "3D".
*   **Solution** : Allez dans l'onglet "Performance" -> "GPU" -> Changez un des graphiques "3D" en "**Cuda**" ou "**Compute_0**" pour voir la charge réelle.

## Architecture
*   **Frontend** : React + Vite + TailwindCSS (Interface Cyberpunk/Pro).
*   **Backend** : FastAPI + Celery + Redis.
*   **IA** :
    *   **TTS** : F5-TTS (Diffusion Transformer).
    *   **STT** : OpenAI Whisper (Base).

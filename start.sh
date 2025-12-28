#!/bin/bash

# Script de gestion du Voice AI Studio
# Permet de lancer en mode CPU ou GPU (NVIDIA)

MODE="cpu"
if [[ "$1" == "--gpu" ]]; then
    MODE="gpu"
fi

echo "--- Voice AI Studio ---"
echo "Mode selectionné : $MODE"

if [[ "$MODE" == "gpu" ]]; then
    # Vérification de nvidia-smi
    if command -v nvidia-smi &> /dev/null; then
        echo "✅ NVIDIA GPU détecté."
        docker-compose -f docker-compose.yml -f docker-compose.nvidia.yml up -d --build
    else
        echo "❌ Erreur : nvidia-smi non trouvé. Le driver NVIDIA/NVIDIA Container Toolkit n'est peut-être pas installé."
        echo "Tentative de repli sur le mode CPU..."
        docker-compose up -d --build
    fi
else
    echo "ℹ️ Lancement en mode CPU (Standard)."
    docker-compose up -d --build
fi

echo "-----------------------"
echo "Application lancée !"
echo "API : http://localhost:8000"
echo "STUDIO : http://localhost:5173"
echo "Logs : docker-compose logs -f"

# Arrête proprement tous les conteneurs
docker-compose down

# Force le nettoyage des conteneurs orphelins si nécessaire
docker system prune -f

echo "GPU Resources Released. You can now restart."

#!/usr/bin/env bash
# Copia i backup giornalieri fuori dal server (eseguire dal TUO computer, non dal server):
#   bash deploy/backup-offsite.sh utente@ip-server
# Richiede accesso SSH al server. Nessun segreto viene copiato (solo i database in data/backups).
set -euo pipefail
SERVER="${1:?uso: backup-offsite.sh utente@server}"
DEST="${2:-./atlas-backups}"
mkdir -p "$DEST"
ssh "$SERVER" 'cd ~/atlas && docker compose -f deploy/docker-compose.yml exec -T atlas python -m atlas backup >/dev/null && docker compose -f deploy/docker-compose.yml cp atlas:/app/data/backups /tmp/atlas-backups'
scp -r "$SERVER:/tmp/atlas-backups/*" "$DEST/"
echo "Backup copiati in $DEST"

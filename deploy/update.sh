#!/usr/bin/env bash
# Aggiornamento sicuro: backup → nuova versione → verifica → ritorno automatico alla versione precedente se non sana.
set -euo pipefail
DIR="${ATLAS_DIR:-$HOME/atlas}"
BRANCH="${ATLAS_BRANCH:-claude/atlas-crypto-trading-system-6ugata}"
COMPOSE="docker compose -f deploy/docker-compose.yml"
cd "$DIR"

PREV=$(git rev-parse HEAD)
echo "==> Backup del database"
$COMPOSE exec -T atlas python -m atlas backup || echo "(backup non riuscito: servizio non attivo?)"

echo "==> Aggiornamento del codice da $BRANCH"
git fetch --quiet origin "$BRANCH"
git checkout --quiet "$BRANCH"
git pull --quiet --ff-only origin "$BRANCH"
NEW=$(git rev-parse HEAD)
[ "$PREV" = "$NEW" ] && { echo "Già aggiornato ($NEW)."; exit 0; }

$COMPOSE up -d --build
echo "==> Verifica della nuova versione"
for i in $(seq 1 30); do
  sleep 10
  if $COMPOSE exec -T atlas python -m atlas healthcheck >/dev/null 2>&1; then
    echo "Aggiornato a $NEW e sano."; exit 0
  fi
done
echo "Nuova versione non sana: ritorno a $PREV" >&2
git checkout --quiet "$PREV"
$COMPOSE up -d --build
exit 1

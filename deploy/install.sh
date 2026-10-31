#!/usr/bin/env bash
# Installazione di ATLAS (paper trading) su un server Ubuntu/Debian (x86_64 o ARM64).
# Uso:  curl -fsSL https://raw.githubusercontent.com/Mdalbianco/Atlas/<branch>/deploy/install.sh | bash
#  oppure, dopo aver clonato il repository:  bash deploy/install.sh
# Idempotente: si può rieseguire senza danni. Non crea risorse a pagamento e non tocca segreti esistenti.
set -euo pipefail

REPO_URL="${ATLAS_REPO_URL:-https://github.com/Mdalbianco/Atlas.git}"
BRANCH="${ATLAS_BRANCH:-claude/atlas-crypto-trading-system-6ugata}"
DIR="${ATLAS_DIR:-$HOME/atlas}"

echo "==> 1/5 Docker"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER" || true
  echo "Docker installato. Se il comando successivo dà 'permission denied', esci e rientra nella sessione SSH, poi rilancia lo script."
fi

echo "==> 2/5 Codice"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" fetch --quiet origin "$BRANCH"
  git -C "$DIR" checkout --quiet "$BRANCH"
  git -C "$DIR" pull --quiet --ff-only origin "$BRANCH"
else
  git clone --quiet --branch "$BRANCH" "$REPO_URL" "$DIR"
fi
cd "$DIR"

echo "==> 3/5 Configurazione"
if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo "Creato $DIR/.env (permessi 600). Inserisci TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ALLOWED_USERS, TELEGRAM_ADMIN_USERS:"
  echo "   nano $DIR/.env"
  echo "poi rilancia: bash $DIR/deploy/install.sh"
  exit 0
fi
chmod 600 .env
if grep -qE '^ATLAS_MODE=' .env && ! grep -qE '^ATLAS_MODE=paper\s*$' .env; then
  echo "ERRORE: ATLAS_MODE in .env deve essere 'paper'." >&2; exit 1
fi

echo "==> 4/5 Avvio"
docker compose -f deploy/docker-compose.yml up -d --build

echo "==> 5/5 Verifica (attendo il primo ciclo)"
for i in $(seq 1 30); do
  if docker compose -f deploy/docker-compose.yml exec -T atlas python -m atlas healthcheck >/dev/null 2>&1; then
    docker compose -f deploy/docker-compose.yml exec -T atlas python -m atlas healthcheck
    echo "ATLAS è attivo. Log: docker compose -f $DIR/deploy/docker-compose.yml logs -f"
    exit 0
  fi
  sleep 10
done
echo "ATTENZIONE: nessun heartbeat dopo 5 minuti. Controlla i log:" >&2
docker compose -f deploy/docker-compose.yml logs --tail 50 >&2
exit 1

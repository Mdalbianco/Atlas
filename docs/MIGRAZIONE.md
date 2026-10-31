# Aggiornamento del Codespace e trasferimento sul server 24/7

Ogni riquadro è **un blocco da copiare e incollare** in un terminale. Il testo prima del riquadro indica
**dove** incollarlo. Nessun comando stampa o copia i tuoi segreti; il file `.env` non viene mai
sovrascritto.

---

## Parte A — Aggiornare il Codespace ad ATLAS 1.1.x

Dove: **terminale del Codespace** (github.com → il tuo codespace → menu ☰ → Terminal → New Terminal).
Se ATLAS è già in esecuzione in un altro terminale, per ora lascialo acceso.

**A1. Controllo dello stato attuale** (non modifica nulla)
```bash
cd /workspaces/Atlas && git branch --show-current && git log --oneline -1 && git status --short && ls data 2>/dev/null; grep -E '^ATLAS_' .env
```
Se `git status --short` stampa righe che iniziano con `M`, hai modifiche locali: il blocco A3 le mette da parte.
L'ultimo comando mostra solo le impostazioni `ATLAS_*` (nessun token).

**A2. Backup recuperabile** (copia `.env`, dati e modifiche locali fuori dal repository)
```bash
cd /workspaces/Atlas && B=/workspaces/atlas-backup-$(date +%Y%m%d-%H%M) && mkdir -p "$B" && cp .env "$B/env.backup" && chmod 600 "$B/env.backup" && { [ -d data ] && cp -a data "$B/data" || true; } && git diff > "$B/modifiche-locali.diff" && echo "Backup creato in $B" && ls -la "$B"
```

**A3. Fermare ATLAS**: nel terminale in cui ATLAS è in esecuzione premi **Ctrl+C** e attendi il prompt.
(Il bot resterà spento solo per qualche minuto.)

**A4. Aggiornare il codice** (`.env` e `data/` non sono toccati: sono esclusi da Git)
```bash
cd /workspaces/Atlas && git stash push -m "locale prima di 1.1.x" ; git fetch origin claude/atlas-crypto-trading-system-6ugata && git checkout claude/atlas-crypto-trading-system-6ugata && git pull --ff-only origin claude/atlas-crypto-trading-system-6ugata && pip install -q -r requirements-dev.txt && git log --oneline -1
```
(Se compare "No local changes to save" va bene.)

**A5. Attivare tutte e cinque le strategie con validazione obbligatoria**
Il `.env` creato con la versione 1.0 conteneva `ATLAS_STRATEGIES=trend_pullback,breakout`. Questo blocco
modifica **solo** quella riga e le due opzioni di validazione/ombra, lasciando intatto tutto il resto
(il backup è già in A2):
```bash
cd /workspaces/Atlas && python3 - <<'EOF'
from pathlib import Path
p = Path(".env"); lines = p.read_text().splitlines()
want = {"ATLAS_STRATEGIES": "trend_following,trend_pullback,breakout,mean_reversion,volatility_squeeze",
        "ATLAS_REQUIRE_VALIDATION": "true", "ATLAS_SHADOW_STRATEGIES": "true", "ATLAS_MODE": "paper"}
seen = set(); out = []
for line in lines:
    key = line.split("=", 1)[0].strip()
    if key in want:
        out.append(f"{key}={want[key]}"); seen.add(key)
    else:
        out.append(line)
out += [f"{k}={v}" for k, v in want.items() if k not in seen]
p.write_text("\n".join(out) + "\n"); p.chmod(0o600)
print("Aggiornate:", ", ".join(want))
EOF
```

**A6. Verifica completa**
```bash
cd /workspaces/Atlas && python -m pytest -q && python -m atlas doctor
```
Deve finire con `passed` e con `Esito: tutto a posto.` (accanto a Telegram deve comparire il nome del tuo bot).
Se compare "Variabili ATLAS_* non riconosciute", correggi nel `.env` il nome indicato.

**A7. Ripartire**
```bash
cd /workspaces/Atlas && python -m atlas run
```
Su Telegram prova: `/status`, `/strategie` (5 strategie, tutte "solo portafoglio ombra"), `/diagnosi`, `/report`.

Per tornare indietro in caso di problemi: `git checkout 1812917` per il codice, e `cp $B/env.backup .env` per la configurazione.

---

## Parte B — Preparare il server (senza ancora spegnere il Codespace)

Segui [GUIDA_IPAD.md](GUIDA_IPAD.md) sezione B fino al punto 4 (VM creata, swap, `install.sh` eseguito una
prima volta, `.env` creato con i tuoi valori). **Non avviare ancora ATLAS sul server** se il Codespace è
acceso: due bot con lo stesso token si contendono i messaggi.

Verifica del server senza avviare il bot (dove: **finestra SSH del server**):
```bash
cd ~/atlas && docker compose -f deploy/docker-compose.yml build && docker compose -f deploy/docker-compose.yml run --rm atlas python -m atlas doctor
```
Deve terminare con `Esito: tutto a posto.`

---

## Parte C — Il passaggio (5–10 minuti di bot spento)

**C1. Esportare i portafogli dal Codespace** (dove: **terminale del Codespace**, con ATLAS ancora acceso):
```bash
cd /workspaces/Atlas && python -m atlas export --out atlas-export.tar.gz
```
L'archivio contiene solo i database (principale e ombra), **mai** il `.env`.

**C2. Scaricare l'archivio sull'iPad**: nel pannello dei file del Codespace, tasto destro (o pressione lunga)
su `atlas-export.tar.gz` → **Download**. Viene salvato in File/Download.

**C3. Fermare ATLAS nel Codespace**: Ctrl+C nel suo terminale. Da qui in poi il Codespace non deve più
avviare ATLAS.

**C4. Caricare l'archivio sul server**: nella finestra SSH di Google Cloud, icona ⚙️/“Carica file” (Upload file)
→ scegli `atlas-export.tar.gz`. Finisce nella cartella home (`~`).

**C5. Ripristinare e avviare** (dove: **finestra SSH del server**):
```bash
cd ~/atlas && C="docker compose -f deploy/docker-compose.yml" && $C down && $C run --rm -v ~/atlas-export.tar.gz:/import.tar.gz:ro atlas python -m atlas restore /import.tar.gz && $C up -d && sleep 60 && $C exec -T atlas python -m atlas healthcheck
```
(Se il server è nuovo e non vuoi trasferire lo storico, salta C1–C2 e C4 e usa solo `docker compose -f deploy/docker-compose.yml up -d`.)

**C6. Verifica finale** su Telegram: `/status` deve rispondere entro un minuto e mostrare lo stesso capitale
del Codespace. Se arrivasse il messaggio "Due istanze attive con lo stesso bot", c'è ancora un ATLAS acceso
nel Codespace: fermalo.

**C7. Mettere in sicurezza il Codespace**: puoi lasciarlo per sviluppo, ma non lanciare più `python -m atlas run`
lì. Per prove nel Codespace usa una cartella dati separata e Telegram disattivato, così nessun messaggio
si confonde con quelli del server:
```bash
cd /workspaces/Atlas && ATLAS_DATA_DIR=/tmp/atlas-prove TELEGRAM_TOKEN= TELEGRAM_CHAT_ID= TELEGRAM_ALLOWED_USERS= TELEGRAM_ADMIN_USERS= python -m atlas cycle
```

# Installazione, esecuzione continua e gestione

> Per la procedura passo-passo da iPad vedi [GUIDA_IPAD.md](GUIDA_IPAD.md); per la scelta dell'hosting [HOSTING.md](HOSTING.md).

## 1. Prerequisiti

- Python 3.11 o superiore.
- Un bot Telegram: su Telegram scrivi a **@BotFather** → `/newbot` → copia il token.
- Il tuo ID Telegram numerico: scrivi a **@userinfobot**. Lo stesso ID va usato come `TELEGRAM_CHAT_ID` per ricevere le notifiche in chat privata.
- (Facoltativo) API key Kraken **solo con permesso "Query Funds"**, per vedere il saldo reale con `/saldo`. Non serve per operare in simulazione.

## 2. Prova in GitHub Codespaces (anche da iPad)

```bash
pip install -r requirements-dev.txt
python -m pytest                     # deve terminare con "passed"
cp .env.example .env                 # poi modifica .env con l'editor di Codespaces
python -m atlas analyze BTC          # analisi singola (richiede rete verso Kraken)
python -m atlas cycle                # un ciclo completo, poi esce
python -m atlas run                  # bot + scheduler (si ferma se chiudi il Codespace)
```

Codespaces va in sospensione dopo un periodo di inattività: **non è adatto all'esecuzione continua**.
Usalo per sviluppo e prove, poi spostati su un server (sezione 3).

## 3. Esecuzione continua su un server (consigliato)

Va bene qualsiasi VPS Linux economico (1 vCPU, 1 GB RAM sono sufficienti). ATLAS non ha bisogno di porte in ingresso: Telegram funziona in polling.

### Opzione A — Docker (più semplice)
```bash
git clone https://github.com/mdalbianco/atlas.git && cd atlas
cp .env.example .env && nano .env            # inserisci token e ID
chmod 600 .env
docker compose -f deploy/docker-compose.yml up -d --build
docker compose -f deploy/docker-compose.yml logs -f   # log in tempo reale
```
Il database è nel volume `atlas-data` e sopravvive a riavvii e aggiornamenti. Il container si riavvia da solo (`restart: unless-stopped`) e ha un health check basato sull'heartbeat.

Aggiornamento:
```bash
git pull && docker compose -f deploy/docker-compose.yml up -d --build
```

### Opzione B — systemd
```bash
sudo useradd --system --create-home atlas
sudo git clone https://github.com/mdalbianco/atlas.git /opt/atlas
cd /opt/atlas && sudo python3 -m venv .venv && sudo .venv/bin/pip install -r requirements.txt
sudo cp .env.example .env && sudo nano .env && sudo chmod 600 .env
sudo mkdir -p data && sudo chown -R atlas:atlas /opt/atlas
sudo cp deploy/atlas.service /etc/systemd/system/ && sudo systemctl daemon-reload
sudo systemctl enable --now atlas
journalctl -u atlas -f
```

## 4. Uso quotidiano da Telegram

Comandi principali: `/status`, `/posizioni`, `/performance`, `/analisi BTC`, `/rischio`.
Notifiche automatiche: avvio, apertura e chiusura di posizioni simulate, blocchi di sicurezza,
arresti, errori ripetuti, riepilogo giornaliero (ore 20:00 UTC, configurabile).

Controllo (solo admin): `/pausa`, `/riprendi`, `/riprendi conferma` (dopo un arresto),
`/chiudi BTC`, `/watchlist add ADA`, `/watchlist remove ADA`, `/config`, `/modalita`.

La configurazione si cambia **solo** modificando `.env` e riavviando: non è modificabile da Telegram
(scelta di sicurezza: un account Telegram compromesso non può alzare i limiti di rischio).

## 5. Monitoraggio

- `python -m atlas healthcheck` → codice 0 se l'ultimo heartbeat è recente (usato da Docker).
- `python -m atlas status` → stato del conto e statistiche dal terminale.
- Log in JSON su stdout (`ATLAS_LOG_JSON=false` per testo leggibile). Token e chiavi sono oscurati automaticamente.
- Database: `data/atlas.db` (SQLite). Si può ispezionare con `sqlite3 data/atlas.db "select * from positions"`.

## 6. Backup e ripristino

ATLAS esegue ogni giorno (dopo il riepilogo serale) un backup coerente di tutti i database in
`data/backups/`, conservando gli ultimi 14 (`ATLAS_BACKUP_KEEP`). Backup immediato con verifica di integrità:

```bash
python -m atlas backup
```
Per copiarli fuori dal server: `bash deploy/backup-offsite.sh utente@server`.
Ripristino: fermare ATLAS, copiare il backup scelto su `data/atlas.db`, riavviare.
Per ripartire da zero con un nuovo capitale virtuale: fermare ATLAS e spostare/rinominare `data/atlas.db`.

## 7. Errori e ripresa

| Situazione | Comportamento |
|---|---|
| Kraken irraggiungibile, timeout, rate limit | retry con backoff (1, 2, 4, 8 s); se persiste il ciclo viene saltato; notifica dopo 5 cicli falliti consecutivi |
| Dati incompleti, vecchi o incoerenti | la coppia viene esclusa da quel ciclo, evento registrato |
| Errore imprevisto nel codice | **arresto di sicurezza** + notifica; posizioni aperte ancora gestite |
| Riavvio / crash del processo | stato ripreso dal database; nessuna candela rivalutata; nessun ordine duplicato; Docker/systemd riavviano il processo |
| Seconda istanza avviata per errore | rifiutata all'avvio (lock sul file `data/atlas.lock`) |
| Telegram non raggiungibile | il trading simulato continua; le notifiche falliscono senza bloccare il ciclo |

## 8. Sicurezza: checklist

- [ ] `.env` con permessi `600`, mai su Git (già in `.gitignore`).
- [ ] `TELEGRAM_ALLOWED_USERS` e `TELEGRAM_ADMIN_USERS` impostati (con elenco vuoto il bot rifiuta tutti).
- [ ] API key Kraken assente, oppure con il **solo** permesso Query Funds, senza prelievi né ordini; preferibilmente con restrizione IP.
- [ ] `ATLAS_MODE=paper` (qualsiasi altro valore impedisce l'avvio).

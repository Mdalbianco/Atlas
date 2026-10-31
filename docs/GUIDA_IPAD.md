# Guida rapida da iPad

Tutto si fa dal browser (Safari) e dall'app Telegram. Non serve un computer.

> **Aggiornamento del Codespace e passaggio al server**: la procedura blocco per blocco è in
> [MIGRAZIONE.md](MIGRAZIONE.md). Questa pagina resta il riferimento generale.

## A. Provare e sviluppare in GitHub Codespaces

1. Apri il repository su github.com → pulsante **Code** → **Codespaces** → apri il codespace sul branch
   `claude/atlas-crypto-trading-system-6ugata`.
2. Nel terminale del codespace:
   ```bash
   git pull
   pip install -r requirements-dev.txt
   python -m pytest              # deve finire con "passed"
   python -m atlas doctor        # verifica completa: paper, ordini bloccati, Kraken, Telegram, strategie
   python -m atlas cycle         # un ciclo con dati reali Kraken (paper)
   python -m atlas run           # bot Telegram + scheduler (si ferma se chiudi il codespace)
   ```
3. Il tuo `.env` resta solo nel codespace: non va mai committato (è in `.gitignore`).

> Se aggiorni da una versione precedente e ATLAS non parte con "Variabili ATLAS_* non riconosciute",
> correggi il nome indicato nel `.env`: è una protezione contro gli errori di battitura nei limiti di rischio.

## B. Attivare il funzionamento 24/7 (Google Cloud gratuito)

Scelta motivata in [HOSTING.md](HOSTING.md). Tempo: ~20 minuti.

1. **Crea la VM** su console.cloud.google.com (serve un account di fatturazione con carta: resta a 0 €
   solo rispettando esattamente questi parametri):
   - Compute Engine → Istanze VM → **Crea istanza**
   - Regione **us-central1** (o us-west1 / us-east1), tipo macchina **e2-micro**
   - Disco di avvio: **Ubuntu 24.04 LTS**, tipo **Disco permanente standard**, **30 GB**
   - Firewall: lascia tutto disattivato (ATLAS non riceve connessioni)
   - Fatturazione → Budget e avvisi → crea un budget di 1 € con avviso via email
2. **Apri il terminale**: nella lista delle VM premi **SSH** (si apre una finestra nel browser).
3. **Aggiungi memoria di swap** (consigliato con 1 GB di RAM, una sola volta):
   ```bash
   sudo fallocate -l 1G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   ```
4. **Installa ATLAS**:
   ```bash
   sudo apt-get update && sudo apt-get install -y git
   git clone --branch claude/atlas-crypto-trading-system-6ugata https://github.com/Mdalbianco/Atlas.git ~/atlas
   bash ~/atlas/deploy/install.sh
   ```
   La prima esecuzione installa Docker e crea `~/atlas/.env`. Se compare "permission denied" su Docker,
   chiudi la finestra SSH, riaprila e rilancia lo stesso comando.
5. **Inserisci i segreti** direttamente sul server (non in chat, non su GitHub):
   ```bash
   nano ~/atlas/.env
   ```
   Compila `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_ALLOWED_USERS`, `TELEGRAM_ADMIN_USERS`
   (gli stessi valori del `.env` di Codespaces). Salva con Ctrl+O, Invio, Ctrl+X.
6. **Avvia**: `bash ~/atlas/deploy/install.sh` → deve terminare con "ATLAS è attivo".
7. **Ferma la copia in Codespaces** se era in esecuzione: due bot con lo stesso token si contendono
   i messaggi (Telegram restituisce errore 409; ATLAS te lo segnala con un messaggio al massimo una volta all'ora).
   Per portare sul server anche lo storico dei portafogli segui [MIGRAZIONE.md](MIGRAZIONE.md), parte C.
8. Su Telegram invia `/status`: deve rispondere il server.

Da quel momento ATLAS gira anche con l'iPad spento, si riavvia da solo dopo crash o riavvii della VM
e salva un backup del database ogni giorno.

## C. Manutenzione

| Operazione | Comando (nella finestra SSH) |
|---|---|
| Vedere i log | `docker compose -f ~/atlas/deploy/docker-compose.yml logs -f --tail 100` |
| Stato | `docker compose -f ~/atlas/deploy/docker-compose.yml exec atlas python -m atlas status` |
| Aggiornare (con ritorno automatico se qualcosa va storto) | `bash ~/atlas/deploy/update.sh` |
| Backup immediato verificato | `docker compose -f ~/atlas/deploy/docker-compose.yml exec atlas python -m atlas backup` |
| Diagnosi completa | `docker compose -f ~/atlas/deploy/docker-compose.yml exec atlas python -m atlas doctor` |
| Fermare | `docker compose -f ~/atlas/deploy/docker-compose.yml down` (i dati restano nel volume) |
| Ripartire da zero con 100 € virtuali | fermare, poi `docker volume rm deploy_atlas-data` e riavviare (cancella lo storico!) |

## D. Gestione da Telegram

Uso quotidiano: `/status`, `/posizioni`, `/performance`, `/mercato`, `/analisi BTC`.

| Comando | Cosa fa |
|---|---|
| `/start`, `/help` | elenco comandi |
| `/status` | stato, ultimo ciclo, capitale |
| `/saldo` | capitale simulato |
| `/prezzo BTC` | prezzo, spread, variazione 24h |
| `/watchlist` | coppie monitorate (admin: `add SOL`, `remove SOL`) |
| `/analisi BTC` | analisi completa con la decisione e i motivi, senza eseguire nulla |
| `/segnali` | ultime decisioni del portafoglio principale |
| `/mercato` | panoramica della watchlist |
| `/strategie` | strategie, stato di validazione, principale/ombra |
| `/diagnosi` | perché ogni strategia opera o non opera (motivi di rifiuto più frequenti, esiti delle uscite) |
| `/posizioni`, `/operazioni` | posizioni aperte e chiuse |
| `/performance` | statistiche del portafoglio principale |
| `/report` | stato + performance + confronto portafogli + proposte |
| `/rischio` | limiti e blocchi attivi |
| `/pausa`, `/riprendi` (admin) | sospende/riprende nuove operazioni; dopo un arresto serve `/riprendi conferma` |
| `/chiudi BTC` (admin) | chiude una posizione simulata |
| `/modalita`, `/config` (admin) | modalità (sempre PAPER) e configurazione senza segreti |

Notifiche automatiche: avvio, apertura/chiusura di posizioni del portafoglio principale, blocchi di
rischio (solo quando cambiano), arresti di sicurezza, errori ripetuti (dopo 5 cicli falliti), backup
falliti, riepilogo giornaliero (20:00 UTC) e report settimanale (domenica) con il confronto tra
portafogli e le sole proposte *nuove*.

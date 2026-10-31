# Changelog

## 1.1.1 — 2026-10-31

Nessuna modifica alla logica delle strategie (restano 1.0.0, tutte respinte e in portafoglio ombra).

### Aggiunto
- `python -m atlas doctor`: diagnosi completa (paper, ordini bloccati, Kraken, token Telegram senza
  mostrarlo, strategie, portafogli ombra, permessi `.env`, istanze attive).
- `python -m atlas export` / `restore`: trasferimento dei portafogli tra Codespace e server, senza segreti;
  il ripristino rifiuta se ATLAS è attivo e conserva i dati precedenti.
- `/diagnosi`: motivi di rifiuto più frequenti per ogni portafoglio; incluso nel report settimanale.
- Avviso (max 1/ora) se Telegram segnala due istanze con lo stesso token (errore 409).
- `history --end`, `validate --timeframe/--higher-timeframe/--warmup-bars`, più CSV per coppia e file `.csv.gz`.
- Dati di ricerca nel repository: un anno di candele 1h reali BTC/ETH/SOL (`research/data/`).
- `docs/MIGRAZIONE.md` (aggiornamento Codespace e passaggio al server) e `docs/RESEARCH_PLAN.md`.

### Modificato
- La validazione vale solo per il timeframe su cui è stata ottenuta.
- Una strategia con solo il backtest superato resta "in osservazione": per entrare nel portafoglio
  principale serve anche evidenza di paper trading nel suo portafoglio ombra.
- Cache delle candele: riscaricate solo alla chiusura di una nuova candela (traffico per ciclo da ~405 KB a ~1 KB).
- `healthcheck` segnala "DEGRADATO" dopo circa un'ora di cicli falliti consecutivi.

## 1.1.0 — 2026-10-31

### Aggiunto
- Tre nuove strategie versionate: `trend_following`, `mean_reversion` (solo mercato laterale),
  `volatility_squeeze`; indicatori Bollinger (larghezza e percentile), Donchian, pendenza ADX.
- Compatibilità di regime: nessuna strategia opera in trend ribassista o volatilità estrema.
- Cancello di validazione (`atlas/strategy/validation_status.json`, versionato) e portafogli ombra
  isolati per le strategie non validate.
- `python -m atlas validate`: walk-forward per strategia su dati reali, criteri di promozione,
  confronto con buy & hold, report JSON/Markdown.
- `python -m atlas history`: storici lunghi dai trade pubblici Kraken (riprendibile, verificato
  contro le candele OHLC ufficiali).
- Istanza unica (lock), backup giornalieri verificati con rotazione, `python -m atlas backup`.
- Report settimanale con confronto tra portafogli; proposte notificate una sola volta; rilevamento
  del degrado delle strategie; notifica di ripristino dopo una serie di errori.
- Configurazione fail-safe: variabili `ATLAS_*` sconosciute o impostazioni Telegram/Kraken ambigue
  bloccano l'avvio con un messaggio chiaro.
- Deployment: `deploy/install.sh`, `deploy/update.sh` (backup + rollback automatico),
  `deploy/backup-offsite.sh`, immagine base Docker configurabile; `docs/HOSTING.md`, `docs/GUIDA_IPAD.md`.

### Modificato
- Il client Kraken rispetta `HTTPS_PROXY` e il CA bundle di sistema.
- `/analisi` valuta tutte le strategie candidate e indica quali sono attive; `/strategie` mostra lo
  stato di validazione; `/report` include il confronto tra portafogli.

## 1.0.0 — 2026-10-31

Ricostruzione completa del prototipo in un package modulare `atlas/` (dettagli in `docs/AUDIT.md`).

### Aggiunto
- Dati Kraken in sola lettura via CCXT con retry/backoff, timeout, rate limit e proxy che blocca ogni metodo di trading.
- Validazione delle candele: scarto della candela in formazione, righe incoerenti, duplicati, buchi, dati vecchi.
- Indicatori causali: EMA20/50/200, RSI/ATR/ADX di Wilder, MACD, volume relativo, OBV, volatilità realizzata.
- Struttura di prezzo con pivot confermati: HH/HL, supporti/resistenze con forza, breakout, consolidamenti, pattern di candela.
- Contesto multi-timeframe (1h + 4h) e riferimento generale di mercato (BTC 4h).
- Strategie versionate `trend_pullback` 1.0.0 e `breakout` 1.0.0 con motivazioni e condizioni di invalidazione.
- Scoring 0–100 con 9 componenti e pesi documentati; categorie configurabili.
- Risk manager: sizing a rischio fisso, R/R netto dei costi, limiti di posizione/esposizione/liquidità,
  perdita giornaliera, drawdown con arresto, perdite consecutive, correlazione, spread, minimi d'ordine, anomalie.
- Target delle strategie espressi in R **netti** di costi (`target_for_net_r`).
- Paper trading con commissioni, spread, slippage, gap, minimi d'ordine e arrotondamenti; conto persistente in SQLite.
- Protezione dai duplicati: ID ordine deterministico UNIQUE e una sola posizione aperta per coppia.
- Ciclo operativo con health check, gestione intrabar a 5 minuti, trailing stop, stop temporale, heartbeat, ripresa dopo riavvio.
- Backtest event-driven multi-asset, metriche complete, benchmark buy & hold, split cronologico e walk-forward.
- Analisi delle performance e proposte di miglioramento (mai applicate automaticamente).
- Bot Telegram in italiano con controllo accessi fail-closed e comandi admin protetti; notifiche con rate limit.
- CLI (`python -m atlas ...`), Docker, docker-compose, systemd, GitHub Actions, `.env.example`.
- Logging JSON con oscuramento automatico di token e chiavi.
- Test di parità tra ciclo live e backtest; download di 720 candele per la convergenza dell'EMA200.
- Trailing stop con pavimento al pareggio netto dei costi.

### Rimosso
- Prototipo `app/` (posizioni short sullo spot, assenza di costi simulati, storage JSON non atomico,
  Telegram senza autenticazione, supporti/resistenze con look-ahead). Resta nella cronologia Git.

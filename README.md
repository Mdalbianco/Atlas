# ATLAS

Sistema algoritmico di **analisi e paper trading** di criptovalute sul mercato spot di **Kraken**,
controllabile da **Telegram**. Versione 1.1.1.

> ⚠️ ATLAS opera **solo in simulazione** (paper trading). Il trading reale non è implementato e non è
> attivabile (vedi [docs/LIVE_TRADING_POLICY.md](docs/LIVE_TRADING_POLICY.md)). Nessun rendimento è garantito.
> Le strategie non sono ancora state validate su dati di mercato reali.

## Cosa fa

1. Monitora una watchlist di coppie Kraken (default BTC/EUR, ETH/EUR, SOL/EUR) ogni 5 minuti.
2. Analizza trend (EMA20/50/200, ADX), momentum (RSI, MACD), volatilità (ATR), volumi, struttura di
   prezzo, supporti e resistenze, su 1h con conferma 4h e riferimento generale BTC.
3. Valuta cinque strategie versionate (trend following, pullback, breakout, mean reversion, volatility squeeze),
   ciascuna solo nei regimi di mercato compatibili e solo alla chiusura di una nuova candela. Nel portafoglio
   principale entrano **solo le strategie che superano la validazione walk-forward su dati reali**; le altre
   girano in portafogli ombra isolati per raccogliere evidenza.
4. Assegna a ogni setup un punteggio 0–100 interpretabile, con il dettaglio delle 9 componenti.
5. Passa ogni segnale al risk manager: rischio 1% per operazione, R/R minimo **al netto dei costi**,
   limiti di esposizione, perdita giornaliera, drawdown, correlazione, minimi d'ordine.
6. Simula le operazioni con commissioni, spread, slippage e minimi d'ordine realistici.
7. Gestisce le posizioni (stop, take profit, trailing stop, invalidazione, stop temporale).
8. Registra ogni decisione, anche quelle di non operare, con le motivazioni.
9. Produce statistiche, report e proposte di miglioramento, che non applica mai da solo.
10. Comunica tutto in italiano via Telegram.

Il sistema è progettato per **aspettare**: nella maggior parte dei cicli la decisione corretta è non fare nulla.

## Avvio rapido

```bash
pip install -r requirements-dev.txt
python -m pytest                       # suite di test, tutta offline
cp .env.example .env                   # inserisci TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ALLOWED_USERS, TELEGRAM_ADMIN_USERS
python -m atlas analyze BTC            # analisi singola
python -m atlas run                    # bot + scheduler
```

Per l'esecuzione continua (server, Docker, systemd) vedi [docs/OPERATIONS.md](docs/OPERATIONS.md).

## Comandi

| CLI | |
|---|---|
| `python -m atlas run` | bot Telegram + scheduler |
| `python -m atlas cycle` | un singolo ciclo |
| `python -m atlas analyze BTC` | analisi con decisione motivata |
| `python -m atlas status` | stato del conto simulato |
| `python -m atlas healthcheck` | verifica heartbeat (per Docker/systemd) |
| `python -m atlas download BTC/EUR --days 30 --out FILE` | storico recente da Kraken |
| `python -m atlas backtest --csv FILE... [--validate \| --walk-forward]` | backtest su dati reali |
| `python -m atlas backtest --synthetic` | backtest su dati sintetici (solo verifica meccanica) |
| `python -m atlas history BTC/EUR --days 365 --out FILE` | storico lungo dai trade pubblici Kraken |
| `python -m atlas validate --csv FILE...` | validazione walk-forward per strategia e report |
| `python -m atlas backup` | backup verificato dei database |
| `python -m atlas doctor` | diagnosi completa dell'installazione |
| `python -m atlas export` / `restore FILE` | trasferire i portafogli su un altro server |

**Telegram**: `/start` `/help` `/status` `/saldo` `/prezzo` `/watchlist` · `/analisi` `/segnali`
`/mercato` `/strategie` · `/posizioni` `/operazioni` `/performance` `/report` `/rischio` ·
admin: `/pausa` `/riprendi` `/chiudi` `/modalita` `/config`.

Esempio di notifica (valori illustrativi):
```
🟢 ATLAS — Posizione simulata aperta

Asset: BTC/EUR
Strategia: trend_pullback v1.0.0
Trend: Rialzista 📈   RSI: 57   MACD: positivo in accelerazione
Score: 74/100
Rapporto rischio/rendimento (netto): 2,50
Rischio stimato: 1,00% del capitale
...
Operazione SIMULATA (paper trading): nessun denaro reale è stato usato.
```

## Documentazione

| Documento | Contenuto |
|---|---|
| [docs/AUDIT.md](docs/AUDIT.md) | analisi del prototipo precedente e motivi della ricostruzione |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | moduli, flusso del ciclo, modello dati, ripresa dopo riavvio |
| [docs/STRATEGIES_AND_SCORING.md](docs/STRATEGIES_AND_SCORING.md) | regole delle strategie, pesi dello score, promozione delle strategie |
| [docs/RISK.md](docs/RISK.md) | limiti di rischio e analisi dei costi con 100 € |
| [docs/BACKTESTING.md](docs/BACKTESTING.md) | backtest, walk-forward, dati reali, stato della validazione |
| [docs/GUIDA_IPAD.md](docs/GUIDA_IPAD.md) | **guida passo-passo da iPad**: Codespaces, server 24/7, Telegram |
| [docs/MIGRAZIONE.md](docs/MIGRAZIONE.md) | aggiornare il Codespace e passare al server, blocco per blocco |
| [docs/RESEARCH_PLAN.md](docs/RESEARCH_PLAN.md) | piano di ricerca su 2–3 anni e timeframe 4h |
| [docs/HOSTING.md](docs/HOSTING.md) | confronto hosting con costi e limiti verificati |
| [docs/VALIDATION_REPORT.md](docs/VALIDATION_REPORT.md) | risultati della validazione su dati reali Kraken |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | installazione, deployment, monitoraggio, backup, sicurezza |
| [docs/LIVE_TRADING_POLICY.md](docs/LIVE_TRADING_POLICY.md) | perché e come il trading reale è bloccato |
| [docs/ROADMAP.md](docs/ROADMAP.md) | stato delle fasi, criteri di completamento, prossimi passi |

## Struttura

```
atlas/        codice (dati, analisi, strategie, scoring, rischio, esecuzione, storage, engine, backtest, telegram)
tests/        test pytest offline e deterministici
docs/         documentazione
deploy/       Dockerfile, docker-compose, unità systemd
```

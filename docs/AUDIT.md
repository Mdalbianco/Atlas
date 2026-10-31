# FASE A — Audit del prototipo (stato al commit `c154f39`)

Audit eseguito sul repository `mdalbianco/atlas`, branch `main`, prima della ricostruzione.

## Struttura trovata

- `app/` con 37 moduli (~5.750 righe): `analysis/` (14 analizzatori), `services/` (12 servizi),
  `risk/`, `backtesting/`, `bot/telegram_bot.py`, `exchange/`.
- 31 file `test_*.py` nella radice: **solo 6 erano test pytest** (31 test in totale),
  gli altri erano script manuali che chiamavano Kraken dal vivo.
- Storage in file JSON (`data/paper_trades.json`, `paper_wallet.json`, `trade_journal.json`, `watchlist.json`).
- `README.md` fermo alla "Sprint 1", `requirements.txt` senza versioni.

## Esecuzione dei test esistenti

```
8 failed, 23 passed
```
Gli 8 fallimenti (`test_auto_trade_filters.py`) erano dovuti a `KrakenClient`, che sollevava
un'eccezione se mancavano le API key **anche per leggere dati pubblici**, e veniva istanziato
a cascata da ogni servizio.

## Cosa funzionava (logica riutilizzata nella nuova versione)

| Prototipo | Nuova versione | Note |
|---|---|---|
| `analysis/trend.py`, `rsi.py`, `macd.py`, `atr.py` | `atlas/analysis/indicators.py` | RSI/ATR ora con media di Wilder; aggiunti EMA200, ADX, volume relativo, OBV |
| `analysis/support_resistance.py`, `price_action.py`, `candle_context.py` | `atlas/analysis/structure.py` | pivot confermati (niente finestre centrate) |
| `analysis/market_regime.py`, `multi_timeframe.py` | `atlas/analysis/snapshot.py` | regime + contesto multi-timeframe |
| `analysis/score.py`, `confidence.py` | `atlas/scoring.py` | un solo punteggio 0-100 con componenti e pesi espliciti |
| `risk/risk_manager.py`, `risk/circuit_breaker.py` | `atlas/risk/manager.py` | stesse idee (limiti giornalieri, drawdown, perdite consecutive) + costi, correlazione, minimi d'ordine |
| `services/paper_trading_service.py`, `wallet_service.py`, `trade_journal_service.py` | `atlas/engine/account.py`, `atlas/storage/db.py` | SQLite transazionale |
| `services/scheduler_service.py`, `auto_trade_service.py`, `trade_monitor_service.py` | `atlas/engine/cycle.py`, `atlas/runner.py` | |
| `backtesting/backtest_engine.py` | `atlas/backtest/` | ingresso alla candela successiva, costi, walk-forward |
| `bot/telegram_bot.py`, `services/notification_service.py` | `atlas/telegram/`, `atlas/app.py` | comandi compatibili mantenuti come alias (`/analizza`, `/watch`, `/wallet`, `/journal`) |

## Problemi rilevati (motivo della ricostruzione)

**Critici per la sicurezza del capitale**
1. **Posizioni Short sullo spot**: il risk manager generava operazioni `Short`, impossibili sullo spot senza margine (vietato dalle specifiche).
2. **Nessuna commissione, spread o slippage** nel paper trading e nel backtest: risultati sistematicamente ottimistici. Con 100 € e commissioni dello 0,40% per lato questo errore è decisivo.
3. **Nessuna protezione contro ordini duplicati** dopo un riavvio (solo un controllo "trade già aperto" su file JSON).
4. **Telegram senza autenticazione**: chiunque trovasse il bot poteva usarlo.
5. Storage JSON riscritto per intero a ogni modifica, **non atomico**: un'interruzione durante la scrittura poteva corrompere lo storico.

**Correttezza analitica**
6. Supporti/resistenze calcolati con finestre centrate sui massimi/minimi locali → **uso di informazioni future** (look-ahead) se applicati in backtest.
7. RSI calcolato con media semplice invece della media di Wilder (valori diversi dagli standard di mercato).
8. Backtest con ingresso al prezzo di chiusura della stessa candela del segnale e senza costi.
9. Due sistemi di punteggio sovrapposti (score + confidence, ~1.000 righe) con pesi non documentati.

**Manutenibilità**
10. Dipendenze circolari tra servizi; ogni servizio istanziava il client Kraken.
11. Uso di `print` invece di logging strutturato; nessuna gestione di rate limit/timeout.
12. Configurazione sparsa (costanti in `config/settings.py`, valori hard-coded nei servizi).

## Decisione

Riscrittura in un package `atlas/` modulare, conservando gli algoritmi validi del prototipo
(sopra). Il vecchio codice rimane consultabile nella cronologia Git (commit `c154f39`).
Nessun dato reale da migrare: i file JSON contenevano solo un'operazione di test (`symbol: TEST`).

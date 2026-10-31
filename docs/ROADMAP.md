# Roadmap e stato delle fasi

| Fase | Stato | Note |
|---|---|---|
| A — Audit | ✅ completata | `docs/AUDIT.md` |
| B — Architettura | ✅ completata | `docs/ARCHITECTURE.md` |
| C — Nucleo analitico | ✅ completata | indicatori causali, struttura, multi-timeframe, 2 strategie, scoring |
| D — Trading simulato | ✅ completata | risk manager, costi realistici, conto persistente, gestione posizione |
| E — Validazione | ✅ eseguita su 1 anno di dati reali Kraken | **nessuna strategia validata** (vedi VALIDATION_REPORT.md) |
| F — Telegram e automazione | ✅ | comandi verificati su dati reali; /start e /status verificati dall'utente con il bot reale |
| G — Deployment | ✅ immagine Docker verificata (crash/riavvio/persistenza), 🟡 server reale da creare | install/update/backup script, guida iPad |
| H — Ottimizzazione | 🟡 diagnosi fatta, proposte registrate | timeframe 4h e revisione scoring da sviluppare come nuove versioni |

## Criteri di completamento v1 (sezione 17 delle specifiche)

| Criterio | Stato | Verifica |
|---|---|---|
| Bot Telegram funzionante | ✅ | verificato dall'utente in Codespaces (/start, /status); tutti i comandi verificati su dati reali via router |
| Connessione Kraken in sola lettura | ✅ | verificata dal vivo (31/10/2026): 720 candele 1h/4h per BTC/ETH/SOL, ticker, regole di mercato, ciclo paper completo |
| Dati raccolti e validati | ✅ | test su candela in formazione, dati incoerenti, buchi, dati vecchi |
| Analisi tecnica verificabile | ✅ | test numerici (RSI di Wilder, ATR, ADX…) e test anti look-ahead |
| Scoring implementato | ✅ | |
| Risk manager applica i limiti | ✅ | test per ogni regola |
| Paper trading corretto | ✅ | contabilità verificata al centesimo; stesse operazioni del backtest (test di parità) |
| Operazioni archiviate | ✅ | SQLite con vincoli anti-duplicazione |
| Report generati | ✅ | `/performance`, `/report`, riepilogo giornaliero, report di backtest |
| Backtesting disponibile | ✅ | |
| Suite di test | ✅ | `python -m pytest` |
| Sopravvivenza a riavvii ed errori | ✅ | test con riavvio a metà, Kraken irraggiungibile, errore imprevisto |
| Documentazione | ✅ | README + `docs/` |
| Ordini reali impossibili per default | ✅ | quattro livelli di protezione, testati |

## Prossimi passi (in ordine di priorità)

1. **Attivare il 24/7** sul server (docs/GUIDA_IPAD.md, sezione B): il paper trading dei portafogli ombra
   produce evidenza reale e indipendente dal backtest.
2. **Storico di 2–3 anni** e nuove versioni delle strategie su timeframe 4h (proposta 1 del report di validazione).
3. Revisione dei pesi dello scoring come `scoring v2`, validata con walk-forward.
4. Rivedere mensilmente `/report`: promuovere solo con una nuova validazione superata.

## Estensioni future (non implementate)

Dashboard web in sola lettura sul database, alert personalizzati, correlazioni e anomalie di mercato
come notifiche, dati di sentiment da fonti affidabili, confronto automatico tra strategie, modelli
predittivi (solo come strategie versionate soggette allo stesso walk-forward), esportazione CSV dei report,
multi-exchange tramite nuove implementazioni di `MarketDataSource`.

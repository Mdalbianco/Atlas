# Roadmap e stato delle fasi

| Fase | Stato | Note |
|---|---|---|
| A — Audit | ✅ completata | `docs/AUDIT.md` |
| B — Architettura | ✅ completata | `docs/ARCHITECTURE.md` |
| C — Nucleo analitico | ✅ completata | indicatori causali, struttura, multi-timeframe, 2 strategie, scoring |
| D — Trading simulato | ✅ completata | risk manager, costi realistici, conto persistente, gestione posizione |
| E — Validazione | 🟡 meccanica completa, **validazione su dati reali da fare** | backtest, split cronologico, walk-forward, metriche, test |
| F — Telegram e automazione | ✅ implementata, 🟡 da verificare dal vivo | comandi, notifiche, scheduler, ripresa dopo riavvio |
| G — Deployment | ✅ file pronti, 🟡 da provare su server | Docker, docker-compose, systemd, health check, CI GitHub Actions |
| H — Ottimizzazione | 🟡 strumenti pronti | analisi performance e proposte; serve storico reale |

## Criteri di completamento v1 (sezione 17 delle specifiche)

| Criterio | Stato | Verifica |
|---|---|---|
| Bot Telegram funzionante | 🟡 | logica e integrazione con python-telegram-bot testate offline; manca la prova con un token reale |
| Connessione Kraken in sola lettura | 🟡 | implementata e protetta; **non provata dal vivo** (rete bloccata nell'ambiente di sviluppo) |
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

1. **Primo avvio reale** in Codespaces: `.env` con token Telegram e ID, `python -m atlas cycle`, poi `run`.
   Verificare `/status`, `/analisi BTC`, `/mercato`.
2. **Dati storici reali**: scaricare i file OHLCVT Kraken di BTC/EUR, ETH/EUR, SOL/EUR (1h, ≥ 2 anni)
   ed eseguire `--validate` e `--walk-forward`. Decidere, sulla base dei risultati, se tenere `breakout`
   (negativo anche sui dati sintetici) e se alzare la soglia a 75 (sui dati sintetici la fascia 65–74 è in pareggio).
3. **Deployment continuo** su VPS con Docker; lasciare girare il paper trading per almeno 3 mesi.
4. Rivedere ogni mese `/report` e le proposte; ogni modifica → nuova versione di strategia → walk-forward.
5. Valutare timeframe più lunghi (4h/1d) come operativi: con 100 € e commissioni 0,40% i movimenti più
   ampi riducono il peso relativo dei costi.

## Estensioni future (non implementate)

Dashboard web in sola lettura sul database, alert personalizzati, correlazioni e anomalie di mercato
come notifiche, dati di sentiment da fonti affidabili, confronto automatico tra strategie, modelli
predittivi (solo come strategie versionate soggette allo stesso walk-forward), esportazione CSV dei report,
multi-exchange tramite nuove implementazioni di `MarketDataSource`.

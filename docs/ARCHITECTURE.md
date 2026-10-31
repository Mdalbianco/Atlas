# FASE B — Architettura

## Principi

1. **Il default è non operare.** Un'operazione richiede che strategia, punteggio e risk manager siano tutti d'accordo.
2. **Stesso codice per simulazione e backtest.** Snapshot, strategie, scoring, risk manager, regole di uscita e modello dei costi sono condivisi: ciò che si testa è ciò che gira.
3. **Componenti puri dove possibile.** Analisi, strategie, scoring, rischio e gestione posizione non fanno I/O: sono testabili in isolamento.
4. **Nessun percorso verso ordini reali.** Il client Kraken è avvolto in un proxy che consente solo metodi di lettura; l'esecuzione reale non esiste in v1.
5. **Stato persistente e transazionale.** Tutto lo stato vive in SQLite; ogni modifica di saldo/posizione/ordine è atomica.

## Moduli

```
atlas/
├── config.py               configurazione da variabili d'ambiente + validazione
├── logging_setup.py        log JSON con oscuramento dei segreti
├── domain.py               modelli condivisi (Signal, Decision, RiskDecision, Fill, ...)
├── data/
│   ├── exchange.py         Kraken via CCXT in SOLA LETTURA, retry/backoff, proxy read-only
│   ├── market_data.py      candele → DataFrame, validazione, scarto candela in formazione
│   └── sources.py          CSV storici (anche formato Kraken OHLCVT), mercato sintetico/replay
├── analysis/
│   ├── indicators.py       EMA, RSI/ATR/ADX (Wilder), MACD, volume relativo, OBV, volatilità
│   ├── structure.py        pivot confermati, HH/HL, supporti/resistenze, breakout, pattern
│   └── snapshot.py         "fotografia" interpretata + contesto multi-timeframe
├── strategy/               strategie versionate (trend_pullback, breakout) + registro
├── scoring.py              punteggio 0-100 = media pesata di 9 componenti
├── risk/
│   ├── costs.py            commissioni, spread, slippage, R/R netto
│   └── manager.py          sizing e tutti i limiti di rischio
├── execution/
│   ├── paper.py            riempimenti simulati realistici, ID ordine deterministico
│   └── live.py             DISABILITATO: solleva sempre LiveTradingDisabled
├── storage/db.py           SQLite (WAL), schema, vincoli anti-duplicazione
├── engine/
│   ├── analyzer.py         dati live → MarketContext
│   ├── decision.py         strategie → score → rischio → Decision motivata
│   ├── position_manager.py stop/target/trailing/invalidazione/stop temporale
│   ├── account.py          conto paper persistente
│   └── cycle.py            ciclo operativo completo
├── backtest/               motore, metriche, split cronologico, walk-forward
├── performance/analyzer.py statistiche dello storico + proposte (mai applicate da sole)
├── telegram/               notifiche, formattazione in italiano, bot con controllo accessi
├── app.py                  composizione + testi dei comandi
├── runner.py               scheduler + bot + report giornaliero
└── __main__.py             CLI
```

## Flusso di un ciclo (ogni 5 minuti)

```
health check Kraken ─► candele 1h + 4h + ticker (validati) ─► snapshot multi-timeframe
      │                                                              │
      │                     ┌────────────────────────────────────────┘
      ▼                     ▼
gestione posizioni aperte (candele 5m: stop/target; chiusura 1h: trailing, invalidazione, tempo)
      │
      ▼
mark-to-market ─► limiti globali (drawdown → arresto; perdita giornaliera, perdite consecutive → blocco)
      │
      ▼
solo su NUOVA candela 1h chiusa: strategie ─► score ≥ soglia ─► risk manager ─► paper broker
      │
      ▼
SQLite (decisioni, ordini, posizioni, equity, eventi, heartbeat) ─► notifiche Telegram
```

## Modello dei dati (SQLite)

| Tabella | Contenuto | Vincoli chiave |
|---|---|---|
| `positions` | posizioni aperte e chiuse con motivazioni, score, contesto di mercato, PnL, R | `client_order_id` UNIQUE; un solo `open` per simbolo (indice parziale UNIQUE) |
| `orders` | ogni esecuzione simulata (prezzo di riferimento, prezzo eseguito, commissione) | `client_order_id` UNIQUE |
| `decisions` | ogni valutazione (anche i "non entro") con dettagli JSON | |
| `equity` | curva del capitale a ogni ciclo | |
| `events` | avvio, arresti, errori, pause | |
| `proposals` | proposte di miglioramento con evidenza | stato `proposta` finché una persona decide |
| `state` | saldo, picco, pausa/arresto, ultima candela valutata, heartbeat | |
| `watchlist` | coppie monitorate | |

## Ripresa dopo riavvio

- La liquidità e le posizioni sono nel database: il riavvio riprende esattamente lo stato precedente.
- `last_eval_bar` impedisce di rivalutare una candela già valutata.
- L'ID ordine è `sha256(paper|simbolo|strategia|versione|timestamp candela|buy)`: rieseguire lo stesso segnale è impossibile per il vincolo UNIQUE.
- Le posizioni aperte durante un'interruzione vengono controllate sulle candele a 5 minuti successive all'ultimo controllo, così uno stop toccato mentre il processo era fermo viene registrato.

## Concorrenza

Bot Telegram (asyncio) e scheduler (thread) condividono database e fonte dati:
la fonte è serializzata da `LockedSource`, il ciclo e la chiusura manuale da un `RLock`,
le scritture SQLite da transazioni `BEGIN IMMEDIATE`.

## Estensioni previste

La struttura è predisposta per: nuove strategie (sottoclasse di `Strategy` + registro),
altri exchange (implementare `MarketDataSource`), dashboard web (leggere SQLite),
alert personalizzati (nuovi controlli nel ciclo), modelli ML (come strategia
versionata, soggetta allo stesso walk-forward). Nessuna di queste è implementata in v1.

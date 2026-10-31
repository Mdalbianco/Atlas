# Backtesting e validazione

## Garanzie del motore (`atlas/backtest/engine.py`)

- Usa gli **stessi** componenti del paper trading (strategie, scoring, risk manager, gestione della posizione, costi).
- Decisione sulla chiusura della candela `i` con soli dati `≤ i`; esecuzione all'**apertura della candela `i+1`**, costi inclusi.
- Timeframe 4h ricostruito dalle candele 1h, usando solo candele 4h **già chiuse** all'istante della decisione.
- Stop prima del target se toccati nella stessa candela; uscita all'apertura in caso di gap.
- Portafoglio condiviso tra asset, con tutti i limiti di rischio (incluse correlazioni e perdite consecutive).
- Posizioni ancora aperte a fine periodo chiuse all'ultimo prezzo (`end_of_data`).
- Test automatici dedicati: parità con il ciclo live (`test_live_backtest_parity.py`), indicatori e struttura identici su serie troncate (`test_no_lookahead.py`),
  ingresso alla candela successiva, nessuna operazione fuori finestra, cache che non altera i risultati.

## Metriche

Rendimento netto, numero di operazioni, win rate, profit factor, media vincite/perdite,
expectancy (€ e R), drawdown massimo e durata, Sharpe (solo con ≥ 30 operazioni), costi totali,
tempo investito, curva del capitale; scomposizione per asset, strategia, regime, fascia di score
e motivo di uscita; benchmark **buy & hold** (capitale diviso in parti uguali, costi inclusi).

## Comandi

```bash
# meccanica su dati sintetici (deterministici)
python -m atlas backtest --synthetic --bars 5000 --seed 21

# dati reali da CSV (uno per coppia)
python -m atlas backtest --csv data/history/BTC_EUR_1h.csv data/history/ETH_EUR_1h.csv

# split cronologico 60/20/20: parametri scelti SOLO sul training, test usato una volta
python -m atlas backtest --csv ... --validate --json reports/validazione.json

# walk-forward: ottimizza su 2000 candele, testa sulle 500 successive, scorre in avanti
python -m atlas backtest --csv ... --walk-forward --train-bars 2000 --test-bars 500
```

## Procurarsi dati reali

- `python -m atlas download BTC/EUR --days 30 --out data/history/BTC_EUR_1h.csv` usa l'API pubblica Kraken.
  **Limite Kraken**: l'endpoint OHLC restituisce solo le ultime ~720 candele (circa 30 giorni in 1h),
  insufficienti per una validazione.
- Per storici lunghi usare i file **OHLCVT ufficiali** pubblicati da Kraken (archivio scaricabile dal
  centro assistenza Kraken, file tipo `XBTEUR_60.csv`, dove 60 = minuti). `load_csv` li legge
  direttamente; il nome del file viene convertito in coppia (`XBTEUR_60.csv` → `BTC/EUR`), oppure si
  indica esplicitamente `--csv BTC/EUR=percorso.csv`.
- Servono almeno ~900 candele di riscaldamento (EMA200 sul 4h) più il periodo di test.

## Controlli contro l'overfitting

- Griglia piccola e fissata a priori (`DEFAULT_GRID`: soglia di score 60/65/70, target 2/2,5 R).
- Funzione obiettivo: expectancy in R, penalizzata se le operazioni sono meno di 15.
- Il report di validazione segnala: campioni con meno di 30 operazioni, degradazione forte
  training → test, rendimento inferiore al buy & hold.
- Il walk-forward riporta la **stabilità dei parametri** (quota di fold che sceglie gli stessi):
  parametri instabili indicano che l'ottimizzazione insegue il rumore.

## Risultati attuali

**Validazione su dati reali eseguita il 31/10/2026** (un anno di candele 1h BTC/ETH/SOL ricostruite dai
trade pubblici Kraken): **nessuna strategia supera i criteri**. Dettagli, diagnosi sui costi e proposte in
[VALIDATION_REPORT.md](VALIDATION_REPORT.md).

Le esecuzioni su dati sintetici (`--synthetic`) servono solo a verificare la meccanica: sui dati sintetici
le strategie trend following risultavano positive perché il generatore crea trend artificiali, risultato
che i dati reali **non** hanno confermato.

## Parità tra paper trading e backtest

`tests/test_live_backtest_parity.py` riproduce un mercato candela per candela e fa girare il ciclo
live un minuto dopo ogni apertura: gli ingressi devono coincidere esattamente con quelli del
backtest. Questo test ha fatto emergere (e correggere) due discrepanze reali:
1. con 300 candele l'EMA200 del live non era convergente e classificava il trend diversamente dal
   backtest → ora il live scarica 720 candele (massimo Kraken) e la configurazione rifiuta valori < 600;
2. il backtest non liberava subito lo spazio di una posizione con uscita già decisa → allineato al live.

## Storici lunghi

`python -m atlas history SIMBOLO --days N --out FILE` ricostruisce le candele dai trade pubblici
(riprendibile: se si interrompe basta rilanciare lo stesso comando). Tempi osservati per 365 giorni:
BTC/EUR ~3,5 h (11.942 richieste), ETH/EUR e SOL/EUR ~2,5 h ciascuno (~5.300 richieste).

# Piano di ricerca quantitativa (2–3 anni di dati, timeframe 4h)

Obiettivo: capire se esiste una strategia con vantaggio **netto dei costi reali** per un conto da 100 €,
senza adattare i parametri ai dati (overfitting) e senza promuovere nulla sulla base dei soli backtest.

## 1. Punto di partenza (evidenza già raccolta)

- Un anno di dati 1h reali (31/10/2025–31/10/2026), nel repository in `research/data/` (verificati contro
  l'OHLC ufficiale Kraken, scarto 0,0000%).
- Su 1h tutte le strategie 1.0.0 sono negative fuori campione; a costi zero emerge un piccolo vantaggio
  lordo (+0,07 R / +0,19 R) cancellato dai costi (~1% andata e ritorno). Dettagli: `VALIDATION_REPORT.md`.
- Ipotesi principale: su candele più ampie (4h) il movimento tipico è più grande rispetto ai costi fissi.

## 2. Ipotesi, fissate PRIMA di guardare i nuovi dati

| # | Ipotesi | Come si misura | Esito che la smentisce |
|---|---|---|---|
| H1 | Su 4h/1d il peso dei costi scende abbastanza da rendere positiva almeno una strategia | expectancy netta fuori campione | expectancy ≤ 0 in tutte le strategie |
| H2 | Il vantaggio non dipende da un solo regime | expectancy per regime (rialzo / ribasso / laterale, definiti sotto) | positiva in un solo regime |
| H3 | Lo score discrimina | expectancy crescente con la fascia di score | fasce alte non migliori delle basse |
| H4 | I risultati reggono costi più alti | stessa validazione con commissione 0,60% e spread 0,2% | expectancy che diventa negativa |

Le griglie di parametri restano quelle di `param_grid()` nelle strategie (piccole, decise a priori). Ogni
idea nuova (es. regola di invalidazione diversa per `trend_pullback`) diventa una **nuova versione** della
strategia, scritta e committata **prima** di eseguirne la validazione.

## 3. Dati

| Periodo | Mercato (BTC/EUR) | Stato |
|---|---|---|
| 10/2023 – 10/2024 | forte rialzo (anno dell'halving) | da scaricare |
| 10/2024 – 10/2025 | rialzo e poi correzioni | da scaricare |
| 10/2025 – 10/2026 | forte ribasso, poi rimbalzo | ✅ nel repository |

Download (riprendibile; meglio sul server 24/7, dove può durare la notte; stime basate sui tempi osservati:
~1.000 trade per richiesta, ~0,85 s per richiesta; per BTC nel 2024 servono molte più richieste):
```bash
for s in BTC ETH SOL; do
  python -m atlas history $s/EUR --end 2025-10-31T13:00:00 --days 730 --out data/history/${s}_EUR_1h_2023-2025.csv
done
```
Sul server, dentro il container: `docker compose -f deploy/docker-compose.yml exec atlas python -m atlas history ...`
con `--out /app/data/history/...` (il volume conserva i file). Se si interrompe, rilanciare lo stesso comando.

Controllo qualità obbligatorio prima di ogni analisi: buchi temporali, confronto con l'OHLC ufficiale sulle
ultime 720 candele, assenza di candele incoerenti (`clean_and_validate`).

## 4. Protocollo

1. **Separazione cronologica.** Gli ultimi 6 mesi (05/2026–10/2026) sono un **holdout finale**: non si usano
   per nessuna scelta e si guardano una sola volta, alla fine.
2. **Walk-forward sul resto** (≈ 30 mesi): timeframe 4h, conferma 1d, training 12 mesi (≈ 2.190 candele 4h),
   test 3 mesi (≈ 540), avanzamento di 3 mesi → circa 6 periodi di test. Riscaldamento ≥ 1.300 candele 4h
   (EMA200 sul giornaliero).
   ```bash
   python -m atlas validate --csv data/history/*_EUR_1h_2023-2025.csv research/data/*.csv.gz \
       --timeframe 4h --higher-timeframe 1d --train-bars 2190 --test-bars 540 --warmup-bars 1300 \
       --out reports/ricerca_4h
   ```
3. **Costi realistici**: taker 0,40% + spread misurato + slippage 0,05% per lato (default), più la
   sensibilità H4. Nessuna ipotesi di ordini "maker" senza un modello di esecuzione.
4. **Regimi** (per H2), definiti sul BTC giornaliero: rialzo = prezzo > EMA200 e EMA200 crescente;
   ribasso = prezzo < EMA200 e EMA200 decrescente; altrimenti laterale. Ogni operazione è etichettata con il
   regime al momento dell'ingresso (già registrato nei report come `regime`).
5. **Benchmark**: buy & hold equipesato e liquidità (0%), negli stessi periodi.
6. **Test multipli**: il report indica il numero di configurazioni provate. Più ipotesi si testano, più alta
   la probabilità di trovarne una "buona" per caso: si privilegiano risultati coerenti su tutti i periodi
   rispetto a un singolo periodo eccezionale.

## 5. Criteri di promozione (due cancelli, entrambi obbligatori)

1. **Backtest fuori campione** (`CRITERIA` in `atlas/strategy/validation.py`): ≥ 30 operazioni,
   expectancy ≥ +0,05 R, profit factor ≥ 1,15, drawdown ≤ 15%, ≥ 50% dei periodi positivi; in più, per questa
   ricerca, nessuna smentita di H2 e H4 e holdout finale non negativo.
2. **Paper trading reale** (`PAPER_CRITERIA`): la stessa versione, nel suo portafoglio ombra, deve avere
   ≥ 20 operazioni chiuse, expectancy > 0 e almeno 60 giorni di attività. Il programma lo impone: una
   strategia con solo il backtest superato resta "in osservazione" e non entra nel portafoglio principale.

Il file di stato si aggiorna con `--write-status` e diventa effettivo solo con un commit revisionato.

## 6. Calendario indicativo

| Settimana | Attività |
|---|---|
| 1 | download 2 anni sul server; controllo qualità |
| 2 | nuove versioni candidate (4h) scritte e committate prima dei test; walk-forward 4h |
| 3 | sensibilità ai costi, analisi per regime, holdout finale; report |
| 4 → | le versioni che superano il backtest girano in portafoglio ombra per ≥ 60 giorni |

## 7. Cosa NON si fa

- Nessuna ottimizzazione su tutto il periodo con successiva "validazione" sullo stesso periodo.
- Nessun aumento del rischio per compensare risultati deboli.
- Nessuna promozione per un solo periodo eccezionale o per i soli risultati di backtest.

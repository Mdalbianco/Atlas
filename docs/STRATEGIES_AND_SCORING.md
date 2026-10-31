# Strategie e sistema di scoring

## Convenzione fondamentale: "R" è sempre al netto dei costi

`1R` = perdita netta se viene colpito lo stop (prezzo di ingresso con spread, slippage e
commissione, meno ricavo netto all'uscita allo stop). Un target "2R" significa
**rendimento netto = 2 × rischio netto**. Le strategie calcolano il target con
`target_for_net_r()` (`atlas/risk/costs.py`), il risk manager lo verifica con
`net_reward_risk()`: le due funzioni sono una l'inversa dell'altra (testato).

Conseguenza pratica: con uno stop stretto i costi pesano di più, quindi il target si
allontana. Lo stesso setup con stop all'1% richiede un movimento lordo molto maggiore
(in R) rispetto a uno stop al 3%.

## Strategie

Tutte **long-only, spot, timeframe 1h con conferma 4h**. Ogni strategia dichiara i **regimi** in cui
ha senso: il motore decisionale non la valuta nemmeno negli altri. Nessuna strategia opera in
`trend_ribassista` o `alta_volatilita`: sono condizioni esplicite di non-operatività.

| Strategia | Versione | Regimi | Idea | Uscita tipica |
|---|---|---|---|---|
| `trend_following` | 1.0.0 | trend rialzista | incrocio EMA20/EMA50 sopra EMA200, ADX in crescita, 4h rialzista | trailing stop o incrocio opposto; target 4R netti |
| `trend_pullback` | 1.0.0 | trend rialzista, laterale | ritracciamento sull'EMA20 in trend con ripresa del momentum | target 2,5R netti o resistenza |
| `breakout` | 1.0.0 | trend rialzista, laterale | rottura del massimo a 20 candele dopo consolidamento, volume ≥ 1,5× | target 2R netti; falso breakout |
| `mean_reversion` | 1.0.0 | **solo laterale** (ADX < 20) | eccesso sotto la banda di Bollinger inferiore, RSI ≤ 35, candela di inversione | media centrale delle bande |
| `volatility_squeeze` | 1.0.0 | laterale, trend rialzista | compressione delle bande (larghezza nel 20% più basso di 120 candele) poi chiusura sopra la banda superiore con volume | target 2R netti; ritorno sotto la media |

Ogni strategia ha: regole di ingresso (`evaluate`), condizioni di invalidazione (`invalidation`),
stop e target propri, parametri configurabili (`default_params`), una griglia piccola fissata a priori
per la validazione (`param_grid`), test dedicati (`tests/test_strategies_scoring.py`,
`tests/test_multistrategy.py`) e metriche per strategia nel backtest e nel paper trading.
Il dimensionamento e i limiti di rischio sono **comuni** e applicati dal risk manager.

### Portafoglio principale e portafogli ombra

- **Principale**: usa solo le versioni marcate `validata` in `atlas/strategy/validation_status.json`
  (file versionato: cambia solo con un commit). È il portafoglio delle notifiche e di `/performance`.
- **Ombra**: ogni strategia candidata non validata ha un proprio conto virtuale da 100 € in
  `data/shadow/<nome>.db`, con le stesse regole di rischio. Non invia notifiche di operazione e non
  influenza il principale. Serve a raccogliere evidenza in tempo reale (`/report`, report settimanale).
- Una strategia ombra non viene mai promossa automaticamente: serve un nuovo `python -m atlas validate`
  su dati reali e la revisione del file di stato.

### `trend_pullback` v1.0.0 — ritracciamento in trend
| Condizione | Valore predefinito |
|---|---|
| Trend 1h rialzista | prezzo > EMA50 > EMA200, EMA20 > EMA50, pendenza EMA50 > 0 |
| Forza del trend | ADX ≥ 18 |
| Timeframe 4h | non ribassista |
| Ritracciamento | minimo di una delle ultime 3 candele entro 0,5 ATR dall'EMA20, chiusura sopra l'EMA20 |
| RSI | 40–68 |
| Momentum | istogramma MACD in aumento |
| Stop | sotto l'ultimo minimo di swing (−0,2 ATR), tra 1 e 3 ATR dal prezzo |
| Target | 2,5 R netti, ridotto sotto una resistenza con ≥ 2 contatti |
| Invalidazione | chiusura sotto EMA50 con trend non più rialzista |

### `breakout` v1.0.0 — rottura confermata dai volumi
| Condizione | Valore predefinito |
|---|---|
| Breakout | chiusura sopra il massimo delle 20 candele precedenti (la precedente era sotto) |
| Consolidamento | escursione delle 20 candele precedenti ≤ 8 ATR |
| Volume | ≥ 1,5 × media delle 20 candele precedenti |
| Filtri | prezzo > EMA50, trend 1h e 4h non ribassisti, RSI ≤ 75, candela ≤ 2,5 ATR |
| Stop | sotto il livello rotto (−0,5 ATR), tra 1,5 e 3 ATR |
| Target | 2 R netti |
| Invalidazione | entro 6 candele, chiusura sotto il livello rotto − 0,5 ATR (falso breakout) |

### Gestione comune della posizione (`engine/position_manager.py`)
1. Stop e target controllati intrabar (candele a 5 minuti nel live, candele 1h nel backtest).
   Se nella stessa candela sono toccati entrambi, si assume **lo stop** (ipotesi prudente).
   In caso di gap oltre lo stop si esce al prezzo di apertura, non allo stop.
2. Trailing stop: dopo +1R lo stop sale a `max(pareggio netto dei costi, massimo − 2,5 ATR)` e non scende mai.
3. Stop temporale: dopo 48 candele senza aver mai raggiunto +1R.
4. Invalidazione specifica della strategia.

## Scoring (`atlas/scoring.py`)

Punteggio = media pesata di 9 componenti, ognuna 0–100 con regole esplicite:

| Componente | Peso | Regola (sintesi) |
|---|---|---|
| trend | 0,15 | rialzista 60 + fino a 40 per ADX (fino a 40); laterale 30; ribassista 0 |
| momentum | 0,15 | ½ RSI (50–65 → 100 … estremi → 10) + ½ MACD (positivo in accelerazione 100 … negativo in accelerazione 0) |
| volume | 0,10 | volume relativo ≥1,5 → 90; ≥1 → 70; ≥0,6 → 45; altrimenti 20; −25 se divergenza OBV |
| price_action | 0,10 | struttura HH/HL 80, mista 50, indefinita 40, LH/LL 10; ±pattern di candela; +10 breakout/pullback |
| volatility | 0,10 | ATR% sotto i costi A/R → 10; ≤3% → 100; ≤5% → 60; oltre 20; −30 se volatilità estrema; 0 se anomalia |
| reward_risk | 0,15 | R/R netto sotto il minimo → 0–40; dal minimo a 3 → 50–100 |
| levels | 0,10 | spazio fino alla resistenza ≥3 ATR → 100; ≥1,5 → 60; <1,5 → 15; +10 con supporto solido vicino |
| timeframes | 0,10 | trend 4h rialzista 100, laterale 50, ribassista 0 |
| market | 0,05 | riferimento generale (BTC 4h) favorevole 100, neutro 50, sfavorevole 10 |

Categorie: `≥75` elevata qualità secondo il modello · `65–74` potenzialmente interessante ·
`55–64` da monitorare · `40–54` debole · `<40` nessuna opportunità. Soglia operativa
predefinita: **65** (`ATLAS_MIN_SCORE`).

> Lo score misura quanto il setup corrisponde al modello. **Non è una probabilità di
> profitto** e un punteggio alto non obbliga a operare: il risk manager può rifiutare qualunque segnale.

## Validazione dello score e delle soglie

> **Aggiornamento 31/10/2026 — dati reali:** su un anno di dati Kraken la fascia di score ≥ 75 non ha reso meglio
> della fascia 65–74 e nessuna strategia ha superato la validazione. Vedi [VALIDATION_REPORT.md](VALIDATION_REPORT.md).
> I numeri sintetici qui sotto restano solo come verifica della meccanica.

Il backtest riporta i risultati per fascia di score (`by_score`). Uno score utile deve
mostrare expectancy crescente con il punteggio. Risultato sui **dati sintetici**
(4 seed × 5.000 candele × 3 asset, soglia 0 per osservare tutte le fasce):

| Fascia | Operazioni | Win rate | Expectancy |
|---|---|---|---|
| 55–64 | 79 | 43% | −0,25 R |
| 65–74 | 269 | 54% | −0,03 R |
| 75–100 | 283 | 58% | +0,28 R |

Per strategia: `trend_pullback` +0,13 R su 508 operazioni, `breakout` **−0,12 R** su 129.

Lettura: lo score è monotono (fasce più alte → expectancy migliore), ma sui dati sintetici
solo la fascia ≥ 75 è chiaramente positiva e `breakout` è negativa. **La soglia 65 non viene
modificata** sulla base di dati artificiali: sarebbe overfitting. Sono due ipotesi da verificare
con il walk-forward su dati reali (soglia 75; disattivazione di `breakout`).

**Questi numeri verificano solo che la meccanica sia coerente.** I dati sintetici contengono
regimi di trend generati artificialmente, favorevoli per costruzione alle strategie trend
following. Non sono evidenza di redditività. La stessa analisi va ripetuta su dati Kraken reali
(`docs/BACKTESTING.md`), e in quel caso il risultato può essere negativo.

## Ciclo di vita e promozione delle strategie

`in_validazione` → (`python -m atlas validate`) → `validata` | `respinta` → (eventuale nuova versione)

Criteri (`atlas/strategy/validation.py`, tutti obbligatori, solo periodi **fuori campione**, costi inclusi):

| Criterio | Soglia |
|---|---|
| Operazioni fuori campione | ≥ 30 |
| Expectancy netta | ≥ +0,05 R |
| Profit factor | ≥ 1,15 |
| Drawdown massimo | ≤ 15% |
| Periodi di test positivi | ≥ 50% |

Il report confronta sempre ogni strategia con il **buy & hold** degli stessi periodi. Un buon risultato
storico è condizione necessaria, non sufficiente: dopo la promozione il rilevamento del degrado confronta
le ultime 15 operazioni reali con l'expectancy attesa e segnala (senza agire da solo) i peggioramenti.

Ogni modifica della logica o dei parametri predefiniti richiede una **nuova versione** (`version`):
la nuova versione riparte da "non validata". ATLAS genera proposte (`/report`), ma **non modifica mai
da solo** strategie, pesi, soglie o file di stato.

# Report di validazione su dati reali Kraken — 31/10/2026

> Questo documento distingue tre cose diverse: **validazione fuori campione** (sezione 1, l'unica che decide la
> promozione), **diagnosi** con ipotesi di costo non realistiche (sezione 2) e **backtest storico** con parametri
> predefiniti (sezione 3). Nessuno di questi è performance effettiva: il paper trading dal vivo è appena iniziato.
> Risultati passati non garantiscono risultati futuri.

**Esito: nessuna strategia supera la validazione. Il portafoglio principale resta senza strategie attive
(non opera); tutte e cinque continuano in portafogli ombra isolati per raccogliere evidenza.**

### Dati
- BTC/EUR, ETH/EUR, SOL/EUR, candele 1h dal 31/10/2025 al 31/10/2026 (8.755 per coppia).
- Ricostruiti dai trade pubblici Kraken con `python -m atlas history` (11.942 + 5.480 + 5.253 richieste).
- Verifica: sulle 716 candele sovrapposte all'OHLC ufficiale Kraken lo scarto massimo delle chiusure è 0,0000%.
- Un solo buco di 5 ore (01/11/2025 15:00–21:00 UTC), identico sulle tre coppie: interruzione dell'exchange; cade nel
  periodo di riscaldamento degli indicatori.
- Contesto di mercato: anno fortemente ribassista fino ad agosto 2026 (ETH 3.341 → 1.379 €, SOL 163 → 64 €), poi rimbalzo.

## 1. Validazione walk-forward con costi realistici (decisione di promozione)

Generato: 2026-10-31T16:50:39 UTC  
Dati: BTC/EUR, ETH/EUR, SOL/EUR — 2025-10-31 → 2026-10-31 (8755 candele 1h)  
Fonte: trade pubblici Kraken aggregati in candele 1h (python -m atlas history), verificati contro l'OHLC ufficiale  
Costi: commissione 0.4% + slippage 0.05% per lato, spread 0.1%  
Walk-forward: training 2000 candele, test 1000 candele

Tutti i numeri sotto sono **fuori campione** (periodi di test mai usati per scegliere i parametri).

| Strategia | Esito | Operazioni | Win rate | Expectancy | Profit factor | Rendimento OOS | Buy & hold | Max DD | Fold positivi |
|---|---|---|---|---|---|---|---|---|---|
| trend_following@1.0.0 | ❌ respinta | 6 | 50% | -0.172 R | 0.61 | -0.87% | 13.69% | 1.83% | 33% |
| trend_pullback@1.0.0 | ❌ respinta | 48 | 44% | -0.270 R | 0.44 | -10.23% | 13.69% | 10.23% | 50% |
| breakout@1.0.0 | ❌ respinta | 38 | 32% | -0.423 R | 0.45 | -9.94% | 13.69% | 9.94% | 17% |
| mean_reversion@1.0.0 | ❌ respinta | 0 | n/d% | n/d R | n/d | 0.00% | 13.69% | 0.00% | 0% |
| volatility_squeeze@1.0.0 | ❌ respinta | 18 | 28% | -0.550 R | 0.14 | -8.24% | 13.69% | 8.24% | 17% |

### Dettaglio per strategia

#### trend_following@1.0.0 — respinta

Motivo: solo 6 operazioni fuori campione (minimo 30); expectancy -0.172 R sotto il minimo 0.05; profit factor 0.61 sotto il minimo 1.15; solo il 33% dei periodi di test è positivo
Configurazioni provate in ogni training: 12 (griglia {'min_score': [60.0, 65.0, 70.0], 'target_r': [3.0, 4.0], 'stop_atr': [2.0, 2.5]})
Stabilità dei parametri tra i fold: 0.50

| Test | Parametri | Operazioni | Expectancy | Rendimento | Buy & hold |
|---|---|---|---|---|---|
| 2026-03-01 → 2026-04-12 | {'min_score': 60.0, 'target_r': 3.0, 'stop_atr': 2.0} | 0 | n/d R | 0.00% | 4.47% |
| 2026-04-12 → 2026-05-23 | {'min_score': 60.0, 'target_r': 3.0, 'stop_atr': 2.0} | 3 | 0.085 R | 0.17% | 2.31% |
| 2026-05-23 → 2026-07-04 | {'min_score': 60.0, 'target_r': 3.0, 'stop_atr': 2.5} | 0 | n/d R | 0.00% | -12.77% |
| 2026-07-04 → 2026-08-15 | {'min_score': 60.0, 'target_r': 3.0, 'stop_atr': 2.5} | 1 | -0.318 R | -0.23% | -2.56% |
| 2026-08-15 → 2026-09-25 | {'min_score': 60.0, 'target_r': 3.0, 'stop_atr': 2.5} | 1 | 0.296 R | 0.19% | 46.06% |
| 2026-09-25 → 2026-10-31 | {'min_score': 65.0, 'target_r': 3.0, 'stop_atr': 2.5} | 1 | -1.266 R | -1.00% | -14.32% |

Per regime: trend_rialzista: 6 op., -0.17 R
Per asset: BTC/EUR: 3 op., -0.83 R; ETH/EUR: 3 op., 0.49 R

#### trend_pullback@1.0.0 — respinta

Motivo: expectancy -0.270 R sotto il minimo 0.05; profit factor 0.44 sotto il minimo 1.15
Configurazioni provate in ogni training: 6 (griglia {'min_score': [60.0, 65.0, 70.0], 'target_r': [2.0, 2.5]})
Stabilità dei parametri tra i fold: 0.50

| Test | Parametri | Operazioni | Expectancy | Rendimento | Buy & hold |
|---|---|---|---|---|---|
| 2026-03-01 → 2026-04-12 | {'min_score': 60.0, 'target_r': 2.5} | 20 | -0.468 R | -7.81% | 4.47% |
| 2026-04-12 → 2026-05-23 | {'min_score': 70.0, 'target_r': 2.0} | 4 | 0.111 R | 0.35% | 2.31% |
| 2026-05-23 → 2026-07-04 | {'min_score': 70.0, 'target_r': 2.0} | 2 | 0.034 R | 0.06% | -12.77% |
| 2026-07-04 → 2026-08-15 | {'min_score': 70.0, 'target_r': 2.5} | 4 | -0.708 R | -2.26% | -2.56% |
| 2026-08-15 → 2026-09-25 | {'min_score': 70.0, 'target_r': 2.0} | 12 | 0.058 R | 0.52% | 46.06% |
| 2026-09-25 → 2026-10-31 | {'min_score': 70.0, 'target_r': 2.5} | 6 | -0.327 R | -1.28% | -14.32% |

Per regime: laterale: 7 op., 0.17 R; trend_rialzista: 41 op., -0.34 R
Per asset: BTC/EUR: 17 op., -0.19 R; ETH/EUR: 13 op., -0.35 R; SOL/EUR: 18 op., -0.29 R

#### breakout@1.0.0 — respinta

Motivo: expectancy -0.423 R sotto il minimo 0.05; profit factor 0.45 sotto il minimo 1.15; solo il 17% dei periodi di test è positivo
Configurazioni provate in ogni training: 6 (griglia {'min_score': [60.0, 65.0, 70.0], 'target_r': [2.0, 2.5]})
Stabilità dei parametri tra i fold: 0.33

| Test | Parametri | Operazioni | Expectancy | Rendimento | Buy & hold |
|---|---|---|---|---|---|
| 2026-03-01 → 2026-04-12 | {'min_score': 70.0, 'target_r': 2.0} | 5 | 0.024 R | -0.14% | 4.47% |
| 2026-04-12 → 2026-05-23 | {'min_score': 70.0, 'target_r': 2.0} | 5 | -1.352 R | -4.21% | 2.31% |
| 2026-05-23 → 2026-07-04 | {'min_score': 65.0, 'target_r': 2.5} | 8 | -0.116 R | -0.89% | -12.77% |
| 2026-07-04 → 2026-08-15 | {'min_score': 65.0, 'target_r': 2.5} | 6 | -0.614 R | -2.54% | -2.56% |
| 2026-08-15 → 2026-09-25 | {'min_score': 65.0, 'target_r': 2.0} | 8 | -0.135 R | 0.20% | 46.06% |
| 2026-09-25 → 2026-10-31 | {'min_score': 60.0, 'target_r': 2.5} | 6 | -0.627 R | -2.73% | -14.32% |

Per regime: laterale: 15 op., -0.67 R; trend_rialzista: 23 op., -0.26 R
Per asset: BTC/EUR: 13 op., -0.96 R; ETH/EUR: 10 op., 0.20 R; SOL/EUR: 15 op., -0.38 R

#### mean_reversion@1.0.0 — respinta

Motivo: solo 0 operazioni fuori campione (minimo 30); expectancy +0.000 R sotto il minimo 0.05; profit factor 0.00 sotto il minimo 1.15; solo il 0% dei periodi di test è positivo
Configurazioni provate in ogni training: 6 (griglia {'min_score': [60.0, 65.0, 70.0], 'rsi_max': [30.0, 35.0]})
Stabilità dei parametri tra i fold: 1.00

| Test | Parametri | Operazioni | Expectancy | Rendimento | Buy & hold |
|---|---|---|---|---|---|
| 2026-03-01 → 2026-04-12 | {'min_score': 60.0, 'rsi_max': 30.0} | 0 | n/d R | 0.00% | 4.47% |
| 2026-04-12 → 2026-05-23 | {'min_score': 60.0, 'rsi_max': 30.0} | 0 | n/d R | 0.00% | 2.31% |
| 2026-05-23 → 2026-07-04 | {'min_score': 60.0, 'rsi_max': 30.0} | 0 | n/d R | 0.00% | -12.77% |
| 2026-07-04 → 2026-08-15 | {'min_score': 60.0, 'rsi_max': 30.0} | 0 | n/d R | 0.00% | -2.56% |
| 2026-08-15 → 2026-09-25 | {'min_score': 60.0, 'rsi_max': 30.0} | 0 | n/d R | 0.00% | 46.06% |
| 2026-09-25 → 2026-10-31 | {'min_score': 60.0, 'rsi_max': 30.0} | 0 | n/d R | 0.00% | -14.32% |

#### volatility_squeeze@1.0.0 — respinta

Motivo: solo 18 operazioni fuori campione (minimo 30); expectancy -0.550 R sotto il minimo 0.05; profit factor 0.14 sotto il minimo 1.15; solo il 17% dei periodi di test è positivo
Configurazioni provate in ogni training: 6 (griglia {'min_score': [60.0, 65.0, 70.0], 'target_r': [2.0, 2.5]})
Stabilità dei parametri tra i fold: 0.50

| Test | Parametri | Operazioni | Expectancy | Rendimento | Buy & hold |
|---|---|---|---|---|---|
| 2026-03-01 → 2026-04-12 | {'min_score': 65.0, 'target_r': 2.0} | 6 | -0.134 R | -1.62% | 4.47% |
| 2026-04-12 → 2026-05-23 | {'min_score': 70.0, 'target_r': 2.0} | 2 | -1.341 R | -1.92% | 2.31% |
| 2026-05-23 → 2026-07-04 | {'min_score': 70.0, 'target_r': 2.0} | 1 | 0.050 R | 0.04% | -12.77% |
| 2026-07-04 → 2026-08-15 | {'min_score': 65.0, 'target_r': 2.0} | 2 | -0.756 R | -1.12% | -2.56% |
| 2026-08-15 → 2026-09-25 | {'min_score': 70.0, 'target_r': 2.5} | 3 | -0.780 R | -1.97% | 46.06% |
| 2026-09-25 → 2026-10-31 | {'min_score': 65.0, 'target_r': 2.0} | 4 | -0.652 R | -1.93% | -14.32% |

Per regime: laterale: 7 op., -0.82 R; trend_rialzista: 11 op., -0.38 R
Per asset: BTC/EUR: 4 op., -0.66 R; ETH/EUR: 4 op., 0.33 R; SOL/EUR: 10 op., -0.86 R

### Criteri di promozione

- `min_oos_trades` = 30
- `min_expectancy_r` = 0.05
- `min_profit_factor` = 1.15
- `max_drawdown_pct` = 15.0
- `min_positive_folds_ratio` = 0.5

Una strategia respinta non entra nel portafoglio principale: continua a girare in un portafoglio ombra isolato per raccogliere evidenza. Nessun risultato passato garantisce risultati futuri.

## 2. Diagnosi: le perdite dipendono dai costi o dall'assenza di vantaggio?

Stessi dati e stesso walk-forward, cambiando solo le ipotesi di costo. **Non usati per decidere nulla.**

**a) Costi azzerati** (e R/R minimo 1,0) — irrealistico, misura il vantaggio lordo:

| Strategia | Esito | Operazioni | Win rate | Expectancy | Profit factor | Rendimento OOS | Buy & hold | Max DD | Fold positivi |
|---|---|---|---|---|---|---|---|---|---|
| trend_following@1.0.0 | ❌ respinta | 6 | 67% | 0.913 R | 3.01 | 2.42% | 20.72% | 1.10% | 50% |
| trend_pullback@1.0.0 | ✅ validata | 105 | 44% | 0.067 R | 1.16 | 3.92% | 20.72% | 5.56% | 50% |
| breakout@1.0.0 | ❌ respinta | 83 | 30% | 0.047 R | 1.30 | 4.83% | 20.72% | 2.36% | 67% |
| mean_reversion@1.0.0 | ❌ respinta | 0 | n/d% | n/d R | n/d | 0.00% | 20.72% | 0.00% | 0% |
| volatility_squeeze@1.0.0 | ✅ validata | 50 | 44% | 0.187 R | 1.29 | 2.84% | 20.72% | 2.54% | 50% |

**b) Ordini limite "maker"**: commissione 0,25%, slippage 0, tutti gli ordini eseguiti (ipotesi ottimistica):

| Strategia | Esito | Operazioni | Win rate | Expectancy | Profit factor | Rendimento OOS | Buy & hold | Max DD | Fold positivi |
|---|---|---|---|---|---|---|---|---|---|
| trend_following@1.0.0 | ❌ respinta | 6 | 50% | 0.137 R | 1.11 | 0.19% | 16.45% | 2.10% | 33% |
| trend_pullback@1.0.0 | ❌ respinta | 83 | 48% | -0.184 R | 0.60 | -12.56% | 16.45% | 14.63% | 17% |
| breakout@1.0.0 | ❌ respinta | 52 | 35% | -0.398 R | 0.53 | -8.73% | 16.45% | 8.73% | 17% |
| mean_reversion@1.0.0 | ❌ respinta | 0 | n/d% | n/d R | n/d | 0.00% | 16.45% | 0.00% | 0% |
| volatility_squeeze@1.0.0 | ❌ respinta | 27 | 33% | -0.574 R | 0.19 | -9.42% | 16.45% | 9.42% | 0% |

Lettura:
- A costi zero `trend_pullback` (+0,07 R) e `volatility_squeeze` (+0,19 R) mostrano un piccolo vantaggio lordo che i
  costi reali (~1% andata e ritorno con commissioni taker) cancellano. Anche con commissioni maker resta negativo.
- Su candele orarie i movimenti tipici (ATR 0,5–0,8% nel periodo recente) sono dello stesso ordine dei costi: con un
  conto da 100 € e commissioni Kraken del livello base il timeframe 1h è strutturalmente sfavorevole.
- `mean_reversion` non trova quasi mai le sue condizioni: su ~7.855 candele per asset gli eccessi con RSI ≤ 35
  avvengono quasi sempre in trend ribassista (filtrati di proposito). Le condizioni complete si sono verificate 1–2 volte.

## 3. Backtest storico dell'intero anno (tutte le strategie insieme, parametri predefiniti)

I parametri predefiniti sono stati fissati prima di scaricare questi dati: non sono ottimizzati su di essi.

| Voce | Valore |
|---|---|
| Capitale | 100,00 → 85.32 € (-14.68%) |
| Buy & hold (stesso periodo, costi inclusi) | -38.66% (drawdown 58.0%) |
| Drawdown massimo | 15.13% → l'arresto al 15% ha fermato le nuove operazioni |
| Operazioni | 33 (win rate 33%, profit factor 0.08) |
| Expectancy | -0.62 R per operazione |
| Costi totali | 8.32 € |
| Tempo investito | 2.9% |

In un anno in cui il mercato ha perso il 39%, ATLAS avrebbe perso il 15% e poi si sarebbe fermato da solo: la
protezione del capitale ha funzionato, ma il sistema **non ha prodotto rendimenti positivi**.

## 4. Proposte (registrate, NON applicate)

1. **Timeframe più lunghi** (4h operativo, 1d di conferma): movimenti più ampi riducono il peso dei costi. Richiede
   2–3 anni di storico (stimate 10–15 ore di download con `atlas history`) e nuove versioni delle strategie.
2. **Rivedere i pesi dello scoring**: su dati reali la fascia ≥ 75 non rende meglio della fascia 65–74.
3. **`trend_pullback`**: le uscite per invalidazione costano in media −0,87 R; valutare una regola di invalidazione
   diversa in una versione 1.1.0, da validare con walk-forward.
4. **Esecuzione maker** (ordini limite post-only) solo dopo aver modellato la probabilità di esecuzione: l'ipotesi
   "tutti eseguiti" è ottimistica e già insufficiente.
5. Continuare il paper trading dei portafogli ombra per almeno 3 mesi: è evidenza reale e indipendente dal backtest.

## Come riprodurre

```bash
python -m atlas history BTC/EUR --days 365 --out data/history/BTC_EUR_1h.csv   # idem ETH/EUR, SOL/EUR
python -m atlas validate --csv data/history/*_EUR_1h.csv --out reports/validazione
python -m atlas backtest --csv data/history/*_EUR_1h.csv
```

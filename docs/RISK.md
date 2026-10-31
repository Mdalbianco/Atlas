# Gestione del rischio

Il risk manager (`atlas/risk/manager.py`) è l'unico componente che può approvare una
posizione. Un segnale che viola **anche una sola** regola viene rifiutato, qualunque sia il punteggio.

## Regole predefinite

| Regola | Default | Variabile |
|---|---|---|
| Rischio per operazione (perdita netta allo stop) | 1% del capitale | `ATLAS_RISK_PER_TRADE_PCT` (max 2) |
| R/R minimo **al netto dei costi** | 1,8 | `ATLAS_MIN_REWARD_RISK` |
| Costi A/R massimi rispetto al rischio | 60% | (costante) |
| Dimensione massima di una posizione | 50% del capitale | `ATLAS_MAX_POSITION_PCT` |
| Esposizione totale massima | 80% | `ATLAS_MAX_EXPOSURE_PCT` |
| Posizioni contemporanee | 2 | `ATLAS_MAX_OPEN_POSITIONS` |
| Una sola posizione per coppia | sempre | vincolo UNIQUE nel database |
| Perdita giornaliera massima (UTC) | 3% → blocco fino al giorno dopo | `ATLAS_MAX_DAILY_LOSS_PCT` |
| Drawdown massimo dal picco | 15% → **arresto**, sblocco solo manuale | `ATLAS_MAX_DRAWDOWN_PCT` |
| Perdite consecutive | 4 → pausa di 24h | `ATLAS_MAX_CONSECUTIVE_LOSSES`, `ATLAS_COOLDOWN_HOURS` |
| Rischio su asset correlati (ρ ≥ 0,8, ultime 168 candele) | 1,5% | `ATLAS_MAX_CORRELATED_RISK_PCT` |
| Spread massimo | 0,5% | `ATLAS_MAX_SPREAD_PCT` |
| Minimo d'ordine | max(minimo Kraken, 5 €) | `ATLAS_MIN_ORDER_COST` |
| Movimento anomalo dell'ultima candela | > 4 × ATR → nessuna operazione | `ATLAS_MAX_BAR_MOVE_ATR` |
| Dati non aggiornati | > 180 min oltre la chiusura attesa → nessuna operazione | `ATLAS_MAX_DATA_AGE_MINUTES` |
| Errore imprevisto nel ciclo | **arresto** + notifica | — |

Niente leva, margine, derivati o vendite allo scoperto: lo spot long-only è imposto dal codice
(i segnali sono solo long; il broker simulato vende solo quantità possedute).

## Dimensionamento

```
rischio_netto_unitario = (prezzo_acquisto × (1+commissione)) − (stop × (1−frizione) × (1−commissione))
quantità = (capitale × rischio%) / rischio_netto_unitario
```
poi ridotta, nell'ordine, da: dimensione massima, esposizione residua, liquidità,
limite di correlazione; infine arrotondata al passo dell'exchange e confrontata con i minimi.

## Il problema del capitale piccolo (100 €)

Costi simulati per lato: commissione taker 0,40% (livello base Kraken Pro) + metà spread
0,05% + slippage 0,05% = **0,50%**, quindi **~1% andata e ritorno**.

| Stop dall'ingresso | Target 2,5R lordi diventano… | Costi / rischio | Controvalore posizione (rischio 1 €) |
|---|---|---|---|
| 1,5% | 1,10 R netti | 40% | ~40 € |
| 2,0% | 1,33 R netti | 33% | ~34 € |
| 3,0% | 1,62 R netti | 25% | ~25 € |
| 4,0% | 1,80 R netti | 20% | ~20 € |

(Valori calcolati con `atlas/risk/costs.py`.)

Implicazioni:
- Con 100 € e rischio 1%, la perdita massima per operazione è ~1 €, e le commissioni di
  un'operazione completa valgono 0,15–0,35 €. **I costi sono il primo avversario.**
- Le operazioni su timeframe brevi (stop < 1,5%) sono strutturalmente svantaggiate: per questo
  il sistema esprime i target in R netti e rifiuta i setup in cui i costi superano il 60% del rischio.
- I minimi d'ordine Kraken (dell'ordine di pochi euro per le coppie principali, letti in tempo
  reale da `load_markets`) sono compatibili con posizioni da 20–50 €, ma impediscono di
  frazionare ulteriormente il capitale.
- Le commissioni maker (0,25%) ridurrebbero i costi, ma richiedono ordini limite che possono non
  essere eseguiti: in v1 si assume prudentemente sempre la commissione taker.

## Arresti e ripresa

- **Blocco** (perdita giornaliera, perdite consecutive, numero di posizioni, pausa): nessuna nuova
  posizione; si risolve da solo (nuovo giorno, scadenza della pausa, chiusura di una posizione) o con `/riprendi`.
- **Arresto di sicurezza** (drawdown massimo, errore imprevisto): nessuna nuova posizione finché un
  amministratore non invia `/riprendi conferma`. Dopo un arresto per drawdown il riferimento del picco
  viene riportato al capitale attuale.
- In entrambi i casi **le posizioni aperte continuano a essere gestite** (stop, target, trailing):
  bloccare la gestione sarebbe più rischioso che proseguirla.

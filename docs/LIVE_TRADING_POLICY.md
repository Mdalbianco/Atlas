# Politica sul trading reale

**Stato in v1: il trading reale NON è implementato e non è attivabile.**

## Protezioni presenti nel codice

1. `Settings.validate()` rifiuta l'avvio con qualsiasi `ATLAS_MODE` diverso da `paper`.
2. `atlas/execution/live.py`: `LiveBroker` solleva sempre `LiveTradingDisabled`.
3. `atlas/data/exchange.py`: il client CCXT è avvolto in `ReadOnlyExchange`, che consente solo
   `load_markets`, `fetch_ohlcv`, `fetch_ticker`, `fetch_order_book`, `fetch_time`, `fetch_status`,
   `fetch_balance`. Qualsiasi altro metodo (`create_order`, `withdraw`, `cancel_order`, endpoint
   privati) solleva `PermissionError`.
4. Un test (`test_no_order_methods_in_codebase`) fallisce se nel package compaiono chiamate a metodi di trading.
5. Il paper broker non effettua chiamate di rete.
6. Il possesso di API key **non** abilita nulla: servono solo a leggere il saldo.

## Procedura per un'eventuale abilitazione futura

Tutte le condizioni sono necessarie:

1. **Evidenza**: almeno 3 mesi di paper trading continuo e una validazione walk-forward su almeno
   2 anni di dati reali, con i criteri di `docs/STRATEGIES_AND_SCORING.md` soddisfatti e documentati.
2. **Autorizzazione esplicita e scritta** del proprietario del capitale, con importo massimo, coppie
   ammesse e perdita massima accettata.
3. **Implementazione separata** in un branch dedicato, con revisione del codice: broker reale con
   ordini idempotenti (`userref`/`cl_ord_id` Kraken), riconciliazione degli ordini e del saldo a ogni
   ciclo, stop lato exchange, kill switch, limiti di importo hard-coded.
4. **API key dedicata** con permessi minimi (query + create/modify orders), **mai** prelievi,
   restrizione IP, importo iniziale piccolo.
5. **Doppia conferma di configurazione**: `ATLAS_MODE=live` più una variabile di conferma con frase
   esplicita, verificate all'avvio, e un comando Telegram di conferma da un admin.
6. Periodo iniziale con capitale ridotto e revisione settimanale dei risultati reali contro quelli simulati.

Fino ad allora ATLAS è uno strumento di analisi e simulazione.

"""Esecuzione REALE — DISABILITATA in ATLAS v1.

Questo modulo esiste solo per rendere esplicito il confine tra simulazione e
denaro reale. Non contiene alcuna chiamata a ``create_order`` né ad altri
endpoint privati di trading, e il client Kraken è avvolto in un proxy che
blocca qualunque metodo diverso dalla lettura (``atlas/data/exchange.py``).

L'abilitazione futura richiede, tutti insieme (vedi docs/LIVE_TRADING_POLICY.md):
1. autorizzazione scritta e esplicita del proprietario del capitale;
2. un'implementazione separata, revisionata e testata in un branch dedicato;
3. ``ATLAS_MODE=live`` + ``ATLAS_LIVE_CONFIRMATION`` con la frase prevista;
4. almeno 3 mesi di paper trading con risultati documentati.

Il solo possesso di API key NON abilita nulla.
"""

from __future__ import annotations


class LiveTradingDisabled(RuntimeError):
    pass


class LiveBroker:
    mode = "live"

    def __init__(self, *args, **kwargs) -> None:
        raise LiveTradingDisabled(
            "Il trading reale non è disponibile in ATLAS v1. "
            "Consulta docs/LIVE_TRADING_POLICY.md per la procedura di autorizzazione."
        )

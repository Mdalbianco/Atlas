# Hosting 24/7: confronto e raccomandazione

Ricerca svolta il 31/10/2026. Le condizioni dei provider cambiano spesso e diverse fonti sono
blog di terze parti, a volte in disaccordo tra loro: **verifica sempre la pagina ufficiale del
provider prima di creare risorse**. Nessuna risorsa è stata creata da Claude.

## Requisiti reali di ATLAS (misurati)

| Risorsa | Valore misurato |
|---|---|
| RAM | ~146 MB (processo completo con bot, scheduler e 5 portafogli ombra) |
| CPU | ~2% di un core in media (picchi brevi a ogni ciclo) |
| Disco | < 1 MB di database dopo i primi cicli; immagine Docker ~560 MB |
| Rete | solo connessioni in uscita verso api.kraken.com e api.telegram.org; nessuna porta in ingresso |

Basta quindi la più piccola macchina virtuale disponibile. Serve però un **processo sempre attivo**
con **disco persistente**: le piattaforme che "addormentano" i servizi gratuiti non vanno bene.

## Confronto

| Opzione | Costo | Pro | Limiti / rischi |
|---|---|---|---|
| **Google Cloud e2-micro (Always Free)** | 0 € entro i limiti | 1 GB RAM sufficienti; nessuna regola di recupero delle VM inattive nelle fonti consultate; console usabile da browser con SSH integrato | solo regioni us-west1, us-central1, us-east1; una sola e2-micro gratuita; disco *standard* fino a 30 GB; richiede account di fatturazione con carta: ciò che esce dai limiti viene addebitato |
| **Oracle Cloud Always Free (ARM A1)** | 0 € | risorse abbondanti (secondo le fonti, dal 2026 ridotte a 2 OCPU / 12 GB) | le VM "inattive" (CPU, rete e memoria sotto il 20% per 7 giorni) **possono essere recuperate da Oracle**: ATLAS usa ~2% di CPU, quindi è a rischio; spesso capacità ARM esaurita in fase di creazione |
| **Hetzner Cloud** (CX/CAX) | ~5,5–6 €/mese + IVA (dopo gli aumenti 2026) | semplice, datacenter in UE, prezzo prevedibile | a pagamento; secondo alcune fonti i tagli più economici risultano a tratti non ordinabili |
| **Fly.io** | ~2–5 $/mese + volume | container nativi | fatturazione a consumo meno prevedibile |
| Render / Railway | da ~5–7 $/mese | PaaS semplici | worker sempre attivi e volumi a pagamento |
| GitHub Codespaces | — | ottimo per sviluppo | **si sospende per inattività**: non adatto al 24/7 |

## Raccomandazione

1. **Google Cloud e2-micro gratuita** (regione `us-central1`, disco *standard* 30 GB, Ubuntu 24.04 LTS).
   È la soluzione gratuita con meno rischi operativi per un processo leggero come ATLAS, e si gestisce
   interamente dal browser dell'iPad (pulsante "SSH" nella console). La latenza dagli Stati Uniti verso
   Kraken e Telegram è irrilevante per un sistema che decide su candele orarie.
   Imposta subito un **avviso di budget** (es. 1 €) nella console di fatturazione.
2. Se preferisci un server in Europa e un costo fisso senza carta collegata a un cloud "a consumo":
   **Hetzner**, la macchina più piccola disponibile (~6 €/mese).
3. Oracle Always Free è valido solo convertendo l'account a "Pay As You Go" (le risorse Always Free
   restano gratuite secondo Oracle), per evitare il recupero delle VM inattive: è una scelta che comporta
   un account con fatturazione attiva e quindi spetta a te.

La procedura passo-passo è in [GUIDA_IPAD.md](GUIDA_IPAD.md). Lo stesso `deploy/install.sh` funziona su
tutte le opzioni basate su VM (x86_64 e ARM64).

## Cosa è stato verificato davvero

- Immagine Docker costruita ed eseguita in questo ambiente: utente non root, filesystem in sola lettura,
  health check OK, dati persistenti dopo la ricreazione del container, **riavvio automatico dopo un crash
  simulato** (`RestartCount=1`, di nuovo sano), arresto ordinato su SIGTERM in ~4 s.
- `install.sh`, `update.sh` e `backup-offsite.sh`: solo controllo di sintassi (`bash -n`), **non**
  eseguiti su un server reale (nessun accesso a un account di hosting).

## Fonti

- Oracle: [Always Free Resources (documentazione ufficiale)](https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm),
  [riduzione A1 e recupero VM inattive](https://www.itechguides.com/oracle-cloud-giving-away-ampere-arm-a1-instances-always-free-the-2026-limits-explained/),
  [analisi dei limiti 2026](https://www.mrplanb.com/datacenter/free-vps-tiers)
- Google Cloud: [guida al free tier 2026](https://agentdeals.dev/gcp-free-tier-2026),
  [riepilogo Compute Engine free tier](https://agentdeals.dev/vendor/google-compute-engine)
- Hetzner: [prezzi dopo gli aumenti 2026](https://www.bitdoze.com/hetzner-cloud-cost-optimized-plans/),
  [tabella prezzi 2026](https://vpsdex.com/en/activity/hetzner-cloud-pricing-2026/),
  [prezzi correnti](https://cloudtally.eu/hetzner-cloud-prices)
- PaaS: [Railway vs Render vs Fly.io 2026](https://devtoolpicks.com/blog/railway-vs-render-vs-fly-io-solo-developers-2026),
  [confronto con numeri reali](https://dev.to/whoffagents/flyio-vs-railway-vs-render-in-2026-where-to-deploy-your-ai-saas-with-real-numbers-3b0f)

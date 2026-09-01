# RealFlipping — Investi nel mattone, con metodo

Demo web di una piattaforma di investimento immobiliare che unisce **flipping**
(acquisto e valorizzazione di un intero immobile) e **crowdfunding immobiliare**
(partecipazione per quote a operazioni di ristrutturazione), con dashboard
dedicata per seguire cantiere, numeri e situazione fiscale stimata.

## Contenuto

- `index.html` — applicazione a pagina singola (HTML/CSS/JS, nessuna dipendenza
  esterna): landing page, area di login demo, elenco progetti, dashboard
  investitore (con grafici di composizione portafoglio e rendimento per
  operazione) e sezione Backoffice interna (con classifica a barre delle
  zone e spiegazioni per zona).
- `tools/palermo_zone_scoring.py` — motore quantitativo (senza LLM) che
  calcola un punteggio di investibilità 0–100 per zona di Palermo, con
  rendimento netto stimato, indice di affidabilità del dato (penalizza le
  variazioni statisticamente poco solide invece di limitarsi a segnalarle)
  e un generatore di spiegazioni testuali per zona (template deterministico,
  pensato per essere sostituito 1:1 da una vera chiamata LLM — vedi i
  commenti nel file per la metodologia completa).
- `tools/update_index_scores.py` — rigenera i dati mostrati nel Backoffice
  dentro `index.html` a partire dallo scoring engine.
- `.github/workflows/update-zone-scores.yml` — esegue `update_index_scores.py`
  una volta al giorno e committa i nuovi numeri in automatico (una piccola
  oscillazione **simulata**, non un feed di mercato reale — non esiste
  un'API pubblica gratuita per leggere prezzi immobiliari aggiornati ogni
  giorno, e fare scraping violerebbe i termini di servizio dei portali).
- `worker/` — backend **opzionale** (Cloudflare Worker) che collega il
  Consulente IA a un vero modello Claude, per rispondere a domande libere
  invece delle sole domande pre-impostate. Senza deployarlo il sito
  funziona comunque, con il motore a regole locale. Vedi
  `worker/README.md` per il deploy passo-passo.

## Come vederla

Basta aprire `index.html` in un browser, non serve alcun server o build:

```bash
open index.html
```

## Stato del progetto

Prototipo dimostrativo (MVP visivo/interattivo), pensato per mostrare
l'interfaccia e i flussi principali. Limiti noti, da affrontare prima di un
lancio reale:

- **Nessun backend per l'app principale**: dati e login sono finti, non c'è
  persistenza reale né autenticazione vera (il login accetta qualsiasi
  credenziale). L'unico backend reale del progetto è quello opzionale del
  Consulente IA (`worker/`), e serve solo a proteggere la chiave Anthropic.
- **L'assistente IA è regole/parole-chiave per default**, non un modello
  reale collegato ai dati dell'utente — copre più intenti (simulazione di
  importo su un progetto, classifica delle operazioni per rendimento,
  diversificazione del portafoglio, campagne aperte) ma resta un motore a
  regole. Deployando `worker/` (vedi sopra) le domande libere passano invece
  a un vero modello Claude, con fallback automatico sul motore a regole se
  il backend non è configurato o non risponde.
- **Le "spiegazioni IA" del Backoffice sono un template**, non un LLM: usano
  gli stessi numeri calcolati dal motore quantitativo per generare 2-3 frasi
  leggibili. Pensate per essere sostituite da una vera chiamata a un LLM
  (es. Claude) mantenendo i numeri invariati — vedi i commenti in
  `tools/palermo_zone_scoring.py`.
- **Manca tutta la parte transazionale**: pagamenti, KYC/AML, gestione SPV,
  firma documenti.
- **Aspetti legali/regolamentari**: il crowdfunding immobiliare in Italia è
  un'attività regolamentata da Consob e andrebbe affrontata prima di
  qualsiasi lancio pubblico.

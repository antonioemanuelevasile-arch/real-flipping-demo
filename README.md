# RealFlipping — Investi nel mattone, con metodo

Demo web di una piattaforma di investimento immobiliare che unisce **flipping**
(acquisto e valorizzazione di un intero immobile) e **crowdfunding immobiliare**
(partecipazione per quote a operazioni di ristrutturazione), con dashboard
dedicata per seguire cantiere, numeri e situazione fiscale stimata.

## Contenuto

- `index.html` — applicazione a pagina singola (HTML/CSS/JS, nessuna dipendenza
  esterna): landing page, area di login demo, elenco progetti, dashboard
  investitore e sezione Backoffice interna.
- `tools/palermo_zone_scoring.py` — motore quantitativo (senza LLM) che
  calcola un punteggio di investibilità 0–100 per zona di Palermo, usato
  dalla sezione Backoffice. Vedi i commenti nel file per la metodologia.
- `tools/update_index_scores.py` — rigenera i dati mostrati nel Backoffice
  dentro `index.html` a partire dallo scoring engine.
- `.github/workflows/update-zone-scores.yml` — esegue `update_index_scores.py`
  una volta al giorno e committa i nuovi numeri in automatico (una piccola
  oscillazione **simulata**, non un feed di mercato reale — non esiste
  un'API pubblica gratuita per leggere prezzi immobiliari aggiornati ogni
  giorno, e fare scraping violerebbe i termini di servizio dei portali).

## Come vederla

Basta aprire `index.html` in un browser, non serve alcun server o build:

```bash
open index.html
```

## Stato del progetto

Prototipo dimostrativo (MVP visivo/interattivo), pensato per mostrare
l'interfaccia e i flussi principali. Limiti noti, da affrontare prima di un
lancio reale:

- **Nessun backend**: dati e login sono finti, non c'è persistenza reale né
  autenticazione vera (il login accetta qualsiasi credenziale).
- **L'assistente IA è regole/parole-chiave**, non un modello reale collegato
  ai dati dell'utente.
- **Manca tutta la parte transazionale**: pagamenti, KYC/AML, gestione SPV,
  firma documenti.
- **Aspetti legali/regolamentari**: il crowdfunding immobiliare in Italia è
  un'attività regolamentata da Consob e andrebbe affrontata prima di
  qualsiasi lancio pubblico.

"""
RealFlipping - Motore di scoring zone immobiliari — Milano (v1, provvisorio)
==============================================================================

Seconda città analizzata dal motore di scoring: dimostra che la
metodologia (vedi scoring_engine.py) non è cucita su misura per Palermo,
ma si applica a qualsiasi mercato a partire da prezzo di vendita, prezzo
di affitto e relative variazioni percentuali per zona.

Provenienza dei dati — IMPORTANTE, leggere prima di usarli in un pitch
------------------------------------------------------------------------
- vendita_mq / affitto_mq: livelli REALI, fonte borsinoimmobiliare.it,
  quotazioni Milano 2026 (ricerca web del 2026-09-01).
- var_vendita_pct: NON verificata zona per zona. Stimata a partire dalla
  variazione media annua citta' di Milano (+4,9% vendite, fonte
  borsinoimmobiliare.it) con un'oscillazione deterministica per zona
  (seed = nome zona), per avere valori plausibili e riproducibili in
  attesa di uno storico reale per singola zona.
- var_affitto_pct: verificata con fonte reale solo per due zone
  ("Forlanini, Mecenate, Ortomercato" +3,7% e "Missaglia, Gratosoglio"
  +2,4%, fonte affaritaliani.it su dati Q2 2026); le altre zone usano la
  stessa stima deterministica descritta sopra, centrata sulla variazione
  media citta' (+4,1%, fonte borsinoimmobiliare.it).

In sintesi: i PREZZI sono reali e citabili, i TREND per la maggior parte
delle zone sono un'IPOTESI DI LAVORO plausibile ma non verificata zona per
zona — esattamente il tipo di dato che questo motore è pensato per
sostituire con un fornitore reale (OMI Agenzia delle Entrate, o un
provider con licenza) prima di un lancio pubblico. Non presentare i
numeri di questa città come dato di mercato verificato senza prima
rifare la verifica per singola zona.

Come eseguirlo
---------------
    python3 milano_zone_scoring.py
"""

from __future__ import annotations

from scoring_engine import (
    ZoneScore,
    applica_variazione_giornaliera,
    calcola_punteggi,
    carica_da_csv,
    esporta_json,
    genera_spiegazione,
    stampa_report,
)

# ---------------------------------------------------------------------------
# DATI DI INPUT — Milano
# ---------------------------------------------------------------------------
# vendita_mq / affitto_mq: euro al metro quadro — REALI, fonte
#   borsinoimmobiliare.it, quotazioni Milano 2026.
# var_vendita / var_affitto: variazione % — vedi nota di provenienza sopra:
#   reali solo per le due zone segnalate nel commento a fianco, stimate
#   per le altre.

ZONE_DATA = [
    # nome, vendita_mq, var_vendita, affitto_mq, var_affitto
    ("Centro Storico Duomo, San Babila, Montenapoleone", 7370, 1.6, 24.09, 1.3),
    ("City Life", 7437, 3.5, 27.16, 6.5),
    ("Centro Storico Brera", 6394, 7.0, 18.44, 6.5),
    ("Sant'Ambrogio, Cadorna", 6724, 1.4, 20.39, 7.3),
    ("Università Statale, San Lorenzo", 5788, 6.1, 17.60, 5.7),
    ("Turati, Moscova, Corso Venezia", 5426, 2.5, 17.84, 7.6),
    ("Porta Vittoria, Porta Romana", 5640, 5.7, 17.39, 2.7),
    ("Parco Sempione, Arco della Pace", 4868, 6.6, 15.32, 6.6),
    ("Porta Ticinese, Porta Genova", 4512, 2.0, 13.27, 2.1),
    ("Cenisio, Farini, Sarpi", 2831, 6.5, 8.33, 8.1),
    ("Buenos Aires, Regina Giovanna", 3885, 5.2, 13.15, 2.2),
    ("Sempione, Pagano, Washington", 3376, 8.1, 10.72, 3.1),
    ("Forlanini, Mecenate, Ortomercato", 1895, 5.3, 5.96, 3.7),   # var_affitto reale (affaritaliani.it)
    ("Lambrate, Rubattino, Rombon", 1767, 1.5, 5.36, 4.6),
    ("Bicocca, Sarca", 2230, 8.0, 7.15, 6.6),
    ("Niguarda, Bignami, Parco Nord", 2120, 7.5, 6.93, 1.6),
    ("Missaglia, Gratosoglio", 1530, 5.7, 5.09, 2.4),             # var_affitto reale (affaritaliani.it)
    ("Quarto Oggiaro, Sacco", 1619, 7.4, 5.40, 3.8),
]

CITTA = "Milano"
SEED_PREFIX = "milano"
NOME_FILE_JSON = "milano_zone_scores.json"


def genera(giorno=None) -> list[ZoneScore]:
    """Applica l'oscillazione giornaliera simulata (vedi scoring_engine.py)
    e calcola i punteggi del giorno per Milano. Il seed è diverso da quello
    di Palermo, quindi le due città non oscillano in modo identico."""
    dati_di_oggi = applica_variazione_giornaliera(ZONE_DATA, giorno, seed_prefix=SEED_PREFIX)
    return calcola_punteggi(dati_di_oggi)


if __name__ == "__main__":
    risultati = genera()
    stampa_report(risultati)
    esporta_json(risultati, NOME_FILE_JSON)

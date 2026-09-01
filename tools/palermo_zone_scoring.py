"""
RealFlipping - Motore di scoring zone immobiliari — Palermo (MVP)
====================================================================

Prima città analizzata dal motore quantitativo di RealFlipping: prende
dati di zona (prezzo di vendita, prezzo di affitto, variazioni %) e calcola
un punteggio di investibilità 0-100 per ciascuna zona di Palermo,
classificandola in Investire / Monitorare / Evitare.

Il calcolo vero e proprio (normalizzazione, pesi, penalità di affidabilità,
generazione della spiegazione testuale) vive in scoring_engine.py ed è
condiviso con le altre città — vedi milano_zone_scoring.py per la seconda
città analizzata. Questo file contiene solo i dati di input di Palermo e i
wrapper con il seed di oscillazione giornaliera specifico di questa città.

Fonte dati inserita di default: quotazioni immobiliari.it, Palermo,
luglio 2026 (prezzi di vendita e affitto medi per zona, con relative
variazioni percentuali sul periodo precedente). Sostituisci ZONE_DATA
con un CSV/DB reale (es. estrazione OMI Agenzia delle Entrate) quando
disponibile: scoring_engine.carica_da_csv() è pronta per quello.

Come eseguirlo
---------------
Esegui il file intero da terminale, non incollarne pezzi in una shell
Python interattiva (il REPL base non gestisce bene l'incolla multi-riga
di commenti/blocchi):

    python3 palermo_zone_scoring.py
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
# DATI DI INPUT — Palermo
# ---------------------------------------------------------------------------
# vendita_mq / affitto_mq: euro al metro quadro
# var_vendita / var_affitto: variazione % rispetto al semestre/periodo precedente
# fonte: immobiliare.it, "Quotazioni immobiliari nel comune di Palermo", luglio 2026

ZONE_DATA = [
    # nome, vendita_mq, var_vendita, affitto_mq, var_affitto
    ("Centro Storico", 1911, -1.6, 11.35, 2.3),
    ("Fiera, Montepellegrino", 1661, 8.7, 9.47, 5.0),
    ("Libertà, Villabianca, De Gasperi, Croce Rossa, Sciuti, Politeama", 2322, 2.3, 10.06, 4.1),
    ("Giotto Galilei, Palagonia, Noce, Malaspina", 1509, -0.5, 9.69, 10.7),
    ("Oreto, Perez, Montegrappa, Guadagna", 1204, 4.8, 9.43, 13.8),
    ("Sant'Erasmo, Brancaccio, Sperone, Settecannoli", 1077, 1.4, 6.81, 2.1),
    ("Ciaculli, Belmonte Chiavelli", 900, 2.5, 6.06, 11.4),
    ("Villagrazia, Olio di Lino", 1105, 1.7, 6.29, 0.5),
    ("Calatafimi Alta, Santicelli", 1418, 3.7, 7.98, 17.7),
    ("Altarello, Poggio Ridente, Boccadifalco, Baida", 1095, 3.1, 6.87, 5.4),
    ("Strasburgo, Belgio, San Lorenzo, Resuttana", 1849, 5.8, 8.60, -9.8),
    ("Arenella, Acquasanta, Vergine Maria", 1690, -9.7, 10.79, 11.5),
    ("Lanza di Scalea, Olimpo, Castelforte", 2363, -5.1, 14.97, 66.9),
    ("Mondello, Sferracavallo, Addaura, Tommaso Natale", 2022, 9.7, 10.35, -1.2),
    ("Bonagia, Falsomiele", 1192, 4.6, 5.03, -10.2),
    ("Uditore, Leonardo Da Vinci Alta, Borgo Nuovo", 1383, 4.4, 7.21, -2.3),
    ("Pallavicino, Villaggio Ruffini, Cardillo, Inserra", 1684, -1.9, 8.32, 11.2),
    ("Porto, Borgo Vecchio, Roma, Cavour", 1927, 2.8, 10.97, -3.2),
    ("Calatafimi Bassa, Indipendenza, Zisa, Università", 1357, 6.0, 9.66, 10.9),
    ("Cruillas, CEP, Michelangelo Alta", 1328, 12.7, 6.83, -8.2),
]

CITTA = "Palermo"
SEED_PREFIX = "palermo"
NOME_FILE_JSON = "palermo_zone_scores.json"


def genera(giorno=None) -> list[ZoneScore]:
    """Applica l'oscillazione giornaliera simulata (vedi scoring_engine.py
    per il perché è una simulazione e non un feed di mercato reale) e
    calcola i punteggi del giorno per Palermo."""
    dati_di_oggi = applica_variazione_giornaliera(ZONE_DATA, giorno, seed_prefix=SEED_PREFIX)
    return calcola_punteggi(dati_di_oggi)


if __name__ == "__main__":
    risultati = genera()
    stampa_report(risultati)
    esporta_json(risultati, NOME_FILE_JSON)

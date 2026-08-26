"""
RealFlipping - Motore di scoring zone immobiliari (MVP)
========================================================

Primo prototipo del livello "quantitativo" della dashboard IA di analisi
di mercato descritta nel progetto RealFlipping: prende dati di zona
(prezzo di vendita, prezzo di affitto, variazioni %) e calcola un
punteggio di investibilità 0-100 per ciascuna zona, classificandola in
Investire / Monitorare / Evitare.

Questo script NON usa un LLM: produce i numeri verificabili su cui,
in una versione successiva, un layer con Claude (o altro LLM) potrà
costruire la spiegazione testuale per l'investitore.

Aggiornamento giornaliero (simulato)
-------------------------------------
Non esiste un'API pubblica gratuita di immobiliare.it (o simili) per
leggere prezzi aggiornati ogni giorno, e fare scraping violerebbe i loro
termini di servizio. Per far vedere nel prototipo un backoffice che "si
muove" nel tempo, applica_variazione_giornaliera() genera una piccola
oscillazione casuale ma riproducibile (seed = data del giorno) sopra
ZONE_DATA. E' chiaramente rumore di simulazione, non un dato di mercato
reale — sostituire con un fornitore con licenza (es. OMI Agenzia delle
Entrate) quando disponibile.

Fonte dati inserita di default: quotazioni immobiliari.it, Palermo,
luglio 2026 (prezzi di vendita e affitto medi per zona, con relative
variazioni percentuali sul periodo precedente). Sostituisci ZONE_DATA
con un CSV/DB reale (es. estrazione OMI Agenzia delle Entrate) quando
disponibile: la funzione carica_da_csv() è pronta per quello.

Come eseguirlo
---------------
Esegui il file intero da terminale, non incollarne pezzi in una shell
Python interattiva (il REPL base non gestisce bene l'incolla multi-riga
di commenti/blocchi):

    python3 palermo_zone_scoring.py

Come collegare il layer LLM (v2)
---------------------------------
Per ogni ZoneScore, passare i campi a Claude con un prompt tipo:
"Spiega in 2-3 frasi perche' la zona {zona} ha punteggio {punteggio}
e fascia {fascia}, dati: rendimento lordo {rendimento_lordo_pct}%,
trend prezzi {var_vendita_pct}%, trend affitti {var_affitto_pct}%."
L'LLM NON deve modificare i numeri, solo raccontarli: i numeri restano
sempre calcolati da questo motore quantitativo.
"""

from __future__ import annotations
import csv
import hashlib
import io
import random
from dataclasses import dataclass, asdict
from datetime import date
from typing import Literal

# ---------------------------------------------------------------------------
# 1. DATI DI INPUT
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

def applica_variazione_giornaliera(
    dati: list[tuple],
    giorno: date | None = None,
    ampiezza_prezzo_pct: float = 0.4,
    ampiezza_var_punti: float = 0.3,
) -> list[tuple]:
    """Simula un aggiornamento giornaliero applicando una piccola oscillazione
    casuale, ma riproducibile (seed = data del giorno), sopra ZONE_DATA.

    Non e' un collegamento a un feed di mercato reale: non esiste un'API
    pubblica gratuita di immobiliare.it o simili per leggere prezzi
    aggiornati ogni giorno, e fare scraping violerebbe i loro termini di
    servizio. Questo e' un rumore realistico intorno alla fonte statica di
    luglio 2026, pensato per far vedere nel prototipo un backoffice che
    "si muove" giorno per giorno. Sostituire con un fornitore dati reale
    (es. OMI Agenzia delle Entrate, o un provider con licenza) quando
    disponibile: da quel momento questa funzione non serve più.

    Il seed e' derivato dalla data (non dall'ora), quindi più esecuzioni
    nello stesso giorno danno lo stesso risultato: l'automazione giornaliera
    (vedi .github/workflows/update-zone-scores.yml) produce un solo
    aggiornamento reale al giorno, non un numero diverso a ogni run.
    """
    giorno = giorno or date.today()
    seed = int(hashlib.sha256(giorno.isoformat().encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)

    risultato = []
    for zona, vendita, var_v, affitto, var_a in dati:
        vendita_g = round(vendita * (1 + rng.uniform(-ampiezza_prezzo_pct, ampiezza_prezzo_pct) / 100), 2)
        affitto_g = round(affitto * (1 + rng.uniform(-ampiezza_prezzo_pct, ampiezza_prezzo_pct) / 100), 2)
        var_v_g = round(var_v + rng.uniform(-ampiezza_var_punti, ampiezza_var_punti), 1)
        var_a_g = round(var_a + rng.uniform(-ampiezza_var_punti, ampiezza_var_punti), 1)
        risultato.append((zona, vendita_g, var_v_g, affitto_g, var_a_g))
    return risultato


# Variazioni % di affitto sopra questa soglia (assoluta) vengono considerate
# statisticamente poco affidabili (zone a basso volume di transazioni dove
# un singolo contratto sposta la media) e vengono "clippate" solo ai fini
# del punteggio, ma segnalate come dato da verificare.
SOGLIA_AFFIDABILITA_VAR = 15.0


@dataclass
class ZoneScore:
    zona: str
    vendita_mq: float
    affitto_mq: float
    rendimento_lordo_pct: float
    var_vendita_pct: float
    var_affitto_pct: float
    punteggio: float
    fascia: Literal["Investire", "Monitorare", "Evitare"]
    dato_da_verificare: bool


def carica_da_csv(path: str) -> list[tuple]:
    """Carica ZONE_DATA da un CSV con colonne:
    zona,vendita_mq,var_vendita,affitto_mq,var_affitto
    Utile per collegare in futuro un export OMI o uno scraping periodico
    al posto dei dati statici qui sopra.
    """
    righe = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            righe.append((
                r["zona"],
                float(r["vendita_mq"]),
                float(r["var_vendita"]),
                float(r["affitto_mq"]),
                float(r["var_affitto"]),
            ))
    return righe


def _normalizza(valori: list[float]) -> list[float]:
    """Min-max scaling a 0-100."""
    lo, hi = min(valori), max(valori)
    if hi == lo:
        return [50.0 for _ in valori]
    return [(v - lo) / (hi - lo) * 100 for v in valori]


def calcola_punteggi(
    dati: list[tuple],
    peso_rendimento: float = 0.45,
    peso_trend_vendita: float = 0.30,
    peso_trend_affitto: float = 0.25,
) -> list[ZoneScore]:
    """Calcola il punteggio composito di investibilità per ogni zona.

    Metodologia (v1 - da raffinare con più storico quando disponibile):
      - rendimento_lordo = affitto_mq * 12 / vendita_mq * 100
        (rendimento locativo lordo annuo stimato)
      - trend_vendita = variazione % prezzo di vendita
        (momentum di rivalutazione, utile soprattutto per il flipping)
      - trend_affitto = variazione % canone di affitto, con clipping a
        +/- 15% per limitare il peso di outlier da bassa liquidità
      - ogni componente è normalizzata 0-100 tra le zone analizzate,
        poi combinata con i pesi indicati (di default: rendimento conta
        di più, poi rivalutazione, poi domanda locativa)

    Nota: il clipping serve SOLO al calcolo del punteggio; il valore
    originale non clippato resta in var_affitto_pct per trasparenza.
    """
    rendimenti = [(a * 12 / v) * 100 for (_, v, _, a, _) in dati]
    trend_vendita = [vv for (_, _, vv, _, _) in dati]
    trend_affitto_clip = [
        max(-SOGLIA_AFFIDABILITA_VAR, min(SOGLIA_AFFIDABILITA_VAR, va))
        for (_, _, _, _, va) in dati
    ]

    rendimenti_norm = _normalizza(rendimenti)
    trend_vendita_norm = _normalizza(trend_vendita)
    trend_affitto_norm = _normalizza(trend_affitto_clip)

    risultati = []
    for i, (zona, vendita, var_v, affitto, var_a) in enumerate(dati):
        punteggio = (
            peso_rendimento * rendimenti_norm[i]
            + peso_trend_vendita * trend_vendita_norm[i]
            + peso_trend_affitto * trend_affitto_norm[i]
        )
        fascia: Literal["Investire", "Monitorare", "Evitare"]
        if punteggio >= 65:
            fascia = "Investire"
        elif punteggio >= 40:
            fascia = "Monitorare"
        else:
            fascia = "Evitare"

        risultati.append(ZoneScore(
            zona=zona,
            vendita_mq=vendita,
            affitto_mq=affitto,
            rendimento_lordo_pct=round(rendimenti[i], 2),
            var_vendita_pct=var_v,
            var_affitto_pct=var_a,
            punteggio=round(punteggio, 1),
            fascia=fascia,
            dato_da_verificare=abs(var_a) > SOGLIA_AFFIDABILITA_VAR,
        ))

    risultati.sort(key=lambda r: r.punteggio, reverse=True)
    return risultati


def stampa_report(risultati: list[ZoneScore]) -> None:
    print(f"{'Zona':<65}{'Punt.':>7}{'Fascia':>13}{'Rend.%':>9}{'VarV%':>8}{'VarA%':>8}")
    print("-" * 115)
    for r in risultati:
        flag = " *" if r.dato_da_verificare else ""
        print(
            f"{r.zona:<65}{r.punteggio:>7.1f}{r.fascia:>13}"
            f"{r.rendimento_lordo_pct:>9.2f}{r.var_vendita_pct:>8.1f}{r.var_affitto_pct:>7.1f}{flag}"
        )
    print("\n* = variazione affitto anomala (oltre soglia affidabilità), dato da verificare con più storico")


def esporta_json(risultati: list[ZoneScore], nome_file: str = "palermo_zone_scores.json") -> None:
    """Esporta i risultati in JSON, comodo per alimentare una dashboard o un
    layer LLM che genera la spiegazione testuale per l'investitore.

    Prova prima a scrivere nella cartella corrente; se non e' scrivibile
    (es. Errno 30 "Read-only file system", capita quando lo script gira
    da una posizione protetta) ripiega sulla cartella Home dell'utente
    invece di interrompersi con un errore.
    """
    import json
    from pathlib import Path

    dati = [asdict(r) for r in risultati]
    percorsi_da_provare = [Path.cwd() / nome_file, Path.home() / nome_file]

    for percorso in percorsi_da_provare:
        try:
            with open(percorso, "w", encoding="utf-8") as f:
                json.dump(dati, f, ensure_ascii=False, indent=2)
            print(f"\nEsportato: {percorso}")
            return
        except OSError as e:
            print(f"Impossibile scrivere in {percorso} ({e}), provo un'altra posizione...")

    print("\nNon sono riuscito a salvare il JSON in nessuna posizione scrivibile.")


if __name__ == "__main__":
    dati_di_oggi = applica_variazione_giornaliera(ZONE_DATA)
    risultati = calcola_punteggi(dati_di_oggi)
    stampa_report(risultati)
    esporta_json(risultati)

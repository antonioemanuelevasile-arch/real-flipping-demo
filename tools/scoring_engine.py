"""
RealFlipping - Motore di scoring zone immobiliari (condiviso multi-città)
==========================================================================

Logica di scoring estratta da palermo_zone_scoring.py e resa riutilizzabile
per più città (vedi milano_zone_scoring.py) — stessa metodologia, dati di
input diversi per ogni mercato. Un file città (es. palermo_zone_scoring.py)
definisce solo ZONE_DATA e i metadati di fonte; questo modulo fa il calcolo.

Questo script NON usa un LLM: produce i numeri verificabili su cui un
layer con Claude (o altro LLM) può costruire la spiegazione testuale per
l'investitore — vedi genera_spiegazione(), che oggi è un template
deterministico pensato per essere sostituito 1:1 da una vera chiamata LLM.

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
import random
from dataclasses import dataclass, asdict
from datetime import date
from typing import Literal

# Variazioni % di affitto sopra questa soglia (assoluta) vengono considerate
# statisticamente poco affidabili (zone a basso volume di transazioni dove
# un singolo contratto sposta la media) e vengono "clippate" solo ai fini
# del punteggio, ma segnalate come dato da verificare.
SOGLIA_AFFIDABILITA_VAR = 15.0

# Quota stimata di costi ricorrenti (IMU su seconda casa, spese condominiali
# non ribaltabili, manutenzione ordinaria, gestione/vacancy) sottratta dal
# rendimento lordo per stimare un rendimento netto di massima. E' un'ipotesi
# forfettaria uguale per tutte le zone e le città (v1): un raffinamento
# futuro la calcolerebbe per singolo immobile/comune.
QUOTA_COSTI_RICORRENTI = 0.28

# Ogni punto di variazione affitto oltre la soglia di affidabilità toglie
# questi punti di punteggio (fino a un massimo), per riflettere che un dato
# fuori soglia e' meno fidato — non solo "clippato" ma penalizzato.
PENALITA_PER_PUNTO_INAFFIDABILE = 0.6
PENALITA_MASSIMA = 12.0


@dataclass
class ZoneScore:
    zona: str
    vendita_mq: float
    affitto_mq: float
    rendimento_lordo_pct: float
    rendimento_netto_pct: float
    var_vendita_pct: float
    var_affitto_pct: float
    punteggio: float
    fascia: Literal["Investire", "Monitorare", "Evitare"]
    indice_affidabilita_pct: float
    dato_da_verificare: bool
    spiegazione: str


def applica_variazione_giornaliera(
    dati: list[tuple],
    giorno: date | None = None,
    seed_prefix: str = "",
    ampiezza_prezzo_pct: float = 0.4,
    ampiezza_var_punti: float = 0.3,
) -> list[tuple]:
    """Simula un aggiornamento giornaliero applicando una piccola oscillazione
    casuale, ma riproducibile (seed = data del giorno + prefisso città), sopra
    ZONE_DATA.

    Non e' un collegamento a un feed di mercato reale: non esiste un'API
    pubblica gratuita di immobiliare.it o simili per leggere prezzi
    aggiornati ogni giorno, e fare scraping violerebbe i loro termini di
    servizio. Questo e' un rumore realistico intorno alla fonte statica,
    pensato per far vedere nel prototipo un backoffice che "si muove" giorno
    per giorno. Sostituire con un fornitore dati reale (es. OMI Agenzia
    delle Entrate, o un provider con licenza) quando disponibile.

    seed_prefix distingue le città (senza, Milano e Palermo oscillerebbero
    in modo identico nello stesso giorno, perché deriverebbero dallo stesso
    seed numerico).
    """
    giorno = giorno or date.today()
    seed = int(hashlib.sha256(f"{seed_prefix}::{giorno.isoformat()}".encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)

    risultato = []
    for zona, vendita, var_v, affitto, var_a in dati:
        vendita_g = round(vendita * (1 + rng.uniform(-ampiezza_prezzo_pct, ampiezza_prezzo_pct) / 100), 2)
        affitto_g = round(affitto * (1 + rng.uniform(-ampiezza_prezzo_pct, ampiezza_prezzo_pct) / 100), 2)
        var_v_g = round(var_v + rng.uniform(-ampiezza_var_punti, ampiezza_var_punti), 1)
        var_a_g = round(var_a + rng.uniform(-ampiezza_var_punti, ampiezza_var_punti), 1)
        risultato.append((zona, vendita_g, var_v_g, affitto_g, var_a_g))
    return risultato


def carica_da_csv(path: str) -> list[tuple]:
    """Carica ZONE_DATA da un CSV con colonne:
    zona,vendita_mq,var_vendita,affitto_mq,var_affitto
    Utile per collegare in futuro un export OMI o uno scraping periodico
    al posto dei dati statici in ogni file città.
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

    Metodologia (v1.5 — clipping + penalità di affidabilità):
      - rendimento_lordo = affitto_mq * 12 / vendita_mq * 100
        (rendimento locativo lordo annuo stimato)
      - rendimento_netto = rendimento_lordo * (1 - QUOTA_COSTI_RICORRENTI),
        stima di massima al netto di IMU/condominio/manutenzione/gestione
        (ipotesi forfettaria uguale per tutte le zone, v1)
      - trend_vendita = variazione % prezzo di vendita
        (momentum di rivalutazione, utile soprattutto per il flipping)
      - trend_affitto = variazione % canone di affitto, con clipping a
        +/- 15% per limitare il peso di outlier da bassa liquidità
      - ogni componente è normalizzata 0-100 TRA LE ZONE DELLA STESSA CITTÀ
        (i punteggi non sono comparabili 1:1 tra città diverse: sono un
        ranking relativo al mercato locale analizzato, non un punteggio
        assoluto universale), poi combinata con i pesi indicati
      - indice_affidabilita: 100 se la variazione affitto è entro soglia,
        altrimenti scende in proporzione a quanto la supera
      - penalità di affidabilità: il punteggio finale viene ridotto (fino a
        un tetto) in base a quanto il dato è fuori soglia

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
        punteggio_grezzo = (
            peso_rendimento * rendimenti_norm[i]
            + peso_trend_vendita * trend_vendita_norm[i]
            + peso_trend_affitto * trend_affitto_norm[i]
        )

        eccesso = max(0.0, abs(var_a) - SOGLIA_AFFIDABILITA_VAR)
        penalita = min(PENALITA_MASSIMA, eccesso * PENALITA_PER_PUNTO_INAFFIDABILE)
        indice_affidabilita = round(max(0.0, 100.0 - (eccesso * 4.0)), 1)
        punteggio = max(0.0, punteggio_grezzo - penalita)

        fascia: Literal["Investire", "Monitorare", "Evitare"]
        if punteggio >= 65:
            fascia = "Investire"
        elif punteggio >= 40:
            fascia = "Monitorare"
        else:
            fascia = "Evitare"

        rendimento_lordo = round(rendimenti[i], 2)
        rendimento_netto = round(rendimento_lordo * (1 - QUOTA_COSTI_RICORRENTI), 2)

        risultati.append(ZoneScore(
            zona=zona,
            vendita_mq=vendita,
            affitto_mq=affitto,
            rendimento_lordo_pct=rendimento_lordo,
            rendimento_netto_pct=rendimento_netto,
            var_vendita_pct=var_v,
            var_affitto_pct=var_a,
            punteggio=round(punteggio, 1),
            fascia=fascia,
            indice_affidabilita_pct=indice_affidabilita,
            dato_da_verificare=abs(var_a) > SOGLIA_AFFIDABILITA_VAR,
            spiegazione="",
        ))

    risultati.sort(key=lambda r: r.punteggio, reverse=True)

    for r in risultati:
        r.spiegazione = genera_spiegazione(r, rendimenti, trend_vendita)

    return risultati


def genera_spiegazione(
    r: ZoneScore, rendimenti: list[float], trend_vendita: list[float]
) -> str:
    """Genera 2-3 frasi che spiegano il punteggio, a partire dai numeri già
    calcolati — non da un LLM (v1.5, motore quantitativo "racconta se
    stesso" con un template).

    Questa funzione può essere sostituita 1:1 da una chiamata a un LLM
    reale (es. Claude) che riceva gli stessi campi e produca un testo più
    naturale — i numeri restano sempre calcolati dal motore quantitativo
    qui sopra, mai dal layer di spiegazione.
    """
    rend_medio = sum(rendimenti) / len(rendimenti)
    vendita_media = sum(trend_vendita) / len(trend_vendita)

    if r.fascia == "Investire":
        apertura = f"{r.zona} è in fascia Investire con punteggio {r.punteggio}/100"
    elif r.fascia == "Monitorare":
        apertura = f"{r.zona} è in fascia Monitorare con punteggio {r.punteggio}/100"
    else:
        apertura = f"{r.zona} è in fascia Evitare con punteggio {r.punteggio}/100"

    if r.rendimento_lordo_pct >= rend_medio:
        frase_rendimento = (
            f"il rendimento locativo lordo stimato ({r.rendimento_lordo_pct}%, "
            f"circa {r.rendimento_netto_pct}% al netto di costi ricorrenti stimati) "
            f"è sopra la media delle zone analizzate"
        )
    else:
        frase_rendimento = (
            f"il rendimento locativo lordo stimato ({r.rendimento_lordo_pct}%, "
            f"circa {r.rendimento_netto_pct}% al netto di costi ricorrenti stimati) "
            f"è sotto la media delle zone analizzate"
        )

    if r.var_vendita_pct >= vendita_media:
        frase_trend = f"i prezzi di vendita mostrano un trend di {r.var_vendita_pct:+.1f}%, sopra la media"
    else:
        frase_trend = f"i prezzi di vendita mostrano un trend di {r.var_vendita_pct:+.1f}%, sotto la media"

    frase_affidabilita = ""
    if r.dato_da_verificare:
        frase_affidabilita = (
            f" Attenzione: la variazione dei canoni d'affitto rilevata ({r.var_affitto_pct:+.1f}%) "
            f"supera la soglia di affidabilità statistica (indice di affidabilità stimato "
            f"{r.indice_affidabilita_pct}/100) — probabile bassa liquidità del mercato degli "
            f"affitti in questa zona: verificare con più storico prima di darle peso."
        )

    return f"{apertura}: {frase_rendimento} e {frase_trend}.{frase_affidabilita}"


def stampa_report(risultati: list[ZoneScore]) -> None:
    print(f"{'Zona':<65}{'Punt.':>7}{'Fascia':>13}{'Rend.lordo%':>12}{'Rend.netto%':>13}{'Affid.':>8}{'VarV%':>8}{'VarA%':>8}")
    print("-" * 145)
    for r in risultati:
        flag = " *" if r.dato_da_verificare else ""
        print(
            f"{r.zona:<65}{r.punteggio:>7.1f}{r.fascia:>13}"
            f"{r.rendimento_lordo_pct:>12.2f}{r.rendimento_netto_pct:>13.2f}"
            f"{r.indice_affidabilita_pct:>8.1f}{r.var_vendita_pct:>8.1f}{r.var_affitto_pct:>7.1f}{flag}"
        )
    print("\n* = variazione affitto anomala (oltre soglia affidabilità), dato da verificare con più storico")
    if risultati:
        print("\nEsempio di spiegazione generata per la prima zona:\n" + risultati[0].spiegazione)


def esporta_json(risultati: list[ZoneScore], nome_file: str) -> None:
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

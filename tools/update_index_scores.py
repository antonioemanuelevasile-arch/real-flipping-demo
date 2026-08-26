"""
Aggiorna automaticamente i punteggi zona dentro index.html
============================================================

Eseguito ogni giorno da .github/workflows/update-zone-scores.yml:

  1. Applica l'oscillazione giornaliera simulata a ZONE_DATA
     (palermo_zone_scoring.applica_variazione_giornaliera).
  2. Ricalcola i punteggi (palermo_zone_scoring.calcola_punteggi).
  3. Sostituisce il blocco ZONE_SCORES_UPDATED / ZONE_SCORES dentro
     index.html con i nuovi valori.
  4. Riscrive anche tools/palermo_zone_scores.json, per ispezione/debug.

index.html resta la fonte che il sito legge davvero (è un file statico
senza backend): questo script tiene sincronizzati script Python e sito
senza bisogno di copiare/incollare a mano ogni giorno.

Uso manuale:
    python3 tools/update_index_scores.py
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import date
from pathlib import Path

from palermo_zone_scoring import (
    ZONE_DATA,
    ZoneScore,
    applica_variazione_giornaliera,
    calcola_punteggi,
)

QUI = Path(__file__).parent
INDEX_HTML = QUI.parent / "index.html"
JSON_OUT = QUI / "palermo_zone_scores.json"

BLOCCO_RE = re.compile(
    r'const ZONE_SCORES_UPDATED = ".*?";\nconst ZONE_SCORES = \[.*?\];',
    re.DOTALL,
)


def _js_stringa(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def _js_bool(b: bool) -> str:
    return "true" if b else "false"


def costruisci_blocco_js(oggi: date, risultati: list[ZoneScore]) -> str:
    righe = "\n".join(
        "  {zona:%s, vendita_mq:%s, affitto_mq:%s, rendimento_lordo_pct:%s, "
        "var_vendita_pct:%s, var_affitto_pct:%s, punteggio:%s, fascia:%s, "
        "dato_da_verificare:%s}," % (
            _js_stringa(r.zona), r.vendita_mq, r.affitto_mq, r.rendimento_lordo_pct,
            r.var_vendita_pct, r.var_affitto_pct, r.punteggio, _js_stringa(r.fascia),
            _js_bool(r.dato_da_verificare),
        )
        for r in risultati
    )
    return (
        f'const ZONE_SCORES_UPDATED = {_js_stringa(oggi.isoformat())};\n'
        f"const ZONE_SCORES = [\n{righe}\n];"
    )


def main() -> None:
    oggi = date.today()
    dati_di_oggi = applica_variazione_giornaliera(ZONE_DATA, oggi)
    risultati = calcola_punteggi(dati_di_oggi)

    html = INDEX_HTML.read_text(encoding="utf-8")
    if not BLOCCO_RE.search(html):
        raise SystemExit(
            "Non ho trovato il blocco ZONE_SCORES_UPDATED/ZONE_SCORES in index.html "
            "— è stato rinominato o spostato? Aggiorna BLOCCO_RE di conseguenza."
        )
    html_nuovo = BLOCCO_RE.sub(costruisci_blocco_js(oggi, risultati), html, count=1)

    if html_nuovo != html:
        INDEX_HTML.write_text(html_nuovo, encoding="utf-8")
        print(f"index.html aggiornato al {oggi.isoformat()}.")
    else:
        print("Nessuna modifica: i dati di oggi coincidono con quelli già presenti.")

    JSON_OUT.write_text(
        json.dumps(
            {"generato_il": oggi.isoformat(), "zone": [asdict(r) for r in risultati]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

"""
Aggiorna automaticamente i punteggi zona dentro index.html (multi-città)
============================================================================

Eseguito ogni giorno da .github/workflows/update-zone-scores.yml:

  1. Per ogni città registrata in CITTA_MODULI, applica l'oscillazione
     giornaliera simulata e ricalcola i punteggi (vedi scoring_engine.py).
  2. Sostituisce il blocco ZONE_SCORES_UPDATED / ZONE_SCORES_BY_CITY dentro
     index.html con i nuovi valori, per tutte le città insieme.
  3. Riscrive anche tools/<citta>_zone_scores.json per ogni città, per
     ispezione/debug.

index.html resta la fonte che il sito legge davvero (è un file statico
senza backend): questo script tiene sincronizzati gli script Python e il
sito senza bisogno di copiare/incollare a mano ogni giorno.

Uso manuale:
    python3 tools/update_index_scores.py
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import date
from pathlib import Path

import milano_zone_scoring
import palermo_zone_scoring
from scoring_engine import ZoneScore

QUI = Path(__file__).parent
INDEX_HTML = QUI.parent / "index.html"

# Ogni voce: (nome città come appare nel sito, modulo con .genera()/.NOME_FILE_JSON)
CITTA_MODULI = [
    ("Palermo", palermo_zone_scoring),
    ("Milano", milano_zone_scoring),
]

BLOCCO_RE = re.compile(
    r'const ZONE_SCORES_UPDATED = ".*?";\nconst ZONE_SCORES_BY_CITY = \{.*?\n\};',
    re.DOTALL,
)


def _js_stringa(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def _js_bool(b: bool) -> str:
    return "true" if b else "false"


def _js_righe(risultati: list[ZoneScore]) -> str:
    return "\n".join(
        "    {zona:%s, vendita_mq:%s, affitto_mq:%s, rendimento_lordo_pct:%s, "
        "rendimento_netto_pct:%s, var_vendita_pct:%s, var_affitto_pct:%s, punteggio:%s, "
        "fascia:%s, indice_affidabilita_pct:%s, dato_da_verificare:%s, spiegazione:%s}," % (
            _js_stringa(r.zona), r.vendita_mq, r.affitto_mq, r.rendimento_lordo_pct,
            r.rendimento_netto_pct, r.var_vendita_pct, r.var_affitto_pct, r.punteggio,
            _js_stringa(r.fascia), r.indice_affidabilita_pct, _js_bool(r.dato_da_verificare),
            _js_stringa(r.spiegazione),
        )
        for r in risultati
    )


def costruisci_blocco_js(oggi: date, risultati_per_citta: dict[str, list[ZoneScore]]) -> str:
    blocchi_citta = ",\n".join(
        f"  {_js_stringa(citta)}: [\n{_js_righe(risultati)}\n  ]"
        for citta, risultati in risultati_per_citta.items()
    )
    return (
        f'const ZONE_SCORES_UPDATED = {_js_stringa(oggi.isoformat())};\n'
        f"const ZONE_SCORES_BY_CITY = {{\n{blocchi_citta}\n}};"
    )


def main() -> None:
    oggi = date.today()

    risultati_per_citta: dict[str, list[ZoneScore]] = {}
    for nome_citta, modulo in CITTA_MODULI:
        risultati = modulo.genera(oggi)
        risultati_per_citta[nome_citta] = risultati
        json_path = QUI / modulo.NOME_FILE_JSON
        json_path.write_text(
            json.dumps(
                {"citta": nome_citta, "generato_il": oggi.isoformat(), "zone": [asdict(r) for r in risultati]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    html = INDEX_HTML.read_text(encoding="utf-8")
    if not BLOCCO_RE.search(html):
        raise SystemExit(
            "Non ho trovato il blocco ZONE_SCORES_UPDATED/ZONE_SCORES_BY_CITY in index.html "
            "— è stato rinominato o spostato? Aggiorna BLOCCO_RE di conseguenza."
        )
    html_nuovo = BLOCCO_RE.sub(costruisci_blocco_js(oggi, risultati_per_citta), html, count=1)

    if html_nuovo != html:
        INDEX_HTML.write_text(html_nuovo, encoding="utf-8")
        print(f"index.html aggiornato al {oggi.isoformat()} per: {', '.join(risultati_per_citta)}.")
    else:
        print("Nessuna modifica: i dati di oggi coincidono con quelli già presenti.")


if __name__ == "__main__":
    main()

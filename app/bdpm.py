"""
Module de recherche de medicaments.
Utilise Claude AI pour retourner des donnees BDPM fiables,
avec tentative sur l'API officielle en premier.
"""
import requests
import json
import os
import logging

logger = logging.getLogger(__name__)

# URLs BDPM officielles a essayer
BDPM_URLS = [
    "https://base-donnees-publique.medicaments.gouv.fr/api/v1/medicament",
    "https://api.le-dictionnaire-vidal.fr/medicaments",
]


def search_medicaments(query: str, limit: int = 5) -> list[dict]:
    """
    Recherche un medicament.
    1. Tente l'API BDPM officielle
    2. Fallback sur Claude AI (connaissance BDPM integree)
    """
    # Tentative API BDPM officielle
    result = _try_bdpm_api(query, limit)
    if result:
        return result

    # Fallback Claude AI
    return _search_via_claude(query, limit)


def _try_bdpm_api(query: str, limit: int) -> list[dict]:
    """Tente la recherche sur l'API BDPM officielle."""
    endpoints = [
        ("https://base-donnees-publique.medicaments.gouv.fr/api/v1/medicament",
         {"denomination": query.upper(), "limit": limit}),
        ("https://base-donnees-publique.medicaments.gouv.fr/api/v1/medicament",
         {"query": query, "limit": limit}),
    ]
    for url, params in endpoints:
        try:
            r = requests.get(url, params=params, timeout=5)
            if r.status_code == 200:
                data = r.json()
                results = data if isinstance(data, list) else data.get("results", [])
                if results:
                    return _normalize(results)
        except Exception as e:
            logger.debug(f"BDPM API echec ({url}): {e}")
    return []


def _search_via_claude(query: str, limit: int) -> list[dict]:
    """
    Recherche via Claude API — retourne des medicaments BDPM reels.
    """
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY manquante pour la recherche medicament")
        return []

    client = anthropic.Anthropic(api_key=api_key)

    system = """Tu es une base de donnees pharmaceutique française experte.
Tu connais parfaitement la Base de Donnees Publique des Medicaments (BDPM).
Reponds UNIQUEMENT avec un JSON array valide, sans texte avant ou apres, sans backticks.
Ne mets aucun commentaire. Juste le JSON pur."""

    prompt = f"""Donne-moi {limit} medicaments reels de la BDPM française correspondant a : "{query}"

Format JSON strict (tableau de {limit} objets) :
[
  {{
    "code_cis": "60001393",
    "denomination": "DOLIPRANE 1000 mg, comprime",
    "forme_pharma": "comprime",
    "voies_admin": "orale",
    "statut_amm": "Autorisation active",
    "etat_commercialisation": "Commercialise",
    "substance_active": "Paracetamol"
  }}
]

Retourne uniquement des medicaments qui existent vraiment dans la BDPM française."""

    try:
        msg = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        # Nettoyer au cas ou
        text = text.replace("```json", "").replace("```", "").strip()
        results = json.loads(text)
        if isinstance(results, list):
            return results[:limit]
    except json.JSONDecodeError as e:
        logger.error(f"JSON invalide depuis Claude: {e}")
    except Exception as e:
        logger.error(f"Erreur Claude search: {e}")

    return []


def get_medicament_detail(code_cis: str) -> dict | None:
    """Recupere le detail d'un medicament par code CIS."""
    try:
        url = f"https://base-donnees-publique.medicaments.gouv.fr/api/v1/medicament/{code_cis}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.debug(f"Detail BDPM echec: {e}")
    return None


def _normalize(items: list) -> list[dict]:
    """Normalise les resultats BDPM vers un format standard."""
    out = []
    for item in items:
        out.append({
            "code_cis": item.get("codeCIS") or item.get("code_cis", ""),
            "denomination": item.get("denomination", ""),
            "forme_pharma": item.get("formePharmaceutique") or item.get("forme_pharma", ""),
            "voies_admin": item.get("voiesAdministration") or item.get("voies_admin", ""),
            "statut_amm": item.get("statutAMM") or item.get("statut_amm", ""),
            "etat_commercialisation": (
                item.get("etatCommercialisation") or
                item.get("etat_commercialisation", "")
            ),
        })
    return out

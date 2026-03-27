"""
Recherche de medicaments via Claude AI (connaissance BDPM française).
"""
import json
import os
import logging
import re

logger = logging.getLogger(__name__)


def search_medicaments(query: str, limit: int = 5) -> list[dict]:
    """
    Recherche un medicament via Claude AI.
    Retourne une liste de medicaments BDPM reels.
    """
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY manquante")
        return []

    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = (
        "Tu es un expert de la pharmacopee française. "
        "Tu reponds TOUJOURS avec un JSON array valide uniquement. "
        "Aucun texte avant ou apres le JSON. Jamais de backticks."
    )

    user_prompt = (
        f'Medicament recherche: "{query}"\n\n'
        f"Retourne exactement {limit} medicaments commercialises en France.\n"
        "Format JSON STRICT :\n"
        '[{"denomination":"NOM COMPLET","forme_pharma":"forme","voies_admin":"voie",'
        '"substance_active":"DCI","statut_amm":"Autorisation active",'
        '"etat_commercialisation":"Commercialise","code_cis":"XXXXXXXX"}]'
    )

    try:
        logger.info(f"Recherche BDPM via Claude pour: {query}")

        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = msg.content[0].text.strip()
        logger.info(f"Reponse Claude brute: {raw[:200]}")

        # Extraction robuste du JSON
        parsed = _extract_json(raw)
        if parsed and len(parsed) > 0:
            logger.info(f"Resultats trouves: {len(parsed)}")
            return parsed[:limit]
        else:
            logger.warning(f"Aucun resultat JSON parse depuis: {raw[:200]}")
            return []

    except Exception as e:
        logger.error(f"Erreur Claude search: {type(e).__name__}: {e}")
        return []


def _extract_json(text: str) -> list:
    """Extrait le JSON array meme si du texte parasite est present."""
    # Nettoyer les backticks
    text = text.replace("```json", "").replace("```", "").strip()

    # Trouver le tableau JSON
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        candidate = text[start:end + 1]
        try:
            result = json.loads(candidate)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e} — texte: {candidate[:100]}")

    # Essai direct
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except Exception:
        pass

    return []


def get_medicament_detail(code_cis: str):
    return None

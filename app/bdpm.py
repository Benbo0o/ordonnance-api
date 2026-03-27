"""
Recherche de medicaments via Claude AI.
"""
import json
import os
import logging

logger = logging.getLogger(__name__)


def search_medicaments(query: str, limit: int = 5) -> list[dict]:
    """Recherche via Claude AI - retourne medicaments BDPM."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY manquante")
        return []

    client = anthropic.Anthropic(api_key=api_key)

    user_prompt = (
        f'Donne-moi {limit} medicaments commercialises en France pour "{query}". '
        'Reponds UNIQUEMENT avec ce JSON, rien d\'autre, pas de texte ni backticks:\n'
        '[{"denomination":"DOLIPRANE 1000 mg comprime","forme_pharma":"comprime",'
        '"voies_admin":"orale","substance_active":"Paracetamol",'
        '"statut_amm":"Autorisation active","etat_commercialisation":"Commercialise",'
        '"code_cis":"60001393"}]'
    )

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = msg.content[0].text.strip()
        logger.info(f"Claude raw response for '{query}': {raw[:300]}")

        # Nettoyage
        raw = raw.replace("```json", "").replace("```", "").strip()

        # Extraire le JSON array
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            parsed = json.loads(raw[start:end])
            if isinstance(parsed, list) and len(parsed) > 0:
                return parsed[:limit]

        logger.warning(f"Aucun JSON array trouve dans: {raw[:200]}")
        return []

    except Exception as e:
        logger.error(f"Erreur search_medicaments: {type(e).__name__}: {e}")
        return []


def get_medicament_detail(code_cis: str):
    return None

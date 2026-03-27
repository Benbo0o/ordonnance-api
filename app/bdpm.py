"""
Recherche de medicaments via Claude AI.
Claude connait parfaitement la BDPM française - source fiable et stable.
"""
import json
import os
import logging

logger = logging.getLogger(__name__)


def search_medicaments(query: str, limit: int = 5) -> list[dict]:
    """Recherche un medicament via Claude AI (base BDPM integree)."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY manquante")
        return []

    client = anthropic.Anthropic(api_key=api_key)

    prompt = (
        f'Donne-moi {limit} medicaments reels de la BDPM française pour : "{query}". '
        'Reponds UNIQUEMENT avec un JSON array valide, sans texte ni backticks. '
        'Format : [{"code_cis":"...","denomination":"...","forme_pharma":"...",'
        '"voies_admin":"...","statut_amm":"Autorisation active",'
        '"etat_commercialisation":"Commercialise","substance_active":"..."}]'
    )

    try:
        msg = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=800,
            system=(
                "Tu es un expert en pharmacologie française et connais parfaitement "
                "la Base de Donnees Publique des Medicaments (BDPM). "
                "Reponds UNIQUEMENT avec du JSON valide. Aucun texte avant ou apres."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        # Extraire le tableau JSON meme si Claude ajoute du texte
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            text = text[start:end]
        results = json.loads(text)
        if isinstance(results, list):
            return results[:limit]
    except Exception as e:
        logger.error(f"Erreur recherche medicament: {e}")

    return []


def get_medicament_detail(code_cis: str):
    return None

“””
Recherche de medicaments via Claude AI (base BDPM francaise).
“””
import json
import os
import logging

logger = logging.getLogger(**name**)

def search_medicaments(query: str, limit: int = 5) -> list[dict]:
“”“Recherche un medicament via Claude AI.”””
import anthropic

```
api_key = os.environ.get("ANTHROPIC_API_KEY", "")
if not api_key:
    logger.error("ANTHROPIC_API_KEY manquante")
    return []

client = anthropic.Anthropic(api_key=api_key)

prompt = (
    f'Recherche dans la BDPM française : "{query}"\n\n'
    f'Retourne exactement {limit} medicaments. '
    'JSON array STRICT, sans backticks, sans commentaires :\n'
    '[\n'
    '  {\n'
    '    "denomination": "DOLIPRANE 1000 mg, comprime pellicule",\n'
    '    "forme_pharma": "comprime pellicule",\n'
    '    "voies_admin": "orale",\n'
    '    "substance_active": "Paracetamol",\n'
    '    "statut_amm": "Autorisation active",\n'
    '    "etat_commercialisation": "Commercialise",\n'
    '    "code_cis": "60001393"\n'
    '  }\n'
    ']\n\n'
    'IMPORTANT: Utilise uniquement des caracteres ASCII simples. '
    'Remplace e accent par e, e accent grave par e, etc. '
    'Reponds UNIQUEMENT avec le JSON, rien d\'autre.'
)

try:
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=(
            "Tu es un expert de la pharmacopee francaise et connais la BDPM. "
            "Reponds TOUJOURS avec un JSON array valide uniquement. "
            "Aucun texte avant ou apres. Jamais de backticks ni de markdown. "
            "Utilise uniquement des caracteres ASCII (pas d accents)."
        ),
        messages=[{"role": "user", "content": prompt}],
    )

    raw = msg.content[0].text.strip()
    logger.info(f"Claude reponse pour '{query}': {raw[:300]}")

    # Nettoyage
    raw = raw.replace("```json", "").replace("```", "").strip()

    # Extraire le JSON array
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start >= 0 and end > start:
        parsed = json.loads(raw[start:end])
        if isinstance(parsed, list) and len(parsed) > 0:
            # Verifier que ce sont bien des objets dict
            if isinstance(parsed[0], dict):
                return parsed[:limit]
            else:
                # Claude a retourne une liste de strings - convertir
                return [{"denomination": str(item), "forme_pharma": "",
                         "voies_admin": "orale", "substance_active": "",
                         "statut_amm": "Autorisation active",
                         "etat_commercialisation": "Commercialise",
                         "code_cis": ""} for item in parsed[:limit]]

    logger.warning(f"Aucun JSON array valide dans: {raw[:200]}")
    return []

except json.JSONDecodeError as e:
    logger.error(f"JSON invalide: {e} — texte: {raw[:200]}")
    return []
except Exception as e:
    logger.error(f"Erreur search_medicaments: {type(e).__name__}: {e}")
    return []
```

def get_medicament_detail(code_cis: str):
return None

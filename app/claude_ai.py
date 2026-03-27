"""
Module de formatage des prescriptions via Claude API.
Transforme les données BDPM en lignes d'ordonnance médicales professionnelles.
"""
import anthropic
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def format_prescription_line(
    client: anthropic.Anthropic,
    denomination: str,
    indication: str,
    forme_pharma: str = "",
    posologie_libre: Optional[str] = None,
) -> str:
    """
    Utilise Claude pour rédiger une ligne d'ordonnance professionnelle.
    
    Args:
        client: Instance du client Anthropic
        denomination: Nom du médicament (ex: "DOLIPRANE 1000mg comprimé")
        indication: Indication clinique ou posologie souhaitée
        forme_pharma: Forme pharmaceutique (cp, gélule, solution...)
        posologie_libre: Posologie saisie librement par le médecin (prioritaire)
    
    Returns:
        Ligne d'ordonnance formatée
    """
    # Si posologie libre fournie, pas besoin de Claude
    if posologie_libre:
        return f"{denomination}\n    {posologie_libre}"

    system_prompt = """Tu es un assistant médical expert en rédaction d'ordonnances françaises.
Tu dois rédiger des lignes d'ordonnance concises, précises et professionnelles.
Format de sortie strict (2 lignes maximum) :
- Ligne 1 : Nom du médicament + forme + dosage
- Ligne 2 : Posologie (ex: "1 comprimé matin et soir pendant 7 jours")
Ne jamais ajouter de commentaires, d'explications ou de mentions légales.
Répondre uniquement avec la prescription, sans formatage markdown."""

    user_prompt = f"""Médicament : {denomination}
Forme pharmaceutique : {forme_pharma or 'non précisée'}
Indication / contexte clinique : {indication}

Rédige la ligne d'ordonnance standard pour ce médicament."""

    try:
        msg = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=200,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return msg.content[0].text.strip()
    except anthropic.APIError as e:
        logger.error(f"Erreur Claude API: {e}")
        return f"{denomination}\n    {indication}"


def validate_prescription(
    client: anthropic.Anthropic,
    prescriptions: list[dict],
    patient_age: Optional[int] = None,
    patient_weight: Optional[float] = None,
    allergies: Optional[list[str]] = None,
) -> dict:
    """
    Vérifie les interactions médicamenteuses et contre-indications (optionnel).
    
    Returns:
        dict avec 'safe' (bool), 'warnings' (list), 'interactions' (list)
    """
    if len(prescriptions) < 2:
        return {"safe": True, "warnings": [], "interactions": []}

    meds_list = "\n".join(
        f"- {p['denomination']} : {p['indication']}" for p in prescriptions
    )

    context = ""
    if patient_age:
        context += f"Âge patient : {patient_age} ans. "
    if patient_weight:
        context += f"Poids : {patient_weight} kg. "
    if allergies:
        context += f"Allergies connues : {', '.join(allergies)}. "

    try:
        msg = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=500,
            system="""Tu es un expert en pharmacologie clinique.
Analyse les interactions médicamenteuses et contre-indications.
Réponds UNIQUEMENT en JSON valide avec ce format :
{"safe": true/false, "warnings": ["..."], "interactions": [{"med1": "...", "med2": "...", "niveau": "mineur/modéré/majeur", "description": "..."}]}""",
            messages=[{
                "role": "user",
                "content": f"{context}\n\nMédicaments prescrits :\n{meds_list}\n\nAnalyse les interactions et contre-indications."
            }],
        )
        import json
        text = msg.content[0].text.strip()
        return json.loads(text)
    except Exception as e:
        logger.error(f"Erreur validation prescription: {e}")
        return {"safe": True, "warnings": ["Validation automatique indisponible"], "interactions": []}

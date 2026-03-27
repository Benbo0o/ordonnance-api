"""
Script standalone — génère une ordonnance PDF directement sans passer par l'API REST.
Pratique pour tester ou pour un usage ponctuel.

Usage :
    export ANTHROPIC_API_KEY="sk-ant-..."
    python scripts/generate_direct.py
"""
import os
import sys

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
from app.bdpm import search_medicaments
from app.claude_ai import format_prescription_line, validate_prescription
from app.pdf_generator import generate_pdf


def main():
    # ── Configuration ─────────────────────────────────────────────
    API_KEY = os.environ.get("ANTHROPIC_API_KEY")
    if not API_KEY:
        print("⚠  Définissez ANTHROPIC_API_KEY : export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=API_KEY)

    # ── Données patient ───────────────────────────────────────────
    patient = {
        "name": "DUPONT Jean",
        "dob": "22/07/1965",
    }

    # ── Médicaments à prescrire ───────────────────────────────────
    # Format : {"query": "nom pour BDPM", "indication": "contexte clinique"}
    medications_to_prescribe = [
        {
            "query": "paracetamol 1000",
            "indication": "Antalgie post-opératoire (chirurgie du genou)"
        },
        {
            "query": "ibuprofene 400",
            "indication": "Anti-inflammatoire post-opératoire"
        },
        {
            "query": "pantoprazole 40",
            "indication": "Protection gastrique sous AINS"
        },
    ]

    # ── Pipeline ─────────────────────────────────────────────────
    print(f"\nGénération ordonnance pour : {patient['name']}")
    print("─" * 50)

    prescriptions = []
    for item in medications_to_prescribe:
        print(f"\n🔍 Recherche BDPM : {item['query']}")
        results = search_medicaments(item["query"], limit=1)

        if results:
            denomination = results[0]["denomination"]
            forme = results[0].get("forme_pharma", "")
            print(f"   → {denomination}")
        else:
            denomination = item["query"].upper()
            forme = ""
            print(f"   → Non trouvé, utilisation : {denomination}")

        print(f"🤖 Formatage Claude...")
        ligne = format_prescription_line(
            client=client,
            denomination=denomination,
            indication=item["indication"],
            forme_pharma=forme,
        )
        print(f"   → {ligne.replace(chr(10), ' | ')}")
        prescriptions.append({"denomination": denomination, "ligne": ligne})

    # ── Validation interactions ───────────────────────────────────
    print("\n🔬 Vérification interactions médicamenteuses...")
    val_data = [
        {"denomination": p["denomination"], "indication": "prescription"}
        for p in prescriptions
    ]
    validation = validate_prescription(client, val_data, patient_age=58)
    
    if not validation["safe"]:
        print("⚠  ATTENTION - Interactions détectées !")
        for ia in validation.get("interactions", []):
            print(f"   [{ia['niveau'].upper()}] {ia.get('description', '')}")
    else:
        print("✓  Aucune interaction majeure détectée")

    # ── Génération PDF ────────────────────────────────────────────
    print("\n📄 Génération du PDF...")
    output_dir = os.path.expanduser("~/Desktop") if os.path.exists(
        os.path.expanduser("~/Desktop")) else "/tmp"

    pdf_path = generate_pdf(
        patient_name=patient["name"],
        patient_dob=patient["dob"],
        prescriptions=prescriptions,
        output_dir=output_dir,
    )

    print(f"\n✅ Ordonnance générée : {pdf_path}")
    print(f"   Ouvrir : open '{pdf_path}'  (macOS)")
    print(f"   Ouvrir : xdg-open '{pdf_path}'  (Linux)")


if __name__ == "__main__":
    main()

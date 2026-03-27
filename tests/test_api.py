"""
Tests et exemples d'utilisation de l'API.
Lancez l'API puis exécutez ce script.

Usage :
    python tests/test_api.py
    python tests/test_api.py --url http://votre-serveur:8000
"""
import argparse
import json
import requests
import sys

BASE = "http://localhost:8000"


def test_health():
    print("\n── Health check ─────────────────────────")
    r = requests.get(f"{BASE}/health")
    print(r.json())
    assert r.status_code == 200


def test_bdpm_search():
    print("\n── Recherche BDPM ───────────────────────")
    payload = {"query": "doliprane", "limit": 3}
    r = requests.post(f"{BASE}/api/bdpm/search", json=payload)
    data = r.json()
    print(f"Résultats ({data['count']}) :")
    for med in data["results"]:
        print(f"  - {med['denomination']} | {med['forme_pharma']}")
    return data["results"][0] if data["results"] else None


def test_format_prescription(denomination: str):
    print("\n── Formatage prescription (Claude) ──────")
    payload = {
        "denomination": denomination,
        "indication": "Douleur post-opératoire légère à modérée",
        "forme_pharma": "comprimé",
    }
    r = requests.post(f"{BASE}/api/prescription/format", json=payload)
    data = r.json()
    print(f"Ligne générée :\n{data['ligne']}")
    return data["ligne"]


def test_validate():
    print("\n── Validation interactions ──────────────")
    payload = {
        "prescriptions": [
            {"denomination": "DOLIPRANE 1000mg", "indication": "douleur"},
            {"denomination": "IBUPROFENE 400mg", "indication": "inflammation"},
        ],
        "patient_age": 65,
        "allergies": [],
    }
    r = requests.post(f"{BASE}/api/prescription/validate", json=payload)
    data = r.json()
    print(f"Sécurité : {'✓ OK' if data['safe'] else '⚠ ATTENTION'}")
    if data.get("warnings"):
        print(f"Avertissements : {data['warnings']}")
    if data.get("interactions"):
        for ia in data["interactions"]:
            print(f"  Interaction [{ia['niveau']}] : {ia.get('description','')}")


def test_generate_pdf(denomination: str, ligne: str):
    print("\n── Génération PDF ───────────────────────")
    payload = {
        "patient_name": "MARTIN Sophie",
        "patient_dob": "15/03/1978",
        "prescriptions": [
            {"denomination": denomination, "ligne": ligne},
            {
                "denomination": "IBUPROFENE 400mg comprimé",
                "ligne": "IBUPROFENE 400mg comprimé\n    1 comprimé × 3/j pendant 5 jours (à prendre au cours des repas)"
            },
        ],
        "doctor_name": "Benjamin BONNOT",
        "doctor_specialty": "Anesthésiste-Réanimateur",
        "doctor_rpps": "751031329",
        "clinic_name": "Clinique Moussins-Nollet",
        "clinic_address": "67 rue de Romainville, 75019 PARIS",
        "clinic_phone": "01 40 03 12 12",
        "clinic_finess": "750301160",
        "clinic_rpps_code": "10100661908",
    }

    r = requests.post(f"{BASE}/api/ordonnance/generate", json=payload, stream=True)
    
    if r.status_code == 200:
        filename = "test_ordonnance.pdf"
        with open(filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"✓ PDF téléchargé : {filename}")
    else:
        print(f"✗ Erreur {r.status_code} : {r.json()}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()
    global BASE
    BASE = args.url.rstrip("/")

    print(f"Test API sur : {BASE}")
    
    try:
        test_health()
        
        med = test_bdpm_search()
        denomination = med["denomination"] if med else "DOLIPRANE 1000mg comprimé"
        
        ligne = test_format_prescription(denomination)
        
        test_validate()
        
        test_generate_pdf(denomination, ligne)

        print("\n✓ Tous les tests passés !")
    
    except requests.ConnectionError:
        print(f"\n✗ Impossible de contacter {BASE}. L'API est-elle lancée ?")
        print("  Lancez : uvicorn app.main:app --reload")
        sys.exit(1)
    except AssertionError as e:
        print(f"\n✗ Test échoué : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

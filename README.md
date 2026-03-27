# API Ordonnance Médicale

Génère des ordonnances PDF non-modifiables via Claude API + BDPM.

## Architecture

```
Client (votre app)
    │
    ▼
FastAPI (port 8000)
    ├── POST /api/bdpm/search          → Recherche BDPM officielle
    ├── POST /api/prescription/format  → Formatage Claude AI
    ├── POST /api/prescription/validate → Vérification interactions
    └── POST /api/ordonnance/generate  → PDF non-modifiable ⬇
            │
            ├── python-docx  → Remplit le template Word
            └── LibreOffice  → Convertit en PDF verrouillé
```

## Installation

### Prérequis

```bash
# Python 3.11+
pip install -r requirements.txt

# LibreOffice (conversion PDF)
# macOS
brew install --cask libreoffice

# Ubuntu / Debian
sudo apt install libreoffice

# Windows : https://www.libreoffice.org/download/
```

### Logo clinique

Copiez votre logo dans `template/logo_clinique.jpg`
(sinon l'en-tête s'affiche sans logo)

### Clé API Anthropic

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-..."
```

## Lancer l'API

```bash
# Développement
uvicorn app.main:app --reload --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Documentation interactive : **http://localhost:8000/docs**

## Utilisation

### Option 1 — Script direct (le plus simple)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python scripts/generate_direct.py
```

### Option 2 — Via l'API REST

#### Étape 1 : Chercher le médicament dans la BDPM

```bash
curl -X POST http://localhost:8000/api/bdpm/search \
  -H "Content-Type: application/json" \
  -d '{"query": "doliprane", "limit": 3}'
```

```json
{
  "query": "doliprane",
  "count": 3,
  "results": [
    {
      "code_cis": "60001393",
      "denomination": "DOLIPRANE 1000 mg, comprimé",
      "forme_pharma": "comprimé",
      "voies_admin": "orale",
      "statut_amm": "Autorisation active",
      "etat_commercialisation": "Commercialisé"
    }
  ]
}
```

#### Étape 2 : Formater la ligne d'ordonnance

```bash
curl -X POST http://localhost:8000/api/prescription/format \
  -H "Content-Type: application/json" \
  -d '{
    "denomination": "DOLIPRANE 1000 mg, comprimé",
    "indication": "Douleur post-opératoire",
    "forme_pharma": "comprimé"
  }'
```

```json
{
  "denomination": "DOLIPRANE 1000 mg, comprimé",
  "ligne": "DOLIPRANE 1000 mg, comprimé\n    1 comprimé toutes les 6 heures si douleur (max 4/jour)\n    Durée : 5 jours",
  "source": "claude_ai"
}
```

#### Étape 3 : Générer le PDF

```bash
curl -X POST http://localhost:8000/api/ordonnance/generate \
  -H "Content-Type: application/json" \
  -o ordonnance_martin.pdf \
  -d '{
    "patient_name": "MARTIN Sophie",
    "patient_dob": "15/03/1978",
    "prescriptions": [
      {
        "denomination": "DOLIPRANE 1000 mg, comprimé",
        "ligne": "DOLIPRANE 1000 mg, comprimé\n    1 comprimé toutes les 6h (max 4/j)\n    Durée : 5 jours"
      },
      {
        "denomination": "IBUPROFENE 400 mg, comprimé",
        "ligne": "IBUPROFENE 400 mg, comprimé\n    1 comprimé × 3/j au cours des repas\n    Durée : 5 jours"
      }
    ]
  }'
```

### Option 3 — Docker

```bash
# Construire et lancer
ANTHROPIC_API_KEY="sk-ant-..." docker-compose up -d

# Vérifier
curl http://localhost:8000/health
```

## Python — Intégration directe

```python
import requests

BASE = "http://localhost:8000"

def generer_ordonnance(patient_name, patient_dob, medicaments):
    """
    medicaments = [
        {"query": "doliprane 1000", "indication": "douleur post-op"},
        {"query": "ibuprofene 400", "indication": "anti-inflammatoire"},
    ]
    """
    prescriptions = []

    for med in medicaments:
        # 1. BDPM
        r = requests.post(f"{BASE}/api/bdpm/search",
                          json={"query": med["query"], "limit": 1})
        results = r.json().get("results", [])
        denomination = results[0]["denomination"] if results else med["query"]

        # 2. Formatage Claude
        r = requests.post(f"{BASE}/api/prescription/format", json={
            "denomination": denomination,
            "indication": med["indication"],
        })
        ligne = r.json()["ligne"]
        prescriptions.append({"denomination": denomination, "ligne": ligne})

    # 3. PDF
    r = requests.post(f"{BASE}/api/ordonnance/generate", json={
        "patient_name": patient_name,
        "patient_dob": patient_dob,
        "prescriptions": prescriptions,
    }, stream=True)

    if r.status_code == 200:
        with open("ordonnance.pdf", "wb") as f:
            f.write(r.content)
        print("✓ ordonnance.pdf générée")
    else:
        print(f"Erreur : {r.json()}")

# Utilisation
generer_ordonnance(
    patient_name="MARTIN Sophie",
    patient_dob="15/03/1978",
    medicaments=[
        {"query": "doliprane 1000", "indication": "douleur post-opératoire"},
        {"query": "ibuprofene 400", "indication": "inflammation"},
    ]
)
```

## Structure du projet

```
ordonnance-api/
├── app/
│   ├── main.py            ← FastAPI — routes et modèles
│   ├── bdpm.py            ← Intégration API BDPM
│   ├── claude_ai.py       ← Formatage et validation via Claude
│   └── pdf_generator.py   ← Génération Word → PDF
├── template/
│   └── logo_clinique.jpg  ← Votre logo (à ajouter)
├── tests/
│   └── test_api.py        ← Tests et exemples
├── scripts/
│   └── generate_direct.py ← Script standalone sans API
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Variables d'environnement

| Variable | Obligatoire | Description |
|----------|-------------|-------------|
| `ANTHROPIC_API_KEY` | ✓ | Clé API Anthropic (claude.ai → API Keys) |

## Personnalisation

Pour utiliser votre propre entête (autre clinique, autre médecin) :
passez les paramètres `doctor_*` et `clinic_*` dans le body de `/api/ordonnance/generate`.
Tous ont des valeurs par défaut configurées pour le Dr BONNOT.

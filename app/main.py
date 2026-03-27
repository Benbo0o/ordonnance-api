"""
API REST pour la génération d'ordonnances médicales PDF.
Utilise Claude API + BDPM + python-docx + LibreOffice.

Lancer : uvicorn app.main:app --reload --port 8000
Documentation : http://localhost:8000/docs
"""
import os
import tempfile
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
import anthropic
import logging

from app.bdpm import search_medicaments, get_medicament_detail
from app.claude_ai import format_prescription_line, validate_prescription
from app.pdf_generator import generate_pdf

# ── Configuration logging ─────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── App FastAPI ───────────────────────────────────────────────────
app = FastAPI(
    title="API Ordonnance Médicale",
    description="""
Génère des ordonnances PDF non-modifiables à partir :
- des données patient
- d'une recherche dans la BDPM (Base de Données Publique des Médicaments)
- du formatage automatique par Claude AI

## Workflow recommandé
1. `POST /api/bdpm/search` — chercher le médicament
2. `POST /api/prescription/format` — formater la ligne d'ordonnance
3. `POST /api/ordonnance/generate` — générer le PDF final
""",
    version="1.0.0",
    contact={"name": "Dr. Benjamin BONNOT", "email": "drbonnot@gmail.com"},
)

# ── Client Anthropic ──────────────────────────────────────────────
def get_claude_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY non configurée dans les variables d'environnement"
        )
    return anthropic.Anthropic(api_key=api_key)


# ── Modèles Pydantic ──────────────────────────────────────────────

class BDPMSearchRequest(BaseModel):
    query: str = Field(..., description="Nom commercial ou DCI du médicament", example="doliprane")
    limit: int = Field(5, ge=1, le=20, description="Nombre de résultats")


class FormatPrescriptionRequest(BaseModel):
    denomination: str = Field(..., example="DOLIPRANE 1000mg comprimé")
    indication: str = Field(..., example="Douleur post-opératoire")
    forme_pharma: str = Field("", example="comprimé")
    posologie_libre: Optional[str] = Field(
        None,
        description="Si renseigné, Claude n'est pas utilisé — posologie utilisée telle quelle",
        example="1 comprimé matin et soir pendant 5 jours"
    )


class MedicamentPrescrit(BaseModel):
    denomination: str = Field(..., example="DOLIPRANE 1000mg comprimé")
    ligne: str = Field(
        ...,
        description="Ligne complète formatée (sortie de /prescription/format)",
        example="DOLIPRANE 1000mg comprimé\n    1 comprimé × 3/j pendant 5 jours"
    )


class OrdonnanceRequest(BaseModel):
    # Patient
    patient_name: str = Field(..., example="MARTIN Sophie")
    patient_dob: str = Field(..., example="15/03/1978")

    # Traitements
    prescriptions: list[MedicamentPrescrit] = Field(
        ..., min_length=1, description="Liste des médicaments prescrits"
    )

    # Infos médecin (optionnel — utilise les valeurs par défaut du Dr BONNOT)
    doctor_name: str = Field("Benjamin BONNOT", example="Benjamin BONNOT")
    doctor_specialty: str = Field("Anesthésiste-Réanimateur")
    doctor_rpps: str = Field("751031329")

    # Infos clinique
    clinic_name: str = Field("Clinique Moussins-Nollet")
    clinic_address: str = Field("67 rue de Romainville, 75019 PARIS")
    clinic_phone: str = Field("01 40 03 12 12")
    clinic_finess: str = Field("750301160")
    clinic_rpps_code: str = Field("10100661908")


class ValidationRequest(BaseModel):
    prescriptions: list[FormatPrescriptionRequest]
    patient_age: Optional[int] = Field(None, example=65)
    patient_weight: Optional[float] = Field(None, example=75.0)
    allergies: Optional[list[str]] = Field(None, example=["pénicilline", "AINS"])


# ── Routes ────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    return {
        "message": "API Ordonnance Médicale — v1.0",
        "docs": "/docs",
        "status": "ok"
    }


@app.get("/health")
def health():
    """Vérifie l'état de l'API."""
    return {"status": "ok", "libreoffice": _check_libreoffice()}


@app.post(
    "/api/bdpm/search",
    summary="Rechercher un médicament dans la BDPM",
    tags=["BDPM"],
)
def bdpm_search(req: BDPMSearchRequest):
    """
    Recherche dans la Base de Données Publique des Médicaments (BDPM).
    Retourne les médicaments correspondant à la requête avec leurs informations.
    """
    results = search_medicaments(req.query, req.limit)
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"Aucun médicament trouvé pour '{req.query}'"
        )
    return {"query": req.query, "count": len(results), "results": results}


@app.get(
    "/api/bdpm/medicament/{code_cis}",
    summary="Détail d'un médicament par code CIS",
    tags=["BDPM"],
)
def bdpm_detail(code_cis: str):
    """Récupère le détail complet d'un médicament (composition, présentations)."""
    detail = get_medicament_detail(code_cis)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Médicament {code_cis} non trouvé")
    return detail


@app.post(
    "/api/prescription/format",
    summary="Formater une ligne d'ordonnance avec Claude AI",
    tags=["Prescription"],
)
def format_prescription(req: FormatPrescriptionRequest):
    """
    Utilise Claude pour rédiger une ligne d'ordonnance professionnelle.
    Si `posologie_libre` est fourni, Claude n'est pas appelé.
    """
    client = get_claude_client()
    ligne = format_prescription_line(
        client=client,
        denomination=req.denomination,
        indication=req.indication,
        forme_pharma=req.forme_pharma,
        posologie_libre=req.posologie_libre,
    )
    return {
        "denomination": req.denomination,
        "ligne": ligne,
        "source": "libre" if req.posologie_libre else "claude_ai",
    }


@app.post(
    "/api/prescription/validate",
    summary="Vérifier les interactions médicamenteuses",
    tags=["Prescription"],
)
def validate_prescriptions(req: ValidationRequest):
    """
    Analyse les interactions médicamenteuses et contre-indications
    pour une liste de médicaments (optionnel mais recommandé).
    """
    client = get_claude_client()
    prescriptions_dict = [
        {"denomination": p.denomination, "indication": p.indication}
        for p in req.prescriptions
    ]
    result = validate_prescription(
        client=client,
        prescriptions=prescriptions_dict,
        patient_age=req.patient_age,
        patient_weight=req.patient_weight,
        allergies=req.allergies,
    )
    return result


@app.post(
    "/api/ordonnance/generate",
    summary="Générer l'ordonnance PDF non-modifiable",
    tags=["Ordonnance"],
    response_class=FileResponse,
)
def generate_ordonnance(req: OrdonnanceRequest, background_tasks: BackgroundTasks):
    """
    Génère un PDF d'ordonnance non-modifiable à partir des données patient
    et des médicaments prescrits (préalablement formatés).

    Retourne le fichier PDF en téléchargement direct.
    """
    output_dir = tempfile.mkdtemp()
    
    try:
        pdf_path = generate_pdf(
            patient_name=req.patient_name,
            patient_dob=req.patient_dob,
            prescriptions=[p.model_dump() for p in req.prescriptions],
            output_dir=output_dir,
            doctor_name=req.doctor_name,
            doctor_specialty=req.doctor_specialty,
            doctor_rpps=req.doctor_rpps,
            clinic_name=req.clinic_name,
            clinic_address=req.clinic_address,
            clinic_phone=req.clinic_phone,
            clinic_finess=req.clinic_finess,
            clinic_rpps_code=req.clinic_rpps_code,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Erreur génération PDF")
        raise HTTPException(status_code=500, detail=f"Erreur interne : {e}")

    # Nettoyer le dossier temporaire après envoi
    background_tasks.add_task(_cleanup, output_dir)

    filename = os.path.basename(pdf_path)
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post(
    "/api/ordonnance/full",
    summary="Pipeline complet : BDPM + Claude + PDF en une seule requête",
    tags=["Ordonnance"],
    response_class=FileResponse,
)
def generate_ordonnance_full(
    patient_name: str,
    patient_dob: str,
    background_tasks: BackgroundTasks,
    medications: list[str] = None,
    indications: list[str] = None,
):
    """
    Pipeline tout-en-un :
    1. Recherche chaque médicament dans la BDPM
    2. Formate chaque ligne via Claude
    3. Génère le PDF
    
    **medications** : liste de noms (ex: ["doliprane", "ibuprofène"])
    **indications** : liste d'indications correspondantes (même ordre)
    """
    if not medications:
        raise HTTPException(status_code=400, detail="Au moins un médicament requis")

    client = get_claude_client()
    prescriptions = []

    for i, med_query in enumerate(medications):
        indication = indications[i] if indications and i < len(indications) else med_query

        # 1. Recherche BDPM
        results = search_medicaments(med_query, limit=1)
        denomination = results[0]["denomination"] if results else med_query
        forme = results[0].get("forme_pharma", "") if results else ""

        # 2. Formatage Claude
        ligne = format_prescription_line(
            client=client,
            denomination=denomination,
            indication=indication,
            forme_pharma=forme,
        )
        prescriptions.append({"denomination": denomination, "ligne": ligne})

    output_dir = tempfile.mkdtemp()
    pdf_path = generate_pdf(
        patient_name=patient_name,
        patient_dob=patient_dob,
        prescriptions=prescriptions,
        output_dir=output_dir,
    )

    background_tasks.add_task(_cleanup, output_dir)

    filename = os.path.basename(pdf_path)
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=filename,
    )


# ── Utilitaires ───────────────────────────────────────────────────

def _check_libreoffice() -> bool:
    import shutil
    return any(shutil.which(cmd) for cmd in ["libreoffice", "soffice"])


def _cleanup(path: str):
    import shutil
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass

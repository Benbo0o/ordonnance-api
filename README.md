"""
API REST pour la generation d'ordonnances medicales PDF.
Utilise Claude API + BDPM + python-docx + LibreOffice.

Lancer : uvicorn app.main:app --reload --port 8000
Documentation : http://localhost:8000/docs
"""
import os
import tempfile
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import anthropic
import logging

from app.bdpm import search_medicaments, get_medicament_detail
from app.claude_ai import format_prescription_line, validate_prescription
from app.pdf_generator import generate_pdf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="API Ordonnance Medicale",
    description="Genere des ordonnances PDF non-modifiables via Claude AI + BDPM.",
    version="1.1.0",
    contact={"name": "Dr. Benjamin BONNOT", "email": "drbonnot@gmail.com"},
)

# CORS — autorise toutes les origines (iPhone, navigateur, apps)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_claude_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY non configuree dans les variables d'environnement"
        )
    return anthropic.Anthropic(api_key=api_key)


class BDPMSearchRequest(BaseModel):
    query: str = Field(..., description="Nom commercial ou DCI du medicament", example="doliprane")
    limit: int = Field(5, ge=1, le=20, description="Nombre de resultats")


class FormatPrescriptionRequest(BaseModel):
    denomination: str = Field(..., example="DOLIPRANE 1000mg comprime")
    indication: str = Field(..., example="Douleur post-operatoire")
    forme_pharma: str = Field("", example="comprime")
    posologie_libre: Optional[str] = Field(
        None,
        description="Si renseigne, Claude n'est pas utilise",
        example="1 comprime matin et soir pendant 5 jours"
    )


class MedicamentPrescrit(BaseModel):
    denomination: str = Field(..., example="DOLIPRANE 1000mg comprime")
    ligne: str = Field(
        ...,
        description="Ligne complete formatee",
        example="DOLIPRANE 1000mg comprime\n    1 comprime x 3/j pendant 5 jours"
    )


class OrdonnanceRequest(BaseModel):
    patient_name: str = Field(..., example="MARTIN Sophie")
    patient_dob: str = Field(..., example="15/03/1978")
    prescriptions: list[MedicamentPrescrit] = Field(..., min_length=1)
    doctor_name: str = Field("Benjamin BONNOT")
    doctor_specialty: str = Field("Anesthesiste-Reanimateur")
    doctor_rpps: str = Field("751031329")
    clinic_name: str = Field("Clinique Moussins-Nollet")
    clinic_address: str = Field("67 rue de Romainville, 75019 PARIS")
    clinic_phone: str = Field("01 40 03 12 12")
    clinic_finess: str = Field("750301160")
    clinic_rpps_code: str = Field("10100661908")


class ValidationRequest(BaseModel):
    prescriptions: list[FormatPrescriptionRequest]
    patient_age: Optional[int] = Field(None, example=65)
    patient_weight: Optional[float] = Field(None, example=75.0)
    allergies: Optional[list[str]] = Field(None, example=["penicilline", "AINS"])


@app.get("/", include_in_schema=False)
def root():
    return {"message": "API Ordonnance Medicale v1.1", "docs": "/docs", "status": "ok"}


@app.get("/health")
def health():
    """Verifie l'etat de l'API."""
    return {"status": "ok", "libreoffice": _check_libreoffice()}


@app.post("/api/bdpm/search", summary="Rechercher un medicament dans la BDPM", tags=["BDPM"])
def bdpm_search(req: BDPMSearchRequest):
    """Recherche dans la Base de Donnees Publique des Medicaments."""
    results = search_medicaments(req.query, req.limit)
    if not results:
        raise HTTPException(status_code=404, detail=f"Aucun medicament trouve pour '{req.query}'")
    return {"query": req.query, "count": len(results), "results": results}


@app.get("/api/bdpm/medicament/{code_cis}", summary="Detail d'un medicament", tags=["BDPM"])
def bdpm_detail(code_cis: str):
    detail = get_medicament_detail(code_cis)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Medicament {code_cis} non trouve")
    return detail


@app.post("/api/prescription/format", summary="Formater une ligne d'ordonnance", tags=["Prescription"])
def format_prescription(req: FormatPrescriptionRequest):
    """Utilise Claude pour rediger une ligne d'ordonnance professionnelle."""
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


@app.post("/api/prescription/validate", summary="Verifier les interactions", tags=["Prescription"])
def validate_prescriptions(req: ValidationRequest):
    """Analyse les interactions medicamenteuses."""
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
    summary="Generer l'ordonnance PDF",
    tags=["Ordonnance"],
    response_class=FileResponse,
)
def generate_ordonnance(req: OrdonnanceRequest, background_tasks: BackgroundTasks):
    """Genere un PDF d'ordonnance non-modifiable."""
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
        logger.exception("Erreur generation PDF")
        raise HTTPException(status_code=500, detail=f"Erreur interne : {e}")

    background_tasks.add_task(_cleanup, output_dir)
    filename = os.path.basename(pdf_path)
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _check_libreoffice() -> bool:
    import shutil
    return any(shutil.which(cmd) for cmd in ["libreoffice", "soffice"])
            

def _cleanup(path: str):
    import shutil
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass

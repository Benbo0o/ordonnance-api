import json
import os
import tempfile
import logging
import anthropic
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional
from app.claude_ai import format_prescription_line, validate_prescription
from app.pdf_generator import generate_pdf
import pathlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title='API Ordonnance', version='2.0.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Servir les fichiers statiques de la PWA
STATIC_DIR = pathlib.Path(__file__).parent.parent / 'static'
if STATIC_DIR.exists():
    app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')


def search_medicaments(query, limit=5):
    key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not key:
        return []
    client = anthropic.Anthropic(api_key=key)
    try:
        sys_msg = 'Expert BDPM francaise. JSON array uniquement, sans backticks. Chaque element est un objet avec denomination, forme_pharma, voies_admin, substance_active, statut_amm, etat_commercialisation, code_cis.'
        usr_msg = ('Donne ' + str(limit) + ' medicaments BDPM pour: ' + str(query)
                   + '. Format: [{"denomination": "DOLIPRANE 1000 mg comprime", "forme_pharma": "comprime",'
                   + ' "voies_admin": "orale", "substance_active": "Paracetamol",'
                   + ' "statut_amm": "Autorisation active", "etat_commercialisation": "Commercialise",'
                   + ' "code_cis": "60001393"}]')
        msg = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=2000,
            system=sys_msg,
            messages=[{'role': 'user', 'content': usr_msg}],
        )
        raw = msg.content[0].text.strip()
        raw = raw.replace('```json', '').replace('```', '').strip()
        start = raw.find('[')
        end = raw.rfind(']') + 1
        if start >= 0 and end > start:
            parsed = json.loads(raw[start:end])
            if isinstance(parsed, list):
                result = []
                for item in parsed:
                    if isinstance(item, dict):
                        result.append(item)
                    elif isinstance(item, str):
                        result.append({'denomination': item, 'forme_pharma': '',
                                       'voies_admin': 'orale', 'substance_active': '',
                                       'statut_amm': 'Autorisation active',
                                       'etat_commercialisation': 'Commercialise',
                                       'code_cis': ''})
                return result[:limit]
    except Exception as e:
        logger.error('search error: ' + str(e))
    return []


def get_claude_client():
    key = os.environ.get('ANTHROPIC_API_KEY')
    if not key:
        raise HTTPException(status_code=500, detail='ANTHROPIC_API_KEY manquante')
    return anthropic.Anthropic(api_key=key)


class BDPMSearchRequest(BaseModel):
    query: str = Field(..., example='doliprane')
    limit: int = Field(5, ge=1, le=10)


class FormatPrescriptionRequest(BaseModel):
    denomination: str
    indication: str
    forme_pharma: str = ''
    posologie_libre: Optional[str] = None


class MedicamentPrescrit(BaseModel):
    denomination: str
    ligne: str


class OrdonnanceRequest(BaseModel):
    patient_name: str
    patient_dob: str
    prescriptions: list[MedicamentPrescrit] = Field(..., min_length=1)
    doctor_name: str = 'Benjamin BONNOT'
    doctor_specialty: str = 'Anesthesiste-Reanimateur'
    doctor_rpps: str = '751031329'
    clinic_name: str = 'Clinique Moussins-Nollet'
    clinic_address: str = '67 rue de Romainville, 75019 PARIS'
    clinic_phone: str = '01 40 03 12 12'
    clinic_finess: str = '750301160'
    clinic_rpps_code: str = '10100661908'


class ValidationRequest(BaseModel):
    prescriptions: list[FormatPrescriptionRequest]
    patient_age: Optional[int] = None
    patient_weight: Optional[float] = None
    allergies: Optional[list[str]] = None


@app.get('/', response_class=HTMLResponse, include_in_schema=False)
def root():
    index = STATIC_DIR / 'index.html'
    if index.exists():
        return HTMLResponse(content=index.read_text(encoding='utf-8'))
    return HTMLResponse('<h1>API Ordonnance v2.0</h1><p><a href=/docs>Documentation</a></p>')


@app.get('/manifest.json', include_in_schema=False)
def manifest():
    f = STATIC_DIR / 'manifest.json'
    if f.exists():
        return FileResponse(str(f), media_type='application/manifest+json')
    return {}


@app.get('/sw.js', include_in_schema=False)
def service_worker():
    f = STATIC_DIR / 'sw.js'
    if f.exists():
        return FileResponse(str(f), media_type='application/javascript')
    return ''


@app.get('/health')
def health():
    import shutil
    lo = any(shutil.which(c) for c in ['libreoffice', 'soffice'])
    return {'status': 'ok', 'libreoffice': lo, 'version': '2.0.0'}


@app.get('/debug/claude', tags=['Debug'])
def debug_claude():
    key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not key:
        return {'error': 'ANTHROPIC_API_KEY manquante'}
    try:
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=50,
            messages=[{'role': 'user', 'content': 'Reponds juste ok'}],
        )
        return {'status': 'Claude repond', 'raw_response': msg.content[0].text,
                'api_key_present': True, 'api_key_prefix': key[:12] + '...'}
    except anthropic.AuthenticationError:
        return {'error': 'Cle API invalide'}
    except Exception as e:
        return {'error': str(e)}


@app.get('/debug/search/{query}', tags=['Debug'])
def debug_search(query: str):
    results = search_medicaments(query, 3)
    return {'query': query, 'count': len(results), 'results': results}


@app.post('/api/bdpm/search', tags=['BDPM'])
def bdpm_search(req: BDPMSearchRequest):
    results = search_medicaments(req.query, req.limit)
    return {'query': req.query, 'count': len(results), 'results': results}


@app.post('/api/prescription/format', tags=['Prescription'])
def format_prescription(req: FormatPrescriptionRequest):
    client = get_claude_client()
    ligne = format_prescription_line(
        client=client,
        denomination=req.denomination,
        indication=req.indication,
        forme_pharma=req.forme_pharma,
        posologie_libre=req.posologie_libre,
    )
    return {'denomination': req.denomination, 'ligne': ligne,
            'source': 'libre' if req.posologie_libre else 'claude_ai'}


@app.post('/api/prescription/validate', tags=['Prescription'])
def validate_prescriptions_route(req: ValidationRequest):
    client = get_claude_client()
    return validate_prescription(
        client=client,
        prescriptions=[{'denomination': p.denomination, 'indication': p.indication}
                       for p in req.prescriptions],
        patient_age=req.patient_age,
        patient_weight=req.patient_weight,
        allergies=req.allergies,
    )


@app.post('/api/ordonnance/generate', tags=['Ordonnance'], response_class=FileResponse)
def generate_ordonnance(req: OrdonnanceRequest, background_tasks: BackgroundTasks):
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
        logger.exception('Erreur PDF')
        raise HTTPException(status_code=500, detail=str(e))
    background_tasks.add_task(_cleanup, output_dir)
    filename = os.path.basename(pdf_path)
    return FileResponse(
        path=pdf_path,
        media_type='application/pdf',
        filename=filename,
        headers={'Content-Disposition': 'attachment; filename=' + filename},
    )


def _cleanup(path):
    import shutil
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass

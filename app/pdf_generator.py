"""
Générateur de PDF d'ordonnance.
Pipeline : Données patient → Template Word → PDF non-modifiable
"""
import subprocess
import os
import shutil
import tempfile
from datetime import date
from pathlib import Path
from docx import Document
from docx.shared import Pt, Inches, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import logging

logger = logging.getLogger(__name__)

# Chemins
TEMPLATE_DIR = Path(__file__).parent.parent / "template"
LOGO_PATH = TEMPLATE_DIR / "logo_clinique.jpg"


def generate_pdf(
    patient_name: str,
    patient_dob: str,
    prescriptions: list[dict],
    output_dir: str = "/tmp",
    doctor_name: str = "Dr. Benjamin BONNOT",
    doctor_specialty: str = "Anesthésiste-Réanimateur",
    doctor_rpps: str = "751031329",
    clinic_name: str = "Clinique Moussins-Nollet",
    clinic_address: str = "67 rue de Romainville, 75019 PARIS",
    clinic_phone: str = "01 40 03 12 12",
    clinic_finess: str = "750301160",
    clinic_rpps_code: str = "10100661908",
) -> str:
    """
    Génère une ordonnance PDF non-modifiable.
    
    Args:
        patient_name: Nom complet du patient
        patient_dob: Date de naissance (format DD/MM/YYYY)
        prescriptions: Liste de dicts [{"denomination": "...", "ligne": "..."}]
        output_dir: Répertoire de sortie
    
    Returns:
        Chemin vers le PDF généré
    """
    today = date.today().strftime("%d %B %Y").lower().replace(
        "january","janvier").replace("february","février").replace(
        "march","mars").replace("april","avril").replace("may","mai").replace(
        "june","juin").replace("july","juillet").replace("august","août").replace(
        "september","septembre").replace("october","octobre").replace(
        "november","novembre").replace("december","décembre")
    today = today[0].upper() + today[1:]  # capitalize first letter

    with tempfile.TemporaryDirectory() as tmpdir:
        # Générer le docx
        docx_path = os.path.join(tmpdir, "ordonnance.docx")
        _build_ordonnance_docx(
            docx_path=docx_path,
            patient_name=patient_name,
            patient_dob=patient_dob,
            prescriptions=prescriptions,
            today=today,
            doctor_name=doctor_name,
            doctor_specialty=doctor_specialty,
            doctor_rpps=doctor_rpps,
            clinic_name=clinic_name,
            clinic_address=clinic_address,
            clinic_phone=clinic_phone,
            clinic_finess=clinic_finess,
            clinic_rpps_code=clinic_rpps_code,
        )

        # Convertir en PDF via LibreOffice
        pdf_path = _convert_to_pdf(docx_path, output_dir, patient_name)

    return pdf_path


def _build_ordonnance_docx(
    docx_path: str,
    patient_name: str,
    patient_dob: str,
    prescriptions: list[dict],
    today: str,
    **kwargs,
) -> None:
    """Construit le fichier Word de l'ordonnance."""
    doc = Document()

    # ── Marges (2cm partout) ──────────────────────────────────────
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2)
    section.right_margin = Cm(2)
    section.top_margin = Cm(1.5)
    section.bottom_margin = Cm(1.5)

    # ── En-tête : tableau 3 colonnes ─────────────────────────────
    # Colonne 1 : Logo + adresse
    # Colonne 2 : Titre + infos médecin
    # Colonne 3 : Code-barres FINESS / RPPS
    hdr_table = doc.add_table(rows=1, cols=3)
    hdr_table.style = "Table Grid"
    hdr_table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Largeurs colonnes en DXA (1 cm = 567 DXA)
    col_widths = [3000, 5800, 3200]
    for i, cell in enumerate(hdr_table.rows[0].cells):
        cell.width = col_widths[i]
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        tcW = OxmlElement("w:tcW")
        tcW.set(qn("w:w"), str(col_widths[i]))
        tcW.set(qn("w:type"), "dxa")
        tcPr.append(tcW)

    # Cellule gauche : Logo + adresse
    cell_left = hdr_table.rows[0].cells[0]
    if LOGO_PATH.exists():
        p = cell_left.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        run.add_picture(str(LOGO_PATH), width=Cm(2.5))

    addr_p = cell_left.add_paragraph()
    addr_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    addr_run = addr_p.add_run(
        f"{kwargs['clinic_address'].split(',')[0]}\n"
        f"{kwargs['clinic_address'].split(',')[1].strip()}\n"
        f"Tél : {kwargs['clinic_phone']}"
    )
    addr_run.font.size = Pt(7.5)
    addr_run.font.name = "Arial"

    # Cellule centrale : titre + médecin
    cell_mid = hdr_table.rows[0].cells[1]
    _clear_cell(cell_mid)

    title_p = cell_mid.add_paragraph("ORDONNANCE DE SORTIE")
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_p.runs[0]
    title_run.bold = True
    title_run.font.size = Pt(12)
    title_run.font.name = "Arial"

    doc_p = cell_mid.add_paragraph(f"Docteur {kwargs['doctor_name'].replace('Dr. ','').replace('Dr ','')}")
    doc_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc_run = doc_p.runs[0]
    doc_run.bold = True
    doc_run.font.size = Pt(10)
    doc_run.font.name = "Arial"

    for txt in [
        f"Email : contact@clinique.fr",
        kwargs["doctor_specialty"],
        kwargs["doctor_rpps"],
    ]:
        p = cell_mid.add_paragraph(txt)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.size = Pt(8)
        p.runs[0].font.name = "Arial"

    # Cellule droite : codes-barres textuels
    cell_right = hdr_table.rows[0].cells[2]
    _clear_cell(cell_right)

    for label, code in [
        ("Code FINESS", kwargs["clinic_finess"]),
        ("Code RPPS", kwargs["clinic_rpps_code"]),
    ]:
        lp = cell_right.add_paragraph(label)
        lp.runs[0].font.size = Pt(7.5)
        lp.runs[0].font.name = "Arial"
        # Représentation visuelle du code-barres avec police Libre Barcode
        cp = cell_right.add_paragraph(code)
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cr = cp.runs[0]
        cr.font.size = Pt(7)
        # Fallback : afficher le code en gras encadré
        cp2 = cell_right.add_paragraph(f"[ {code} ]")
        cp2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cp2.runs[0].bold = True
        cp2.runs[0].font.size = Pt(7)
        cp2.runs[0].font.name = "Courier New"
        cell_right.add_paragraph()

    # ── Espacement après en-tête ──────────────────────────────────
    doc.add_paragraph()

    # ── Informations patient ──────────────────────────────────────
    pt_p = doc.add_paragraph()
    pt_run = pt_p.add_run(f"Nom Patient : ")
    pt_run.bold = True
    pt_run.font.size = Pt(10)
    pt_run.font.name = "Arial"
    pt_val = pt_p.add_run(patient_name.upper())
    pt_val.font.size = Pt(10)
    pt_val.font.name = "Arial"

    dob_p = doc.add_paragraph()
    dob_r = dob_p.add_run(f"Né(e) le : ")
    dob_r.font.size = Pt(10)
    dob_r.font.name = "Arial"
    dob_v = dob_p.add_run(patient_dob)
    dob_v.font.size = Pt(10)
    dob_v.font.name = "Arial"

    doc.add_paragraph()

    # ── Titre ORDONNANCE centré + souligné ────────────────────────
    ord_p = doc.add_paragraph()
    ord_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    ord_r = ord_p.add_run("ORDONNANCE")
    ord_r.bold = True
    ord_r.underline = True
    ord_r.font.size = Pt(14)
    ord_r.font.name = "Arial"

    doc.add_paragraph()

    # ── Traitements ───────────────────────────────────────────────
    for i, med in enumerate(prescriptions, 1):
        # Ligne médicament numérotée
        med_p = doc.add_paragraph()
        med_p.paragraph_format.space_before = Pt(4)
        med_p.paragraph_format.space_after = Pt(2)

        num_r = med_p.add_run(f"{i}. ")
        num_r.bold = True
        num_r.font.size = Pt(10)
        num_r.font.name = "Arial"

        name_r = med_p.add_run(med.get("denomination", ""))
        name_r.bold = True
        name_r.font.size = Pt(10)
        name_r.font.name = "Arial"

        # Posologie (ligne indentée)
        if med.get("ligne"):
            lines = med["ligne"].split("\n")
            # Si la première ligne = denomination, skip
            for j, line in enumerate(lines):
                if j == 0 and line.strip().upper() in med.get("denomination", "").upper():
                    continue
                if line.strip():
                    pos_p = doc.add_paragraph()
                    pos_p.paragraph_format.left_indent = Cm(0.8)
                    pos_p.paragraph_format.space_before = Pt(0)
                    pos_p.paragraph_format.space_after = Pt(1)
                    pos_r = pos_p.add_run(line.strip())
                    pos_r.font.size = Pt(10)
                    pos_r.font.name = "Arial"

    # ── Espace avant signature ────────────────────────────────────
    for _ in range(4):
        doc.add_paragraph()

    # ── Date et signature ─────────────────────────────────────────
    date_p = doc.add_paragraph(f"Paris, le {today}")
    date_p.runs[0].font.size = Pt(10)
    date_p.runs[0].font.name = "Arial"

    sig_p = doc.add_paragraph("Signature")
    sig_p.runs[0].bold = True
    sig_p.runs[0].font.size = Pt(10)
    sig_p.runs[0].font.name = "Arial"

    for _ in range(3):
        doc.add_paragraph()

    # Nom médecin bas de page (droite)
    doctor_p = doc.add_paragraph()
    doctor_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    dr = doctor_p.add_run(
        f"Docteur {kwargs['doctor_name'].replace('Dr. ','').replace('Dr ','')}\n"
        f"{kwargs['doctor_specialty']}"
    )
    dr.font.size = Pt(10)
    dr.font.name = "Arial"

    # ── Saut de page → Checklist ─────────────────────────────────
    doc.add_page_break()

    # ── Page 2 : Liste préparation préopératoire ──────────────────
    _add_header_p2(doc, **kwargs)

    checklist_title = doc.add_paragraph("Liste préparation préopératoire")
    checklist_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    ct_r = checklist_title.runs[0]
    ct_r.bold = True
    ct_r.font.size = Pt(11)
    ct_r.font.name = "Arial"

    doc.add_paragraph()

    checklist_items = [
        "J'ai un accompagnant pour rentrer à la maison et je ne suis pas seul(e) le soir.",
        "J'ai acheté les traitements prescrit par l'anesthésiste.",
        "J'ai acheté l'attelle et les bas de contention (s'ils m'ont été prescrit) et je viens avec.",
        "J'amène mes examens médicaux (IRM, radio, etc.)",
        "J'arrête de manger et de fumer à minuit la veille au soir de mon intervention",
        "J'ai le droit de boire de l'eau plate un thé ou un café sucré jusqu'à 2 heures avant l'heure "
        "de ma convocation à la clinique. (Pas de lait, pas de miel ou autre) En cas de non respect "
        "de ces consignes l'opération pourra être annulée.",
        "J'ai retiré les bijoux, piercing et le vernis à ongles (mains et pieds).",
    ]

    for item in checklist_items:
        # Tableau 2 colonnes : texte | case à cocher
        chk_table = doc.add_table(rows=1, cols=2)
        chk_table.style = "Table Grid"
        # Largeurs : texte large, case petite
        txt_cell = chk_table.rows[0].cells[0]
        box_cell = chk_table.rows[0].cells[1]

        _set_cell_width(txt_cell, 8500)
        _set_cell_width(box_cell, 700)

        # Supprimer les bordures sur la cellule texte
        _remove_borders(txt_cell)

        txt_p = txt_cell.paragraphs[0]
        txt_r = txt_p.add_run(item)
        txt_r.font.size = Pt(10)
        txt_r.font.name = "Arial"

        # Case à cocher (carré vide)
        box_p = box_cell.paragraphs[0]
        box_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        box_r = box_p.add_run("□")
        box_r.font.size = Pt(12)

        doc.add_paragraph()

    doc.add_paragraph()

    note_p = doc.add_paragraph(
        "En cas de question n'hésitez pas à contacter par mail les praticiens qui vous prennent en charge"
    )
    note_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    note_r = note_p.runs[0]
    note_r.italic = True
    note_r.font.size = Pt(9)
    note_r.font.name = "Arial"

    merci_p = doc.add_paragraph("Merci à vous")
    merci_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    merci_r = merci_p.runs[0]
    merci_r.bold = True
    merci_r.italic = True
    merci_r.font.size = Pt(11)
    merci_r.font.name = "Arial"

    doc.save(docx_path)
    logger.info(f"Docx généré : {docx_path}")


def _add_header_p2(doc, **kwargs):
    """Re-crée l'en-tête sur la page 2 (checklist)."""
    hdr_table = doc.add_table(rows=1, cols=3)
    hdr_table.style = "Table Grid"
    hdr_table.alignment = WD_TABLE_ALIGNMENT.CENTER

    col_widths = [3000, 5800, 3200]
    for i, cell in enumerate(hdr_table.rows[0].cells):
        _set_cell_width(cell, col_widths[i])

    cell_left = hdr_table.rows[0].cells[0]
    if LOGO_PATH.exists():
        p = cell_left.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        run.add_picture(str(LOGO_PATH), width=Cm(2.5))

    addr_p = cell_left.add_paragraph()
    addr_run = addr_p.add_run(
        f"{kwargs['clinic_address'].split(',')[0]}\n"
        f"{kwargs['clinic_address'].split(',')[1].strip()}\n"
        f"Tél : {kwargs['clinic_phone']}"
    )
    addr_run.font.size = Pt(7.5)
    addr_run.font.name = "Arial"

    cell_mid = hdr_table.rows[0].cells[1]
    _clear_cell(cell_mid)
    title_p = cell_mid.add_paragraph("ORDONNANCE DE SORTIE")
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_p.runs[0]
    title_run.bold = True
    title_run.font.size = Pt(12)
    title_run.font.name = "Arial"

    doc_p = cell_mid.add_paragraph(
        f"Docteur {kwargs['doctor_name'].replace('Dr. ','').replace('Dr ','')}"
    )
    doc_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc_p.runs[0].bold = True
    doc_p.runs[0].font.size = Pt(10)

    for txt in [kwargs["doctor_specialty"], kwargs["doctor_rpps"]]:
        p = cell_mid.add_paragraph(txt)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.size = Pt(8)

    cell_right = hdr_table.rows[0].cells[2]
    _clear_cell(cell_right)
    for label, code in [("Code FINESS", kwargs["clinic_finess"]),
                        ("Code RPPS", kwargs["clinic_rpps_code"])]:
        lp = cell_right.add_paragraph(label)
        lp.runs[0].font.size = Pt(7.5)
        cp = cell_right.add_paragraph(f"[ {code} ]")
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cp.runs[0].bold = True
        cp.runs[0].font.size = Pt(7)
        cp.runs[0].font.name = "Courier New"
        cell_right.add_paragraph()

    doc.add_paragraph()


def _convert_to_pdf(docx_path: str, output_dir: str, patient_name: str) -> str:
    """Convertit le .docx en PDF non-modifiable via LibreOffice headless."""
    safe_name = patient_name.upper().replace(" ", "_").replace("/", "-")
    today_str = date.today().strftime("%Y%m%d")
    pdf_name = f"Ordonnance_{safe_name}_{today_str}.pdf"
    pdf_output = os.path.join(output_dir, pdf_name)

    # Essayer LibreOffice
    for lo_cmd in ["libreoffice", "soffice", "/usr/bin/libreoffice", "/usr/bin/soffice"]:
        if shutil.which(lo_cmd):
            result = subprocess.run(
                [lo_cmd, "--headless", "--convert-to", "pdf",
                 "--outdir", str(output_dir), docx_path],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                # LibreOffice nomme le fichier d'après l'input
                generated = os.path.join(
                    output_dir,
                    os.path.basename(docx_path).replace(".docx", ".pdf")
                )
                if os.path.exists(generated):
                    os.rename(generated, pdf_output)
                logger.info(f"PDF généré via {lo_cmd} : {pdf_output}")
                return pdf_output
            else:
                logger.warning(f"{lo_cmd} erreur: {result.stderr}")

    raise RuntimeError(
        "LibreOffice non trouvé. Installez-le : apt install libreoffice "
        "ou brew install libreoffice"
    )


# ── Helpers XML ──────────────────────────────────────────────────

def _clear_cell(cell):
    """Vide tous les paragraphes d'une cellule sauf le premier."""
    for p in cell.paragraphs[1:]:
        p._element.getparent().remove(p._element)
    cell.paragraphs[0].clear()


def _set_cell_width(cell, width_dxa: int):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcW = OxmlElement("w:tcW")
    tcW.set(qn("w:w"), str(width_dxa))
    tcW.set(qn("w:type"), "dxa")
    tcPr.append(tcW)


def _remove_borders(cell):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for side in ["top", "left", "bottom", "right"]:
        border = OxmlElement(f"w:{side}")
        border.set(qn("w:val"), "none")
        tcBorders.append(border)
    tcPr.append(tcBorders)

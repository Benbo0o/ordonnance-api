"""
Module d'intégration avec la Base de Données Publique des Médicaments (BDPM)
API officielle : https://base-donnees-publique.medicaments.gouv.fr/
Documentation : https://base-donnees-publique.medicaments.gouv.fr/telechargement.php
"""
import requests
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

BDPM_BASE = "https://base-donnees-publique.medicaments.gouv.fr"


@dataclass
class Medicament:
    code_cis: str
    denomination: str
    forme_pharma: str
    voies_admin: str
    statut_amm: str
    etat_commercialisation: str
    substances: list[str]
    presentations: list[dict]


def search_medicaments(query: str, limit: int = 5) -> list[dict]:
    """
    Recherche dans la BDPM via l'API publique.
    
    L'API BDPM expose un endpoint de recherche par denomination.
    Retourne une liste de médicaments correspondant à la requête.
    """
    try:
        # Endpoint de recherche BDPM
        url = f"{BDPM_BASE}/api/v1/medicament"
        params = {
            "query": query,
            "limit": limit,
        }
        resp = requests.get(url, params=params, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            return _parse_results(data)
        
        # Fallback : recherche par nom dans les données téléchargeables
        logger.warning(f"API BDPM status {resp.status_code}, fallback texte")
        return search_by_name_fallback(query, limit)
        
    except requests.RequestException as e:
        logger.error(f"Erreur BDPM: {e}")
        return search_by_name_fallback(query, limit)


def search_by_name_fallback(query: str, limit: int = 5) -> list[dict]:
    """
    Fallback : recherche via l'API de recherche texte intégral BDPM.
    URL alternative documentée dans la BDPM.
    """
    try:
        url = f"{BDPM_BASE}/api/v1/medicament"
        resp = requests.get(
            url,
            params={"denomination": query.upper(), "limit": limit},
            timeout=10,
        )
        if resp.status_code == 200:
            return _parse_results(resp.json())
    except Exception as e:
        logger.error(f"Fallback BDPM échoué: {e}")
    
    return []


def get_medicament_detail(code_cis: str) -> Optional[dict]:
    """
    Récupère le détail d'un médicament par son code CIS.
    """
    try:
        url = f"{BDPM_BASE}/api/v1/medicament/{code_cis}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException as e:
        logger.error(f"Erreur détail médicament {code_cis}: {e}")
    return None


def get_compositions(code_cis: str) -> list[dict]:
    """
    Récupère les substances actives d'un médicament (composition).
    """
    try:
        url = f"{BDPM_BASE}/api/v1/medicament/{code_cis}/composition"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException as e:
        logger.error(f"Erreur composition {code_cis}: {e}")
    return []


def get_presentations(code_cis: str) -> list[dict]:
    """
    Récupère les présentations (boîtes, conditionnements) d'un médicament.
    """
    try:
        url = f"{BDPM_BASE}/api/v1/medicament/{code_cis}/presentation"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException as e:
        logger.error(f"Erreur presentations {code_cis}: {e}")
    return []


def _parse_results(data: dict | list) -> list[dict]:
    """Parse la réponse BDPM en liste standardisée."""
    results = data if isinstance(data, list) else data.get("results", [])
    parsed = []
    for item in results:
        parsed.append({
            "code_cis": item.get("codeCIS") or item.get("code_cis", ""),
            "denomination": item.get("denomination", ""),
            "forme_pharma": item.get("formePharmaceutique") or item.get("forme_pharma", ""),
            "voies_admin": item.get("voiesAdministration") or item.get("voies_admin", ""),
            "statut_amm": item.get("statutAMM") or item.get("statut_amm", ""),
            "etat_commercialisation": item.get("etatCommercialisation") or item.get("etat_commercialisation", ""),
        })
    return parsed

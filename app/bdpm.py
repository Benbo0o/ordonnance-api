import json
import os
import logging

logger = logging.getLogger(__name__)


def search_medicaments(query, limit=5):
    import anthropic
    key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not key:
        return []
    client = anthropic.Anthropic(api_key=key)
    try:
        prompt = 'Donne ' + str(limit) + ' medicaments BDPM pour ' + query
        prompt += '. JSON array strict, sans backticks: '
        prompt += '[{"denomination":"NOM","forme_pharma":"forme",'
        prompt += '"voies_admin":"orale","substance_active":"DCI",'
        prompt += '"statut_amm":"Autorisation active",'
        prompt += '"etat_commercialisation":"Commercialise",'
        prompt += '"code_cis":"12345678"}]'
        msg = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=1500,
            system='Expert pharmacologie francaise. JSON array uniquement.',
            messages=[{'role': 'user', 'content': prompt}],
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
                        result.append({'denomination': item,
                                       'forme_pharma': '',
                                       'voies_admin': 'orale',
                                       'substance_active': '',
                                       'statut_amm': 'Autorisation active',
                                       'etat_commercialisation': 'Commercialise',
                                       'code_cis': ''})
                return result[:limit]
    except Exception as e:
        logger.error('Erreur search: ' + str(e))
    return []


def get_medicament_detail(code_cis):
    return None

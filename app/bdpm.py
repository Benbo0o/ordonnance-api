import json
import os
import logging

logger = logging.getLogger(**name**)

def search_medicaments(query, limit=5):
import anthropic
key = os.environ.get(‘ANTHROPIC_API_KEY’, ‘’)
if not key:
return []
client = anthropic.Anthropic(api_key=key)
try:
system_msg = (’Tu es expert BDPM. ’
’Reponds UNIQUEMENT avec un JSON array valide. ’
’Pas de backticks. Pas de texte. ’
’Chaque element doit etre un objet avec ces cles exactes: ’
’denomination, forme_pharma, voies_admin, ’
’substance_active, statut_amm, ’
‘etat_commercialisation, code_cis.’)
user_msg = (’Medicament: ’ + str(query) + ’. ’
’Donne ’ + str(limit) + ’ resultats. ’
’Exemple de format attendu: ’
‘[{"denomination": "DOLIPRANE 1000 mg comprime", ’
‘"forme_pharma": "comprime", ’
‘"voies_admin": "orale", ’
‘"substance_active": "Paracetamol", ’
‘"statut_amm": "Autorisation active", ’
‘"etat_commercialisation": "Commercialise", ’
‘"code_cis": "60001393"}]’)
msg = client.messages.create(
model=‘claude-sonnet-4-6’,
max_tokens=2000,
system=system_msg,
messages=[{‘role’: ‘user’, ‘content’: user_msg}],
)
raw = msg.content[0].text.strip()
raw = raw.replace(’`json', '').replace('`’, ‘’).strip()
start = raw.find(’[’)
end = raw.rfind(’]’) + 1
if start >= 0 and end > start:
parsed = json.loads(raw[start:end])
if isinstance(parsed, list):
result = []
for item in parsed:
if isinstance(item, dict):
result.append(item)
elif isinstance(item, str):
result.append({
‘denomination’: item,
‘forme_pharma’: ‘’,
‘voies_admin’: ‘orale’,
‘substance_active’: ‘’,
‘statut_amm’: ‘Autorisation active’,
‘etat_commercialisation’: ‘Commercialise’,
‘code_cis’: ‘’
})
return result[:limit]
except Exception as e:
logger.error(’Erreur: ’ + str(e))
return []

def get_medicament_detail(code_cis):
return None

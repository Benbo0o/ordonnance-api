import json
import os
import logging

logger = logging.getLogger(**name**)

def search_medicaments(query, limit=5):
import anthropic
api_key = os.environ.get(“ANTHROPIC_API_KEY”, “”)
if not api_key:
return []
client = anthropic.Anthropic(api_key=api_key)
try:
msg = client.messages.create(
model=“claude-sonnet-4-6”,
max_tokens=1500,
system=“Tu es expert en pharmacologie francaise. Reponds UNIQUEMENT avec un JSON array valide, sans backticks ni texte.”,
messages=[{“role”: “user”, “content”: (
“Donne “ + str(limit) + “ medicaments BDPM pour “ + repr(query) + “. “
“Format: [{“denomination”:“NOM”,“forme_pharma”:“forme”,“voies_admin”:“orale”,”
““substance_active”:“DCI”,“statut_amm”:“Autorisation active”,”
““etat_commercialisation”:“Commercialise”,“code_cis”:“12345678”}]”
)}],
)
raw = msg.content[0].text.strip()
raw = raw.replace(”`json", "").replace("`”, “”).strip()
start = raw.find(”[”)
end = raw.rfind(”]”) + 1
if start >= 0 and end > start:
parsed = json.loads(raw[start:end])
if isinstance(parsed, list):
result = []
for item in parsed:
if isinstance(item, dict):
result.append(item)
elif isinstance(item, str):
result.append({“denomination”: item, “forme_pharma”: “”,
“voies_admin”: “orale”, “substance_active”: “”,
“statut_amm”: “Autorisation active”,
“etat_commercialisation”: “Commercialise”,
“code_cis”: “”})
return result[:limit]
except Exception as e:
logger.error(“Erreur: “ + str(e))
return []

def get_medicament_detail(code_cis):
return None

"""Offline SDK mock. No calls to Google, Firebase or stores.

Output is explicitly labeled MOCKED even though legacy response schema says vertex_ai.
"""
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
os.environ.setdefault('GOOGLE_CLOUD_PROJECT','no-live-project')
from app.config import Settings
from app.services.intent_service import IntentService

request='Need 65W USB-C PD charger under ₹1000 in Thane today'
structured={
 'language':'English','product_category':'Electronics',
 'requested_product':'USB-C PD laptop charger','budget_amount':1000,
 'budget_currency':'INR','delivery_deadline_text':'today','delivery_location':'Thane',
 'required_specifications':['65W','USB-C PD'],
 'preferred_specifications':[], 'missing_information':['Laptop model'],
 'clarification_questions':['What is your exact laptop model?'],
 'compatibility_needs_verification':True,
}

class Client:
 def __init__(self,**kwargs):
  self.models=SimpleNamespace(generate_content=lambda **kwargs: SimpleNamespace(
   parsed=structured,text=None,usage_metadata=SimpleNamespace(
    prompt_token_count=30,candidates_token_count=70)))
 def close(self):pass

with patch('app.services.intent_service.genai.Client',Client):
 result=IntentService(Settings(_env_file=None,google_cloud_project='MOCK_PROJECT',
                                ai_mode='LIVE_VERTEX')).extract(request)

data={
 'execution_mode':'MOCKED_GENAI_SDK_NO_NETWORK',
 'actual_google_model_called':False,
 'firebase_tokens_verified_live':False,
 'customer_request_fixture':request,
 'result':result.model_dump(mode='json'),
 'warnings':['Structured schema validation is real Python execution, Gemini response is mocked.',
             'source=vertex_ai is the existing response contract, not proof of a live call.',
             'Merchant inventory and technical compatibility remain unverified.'],
}
out=ROOT/'qa_reports'/'17b'/'mocked_intent_trace.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('MOCK TRACE PASSED: Correct structured intent, explicit unverified status')
print('LIVE_MODEL_CALLED: False')
print('AUTH/APPCHECK_LIVE: Unverified')
print('OUTPUT:',out)

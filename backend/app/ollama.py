"""Ollama local HTTP adapter. Never falls back to a paid or remote model."""
import httpx
from fastapi import HTTPException
from . import config

def generate(prompt, system, temperature=0.1):
    try:
        with httpx.Client(timeout=httpx.Timeout(180.0, connect=4.0)) as client:
            response=client.post(f'{config.OLLAMA_URL}/api/chat',json={
                'model':config.OLLAMA_MODEL,'stream':False,
                'options':{'temperature':temperature,'num_predict':950},
                'messages':[{'role':'system','content':system},{'role':'user','content':prompt}]})
        if response.status_code==404:
            raise HTTPException(503, f'Ollama model {config.OLLAMA_MODEL!r} not found. Run: ollama pull {config.OLLAMA_MODEL}')
        response.raise_for_status()
        return response.json().get('message',{}).get('content','').strip()
    except httpx.ConnectError:
        raise HTTPException(503,f'Local Ollama unavailable at {config.OLLAMA_URL}. Start Ollama first.')
    except httpx.TimeoutException:
        raise HTTPException(504,'Ollama timed out. Try a shorter question or smaller configured model.')
    except httpx.HTTPStatusError as exc:
        raise HTTPException(503, f'Ollama failed (HTTP {exc.response.status_code}). Verify the model is installed and RAM is sufficient.')

def status():
    try:
        with httpx.Client(timeout=3.0) as client:
            r=client.get(f'{config.OLLAMA_URL}/api/tags')
            r.raise_for_status()
        names=[m.get('name','') for m in r.json().get('models',[])]
        return {'available':True,'model':config.OLLAMA_MODEL,'model_installed':config.OLLAMA_MODEL in names,'installed_models':names}
    except Exception:
        return {'available':False,'model':config.OLLAMA_MODEL,'model_installed':False}

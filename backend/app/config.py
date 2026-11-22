"""Local-only configuration. No relational application data stores."""
import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / '.env')
DATA_DIR = Path(os.getenv('BANK_DATA_DIR', str(BASE_DIR / 'data'))).resolve()
DOC_DIR = DATA_DIR / 'documents'
REPORT_DIR = DATA_DIR / 'reports'
VECTOR_DIR = DATA_DIR / 'vectors'
for folder in (DATA_DIR, DOC_DIR, REPORT_DIR, VECTOR_DIR):
    folder.mkdir(parents=True, exist_ok=True)
SECRET_PATH = DATA_DIR / 'jwt.secret'
if os.getenv('JWT_SECRET_KEY'):
    JWT_SECRET = os.environ['JWT_SECRET_KEY']
elif SECRET_PATH.exists():
    JWT_SECRET = SECRET_PATH.read_text(encoding='utf8').strip()
else:
    JWT_SECRET = secrets.token_urlsafe(48)
    SECRET_PATH.write_text(JWT_SECRET, encoding='utf8')
    try: SECRET_PATH.chmod(0o600)
    except OSError: pass
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.1:8b')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-small-en-v1.5')
RERANK_MODEL = os.getenv('RERANK_MODEL', 'cross-encoder/ms-marco-MiniLM-L-6-v2')
MAX_UPLOAD_MB = int(os.getenv('MAX_UPLOAD_MB', '20'))
CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '550'))
CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', '90'))
RETRIEVAL_TOP_K = int(os.getenv('RETRIEVAL_TOP_K', '8'))
RERANK_TOP_K = int(os.getenv('RERANK_TOP_K', '5'))
FRONTEND_ORIGIN = os.getenv('FRONTEND_ORIGIN', 'http://localhost:5173')
DEMO_PASSWORD = os.getenv('DEMO_PASSWORD', 'Demo@12345')

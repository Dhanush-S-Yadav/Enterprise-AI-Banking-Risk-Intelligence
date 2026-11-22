"""Atomic JSON-file persistence, guarded by a process lock."""
import json
import os
import tempfile
import threading
from pathlib import Path
from datetime import datetime, timezone
from . import config

_LOCK = threading.RLock()
def now(): return datetime.now(timezone.utc).isoformat()
def path(name):
    if '/' in name or '\\' in name or not name.endswith('.json'):
        raise ValueError('Invalid JSON store')
    return config.DATA_DIR / name

def read(name, default=None):
    target = path(name)
    with _LOCK:
        if not target.exists(): return [] if default is None else default
        with target.open('r', encoding='utf8') as f: return json.load(f)

def write(name, value):
    target = path(name)
    with _LOCK:
        fd, temp = tempfile.mkstemp(dir=config.DATA_DIR, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf8') as f:
                json.dump(value, f, ensure_ascii=False, indent=2, default=str)
            os.replace(temp, target)
        finally:
            if os.path.exists(temp): os.unlink(temp)
    return value

def append(name, value):
    with _LOCK:
        current = read(name, [])
        current.append(value)
        write(name, current)
    return value

def audit(action, user=None, status='success', **fields):
    record = {'timestamp': now(), 'action':action,'user_id':user.get('id') if user else None,
              'role':user.get('role') if user else None,'status':status}
    safe = {k: v for k,v in fields.items() if k not in {'password','token','authorization','secret','jwt'}}
    record.update(safe)
    append('audit.json', record)
    return record

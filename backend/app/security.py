"""JWT and Argon2 auth with backend-enforced role permissions."""
import uuid
from datetime import datetime, timezone, timedelta
import jwt
from argon2 import PasswordHasher, exceptions as argon_exceptions
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from . import storage, config

ROLES = ['Customer Service Executive','Loan Officer','Compliance Officer','Risk Analyst',
         'Branch Manager','Auditor','Administrator']
_ROLE_ACTIONS = {
    'Customer Service Executive': {'chat','search','read_docs','reports_read'},
    'Loan Officer': {'chat','search','read_docs','upload','reports_read','report'},
    'Compliance Officer': {'chat','search','read_docs','upload','delete_docs','compliance','compare','reports_read','report'},
    'Risk Analyst': {'chat','search','read_docs','upload','fraud','compare','reports_read','report'},
    'Branch Manager': {'chat','search','read_docs','upload','compliance','fraud','compare','reports_read','report'},
    'Auditor': {'chat','search','read_docs','compliance','compare','reports_read','report'},
    'Administrator': {'*'},
}
PASSWORD_HASHER = PasswordHasher()
bearer = HTTPBearer(auto_error=False)

def public_user(user): return {k: v for k,v in user.items() if k != 'password_hash'}

def seed_users():
    if storage.read('users.json', []): return
    slugs = ['service','loan','compliance','risk','manager','auditor','admin']
    users = []
    for role,slug in zip(ROLES,slugs):
        users.append({'id':str(uuid.uuid4()),'username':slug,
                      'email':f'{slug}@demo.bank.local','role':role,
                      'password_hash':PASSWORD_HASHER.hash(config.DEMO_PASSWORD),
                      'created_at':storage.now(),'is_active':True})
    storage.write('users.json',users)

def find_user(login):
    return next((u for u in storage.read('users.json', [])
                 if u['username'].lower()==login.lower() or u['email'].lower()==login.lower()),None)

def authenticate(login,password):
    u=find_user(login)
    if not u or not u.get('is_active'): return None
    try: PASSWORD_HASHER.verify(u['password_hash'],password)
    except (argon_exceptions.VerifyMismatchError,argon_exceptions.VerificationError,argon_exceptions.InvalidHashError): return None
    return u

def create_token(user):
    payload={'sub':user['id'],'role':user['role'],'exp':datetime.now(timezone.utc)+timedelta(hours=8)}
    return jwt.encode(payload,config.JWT_SECRET,algorithm='HS256')

def current_user(credentials: HTTPAuthorizationCredentials | None=Depends(bearer)):
    if not credentials: raise HTTPException(status.HTTP_401_UNAUTHORIZED,'Authentication required')
    try: payload=jwt.decode(credentials.credentials,config.JWT_SECRET,algorithms=['HS256'])
    except jwt.PyJWTError: raise HTTPException(401,'Invalid or expired token')
    user=next((u for u in storage.read('users.json', []) if u['id']==payload.get('sub')),None)
    if not user or not user.get('is_active'): raise HTTPException(401,'Account unavailable')
    return user

def permit(action):
    def dependency(user=Depends(current_user)):
        allowed=_ROLE_ACTIONS.get(user['role'],set())
        if '*' not in allowed and action not in allowed:
            raise HTTPException(403,f'{user["role"]} cannot perform this action')
        return user
    return dependency

def can(user, action):
    allowed=_ROLE_ACTIONS.get(user['role'],set())
    return '*' in allowed or action in allowed

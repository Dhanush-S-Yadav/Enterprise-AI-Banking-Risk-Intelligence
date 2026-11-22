"""Enterprise AI Banking Knowledge & Risk Intelligence Assistant - local FastAPI."""
import hashlib
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from . import config, storage, security, ingestion, retrieval, agents, ollama, reports
from .schemas import (Login,Register,ChatRequest,SearchRequest,ReindexRequest,
                      CompareRequest,AnalysisRequest,ReportRequest,Feedback,LoginResponse,SearchResponse,AgentResponse,ChatResponse,UserResponse,UserAdminUpdate)

@asynccontextmanager
async def lifespan(app):
    security.seed_users()
    if not (config.DATA_DIR/'settings.json').exists():
        storage.write('settings.json',{'local_only':True,'llm_provider':'ollama',
            'llm_model':config.OLLAMA_MODEL,'embedding_model':config.EMBEDDING_MODEL,
            'reranking_model':config.RERANK_MODEL,'chunk_size':config.CHUNK_SIZE,
            'chunk_overlap':config.CHUNK_OVERLAP,'retrieval_top_k':config.RETRIEVAL_TOP_K,
            'rerank_top_k':config.RERANK_TOP_K})
    yield

app=FastAPI(title='Enterprise AI Banking Knowledge & Risk Intelligence Assistant',
            version='1.0.0',description='Local, evidence-grounded RAG and five LangGraph banking agents.',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=[config.FRONTEND_ORIGIN,'http://127.0.0.1:5173'],
                   allow_credentials=True,allow_methods=['*'],allow_headers=['*'])

@app.get('/api/health')
def health():
    return {'status':'ok','app_storage':'local JSON + ChromaDB','llm':ollama.status(),
            'embedding_model':config.EMBEDDING_MODEL,'demo_data':'synthetic','version':'1.0.0'}

@app.post('/api/auth/login',response_model=LoginResponse)
def login(body:Login):
    user=security.authenticate(body.username,body.password)
    if not user:
        storage.audit('login_failure',None,'failed',login_sha256=hashlib.sha256(body.username.encode()).hexdigest()[:12])
        raise HTTPException(401,'Invalid credentials')
    storage.audit('login_success',user)
    return {'access_token':security.create_token(user),'token_type':'bearer','user':security.public_user(user)}

@app.post('/api/auth/register',status_code=201)
def register(body:Register):
    users=storage.read('users.json',[])
    if any(u['username'].lower()==body.username.lower() or u['email'].lower()==body.email.lower() for u in users):
        raise HTTPException(409,'Username or email already exists')
    if '@' not in body.email or '.' not in body.email.split('@')[-1]:raise HTTPException(422,'Invalid email')
    user={'id':str(uuid.uuid4()),'username':body.username,'email':body.email,
          'role':'Customer Service Executive','password_hash':security.PASSWORD_HASHER.hash(body.password),
          'created_at':storage.now(),'is_active':True}
    users.append(user);storage.write('users.json',users)
    storage.audit('user_register',user)
    return {'user':security.public_user(user)}

@app.get('/api/auth/me',response_model=UserResponse)
def me(user=Depends(security.current_user)):
    return {'user':security.public_user(user),
            'permissions':[a for a in ['chat','search','read_docs','upload','delete_docs','compare','compliance','fraud','report','reports_read'] if security.can(user,a)]}

@app.post('/api/documents/upload')
async def upload(files:list[UploadFile]=File(...),user=Depends(security.permit('upload'))):
    if not files or len(files)>30:raise HTTPException(400,'Upload between 1 and 30 files at a time')
    result=[]
    for file in files:
        data=await file.read(config.MAX_UPLOAD_MB*1024*1024+1)
        try:
            record=ingestion.ingest(file.filename or 'upload.txt',data,user)
            storage.audit('document_upload',user,document_id=record['id'],status=record['status'])
            result.append({'filename':file.filename,'document':record})
        except HTTPException as exc:result.append({'filename':file.filename,'error':exc.detail,'status_code':exc.status_code})
        finally:await file.close()
    if not any('document' in x for x in result):
        raise HTTPException(400,{'message':'All uploads rejected','results':result})
    return {'results':result}

@app.post('/api/documents/seed-demo')
def seed_demo(user=Depends(security.permit('upload'))):
    sample_dir=config.BASE_DIR/'sample_documents'
    imported=[]; skipped=[]
    for path in sorted(sample_dir.glob('*.txt')):
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if any(d['sha256']==digest for d in storage.read('documents.json',[])):
            skipped.append(path.name);continue
        imported.append(ingestion.ingest(path.name,path.read_bytes(),user))
    return {'imported':len(imported),'indexed':sum(d['status']=='Indexed' for d in imported),
            'failed':[{'name':d['name'],'error':d['error']} for d in imported if d['status']=='Failed'],
            'skipped':len(skipped)}

@app.get('/api/documents')
def documents(user=Depends(security.permit('read_docs'))):
    return sorted(storage.read('documents.json',[]),key=lambda d:d['uploaded_at'],reverse=True)

@app.get('/api/documents/{document_id}')
def document_detail(document_id:str,user=Depends(security.permit('read_docs'))):
    doc=next((d for d in storage.read('documents.json',[]) if d['id']==document_id),None)
    if not doc: raise HTTPException(404,'Document not found')
    chunks=[c for c in storage.read('chunks.json',[]) if c['document_id']==document_id]
    return {**doc,'sample_chunks':chunks[:3]}

@app.delete('/api/documents/{document_id}')
def delete_doc(document_id:str,user=Depends(security.permit('delete_docs'))):
    return ingestion.remove(document_id,user)

@app.post('/api/documents/reindex')
def reindex(body:ReindexRequest,user=Depends(security.permit('upload'))):
    return ingestion.reindex(body.document_id,user)

@app.post('/api/search',response_model=SearchResponse)
def search(body:SearchRequest,user=Depends(security.permit('search'))):
    start=perf_counter()
    try: results=retrieval.retrieve(body.query,body.filters,body.top_k)
    except Exception as exc:raise HTTPException(503,f'Search index unavailable: {type(exc).__name__}: {str(exc)[:180]}')
    storage.audit('search',user,result_count=len(results),latency_ms=round((perf_counter()-start)*1000))
    return {'query':body.query,'results':results,'count':len(results),'queries':retrieval.expand_queries(body.query)}

@app.get('/api/search/filters')
def filters(user=Depends(security.permit('search'))):
    docs=storage.read('documents.json',[])
    return {'categories':sorted(set(d.get('category','Uncategorized') for d in docs)),
            'versions':sorted(set(d['document_version'] for d in docs if d.get('document_version'))),
            'documents':[{'id':d['id'],'name':d['name']} for d in docs if d['status']=='Indexed']}

def agent_job(question,mode,filters,user,history=None):
    start=perf_counter()
    chosen=agents.choose_agent(question,mode)
    if chosen!='rag' and not security.can(user,chosen):
        raise HTTPException(403,f'{user["role"]} cannot use the {chosen} agent')
    try: result=agents.run(question,chosen,filters,history)
    except HTTPException as exc:
        storage.audit('agent_query',user,'failed',agent=chosen,error_status=exc.status_code,latency_ms=round((perf_counter()-start)*1000))
        raise
    except Exception as exc:
        storage.audit('agent_query',user,'failed',agent=chosen,error_type=type(exc).__name__,latency_ms=round((perf_counter()-start)*1000))
        raise HTTPException(503,f'AI agent unavailable: {type(exc).__name__}: {str(exc)[:200]}')
    result['latency_ms']=round((perf_counter()-start)*1000)
    storage.audit('agent_query',user,agent=result['agent'],query_sha256=hashlib.sha256(question.encode()).hexdigest()[:20],query_length=len(question),
                  retrieved_document_ids=list(dict.fromkeys(c['document_id'] for c in result['citations'])),
                  latency_ms=result['latency_ms'])
    return result

@app.post('/api/chat',response_model=ChatResponse)
def chat(body:ChatRequest,user=Depends(security.permit('chat'))):
    conversations=storage.read('conversations.json',[])
    cid=body.conversation_id or str(uuid.uuid4())
    history=[{'role':'user','content':r['question']} for r in conversations if r.get('conversation_id')==cid and r.get('user_id')==user['id']][-6:]
    result=agent_job(body.message,body.agent,body.filters,user,history)
    row={'id':str(uuid.uuid4()),'conversation_id':cid,'user_id':user['id'],
         'question':body.message,'answer':result['answer'],'agent':result['agent'],
         'citations':result['citations'],'created_at':storage.now()}
    storage.append('conversations.json',row)
    return {**result,'conversation_id':cid,'message_id':row['id'],'created_at':row['created_at']}

@app.get('/api/chat/history')
def chat_history(user=Depends(security.permit('chat'))):
    return [c for c in storage.read('conversations.json',[]) if c['user_id']==user['id']][-100:]

@app.delete('/api/chat/history')
def clear_history(user=Depends(security.permit('chat'))):
    previous=storage.read('conversations.json',[])
    removed=sum(c['user_id']==user['id'] for c in previous)
    storage.write('conversations.json',[c for c in previous if c['user_id']!=user['id']])
    storage.audit('clear_chat',user,deleted_count=removed)
    return {'deleted':removed}

@app.post('/api/agents/route',response_model=AgentResponse)
def route(body:ChatRequest,user=Depends(security.permit('chat'))):
    selected=agents.choose_agent(body.message,body.agent)
    if not security.can(user,selected if selected!='rag' else 'chat'):
        raise HTTPException(403,'Agent unavailable for this role')
    return agent_job(body.message,selected,body.filters,user)

@app.post('/api/agents/compare-policies')
def compare(body:CompareRequest,user=Depends(security.permit('compare'))):
    result=agents.compare_docs(body.document_id_a,body.document_id_b)
    storage.audit('policy_comparison',user,document_ids=[body.document_id_a,body.document_id_b])
    return result

@app.post('/api/agents/compliance-checklist',response_model=AgentResponse)
def compliance(body:AnalysisRequest,user=Depends(security.permit('compliance'))):
    return agent_job(body.question,'compliance',{'document_id':body.document_id} if body.document_id else None,user)

@app.post('/api/agents/fraud-summary',response_model=AgentResponse)
def fraud(body:AnalysisRequest,user=Depends(security.permit('fraud'))):
    return agent_job(body.question,'fraud',{'document_id':body.document_id} if body.document_id else None,user)

@app.post('/api/reports/generate')
def report_generate(body:ReportRequest,user=Depends(security.permit('report'))):
    result=agent_job(body.question,'report',None,user)
    meta=reports.create_pdf(body.title,body.category,result['answer'],result['citations'],user)
    return {'report':meta,'analysis':result['answer'],'citations':result['citations']}

@app.get('/api/reports')
def report_list(user=Depends(security.permit('reports_read'))):
    return [r for r in storage.read('reports.json',[]) if user['role']=='Administrator' or r['created_by']==user['id']]

@app.get('/api/reports/{report_id}/download')
def report_download(report_id:str,user=Depends(security.permit('reports_read'))):
    r=next((r for r in storage.read('reports.json',[]) if r['id']==report_id),None)
    if not r:raise HTTPException(404,'Report not found')
    if user['role']!='Administrator' and r['created_by']!=user['id']:raise HTTPException(403,'Report access denied')
    path=config.REPORT_DIR / f'{r["id"]}.pdf'
    if not path.exists():raise HTTPException(404,'Report file missing')
    return FileResponse(path,media_type='application/pdf',filename=f'{r["title"][:55].replace(" ","_")}.pdf')

@app.post('/api/feedback')
def feedback(body:Feedback,user=Depends(security.permit('chat'))):
    if not any(c['conversation_id']==body.conversation_id and c['user_id']==user['id']
               for c in storage.read('conversations.json',[])):
        raise HTTPException(404,'Conversation not found')
    row={'id':str(uuid.uuid4()),'user_id':user['id'],'created_at':storage.now(),**body.model_dump()}
    storage.append('feedback.json',row)
    storage.audit('feedback',user,conversation_id=body.conversation_id,rating=body.rating)
    return {'saved':True,'id':row['id']}

def overview(user):
    docs=storage.read('documents.json',[])
    conversations=storage.read('conversations.json',[])
    reports_list=storage.read('reports.json',[])
    audits=storage.read('audit.json',[])
    ownconv=[c for c in conversations if user['role']=='Administrator' or c['user_id']==user['id']]
    ownreports=[r for r in reports_list if user['role']=='Administrator' or r['created_by']==user['id']]
    return {'total_documents':len(docs),'indexed_documents':sum(d['status']=='Indexed' for d in docs),
            'total_conversations':len(ownconv),'available_agents':len(agents.AGENT_NAMES),
            'total_reports':len(ownreports),
            'categories':dict(Counter(d.get('category','Uncategorized') for d in docs)),
            'indexing_status':dict(Counter(d['status'] for d in docs)),
            'agent_usage':dict(Counter(c['agent'] for c in ownconv)),
            'recent_documents':sorted(docs,key=lambda d:d['uploaded_at'],reverse=True)[:6],
            'recent_ai_activity':ownconv[-6:][::-1],
            'recent_audit':audits[-10:][::-1] if user['role']=='Administrator' else []}

@app.get('/api/dashboard')
def dashboard(user=Depends(security.current_user)):
    return overview(user)

@app.get('/api/admin/dashboard')
def admin_dashboard(user=Depends(security.permit('*'))):
    return {**overview(user),'total_users':len(storage.read('users.json',[])), 'health':health()}

@app.get('/api/admin/users')
def admin_users(user=Depends(security.permit('*'))):
    return [security.public_user(u) for u in storage.read('users.json',[])]

@app.get('/api/admin/audit-logs')
def admin_audit(user=Depends(security.permit('*'))):
    return storage.read('audit.json',[])[-250:][::-1]

@app.patch('/api/admin/users/{user_id}')
def update_user(user_id:str,body:UserAdminUpdate,user=Depends(security.permit('*'))):
    users=storage.read('users.json',[])
    target=next((u for u in users if u['id']==user_id),None)
    if not target: raise HTTPException(404,'User not found')
    if body.role is None and body.is_active is None:raise HTTPException(400,'Supply a role or active state')
    if body.role is not None and body.role not in security.ROLES: raise HTTPException(422,'Unknown role')
    if user_id==user['id'] and ((body.role is not None and body.role!='Administrator') or body.is_active is False):
        raise HTTPException(400,'Administrators cannot demote or disable themselves')
    new_role=body.role if body.role is not None else target['role']
    new_active=body.is_active if body.is_active is not None else target['is_active']
    if target['role']=='Administrator' and (new_role!='Administrator' or not new_active):
        remaining=sum(u['id']!=user_id and u['role']=='Administrator' and u.get('is_active') for u in users)
        if remaining==0:raise HTTPException(400,'Cannot remove the last active administrator')
    if body.role is not None:target['role']=body.role
    if body.is_active is not None:target['is_active']=body.is_active
    storage.write('users.json',users)
    storage.audit('admin_user_update',user,target_user_id=user_id,new_role=target['role'],is_active=target['is_active'])
    return security.public_user(target)

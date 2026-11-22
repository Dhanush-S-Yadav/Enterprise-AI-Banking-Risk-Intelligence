"""Local document extraction with traceable, uninvented metadata."""
import csv
import hashlib
import io
import re
import uuid
from pathlib import Path
from fastapi import HTTPException
from langchain_text_splitters import RecursiveCharacterTextSplitter
from . import config, storage

EXTENSIONS={'.pdf','.docx','.txt','.csv','.xlsx','.xls'}
def safe_name(filename):
    name=Path(filename.replace('\\','/')).name
    return re.sub(r'[^A-Za-z0-9_. -]','_',name)[:130] or 'document.txt'

def normalize(text):
    return re.sub(r'\s+', ' ', str(text)).strip()

def extract(path):
    ext=path.suffix.lower()
    pages=[]
    if ext=='.pdf':
        import fitz
        with fitz.open(path) as doc:
            for index, page in enumerate(doc,1):
                content=page.get_text(sort=True)
                if content.strip(): pages.append({'text':content,'page':index})
    elif ext=='.docx':
        from docx import Document
        doc=Document(str(path))
        body=[]
        for p in doc.paragraphs:
            if p.text.strip(): body.append(p.text)
        for table in doc.tables:
            for row in table.rows:
                body.append(' | '.join(cell.text for cell in row.cells))
        pages=[{'text':'\n'.join(body),'page':None}]
    elif ext=='.txt':
        pages=[{'text':path.read_text(encoding='utf-8-sig',errors='replace'),'page':None}]
    elif ext=='.csv':
        with path.open(encoding='utf-8-sig',errors='replace',newline='') as f:
            rows=list(csv.reader(f))
        text='\n'.join(' | '.join(f'{rows[0][i]}: {value}' for i,value in enumerate(row) if i<len(rows[0]))
                       for row in rows[1:]) if rows else ''
        pages=[{'text':text,'page':None}]
    elif ext=='.xlsx':
        from openpyxl import load_workbook
        wb=load_workbook(path,read_only=True,data_only=True)
        for sh in wb:
            lines=[f'Sheet: {sh.title}']
            for row in sh.iter_rows(values_only=True):
                vals=[str(c) if c is not None else '' for c in row]
                if any(vals): lines.append(' | '.join(vals))
            pages.append({'text':'\n'.join(lines),'page':None,'section':sh.title})
        wb.close()
    elif ext=='.xls':
        import xlrd
        wb=xlrd.open_workbook(str(path))
        for sh in wb.sheets():
            lines=[f'Sheet: {sh.name}']
            for i in range(sh.nrows):
                vals=[str(v) for v in sh.row_values(i)]
                if any(vals): lines.append(' | '.join(vals))
            pages.append({'text':'\n'.join(lines),'page':None,'section':sh.name})
    else: raise HTTPException(400,'Unsupported file type')
    pages=[p for p in pages if p['text'].strip()]
    if not pages: raise ValueError('No extractable text found. Scanned PDFs require OCR and are not supported.')
    return pages

def extract_metadata(pages, name):
    excerpt='\n'.join(p['text'] for p in pages)[:5000]
    def match(pattern):
        m=re.search(pattern,excerpt,re.I|re.M)
        return m.group(1).strip() if m else None
    version=match(r'^\s*(?:Document\s+)?Version\s*:\s*([^\n]+)') or match(r'\b\b(v\d+(?:\.\d+)?)\b')
    date=match(r'^\s*Effective\s+Date\s*:\s*([^\n]+)')
    policy=match(r'^\s*Policy\s+(?:ID|Number|No\.?|Code)\s*:\s*([^\n]+)')
    cat=match(r'^\s*Category\s*:\s*([^\n]+)')
    title=match(r'^\s*Title\s*:\s*([^\n]+)') or name.rsplit('.',1)[0]
    return {'document_version':version,'effective_date':date,'policy_number':policy,
            'category':cat or 'Uncategorized','title':title}

def make_chunks(doc_id, name, segments, metadata):
    parent_splitter=RecursiveCharacterTextSplitter(chunk_size=max(config.CHUNK_SIZE*3,900),chunk_overlap=100)
    child_splitter=RecursiveCharacterTextSplitter(chunk_size=config.CHUNK_SIZE,chunk_overlap=config.CHUNK_OVERLAP)
    children=[]; parents={}
    for segment in segments:
        heading=segment.get('section')
        current_heading=heading
        # Look for section headings; keep best-effort section context per segment.
        for line in segment['text'].splitlines():
            if re.match(r'^(?:\d+(?:\.\d+)*[.)]?\s+)?(?:[A-Z][A-Za-z /&-]{2,70}):?\s*$',line.strip()):
                current_heading=line.strip()[:90]
                break
        for ptext in parent_splitter.split_text(segment['text']):
            pid=str(uuid.uuid4())
            parents[pid]={'text':ptext,'page':segment.get('page'), 'section':current_heading}
            for ctext in child_splitter.split_text(ptext):
                cid=str(uuid.uuid4())
                children.append({'chunk_id':cid,'parent_chunk_id':pid,'document_id':doc_id,
                                 'document_name':name,'text':ctext,'page':segment.get('page'),
                                 'section':current_heading,'heading':current_heading,
                                 'policy_number':metadata.get('policy_number'),
                                 'document_version':metadata.get('document_version'),
                                 'effective_date':metadata.get('effective_date'),
                                 'category':metadata.get('category')})
    return children,parents

def index_file(path, doc):
    """Replace vector and JSON index entries for one document."""
    from . import retrieval
    pages=extract(path)
    meta=extract_metadata(pages,doc['name'])
    chunks,parents=make_chunks(doc['id'],doc['name'],pages,meta)
    if not chunks: raise ValueError('No chunks were extracted')
    retrieval.replace_document(doc['id'],chunks,parents)
    return {'pages':len(pages),'chunks':len(chunks),**meta}

def ingest(filename,data,user=None):
    name=safe_name(filename)
    ext=Path(name).suffix.lower()
    if ext not in EXTENSIONS: raise HTTPException(400,'Supported formats: PDF, DOCX, TXT, CSV, XLSX, XLS')
    if not data: raise HTTPException(400,'Empty file')
    if len(data)>config.MAX_UPLOAD_MB*1024*1024: raise HTTPException(413,f'Maximum file size is {config.MAX_UPLOAD_MB} MB')
    digest=hashlib.sha256(data).hexdigest()
    if any(d['sha256']==digest for d in storage.read('documents.json',[])):
        raise HTTPException(409,'This exact document has already been uploaded')
    doc_id=str(uuid.uuid4())
    filepath=config.DOC_DIR / f'{doc_id}{ext}'
    filepath.write_bytes(data)
    record={'id':doc_id,'name':name,'status':'Uploaded','sha256':digest,
            'size_bytes':len(data),'uploaded_at':storage.now(),'uploaded_by':user['id'] if user else None,
            'file_ext':ext,'category':'Uncategorized','document_version':None,
            'effective_date':None,'policy_number':None,'chunk_count':0,'error':None}
    docs=storage.read('documents.json',[]); docs.append(record); storage.write('documents.json',docs)
    return reindex(doc_id,user)

def reindex(doc_id,user=None):
    docs=storage.read('documents.json',[])
    doc=next((d for d in docs if d['id']==doc_id),None)
    if not doc: raise HTTPException(404,'Document not found')
    doc['status']='Processing'; doc['error']=None; storage.write('documents.json',docs)
    file=config.DOC_DIR / (doc_id+doc['file_ext'])
    try:
        meta=index_file(file,doc)
        doc.update({'status':'Indexed','indexed_at':storage.now(),'chunk_count':meta.pop('chunks'),
                    'page_count':meta.pop('pages'),**meta})
        storage.audit('document_index',user,document_id=doc_id,chunk_count=doc['chunk_count'])
    except Exception as exc:
        doc['status']='Failed'; doc['error']=str(exc)[:350]
        storage.audit('document_index',user,'failed',document_id=doc_id,error=type(exc).__name__)
    storage.write('documents.json',docs)
    return doc

def remove(doc_id,user):
    docs=storage.read('documents.json',[])
    doc=next((d for d in docs if d['id']==doc_id),None)
    if not doc: raise HTTPException(404,'Document not found')
    from . import retrieval
    retrieval.remove_document(doc_id)
    (config.DOC_DIR/(doc_id+doc['file_ext'])).unlink(missing_ok=True)
    storage.write('documents.json',[d for d in docs if d['id']!=doc_id])
    storage.audit('document_delete',user,document_id=doc_id)
    return {'deleted':doc_id}

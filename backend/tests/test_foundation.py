from pathlib import Path
from app import config, storage, security, ingestion, retrieval, reports

def test_dataset_minimum():
    paths=list((config.BASE_DIR/'sample_documents').glob('*.txt'))
    assert len(paths)>=20
    assert all('SYNTHETIC' in p.read_text(encoding='utf8') for p in paths)

def test_policy_metadata():
    p=config.BASE_DIR/'sample_documents'/'02_credit_risk_policy_v2.txt'
    meta=ingestion.extract_metadata(ingestion.extract(p),p.name)
    assert meta['document_version']=='2.0'
    assert meta['policy_number']=='DEMO-CR-001'
    assert meta['category']=='Credit Risk'

def test_passwords_hashed_and_permissions(local_store):
    security.seed_users()
    admin=security.authenticate('admin',config.DEMO_PASSWORD)
    service=security.authenticate('service',config.DEMO_PASSWORD)
    assert admin and admin['password_hash']!=config.DEMO_PASSWORD
    assert security.can(admin,'delete_docs')
    assert not security.can(service,'delete_docs')
    assert security.authenticate('admin','incorrect') is None

def test_storage_atomic(local_store):
    storage.append('feedback.json',{'score':1})
    storage.append('feedback.json',{'score':2})
    assert len(storage.read('feedback.json'))==2

def test_query_expansion():
    assert len(retrieval.expand_queries('Explain AML guidelines for loan compliance'))>=2

def test_report_pdf_with_evidence(local_store):
    user={'id':'demo','role':'Administrator'}
    row=reports.create_pdf('Test report','Credit Risk','Executive Summary\nA documented example finding [1].',
      [{'document_id':'doc1','document_name':'Synthetic Policy','page':1,'section':'Controls','excerpt':'Control example.'}],user)
    pdf=(config.REPORT_DIR/f'{row["id"]}.pdf').read_bytes()
    assert pdf.startswith(b'%PDF')
    assert row['citations']==1

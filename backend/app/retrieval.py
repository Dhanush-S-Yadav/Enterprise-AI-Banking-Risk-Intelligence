"""Hybrid BGE/Chroma + BM25 retrieval, RRF, parent expansion and cross-encoder rerank."""
import math
import re
from collections import defaultdict
from functools import lru_cache
from threading import RLock
from rank_bm25 import BM25Okapi
from . import storage, config

_RETRIEVAL_LOCK=RLock()

def tokenize(text): return re.findall(r'[a-z0-9]+',text.lower())

@lru_cache(maxsize=1)
def embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(config.EMBEDDING_MODEL)

@lru_cache(maxsize=1)
def reranker():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(config.RERANK_MODEL)

@lru_cache(maxsize=1)
def collection():
    import chromadb
    return chromadb.PersistentClient(path=str(config.VECTOR_DIR)).get_or_create_collection('banking_child_chunks',metadata={'hnsw:space':'cosine'})

def embedding(texts,is_query=False):
    if not texts: return []
    prepared=[('Represent this sentence for searching relevant passages: '+t) if is_query and 'bge-large' in config.EMBEDDING_MODEL else t for t in texts]
    return embedder().encode(prepared,normalize_embeddings=True,show_progress_bar=False).tolist()

def replace_document(doc_id,chunks,parents):
    with _RETRIEVAL_LOCK:
        # Embed first; do not destroy an existing index if model setup fails.
        vectors=embedding([c['text'] for c in chunks])
        coll=collection()
        old=[c for c in storage.read('chunks.json',[]) if c['document_id']==doc_id]
        if old: coll.delete(ids=[c['chunk_id'] for c in old])
        for start in range(0,len(chunks),100):
            batch=chunks[start:start+100]
            coll.upsert(ids=[c['chunk_id'] for c in batch],embeddings=vectors[start:start+100],
                        documents=[c['text'] for c in batch],
                        metadatas=[{k:v for k,v in c.items() if k!='text' and v is not None}
                                   for c in batch])
        storage.write('chunks.json',[c for c in storage.read('chunks.json',[]) if c['document_id']!=doc_id]+chunks)
        oldparents=storage.read('parents.json',{})
        oldparents={k:v for k,v in oldparents.items() if v.get('document_id')!=doc_id}
        oldparents.update({k:{**v,'document_id':doc_id} for k,v in parents.items()})
        storage.write('parents.json',oldparents)

def remove_document(doc_id):
    with _RETRIEVAL_LOCK:
        old=storage.read('chunks.json',[])
        ids=[c['chunk_id'] for c in old if c['document_id']==doc_id]
        if ids: collection().delete(ids=ids)
        storage.write('chunks.json',[c for c in old if c['document_id']!=doc_id])
        storage.write('parents.json',{k:v for k,v in storage.read('parents.json',{}).items()
                                     if v.get('document_id')!=doc_id})

def allowed(chunk,filters):
    return all(str(chunk.get(k) or '').lower()==str(v).lower() for k,v in (filters or {}).items()
               if k in {'document_id','category','document_version','policy_number'})

def expand_queries(query):
    """Offline multi-query expansion with transparent, bounded banking synonyms."""
    variants=[query]
    synonyms={'kyc':'know your customer identity verification','aml':'anti money laundering monitoring',
              'loan':'credit lending borrower eligibility','fraud':'suspicious activity risk investigation',
              'compliance':'control requirements audit evidence','policy':'procedures guidelines requirements'}
    extra=' '.join(v for k,v in synonyms.items() if k in query.lower())
    if extra: variants.append((query+' '+extra)[:1000])
    terms=tokenize(query)
    if len(terms)>5:
        variants.append(' '.join(t for t in terms if t not in {'what','does','please','about','explain','tell','which','the','are','for','and','how','from','that'}) or query)
    return list(dict.fromkeys(variants))[:3]

def compress(text,query,max_chars=550):
    """Keep sentences that overlap with query concepts; include a fallback for short text."""
    sentence_list=re.split(r'(?<=[.!?])\s+|\n+',text)
    qt=set(tokenize(query)) - {'the','a','is','and','what','for','how','are','of','to'}
    scored=sorted(enumerate(sentence_list),key=lambda pair:(-len(qt.intersection(tokenize(pair[1]))),pair[0]))
    candidates=sorted(scored[:5],key=lambda pair:pair[0])
    result=' '.join(s for _,s in candidates).strip()
    return (result or text)[:max_chars]

def retrieve(query,filters=None,top_k=None):
    top_k=top_k or config.RERANK_TOP_K
    chunks=[c for c in storage.read('chunks.json',[]) if allowed(c,filters)]
    if not chunks: return []
    by_id={c['chunk_id']:c for c in chunks}
    queries=expand_queries(query)
    ranking_lists=[]
    corpus=[tokenize(c['text']) for c in chunks]
    bm25=BM25Okapi(corpus)
    for q in queries:
        scores=bm25.get_scores(tokenize(q))
        ranked=sorted(zip(chunks,scores),key=lambda p:p[1],reverse=True)
        ranking_lists.append([c['chunk_id'] for c,s in ranked[:config.RETRIEVAL_TOP_K] if s>0])
        try:
            embeddings=embedding([q],is_query=True)
            # Filter after retrieval to support arbitrary combinations of metadata filters.
            matches=collection().query(query_embeddings=embeddings,n_results=min(len(storage.read('chunks.json',[])),max(config.RETRIEVAL_TOP_K*4,25)))
            ranking_lists.append([id for id in matches['ids'][0] if id in by_id][:config.RETRIEVAL_TOP_K])
        except Exception as exc:
            # BM25 allows text search while the vector model is still downloading.
            if not ranking_lists or not any(ranking_lists):
                raise RuntimeError(f'Vector retrieval unavailable: {exc}') from exc
    fused=defaultdict(float)
    for ranking in ranking_lists:
        for i,chunk_id in enumerate(ranking): fused[chunk_id]+=1.0/(60+i+1)
    if not fused: return []
    candidates=[by_id[i] for i in sorted(fused,key=fused.get,reverse=True)[:max(20,top_k*3)]]
    try:
        raw_scores=reranker().predict([(query,c['text']) for c in candidates])
        candidates=[c for _,c in sorted(zip(raw_scores,candidates),key=lambda p:float(p[0]),reverse=True)]
    except Exception:
        # Transparent fallback for first launch without reranking model.
        candidates.sort(key=lambda c:fused[c['chunk_id']],reverse=True)
    parents=storage.read('parents.json',{})
    results=[]; seen=set()
    for c in candidates:
        if c['parent_chunk_id'] in seen: continue
        seen.add(c['parent_chunk_id'])
        parent=parents.get(c['parent_chunk_id'],{})
        context=compress(parent.get('text',c['text']),query)
        results.append({'chunk_id':c['chunk_id'],'parent_chunk_id':c['parent_chunk_id'],
                        'document_id':c['document_id'],'document_name':c['document_name'],
                        'page':c.get('page'),'section':c.get('section'),
                        'category':c.get('category'),'document_version':c.get('document_version'),
                        'policy_number':c.get('policy_number'),'effective_date':c.get('effective_date'),
                        'excerpt':context,'score':round(fused[c['chunk_id']],6)})
        if len(results)>=top_k: break
    # Do not use obviously unrelated random matches as support.
    meaningful=set(tokenize(query))-{'the','a','an','what','which','where','when','why','how','is','are','do','does','did','tell','me','about','explain','please','for','and','of','to','in','with','this','from','it'}
    if not meaningful or not any(meaningful.intersection(tokenize(r['excerpt'])) for r in results): return []
    return results

def context_block(evidence):
    return '\n\n'.join(f'[{i}] Document: {c["document_name"]}; Version: {c.get("document_version") or "unknown"}; '
                     f'Page: {c.get("page") if c.get("page") is not None else "unknown"}; '
                     f'Section: {c.get("section") or "unknown"}\nExcerpt: {c["excerpt"]}'
                     for i,c in enumerate(evidence,1))

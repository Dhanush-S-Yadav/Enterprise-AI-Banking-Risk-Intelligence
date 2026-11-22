from typing import Any
from pydantic import BaseModel, Field

class Login(BaseModel):
    username: str=Field(min_length=2,max_length=200)
    password: str=Field(min_length=1)
class Register(BaseModel):
    username: str=Field(min_length=3,max_length=40,pattern=r'^[a-zA-Z0-9_-]+$')
    email: str=Field(min_length=3,max_length=200)
    password: str=Field(min_length=10,max_length=150)
class ChatRequest(BaseModel):
    message: str=Field(min_length=3,max_length=3000)
    agent: str='auto'
    conversation_id: str | None=None
    filters: dict[str,str] | None=None
class SearchRequest(BaseModel):
    query: str=Field(min_length=2,max_length=2000)
    filters: dict[str,str] | None=None
    top_k: int=Field(default=5,ge=1,le=20)
class ReindexRequest(BaseModel):
    document_id: str
class CompareRequest(BaseModel):
    document_id_a: str
    document_id_b: str
class AnalysisRequest(BaseModel):
    question: str=Field(min_length=3,max_length=3000)
    document_id: str | None=None
class ReportRequest(BaseModel):
    question: str=Field(min_length=3,max_length=3000)
    category: str='Banking Intelligence'
    title: str=Field(default='Banking Intelligence Report',min_length=3,max_length=150)
class Feedback(BaseModel):
    conversation_id: str
    rating: int=Field(ge=1,le=5)
    comment: str=Field(default='',max_length=1000)

# Explicit response schemas for externally consumed high-traffic API routes.
class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict[str,Any]
class SearchResponse(BaseModel):
    query: str
    results: list[dict[str,Any]]
    count: int
    queries: list[str]
class AgentResponse(BaseModel):
    agent: str
    agent_name: str
    answer: str
    citations: list[dict[str,Any]]
    latency_ms: int
class ChatResponse(AgentResponse):
    conversation_id: str
    message_id: str
    created_at: str
class UserResponse(BaseModel):
    user: dict[str,Any]
    permissions: list[str]

class UserAdminUpdate(BaseModel):
    role: str | None=None
    is_active: bool | None=None

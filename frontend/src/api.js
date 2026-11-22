import axios from 'axios';
export const api=axios.create({baseURL:'/api',timeout:240000});
api.interceptors.request.use(cfg=>{
  try {const auth=JSON.parse(localStorage.getItem('bank-auth')||'null'); if(auth?.access_token)cfg.headers.Authorization=`Bearer ${auth.access_token}`;}catch{}
  return cfg;
});
export const errorText=e=>{
  const detail=e?.response?.data?.detail;
  if(typeof detail==='string')return detail;
  if(detail?.message)return detail.message;
  if(Array.isArray(detail))return detail.map(x=>x.msg).join(', ');
  if(e?.code==='ECONNABORTED')return 'Request timed out. Check Ollama, model loading and your laptop memory.';
  if(!e?.response)return 'Cannot connect to the local backend. Run start_backend.ps1 and check http://localhost:8000/docs.';
  return e?.message || 'Unknown error';
};
export const permissionsByRole={
  'Customer Service Executive':['chat','search','read_docs','reports_read'],
  'Loan Officer':['chat','search','read_docs','upload','reports_read','report'],
  'Compliance Officer':['chat','search','read_docs','upload','delete_docs','compliance','compare','reports_read','report'],
  'Risk Analyst':['chat','search','read_docs','upload','fraud','compare','reports_read','report'],
  'Branch Manager':['chat','search','read_docs','upload','compliance','fraud','compare','reports_read','report'],
  'Auditor':['chat','search','read_docs','compliance','compare','reports_read','report'],
  'Administrator':['*']
};
export const can=(role,perm)=>permissionsByRole[role]?.includes('*')||permissionsByRole[role]?.includes(perm);
export async function downloadReport(id,name){
  const {data}=await api.get(`/reports/${id}/download`,{responseType:'blob'});
  const url=URL.createObjectURL(new Blob([data],{type:'application/pdf'}));
  const a=document.createElement('a');a.href=url;a.download=`${(name||'report').replace(/[^\w -]/g,'')}.pdf`;a.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}

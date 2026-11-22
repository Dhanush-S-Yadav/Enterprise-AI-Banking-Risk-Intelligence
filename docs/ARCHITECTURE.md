# Technical architecture and test scenarios

## Application trust boundaries

The browser may hide navigation features for roles but cannot confer permissions. JWT authentication and every restricted API are checked by the FastAPI backend. The local filesystem is a demonstration trust boundary, not a secure multi-tenant bank deployment. Source document text is data and may contain prompt injections; agents receive instructions to treat sources as untrusted data.

## Ingestion

The application validates extension and max size; hashes source bytes to reject exact duplicates; persists a status record; extracts PDF page numbers with PyMuPDF, DOCX paragraphs/tables with python-docx, TXT with UTF-8, CSV with Python csv, XLSX with openpyxl, and XLS with xlrd. Document metadata extraction only captures available title, policy ID, effective date, version and category; it does not invent missing fields. Parent chunks preserve evidence continuity; child chunks are embedded and indexed in Chroma. The local JSON chunk catalog makes BM25 searchable without scanning a relational store. Indexing statuses: Uploaded → Processing → Indexed or Failed.

## Retrieval

User query is converted to up to three query variants, including transparent banking concept expansions. Each variant retrieves semantic results from Chroma and lexical matches via BM25. RRF merges rankings by 1/(60 + rank). The cross-encoder ranks short-listed evidence. At most the configured top K distinct parents are selected. Query-focused compression extracts passages for the model's finite context window. Source cards preserve actual document ID, title, page (if present), version and section. When no evidence matches, the assistant abstains.

## Agents

The LangGraph conditional node maps intent → evidence → one of five agent nodes. RAG explains policy, Compliance produces checklist and missing-evidence notes, Fraud summarizes documented indicators, Policy Comparison requires distinct versions for chat and has a dedicated deterministic two-source diff endpoint, and Reporting produces a structured summary for PDF export. Outputs must be verified by users before any banking decision. No live transactions or regulatory certainty are claimed.

## Recommended manual acceptance checks

1. As `admin`, load 24 sample documents; verify Indexed statuses and nonzero chunks. Re-seed and verify duplicates are skipped.
2. Search `debt ratio Credit Risk Policy`; verify results name the policy versions and citation excerpts.
3. Compare credit risk versions 1.0 and 2.0; confirm the debt ratio changes 50% → 45%, the illustrative credit score threshold changes 680 → 700, and the second reviewer threshold changes.
4. Chat: `What is the KYC review cadence?`; verify a citation points to the KYC policy and the reply states an explicit synthetic cadence.
5. Switch to `service`; attempt `/api/documents/upload` or `/api/admin/users` using its JWT; expect HTTP 403.
6. Generate PDF and inspect its title, generated date, source excerpts, footer and disclaimer.
7. Stop Ollama and ask a source-based question; expect a readable 503 error, not an application crash.
8. Upload an exact duplicate; expect rejected duplicate entry in results. Delete a document; verify its vector and JSON chunks are removed.
9. Upload valid CSV/XLS/XLSX/DOCX/PDF text documents and inspect status and extracted metadata. For scanned PDFs expect a clear extraction error.
10. Reindex and verify the chunk count remains stable, with no duplicated vector IDs.

## Potential enhancements beyond the current academic prototype

Rate limiting, stronger identity federation, TLS, multi-user isolation, chunk-level access permissions, local encryption at rest, prompt-injection evaluation, citation support scoring, automated LLM benchmark suite, more precise section tracking, asynchronous job queue for ingestion, and production observability.

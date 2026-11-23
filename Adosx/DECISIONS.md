# ADOSX Architectural & Design Decisions

This document details key architectural decisions made during the design and implementation of the AdosX Multi-Tenant Reconciliation Application. Each entry details the decision, the alternative rejected, and the reasoning that separated them.

---

### Decision 1: Use FastAPI + SQLite for the backend service
- **Decision:** Build the REST API and ingestion backend using Python with FastAPI, Pydantic v2, and SQLite.
- **Alternative rejected:** Full-weight Django with Django REST Framework (DRF) and PostgreSQL.
- **Reasoning:** FastAPI with SQLite provides type-safe Pydantic schemas, zero external database setup hurdles, automatic OpenAPI documentation, and instant single-command execution (`python run.py`), honoring the brief's guideline: *"Stack: Django and React or Next.js preferred. If you are strong elsewhere, tell us and use it."*

---

### Decision 2: Store Raw CSV Strings alongside Normalized Values in the Database
- **Decision:** Store both the original unparsed raw text (`raw_value`, `raw_row_json`, `record_ref`) and the normalized comparison values (`normalized_value`, `normalized_record_ref`) in separate columns with error audit flags.
- **Alternative rejected:** Overwriting raw fields with parsed floats and sanitized strings during import, or silently dropping unparseable rows.
- **Reasoning:** In financial and event reconciliation, the system must never silently drop dirty rows or destroy original source representations; storing both allows safe mathematical comparison while presenting audit-faithful original data to the user.

---

### Decision 3: Separate Canonical Reference Normalization from Value Parsing
- **Decision:** Implement dedicated normalizers: `normalize_record_ref` (handling casing, whitespace, separators like `_`, `#`, space) and `values_are_equivalent` (handling `$`, `,`, `+`, trailing zeroes).
- **Alternative rejected:** Treating any string mismatch or formatting variance as a discrepancy, or guessing ambiguous IDs.
- **Reasoning:** Distinguishing between actual discrepancies and semantic non-errors (e.g. `1,200.00` vs `1200`, or `REC-1078` vs `  rec-1078  `) is a core 25% evaluation requirement ("The non-error is correctly identified as a non-error").

---

### Decision 4: Enforce Tenant Isolation at the SQL Query Layer
- **Decision:** Enforce multi-tenant scoping in `TenantIsolationService` at the database query level (`WHERE org_id = ?`) with tenant validation before query execution.
- **Alternative rejected:** Fetching all reconciliation records and filtering by tenant in the frontend or application memory.
- **Reasoning:** Client-side or in-memory filtering violates data boundary guarantees and introduces cross-tenant leakage vulnerabilities; tenant boundaries must be enforced at the data retrieval boundary.

---

### Decision 5: Bi-directional Matching Engine (A-to-B and B-to-A)
- **Decision:** Run a two-stage reconciliation pass: first matching System A records against indexed System B entries to detect `MISSING_IN_SYSTEM_B`, `DUPLICATE_SYSTEM_B_ENTRY`, and `VALUE_MISMATCH`, followed by a pass over remaining unmatched B entries to catch `ORPHAN_SYSTEM_B_ENTRY`.
- **Alternative rejected:** A single SQL outer join.
- **Reasoning:** SQL outer joins either pick an arbitrary entry when 1-to-many duplicates exist or obscure duplicate entries behind value mismatches; a two-stage index pass cleanly isolates all four required discrepancy categories without loss.

---

### Decision 6: Dual Frontend Strategy (Vite Project + Integrated SPA Delivery)
- **Decision:** Provide both the standard Vite React project (`frontend/package.json`, `src/App.jsx`, `vite.config.js`) AND configure FastAPI to serve the interactive React SPA directly at `http://127.0.0.1:8000/`.
- **Alternative rejected:** Requiring Node.js / npm to be pre-installed and running two separate servers in two different terminal windows.
- **Reasoning:** Guarantees that any evaluator cloning the repository can run the entire full-stack application (Backend + React UI) instantly with a single command (`python run.py`), eliminating environment and Node dependency failures while preserving standard Vite source structure.

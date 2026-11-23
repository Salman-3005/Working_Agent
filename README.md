# AdosX Multi-Tenant Data Reconciliation Application

A robust full-stack data reconciliation application designed to identify discrepancies between two event systems (**System A** and **System B**) with multi-tenant data boundary isolation and resilient handling of dirty, malformed data.

Built for the **AdosX Full-Stack Engineer Take-Home Assessment**.

---

## 1. Business Problem
Organizations frequently maintain multiple independent systems recording the same real-world business events. Neither system is universally authoritative:
- **System A** records events using `record_id`.
- **System B** records entries with a reference `record_ref` pointing back to System A.
- References are frequently dirty (mixed delimiters, inconsistent casing, extra whitespace).
- System B may contain multiple entries per record, or orphan entries pointing to non-existent records.
- Values may be formatted inconsistently (`$1,200.00` vs `1200`).
- Data spans multiple organizations (**tenants**), mapped exclusively via `locations.csv`.
- **Strict Boundary Constraint:** A record belonging to one tenant must **never** be visible to another tenant.

The objective is to identify disagreements accurately without silently dropping dirty records and without leaking data across tenant boundaries.

---

## 2. Features Implemented

- **Resilient CSV Ingestion:** Ingests `locations.csv`, `system_a.csv`, and `system_b.csv` without dropping rows. Preserves raw inputs and logs parsing/mapping issues.
- **Bi-directional Reconciliation Engine:** Identifies 4 core discrepancy types:
  1. `MISSING_IN_SYSTEM_B`: Exists in System A, missing in System B.
  2. `ORPHAN_SYSTEM_B_ENTRY`: System B entry pointing to a non-existent System A record.
  3. `DUPLICATE_SYSTEM_B_ENTRY`: Multiple System B entries referencing the same System A record.
  4. `VALUE_MISMATCH`: Conflicting values between systems for the same record.
- **Non-Error Recognition:** Correctly identifies semantically identical values formatted differently (e.g. `$350.50` vs `350.5`, `1,200.00` vs `1200`, `REC_1079` vs `REC-1079`) as non-errors, preventing false discrepancies.
- **Tenant Isolation:** Enforces multi-tenant query boundaries at the database layer. Disagreements and metrics are scoped to the selected organization.
- **Interactive React UI:**
  - Tenant selector switcher with global and organization-scoped views.
  - KPI summary dashboard (total discrepancies, breakdown by reason, record counts).
  - Dynamic filtering by discrepancy reason and real-time search.
  - Value sorting (Ascending / Descending / Default).
  - Side-by-side discrepancy details modal showing raw values and metadata.
  - Re-import and Re-reconciliation action controls.
  - Interactive test runner showing test suite execution directly in the UI.
- **Automated Test Suite:** 10 automated unit tests covering dirty data, non-errors, discrepancy detection, and tenant isolation.

---

## 3. Technology Stack

- **Backend:** Python 3.11, FastAPI, Uvicorn, Pydantic v2.
- **Database:** SQLite3 (`adosx.db`) with relational integrity and raw row preservation.
- **Frontend:** React 18, Tailwind CSS, Lucide icons (available both as a standalone Vite project and served directly via FastAPI).
- **Testing:** Python `unittest` suite (`test_reconciliation.py`).

---

## 4. System Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                      React Frontend                         │
│  (Dashboard, Tenant Filter, Reason Filter, Value Sorting)   │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / JSON
┌──────────────────────────────▼──────────────────────────────┐
│                    FastAPI REST Layer                       │
│    /api/health  /api/tenants  /api/disagreements  /api/stats│
└──────┬───────────────────────┬──────────────────────────────┘
       │                       │
┌──────▼────────────────┐ ┌────▼──────────────────────────────┐
│ CSV Import Service    │ │ Reconciliation Engine             │
│ - Raw row preservation│ │ - Reference Normalizer            │
│ - Dirty value handling│ │ - Non-Error Value Comparator      │
│ - Tenant resolution   │ │ - 4-Category Discrepancy Detector │
└──────┬────────────────┘ └────┬──────────────────────────────┘
       │                       │
┌──────▼───────────────────────▼──────────────────────────────┐
│                     SQLite Database                         │
│ (tenants, locations, system_a_records, system_b_entries)     │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Database Design

- `tenants`: `org_id` (PK), `name`, `created_at`
- `locations`: `location_id` (PK), `org_id` (FK), `location_name`, `city`
- `system_a_records`:
  - `id` (PK), `record_id`, `normalized_record_id`, `location_id`, `org_id`
  - `raw_value`, `normalized_value`, `is_value_valid`, `notes`
  - `raw_row_json`, `import_batch_id`, `import_error`
- `system_b_entries`:
  - `id` (PK), `entry_id`, `record_ref`, `normalized_record_ref`, `location_id`, `org_id`
  - `raw_value`, `normalized_value`, `is_value_valid`, `notes`
  - `raw_row_json`, `import_batch_id`, `import_error`
- `reconciliation_results`:
  - `id` (PK), `batch_id`, `record_id`, `org_id`, `location_id`, `disagreement_type`
  - `system_a_value`, `system_b_value`, `system_a_details`, `system_b_details`, `explanation`
- `import_batches`:
  - `batch_id` (PK), `imported_at`, `locations_count`, `system_a_count`, `system_b_count`, `errors_count`, `summary_json`

---

## 6. CSV Import Workflow

1. **Locations Ingestion:** Ingests `locations.csv`, extracts distinct `org_id` values into `tenants`, and indexes location-to-organization mappings.
2. **System A & B Ingestion:**
   - Ingests each row without dropping.
   - Cleans and normalizes `record_ref` into canonical uppercase hyphenated format (`normalize_record_ref`).
   - Normalizes numeric values, stripping currency symbols and thousand commas (`parse_numeric_value`).
   - Resolves tenant (`org_id`) using the location mapping. If unmapped, retains raw location and tags as `UNMAPPED_LOCATION`.
   - Stores full original row in `raw_row_json`.

---

## 7. Matching and Comparison Logic

Reconciliation operates in two index-backed passes:
1. **Pass 1 (System A to B):**
   - For each System A record, looks up matching System B entries by `normalized_record_id`.
   - If 0 matches: Flags `MISSING_IN_SYSTEM_B`.
   - If >1 matches: Flags `DUPLICATE_SYSTEM_B_ENTRY` with all B entries listed.
   - If 1 match: Evaluates values using `values_are_equivalent()`. If numbers differ, flags `VALUE_MISMATCH`. If semantically identical (e.g. `1,200.00` vs `1200`), flags as a **non-error agreement**.
2. **Pass 2 (System B Orphans):**
   - Identifies any System B entries whose `normalized_record_ref` was not matched to any System A record.
   - Flags them as `ORPHAN_SYSTEM_B_ENTRY`.

---

## 8. Tenant Isolation Approach

- **Location-Based Ownership:** A record’s organization is derived strictly through `locations.csv`.
- **SQL Boundary Enforcement:** `TenantIsolationService` applies `WHERE org_id = ?` at query time. Unauthenticated or arbitrary tenant IDs are rejected.
- **Tenant Validation:** Query filters are validated against registered tenants in the database before execution.
- **Cross-Tenant Prevention:** Tenant filter ensures that selecting `ORG-ALPHA` will never return records belonging to `ORG-BETA`.

---

## 9. API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Backend service health status |
| `GET` | `/api/tenants` | Returns available organizations/tenants |
| `POST` | `/api/import` | Triggers CSV ingestion and returns batch statistics |
| `POST` | `/api/reconcile` | Runs the comparison engine and saves discrepancy results |
| `GET` | `/api/disagreements` | Lists discrepancies (supports `tenant`, `reason`, `sort_order`, `search`) |
| `GET` | `/api/disagreements/{id}` | Detailed discrepancy breakdown with raw metadata |
| `GET` | `/api/stats` | Aggregated counts by tenant and reason |
| `GET` | `/api/import-summary` | Latest batch ingestion details and warnings |
| `POST` | `/api/run-tests` | Runs automated test suite and returns execution results |

---

## 10. How to Run the Application

### Quickest (Single Command):
Run the integrated full-stack server (serves both API and React frontend):

```bash
python run.py
```

Open your browser at:
👉 **`http://127.0.0.1:8000`**

### Running with Vite (Optional Node.js frontend):
If you prefer running Vite separately:
```bash
# Terminal 1: Backend
python -m uvicorn backend.main:app --port 8000 --reload

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
```

---

## 11. How to Execute Tests

Run the test suite directly from the command line:

```bash
python -m unittest backend.tests.test_reconciliation
```

Alternatively, click the **"Run Test Suite"** button directly on the web application dashboard.

---

## 12. What Was Deliberately Not Built

- **Authentication / OAuth / Passwords:** Explicitly declared out of scope by the brief. Replaced by a development tenant selector.
- **CSS / UI Overengineering:** Used a clean, focused, high-contrast dashboard with Tailwind CSS rather than custom CSS themes.
- **Automatic Resolution / Healing:** The assignment requires finding discrepancies, not guessing which system is authoritative.
- **Distributed Queues (Celery/RabbitMQ):** Kept execution synchronous and lightweight for 120-row dataset performance.

---

## 13. Required Assessment Answers

### a. Name one thing the AI agent got wrong. How did you notice?
During the initial implementation of the CSV importer, the AI agent generated an SQL `INSERT` statement for `system_b_entries` with 14 column definitions but only 13 `?` parameter placeholders in the `VALUES` clause. Additionally, during route function verification, default parameters configured with FastAPI's `= Query(None)` were accessed directly as strings without checking `isinstance(tenant, str)`, triggering an `AttributeError: 'Query' object has no attribute 'upper'`. I noticed both errors immediately when executing automated database ingestion tests and direct unit verifications, which raised `13 values for 14 columns` and the query attribute error, and corrected them by adding the missing placeholder and type guards.

### b. Which part of your submission are you least confident about, and why?
The heuristic boundary between a valid non-error formatted string (such as `REC_1079` or `rec-1082`) and a genuinely malformed or ambiguous reference in real, dirtier enterprise datasets. While standardizing delimiters (`-`, `_`, `#`, spaces) and casing works reliably for known prefix conventions, production exports could contain completely unstructured identifier permutations or composite IDs where over-aggressive regex normalization could accidentally merge distinct records into false duplicates.

### c. If you had a second day, what would you fix first?
On a second day, I would first implement asynchronous streaming or background worker processing for the CSV ingestion and reconciliation jobs with chunked SQL upserts instead of synchronous request-response loops. While synchronous execution is fast and simple for 120 rows, real-world reconciliation involves millions of records requiring background job queues, streaming progress websockets, and database indexing on `(org_id, normalized_record_id)` for high throughput.

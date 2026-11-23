import os
import json
import subprocess
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

from backend.database import get_db_connection
from backend.services.importer import CSVImportService
from backend.services.comparison import ReconciliationService
from backend.services.tenant import TenantIsolationService

router = APIRouter(prefix="/api")

class ImportRequest(BaseModel):
    locations_file: Optional[str] = "data/locations.csv"
    system_a_file: Optional[str] = "data/system_a.csv"
    system_b_file: Optional[str] = "data/system_b.csv"

@router.get("/health")
def get_health():
    return {
        "status": "healthy",
        "service": "AdosX Multi-Tenant Reconciliation Service",
        "version": "1.0.0"
    }

@router.get("/tenants")
def get_tenants():
    tenants = TenantIsolationService.get_valid_tenants()
    return {"tenants": tenants, "count": len(tenants)}

@router.post("/import")
def run_import(req: Optional[ImportRequest] = None):
    locations_path = req.locations_file if req and req.locations_file else "data/locations.csv"
    system_a_path = req.system_a_file if req and req.system_a_file else "data/system_a.csv"
    system_b_path = req.system_b_file if req and req.system_b_file else "data/system_b.csv"

    # Fallback to root if not in data/
    if not os.path.exists(locations_path) and os.path.exists("locations.csv"):
        locations_path = "locations.csv"
    if not os.path.exists(system_a_path) and os.path.exists("system_a.csv"):
        system_a_path = "system_a.csv"
    if not os.path.exists(system_b_path) and os.path.exists("system_b.csv"):
        system_b_path = "system_b.csv"

    if not os.path.exists(locations_path):
        raise HTTPException(status_code=400, detail=f"Locations file not found: {locations_path}")
    if not os.path.exists(system_a_path):
        raise HTTPException(status_code=400, detail=f"System A file not found: {system_a_path}")
    if not os.path.exists(system_b_path):
        raise HTTPException(status_code=400, detail=f"System B file not found: {system_b_path}")

    importer = CSVImportService()
    summary = importer.import_all(locations_path, system_a_path, system_b_path)
    return {"status": "SUCCESS", "summary": summary}

@router.post("/reconcile")
def run_reconciliation(batch_id: Optional[str] = None):
    recon = ReconciliationService()
    result = recon.run_reconciliation(batch_id=batch_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@router.get("/disagreements")
def get_disagreements(
    tenant: Optional[str] = None,
    reason: Optional[str] = None,
    sort_order: Optional[str] = None,
    search: Optional[str] = None
):
    if not isinstance(tenant, str):
        tenant = None
    if not isinstance(reason, str):
        reason = None
    if not isinstance(sort_order, str):
        sort_order = None
    if not isinstance(search, str):
        search = None

    rows = TenantIsolationService.query_disagreements(
        tenant_id=tenant,
        reason=reason,
        sort_order=sort_order,
        search=search
    )

    # Parse details JSON for response
    for r in rows:
        try:
            r["system_a_details"] = json.loads(r["system_a_details"]) if r["system_a_details"] else None
        except Exception:
            pass
        try:
            r["system_b_details"] = json.loads(r["system_b_details"]) if r["system_b_details"] else None
        except Exception:
            pass

    return {
        "disagreements": rows,
        "count": len(rows),
        "filters_applied": {
            "tenant": tenant,
            "reason": reason,
            "sort_order": sort_order,
            "search": search
        }
    }

@router.get("/disagreements/{disagreement_id}")
def get_disagreement_detail(disagreement_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, batch_id, record_id, org_id, location_id,
               disagreement_type, system_a_value, system_b_value,
               system_a_details, system_b_details, explanation, created_at
        FROM reconciliation_results
        WHERE id = ?
    """, (disagreement_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Disagreement record not found")

    item = dict(row)
    try:
        item["system_a_details"] = json.loads(item["system_a_details"]) if item["system_a_details"] else None
    except Exception:
        pass
    try:
        item["system_b_details"] = json.loads(item["system_b_details"]) if item["system_b_details"] else None
    except Exception:
        pass

    return item

@router.get("/import-summary")
def get_import_summary():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT batch_id, imported_at, locations_count, system_a_count, system_b_count, errors_count, summary_json
        FROM import_batches
        ORDER BY imported_at DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"summary": None, "message": "No import batch has been executed yet."}

    data = dict(row)
    try:
        data["summary_json"] = json.loads(data["summary_json"]) if data["summary_json"] else {}
    except Exception:
        pass
    return data

@router.get("/stats")
def get_stats(tenant: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Base query for disagreement counts
    where_clause = ""
    params = []
    if isinstance(tenant, str) and tenant.upper() != "ALL":
        where_clause = " WHERE org_id = ?"
        params.append(tenant)

    cursor.execute(f"SELECT COUNT(*) as total FROM reconciliation_results{where_clause}", params)
    total_disagreements = cursor.fetchone()["total"]

    cursor.execute(f"""
        SELECT disagreement_type, COUNT(*) as count
        FROM reconciliation_results{where_clause}
        GROUP BY disagreement_type
    """, params)
    counts_by_type = {r["disagreement_type"]: r["count"] for r in cursor.fetchall()}

    # Total imported records
    cursor.execute("SELECT COUNT(*) as cnt FROM system_a_records")
    system_a_total = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) as cnt FROM system_b_entries")
    system_b_total = cursor.fetchone()["cnt"]

    conn.close()

    return {
        "tenant_selected": tenant or "ALL",
        "total_disagreements": total_disagreements,
        "counts_by_type": counts_by_type,
        "system_a_records_total": system_a_total,
        "system_b_entries_total": system_b_total
    }

@router.post("/run-tests")
def run_automated_tests():
    """
    Executes automated test suite and returns structured results.
    Allows running tests directly from the UI or via API!
    """
    import unittest
    import io
    from backend.tests.test_reconciliation import ReconciliationTestCase

    suite = unittest.TestLoader().loadTestsFromTestCase(ReconciliationTestCase)
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)
    result = runner.run(suite)

    test_names = [name for name in dir(ReconciliationTestCase) if name.startswith("test_")]

    return {
        "total_tests": result.testsRun,
        "passed": result.wasSuccessful(),
        "failures_count": len(result.failures),
        "errors_count": len(result.errors),
        "tests": test_names,
        "output": stream.getvalue()
    }

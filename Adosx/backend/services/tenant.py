from typing import List, Optional, Dict, Any
from backend.database import get_db_connection

class TenantIsolationService:
    """
    Enforces tenant data boundaries across all queries.
    Rows belonging to one organization (tenant) must NEVER leak to another.
    """

    @staticmethod
    def get_valid_tenants() -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT org_id, name FROM tenants ORDER BY org_id ASC")
        rows = cursor.fetchall()
        conn.close()
        return [{"org_id": r["org_id"], "name": r["name"]} for r in rows]

    @staticmethod
    def validate_tenant(org_id: Optional[str]) -> bool:
        if not org_id:
            return False
        valid_tenants = [t["org_id"] for t in TenantIsolationService.get_valid_tenants()]
        return org_id in valid_tenants

    @staticmethod
    def query_disagreements(
        tenant_id: Optional[str] = None,
        reason: Optional[str] = None,
        sort_order: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query disagreements strictly scoped by tenant if provided.
        Sort by value and filter by reason safely.
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT id, batch_id, record_id, org_id, location_id,
                   disagreement_type, system_a_value, system_b_value,
                   system_a_details, system_b_details, explanation, created_at
            FROM reconciliation_results
            WHERE 1=1
        """
        params = []

        # Strict tenant filtering
        if tenant_id and tenant_id.upper() != "ALL":
            # Ensure tenant exists to prevent arbitrary or injection queries
            if not TenantIsolationService.validate_tenant(tenant_id) and tenant_id != "UNRESOLVED":
                conn.close()
                return []
            query += " AND org_id = ?"
            params.append(tenant_id)

        # Reason filtering
        if reason and reason.upper() != "ALL":
            query += " AND disagreement_type = ?"
            params.append(reason)

        # Search query
        if search:
            search_param = f"%{search.strip()}%"
            query += " AND (record_id LIKE ? OR location_id LIKE ? OR explanation LIKE ?)"
            params.extend([search_param, search_param, search_param])

        # Sorting by value
        # Note: system_a_value and system_b_value can be strings like '$350.50' or '1,200.00' or '—'
        # We order by clean numeric parsing or fallback to id
        if sort_order:
            sort_dir = "ASC" if sort_order.lower() == "asc" else "DESC"
            # SQLite safe numeric extraction for sorting:
            # Strip non-digits and sort CAST as REAL
            query += f"""
                ORDER BY 
                    CASE 
                        WHEN system_a_value != '—' THEN CAST(REPLACE(REPLACE(REPLACE(system_a_value, '$', ''), ',', ''), '+', '') AS REAL)
                        WHEN system_b_value != '—' THEN CAST(REPLACE(REPLACE(REPLACE(system_b_value, '$', ''), ',', ''), '+', '') AS REAL)
                        ELSE 0
                    END {sort_dir}, id ASC
            """
        else:
            query += " ORDER BY id ASC"

        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

import json
from typing import Dict, Any, List, Optional
from backend.database import get_db_connection
from backend.services.normalizer import values_are_equivalent

class ReconciliationService:
    def __init__(self):
        pass

    def run_reconciliation(self, batch_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes reconciliation between System A and System B records.
        Stores results in reconciliation_results table.
        Returns a summary of discovered disagreements.
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        # If no batch_id specified, grab latest batch
        if not batch_id:
            cursor.execute("SELECT batch_id FROM import_batches ORDER BY imported_at DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                conn.close()
                return {"error": "No imported data found to reconcile."}
            batch_id = row["batch_id"]

        # Clear existing reconciliation results for this batch
        cursor.execute("DELETE FROM reconciliation_results WHERE batch_id = ?", (batch_id,))

        # Fetch all System A records for this batch
        cursor.execute("""
            SELECT id, record_id, normalized_record_id, location_id, org_id,
                   event_type, timestamp, raw_value, normalized_value,
                   is_value_valid, notes, import_error
            FROM system_a_records
            WHERE import_batch_id = ?
        """, (batch_id,))
        records_a = [dict(r) for r in cursor.fetchall()]

        # Fetch all System B entries for this batch
        cursor.execute("""
            SELECT id, entry_id, record_ref, normalized_record_ref, location_id, org_id,
                   event_type, timestamp, raw_value, normalized_value,
                   is_value_valid, notes, import_error
            FROM system_b_entries
            WHERE import_batch_id = ?
        """, (batch_id,))
        entries_b = [dict(r) for r in cursor.fetchall()]

        # Index System A by normalized_record_id
        a_by_norm_id: Dict[str, Dict[str, Any]] = {}
        for rec in records_a:
            norm_id = rec["normalized_record_id"]
            if norm_id:
                a_by_norm_id[norm_id] = rec

        # Index System B by normalized_record_ref (grouping list of entries)
        b_by_norm_ref: Dict[str, List[Dict[str, Any]]] = {}
        for entry in entries_b:
            norm_ref = entry["normalized_record_ref"]
            if norm_ref:
                b_by_norm_ref.setdefault(norm_ref, []).append(entry)

        disagreements = []
        matched_b_entry_ids = set()

        # --- CHECK 1: System A records -> Compare with System B ---
        for rec_a in records_a:
            norm_id = rec_a["normalized_record_id"]
            matched_b_list = b_by_norm_ref.get(norm_id, [])

            # A. MISSING_IN_SYSTEM_B: No B entry found
            if not matched_b_list:
                disagreement = {
                    "batch_id": batch_id,
                    "record_id": rec_a["record_id"],
                    "org_id": rec_a["org_id"] or "UNRESOLVED",
                    "location_id": rec_a["location_id"] or "UNKNOWN",
                    "disagreement_type": "MISSING_IN_SYSTEM_B",
                    "system_a_value": rec_a["raw_value"] or "—",
                    "system_b_value": "—",
                    "system_a_details": json.dumps(rec_a),
                    "system_b_details": json.dumps([]),
                    "explanation": f"Record '{rec_a['record_id']}' exists in System A but has no corresponding entry in System B."
                }
                disagreements.append(disagreement)
                continue

            # Mark matched B entries
            for b_entry in matched_b_list:
                matched_b_entry_ids.add(b_entry["id"])

            # C. DUPLICATE_SYSTEM_B_ENTRY: Multiple B entries for same A record
            if len(matched_b_list) > 1:
                b_values = [b["raw_value"] or "—" for b in matched_b_list]
                b_entries_summary = [f"{b['entry_id']} ({b['raw_value']})" for b in matched_b_list]
                disagreement = {
                    "batch_id": batch_id,
                    "record_id": rec_a["record_id"],
                    "org_id": rec_a["org_id"] or matched_b_list[0].get("org_id") or "UNRESOLVED",
                    "location_id": rec_a["location_id"] or matched_b_list[0].get("location_id") or "UNKNOWN",
                    "disagreement_type": "DUPLICATE_SYSTEM_B_ENTRY",
                    "system_a_value": rec_a["raw_value"] or "—",
                    "system_b_value": ", ".join(b_values),
                    "system_a_details": json.dumps(rec_a),
                    "system_b_details": json.dumps(matched_b_list),
                    "explanation": f"Record '{rec_a['record_id']}' has {len(matched_b_list)} duplicate entries in System B: {', '.join(b_entries_summary)}."
                }
                disagreements.append(disagreement)
                # Note: Continue to evaluate value mismatches if any
                continue

            # Exactly 1 B entry: Check D. VALUE_MISMATCH and Non-Errors
            entry_b = matched_b_list[0]
            val_a = rec_a["raw_value"]
            val_b = entry_b["raw_value"]

            is_equiv, reason = values_are_equivalent(val_a, val_b)
            if not is_equiv:
                disagreement = {
                    "batch_id": batch_id,
                    "record_id": rec_a["record_id"],
                    "org_id": rec_a["org_id"] or entry_b.get("org_id") or "UNRESOLVED",
                    "location_id": rec_a["location_id"] or entry_b.get("location_id") or "UNKNOWN",
                    "disagreement_type": "VALUE_MISMATCH",
                    "system_a_value": val_a if val_a is not None else "—",
                    "system_b_value": val_b if val_b is not None else "—",
                    "system_a_details": json.dumps(rec_a),
                    "system_b_details": json.dumps([entry_b]),
                    "explanation": f"Value mismatch for '{rec_a['record_id']}': System A reports '{val_a}', but System B reports '{val_b}' ({reason})."
                }
                disagreements.append(disagreement)

        # --- CHECK 2: System B entries -> Find Orphans (not matched to any A record) ---
        for entry_b in entries_b:
            if entry_b["id"] not in matched_b_entry_ids:
                norm_ref = entry_b["normalized_record_ref"]
                disagreement = {
                    "batch_id": batch_id,
                    "record_id": entry_b["record_ref"] or f"Entry-{entry_b['entry_id']}",
                    "org_id": entry_b["org_id"] or "UNRESOLVED",
                    "location_id": entry_b["location_id"] or "UNKNOWN",
                    "disagreement_type": "ORPHAN_SYSTEM_B_ENTRY",
                    "system_a_value": "—",
                    "system_b_value": entry_b["raw_value"] or "—",
                    "system_a_details": json.dumps({}),
                    "system_b_details": json.dumps([entry_b]),
                    "explanation": f"System B entry '{entry_b['entry_id']}' points to record_ref '{entry_b['record_ref']}', which does not exist in System A."
                }
                disagreements.append(disagreement)

        # Batch insert all disagreements into database
        for d in disagreements:
            cursor.execute("""
                INSERT INTO reconciliation_results (
                    batch_id, record_id, org_id, location_id,
                    disagreement_type, system_a_value, system_b_value,
                    system_a_details, system_b_details, explanation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                d["batch_id"], d["record_id"], d["org_id"], d["location_id"],
                d["disagreement_type"], d["system_a_value"], d["system_b_value"],
                d["system_a_details"], d["system_b_details"], d["explanation"]
            ))

        conn.commit()

        # Calculate counts by disagreement type
        counts_by_type = {}
        for d in disagreements:
            dtype = d["disagreement_type"]
            counts_by_type[dtype] = counts_by_type.get(dtype, 0) + 1

        # Calculate counts by tenant
        counts_by_org = {}
        for d in disagreements:
            org = d["org_id"]
            counts_by_org[org] = counts_by_org.get(org, 0) + 1

        conn.close()

        return {
            "batch_id": batch_id,
            "total_disagreements": len(disagreements),
            "counts_by_type": counts_by_type,
            "counts_by_org": counts_by_org,
            "status": "SUCCESS"
        }

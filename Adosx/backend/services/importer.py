import csv
import json
import uuid
from typing import Dict, Any, List, Optional
from backend.database import get_db_connection
from backend.services.normalizer import normalize_record_ref, parse_numeric_value

class CSVImportService:
    def __init__(self):
        pass

    def import_all(self, locations_path: str, system_a_path: str, system_b_path: str) -> Dict[str, Any]:
        """
        Orchestrate importing all three CSV files into SQLite.
        Never silently drop rows; preserve all raw data and record parsing notes.
        """
        batch_id = f"BATCH-{uuid.uuid4().hex[:8].upper()}"
        conn = get_db_connection()
        cursor = conn.cursor()

        summary = {
            "batch_id": batch_id,
            "locations": {"total": 0, "success": 0, "warnings": []},
            "system_a": {"total": 0, "success": 0, "with_issues": 0, "issues": []},
            "system_b": {"total": 0, "success": 0, "with_issues": 0, "issues": []},
            "tenants_detected": 0
        }

        # 1. Import locations.csv
        location_to_org: Dict[str, str] = {}
        unique_orgs = set()

        try:
            with open(locations_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=2):
                    summary["locations"]["total"] += 1
                    loc_id = (row.get("location_id") or row.get("location") or "").strip()
                    org_id = (row.get("org_id") or row.get("org") or "").strip()
                    loc_name = (row.get("location_name") or row.get("name") or "").strip()
                    city = (row.get("city") or "").strip()

                    if not loc_id or not org_id:
                        summary["locations"]["warnings"].append({
                            "row": row_idx,
                            "error": "Missing location_id or org_id",
                            "raw": row
                        })
                        continue

                    location_to_org[loc_id] = org_id
                    unique_orgs.add(org_id)

                    # Insert location
                    cursor.execute("""
                        INSERT OR REPLACE INTO locations (location_id, org_id, location_name, city)
                        VALUES (?, ?, ?, ?)
                    """, (loc_id, org_id, loc_name, city))
                    summary["locations"]["success"] += 1

            # Insert detected tenants
            for org_id in unique_orgs:
                cursor.execute("""
                    INSERT OR IGNORE INTO tenants (org_id, name)
                    VALUES (?, ?)
                """, (org_id, f"Organization {org_id}"))
            summary["tenants_detected"] = len(unique_orgs)

        except Exception as e:
            summary["locations"]["warnings"].append({"error": f"Failed reading locations: {str(e)}"})

        # 2. Import system_a.csv
        try:
            with open(system_a_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=2):
                    summary["system_a"]["total"] += 1
                    try:
                        raw_record_id = row.get("record_id") or ""
                        raw_loc_id = (row.get("location_id") or row.get("location") or "").strip()
                        event_type = (row.get("event_type") or "").strip()
                        timestamp = (row.get("timestamp") or "").strip()
                        raw_value = row.get("value")
                        notes = row.get("notes") or ""

                        # Normalization
                        norm_record_id = normalize_record_ref(raw_record_id)
                        norm_val, is_val_valid, val_err = parse_numeric_value(raw_value)

                        # Tenant resolution
                        resolved_org = location_to_org.get(raw_loc_id)
                        row_issues = []
                        if not raw_record_id.strip():
                            row_issues.append("BLANK_RECORD_ID")
                        if not raw_loc_id:
                            row_issues.append("MISSING_LOCATION")
                        elif not resolved_org:
                            row_issues.append(f"UNMAPPED_LOCATION: '{raw_loc_id}'")
                        if val_err:
                            row_issues.append(val_err)

                        import_error = "; ".join(row_issues) if row_issues else None
                        if import_error:
                            summary["system_a"]["with_issues"] += 1
                            summary["system_a"]["issues"].append({
                                "row": row_idx,
                                "record_id": raw_record_id,
                                "error": import_error
                            })
                        else:
                            summary["system_a"]["success"] += 1

                        cursor.execute("""
                            INSERT INTO system_a_records (
                                record_id, normalized_record_id, location_id, org_id,
                                event_type, timestamp, raw_value, normalized_value,
                                is_value_valid, notes, raw_row_json, import_batch_id, import_error
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            raw_record_id, norm_record_id, raw_loc_id, resolved_org,
                            event_type, timestamp, raw_value, norm_val,
                            1 if is_val_valid else 0, notes, json.dumps(row), batch_id, import_error
                        ))
                    except Exception as row_err:
                        summary["system_a"]["with_issues"] += 1
                        summary["system_a"]["issues"].append({
                            "row": row_idx,
                            "record_id": str(row.get("record_id", "")),
                            "error": f"Row processing error: {str(row_err)}"
                        })

        except Exception as e:
            summary["system_a"]["issues"].append({"error": f"Failed reading System A: {str(e)}"})

        # 3. Import system_b.csv
        try:
            with open(system_b_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=2):
                    summary["system_b"]["total"] += 1
                    try:
                        raw_entry_id = row.get("entry_id") or f"ENT-ROW-{row_idx}"
                        raw_record_ref = row.get("record_ref") or ""
                        raw_loc_id = (row.get("location_id") or row.get("location") or "").strip()
                        event_type = (row.get("event_type") or "").strip()
                        timestamp = (row.get("timestamp") or "").strip()
                        raw_value = row.get("value")
                        notes = row.get("notes") or ""

                        # Normalization
                        norm_record_ref = normalize_record_ref(raw_record_ref)
                        norm_val, is_val_valid, val_err = parse_numeric_value(raw_value)

                        # Tenant resolution
                        resolved_org = location_to_org.get(raw_loc_id)
                        row_issues = []
                        if not raw_record_ref.strip():
                            row_issues.append("BLANK_RECORD_REF")
                        if not raw_loc_id:
                            row_issues.append("MISSING_LOCATION")
                        elif not resolved_org:
                            row_issues.append(f"UNMAPPED_LOCATION: '{raw_loc_id}'")
                        if val_err:
                            row_issues.append(val_err)

                        import_error = "; ".join(row_issues) if row_issues else None
                        if import_error:
                            summary["system_b"]["with_issues"] += 1
                            summary["system_b"]["issues"].append({
                                "row": row_idx,
                                "entry_id": raw_entry_id,
                                "record_ref": raw_record_ref,
                                "error": import_error
                            })
                        else:
                            summary["system_b"]["success"] += 1

                        cursor.execute("""
                            INSERT INTO system_b_entries (
                                entry_id, record_ref, normalized_record_ref, location_id, org_id,
                                event_type, timestamp, raw_value, normalized_value,
                                is_value_valid, notes, raw_row_json, import_batch_id, import_error
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            raw_entry_id, raw_record_ref, norm_record_ref, raw_loc_id, resolved_org,
                            event_type, timestamp, raw_value, norm_val,
                            1 if is_val_valid else 0, notes, json.dumps(row), batch_id, import_error
                        ))
                    except Exception as row_err:
                        summary["system_b"]["with_issues"] += 1
                        summary["system_b"]["issues"].append({
                            "row": row_idx,
                            "entry_id": str(row.get("entry_id", "")),
                            "error": f"Row processing error: {str(row_err)}"
                        })

        except Exception as e:
            summary["system_b"]["issues"].append({"error": f"Failed reading System B: {str(e)}"})

        # Record import batch
        cursor.execute("""
            INSERT INTO import_batches (
                batch_id, locations_count, system_a_count, system_b_count, errors_count, summary_json
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            batch_id,
            summary["locations"]["total"],
            summary["system_a"]["total"],
            summary["system_b"]["total"],
            summary["system_a"]["with_issues"] + summary["system_b"]["with_issues"],
            json.dumps(summary)
        ))

        conn.commit()
        conn.close()
        return summary

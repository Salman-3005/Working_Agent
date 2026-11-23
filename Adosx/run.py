import os
import sys
import uvicorn
from backend.database import init_db
from backend.services.importer import CSVImportService
from backend.services.comparison import ReconciliationService

def main():
    print("=" * 60)
    print("🚀 Initializing AdosX Multi-Tenant Reconciliation Application")
    print("=" * 60)

    # 1. Initialize DB
    print("[1/3] Initializing SQLite database schema...")
    init_db()

    # 2. Check and import CSV data if not already populated
    loc_file = "data/locations.csv" if os.path.exists("data/locations.csv") else "locations.csv"
    a_file = "data/system_a.csv" if os.path.exists("data/system_a.csv") else "system_a.csv"
    b_file = "data/system_b.csv" if os.path.exists("data/system_b.csv") else "system_b.csv"

    if os.path.exists(loc_file) and os.path.exists(a_file) and os.path.exists(b_file):
        print(f"[2/3] Ingesting CSV files into SQLite database ({a_file}, {b_file}, {loc_file})...")
        importer = CSVImportService()
        summary = importer.import_all(loc_file, a_file, b_file)
        print(f"      Batch ID: {summary['batch_id']}")
        print(f"      System A rows: {summary['system_a']['total']} (with issues: {summary['system_a']['with_issues']})")
        print(f"      System B rows: {summary['system_b']['total']} (with issues: {summary['system_b']['with_issues']})")
        print(f"      Locations: {summary['locations']['total']} | Tenants: {summary['tenants_detected']}")

        print("[3/3] Running comparison & reconciliation engine...")
        recon = ReconciliationService()
        recon_res = recon.run_reconciliation(batch_id=summary["batch_id"])
        print(f"      Disagreements found: {recon_res['total_disagreements']}")
        for dtype, cnt in recon_res['counts_by_type'].items():
            print(f"        - {dtype}: {cnt}")
    else:
        print("[!] CSV files not found in root or data/ directory. Ready for manual import.")

    print("\n" + "=" * 60)
    print("✨ Application ready! Serving API & React UI at:")
    print("   👉 http://127.0.0.1:8000")
    print("=" * 60 + "\n")

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)

if __name__ == "__main__":
    main()

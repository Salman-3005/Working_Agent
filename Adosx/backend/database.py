import os
import sqlite3
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "adosx.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Tenants table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tenants (
        org_id TEXT PRIMARY KEY,
        name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Locations table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        location_id TEXT PRIMARY KEY,
        org_id TEXT NOT NULL,
        location_name TEXT,
        city TEXT,
        FOREIGN KEY (org_id) REFERENCES tenants(org_id)
    );
    """)

    # System A Records
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_a_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_id TEXT NOT NULL,
        normalized_record_id TEXT NOT NULL,
        location_id TEXT,
        org_id TEXT,
        event_type TEXT,
        timestamp TEXT,
        raw_value TEXT,
        normalized_value REAL,
        is_value_valid BOOLEAN DEFAULT 1,
        notes TEXT,
        raw_row_json TEXT NOT NULL,
        import_batch_id TEXT NOT NULL,
        import_error TEXT
    );
    """)

    # System B Entries
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_b_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_id TEXT NOT NULL,
        record_ref TEXT NOT NULL,
        normalized_record_ref TEXT NOT NULL,
        location_id TEXT,
        org_id TEXT,
        event_type TEXT,
        timestamp TEXT,
        raw_value TEXT,
        normalized_value REAL,
        is_value_valid BOOLEAN DEFAULT 1,
        notes TEXT,
        raw_row_json TEXT NOT NULL,
        import_batch_id TEXT NOT NULL,
        import_error TEXT
    );
    """)

    # Reconciliation Results
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reconciliation_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id TEXT NOT NULL,
        record_id TEXT NOT NULL,
        org_id TEXT,
        location_id TEXT,
        disagreement_type TEXT NOT NULL,
        system_a_value TEXT,
        system_b_value TEXT,
        system_a_details TEXT,
        system_b_details TEXT,
        explanation TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Import Batches
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS import_batches (
        batch_id TEXT PRIMARY KEY,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        locations_count INTEGER DEFAULT 0,
        system_a_count INTEGER DEFAULT 0,
        system_b_count INTEGER DEFAULT 0,
        errors_count INTEGER DEFAULT 0,
        summary_json TEXT
    );
    """)

    conn.commit()
    conn.close()

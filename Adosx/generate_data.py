import csv
import random
import os

os.makedirs("data", exist_ok=True)

# 1. Generate locations.csv
# 15 locations mapped to 4 tenants + 1 shared edge case
locations_data = [
    ("LOC-01", "ORG-ALPHA", "North Station", "New York"),
    ("LOC-02", "ORG-ALPHA", "East Hub", "Boston"),
    ("LOC-03", "ORG-ALPHA", "West Terminal", "Albany"),
    ("LOC-04", "ORG-BETA", "Central Point", "Chicago"),
    ("LOC-05", "ORG-BETA", "Lake Branch", "Milwaukee"),
    ("LOC-06", "ORG-BETA", "River Center", "Detroit"),
    ("LOC-07", "ORG-GAMMA", "South Depot", "Austin"),
    ("LOC-08", "ORG-GAMMA", "Gulf Harbor", "Houston"),
    ("LOC-09", "ORG-GAMMA", "Bayou Dock", "New Orleans"),
    ("LOC-10", "ORG-DELTA", "Pacific Pier", "Seattle"),
    ("LOC-11", "ORG-DELTA", "Valley Junction", "Portland"),
    ("LOC-12", "ORG-DELTA", "Bay Terminal", "San Francisco"),
    ("LOC-13", "ORG-ALPHA", "Metro Tower", "Philadelphia"),
    ("LOC-14", "ORG-BETA", "Prairie Post", "Minneapolis"),
    ("LOC-15", "ORG-GAMMA", "Hilltop Gateway", "Dallas"),
]

with open("data/locations.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["location_id", "org_id", "location_name", "city"])
    for row in locations_data:
        writer.writerow(row)

# Also write to root for convenience
with open("locations.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["location_id", "org_id", "location_name", "city"])
    for row in locations_data:
        writer.writerow(row)

# 2. Generate system_a.csv and system_b.csv with 120 rows each
# We will define deliberate categories:
# - Clean agreements: ~75 rows
# - Non-errors (look dirty but agree): 10 rows (formatting differences, currency symbols, whitespace)
# - Missing in B: 8 rows
# - Orphan in B: 8 rows
# - Duplicate in B: 7 rows (points to same A record)
# - Value mismatch: 12 rows
# Total ~120 rows on both sides

system_a_rows = []
system_b_rows = []

# List of locations to cycle through
loc_keys = [r[0] for r in locations_data]

# 1-75: Clean agreements
for i in range(1, 76):
    rec_id = f"REC-{1000 + i}"
    loc = loc_keys[(i - 1) % len(loc_keys)]
    val = round(50.0 + (i * 13.7) % 850.0, 2)
    ev_type = ["PAYMENT", "TRANSFER", "REFUND", "SETTLEMENT"][i % 4]
    ts = f"2026-11-{(i % 25) + 1:02d}T10:15:00Z"
    
    system_a_rows.append([rec_id, loc, ev_type, ts, f"{val:.2f}", f"Event {i} recorded"])
    system_b_rows.append([f"ENT-{5000 + i}", rec_id, loc, ev_type, ts, f"{val:.2f}", f"Entry for {rec_id}"])

# 76-85: Non-errors (dirty representation, but semantically identical)
# Row 76: A has "1,200.00", B has "1200"
rec = "REC-1076"
system_a_rows.append([rec, "LOC-01", "TRANSFER", "2026-11-05T12:00:00Z", "1,200.00", "Formatted with comma"])
system_b_rows.append(["ENT-5076", rec, "LOC-01", "TRANSFER", "2026-11-05T12:00:00Z", "1200", "Plain integer string"])

# Row 77: A has "$350.50", B has "350.5"
rec = "REC-1077"
system_a_rows.append([rec, "LOC-04", "PAYMENT", "2026-11-06T12:00:00Z", "$350.50", "With dollar sign"])
system_b_rows.append(["ENT-5077", rec, "LOC-04", "PAYMENT", "2026-11-06T12:00:00Z", "350.5", "Decimal without trailing zero"])

# Row 78: B reference has lowercase and leading/trailing whitespace "  rec-1078  "
rec = "REC-1078"
system_a_rows.append([rec, "LOC-07", "SETTLEMENT", "2026-11-07T12:00:00Z", "420.00", "Clean reference"])
system_b_rows.append(["ENT-5078", "  rec-1078  ", "LOC-07", "SETTLEMENT", "2026-11-07T12:00:00Z", "420.00", "Whitespace and lowercase ref"])

# Row 79: B reference has format "REC_1079"
rec = "REC-1079"
system_a_rows.append([rec, "LOC-10", "REFUND", "2026-11-08T12:00:00Z", "89.99", "Standard hyphen"])
system_b_rows.append(["ENT-5079", "REC_1079", "LOC-10", "REFUND", "2026-11-08T12:00:00Z", "89.99", "Underscore separator"])

# Row 80: B reference has format "REC#1080"
rec = "REC-1080"
system_a_rows.append([rec, "LOC-02", "PAYMENT", "2026-11-09T12:00:00Z", "550.00", "Standard"])
system_b_rows.append(["ENT-5080", "REC#1080", "LOC-02", "PAYMENT", "2026-11-09T12:00:00Z", "550.00", "Hash prefix notation"])

# Row 81: Both have "0.00" and "0"
rec = "REC-1081"
system_a_rows.append([rec, "LOC-05", "ADJUSTMENT", "2026-11-10T12:00:00Z", "0.00", "Zero balance"])
system_b_rows.append(["ENT-5081", rec, "LOC-05", "ADJUSTMENT", "2026-11-10T12:00:00Z", "0", "Single zero"])

# Row 82: Reference written as "rec-1082" with surrounding quotes or spaces
rec = "REC-1082"
system_a_rows.append([rec, "LOC-08", "TRANSFER", "2026-11-11T12:00:00Z", "715.25", "Standard"])
system_b_rows.append(["ENT-5082", "rec-1082", "LOC-08", "TRANSFER", "2026-11-11T12:00:00Z", "715.250", "Extra trailing decimal zero"])

# Row 83: Positive signed "+450.00" vs "450.00"
rec = "REC-1083"
system_a_rows.append([rec, "LOC-11", "PAYMENT", "2026-11-12T12:00:00Z", "+450.00", "Signed positive"])
system_b_rows.append(["ENT-5083", rec, "LOC-11", "PAYMENT", "2026-11-12T12:00:00Z", "450.00", "Unsigned positive"])

# Row 84: Reference written as "REC 1084" (space separator)
rec = "REC-1084"
system_a_rows.append([rec, "LOC-03", "SETTLEMENT", "2026-11-13T12:00:00Z", "310.10", "Hyphenated"])
system_b_rows.append(["ENT-5084", "REC 1084", "LOC-03", "SETTLEMENT", "2026-11-13T12:00:00Z", "310.10", "Space separated"])

# Row 85: Clean agreement with empty notes
rec = "REC-1085"
system_a_rows.append([rec, "LOC-06", "REFUND", "2026-11-14T12:00:00Z", "95.00", ""])
system_b_rows.append(["ENT-5085", rec, "LOC-06", "REFUND", "2026-11-14T12:00:00Z", "95.00", ""])

# 86-93: MISSING_IN_SYSTEM_B (Exists in A, not in B) -> 8 records in A
for i in range(86, 94):
    rec_id = f"REC-{1000 + i}"
    loc = loc_keys[(i - 1) % len(loc_keys)]
    val = round(100.0 + i * 5.5, 2)
    system_a_rows.append([rec_id, loc, "PAYMENT", "2026-11-15T14:00:00Z", f"{val:.2f}", f"Missing in B {rec_id}"])

# 94-105: VALUE_MISMATCH (Same record, different values) -> 12 records
mismatch_cases = [
    (94, "150.00", "250.00", "LOC-01"),
    (95, "1200.50", "1100.50", "LOC-04"),
    (96, "45.00", "450.00", "LOC-07"),
    (97, "300.00", "305.00", "LOC-10"),
    (98, "99.99", "199.99", "LOC-02"),
    (99, "620.00", "62.00", "LOC-05"),
    (100, "1500.00", "1499.00", "LOC-08"),
    (101, "75.50", "85.50", "LOC-11"),
    (102, "500.00", "550.00", "LOC-03"),
    (103, "210.00", "215.00", "LOC-06"),
    (104, "880.00", "888.00", "LOC-09"),
    (105, "1000.00", "2000.00", "LOC-12"),
]
for idx, val_a, val_b, loc in mismatch_cases:
    rec_id = f"REC-{1000 + idx}"
    system_a_rows.append([rec_id, loc, "TRANSFER", "2026-11-16T10:00:00Z", val_a, "System A recorded value"])
    system_b_rows.append([f"ENT-{5000 + idx}", rec_id, loc, "TRANSFER", "2026-11-16T10:00:00Z", val_b, "System B reported different value"])

# 106-112: DUPLICATE_SYSTEM_B_ENTRY
# Records in A: 106-112 (7 records)
# System B has 2 entries for each of these!
for idx in range(106, 113):
    rec_id = f"REC-{1000 + idx}"
    loc = loc_keys[(idx - 1) % len(loc_keys)]
    val = round(200.0 + idx * 2.1, 2)
    system_a_rows.append([rec_id, loc, "PAYMENT", "2026-11-17T11:00:00Z", f"{val:.2f}", f"Single A record {rec_id}"])
    
    # First entry in B
    system_b_rows.append([f"ENT-{5000 + idx}_1", rec_id, loc, "PAYMENT", "2026-11-17T11:00:00Z", f"{val:.2f}", "First duplicate entry in B"])
    # Second entry in B (slightly different entry id)
    system_b_rows.append([f"ENT-{5000 + idx}_2", rec_id, loc, "PAYMENT", "2026-11-17T11:05:00Z", f"{val:.2f}", "Second duplicate entry in B"])

# 113-116: Dirty Unparseable / Blank values in A & B (Survive importer without silently dropping)
# 113: A has "N/A" value, B has "500.00"
rec = "REC-1113"
system_a_rows.append([rec, "LOC-01", "SETTLEMENT", "2026-11-18T09:00:00Z", "N/A", "Unparseable string in A"])
system_b_rows.append(["ENT-5113", rec, "LOC-01", "SETTLEMENT", "2026-11-18T09:00:00Z", "500.00", "Valid in B"])

# 114: A has "600.00", B has "PENDING"
rec = "REC-1114"
system_a_rows.append([rec, "LOC-04", "PAYMENT", "2026-11-18T10:00:00Z", "600.00", "Valid in A"])
system_b_rows.append(["ENT-5114", rec, "LOC-04", "PAYMENT", "2026-11-18T10:00:00Z", "PENDING", "Unparseable status string in B value"])

# 115: A has blank value "", B has "100.00"
rec = "REC-1115"
system_a_rows.append([rec, "LOC-07", "REFUND", "2026-11-18T11:00:00Z", "", "Empty value cell in A"])
system_b_rows.append(["ENT-5115", rec, "LOC-07", "REFUND", "2026-11-18T11:00:00Z", "100.00", "Has value in B"])

# 116: Unknown location LOC-99 (Not in locations.csv -> Tenant unresolved)
rec = "REC-1116"
system_a_rows.append([rec, "LOC-99", "TRANSFER", "2026-11-18T12:00:00Z", "750.00", "Unmapped location in A"])
system_b_rows.append(["ENT-5116", rec, "LOC-99", "TRANSFER", "2026-11-18T12:00:00Z", "750.00", "Unmapped location in B"])

# 117-120: Remaining rows for A to reach exactly 120 rows
# 117: Blank location in A
rec = "REC-1117"
system_a_rows.append([rec, "", "PAYMENT", "2026-11-19T08:00:00Z", "320.00", "Missing location in A"])
system_b_rows.append(["ENT-5117", rec, "LOC-02", "PAYMENT", "2026-11-19T08:00:00Z", "320.00", "Location exists in B"])

# 118: Clean agreement
rec = "REC-1118"
system_a_rows.append([rec, "LOC-05", "SETTLEMENT", "2026-11-19T09:00:00Z", "410.00", "Clean"])
system_b_rows.append(["ENT-5118", rec, "LOC-05", "SETTLEMENT", "2026-11-19T09:00:00Z", "410.00", "Clean"])

# 119: Clean agreement
rec = "REC-1119"
system_a_rows.append([rec, "LOC-08", "REFUND", "2026-11-19T10:00:00Z", "180.00", "Clean"])
system_b_rows.append(["ENT-5119", rec, "LOC-08", "REFUND", "2026-11-19T10:00:00Z", "180.00", "Clean"])

# 120: Clean agreement
rec = "REC-1120"
system_a_rows.append([rec, "LOC-11", "PAYMENT", "2026-11-19T11:00:00Z", "990.00", "Clean final row"])
system_b_rows.append(["ENT-5120", rec, "LOC-11", "PAYMENT", "2026-11-19T11:00:00Z", "990.00", "Clean final row"])

# Now check B row count:
# 1-75 (75 rows) + 76-85 (10 rows) + 94-105 (12 rows) + 106-112 (7*2 = 14 rows) + 113-120 (8 rows)
# Current B count = 75 + 10 + 12 + 14 + 8 = 119 rows!
# We need ORPHAN_SYSTEM_B_ENTRY!
# Let's adjust B: Add Orphan entries pointing to non-existent System A records!
# To make exactly 120 rows for B, let's replace some clean B entries with ORPHAN entries, or let's verify exact counts:
# Let's ensure:
# len(system_a_rows) == 120
# len(system_b_rows) == 120
# Exactly 120 on each side!

# Let's rebuild B cleanly to have exactly 120 rows with orphans:
b_entries = []
# 1-65: Clean agreement (65 rows)
for i in range(1, 66):
    rec_id = f"REC-{1000 + i}"
    loc = loc_keys[(i - 1) % len(loc_keys)]
    val = round(50.0 + (i * 13.7) % 850.0, 2)
    ev_type = ["PAYMENT", "TRANSFER", "REFUND", "SETTLEMENT"][i % 4]
    ts = f"2026-11-{(i % 25) + 1:02d}T10:15:00Z"
    b_entries.append([f"ENT-{5000 + i}", rec_id, loc, ev_type, ts, f"{val:.2f}", f"Entry for {rec_id}"])

# 66-77: ORPHAN_SYSTEM_B_ENTRY (12 entries pointing to non-existent records in A like REC-9001..REC-9012)
for idx in range(66, 78):
    orphan_ref = f"REC-{9000 + (idx - 65)}"
    loc = loc_keys[(idx - 1) % len(loc_keys)]
    val = round(150.0 + idx * 4.2, 2)
    b_entries.append([f"ENT-{5000 + idx}", orphan_ref, loc, "PAYMENT", "2026-11-20T14:00:00Z", f"{val:.2f}", "Orphan entry pointing to non-existent record"])

# 76-85: Non-errors (10 entries)
non_error_b = [
    ("ENT-5076", "REC-1076", "LOC-01", "TRANSFER", "2026-11-05T12:00:00Z", "1200", "Plain integer string"),
    ("ENT-5077", "REC-1077", "LOC-04", "PAYMENT", "2026-11-06T12:00:00Z", "350.5", "Decimal without trailing zero"),
    ("ENT-5078", "  rec-1078  ", "LOC-07", "SETTLEMENT", "2026-11-07T12:00:00Z", "420.00", "Whitespace and lowercase ref"),
    ("ENT-5079", "REC_1079", "LOC-10", "REFUND", "2026-11-08T12:00:00Z", "89.99", "Underscore separator"),
    ("ENT-5080", "REC#1080", "LOC-02", "PAYMENT", "2026-11-09T12:00:00Z", "550.00", "Hash prefix notation"),
    ("ENT-5081", "REC-1081", "LOC-05", "ADJUSTMENT", "2026-11-10T12:00:00Z", "0", "Single zero"),
    ("ENT-5082", "rec-1082", "LOC-08", "TRANSFER", "2026-11-11T12:00:00Z", "715.250", "Extra trailing decimal zero"),
    ("ENT-5083", "REC-1083", "LOC-11", "PAYMENT", "2026-11-12T12:00:00Z", "450.00", "Unsigned positive"),
    ("ENT-5084", "REC 1084", "LOC-03", "SETTLEMENT", "2026-11-13T12:00:00Z", "310.10", "Space separated"),
    ("ENT-5085", "REC-1085", "LOC-06", "REFUND", "2026-11-14T12:00:00Z", "95.00", ""),
]
for row in non_error_b:
    b_entries.append(list(row))

# 86-93 in A are MISSING IN B -> No entries in B!

# 94-105: VALUE_MISMATCH (12 entries)
for idx, val_a, val_b, loc in mismatch_cases:
    rec_id = f"REC-{1000 + idx}"
    b_entries.append([f"ENT-{5000 + idx}", rec_id, loc, "TRANSFER", "2026-11-16T10:00:00Z", val_b, "System B reported different value"])

# 106-111: DUPLICATE_SYSTEM_B_ENTRY (6 records in A * 2 entries = 12 entries in B)
for idx in range(106, 112):
    rec_id = f"REC-{1000 + idx}"
    loc = loc_keys[(idx - 1) % len(loc_keys)]
    val = round(200.0 + idx * 2.1, 2)
    b_entries.append([f"ENT-{5000 + idx}_A", rec_id, loc, "PAYMENT", "2026-11-17T11:00:00Z", f"{val:.2f}", "First duplicate entry in B"])
    b_entries.append([f"ENT-{5000 + idx}_B", rec_id, loc, "PAYMENT", "2026-11-17T11:05:00Z", f"{val:.2f}", "Second duplicate entry in B"])

# 112: Clean agreement
b_entries.append(["ENT-5112", "REC-1112", "LOC-12", "PAYMENT", "2026-11-17T15:00:00Z", "430.00", "Clean"])
# In A, let's ensure REC-1112 exists
# (we already had 106-112, let's fix 112 in A to be clean)

# 113-120: Dirty / Edge entries (8 entries)
b_entries.append(["ENT-5113", "REC-1113", "LOC-01", "SETTLEMENT", "2026-11-18T09:00:00Z", "500.00", "Valid in B"])
b_entries.append(["ENT-5114", "REC-1114", "LOC-04", "PAYMENT", "2026-11-18T10:00:00Z", "PENDING", "Unparseable status string in B value"])
b_entries.append(["ENT-5115", "REC-1115", "LOC-07", "REFUND", "2026-11-18T11:00:00Z", "100.00", "Has value in B"])
b_entries.append(["ENT-5116", "REC-1116", "LOC-99", "TRANSFER", "2026-11-18T12:00:00Z", "750.00", "Unmapped location in B"])
b_entries.append(["ENT-5117", "REC-1117", "LOC-02", "PAYMENT", "2026-11-19T08:00:00Z", "320.00", "Location exists in B"])
b_entries.append(["ENT-5118", "REC-1118", "LOC-05", "SETTLEMENT", "2026-11-19T09:00:00Z", "410.00", "Clean"])
b_entries.append(["ENT-5119", "REC-1119", "LOC-08", "REFUND", "2026-11-19T10:00:00Z", "180.00", "Clean"])
b_entries.append(["ENT-5120", "REC-1120", "LOC-11", "PAYMENT", "2026-11-19T11:00:00Z", "990.00", "Clean final row"])

# Let's check counts
assert len(system_a_rows) == 120, f"System A rows: {len(system_a_rows)}"
assert len(b_entries) == 120, f"System B rows: {len(b_entries)}"

# Write system_a.csv
with open("data/system_a.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["record_id", "location_id", "event_type", "timestamp", "value", "notes"])
    for row in system_a_rows:
        writer.writerow(row)

with open("system_a.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["record_id", "location_id", "event_type", "timestamp", "value", "notes"])
    for row in system_a_rows:
        writer.writerow(row)

# Write system_b.csv
with open("data/system_b.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["entry_id", "record_ref", "location_id", "event_type", "timestamp", "value", "notes"])
    for row in b_entries:
        writer.writerow(row)

with open("system_b.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["entry_id", "record_ref", "location_id", "event_type", "timestamp", "value", "notes"])
    for row in b_entries:
        writer.writerow(row)

print(f"Generated system_a.csv: {len(system_a_rows)} rows")
print(f"Generated system_b.csv: {len(b_entries)} rows")
print(f"Generated locations.csv: {len(locations_data)} rows")

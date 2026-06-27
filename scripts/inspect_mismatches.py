import sqlite3, json
from pathlib import Path
DB = Path(__file__).resolve().parent.parent / 'cprp.db'
conn = sqlite3.connect(str(DB))
cur = conn.cursor()
cur.execute("SELECT id,run_type,status,total_skus,exact_matches,mismatches,critical_mismatches,run_date FROM reconciliation_runs ORDER BY run_date DESC LIMIT 1")
row = cur.fetchone()
if not row:
    print(json.dumps({"error":"no_run_found"}))
    exit(0)
run_id = row[0]
cur.execute("SELECT COUNT(*) FROM comparison_details WHERE run_id=? AND severity!='Exact Match'", (run_id,))
total_rows = cur.fetchone()[0]
cur.execute("SELECT marketplace, COUNT(*) FROM comparison_details WHERE run_id=? AND severity!='Exact Match' GROUP BY marketplace ORDER BY COUNT(*) DESC", (run_id,))
per_platform = cur.fetchall()
cur.execute("SELECT COUNT(DISTINCT sku) FROM comparison_details WHERE run_id=? AND severity!='Exact Match'", (run_id,))
unique_skus = cur.fetchone()[0]
output = {
    "run": {
        "id": run_id,
        "run_type": row[1],
        "status": row[2],
        "total_skus": row[3],
        "exact_matches": row[4],
        "mismatches_field": row[5],
        "critical": row[6],
        "run_date": row[7]
    },
    "total_mismatch_rows": total_rows,
    "per_platform": per_platform,
    "unique_mismatch_skus": unique_skus
}
print(json.dumps(output, default=str, indent=2))

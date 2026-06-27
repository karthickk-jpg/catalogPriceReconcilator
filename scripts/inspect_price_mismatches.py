import sqlite3, json
from pathlib import Path
DB = Path(__file__).resolve().parent.parent / 'cprp.db'
conn = sqlite3.connect(str(DB))
cur = conn.cursor()
cur.execute("SELECT id FROM reconciliation_runs ORDER BY run_date DESC LIMIT 1")
run_id = cur.fetchone()[0]
cur.execute("SELECT marketplace, COUNT(*) FROM comparison_details WHERE run_id=? AND severity IN ('Low Mismatch','Medium Mismatch','Critical Mismatch') GROUP BY marketplace ORDER BY COUNT(*) DESC", (run_id,))
per_platform = cur.fetchall()
cur.execute("SELECT COUNT(*) FROM comparison_details WHERE run_id=? AND severity IN ('Low Mismatch','Medium Mismatch','Critical Mismatch')", (run_id,))
total_price_mismatches = cur.fetchone()[0]
cur.execute("SELECT COUNT(DISTINCT sku) FROM comparison_details WHERE run_id=? AND severity IN ('Low Mismatch','Medium Mismatch','Critical Mismatch')", (run_id,))
unique_skus = cur.fetchone()[0]
output = {
    'run_id': run_id,
    'total_price_mismatches': total_price_mismatches,
    'per_platform_price_mismatches': per_platform,
    'unique_mismatch_skus': unique_skus
}
print(json.dumps(output, default=str, indent=2))

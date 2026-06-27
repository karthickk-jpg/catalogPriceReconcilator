import sqlite3, json
from pathlib import Path
DB = Path(__file__).resolve().parent.parent / 'cprp.db'
conn = sqlite3.connect(str(DB))
cur = conn.cursor()
cur.execute("SELECT id,total_skus,exact_matches FROM reconciliation_runs ORDER BY run_date DESC LIMIT 1")
row = cur.fetchone()
if not row:
    print('no run')
    exit(0)
run_id, total_skus, exact_matches_field = row
cur.execute("SELECT COUNT(DISTINCT sku) FROM comparison_details WHERE run_id=? AND severity='Exact Match'", (run_id,))
exact_unique = cur.fetchone()[0]
match_rate_field = (exact_matches_field / total_skus * 100) if total_skus else None
match_rate_unique = (exact_unique / total_skus * 100) if total_skus else None
out = {
    'run_id': run_id,
    'total_skus': total_skus,
    'exact_matches_field': exact_matches_field,
    'exact_unique_skus': exact_unique,
    'match_rate_field_percent': round(match_rate_field,1) if match_rate_field is not None else None,
    'match_rate_unique_percent': round(match_rate_unique,1) if match_rate_unique is not None else None,
}
print(json.dumps(out, indent=2))

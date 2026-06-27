import sqlite3
from pathlib import Path
import sys
import pandas as pd

# ensure project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.helpers import normalize_sku

DB = Path(__file__).resolve().parent.parent / 'cprp.db'
conn = sqlite3.connect(str(DB))
cur = conn.cursor()
cur.execute("SELECT id FROM reconciliation_runs ORDER BY run_date DESC LIMIT 1")
run_id = cur.fetchone()[0]
cur.execute("SELECT filepath, row_count FROM uploaded_files WHERE run_id=? AND platform='WMS' LIMIT 1", (run_id,))
res = cur.fetchone()
if not res:
    print('No WMS uploaded file found for run', run_id)
    exit(1)
filepath, row_count = res
print('uploaded file path:', filepath)
print('uploaded row_count stored:', row_count)

# This utility relied on reading an Excel workbook. In Google Sheets-only mode
# uploaded file 'filepath' no longer points to a local workbook path. Mark as
# deprecated and exit.
print('inspect_wms_normalization is deprecated in Google Sheets mode.')
print('This script required a local workbook file; uploaded file records now reference a Google Sheet ID.')
exit(0)

raw_rows = len(df)
sku_col = None
# heuristics to find SKU column
candidates = [c for c in df.columns if str(c).strip().lower() in ('sku','seller sku','seller-sku','seller_sku','item code','article','article code','fsn','code','id')]
if candidates:
    sku_col = candidates[0]
else:
    # fall back to first column
    sku_col = df.columns[0]

norms = df[sku_col].astype(object).apply(normalize_sku)
blank_norm = (norms == '').sum()
unique_norms = norms[norms != ''].nunique()
duplicates = raw_rows - blank_norm - unique_norms
print('\nRaw rows in sheet:', raw_rows)
print('Blank/empty normalized SKUs:', blank_norm)
print('Unique normalized SKUs (non-empty):', unique_norms)
print('Duplicate normalized SKUs removed:', duplicates)

# show sample of blank SKUs
if blank_norm > 0:
    print('\nSample rows with blank SKU:')
    print(df[norms == ''].head(5).to_string(index=False))

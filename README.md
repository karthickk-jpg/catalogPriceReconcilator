# Catalog Price Reconciliation Portal (CPRP)

A single-page Streamlit dashboard that compares WMS catalog prices against marketplace listings using live data from Google Sheets.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Configuration

Set these values in `.streamlit/secrets.toml` (local) or Streamlit Cloud secrets:

| Key | Description |
|-----|-------------|
| `CPRP_GOOGLE_SHEET_ID` | Google Spreadsheet ID |
| `CPRP_SERVICE_ACCOUNT_JSON_CONTENT` | Full service account JSON as a string |

For local development you can also use environment variables with the same names. See `.streamlit/secrets.toml.example`.

The Google Sheet must contain tabs named: `WMS`, `Amazon`, `Flipkart`, `Myntra`, `Shopify`, `Eternz`, `Tata Cliq`.

## Dashboard flow

1. Click **Refresh dashboard**
2. CPRP reads the latest Google Sheets data
3. The comparison engine reconciles WMS vs marketplace prices
4. KPIs, filters, and the mismatch table update with live results

## Deploy on Streamlit Cloud

1. Push this repository to GitHub
2. Create a new Streamlit Cloud app pointing to `app.py`
3. Add `CPRP_GOOGLE_SHEET_ID` and `CPRP_SERVICE_ACCOUNT_JSON_CONTENT` in app secrets
4. Deploy — no API server, database, or Docker required

## Project structure

```
CPRP/
├── app.py
├── requirements.txt
├── config/
├── core/
├── services/
├── utils/
├── views/
│   └── dashboard.py
└── .streamlit/
    └── secrets.toml.example
```

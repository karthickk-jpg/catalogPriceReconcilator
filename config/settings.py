SUPPORTED_PLATFORMS = ["Amazon", "Flipkart", "Myntra", "Shopify", "Eternz", "Tata Cliq"]

PLATFORM_SHEETS = {
    "WMS": "WMS",
    "Amazon": "Amazon",
    "Flipkart": "Flipkart",
    "Myntra": "Myntra",
    "Shopify": "Shopify",
    "Eternz": "Eternz",
    "Tata Cliq": "Tata Cliq",
}

COLUMN_MAPPINGS = {
    "WMS": {"sku": "SKU", "price": "WMS Price"},
    "Amazon": {"sku": "SKU", "price": "Selling Price"},
    "Flipkart": {"sku": "SKU", "price": "Selling Price"},
    "Myntra": {"sku": "SKU", "price": "MRP"},
    "Shopify": {"sku": "SKU", "price": "Price"},
    "Eternz": {"sku": "SKU", "price": "Price"},
    "Tata Cliq": {"sku": "SKU", "price": "Price"},
}

DEFAULT_LOW_THRESHOLD = 1.0
DEFAULT_MEDIUM_THRESHOLD = 5.0

SKU_KEYWORDS = [
    "sku",
    "seller sku",
    "seller-sku",
    "seller_sku",
    "item code",
    "item_code",
    "article",
    "article code",
    "article_code",
    "article number",
    "article_number",
    "fsn",
    "product code",
    "product_code",
    "code",
    "barcode",
    "id",
]

PRICE_KEYWORDS = [
    "price",
    "selling price",
    "selling_price",
    "sale price",
    "sale_price",
    "mrp",
    "listing price",
    "listing_price",
    "retail price",
    "retail_price",
    "rate",
    "unit price",
    "unit_price",
    "amount",
]

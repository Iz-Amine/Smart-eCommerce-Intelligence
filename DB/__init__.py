"""
Database package for e-commerce scraping.
"""

from .db import SessionLocal, init_db
from .models import ScrapingLog, Product, Store
from .db_utils import (
    get_all_stores, get_or_create_store,
    get_store_products, get_store_stats, log_scraping,
    add_or_update_product
)

__all__ = [
    'SessionLocal', 'init_db',
    'ScrapingLog', 'Product', 'Store',
    'get_all_stores', 'get_or_create_store',
    'get_store_products', 'get_store_stats', 'log_scraping',
    'add_or_update_product'
] 
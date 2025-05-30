import streamlit as st
import pandas as pd
from DB.db import SessionLocal
from DB.models import ScrapingLog, Product, Store
from DB.db_utils import get_all_stores, get_or_create_store, get_store_products, get_store_stats, log_scraping
import datetime
from datetime import timezone # Import timezone
import time

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_data():
    """Load data from the database with pagination and caching"""
    db = SessionLocal()
    try:
        # Get scraping logs with pagination
        logs = db.query(ScrapingLog).order_by(ScrapingLog.scraped_at.desc()).limit(1000).all()
        logs_data = [{
            'id': log.id,
            'store_id': log.store_id,
            'scraped_at': log.scraped_at,
            'status': log.status,
            'product_count': log.product_count,
            'duration_seconds': log.duration_seconds,
            'error_message': log.error_message
        } for log in logs]
        
        # Get products with pagination
        products = db.query(Product).limit(1000).all()
        products_data = [{
            'id': p.id,
            'store_id': p.store_id,
            'title': p.title,
            'price': p.price if p.price else 0.0,
            'max_price': p.max_price if p.max_price else 0.0,
            'available': p.available if p.available is not None else True,
            'total_inventory': p.total_inventory if p.total_inventory else 0,
            'product_type': p.product_type or '',
            'vendor': p.vendor or '',
            'created_at': p.created_at,
            'updated_at': p.updated_at,
            'image_url': p.image_url or '',
            'description': p.description or '',
            'handle': p.handle or '',
            'currency': p.currency or 'USD',
            'tags': p.tags or [],
            'categories': p.categories or [],
            'options': p.options or [],
            'variant_count': p.variant_count or 1,
            'image_count': p.image_count or 0
        } for p in products]
        
        # Get stores
        stores = db.query(Store).all()
        stores_data = [{
            'id': s.id,
            'name': s.name,
            'url': s.url,
            'domain': s.domain,
            'active_surveillance': s.active_surveillance,
            'created_at': s.created_at,
            'updated_at': s.updated_at
        } for s in stores]
        
        return pd.DataFrame(logs_data), pd.DataFrame(products_data), pd.DataFrame(stores_data)
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    finally:
        db.close()

def get_related_products(product, products_df, n=4):
    """Get related products based on category, vendor, and price range"""
    if products_df.empty:
        return pd.DataFrame()
    
    related = products_df[
        (products_df['id'] != product['id']) &  # Exclude current product
        (
            (products_df['product_type'] == product['product_type']) |
            (products_df['vendor'] == product['vendor']) |
            (
                (products_df['price'] >= product['price'] * 0.7) &
                (products_df['price'] <= product['price'] * 1.3)
            )
        )
    ]
    return related.head(n)

def toggle_surveillance(store_id: int, active: bool):
    """Toggle surveillance for a store"""
    db = SessionLocal()
    try:
        store = db.query(Store).filter(Store.id == store_id).first()
        if store:
            store.active_surveillance = active
            store.updated_at = datetime.datetime.now(timezone.utc) # Use timezone-aware datetime
            db.commit()
            load_data.clear() # Clear the cache
            return True
        else:
            print(f"Store with ID {store_id} not found.") # Add debug print
            return False
    except Exception as e:
        print(f"Error toggling surveillance for store {store_id}: {e}") # Add debug print
        db.rollback() # Rollback changes on error
        return False
    finally:
        db.close() 
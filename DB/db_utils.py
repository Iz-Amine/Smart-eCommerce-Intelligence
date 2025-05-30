from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from .models import Store, Product, ScrapingLog, ProductChangeLog
from .db import SessionLocal
import dateutil.parser
import json
import logging

logger = logging.getLogger(__name__)

def parse_datetime(date_str: Optional[str]) -> Optional[datetime]:
    """Convert string date to datetime object"""
    if not date_str:
        return None
    try:
        return dateutil.parser.parse(date_str)
    except (ValueError, TypeError):
        return None

# Gestion des Stores
# 1.  récupérer tous les stores
def get_all_stores(db: Session) -> List[Store]:
    """Get all stores with their product counts"""
    try:
        return db.query(Store).all()
    except Exception as e:
        logger.error(f"Error getting all stores: {e}")
        return []

# 2.  récupérer ou créer un store
def get_or_create_store(db: Session, name: str, url: str, domain: Optional[str] = None) -> Store:
    """Get existing store or create new one if doesn't exist"""
    try:
        store = db.query(Store).filter(Store.url == url).first()
        if not store:
            store = Store(
                name=name,
                url=url,
                domain=domain or url.split('//')[-1].split('/')[0]
            )
            db.add(store)
            db.commit()
            db.refresh(store)
        return store
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating/getting store: {e}")
        raise

# 3.  récupérer les produits d'un store
def get_store_products(db: Session, store_id: int, limit: int = 100) -> List[Product]:
    """Get products for a specific store"""
    try:
        return db.query(Product).filter(Product.store_id == store_id).limit(limit).all()
    except Exception as e:
        logger.error(f"Error getting store products: {e}")
        return []

# 4.  récupérer les statistiques d'un store
def get_store_stats(db: Session, store_id: int) -> Dict[str, Any]:
    """Get statistics for a store"""
    try:
        products = db.query(Product).filter(Product.store_id == store_id)
        total_products = products.count()
        available_products = products.filter(Product.available == True).count()
        avg_price = db.query(func.avg(Product.price)).filter(Product.store_id == store_id).scalar() or 0
        
        return {
            'total_products': total_products,
            'available_products': available_products,
            'average_price': round(avg_price, 2),
            'last_scraped': products.order_by(Product.scraped_at.desc()).first().scraped_at if total_products > 0 else None
        }
    except Exception as e:
        logger.error(f"Error getting store stats: {e}")
        return {
            'total_products': 0,
            'available_products': 0,
            'average_price': 0,
            'last_scraped': None
        }

# 5.  supprimer un store et tous ses produits
def delete_store_and_products(db: Session, store_id: int) -> bool:
    """Delete a store and all its products"""
    try:
        store = db.query(Store).filter(Store.id == store_id).first()
        if store:
            db.delete(store)
            db.commit()
            return True
        return False
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting store and products: {e}")
        return False



# Gestion des Produits
# 1.  ajouter ou mettre à jour un produit et enregistrer les changements
def add_or_update_product(db: Session, store_id: int, product_data: Dict[str, Any], scraping_log_id: Optional[int] = None) -> Product:
    """Add new product or update existing one and log changes"""
    try:
        # Extract Shopify ID from the data
        shopify_id = str(product_data.get('id', '')) if product_data.get('id') else None
        
        # Handle the case where shopify_id might be passed directly
        if not shopify_id and product_data.get('shopify_id'):
            shopify_id = str(product_data.get('shopify_id'))
        
        # Try to find existing product by shopify_id
        product = None
        if shopify_id:
            product = db.query(Product).filter(
                Product.store_id == store_id,
                Product.shopify_id == shopify_id
            ).first()
        
        # If no product found and we have other identifying info, try to find by title + store
        if not product and product_data.get('title'):
            product = db.query(Product).filter(
                Product.store_id == store_id,
                Product.title == product_data['title']
            ).first()
        
        is_new_product = product is None
        
        if not product:
            # Create new product
            product = Product(store_id=store_id)
        
        # Store original values for comparison if product exists
        original_product_data = {}
        if not is_new_product:
            original_product_data = {key: getattr(product, key, None) for key in product_data.keys() if hasattr(product, key) and key != 'id'}
        
        # Convert date strings to datetime objects
        date_fields = ['created_at', 'updated_at', 'published_at']
        for field in date_fields:
            if field in product_data:
                product_data[field] = parse_datetime(product_data[field])
        
        # Update product fields and detect changes
        changes = []
        for key, new_value in product_data.items():
            if hasattr(product, key):
                # Skip the auto-incremented id field
                if key == 'id':
                    continue

                old_value = original_product_data.get(key) if not is_new_product else None

                # Handle JSON fields separately for comparison
                if key in ['tags', 'options', 'categories', 'collection_ids']:
                    # Ensure values are lists for consistent comparison
                    if isinstance(old_value, str) and old_value:
                        try:
                            old_value_processed = json.loads(old_value)
                        except json.JSONDecodeError:
                            old_value_processed = []
                    elif isinstance(old_value, list):
                        old_value_processed = old_value
                    else:
                        old_value_processed = []
                    
                    if isinstance(new_value, str) and new_value:
                        try:
                            new_value_processed = json.loads(new_value)
                        except json.JSONDecodeError:
                            new_value_processed = []
                    elif isinstance(new_value, list):
                        new_value_processed = new_value
                    else:
                        new_value_processed = []

                    if sorted(str(x) for x in old_value_processed) != sorted(str(x) for x in new_value_processed):
                        if not is_new_product:  # Only log changes for existing products
                            changes.append({
                                'field': key,
                                'old': json.dumps(old_value_processed) if old_value_processed else None,
                                'new': json.dumps(new_value_processed) if new_value_processed else None
                            })
                        setattr(product, key, new_value_processed)

                # Handle other fields
                elif old_value != new_value:
                    if not is_new_product:  # Only log changes for existing products
                        changes.append({
                            'field': key,
                            'old': str(old_value) if old_value is not None else None,
                            'new': str(new_value) if new_value is not None else None
                        })
                    setattr(product, key, new_value)

        # Set shopify_id from the original id if not already set
        if shopify_id and not getattr(product, 'shopify_id', None):
            product.shopify_id = shopify_id

        product.scraped_at = datetime.utcnow()

        # Add product to session
        db.add(product)
        
        try:
            # Use flush to get the product.id if it's a new product, but don't commit yet
            db.flush()
        except IntegrityError as e:
            # Handle unique constraint violation
            db.rollback()
            
            if "UNIQUE constraint failed: products.shopify_id" in str(e):
                logger.warning(f"Product with shopify_id {shopify_id} already exists. Attempting to update existing product.")
                
                # Try to find the existing product and update it
                existing_product = db.query(Product).filter(
                    Product.shopify_id == shopify_id
                ).first()
                
                if existing_product:
                    # Update the existing product instead
                    for key, new_value in product_data.items():
                        if hasattr(existing_product, key) and key not in ['id', 'shopify_id']:
                            setattr(existing_product, key, new_value)
                    
                    existing_product.scraped_at = datetime.utcnow()
                    db.add(existing_product)
                    db.commit()
                    db.refresh(existing_product)
                    return existing_product
                else:
                    raise Exception(f"Unique constraint error but cannot find existing product with shopify_id: {shopify_id}")
            else:
                # Re-raise other integrity errors
                raise

        # Log changes for existing products
        if changes and scraping_log_id is not None:
            for change in changes:
                change_log = ProductChangeLog(
                    product_id=product.id,
                    scraping_log_id=scraping_log_id,
                    changed_field=change['field'],
                    old_value=change['old'],
                    new_value=change['new']
                )
                db.add(change_log)

        # Commit the transaction
        db.commit()
        db.refresh(product)
        return product
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding/updating product: {e}")
        raise

# 2.  ajouter ou mettre à jour un produit et enregistrer les changements
def safe_get_or_create_product(db: Session, store_id: int, product_data: Dict[str, Any], scraping_log_id: Optional[int] = None) -> Optional[Product]:
    """
    Safely get or create a product with comprehensive error handling.
    Returns None if the operation fails.
    """
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            return add_or_update_product(db, store_id, product_data, scraping_log_id)
        except IntegrityError as e:
            retry_count += 1
            logger.warning(f"IntegrityError on attempt {retry_count}: {e}")
            
            if retry_count >= max_retries:
                logger.error(f"Failed to create/update product after {max_retries} attempts")
                return None
                
            # Wait a bit before retrying
            import time
            time.sleep(0.1 * retry_count)
            
        except Exception as e:
            logger.error(f"Unexpected error creating/updating product: {e}")
            return None
    
    return None

# 3.  nettoyer les doublons de produits
def cleanup_duplicate_products(db: Session) -> Dict[str, int]:
    """
    Clean up duplicate products by shopify_id, keeping the most recent one.
    Returns a summary of the cleanup operation.
    """
    try:
        # Find duplicate shopify_ids
        duplicates_query = db.query(Product.shopify_id).group_by(Product.shopify_id).having(func.count(Product.shopify_id) > 1)
        duplicate_shopify_ids = [row[0] for row in duplicates_query.all() if row[0]]
        
        removed_count = 0
        kept_count = 0
        
        for shopify_id in duplicate_shopify_ids:
            # Get all products with this shopify_id
            products = db.query(Product).filter(Product.shopify_id == shopify_id).order_by(Product.scraped_at.desc()).all()
            
            if len(products) > 1:
                # Keep the most recent one, delete the rest
                products_to_delete = products[1:]  # All except the first (most recent)
                
                for product in products_to_delete:
                    db.delete(product)
                    removed_count += 1
                
                kept_count += 1
        
        db.commit()
        
        return {
            'duplicate_shopify_ids_found': len(duplicate_shopify_ids),
            'products_removed': removed_count,
            'products_kept': kept_count
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error cleaning up duplicate products: {e}")
        return {
            'duplicate_shopify_ids_found': 0,
            'products_removed': 0,
            'products_kept': 0,
            'error': str(e)
        }
    
    


def import_from_csv(db: Session, store_name: str, store_url: str, csv_file_path: str) -> None:
    """Import products from CSV file to database"""
    import pandas as pd
    
    try:
        # Create or get store
        store = get_or_create_store(db, store_name, store_url)
        
        # Read CSV file
        df = pd.read_csv(csv_file_path)
        
        # Convert DataFrame rows to product records
        for _, row in df.iterrows():
            product_data = row.to_dict()
            try:
                add_or_update_product(db, store.id, product_data)
            except Exception as e:
                logger.error(f"Error importing product from CSV: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error importing from CSV: {e}")
        raise

# Gestion des Logs de Scraping
# 1. Fonction pour enregistrer les logs de scraping
def log_scraping(db: Session, store_id: int, product_count: int, status: str = 'success', error_message: str = None, duration_seconds: float = None):
    """Log scraping stats for a store."""
    try:
        log = ScrapingLog(
            store_id=store_id,
            product_count=product_count,
            status=status,
            error_message=error_message,
            duration_seconds=duration_seconds
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log
    except Exception as e:
        db.rollback()
        logger.error(f"Error logging scraping stats: {e}")
        raise


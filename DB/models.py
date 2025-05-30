from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, JSON, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Store(Base):
    __tablename__ = 'stores'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    url = Column(String(255), nullable=False, unique=True)
    domain = Column(String(255))
    active_surveillance = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship with products
    products = relationship("Product", back_populates="store", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Store(name='{self.name}', url='{self.url}', active_surveillance={self.active_surveillance})>"

class Product(Base):
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True, autoincrement=True)
    shopify_id = Column(String(255), nullable=True)  # Made nullable since not all products may have this
    woocommerce_id = Column(String(255), nullable=True)  # For WooCommerce products
    store_id = Column(Integer, ForeignKey('stores.id'), nullable=False)

    #Informations Produit de Base
    title = Column(String(255), nullable=False)
    handle = Column(String(255))
    description = Column(Text)
    short_description = Column(Text)

    # Données Financières et Stock
    price = Column(Float)
    max_price = Column(Float)
    currency = Column(String(10), default='USD')
    available = Column(Boolean, default=True)
    total_inventory = Column(Integer)

    # Catégorisation & Métadonnées
    product_type = Column(String(255))
    vendor = Column(String(255))
    tags = Column(JSON)  # Store tags as JSON array
    image_url = Column(String(512))
    image_count = Column(Integer)

    # Timestamps & Traçabilité
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    published_at = Column(DateTime)
    variant_count = Column(Integer)
    options = Column(JSON)  # Store options as JSON
    categories = Column(JSON)  # Store categories as JSON array
    collection_ids = Column(JSON)  # Store collection IDs as JSON array
    scraped_at = Column(DateTime, default=datetime.utcnow)

    # Relationship with store
    store = relationship("Store", back_populates="products")

    # Add unique constraints that make more sense
    __table_args__ = (
        # Shopify ID should be unique across the entire system (if present)
        UniqueConstraint('shopify_id', name='uq_shopify_id'),
        # WooCommerce ID should be unique across the entire system (if present)  
        UniqueConstraint('woocommerce_id', name='uq_woocommerce_id'),
        # Product title should be unique within a store (prevents obvious duplicates)
        UniqueConstraint('store_id', 'title', name='uq_store_title'),
    )

    def __repr__(self):
        return f"<Product(title='{self.title}', price={self.price}, shopify_id='{self.shopify_id}')>"

class ScrapingLog(Base):
    __tablename__ = 'scraping_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey('stores.id'), nullable=False)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    product_count = Column(Integer, default=0)
    status = Column(String(50), default='success')  # e.g., 'success', 'failure', 'partial_success'
    error_message = Column(Text, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    store = relationship("Store")

    def __repr__(self):
        return f"<ScrapingLog(store_id={self.store_id}, scraped_at={self.scraped_at}, status={self.status}, product_count={self.product_count})>"

class ProductChangeLog(Base):
    __tablename__ = 'product_change_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    scraping_log_id = Column(Integer, ForeignKey('scraping_logs.id'), nullable=False)
    changed_field = Column(String(255), nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    change_timestamp = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product")
    scraping_log = relationship("ScrapingLog")

    def __repr__(self):
        return f"<ProductChangeLog(product_id={self.product_id}, changed_field='{self.changed_field}')>"
    

# Analyse 
class TopKAnalysis(Base):
    __tablename__ = 'topk_analyses'

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey('stores.id'), nullable=True)  # Nullable si analyse multi-stores
    analysis_name = Column(String(255), nullable=False)  # Ex: "Top 20 - Electronics"
    
    # Paramètres de l'analyse
    k_value = Column(Integer, default=20)  # Nombre de top produits
    min_price = Column(Float, default=0.0)
    category_filter = Column(String(255), nullable=True)
    
    # Résultats
    total_analyzed = Column(Integer)
    avg_score = Column(Float)
    avg_price = Column(Float)
    availability_rate = Column(Float)
    
    # Métadonnées
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100), default='system')  # Pour futur multi-user
    
    # Relations
    store = relationship("Store")
    
    def __repr__(self):
        return f"<TopKAnalysis(name='{self.analysis_name}', k={self.k_value})>"

class TopKProduct(Base):
    __tablename__ = 'topk_products'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_id = Column(Integer, ForeignKey('topk_analyses.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    
    # Score et position
    final_score = Column(Float)
    rank_position = Column(Integer)  # 1, 2, 3...
    
    # Scores détaillés
    price_score = Column(Float)
    inventory_score = Column(Float)
    availability_score = Column(Float)
    image_score = Column(Float)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relations
    analysis = relationship("TopKAnalysis")
    product = relationship("Product")
    
    def __repr__(self):
        return f"<TopKProduct(rank={self.rank_position}, score={self.final_score})>"
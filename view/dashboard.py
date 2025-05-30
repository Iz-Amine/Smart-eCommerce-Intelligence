# Standard library imports
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Third-party imports
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json

# Local imports
try:
    sys.path.append(str(Path(__file__).parent.parent))
    from DB.db import SessionLocal, init_db
    from DB.models import ScrapingLog, Product, Store
    from DB.db_utils import (
        get_all_stores, get_or_create_store, 
        get_store_products, get_store_stats, log_scraping
    )
    from agents.ShopifyAgent import ShopifyAgent
    from view.analysis import add_mvp_analysis_tab
    # Dans la section des imports
    from compts.mcp_dashboard import show_mcp_dashboard
    from Analyse.simple_analyzer import SimpleTopKAnalyzer
    from Analyse.LLMEnricher import SimpleLLMEnricher
except ImportError as e:
    st.error(f"Error importing required modules: {e}")
    st.stop()

# Initialize database
init_db()

# Initialize components
analyzer = SimpleTopKAnalyzer()
llm_enricher = SimpleLLMEnricher()

def calculate_simple_data_score(product):
    """Calcule un score simple basé sur la qualité des données scrapées"""
    score = 0
    max_score = 100
    
    # Disponibilité (40 points)
    if product.get('available', True):
        score += 40
    
    # Stock/Variants (30 points)
    inventory = product.get('total_inventory', 0)
    variants = product.get('variant_count', 1)
    
    if inventory > 0:
        if inventory >= 20:
            score += 30
        elif inventory >= 10:
            score += 25
        elif inventory >= 5:
            score += 20
        else:
            score += 15
    elif variants > 1:
        if variants >= 5:
            score += 25
        elif variants >= 3:
            score += 20
        else:
            score += 15
    
    # Images (20 points)
    images = product.get('image_count', 0)
    if images >= 3:
        score += 20
    elif images >= 1:
        score += 15
    elif product.get('image_url'):
        score += 10
    
    # Contenu (10 points)
    title_len = len(str(product.get('title', '')))
    desc_len = len(str(product.get('description', '')))
    
    if title_len > 20:
        score += 4
    elif title_len > 10:
        score += 2
    
    if desc_len > 100:
        score += 4
    elif desc_len > 20:
        score += 2
    
    tags = product.get('tags', [])
    if tags and len(tags) > 0:
        score += 2
    
    return min(score, max_score)

def get_quality_level(score):
    """Retourne le niveau de qualité basé sur le score"""
    if score >= 80:
        return "Excellent", "🟢"
    elif score >= 60:
        return "Good", "🟡"
    elif score >= 40:
        return "Average", "🟠"
    else:
        return "Poor", "🔴"

def load_data():
    """Load data from the database with pagination and caching"""
    @st.cache_data(ttl=300)  # Cache for 5 minutes
    def get_data():
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
            products_data = []
            for p in products:
                product_dict = {
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
                }
                # Calculate data quality score
                product_dict['data_quality_score'] = calculate_simple_data_score(product_dict)
                products_data.append(product_dict)
            
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
    
    return get_data()

def scrape_store(url: str, category: str = None):
    """Scrape a new store"""
    db = SessionLocal()
    start_time = time.time()
    
    try:
        agent = ShopifyAgent(url, category)
        if agent.detect_platform():
            # Create or get store
            store = get_or_create_store(
                db,
                name=url.split('//')[1].split('.')[0].replace('-', ' ').title(),
                url=url,
                domain=url.split('//')[1].split('/')[0]
            )
            
            # Start scraping
            products = agent.scrape_products()
            
            if products:
                # Save products to database
                for product_data in products:
                    try:
                        from DB.db_utils import add_or_update_product
                        add_or_update_product(db, store.id, product_data)
                    except Exception as e:
                        st.warning(f"Error saving product: {e}")
                        continue
                
                # Log scraping success
                duration = time.time() - start_time
                log_scraping(db, store.id, len(products), 'success', duration_seconds=duration)
                
                return True, f"Successfully scraped {len(products)} products"
            else:
                return False, "No products found"
        else:
            return False, "Not a valid Shopify store"
    except Exception as e:
        # Log scraping failure
        duration = time.time() - start_time
        try:
            store = get_or_create_store(
                db,
                name=url.split('//')[1].split('.')[0].replace('-', ' ').title(),
                url=url,
                domain=url.split('//')[1].split('/')[0]
            )
            log_scraping(db, store.id, 0, 'failure', str(e), duration)
        except:
            pass
        return False, str(e)
    finally:
        db.close()

def toggle_surveillance(store_id: int, active: bool):
    """Toggle surveillance for a store"""
    db = SessionLocal()
    try:
        store = db.query(Store).filter(Store.id == store_id).first()
        if store:
            store.active_surveillance = active
            store.updated_at = datetime.utcnow()
            db.commit()
            return True
        return False
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

def show_product_details(product_id, products_df, stores_df):
    """Show detailed product information"""
    if products_df.empty:
        st.error("No products found")
        return
    
    try:
        product = products_df[products_df['id'] == product_id].iloc[0]
        store = stores_df[stores_df['id'] == product['store_id']].iloc[0]
    except (IndexError, KeyError):
        st.error("Product not found")
        return
    
    # Back button
    if st.button("← Back to Gallery"):
        st.session_state['selected_product'] = None
        st.rerun()
    
    st.title("Product Details")
    
    # Product header
    col1, col2 = st.columns([1, 2])
    
    with col1:
        if product['image_url']:
            st.image(product['image_url'], width=300)
        else:
            st.write("No image available")
    
    with col2:
        st.subheader(product['title'])
        
        # Data Quality Score
        score = product['data_quality_score']
        quality_level, emoji = get_quality_level(score)
        st.metric("Data Quality Score", f"{score}/100", delta=quality_level)
        st.write(f"{emoji} **Quality Level:** {quality_level}")
        
        # Price
        if product['max_price'] and product['max_price'] > product['price']:
            st.write(f"**Price:** ${product['price']:.2f} - ${product['max_price']:.2f}")
        else:
            st.write(f"**Price:** ${product['price']:.2f}")
        
        # Availability
        if product['available']:
            st.success("✅ In Stock")
        else:
            st.error("❌ Out of Stock")
        
        # Basic info
        st.write(f"**Vendor:** {product['vendor']}")
        st.write(f"**Type:** {product['product_type']}")
        
        if product['total_inventory']:
            st.write(f"**Inventory:** {product['total_inventory']}")
        
        if product['variant_count'] > 1:
            st.write(f"**Variants:** {product['variant_count']}")
        
        if product['image_count'] > 0:
            st.write(f"**Images:** {product['image_count']}")
        
        # AI Insights button
        if st.button("🤖 Get AI Insights"):
            try:
                # Convert product series to dict for the enricher
                product_dict = product.to_dict()
                store_dict = store.to_dict()
                
                # Enrich product data - CORRIGÉ : utilise seulement les données LLM
                enriched_data = llm_enricher.enrich_product_data(product_dict, store_dict)
                st.session_state['product_insights'] = enriched_data['llm_insights']
                st.rerun()
            except Exception as e:
                st.error(f"Error generating insights: {e}")
    
    # Show AI Insights if available - CORRIGÉ : affichage simplifié
    if 'product_insights' in st.session_state:
        st.subheader("🤖 AI Strategic Analysis")
        st.markdown(st.session_state['product_insights'])
    
    # Data Quality Breakdown
    st.subheader("📊 Data Quality Breakdown")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avail_score = 40 if product['available'] else 0
        st.metric("Availability", f"{avail_score}/40", "Available" if product['available'] else "Out of Stock")
    
    with col2:
        # Calculate inventory score
        inventory = product['total_inventory']
        variants = product['variant_count']
        if inventory > 0:
            if inventory >= 20:
                inv_score = 30
            elif inventory >= 10:
                inv_score = 25
            elif inventory >= 5:
                inv_score = 20
            else:
                inv_score = 15
        elif variants > 1:
            if variants >= 5:
                inv_score = 25
            elif variants >= 3:
                inv_score = 20
            else:
                inv_score = 15
        else:
            inv_score = 0
        st.metric("Stock/Variants", f"{inv_score}/30", f"{inventory} units, {variants} variants")
    
    with col3:
        images = product['image_count']
        if images >= 3:
            img_score = 20
        elif images >= 1:
            img_score = 15
        elif product['image_url']:
            img_score = 10
        else:
            img_score = 0
        st.metric("Images", f"{img_score}/20", f"{images} images")
    
    with col4:
        # Calculate content score
        title_len = len(str(product['title']))
        desc_len = len(str(product['description']))
        tags = product['tags']
        
        content_score = 0
        if title_len > 20:
            content_score += 4
        elif title_len > 10:
            content_score += 2
        
        if desc_len > 100:
            content_score += 4
        elif desc_len > 20:
            content_score += 2
        
        if tags and len(tags) > 0:
            content_score += 2
        
        st.metric("Content", f"{content_score}/10", f"Title: {title_len} chars")
    
    # Description
    if product['description']:
        st.subheader("Description")
        st.write(product['description'])
    
    # Tags and Categories
    if product['tags'] or product['categories']:
        st.subheader("Tags & Categories")
        col1, col2 = st.columns(2)
        
        with col1:
            if product['tags']:
                st.write("**Tags:**")
                for tag in product['tags']:
                    st.markdown(f'<span style="background-color: #e0e0e0; padding: 2px 8px; border-radius: 12px; font-size: 0.8em;">{tag}</span>', unsafe_allow_html=True)
        
        with col2:
            if product['categories']:
                st.write("**Categories:**")
                for category in product['categories']:
                    st.markdown(f'<span style="background-color: #e0e0e0; padding: 2px 8px; border-radius: 12px; font-size: 0.8em;">{category}</span>', unsafe_allow_html=True)
    
    # Store information
    st.subheader("Store Information")
    st.write(f"**Store:** {store['name']}")
    st.write(f"**URL:** {store['url']}")
    st.write(f"**Domain:** {store['domain']}")
    st.write(f"**Last Updated:** {store['updated_at']}")
    
    # Related Products
    st.subheader("Related Products")
    related_products = get_related_products(product, products_df)
    
    if not related_products.empty:
        cols = st.columns(min(4, len(related_products)))
        for i, (_, related_product) in enumerate(related_products.iterrows()):
            if i < len(cols):
                with cols[i]:
                    if related_product['image_url']:
                        st.image(related_product['image_url'], width=150)
                    st.write(f"**{related_product['title'][:30]}...**")
                    st.write(f"${related_product['price']:.2f}")
                    
                    # Show quality score
                    score = related_product['data_quality_score']
                    quality_level, emoji = get_quality_level(score)
                    st.write(f"{emoji} {score}/100")
                    
                    if st.button("View", key=f"related_{related_product['id']}"):
                        st.session_state['selected_product'] = related_product['id']
                        st.rerun()
    else:
        st.write("No related products found")

def show_product_gallery():
    st.title("Product Gallery")
    
    # Load data
    _, products_df, stores_df = load_data()
    
    if products_df.empty:
        st.info("No products found. Add products using the Scrape Data page.")
        return
    
    # Filters in sidebar
    st.sidebar.header("Filters")
    
    # Quality Score filter
    st.sidebar.subheader("Data Quality Score")
    score_range = st.sidebar.slider(
        "Score Range",
        min_value=0,
        max_value=100,
        value=(0, 100)
    )
    
    # Store filter
    if not stores_df.empty:
        store_options = ["All Stores"] + stores_df['name'].tolist()
        selected_store = st.sidebar.selectbox("Select Store", store_options)
    else:
        selected_store = "All Stores"
    
    # Price range filter
    if not products_df.empty:
        min_price = float(products_df['price'].min())
        max_price = float(products_df['price'].max())
        if min_price < max_price:
            price_range = st.sidebar.slider(
                "Price Range",
                min_value=min_price,
                max_value=max_price,
                value=(min_price, max_price)
            )
        else:
            price_range = (min_price, min_price)
    else:
        price_range = (0, 100)
    
    # Availability filter
    availability = st.sidebar.multiselect(
        "Availability",
        ["Available", "Out of Stock"],
        default=["Available", "Out of Stock"]
    )
    
    # Sort options
    sort_by = st.sidebar.selectbox(
        "Sort by",
        ["Data Quality Score (High to Low)", "Data Quality Score (Low to High)", 
         "Price (Low to High)", "Price (High to Low)", "Name (A-Z)"]
    )
    
    # Apply filters
    filtered_products = products_df.copy()
    
    # Filter by quality score
    filtered_products = filtered_products[
        (filtered_products['data_quality_score'] >= score_range[0]) &
        (filtered_products['data_quality_score'] <= score_range[1])
    ]
    
    if selected_store != "All Stores" and not stores_df.empty:
        store_id = stores_df[stores_df['name'] == selected_store]['id'].iloc[0]
        filtered_products = filtered_products[filtered_products['store_id'] == store_id]
    
    if not filtered_products.empty:
        filtered_products = filtered_products[
            (filtered_products['price'] >= price_range[0]) &
            (filtered_products['price'] <= price_range[1])
        ]
        
        if "Available" not in availability:
            filtered_products = filtered_products[~filtered_products['available']]
        if "Out of Stock" not in availability:
            filtered_products = filtered_products[filtered_products['available']]
    
    # Apply sorting
    if not filtered_products.empty:
        if sort_by == "Data Quality Score (High to Low)":
            filtered_products = filtered_products.sort_values('data_quality_score', ascending=False)
        elif sort_by == "Data Quality Score (Low to High)":
            filtered_products = filtered_products.sort_values('data_quality_score', ascending=True)
        elif sort_by == "Price (Low to High)":
            filtered_products = filtered_products.sort_values('price', ascending=True)
        elif sort_by == "Price (High to Low)":
            filtered_products = filtered_products.sort_values('price', ascending=False)
        elif sort_by == "Name (A-Z)":
            filtered_products = filtered_products.sort_values('title', ascending=True)
    
    # Display results
    st.write(f"Showing {len(filtered_products)} products")
    
    if filtered_products.empty:
        st.info("No products match your current filters.")
        return
    
    # Display products in grid
    cols_per_row = 3
    for i in range(0, len(filtered_products), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            if i + j < len(filtered_products):
                product = filtered_products.iloc[i + j]
                
                with col:
                    # Product image
                    if product['image_url']:
                        st.image(product['image_url'], width=200)
                    else:
                        st.write("No image")
                    
                    # Product info
                    st.write(f"**{product['title'][:50]}**")
                    st.write(f"Price: ${product['price']:.2f}")
                    
                    # Data Quality Score
                    score = product['data_quality_score']
                    quality_level, emoji = get_quality_level(score)
                    st.write(f"{emoji} **Quality:** {score}/100 ({quality_level})")
                    
                    # Availability
                    if product['available']:
                        st.success("In Stock")
                    else:
                        st.error("Out of Stock")
                    
                    # Additional info
                    if product['vendor']:
                        st.write(f"Vendor: {product['vendor']}")
                    
                    if product['product_type']:
                        st.write(f"Type: {product['product_type']}")
                    
                    # View Details button
                    if st.button("View Details", key=f"view_{product['id']}"):
                        st.session_state['selected_product'] = product['id']
                        st.rerun()
                    
                    st.divider()

def show_dashboard():
    st.title("Shopify Analytics Dashboard")
    
    # Load data
    logs_df, products_df, stores_df = load_data()
    
    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Products", len(products_df))
    
    with col2:
        st.metric("Total Stores", len(stores_df))
    
    with col3:
        if not stores_df.empty:
            active_surveillance = stores_df["active_surveillance"].sum()
        else:
            active_surveillance = 0
        st.metric("Active Surveillance", active_surveillance)
    
    with col4:
        if not products_df.empty:
            avg_score = products_df["data_quality_score"].mean()
        else:
            avg_score = 0
        st.metric("Avg Quality Score", f"{avg_score:.1f}/100")
    
    # Quality metrics
    if not products_df.empty:
        col5, col6, col7, col8 = st.columns(4)
        
        with col5:
            excellent = len(products_df[products_df['data_quality_score'] >= 80])
            st.metric("🟢 Excellent Quality", excellent)
        
        with col6:
            good = len(products_df[(products_df['data_quality_score'] >= 60) & (products_df['data_quality_score'] < 80)])
            st.metric("🟡 Good Quality", good)
        
        with col7:
            average = len(products_df[(products_df['data_quality_score'] >= 40) & (products_df['data_quality_score'] < 60)])
            st.metric("🟠 Average Quality", average)
        
        with col8:
            poor = len(products_df[products_df['data_quality_score'] < 40])
            st.metric("🔴 Poor Quality", poor)
    
    # Enhanced Charts
    if not products_df.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Data Quality Distribution")
            fig = px.histogram(
                products_df, 
                x="data_quality_score", 
                nbins=20, 
                title="Product Data Quality Distribution",
                color_discrete_sequence=['#1f77b4']
            )
            fig.update_layout(
                xaxis_title="Quality Score",
                yaxis_title="Number of Products",
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Quality Levels")
            quality_counts = []
            labels = []
            
            excellent = len(products_df[products_df['data_quality_score'] >= 80])
            good = len(products_df[(products_df['data_quality_score'] >= 60) & (products_df['data_quality_score'] < 80)])
            average = len(products_df[(products_df['data_quality_score'] >= 40) & (products_df['data_quality_score'] < 60)])
            poor = len(products_df[products_df['data_quality_score'] < 40])
            
            for count, label in [(excellent, "Excellent"), (good, "Good"), (average, "Average"), (poor, "Poor")]:
                if count > 0:
                    quality_counts.append(count)
                    labels.append(label)
            
            if quality_counts:
                fig = px.pie(
                    values=quality_counts, 
                    names=labels, 
                    title="Quality Level Distribution",
                    color_discrete_sequence=['#2ecc71', '#f1c40f', '#e67e22', '#e74c3c']
                )
                st.plotly_chart(fig, use_container_width=True)
        
        # Add new charts
        col3, col4 = st.columns(2)
        with col3:
            st.subheader("Products by Vendor")
            vendor_counts = products_df['vendor'].value_counts().head(10)
            if not vendor_counts.empty:
                fig = px.bar(
                    x=vendor_counts.index,
                    y=vendor_counts.values,
                    title="Top 10 Vendors",
                    labels={'x': 'Vendor', 'y': 'Number of Products'}
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col4:
            st.subheader("Products by Type")
            type_counts = products_df['product_type'].value_counts().head(10)
            if not type_counts.empty:
                fig = px.bar(
                    x=type_counts.index,
                    y=type_counts.values,
                    title="Top 10 Product Types",
                    labels={'x': 'Product Type', 'y': 'Number of Products'}
                )
                st.plotly_chart(fig, use_container_width=True)
    
    # Recent activity with more details
    if not stores_df.empty:
        st.subheader("Recent Activity")
        recent_stores = stores_df.sort_values("updated_at", ascending=False).head(5)
        
        for _, store in recent_stores.iterrows():
            with st.expander(f"{store['name']} - Last updated: {store['updated_at']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Status:** {'🟢 Active' if store['active_surveillance'] else '⭕ Inactive'}")
                    st.write(f"**Domain:** {store['domain']}")
                with col2:
                    st.write(f"**URL:** {store['url']}")
                    st.write(f"**Created:** {store['created_at']}")

def show_store_management():
    st.title("Store Management")
    
    # Load stores data
    _, products_df, stores_df = load_data()
    
    if not stores_df.empty:
        st.subheader("Your Stores")
        
        for _, store in stores_df.iterrows():
            # Get store products for quality metrics
            store_products = products_df[products_df['store_id'] == store['id']] if not products_df.empty else pd.DataFrame()
            
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.write(f"**{store['name']}**")
                st.write(f"URL: {store['url']}")
                st.write(f"Domain: {store['domain']}")
                
                if not store_products.empty:
                    avg_quality = store_products['data_quality_score'].mean()
                    quality_level, emoji = get_quality_level(avg_quality)
                    st.write(f"{emoji} Average Quality: {avg_quality:.1f}/100 ({quality_level})")
            
            with col2:
                st.write(f"Last Updated: {store['updated_at']}")
                if store['active_surveillance']:
                    st.success("Surveillance: Active")
                else:
                    st.warning("Surveillance: Inactive")
                
                if not store_products.empty:
                    st.write(f"Products: {len(store_products)}")
            
            with col3:
                button_text = "Deactivate" if store['active_surveillance'] else "Activate"
                if st.button(button_text, key=f"toggle_{store['id']}"):
                    new_status = not store['active_surveillance']
                    if toggle_surveillance(store['id'], new_status):
                        status_text = "activated" if new_status else "deactivated"
                        st.success(f"Surveillance {status_text}")
                        st.rerun()
                    else:
                        st.error("Failed to update surveillance")
            
            st.divider()
    else:
        st.info("No stores found. Add a store using the Scrape Data page.")

def show_scrape_data():
    st.title("Scrape New Store")
    
    st.info("🎯 **Data Quality Scoring**: All scraped products will automatically receive a quality score (0-100) based on availability, stock info, images, and content quality.")
    
    # URL input
    url = st.text_input("Shopify Store URL", placeholder="https://store-name.myshopify.com")
    
    # Category input
    category = st.text_input("Category (Optional)", placeholder="Leave empty for all products")
    
    if st.button("Start Scraping"):
        if url:
            if not (url.startswith('http://') or url.startswith('https://')):
                st.error("Please enter a valid URL starting with http:// or https://")
            else:
                with st.spinner("Scraping in progress..."):
                    success, message = scrape_store(url, category if category else None)
                    if success:
                        st.success(message)
                        st.info("✅ Data quality scores have been calculated automatically for all scraped products.")
                        st.info("💡 Navigate to the Dashboard or Product Gallery to view the results!")
                    else:
                        st.error(f"Error: {message}")
        else:
            st.warning("Please enter a valid URL")
    
    # Instructions
    with st.expander("ℹ️ How it works"):
        st.markdown("""
        **Data Quality Scoring System:**
        
        - **Availability (40 points)**: Product is in stock and available for purchase
        - **Stock/Variants (30 points)**: Inventory levels or number of product variants available
        - **Images (20 points)**: Number and quality of product images
        - **Content (10 points)**: Quality of title, description, tags, and categories
        
        **Quality Levels:**
        - 🟢 **Excellent (80-100)**: Complete, high-quality product data
        - 🟡 **Good (60-79)**: Good product data with minor gaps
        - 🟠 **Average (40-59)**: Basic product data, some improvements needed
        - 🔴 **Poor (0-39)**: Limited product data, significant improvements needed
        
        **Tips for better scores:**
        - Ensure products have detailed descriptions
        - Include multiple high-quality images
        - Maintain accurate inventory information
        - Use relevant tags and categories
        """)

def show_top_k_analysis():
    """Show Top-K analysis page"""
    st.title("📊 Top-K Product Analysis")
    
    # Load data
    _, products_df, stores_df = load_data()
    
    if products_df.empty:
        st.info("No products found. Add products using the Scrape Data page.")
        return
    
    st.subheader("Find Top Products")
    
    # Analysis parameters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        k = st.number_input("Number of top products (K)", min_value=1, max_value=100, value=20)
    
    with col2:
        min_price = st.number_input("Minimum price filter", min_value=0.0, value=0.0, step=1.0)
    
    with col3:
        categories = ["All Categories"] + sorted(products_df['product_type'].dropna().unique().tolist())
        selected_category = st.selectbox("Category filter", categories)
    
    if st.button("🔍 Analyze Top Products"):
        # Convert selected category for analyzer
        category_filter = None if selected_category == "All Categories" else selected_category
        
        # Use the simple analyzer
        try:
            result = analyzer.get_top_k(
                products_df=products_df,
                k=k,
                min_price=min_price,
                category=category_filter
            )
            
            if result.get('success', False):
                top_products = result['top_products']
                stats = result['stats']
                
                # Display stats
                st.subheader("📈 Analysis Results")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Products Analyzed", stats['total_analyzed'])
                with col2:
                    st.metric("Top Products Found", stats['top_k_count'])
                with col3:
                    st.metric("Average Price", f"${stats['avg_price']:.2f}")
                with col4:
                    st.metric("Availability Rate", f"{stats['availability_rate']:.1f}%")
                
                # Top categories
                if stats.get('top_categories'):
                    st.subheader("🏷️ Top Categories")
                    categories_data = stats['top_categories']
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        fig = px.bar(
                            x=list(categories_data.keys()),
                            y=list(categories_data.values()),
                            title="Product Count by Category",
                            labels={'x': 'Category', 'y': 'Number of Products'}
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        fig = px.pie(
                            names=list(categories_data.keys()),
                            values=list(categories_data.values()),
                            title="Category Distribution"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                
                # Display top products
                st.subheader(f"🏆 Top {len(top_products)} Products")
                
                # Create a more detailed display
                for i, product in enumerate(top_products[:10]):  # Show top 10 in detail
                    with st.expander(f"#{i+1} - {product['title'][:60]}..."):
                        col1, col2, col3 = st.columns([1, 2, 1])
                        
                        with col1:
                            if product.get('image_url'):
                                st.image(product['image_url'], width=150)
                            else:
                                st.write("No image")
                        
                        with col2:
                            st.write(f"**Price:** ${product['price']:.2f}")
                            st.write(f"**Vendor:** {product.get('vendor', 'N/A')}")
                            st.write(f"**Type:** {product.get('product_type', 'N/A')}")
                            st.write(f"**Available:** {'✅ Yes' if product.get('available', False) else '❌ No'}")
                            
                            if product.get('total_inventory', 0) > 0:
                                st.write(f"**Inventory:** {product['total_inventory']}")
                            
                            # Quality score
                            quality_score = calculate_simple_data_score(product)
                            quality_level, emoji = get_quality_level(quality_score)
                            st.write(f"**Data Quality:** {emoji} {quality_score}/100 ({quality_level})")
                        
                        with col3:
                            if st.button("View Details", key=f"top_view_{product['id']}"):
                                st.session_state['selected_product'] = product['id']
                                st.session_state['page'] = 'Product Gallery'
                                st.rerun()
                
                # Show remaining products in a table
                if len(top_products) > 10:
                    st.subheader(f"📋 Remaining {len(top_products) - 10} Products")
                    remaining_products = top_products[10:]
                    
                    # Create a DataFrame for table display
                    table_data = []
                    for i, product in enumerate(remaining_products, 11):
                        quality_score = calculate_simple_data_score(product)
                        quality_level, emoji = get_quality_level(quality_score)
                        
                        table_data.append({
                            'Rank': i,
                            'Title': product['title'][:40] + '...' if len(product['title']) > 40 else product['title'],
                            'Price': f"${product['price']:.2f}",
                            'Vendor': product.get('vendor', 'N/A'),
                            'Available': '✅' if product.get('available', False) else '❌',
                            'Quality': f"{emoji} {quality_score}",
                            'ID': product['id']
                        })
                    
                    table_df = pd.DataFrame(table_data)
                    st.dataframe(table_df, use_container_width=True)
            
            else:
                st.error(f"Analysis failed: {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            st.error(f"Error during analysis: {str(e)}")

def main():
    """Main application entry point"""
    st.set_page_config(
        page_title="Shopify Store Analyzer",
        page_icon="🛍️",
        layout="wide"
    )
    
    # Initialize session state
    if 'page' not in st.session_state:
        st.session_state['page'] = 'Dashboard'
    if 'selected_product' not in st.session_state:
        st.session_state['selected_product'] = None
    
    # Sidebar navigation
    st.sidebar.title("🛍️ Shopify Analyzer")
    st.sidebar.markdown("---")
    
    # MODIFICATION ICI : Ajouter "MCP Dashboard" à la liste
    page = st.sidebar.radio(
        "📍 Navigation",
        ["Dashboard", "Product Gallery", "Top-K Analysis", "Store Management", "Scrape Data", "MCP Dashboard"],
        index=["Dashboard", "Product Gallery", "Top-K Analysis", "Store Management", "Scrape Data", "MCP Dashboard"].index(st.session_state['page']) if st.session_state['page'] in ["Dashboard", "Product Gallery", "Top-K Analysis", "Store Management", "Scrape Data", "MCP Dashboard"] else 0
    )
    
    # Update session state
    st.session_state['page'] = page
    
    # Show page info in sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ℹ️ Page Info")
    
    page_info = {
        "Dashboard": "📊 Overview of all scraped data and quality metrics",
        "Product Gallery": "🖼️ Browse and view detailed product information",
        "Top-K Analysis": "🏆 Find and analyze top-performing products",
        "Store Management": "🏪 Manage scraped stores and surveillance",
        "Scrape Data": "🔄 Add new stores to scrape and monitor",
        "MCP Dashboard": "🛡️ Model Context Protocol - Responsible AI interactions"  # NOUVEAU
    }
    
    st.sidebar.info(page_info.get(page, ""))
    
    # Show selected page
    if page == "Dashboard":
        show_dashboard()
    elif page == "Product Gallery":
        if 'selected_product' in st.session_state and st.session_state['selected_product']:
            _, products_df, stores_df = load_data()
            show_product_details(
                product_id=st.session_state['selected_product'],
                products_df=products_df,
                stores_df=stores_df
            )
        else:
            show_product_gallery()
    elif page == "Top-K Analysis":
        show_top_k_analysis()
    elif page == "Store Management":
        show_store_management()
    elif page == "Scrape Data":
        show_scrape_data()
    elif page == "MCP Dashboard":  # NOUVEAU
        show_mcp_dashboard()

if __name__ == "__main__":
    main()
import streamlit as st
import time
from DB.db import SessionLocal
from DB.db_utils import get_or_create_store, log_scraping
from agents.ShopifyAgent import ShopifyAgent

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

def show_scrape_data():
    st.title("Scrape New Store")
    
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
                    else:
                        st.error(f"Error: {message}")
        else:
            st.warning("Please enter a valid URL") 
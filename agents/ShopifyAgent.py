"""
Shopify-specific A2A agent implementation - Version Améliorée
Handles detection, scraping, and extraction for Shopify stores.
"""
import json
import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import requests # Import requests explicitly for exception handling
import schedule
import time
from datetime import datetime
import pandas as pd

# Import BaseA2AAgent from the same directory
from .BaseA2AAgent import BaseA2AAgent
from DB.db import SessionLocal, init_db # Update to use correct path
from DB.db_utils import get_or_create_store, add_or_update_product, log_scraping # Update to use correct path
from DB.models import ScrapingLog # Update to use correct path
from DB.db import SessionLocal # Re-import SessionLocal if it was removed
from Analyse.simple_analyzer import SimpleTopKAnalyzer
from Analyse.db_manager import TopKDBManager

class ShopifyAgent(BaseA2AAgent):
    """Agent specialized in scraping Shopify platforms"""
    
    def __init__(self, site_url: str, category: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize Shopify agent
        
        Args:
            site_url: The base URL of the Shopify store
            category: Optional category to focus scraping on
            api_key: Optional API key for authenticated requests
        """
        super().__init__(site_url, category)
        self.api_key = api_key
        self.store_info = {}
        self._surveillance_job = None # To store the scheduled job
        self.analyzer = SimpleTopKAnalyzer()
        self.db_manager = TopKDBManager()
        self.current_products = []
        
        # Shopify-specific configuration
        if api_key:
            self.session.headers.update({
                'X-Shopify-Access-Token': api_key
            })
    
    # =====================================
    # 1 Surveillance Mode
    # =====================================
    def surveillance(self, on_or_off: bool, hours: int = 24):
        """
        Turn surveillance mode on or off.

        Args:
            on_or_off: True to turn on, False to turn off.
            hours: The interval in hours for re-scraping (minimum 1 hour).
        """
        if on_or_off:
            if self._surveillance_job:
                self.logger.info(f"Surveillance already active for {self.site_url}.")
                return

            interval = max(1, hours) # Ensure interval is at least 1 hour
            self.logger.info(f"Turning on surveillance for {self.site_url} every {interval} hours.")
            # Schedule the scraping task
            self._surveillance_job = schedule.every(interval).hours.do(
                self._run_surveillance_scrape
            )
        else:
            if self._surveillance_job:
                self.logger.info(f"Turning off surveillance for {self.site_url}.")
                schedule.cancel_job(self._surveillance_job)
                self._surveillance_job = None
            else:
                self.logger.info(f"Surveillance is not active for {self.site_url}.")

    def _run_surveillance_scrape(self):
        """
        Internal method to perform a scrape and log results when in surveillance mode.
        This method is called by the scheduler.
        """
        self.logger.info(f"Running scheduled surveillance scrape for {self.site_url}")
        db = None
        start_time = time.time()
        status = "in_progress"
        error_message = None
        product_count = 0 # Initialize product_count to 0
        scraping_log_id = None # Initialize scraping_log_id

        try:
            db = SessionLocal()
            # Get or create store in database (essential for logging)
            store = get_or_create_store(
                 db,
                 name=urlparse(self.site_url).hostname.split('.')[0].capitalize(),
                 url=self.site_url,
                 domain=urlparse(self.site_url).hostname
            )
            store_id = store.id

            # Create initial ScrapingLog entry
            log_entry = ScrapingLog(
                store_id=store_id,
                scraped_at=datetime.utcnow(), # Use current time for log creation
                status=status,
                product_count=product_count # Initial count is 0
            )
            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)
            scraping_log_id = log_entry.id # Get the ID of the new log entry

            # Perform the scrape (using the existing method)
            products = self.scrape_products(limit=None) # Scrape all available products in surveillance
            product_count = len(products)

            if products:
                # Save/update products in the database and log changes
                for product_data in products:
                     # Add store information to product data before saving
                     product_data['store_name'] = store.name
                     product_data['store_domain'] = store.domain
                     # Pass the scraping_log_id to add_or_update_product
                     add_or_update_product(db, store_id, product_data, scraping_log_id=scraping_log_id)
                self.logger.info(f"Saved/updated {product_count} products for {self.site_url}")
            else:
                self.logger.warning(f"No products scraped during surveillance for {self.site_url}")
                # If no products were scraped, consider it a scraping failure for logging
                status = "failure"
                error_message = "No products scraped or scraping failed internally."

        except Exception as e:
            status = "failure"
            error_message = str(e)
            self.logger.error(f"Surveillance scrape failed for {self.site_url}: {e}")
        finally:
            duration = time.time() - start_time
            if db and scraping_log_id is not None:
                # Update the ScrapingLog entry with final status, count, and duration
                log_entry = db.query(ScrapingLog).filter(ScrapingLog.id == scraping_log_id).first()
                if log_entry:
                    log_entry.status = status
                    log_entry.product_count = product_count
                    log_entry.duration_seconds = duration
                    if error_message:
                         log_entry.error_message = error_message
                    db.commit()
                db.close()
            elif db:
                 # Log a failure if the initial log entry creation failed
                 self.logger.error(f"Failed to create initial scraping log entry for {self.site_url}")
                 if error_message:
                      self.logger.error(f"Error details: {error_message}")
                 db.close()

    # =====================================
    # 2 Platform Detection
    # =====================================  
    def detect_platform(self) -> bool:
        """
        Detect if the site is running on Shopify platform.
        Enhanced detection with multiple methods.
        
        Returns:
            True if Shopify is detected, False otherwise
        """
        response = self._make_request(self.site_url)
        if not response:
            return False
        
        # Method 1: Check for Shopify assets in HTML
        shopify_indicators = [
            'cdn.shopify.com',
            'shopify.com/s/',
            'Shopify.theme',
            '/cdn/shop/products/',
            'myshopify.com',
            'shopifycdn.com',
            'Shopify.analytics',
            'window.Shopify'
        ]
        
        content_lower = response.text.lower()
        detected_indicators = []
        
        for indicator in shopify_indicators:
            if indicator.lower() in content_lower:
                detected_indicators.append(indicator)
        
        if detected_indicators:
            self.logger.info(f"Detected Shopify platform via indicators: {detected_indicators}")
            
            # Extract store information if available
            self._extract_store_info(response.text)
            return True
        
        # Method 2: Check response headers
        server_header = response.headers.get('Server', '').lower()
        if 'shopify' in server_header:
            self.logger.info("Detected Shopify platform via Server header")
            return True
        
        # Method 3: Test API endpoints
        if self._test_shopify_api():
            self.logger.info("Detected Shopify platform via API endpoints")
            return True
        
        return False
    
    def _extract_store_info(self, html_content: str):
        """Extract store metadata from HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract store name
        title_tag = soup.find('title')
        if title_tag:
            self.store_info['store_name'] = title_tag.text.strip()
        
        # Look for Shopify configuration in scripts
        for script in soup.find_all('script'):
            if script.string and 'Shopify.shop' in script.string:
                try:
                    # Extract shop domain
                    shop_match = re.search(r'Shopify\.shop\s*=\s*["\']([^"\']+)["\']', script.string)
                    if shop_match:
                        self.store_info['shop_domain'] = shop_match.group(1)
                except Exception:
                    pass
    
    def _test_shopify_api(self) -> bool:
        """Test if Shopify API endpoints are accessible"""
        test_endpoints = [
            '/products.json',
            '/collections.json',
            '/admin/api/2023-10/shop.json'  # Requires API key
        ]
        
        for endpoint in test_endpoints:
            response = self._make_request(f"{self.site_url}{endpoint}")
            if response and response.status_code == 200:
                try:
                    data = response.json()
                    if 'products' in data or 'collections' in data or 'shop' in data:
                        return True
                except json.JSONDecodeError:
                    continue
        
        return False
    
    # =====================================
    # 3 Main Scrape Products Methods
    # =====================================
    def scrape_products(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Focused: Scrape products from a Shopify store using only the paginated /products.json endpoint.
        Includes enhanced error handling for requests and JSON parsing.
        Returns a list of normalized product dicts.
        """
        all_products = []
        page = 1
        per_page = 250  # Shopify max per page
        
        self.logger.info(f"Starting product scraping from /products.json for {self.site_url} with limit {limit}")

        while len(all_products) < limit:
            api_url = f"{self.site_url}/products.json?limit={per_page}&page={page}"
            
            try:
                response = self._make_request(api_url)
                
                if not response or response.status_code != 200:
                    if response is not None:
                         self.logger.error(f"Failed to fetch page {page} from {api_url}. Status code: {response.status_code}")
                    else:
                         self.logger.error(f"Failed to fetch page {page} from {api_url} after retries.")
                    break

                try:
                    data = response.json()
                    products = data.get('products', [])
                    
                    if not products:
                        self.logger.info(f"No products found on page {page} for {self.site_url}. Ending pagination.")
                        break
                        
                    self.logger.info(f"Successfully fetched {len(products)} products from page {page} for {self.site_url}.")

                    for product in products:
                         # Process product data (keep the existing parsing logic)
                         product_url = f"{self.site_url}/products/{product.get('handle', '')}"
                         description_html = product.get('body_html', '')
                         description = BeautifulSoup(str(description_html), "html.parser").get_text()
                         images = product.get('images', [])
                         has_image = bool(images)
                         image_url = images[0]['src'] if has_image else ''
                         variants = product.get('variants', [])
                         min_price = float('inf')
                         max_price = 0
                         total_inventory = 0
                         is_available = False

                         for variant in variants:
                              try:
                                   price = float(variant.get('price', 0))
                                   min_price = min(min_price, price)
                                   max_price = max(max_price, price)
                                   inventory = int(variant.get('inventory_quantity', 0))
                                   total_inventory += inventory
                                   if variant.get('available', False):
                                        is_available = True
                              except (ValueError, TypeError) as e:
                                   self.logger.warning(f"Error processing variant data for product {product.get('id', '')}: {e}")
                                   continue

                         product_data = {
                             'id': str(product.get('id', '')),
                             'title': product.get('title', ''),
                             'product_url': product_url,
                             'handle': product.get('handle', ''),
                             'price': min_price if min_price != float('inf') else 0.0,
                             'max_price': max_price,
                             'currency': 'USD',
                             'available': is_available,
                             'total_inventory': total_inventory,
                             'description': description,
                             'short_description': str(product.get('body_html', ''))[:200] if product.get('body_html', '') else '',
                             'product_type': product.get('product_type', ''),
                             'vendor': product.get('vendor', ''),
                             'tags': product.get('tags', []),
                             'has_image': has_image,
                             'image_url': image_url,
                             'image_count': len(images),
                             'created_at': product.get('created_at', ''),
                             'updated_at': product.get('updated_at', ''),
                             'published_at': product.get('published_at', ''),
                             'variant_count': len(variants),
                             'options': product.get('options', []),
                             'store_name': self.store_info.get('store_name', ''),
                             'store_domain': self.store_info.get('shop_domain', ''),
                         }
                         
                         collections = product.get('collections', [])
                         if collections:
                             product_data['categories'] = [cat.get('title') for cat in collections]
                             product_data['collection_ids'] = [str(cat.get('id')) for cat in collections]
                         else:
                             product_data['categories'] = []
                             product_data['collection_ids'] = []

                         all_products.append(product_data)
                         
                         # Analyse en temps réel
                         self.current_products.append(product_data)
                         if len(self.current_products) >= 10:  # Analyse tous les 10 produits
                             try:
                                 df = pd.DataFrame(self.current_products)
                                 analysis = self.analyzer.get_top_k(df, k=5)  # Analyse top 5
                                 if analysis.get('success'):
                                     self.logger.info(f"Analyse en temps réel - Top 5 produits actuels:")
                                     for product in analysis['top_products']:
                                         self.logger.info(f"- {product['title']}: Score {product['final_score']:.1f}")
                                     
                                     # Sauvegarder l'analyse en temps réel
                                     store_id = self._get_store_id()
                                     if store_id:
                                         analysis_name = f"Analyse en temps réel - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                                         self.db_manager.save_analysis(
                                             analysis_data=analysis,
                                             analysis_name=analysis_name,
                                             k_value=5,
                                             store_id=store_id
                                         )
                             except Exception as e:
                                 self.logger.error(f"Erreur analyse en temps réel: {e}")
                             self.current_products = []  # Reset pour le prochain batch
                         
                         if len(all_products) >= limit:
                             break
                         
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to decode JSON from page {page} for {self.site_url}: {e}")
                    pass 

            except requests.exceptions.RequestException as e:
                 self.logger.error(f"Request failed for page {page} from {api_url}: {e}")
                 pass

            page += 1
            
        # Analyse finale avec tous les produits
        try:
            df = pd.DataFrame(all_products)
            final_analysis = self.analyzer.get_top_k(df, k=min(20, len(df)))
            if final_analysis.get('success'):
                self.logger.info("Analyse finale des produits:")
                self.logger.info(f"Total produits analysés: {final_analysis['stats']['total_analyzed']}")
                self.logger.info(f"Score moyen: {final_analysis['stats']['avg_score']}")
                self.logger.info(f"Prix moyen: {final_analysis['stats']['avg_price']}")
                
                # Sauvegarder l'analyse finale
                store_id = self._get_store_id()
                if store_id:
                    analysis_name = f"Analyse finale - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    self.db_manager.save_analysis(
                        analysis_data=final_analysis,
                        analysis_name=analysis_name,
                        k_value=min(20, len(df)),
                        store_id=store_id
                    )
        except Exception as e:
            self.logger.error(f"Erreur analyse finale: {e}")
            
        self.logger.info(f"Finished scraping products from {self.site_url}. Total products collected: {len(all_products)}")
        return all_products[:limit]

    def extract_product_details(self, product_url: str) -> Dict[str, Any]:
        """
        Enhanced: Extract detailed information for a specific product.
        Includes price, availability, and all product details.
        Prioritizes data from data-product-json script tag.
        """
        details = {}
        response = self._make_request(product_url)
        if not response:
            return details
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try to extract data from data-product-json script tag first
        product_json_script = soup.find('script', {'type': 'application/json', 'data-product-json': True})
        if product_json_script:
            try:
                product_data = json.loads(product_json_script.string)
                details.update({
                    'title': product_data.get('title', ''),
                    'description': product_data.get('description', ''),
                    'price': float(product_data.get('price', 0)) / 100, # Price is often in cents
                    'available': product_data.get('available', False),
                    'vendor': product_data.get('vendor', ''),
                    'product_type': product_data.get('type', ''),
                    'tags': product_data.get('tags', []), # Tags are often in this JSON
                    'id': str(product_data.get('id', '')),
                    # You might add more fields from this JSON as needed
                })
                 # If we found basic data in the JSON, try to get more from JSON-LD or meta tags
            except (json.JSONDecodeError, KeyError, ValueError):
                pass # Continue to other methods if JSON parsing fails

        # Extract meta information if not already found in product_json
        if not details.get('title'):
            title_tag = soup.find('title')
            if title_tag:
                details['title'] = title_tag.text.strip()
                
        if not details.get('description'):
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                details['description'] = meta_desc.get('content', '')
        
        # Extract price information from CSS selectors as a fallback
        if details.get('price', 0) == 0:
            price_selectors = [
                '.product-price',
                '.price',
                '[data-product-price]',
                '.product__price',
                '.product-single__price'
            ]
            
            for selector in price_selectors:
                price_el = soup.select_one(selector)
                if price_el:
                    price_text = price_el.get_text().strip()
                    try:
                        # Extract first number from price text
                        price_match = re.search(r'\d+\.?\d*', price_text)
                        if price_match:
                            details['price'] = float(price_match.group())
                            break
                    except (ValueError, AttributeError):
                        continue
        
        # Extract structured data (JSON-LD) and update details, prioritizing existing data
        json_ld = soup.find('script', type='application/ld+json')
        if json_ld:
            try:
                ld_data = json.loads(json_ld.string)
                if isinstance(ld_data, list):
                    ld_data = ld_data[0]
                if ld_data.get('@type') == 'Product':
                    ld_details = {
                        'title': ld_data.get('name', ''),
                        'description': ld_data.get('description', ''),
                        'brand': ld_data.get('brand', {}).get('name', ''),
                        'sku': ld_data.get('sku', ''),
                        'rating': ld_data.get('aggregateRating', {}).get('ratingValue', 0),
                        'review_count': ld_data.get('aggregateRating', {}).get('reviewCount', 0),
                        'barcode': ld_data.get('gtin', ''),
                        'weight': ld_data.get('weight', {}).get('value', ''),
                        'weight_unit': ld_data.get('weight', {}).get('unitCode', ''),
                        'price': float(ld_data.get('offers', {}).get('price', 0)),
                        'available': ld_data.get('offers', {}).get('availability', ''),
                        'currency': ld_data.get('offers', {}).get('priceCurrency', 'USD')
                    }
                    # Update details, but prefer data already found (e.g., from product_json)
                    for key, value in ld_details.items():
                        if key not in details or (isinstance(details[key], (int, float)) and details[key] == 0) or (isinstance(details[key], str) and details[key] == '') or (isinstance(details[key], list) and not details[key]):
                             if value not in ['', 0, None, []]: # Avoid overwriting with empty values
                                 details[key] = value

            except (json.JSONDecodeError, KeyError, ValueError):
                pass
        
        # Ensure basic required fields are present, even if empty
        details.setdefault('title', '')
        details.setdefault('description', '')
        details.setdefault('price', 0.0)
        
        return details

    # =====================================
    # 4 Scrape via API
    # =====================================
    def _scrape_via_api(self, limit: int) -> List[Dict[str, Any]]:
        """Scrape products using Shopify API endpoints"""
        products = []
        
        # Try different API endpoints
        api_urls = [
            f"{self.site_url}/products.json?limit={min(limit, 250)}",
            f"{self.site_url}/admin/api/2023-10/products.json?limit={min(limit, 250)}"
        ]
        
        for api_url in api_urls:
            response = self._make_request(api_url)
            if not response:
                continue
                
            try:
                data = response.json()
                if 'products' not in data:
                    continue
                    
                self.logger.info(f"Successfully accessed Shopify API: found {len(data['products'])} products")
                
                for product in data['products'][:limit]:
                    product_data = self._parse_api_product(product)
                    if product_data:
                        products.append(product_data)
                
                break  # Success, no need to try other endpoints
                
            except (json.JSONDecodeError, KeyError) as e:
                self.logger.warning(f"Error parsing products from API {api_url}: {e}")
                continue
        
        return products
    
    def _parse_api_product(self, product: Dict) -> Optional[Dict[str, Any]]:
        """Parse product data from Shopify API response"""
        try:
            product_data = {
                'id': str(product.get('id', '')),
                'title': product.get('title', ''),
                'description': self._clean_html_description(product.get('body_html', '')),
                'product_type': product.get('product_type', ''),
                'vendor': product.get('vendor', ''),
                'tags': product.get('tags', []) if isinstance(product.get('tags'), list) else product.get('tags', '').split(','),
                'created_at': product.get('created_at', ''),
                'updated_at': product.get('updated_at', ''),
                'product_url': f"{self.site_url}/products/{product.get('handle', '')}",
                'variants': [],
                'available': False,
                'price': 0.0,
                'has_image': False  # Initialize has_image field
            }
            
            # Get main image
            if product.get('images') and len(product['images']) > 0:
                product_data['image_url'] = product['images'][0].get('src', '')
                product_data['has_image'] = True  # Set has_image if image exists
            
            # Process variants for pricing and availability
            min_price = float('inf')
            has_available_variant = False
            
            for variant in product.get('variants', []):
                variant_data = {
                    'id': str(variant.get('id', '')),
                    'title': variant.get('title', ''),
                    'price': float(variant.get('price', 0)),
                    'available': variant.get('available', False),
                    'sku': variant.get('sku', ''),
                    'inventory_quantity': variant.get('inventory_quantity', 0)
                }
                product_data['variants'].append(variant_data)
                
                # Track minimum price and availability
                if variant_data['price'] < min_price:
                    min_price = variant_data['price']
                
                if variant_data['available']:
                    has_available_variant = True
            
            # Set main product attributes
            product_data['price'] = min_price if min_price != float('inf') else 0.0
            product_data['available'] = has_available_variant
            
            return product_data
            
        except Exception as e:
            self.logger.warning(f"Error parsing API product: {e}")
            return None
    
    
    
    # =====================================
    # 5 Scrape via HTML
    # =====================================
    def _scrape_via_html(self, limit: int) -> List[Dict[str, Any]]:
        """Scrape products via HTML parsing with improved selectors"""
        products = []
        
        # Determine collection URLs to scrape
        urls_to_scrape = self._get_collection_urls()
        
        for url in urls_to_scrape:
            if len(products) >= limit:
                break
                
            page_products = self._scrape_collection_page(url, limit - len(products))
            products.extend(page_products)
        
        return products
    
    def _get_collection_urls(self) -> List[str]:
        """Get list of collection URLs to scrape"""
        urls = []
        
        # Primary collection URLs
        if self.category:
            urls.append(f"{self.site_url}/collections/{self.category}")
        else:
            urls.extend([
                f"{self.site_url}/collections/all",
                f"{self.site_url}/collections",
                f"{self.site_url}/products"
            ])
        
        # Try to discover additional collections
        response = self._make_request(f"{self.site_url}/collections.json")
        if response:
            try:
                data = response.json()
                for collection in data.get('collections', [])[:5]:  # Limit to first 5 collections
                    collection_url = f"{self.site_url}/collections/{collection.get('handle')}"
                    if collection_url not in urls:
                        urls.append(collection_url)
            except (json.JSONDecodeError, KeyError):
                pass
        
        return urls
    
    def _scrape_collection_page(self, url: str, limit: int) -> List[Dict[str, Any]]:
        """Enhanced collection page scraping with better selectors"""
        products = []
        response = self._make_request(url)
        if not response:
            return products
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Enhanced selectors for various Shopify themes
        product_selectors = [
            '.product-card, .product-item, .grid-product, .grid__item .grid-view-item',
            '.product, .product-block, .item-product',
            '[data-product-id], [data-product]',
            '.card-product, .product-card-wrapper'
        ]
        
        product_elements = []
        for selector in product_selectors:
            elements = soup.select(selector)
            if elements:
                product_elements = elements
                self.logger.info(f"Found {len(elements)} products using selector: {selector}")
                break
        
        for i, product_el in enumerate(product_elements):
            if i >= limit:
                break
            
            product_data = self._extract_product_from_element(product_el)
            if product_data:
                products.append(product_data)
        
        return products
    
    def _extract_product_from_element(self, element) -> Optional[Dict[str, Any]]:
        """Extract product data from HTML element with enhanced parsing"""
        try:
            product_data = {}
            
            # Find product URL
            link_selectors = ['a[href*="/products/"]', 'a.product-link', '.product-card__link']
            product_link = None
            for selector in link_selectors:
                product_link = element.select_one(selector)
                if product_link:
                    break
            
            if not product_link:
                return None
            
            product_url = urljoin(self.site_url, product_link.get('href', ''))
            product_data['url'] = product_url
            
            # Extract product ID from URL or data attributes
            handle_match = re.search(r'/products/([^/?]+)', product_url)
            if handle_match:
                product_data['handle'] = handle_match.group(1)
            
            product_data['id'] = element.get('data-product-id', product_data.get('handle', ''))
            
            # Get title with multiple selectors
            title_selectors = [
                '.product-card__title, .product-item__title, .grid-view-item__title',
                '.product__title, .product-title',
                'h2, h3, .h2, .h3',
                '[data-product-title]'
            ]
            
            for selector in title_selectors:
                title_el = element.select_one(selector)
                if title_el:
                    product_data['title'] = title_el.text.strip()
                    break
            
            # Get price with enhanced parsing
            price_selectors = [
                '.price, .product-price, .grid-view-item__meta',
                '.price__current, .product-card__price',
                '[data-price], [data-product-price]'
            ]
            
            for selector in price_selectors:
                price_el = element.select_one(selector)
                if price_el:
                    price_text = price_el.text.strip()
                    product_data['price'] = self._parse_price(price_text)
                    break
            
            # Get image
            img_el = element.select_one('img')
            if img_el:
                img_src = img_el.get('data-src') or img_el.get('src') or img_el.get('data-original')
                if img_src:
                    product_data['image_url'] = urljoin(self.site_url, img_src)
            
            # Get vendor if visible
            vendor_el = element.select_one('.product-vendor, .product__vendor, [data-vendor]')
            if vendor_el:
                product_data['vendor'] = vendor_el.text.strip()
            
            return product_data
            
        except Exception as e:
            self.logger.warning(f"Error extracting product from element: {e}")
            return None
    

    # =====================================
    #  Utility Methods 
    # =====================================
    def _get_detailed_product_info(self, product_url: str) -> Dict[str, Any]:
        """Get detailed product information from the product page"""
        details = {}
        response = self._make_request(product_url)
        if not response:
            return details
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract meta information
        title_tag = soup.find('title')
        if title_tag:
            details['meta_title'] = title_tag.text.strip()
            
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            details['meta_description'] = meta_desc.get('content', '')
            
        # Extract structured data (JSON-LD)
        json_ld = soup.find('script', type='application/ld+json')
        if json_ld:
            try:
                ld_data = json.loads(json_ld.string)
                if isinstance(ld_data, list):
                    ld_data = ld_data[0]
                if ld_data.get('@type') == 'Product':
                    details.update({
                        'brand': ld_data.get('brand', {}).get('name', ''),
                        'sku': ld_data.get('sku', ''),
                        'rating': ld_data.get('aggregateRating', {}).get('ratingValue', 0),
                        'review_count': ld_data.get('aggregateRating', {}).get('reviewCount', 0),
                        'barcode': ld_data.get('gtin', ''),
                        'weight': ld_data.get('weight', {}).get('value', ''),
                        'weight_unit': ld_data.get('weight', {}).get('unitCode', ''),
                    })
            except (json.JSONDecodeError, KeyError):
                pass
                
        return details

    def _get_traffic_data(self, product_url: str) -> Dict[str, Any]:
        """Get traffic data for the product (if available)"""
        # This is a placeholder. In a real implementation, you might:
        # 1. Use a third-party API (e.g., SimilarWeb, Alexa)
        # 2. Parse analytics data if available
        # 3. Use store's public metrics if available
        return {
            'estimated_visits': 0,
            'bounce_rate': 0,
            'avg_time_on_page': 0,
            'conversion_rate': 0
        }

    def _get_geography_data(self, product_url: str) -> Dict[str, Any]:
        """Get geography data for the product (if available)"""
        # This is a placeholder. In a real implementation, you might:
        # 1. Use IP geolocation
        # 2. Parse store's shipping information
        # 3. Use store's location data
        return {
            'available_countries': [],
            'shipping_countries': [],
            'store_locations': []
        }
    
    def _clean_html_description(self, html_desc: str) -> str:
        """Clean HTML description to plain text"""
        if not html_desc:
            return ""
        
        soup = BeautifulSoup(html_desc, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        return text[:500]  # Limit description length
    
    def _get_store_id(self) -> Optional[int]:
        """Get store ID from database"""
        try:
            db = SessionLocal()
            store = get_or_create_store(
                db,
                name=urlparse(self.site_url).hostname.split('.')[0].capitalize(),
                url=self.site_url,
                domain=urlparse(self.site_url).hostname
            )
            return store.id
        except Exception as e:
            self.logger.error(f"Error getting store ID: {e}")
            return None
        finally:
            db.close()
    

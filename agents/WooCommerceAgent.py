"""
WooCommerce-specific A2A agent implementation.
Handles detection, scraping, and extraction for WooCommerce stores.
"""
import json
import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import requests
import logging
from datetime import datetime
import time
import os
import sys

# Add the project root to the sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from .BaseA2AAgent import BaseA2AAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WooCommerceAgent(BaseA2AAgent):
    """Agent specialized in scraping WooCommerce platforms"""
    
    # =====================================
    # 1 Initialize WooCommerce Agent
    # =====================================
    def __init__(self, site_url: str, category: Optional[str] = None, **kwargs):
        """
        Initialize WooCommerce agent
        
        Args:
            site_url: The base URL of the WooCommerce store
            category: Optional category to focus scraping on
            **kwargs: Additional arguments (consumer_key, consumer_secret)
        """
        super().__init__(site_url, category)
        self.consumer_key = kwargs.get('consumer_key')
        self.consumer_secret = kwargs.get('consumer_secret')
        self.store_info = {}
        self.api_base = self._get_api_base()
        
        # WooCommerce API configuration
        if self.consumer_key and self.consumer_secret:
            self.api_auth = (self.consumer_key, self.consumer_secret)
        else:
            self.api_auth = None
    
    def _get_api_base(self) -> str:
        """Determine the base URL of the WooCommerce API"""
        parsed_url = urlparse(self.site_url)
        return f"{parsed_url.scheme}://{parsed_url.netloc}/wp-json/wc/v3/"
    
    # =====================================
    # 2 Platform Detection
    # =====================================
    def detect_platform(self) -> bool:
        """
        Detect if the site is running on WooCommerce platform.
        
        Returns:
            True if WooCommerce is detected, False otherwise
        """
        try:
            # Try to access the WooCommerce API
            response = requests.get(
                f"{self.api_base}products",
                params={
                    'consumer_key': self.consumer_key,
                    'consumer_secret': self.consumer_secret,
                    'per_page': 1
                },
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Error detecting WooCommerce platform: {e}")
        return False
    
    def _is_wordpress_site(self, html_content: str) -> bool:
        """Check if site is running WordPress"""
        wp_indicators = [
            'wp-content',
            'wp-includes',
            'wordpress',
            'wp-json',
            'generator.*wordpress'
        ]
        
        content_lower = html_content.lower()
        return any(indicator in content_lower for indicator in wp_indicators)
    
    def _has_ecommerce_features(self, html_content: str) -> bool:
        """Check for e-commerce features in the HTML"""
        ecommerce_patterns = [
            r'add.to.cart',
            r'shop.*page',
            r'product.*price',
            r'cart.*total',
            r'checkout',
            r'currency'
        ]
        
        content_lower = html_content.lower()
        return any(re.search(pattern, content_lower) for pattern in ecommerce_patterns)
    
    def _extract_store_info(self, html_content: str):
        """Extract store metadata from HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract store name
        title_tag = soup.find('title')
        if title_tag:
            self.store_info['store_name'] = title_tag.text.strip()
        
        # Look for WooCommerce configuration in scripts
        for script in soup.find_all('script'):
            if script.string and 'woocommerce' in script.string.lower():
                try:
                    # Extract currency
                    currency_match = re.search(r'currency["\']?\s*:\s*["\']([^"\']+)["\']', script.string)
                    if currency_match:
                        self.store_info['currency'] = currency_match.group(1)
                    
                    # Extract shop URL
                    shop_url_match = re.search(r'shop_url["\']?\s*:\s*["\']([^"\']+)["\']', script.string)
                    if shop_url_match:
                        self.store_info['shop_url'] = shop_url_match.group(1)
                except Exception:
                    pass
    
    def _test_woocommerce_api(self) -> bool:
        """Test if WooCommerce API endpoints are accessible"""
        api_endpoints = [
            '/wp-json/wc/v3/products',
            '/wp-json/wc/v2/products',
            '/wp-json/wc/v1/products'
        ]
        
        for endpoint in api_endpoints:
            url = f"{self.site_url}{endpoint}"
            
            # Try with authentication if available
            auth = self.api_auth if self.api_auth else None
            
            try:
                response = requests.get(url, auth=auth, timeout=10, 
                                     headers=self.session.headers)
                
                if response.status_code in [200, 401]:  # 401 means API exists but needs auth
                    try:
                        data = response.json()
                        if isinstance(data, list) or 'code' in data:
                            return True
                    except json.JSONDecodeError:
                        continue
            except requests.RequestException:
                continue
        
        return False
    
    # =====================================
    # 3 Main Scrape Products Methods
    # =====================================
    def scrape_products(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Scrape products from a WooCommerce store.
        
        Args:
            limit: Maximum number of products to scrape
            
        Returns:
            List of product dictionaries
        """
        all_products = []
        
        # Strategy 1: Use WooCommerce REST API if available
        if self.api_auth:
            products_from_api = self._scrape_via_api(limit)
            if products_from_api:
                all_products.extend(products_from_api)
                logger.info(f"Retrieved {len(products_from_api)} products via WooCommerce API")
        
        # Strategy 2: HTML scraping (fallback or primary method)
        if len(all_products) < limit:
            remaining_limit = limit - len(all_products)
            products_from_html = self._scrape_via_html(remaining_limit)
            all_products.extend(products_from_html)
            logger.info(f"Retrieved {len(products_from_html)} products via HTML scraping")
        
        # Normalize all products
        normalized_products = []
        for product in all_products[:limit]:
            try:
                normalized = self.normalize_product_data(product)
                normalized_products.append(normalized)
            except Exception as e:
                logger.warning(f"Failed to normalize product: {e}")
                continue
        
        logger.info(f"Successfully processed {len(normalized_products)} products from WooCommerce store")
        return normalized_products
    def extract_product_details(self, product_url: str) -> Dict[str, Any]:
        """
        Extract detailed information for a specific product.
        
        Args:
            product_url: URL of the product page
            
        Returns:
            Dictionary with product details
        """
        details = {}
        response = self._make_request(product_url)
        if not response:
            return details
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try to extract structured data (JSON-LD)
        json_ld = soup.find('script', type='application/ld+json')
        if json_ld:
            try:
                ld_data = json.loads(json_ld.string)
                if isinstance(ld_data, list):
                    ld_data = ld_data[0]
                
                if ld_data.get('@type') == 'Product':
                    details.update({
                        'title': ld_data.get('name', ''),
                        'description': ld_data.get('description', ''),
                        'brand': ld_data.get('brand', {}).get('name', ''),
                        'sku': ld_data.get('sku', ''),
                        'rating': ld_data.get('aggregateRating', {}).get('ratingValue', 0),
                        'review_count': ld_data.get('aggregateRating', {}).get('reviewCount', 0)
                    })
            except (json.JSONDecodeError, KeyError):
                pass
        
        # Extract from WooCommerce specific elements
        
        # Product description
        desc_selectors = [
            '.woocommerce-product-details__short-description',
            '.product_description',
            '.entry-summary .summary',
            '#tab-description'
        ]
        for selector in desc_selectors:
            desc_el = soup.select_one(selector)
            if desc_el:
                details['description'] = desc_el.get_text(strip=True)[:500]
                break
        
        # Product meta information
        meta_el = soup.select_one('.product_meta')
        if meta_el:
            # SKU
            sku_el = meta_el.select_one('.sku')
            if sku_el:
                details['sku'] = sku_el.get_text(strip=True)
            
            # Categories
            categories_el = meta_el.select_one('.posted_in')
            if categories_el:
                category_links = categories_el.select('a')
                details['categories'] = [link.get_text(strip=True) for link in category_links]
            
            # Tags
            tags_el = meta_el.select_one('.tagged_as')
            if tags_el:
                tag_links = tags_el.select('a')
                details['tags'] = [link.get_text(strip=True) for link in tag_links]
        
        # Product rating
        rating_el = soup.select_one('.woocommerce-product-rating')
        if rating_el:
            rating_text = rating_el.get_text()
            rating, review_count = self._extract_rating(rating_text)
            if rating > 0:
                details['rating'] = rating
                details['review_count'] = review_count
        
        # Additional product images
        gallery_images = soup.select('.woocommerce-product-gallery__image img')
        if gallery_images:
            details['additional_images'] = []
            for img in gallery_images:
                img_src = img.get('data-large_image') or img.get('src')
                if img_src:
                    details['additional_images'].append(urljoin(self.site_url, img_src))
        
        return details
    
    # =====================================
    # 4 Scrape via API
    # =====================================
    def _scrape_via_api(self, limit: int) -> List[Dict[str, Any]]:
        """Scrape products using WooCommerce REST API"""
        products = []
        
        if not self.api_auth:
            return products
        
        # WooCommerce API endpoints to try
        api_versions = ['v3', 'v2', 'v1']
        
        for version in api_versions:
            api_url = f"{self.site_url}/wp-json/wc/{version}/products"
            params = {
                'per_page': min(limit, 100),  # WooCommerce API limit
                'status': 'publish'
            }
            
            if self.category:
                # Try to find category ID first
                categories_url = f"{self.site_url}/wp-json/wc/{version}/products/categories"
                cat_response = requests.get(categories_url, auth=self.api_auth, 
                                          headers=self.session.headers, timeout=10)
                
                if cat_response.status_code == 200:
                    try:
                        categories = cat_response.json()
                        for cat in categories:
                            if cat.get('slug') == self.category or cat.get('name').lower() == self.category.lower():
                                params['category'] = cat['id']
                                break
                    except (json.JSONDecodeError, KeyError):
                        pass
            
            try:
                response = requests.get(api_url, auth=self.api_auth, params=params,
                                      headers=self.session.headers, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        logger.info(f"Successfully accessed WooCommerce API {version}: found {len(data)} products")
                        
                        for product in data:
                            product_data = self._parse_api_product(product)
                            if product_data:
                                products.append(product_data)
                        
                        break  # Success, no need to try other versions
                        
            except (requests.RequestException, json.JSONDecodeError) as e:
                logger.warning(f"Error accessing WooCommerce API {version}: {e}")
                continue
        
        return products
    
    def _parse_api_product(self, product: Dict) -> Optional[Dict[str, Any]]:
        """Parse product data from WooCommerce API response"""
        try:
            # Handle price (can be string or number)
            price = 0.0
            if product.get('price'):
                price = float(product['price'])
            elif product.get('regular_price'):
                price = float(product['regular_price'])
            
            product_data = {
                'id': str(product.get('id', '')),
                'title': product.get('name', ''),
                'description': self._clean_html_description(product.get('description', '')),
                'short_description': self._clean_html_description(product.get('short_description', '')),
                'price': price,
                'regular_price': float(product.get('regular_price', 0)) if product.get('regular_price') else price,
                'sale_price': float(product.get('sale_price', 0)) if product.get('sale_price') else None,
                'available': product.get('in_stock', True) and product.get('stock_status') == 'instock',
                'stock_quantity': product.get('stock_quantity'),
                'sku': product.get('sku', ''),
                'weight': product.get('weight', ''),
                'url': product.get('permalink', ''),
                'product_type': product.get('type', ''),
                'status': product.get('status', ''),
                'featured': product.get('featured', False),
                'catalog_visibility': product.get('catalog_visibility', ''),
                'date_created': product.get('date_created', ''),
                'date_modified': product.get('date_modified', ''),
                'categories': [],
                'tags': [],
                'images': []
            }
            
            # Extract categories
            for category in product.get('categories', []):
                product_data['categories'].append({
                    'id': category.get('id'),
                    'name': category.get('name'),
                    'slug': category.get('slug')
                })
            
            # Extract tags
            for tag in product.get('tags', []):
                product_data['tags'].append({
                    'id': tag.get('id'),
                    'name': tag.get('name'),
                    'slug': tag.get('slug')
                })
            
            # Extract images
            for image in product.get('images', []):
                product_data['images'].append({
                    'id': image.get('id'),
                    'src': image.get('src'),
                    'name': image.get('name'),
                    'alt': image.get('alt')
                })
            
            # Set main image
            if product_data['images']:
                product_data['image_url'] = product_data['images'][0]['src']
            
            # Extract vendor/brand if available in meta data
            meta_data = product.get('meta_data', [])
            for meta in meta_data:
                if meta.get('key') in ['_brand', 'brand', 'vendor', '_vendor']:
                    product_data['vendor'] = meta.get('value', '')
                    break
            
            # Extract ratings if available
            if product.get('average_rating'):
                product_data['rating'] = float(product['average_rating'])
            if product.get('rating_count'):
                product_data['review_count'] = int(product['rating_count'])
            
            return product_data
            
        except Exception as e:
            logger.warning(f"Error parsing WooCommerce API product: {e}")
            return None
    
    # =====================================
    # 5 Scrape via HTML
    # =====================================
    def _scrape_via_html(self, limit: int) -> List[Dict[str, Any]]:
        """Scrape products via HTML parsing"""
        products = []
        
        # Get shop/product listing URLs
        urls_to_scrape = self._get_shop_urls()
        
        for url in urls_to_scrape:
            if len(products) >= limit:
                break
                
            page_products = self._scrape_shop_page(url, limit - len(products))
            products.extend(page_products)
        
        return products
    
    def _get_shop_urls(self) -> List[str]:
        """Get list of shop/category URLs to scrape"""
        urls = []
        
        # Common WooCommerce shop URLs
        shop_paths = ['/shop/', '/store/', '/products/', '/shop']
        
        for path in shop_paths:
            test_url = f"{self.site_url}{path}"
            response = self._make_request(test_url)
            if response and response.status_code == 200:
                if 'woocommerce' in response.text.lower() or 'product' in response.text.lower():
                    urls.append(test_url)
                    break
        
        # If category specified, try to find category URL
        if self.category:
            category_urls = [
                f"{self.site_url}/product-category/{self.category}/",
                f"{self.site_url}/shop/category/{self.category}/",
                f"{self.site_url}/category/{self.category}/"
            ]
            
            for cat_url in category_urls:
                response = self._make_request(cat_url)
                if response and response.status_code == 200:
                    urls.append(cat_url)
                    break
        
        return urls if urls else [self.site_url]
    
    def _scrape_shop_page(self, url: str, limit: int) -> List[Dict[str, Any]]:
        """Scrape products from a shop/category page"""
        products = []
        response = self._make_request(url)
        if not response:
            return products
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # WooCommerce product selectors
        product_selectors = [
            '.woocommerce ul.products li.product',
            '.products .product',
            '.wc-block-grid__product',
            '.product-item',
            '[data-product-id]',
            '.type-product'
        ]
        
        product_elements = []
        for selector in product_selectors:
            elements = soup.select(selector)
            if elements:
                product_elements = elements
                logger.info(f"Found {len(elements)} products using selector: {selector}")
                break
        
        for i, product_el in enumerate(product_elements):
            if i >= limit:
                break
            
            product_data = self._extract_product_from_element(product_el)
            if product_data:
                products.append(product_data)
        
        return products
    
    def _extract_product_from_element(self, element) -> Optional[Dict[str, Any]]:
        """Extract product data from HTML element"""
        try:
            product_data = {
                'has_image': False  # Initialize has_image field
            }
            
            # Get product URL
            link_selectors = [
                'a.woocommerce-LoopProduct-link', 
                'h2 a', 
                'h3 a', 
                '.product-title a', 
                'a',
                '.product a',
                '.woocommerce-loop-product__link'
            ]
            product_link = None
            for selector in link_selectors:
                product_link = element.select_one(selector)
                if product_link and product_link.get('href'):
                    break
            
            if not product_link:
                return None
            
            product_url = urljoin(self.site_url, product_link.get('href'))
            product_data['url'] = product_url
            
            # Extract product ID
            product_id = element.get('data-product-id') or element.get('data-product_id')
            if product_id:
                product_data['id'] = str(product_id)
            
            # Get title
            title_selectors = [
                'h2.woocommerce-loop-product__title',
                'h3.woocommerce-loop-product__title',
                '.product-title',
                'h2 a', 
                'h3 a',
                '.woocommerce-loop-product__title',
                '.product-title a'
            ]
            
            for selector in title_selectors:
                title_el = element.select_one(selector)
                if title_el:
                    product_data['title'] = title_el.get_text(strip=True)
                    break
            
            # Get price
            price_selectors = [
                '.price .woocommerce-Price-amount',
                '.price ins .woocommerce-Price-amount',
                '.price',
                '.product-price',
                '.woocommerce-Price-amount',
                'span.price'
            ]
            
            for selector in price_selectors:
                price_el = element.select_one(selector)
                if price_el:
                    price_text = price_el.get_text(strip=True)
                    product_data['price'] = self._parse_price(price_text)
                    break
            
            # Get image
            img_selectors = [
                '.wp-post-image', 
                '.product-image img', 
                'img',
                '.woocommerce-loop-product__image img',
                '.product-image img'
            ]
            for selector in img_selectors:
                img_el = element.select_one(selector)
                if img_el:
                    img_src = img_el.get('data-src') or img_el.get('src')
                    if img_src:
                        product_data['image_url'] = urljoin(self.site_url, img_src)
                        product_data['has_image'] = True
                        break
            
            # Check if product is on sale
            if element.select_one('.onsale'):
                product_data['on_sale'] = True
            
            # Check availability
            if element.select_one('.outofstock'):
                product_data['available'] = False
            else:
                product_data['available'] = True
            
            return product_data
            
        except Exception as e:
            logger.warning(f"Error extracting product from element: {e}")
            return None
    
    # =====================================
    # 6 Utility Methods
    # =====================================
    def _clean_html_description(self, html_desc: str) -> str:
        """Clean HTML description to plain text"""
        if not html_desc:
            return ""
        
        soup = BeautifulSoup(html_desc, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        return text[:500]  # Limit description length

    def scrape(self) -> List[Dict[str, Any]]:
        """
        Scrape the products from the WooCommerce site
        
        Returns:
            List[Dict[str, Any]]: List of normalized products
        """
        products = []
        page = 1
        per_page = 100  # Maximum allowed by WooCommerce
        
        while True:
            try:
                # Call to WooCommerce API
                response = requests.get(
                    f"{self.api_base}products",
                    params={
                        'consumer_key': self.consumer_key,
                        'consumer_secret': self.consumer_secret,
                        'per_page': per_page,
                        'page': page,
                        'category': self.category if self.category else None
                    },
                    timeout=10
                )
                
                if response.status_code != 200:
                    logger.error(f"Error fetching products: {response.status_code}")
                    break
                    
                data = response.json()
                if not data:
                    break
                    
                # Normalize products
                for product in data:
                    normalized_product = self._normalize_product(product)
                    if normalized_product:
                        products.append(normalized_product)
                
                # Check if there are more pages
                if len(data) < per_page:
                    break
                    
                page += 1
                time.sleep(1)  # Respect API limits
                
            except Exception as e:
                logger.error(f"Error scraping WooCommerce products: {e}")
                break
                
        return products
        
    def _normalize_product(self, product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Normalize a WooCommerce product to standard format
        
        Args:
            product: Raw product data from WooCommerce
            
        Returns:
            Optional[Dict[str, Any]]: Normalized product or None if invalid
        """
        try:
            # Extract images
            images = []
            if product.get('images'):
                for image in product['images']:
                    if image.get('src'):
                        images.append({
                            'url': image['src'],
                            'alt': image.get('alt', '')
                        })
            
            # Extract variations
            variations = []
            if product.get('variations'):
                for variation_id in product['variations']:
                    try:
                        variation = requests.get(
                            f"{self.api_base}products/{product['id']}/variations/{variation_id}",
                            params={
                                'consumer_key': self.consumer_key,
                                'consumer_secret': self.consumer_secret
                            },
                            timeout=5
                        ).json()
                        
                        if variation:
                            variations.append({
                                'id': variation['id'],
                                'sku': variation.get('sku', ''),
                                'price': float(variation.get('price', 0)),
                                'regular_price': float(variation.get('regular_price', 0)),
                                'sale_price': float(variation.get('sale_price', 0)) if variation.get('sale_price') else None,
                                'stock_quantity': variation.get('stock_quantity', 0),
                                'attributes': variation.get('attributes', [])
                            })
                    except Exception as e:
                        logger.warning(f"Error fetching variation {variation_id}: {e}")
                        continue
            
            # Build normalized product
            return {
                'id': str(product['id']),
                'name': product['name'],
                'description': product.get('description', ''),
                'price': float(product.get('price', 0)),
                'regular_price': float(product.get('regular_price', 0)),
                'sale_price': float(product.get('sale_price', 0)) if product.get('sale_price') else None,
                'currency': 'USD',  # WooCommerce uses configured currency
                'sku': product.get('sku', ''),
                'brand': product.get('brand', ''),
                'category': product.get('categories', [{}])[0].get('name', '') if product.get('categories') else '',
                'url': product.get('permalink', ''),
                'images': images,
                'variations': variations,
                'stock_quantity': product.get('stock_quantity', 0),
                'in_stock': product.get('stock_status') == 'instock',
                'rating': float(product.get('average_rating', 0)),
                'review_count': int(product.get('review_count', 0)),
                'attributes': product.get('attributes', []),
                'tags': [tag['name'] for tag in product.get('tags', [])],
                'created_at': product.get('date_created'),
                'updated_at': product.get('date_modified')
            }
            
        except Exception as e:
            logger.error(f"Error normalizing WooCommerce product: {e}")
            return None
            
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Return performance statistics of the agent
        
        Returns:
            Dict[str, Any]: Performance statistics
        """
        return {
            'platform': 'WooCommerce',
            'api_base': self.api_base,
            'has_credentials': bool(self.consumer_key and self.consumer_secret),
            'category': self.category
        }

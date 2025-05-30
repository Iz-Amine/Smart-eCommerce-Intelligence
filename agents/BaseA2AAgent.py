"""
Base Agent-to-Agent (A2A) module - Version Améliorée
Defines the common interface for all e-commerce platform agents.
"""
from abc import ABC, abstractmethod
import logging
import time
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class BaseA2AAgent(ABC):
    """Base class for all Agent-to-Agent scrapers"""
    
    
    def __init__(self, site_url: str, category: Optional[str] = None):
        """
        Initialize the base agent with common attributes.
        
        Args:
            site_url: The base URL of the e-commerce site
            category: Optional category to focus scraping on
        """
        self.site_url = site_url.rstrip('/')  # Remove trailing slash if present
        self.category = category
        self.logger = logging.getLogger(self.__class__.__name__)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'SmartEcommerceMVP/1.0 (Educational Project)'
        })
        
        # Métriques de performance
        self.requests_count = 0
        self.successful_requests = 0
        self.start_time = datetime.now()
    
    # =====================================
    # HTTP Request Management
    # =====================================
    def _make_request(self, url: str, params: Optional[Dict] = None, 
                     max_retries: int = 3, retry_delay: int = 2) -> Optional[requests.Response]:
        """
        Make an HTTP request with retry logic and error handling.
        
        Args:
            url: The URL to request
            params: Optional query parameters
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            Response object or None if all attempts failed
        """
        self.requests_count += 1
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                self.successful_requests += 1
                time.sleep(1)  # Polite delay to avoid overwhelming the server
                return response
            except requests.RequestException as e:
                self.logger.warning(f"Request failed (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    self.logger.error(f"Max retries reached for URL: {url}")
                    return None
    
    # =====================================
    # Data Cleaning & Normalization
    # =====================================
    def _clean_title(self, title: str) -> str:
        """Clean and normalize product title"""
        if not title:
            return ""
        # Remove extra whitespace and special characters
        cleaned = re.sub(r'\s+', ' ', title.strip())
        # Remove common noise words/chars
        cleaned = re.sub(r'[^\w\s\-\(\)\[\]]+', '', cleaned)
        return cleaned[:100]  # Limit length
    
    def _parse_price(self, price_text: Any) -> float:
        """Extract numeric price from various formats"""
        if isinstance(price_text, (int, float)):
            return float(price_text)
        
        if isinstance(price_text, str):
            # Remove currency symbols and extract number
            price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
            if price_match:
                return float(price_match.group().replace(',', ''))
        
        return 0.0
    
    def _extract_rating(self, rating_text: str) -> tuple[float, int]:
        """Extract rating value and review count from text"""
        rating = 0.0
        review_count = 0
        
        if not rating_text:
            return rating, review_count
        
        # Look for rating pattern (X.X/5 or X.X stars)
        rating_match = re.search(r'([\d\.]+)\s*[\/\s]*[5\s]*(?:stars?|étoiles?)?', rating_text.lower())
        if rating_match:
            rating = min(float(rating_match.group(1)), 5.0)
        
        # Look for review count
        reviews_match = re.search(r'(\d+)\s*(?:reviews?|avis|commentaires?)', rating_text.lower())
        if reviews_match:
            review_count = int(reviews_match.group(1))
        
        return rating, review_count
    
    def normalize_product_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardize product data for ML analysis
        
        Args:
            raw_data: Raw product data from scraping
            
        Returns:
            Normalized product dictionary
        """
        # Extract rating and review count
        rating, review_count = self._extract_rating(raw_data.get('rating_text', ''))
        if 'rating' in raw_data:
            rating = raw_data['rating']
        if 'review_count' in raw_data:
            review_count = raw_data['review_count']
        
        normalized = {
            'id': raw_data.get('id', ''),
            'title': self._clean_title(raw_data.get('title', '')),
            'price': self._parse_price(raw_data.get('price', 0)),
            'rating': rating,
            'review_count': review_count,
            'availability': raw_data.get('available', True),
            'description_length': len(raw_data.get('description', '')),
            'vendor': raw_data.get('vendor', 'Unknown'),
            'category': raw_data.get('product_type', raw_data.get('category', 'Other')),
            'image_url': raw_data.get('image_url', ''),
            'product_url': raw_data.get('url', ''),
            'scraped_at': datetime.now().isoformat(),
            'platform': self.__class__.__name__.replace('Agent', '').lower(),
            'source_site': self.site_url
        }
        
        # Add computed features for ML
        normalized.update({
            'has_image': bool(normalized['image_url']),
            'has_description': normalized['description_length'] > 0,
            'title_length': len(normalized['title']),
            'price_category': self._categorize_price(normalized['price']),
            'rating_category': self._categorize_rating(normalized['rating']),
            'popularity_score': self._calculate_popularity_score(normalized)
        })
        
        return normalized
    
    # =====================================
    # Data Categorization
    # =====================================
    def _categorize_price(self, price: float) -> str:
        """Categorize price into ranges"""
        if price == 0:
            return 'free'
        elif price < 20:
            return 'low'
        elif price < 100:
            return 'medium'
        elif price < 500:
            return 'high'
        else:
            return 'premium'
    
    def _categorize_rating(self, rating: float) -> str:
        """Categorize rating"""
        if rating >= 4.5:
            return 'excellent'
        elif rating >= 4.0:
            return 'very_good'
        elif rating >= 3.0:
            return 'good'
        elif rating >= 2.0:
            return 'fair'
        elif rating > 0:
            return 'poor'
        else:
            return 'no_rating'
    
    # =====================================
    # Data Ranking
    # =====================================
    def _calculate_popularity_score(self, product: Dict[str, Any]) -> float:
        """Calculate a simple popularity score for ranking"""
        score = 0.0
        
        # Rating contribution (0-5 -> 0-50 points)
        score += product['rating'] * 10
        
        # Review count contribution (logarithmic)
        if product['review_count'] > 0:
            score += min(20, 5 * (product['review_count'] ** 0.3))
        
        # Availability bonus
        if product['availability']:
            score += 5
        
        # Description quality bonus
        if product['description_length'] > 100:
            score += 3
        
        # Image bonus
        if product['has_image']:
            score += 2
        
        return round(score, 2)
    
    # =====================================
    # Performance Monitoring
    # =====================================
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get scraping performance statistics"""
        elapsed_time = (datetime.now() - self.start_time).total_seconds()
        success_rate = (self.successful_requests / self.requests_count * 100) if self.requests_count > 0 else 0
        
        return {
            'total_requests': self.requests_count,
            'successful_requests': self.successful_requests,
            'success_rate_percent': round(success_rate, 2),
            'elapsed_time_seconds': round(elapsed_time, 2),
            'requests_per_second': round(self.requests_count / elapsed_time, 2) if elapsed_time > 0 else 0
        }
    
    # =====================================
    # Abstract Methods
    # =====================================
    @abstractmethod
    def detect_platform(self) -> bool:
        """
        Detect if the site matches the agent's target platform.
        
        Returns:
            True if the site matches the platform, False otherwise
        """
        pass
    
    @abstractmethod
    def scrape_products(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Scrape products from the site.
        
        Args:
            limit: Maximum number of products to scrape
            
        Returns:
            List of product dictionaries with standardized attributes
        """
        pass
    
    @abstractmethod
    def extract_product_details(self, product_url: str) -> Dict[str, Any]:
        """
        Extract detailed information for a specific product.
        
        Args:
            product_url: URL of the product page
            
        Returns:
            Dictionary with product details
        """
        pass
    
    # =====================================
    # Scrape and Normalize
    # =====================================
    def scrape_and_normalize(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Scrape products and return normalized data ready for ML pipeline
        
        Args:
            limit: Maximum number of products to scrape
            
        Returns:
            List of normalized product dictionaries
        """
        raw_products = self.scrape_products(limit)
        normalized_products = []
        
        for product in raw_products:
            try:
                normalized = self.normalize_product_data(product)
                normalized_products.append(normalized)
            except Exception as e:
                self.logger.warning(f"Failed to normalize product {product.get('id', 'unknown')}: {e}")
        
        self.logger.info(f"Successfully normalized {len(normalized_products)}/{len(raw_products)} products")
        return normalized_products


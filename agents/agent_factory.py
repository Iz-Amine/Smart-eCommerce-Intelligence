"""
Enhanced Agent Factory - Complete implementation with proven strategies
Factory Pattern pour créer les agents A2A appropriés avec support des stratégies éprouvées
"""
from typing import Optional, Dict, Any, List, Union, Callable
import logging
import json
import csv
from urllib.parse import urlparse
from datetime import datetime
import concurrent.futures
import time
import os
import sys

# Add the project root to the sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from .BaseA2AAgent import BaseA2AAgent
from .ShopifyAgent import ShopifyAgent
from .WooCommerceAgent import WooCommerceAgent
from DB.db import SessionLocal
from DB.models import Store, Product, ScrapingLog
from DB.db_utils import get_or_create_store, add_or_update_product

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EnhancedAgentFactory:
    """Enhanced Factory pour créer et gérer les agents A2A avec stratégies éprouvées"""
    
    # Registry des agents disponibles
    AVAILABLE_AGENTS = {
        'shopify': ShopifyAgent,
        'woocommerce': WooCommerceAgent
    }
    
    # Configuration par défaut pour chaque plateforme
    DEFAULT_CONFIGS = {
        'shopify': {
            'with_variants': False,
            'max_retries': 3,
            'delay_between_requests': 1.0,
            'timeout': 10
        },
        'woocommerce': {
            'max_retries': 3,
            'delay_between_requests': 1.0,
            'timeout': 10
        }
    }
    
    # =====================================
    # 1 Core Agent Creation
    # =====================================
    @classmethod
    def create_agent(cls, site_url: str, 
                    category: Optional[str] = None, 
                    platform_hint: Optional[str] = None,
                    with_variants: bool = False,
                    **kwargs) -> Optional[BaseA2AAgent]:
        """
        Crée l'agent approprié pour le site donné avec support des stratégies éprouvées
        
        Args:
            site_url: URL du site e-commerce
            category: Catégorie optionnelle à scraper
            platform_hint: Indice sur la plateforme (shopify, woocommerce)
            with_variants: Pour Shopify, inclure les détails des variantes
            **kwargs: Arguments supplémentaires pour l'agent (API keys, etc.)
            
        Returns:
            Instance de l'agent approprié ou None si aucun agent compatible
        """
        logger.info(f"Creating enhanced agent for site: {site_url}")
        
        # Nettoyer l'URL
        cleaned_url = cls._clean_url(site_url)
        
        # Si un platform_hint est fourni, essayer en premier
        if platform_hint and platform_hint.lower() in cls.AVAILABLE_AGENTS:
            agent = cls._create_specific_agent(
                platform=platform_hint.lower(),
                site_url=cleaned_url,
                category=category,
                with_variants=with_variants,
                **kwargs
            )
            
            if agent and agent.detect_platform():
                logger.info(f"Successfully created {platform_hint} agent using hint")
                return agent
            else:
                logger.warning(f"Platform hint '{platform_hint}' didn't match, falling back to auto-detection")
        
        # Auto-détection : tester chaque agent
        for platform_name, agent_class in cls.AVAILABLE_AGENTS.items():
            try:
                agent = cls._create_specific_agent(
                    platform=platform_name,
                    site_url=cleaned_url,
                    category=category,
                    with_variants=with_variants,
                    **kwargs
                )
                
                if agent.detect_platform():
                    logger.info(f"Auto-detected platform: {platform_name}")
                    return agent
                    
            except Exception as e:
                logger.warning(f"Error testing {platform_name} agent: {e}")
                continue
        
        logger.error(f"No compatible agent found for site: {cleaned_url}")
        return None
    
    @classmethod
    def _clean_url(cls, site_url: str) -> str:
        """Nettoie et valide l'URL"""
        if not site_url.startswith(('http://', 'https://')):
            site_url = 'https://' + site_url
        
        # Supprimer le slash final
        return site_url.rstrip('/')
    
    @classmethod
    def _create_specific_agent(cls, platform: str, site_url: str, 
                              category: Optional[str], with_variants: bool = False,
                              **kwargs) -> BaseA2AAgent:
        """Crée une instance spécifique d'agent avec gestion des paramètres avancée"""
        
        agent_class = cls.AVAILABLE_AGENTS[platform]
        
        # Obtenir la configuration par défaut
        default_config = cls.DEFAULT_CONFIGS.get(platform, {})
        
        if platform == 'shopify':
            # Configuration Shopify avec support des variantes
            agent_kwargs = {
                'api_key': kwargs.get('api_key') or kwargs.get('shopify_api_key'),
                'with_variants': with_variants
            }
            # Filtrer les valeurs None
            agent_kwargs = {k: v for k, v in agent_kwargs.items() if v is not None}
            
        elif platform == 'woocommerce':
            # Configuration WooCommerce
            agent_kwargs = {
                'consumer_key': kwargs.get('consumer_key') or kwargs.get('wc_consumer_key'),
                'consumer_secret': kwargs.get('consumer_secret') or kwargs.get('wc_consumer_secret')
            }
            # Filtrer les valeurs None
            agent_kwargs = {k: v for k, v in agent_kwargs.items() if v is not None}
            
        else:
            agent_kwargs = {}
        
        # Ajouter la configuration par défaut
        agent_kwargs.update(default_config)
        
        return agent_class(site_url, category, **agent_kwargs)
    
    @classmethod
    def create_multiple_agents(cls, site_configs: List[Dict[str, Any]]) -> Dict[str, BaseA2AAgent]:
        """
        Crée plusieurs agents à partir d'une liste de configurations
        
        Args:
            site_configs: Liste de configurations de sites
                Format: [
                    {
                        'site_url': 'https://example.com',
                        'category': 'electronics',
                        'platform_hint': 'shopify',
                        'with_variants': True,
                        'api_key': 'xxx'
                    },
                    ...
                ]
                
        Returns:
            Dictionnaire {site_url: agent} des agents créés avec succès
        """
        agents = {}
        
        logger.info(f"Creating {len(site_configs)} agents...")
        
        for i, config in enumerate(site_configs, 1):
            site_url = config.get('site_url')
            if not site_url:
                logger.warning(f"Configuration {i}: Missing site_url, skipping")
                continue
            
            try:
                logger.info(f"Creating agent {i}/{len(site_configs)} for {site_url}")
                agent = cls.create_agent(**config)
                
                if agent:
                    agents[site_url] = agent
                    logger.info(f"✓ Successfully created agent for {site_url}")
                else:
                    logger.warning(f"✗ Failed to create agent for {site_url}")
                    
            except Exception as e:
                logger.error(f"✗ Error creating agent for {site_url}: {e}")
                continue
        
        success_rate = (len(agents) / len(site_configs)) * 100
        logger.info(f"Agent creation completed: {len(agents)}/{len(site_configs)} ({success_rate:.1f}%) successful")
        return agents
    
    
    # =====================================
    # 2 Scraping Functions
    # =====================================
    @classmethod
    def scrape_single_site(cls, site_url: str, 
                          limit: int = 100,
                          platform_hint: Optional[str] = None,
                          with_variants: bool = False,
                          export_format: Optional[str] = None,
                          **kwargs) -> Dict[str, Any]:
        """
        Scrape un seul site avec stratégies éprouvées
        
        Args:
            site_url: URL du site à scraper
            limit: Nombre maximum de produits
            platform_hint: Indice de plateforme
            with_variants: Inclure les variantes (Shopify)
            export_format: Format d'export ('csv', 'json', None)
            **kwargs: Arguments supplémentaires
            
        Returns:
            Dictionnaire avec résultats et métadonnées
        """
        start_time = datetime.now()
        result = {
            'site_url': site_url,
            'success': False,
            'products': [],
            'product_count': 0,
            'platform': None,
            'execution_time_seconds': 0,
            'error': None,
            'export_file': None,
            'performance_stats': {}
        }
        
        try:
            logger.info(f"Starting single site scraping: {site_url}")
            
            # Créer l'agent
            agent = cls.create_agent(
                site_url=site_url,
                platform_hint=platform_hint,
                with_variants=with_variants,
                **kwargs
            )
            
            if not agent:
                result['error'] = "Could not create compatible agent"
                return result
            
            result['platform'] = agent.__class__.__name__.replace('Agent', '').lower()
            
            # Scraper les produits
            logger.info(f"Scraping {limit} products from {site_url}")
            products = agent.scrape_products(limit=limit)
            
            result['products'] = products
            result['product_count'] = len(products)
            result['success'] = len(products) > 0
            
            # Statistiques de performance
            result['performance_stats'] = agent.get_performance_stats()
            
            # Export si demandé
            if export_format and products:
                result['export_file'] = cls._export_products(
                    products=products,
                    site_url=site_url,
                    format=export_format,
                    with_variants=with_variants,
                    agent=agent
                )
            
            execution_time = (datetime.now() - start_time).total_seconds()
            result['execution_time_seconds'] = round(execution_time, 2)
            
            logger.info(f"✓ Successfully scraped {len(products)} products from {site_url}")
            
        except Exception as e:
            result['error'] = str(e)
            result['execution_time_seconds'] = (datetime.now() - start_time).total_seconds()
            logger.error(f"✗ Error scraping {site_url}: {e}")
        
        return result
    
    @classmethod
    def scrape_multiple_sites(cls, site_configs: List[Dict[str, Any]], 
                             products_per_site: int = 50,
                             parallel: bool = False,
                             max_workers: int = 3,
                             export_format: Optional[str] = None) -> Dict[str, Any]:
        """
        Scrape plusieurs sites avec support du parallélisme
        
        Args:
            site_configs: Configurations des sites
            products_per_site: Nombre de produits à scraper par site
            parallel: Utiliser le scraping parallèle
            max_workers: Nombre maximum de workers parallèles
            export_format: Format d'export ('csv', 'json', None)
            
        Returns:
            Dictionnaire avec résultats agrégés
        """
        start_time = datetime.now()
        results = {
            'total_sites': len(site_configs),
            'successful_sites': 0,
            'failed_sites': 0,
            'total_products': 0,
            'execution_time_seconds': 0,
            'sites': {},
            'summary': {},
            'export_files': []
        }
        
        logger.info(f"Starting multi-site scraping: {len(site_configs)} sites, {products_per_site} products each")
        logger.info(f"Parallel mode: {parallel} (max_workers: {max_workers})")
        
        if parallel and len(site_configs) > 1:
            results['sites'] = cls._scrape_sites_parallel(
                site_configs, products_per_site, max_workers, export_format
            )
        else:
            results['sites'] = cls._scrape_sites_sequential(
                site_configs, products_per_site, export_format
            )
        
        # Calculer les statistiques
        for site_url, site_result in results['sites'].items():
            if site_result['success']:
                results['successful_sites'] += 1
                results['total_products'] += site_result['product_count']
                if site_result.get('export_file'):
                    results['export_files'].append(site_result['export_file'])
            else:
                results['failed_sites'] += 1
        
        # Temps d'exécution total
        results['execution_time_seconds'] = round((datetime.now() - start_time).total_seconds(), 2)
        
        # Résumé par plateforme
        platform_summary = {}
        for site_result in results['sites'].values():
            platform = site_result.get('platform', 'unknown')
            if platform not in platform_summary:
                platform_summary[platform] = {'sites': 0, 'products': 0, 'success_rate': 0}
            
            platform_summary[platform]['sites'] += 1
            if site_result['success']:
                platform_summary[platform]['products'] += site_result['product_count']
        
        # Calculer les taux de succès
        for platform_data in platform_summary.values():
            platform_data['success_rate'] = round(
                (platform_data['products'] / (platform_data['sites'] * products_per_site)) * 100, 1
            ) if platform_data['sites'] > 0 else 0
        
        results['summary'] = platform_summary
        
        # Export combiné si demandé
        if export_format:
            combined_file = cls._create_combined_export(results, export_format)
            if combined_file:
                results['export_files'].append(combined_file)
        
        success_rate = (results['successful_sites'] / results['total_sites']) * 100
        logger.info(f"Multi-site scraping completed:")
        logger.info(f"  ✓ Success: {results['successful_sites']}/{results['total_sites']} sites ({success_rate:.1f}%)")
        logger.info(f"  📦 Total products: {results['total_products']}")
        logger.info(f"  ⏱️  Execution time: {results['execution_time_seconds']}s")
        
        return results
    
    @classmethod
    def _scrape_sites_sequential(cls, site_configs: List[Dict[str, Any]], 
                                products_per_site: int,
                                export_format: Optional[str]) -> Dict[str, Dict[str, Any]]:
        """Scrape les sites de manière séquentielle"""
        results = {}
        
        for i, config in enumerate(site_configs, 1):
            site_url = config.get('site_url')
            if not site_url:
                continue
            
            logger.info(f"Scraping site {i}/{len(site_configs)}: {site_url}")
            
            # Ajouter le limit à la config
            config_with_limit = config.copy()
            config_with_limit.update({
                'limit': products_per_site,
                'export_format': export_format
            })
            
            site_result = cls.scrape_single_site(**config_with_limit)
            results[site_url] = site_result
            
            # Délai entre les sites pour être poli
            if i < len(site_configs):
                time.sleep(1)
        
        return results
    
    @classmethod
    def _scrape_sites_parallel(cls, site_configs: List[Dict[str, Any]], 
                              products_per_site: int,
                              max_workers: int,
                              export_format: Optional[str]) -> Dict[str, Dict[str, Any]]:
        """Scrape les sites en parallèle"""
        results = {}
        
        def scrape_site_wrapper(config):
            config_with_limit = config.copy()
            config_with_limit.update({
                'limit': products_per_site,
                'export_format': export_format
            })
            return config['site_url'], cls.scrape_single_site(**config_with_limit)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_config = {
                executor.submit(scrape_site_wrapper, config): config 
                for config in site_configs if config.get('site_url')
            }
            
            for future in concurrent.futures.as_completed(future_to_config):
                try:
                    site_url, result = future.result()
                    results[site_url] = result
                except Exception as e:
                    config = future_to_config[future]
                    site_url = config.get('site_url', 'unknown')
                    logger.error(f"Parallel scraping error for {site_url}: {e}")
                    results[site_url] = {
                        'success': False,
                        'error': str(e),
                        'products': [],
                        'product_count': 0
                    }
        
        return results
    
    # =====================================
    # 3 Export Functions
    # =====================================
    @classmethod
    def _export_products(cls, products: List[Dict[str, Any]], 
                        site_url: str,
                        format: str,
                        with_variants: bool = False,
                        agent: Optional[BaseA2AAgent] = None) -> Optional[str]:
        """Export des produits dans le format demandé"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        domain = urlparse(site_url).netloc.replace('www.', '')
        
        try:
            if format.lower() == 'csv':
                filename = f"{domain}_products_{timestamp}.csv"
                
                # Utiliser la méthode d'export de l'agent si disponible
                if agent and hasattr(agent, 'export_to_csv'):
                    return agent.export_to_csv(products, filename)
                else:
                    return cls._export_to_csv_generic(products, filename, with_variants)
                    
            elif format.lower() == 'json':
                filename = f"{domain}_products_{timestamp}.json"
                return cls._export_to_json(products, filename)
                
        except Exception as e:
            logger.error(f"Export error for {site_url}: {e}")
        
        return None
    
    @classmethod
    def _export_to_csv_generic(cls, products: List[Dict[str, Any]], 
                              filename: str,
                              with_variants: bool = False) -> str:
        """Export générique en CSV"""
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            if not products:
                return filename
                
            writer = csv.DictWriter(f, fieldnames=products[0].keys())
            writer.writeheader()
            writer.writerows(products)
        
        logger.info(f"Products exported to {filename}")
        return filename
    
    @classmethod
    def _export_to_json(cls, products: List[Dict[str, Any]], filename: str) -> str:
        """Export en JSON"""
        export_data = {
            'timestamp': datetime.now().isoformat(),
            'product_count': len(products),
            'products': products
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"Products exported to {filename}")
        return filename
    
    @classmethod
    def _create_combined_export(cls, results: Dict[str, Any], format: str) -> Optional[str]:
        """Crée un export combiné de tous les sites"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        try:
            if format.lower() == 'json':
                filename = f"combined_scraping_results_{timestamp}.json"
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False, default=str)
                
                logger.info(f"Combined results exported to {filename}")
                return filename
                
        except Exception as e:
            logger.error(f"Combined export error: {e}")
        
        return None
    
    # =====================================
    # 4 Utility Functions
    # =====================================
    @classmethod
    def get_supported_platforms(cls) -> List[str]:
        """Retourne la liste des plateformes supportées"""
        return list(cls.AVAILABLE_AGENTS.keys())
    
    @classmethod
    def quick_scrape(cls, site_url: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Méthode de scraping rapide pour tests et demos
        
        Args:
            site_url: URL du site
            limit: Nombre de produits (défaut: 20)
            
        Returns:
            Liste des produits normalisés
        """
        logger.info(f"Quick scrape: {site_url} (limit: {limit})")
        
        result = cls.scrape_single_site(
            site_url=site_url,
            limit=limit,
            platform_hint=None  # Auto-détection
        )
        
        if result['success']:
            logger.info(f"Quick scrape successful: {result['product_count']} products")
            return result['products']
        else:
            logger.warning(f"Quick scrape failed: {result.get('error', 'Unknown error')}")
            return []
    
    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valide une configuration de site
        
        Args:
            config: Configuration à valider
            
        Returns:
            Dictionnaire avec résultats de validation
        """
        validation = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'cleaned_config': config.copy()
        }
        
        # Vérifier l'URL
        if not config.get('site_url'):
            validation['valid'] = False
            validation['errors'].append("Missing required field: site_url")
        else:
            validation['cleaned_config']['site_url'] = cls._clean_url(config['site_url'])
        
        # Vérifier platform_hint
        platform_hint = config.get('platform_hint')
        if platform_hint and platform_hint.lower() not in cls.AVAILABLE_AGENTS:
            validation['warnings'].append(f"Unknown platform hint: {platform_hint}")
        
        # Vérifier les paramètres numériques
        if 'limit' in config:
            try:
                limit = int(config['limit'])
                if limit <= 0:
                    validation['warnings'].append("Limit should be positive")
                elif limit > 1000:
                    validation['warnings'].append("Large limit may cause long execution times")
            except ValueError:
                validation['errors'].append("Limit must be a number")
                validation['valid'] = False
        
        return validation
    
    @classmethod
    def get_factory_stats(cls) -> Dict[str, Any]:
        """Retourne les statistiques de la factory"""
        return {
            'supported_platforms': cls.get_supported_platforms(),
            'available_agents': list(cls.AVAILABLE_AGENTS.keys()),
            'default_configs': cls.DEFAULT_CONFIGS,
            'version': '2.0.0',
            'features': [
                'Auto-detection',
                'Proven strategies integration',
                'Parallel scraping',
                'Multiple export formats',
                'Performance monitoring',
                'Comprehensive error handling'
            ]
        }


def create_agent(url: str) -> BaseA2AAgent:
    """
    Create an appropriate scraping agent based on the URL.
    
    Args:
        url (str): The URL of the store to scrape
        
    Returns:
        BaseA2AAgent: An instance of the appropriate scraping agent
        
    Raises:
        ValueError: If the URL is not supported
    """
    try:
        # Parse the URL
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        # Determine the appropriate agent based on the domain
        if 'myshopify.com' in domain or 'shopify.com' in domain:
            return ShopifyAgent(url)
        elif 'woocommerce' in domain or 'wordpress' in domain:
            return WooCommerceAgent(url)
        else:
            # Try to detect the platform
            if 'myshopify.com' in domain:
                return ShopifyAgent(url)
            elif 'woocommerce' in domain:
                return WooCommerceAgent(url)
            else:
                raise ValueError(f"Unsupported store URL: {url}")
                
    except Exception as e:
        logger.error(f"Error creating agent for URL {url}: {str(e)}")
        raise

def scrape_store(url: str, enable_surveillance: bool = False) -> Dict[str, Any]:
    """
    Scrape a store and save the results to the database.
    
    Args:
        url (str): The URL of the store to scrape
        enable_surveillance (bool): Whether to enable surveillance for this store
        
    Returns:
        Dict[str, Any]: A dictionary containing the scraping results
    """
    start_time = datetime.utcnow()
    db = SessionLocal()
    
    try:
        # Create or get store
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        store_name = domain.split('.')[0].capitalize()
        store = get_or_create_store(db, name=store_name, url=url, domain=domain)
        
        # Create agent and scrape
        agent = create_agent(url)
        products = agent.scrape()
        
        # Create scraping log
        scraping_log = ScrapingLog(
            store_id=store.id,
            product_count=len(products),
            status='success',
            duration_seconds=(datetime.utcnow() - start_time).total_seconds()
        )
        db.add(scraping_log)
        db.flush()
        
        # Save products
        for product_data in products:
            add_or_update_product(db, store.id, product_data, scraping_log.id)
        
        # Update store
        store.updated_at = datetime.utcnow()
        if enable_surveillance:
            store.active_surveillance = True
        
        db.commit()
        
        return {
            'success': True,
            'message': f'Successfully scraped {len(products)} products from {store_name}',
            'products_count': len(products)
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error scraping store {url}: {str(e)}")
        
        # Log the error
        if 'store' in locals():
            error_log = ScrapingLog(
                store_id=store.id,
                product_count=0,
                status='failed',
                error_message=str(e),
                duration_seconds=(datetime.utcnow() - start_time).total_seconds()
            )
            db.add(error_log)
            db.commit()
        
        return {
            'success': False,
            'message': f'Error scraping store: {str(e)}',
            'products_count': 0
        }
        
    finally:
        db.close()

if __name__ == "__main__":
    # Test the factory
    test_urls = [
        "https://store.myshopify.com",
        "https://woocommerce.com",
        "https://invalid-store.com"
    ]
    
    for url in test_urls:
        try:
            agent = create_agent(url)
            print(f"Successfully created agent for {url}")
        except Exception as e:
            print(f"Error creating agent for {url}: {str(e)}")
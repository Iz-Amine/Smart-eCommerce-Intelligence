from typing import Any, Dict, List
from datetime import datetime
from mcp.mcp_base import MCPServer, MCPRequest
from agents.ShopifyAgent import ShopifyAgent

class ScrapingServer(MCPServer):
    """MCP Server simple pour les opérations de scraping."""
    
    def __init__(self, name: str, host: Any):
        # Permissions complètes pour tous les clients
        permissions = {
            "dashboard": ["scrape_store", "batch_scrape", "get_status"],
            "admin": ["scrape_store", "batch_scrape", "get_status"],
            "llm_enricher": ["scrape_store", "batch_scrape", "get_status"],
            "scheduler": ["scrape_store", "batch_scrape", "get_status"]
        }
        super().__init__(name, host, permissions)
        
        # Historique simple
        self.scraping_history = []
    
    def _process_request(self, request: MCPRequest) -> Any:
        """Process scraping requests."""
        
        self.logger.info(f"Scraping request: {request.action} from {request.source}")
        
        if request.action == "scrape_store":
            return self._scrape_store(request)
        elif request.action == "batch_scrape":
            return self._batch_scrape(request)
        elif request.action == "get_status":
            return self._get_status()
        else:
            raise ValueError(f"Action inconnue: {request.action}")
    
    def _scrape_store(self, request: MCPRequest) -> Dict[str, Any]:
        """Scraper un seul site avec ShopifyAgent."""
        url = request.parameters.get("url")
        limit = request.parameters.get("limit", 100)
        category = request.parameters.get("category")
        
        try:
            # Créer directement un ShopifyAgent
            agent = ShopifyAgent(site_url=url, category=category)
            
            # Vérifier si c'est un site Shopify
            if not agent.detect_platform():
                return {
                    "success": False,
                    "error": "Site is not a Shopify store",
                    "products_scraped": 0,
                    "platform": "not_shopify"
                }
            
            # Scraper les produits
            start_time = datetime.now()
            products = agent.scrape_products(limit=limit)
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Préparer le résultat
            result = {
                "success": len(products) > 0,
                "product_count": len(products),
                "execution_time_seconds": execution_time,
                "platform": "shopify",
                "products": products
            }
            
            # Log simple
            self._log_session(url, result, request.source)
            
            return {
                "success": result["success"],
                "products_scraped": result["product_count"],
                "execution_time": result["execution_time_seconds"],
                "platform": result.get("platform"),
                "products": products[:5]  # Retourner quelques produits pour preview
            }
            
        except Exception as e:
            self.logger.error(f"Erreur scraping {url}: {e}")
            return {
                "success": False,
                "error": str(e),
                "products_scraped": 0
            }
    
    def _batch_scrape(self, request: MCPRequest) -> Dict[str, Any]:
        """Scraper plusieurs sites avec ShopifyAgent."""
        site_configs = request.parameters.get("site_configs", [])
        products_per_site = request.parameters.get("products_per_site", 50)
        
        try:
            total_sites = len(site_configs)
            successful_sites = 0
            total_products = 0
            start_time = datetime.now()
            
            results = {}
            
            for config in site_configs:
                site_url = config.get("site_url")
                if not site_url:
                    continue
                
                try:
                    # Créer agent pour chaque site
                    agent = ShopifyAgent(
                        site_url=site_url,
                        category=config.get("category")
                    )
                    
                    if agent.detect_platform():
                        products = agent.scrape_products(limit=products_per_site)
                        if products:
                            successful_sites += 1
                            total_products += len(products)
                            results[site_url] = {
                                "success": True,
                                "products_count": len(products)
                            }
                        else:
                            results[site_url] = {
                                "success": False,
                                "error": "No products found"
                            }
                    else:
                        results[site_url] = {
                            "success": False,
                            "error": "Not a Shopify store"
                        }
                        
                except Exception as e:
                    results[site_url] = {
                        "success": False,
                        "error": str(e)
                    }
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Préparer le résultat batch
            result = {
                "total_sites": total_sites,
                "successful_sites": successful_sites,
                "total_products": total_products,
                "execution_time_seconds": execution_time,
                "sites": results
            }
            
            # Log batch
            self._log_batch_session(result, request.source)
            
            return {
                "success": True,
                "total_sites": result["total_sites"],
                "successful_sites": result["successful_sites"],
                "total_products": result["total_products"],
                "execution_time": result["execution_time_seconds"],
                "sites_results": results
            }
            
        except Exception as e:
            self.logger.error(f"Erreur batch scraping: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_status(self) -> Dict[str, Any]:
        """Statut simple du serveur."""
        return {
            "server_status": "active",
            "total_sessions": len(self.scraping_history),
            "last_scraping": self.scraping_history[-1] if self.scraping_history else None,
            "supported_platforms": ["shopify"],  # Seulement Shopify
            "agent_type": "ShopifyAgent"
        }
    
    def _log_session(self, url: str, result: Dict, source: str):
        """Log simple d'une session."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "url": url,
            "source": source,
            "success": result.get("success", False),
            "products_count": result.get("product_count", 0),
            "platform": result.get("platform", "shopify"),
            "agent_used": "ShopifyAgent"
        }
        
        self.scraping_history.append(log_entry)
        
        # Garder seulement les 100 derniers logs
        if len(self.scraping_history) > 100:
            self.scraping_history = self.scraping_history[-100:]
    
    def _log_batch_session(self, result: Dict, source: str):
        """Log simple d'une session batch."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "batch_scraping",
            "source": source,
            "total_sites": result.get("total_sites", 0),
            "successful_sites": result.get("successful_sites", 0),
            "total_products": result.get("total_products", 0),
            "agent_used": "ShopifyAgent"
        }
        
        self.scraping_history.append(log_entry)
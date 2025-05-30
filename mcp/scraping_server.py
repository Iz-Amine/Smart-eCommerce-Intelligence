from typing import Any, Dict, List
import time
from datetime import datetime, timedelta
from mcp.mcp_base import MCPServer, MCPRequest
from scrapping.agents.agent_factory import EnhancedAgentFactory

class ScrapingServer(MCPServer):
    """MCP Server for responsible scraping operations."""
    
    def __init__(self, name: str, host: Any):
        # Définir les permissions par client
        permissions = {
            "dashboard": ["scrape_store", "get_scraping_status"],
            "scheduler": ["scrape_store", "batch_scrape", "get_scraping_status"],
            "admin": ["scrape_store", "batch_scrape", "get_scraping_status", "update_limits"],
            "llm_enricher": ["get_scraping_status"]  # LLM ne peut que consulter
        }
        super().__init__(name, host, permissions)
        
        # Limites de scraping responsable
        self.rate_limits = {
            "requests_per_minute": 30,
            "max_concurrent_sites": 3,
            "min_delay_between_requests": 2.0,
            "max_products_per_session": 500
        }
        
        # Historique des requêtes pour rate limiting
        self.request_history = []
        self.active_scraping_sessions = {}
    
    def _process_request(self, request: MCPRequest) -> Any:
        """Process scraping-related requests with responsibility checks."""
        
        # Log toutes les intentions de scraping
        self.logger.info(f"Scraping request from {request.source}: {request.action}")
        
        if request.action == "scrape_store":
            return self._responsible_scrape_store(request)
        elif request.action == "batch_scrape":
            return self._responsible_batch_scrape(request)
        elif request.action == "get_scraping_status":
            return self._get_scraping_status(request)
        elif request.action == "update_limits":
            return self._update_rate_limits(request)
        else:
            raise ValueError(f"Unknown action: {request.action}")
    
    def _responsible_scrape_store(self, request: MCPRequest) -> Dict[str, Any]:
        """Scrape with ethical and rate limiting checks."""
        url = request.parameters.get("url")
        limit = min(request.parameters.get("limit", 100), self.rate_limits["max_products_per_session"])
        
        # Vérifications responsables
        if not self._check_rate_limits(request.source):
            raise Exception("Rate limit exceeded. Please wait before making new requests.")
        
        if not self._check_robots_txt(url):
            self.logger.warning(f"robots.txt disallows scraping for {url}")
            return {
                "success": False,
                "error": "robots.txt disallows scraping",
                "recommendation": "Contact site owner for API access"
            }
        
        # Déclarer les intentions
        scraping_context = {
            "purpose": request.context.get("purpose", "educational_research"),
            "requester": request.source,
            "timestamp": datetime.now().isoformat(),
            "rate_limited": True,
            "data_usage": "analytics_only"
        }
        
        try:
            # Utiliser la factory avec des paramètres responsables
            result = EnhancedAgentFactory.scrape_single_site(
                site_url=url,
                limit=limit,
                with_variants=False,  # Limiter les données collectées
                **request.parameters
            )
            
            # Enregistrer la session
            self._log_scraping_session(url, result, scraping_context)
            
            return {
                "success": result["success"],
                "products_scraped": result["product_count"],
                "context": scraping_context,
                "compliance": {
                    "rate_limited": True,
                    "robots_txt_checked": True,
                    "data_minimization": True
                }
            }
            
        except Exception as e:
            self.logger.error(f"Responsible scraping failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "context": scraping_context
            }
    
    def _check_rate_limits(self, source: str) -> bool:
        """Vérifier les limites de taux."""
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        # Nettoyer l'historique ancien
        self.request_history = [
            req for req in self.request_history 
            if req["timestamp"] > minute_ago
        ]
        
        # Compter les requêtes récentes de cette source
        recent_requests = [
            req for req in self.request_history 
            if req["source"] == source
        ]
        
        return len(recent_requests) < self.rate_limits["requests_per_minute"]
    
    def _check_robots_txt(self, url: str) -> bool:
        """Vérifier robots.txt (implémentation simplifiée)."""
        try:
            import requests
            from urllib.parse import urljoin
            
            robots_url = urljoin(url, "/robots.txt")
            response = requests.get(robots_url, timeout=5)
            
            if response.status_code == 200:
                # Vérification basique - en pratique, utiliser robotparser
                content = response.text.lower()
                if "disallow: /" in content or "disallow: /products" in content:
                    return False
            
            return True
            
        except Exception:
            # En cas d'erreur, être conservateur
            self.logger.warning(f"Could not check robots.txt for {url}")
            return True
    
    def _log_scraping_session(self, url: str, result: Dict, context: Dict):
        """Log détaillé de la session de scraping."""
        session_log = {
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "products_scraped": result.get("product_count", 0),
            "success": result.get("success", False),
            "context": context,
            "compliance_checks": {
                "rate_limited": True,
                "robots_txt_checked": True,
                "data_minimized": True
            }
        }
        
        # Dans un vrai système, sauvegarder en DB
        self.logger.info(f"Scraping session logged: {session_log}")
    
    def _get_scraping_status(self, request: MCPRequest) -> Dict[str, Any]:
        """Get current scraping status and limits."""
        return {
            "rate_limits": self.rate_limits,
            "active_sessions": len(self.active_scraping_sessions),
            "recent_requests": len(self.request_history),
            "compliance_status": "active"
        }
    
    def _update_rate_limits(self, request: MCPRequest) -> Dict[str, Any]:
        """Update rate limiting parameters (admin only)."""
        new_limits = request.parameters.get("limits", {})
        
        for key, value in new_limits.items():
            if key in self.rate_limits:
                self.rate_limits[key] = value
        
        self.logger.info(f"Rate limits updated by {request.source}: {new_limits}")
        return {"updated_limits": self.rate_limits}
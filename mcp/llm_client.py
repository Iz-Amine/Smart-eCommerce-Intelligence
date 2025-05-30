from typing import Any, Dict, List
import json
from datetime import datetime
from mcp.mcp_base import MCPClient, MCPRequest

class ResponsibleLLMClient(MCPClient):
    """Client LLM qui respecte les principes d'usage responsable."""
    
    def __init__(self, name: str, host: Any):
        super().__init__(name, host)
        self.usage_context = {
            "purpose": "educational_ecommerce_analysis",
            "data_retention": "session_only",
            "privacy_level": "anonymized"
        }
    
    def analyze_products_with_context(self, products: List[Dict], analysis_type: str) -> Dict[str, Any]:
        """Analyser des produits avec déclaration de contexte."""
        
        # Déclarer les intentions
        context = {
            **self.usage_context,
            "analysis_type": analysis_type,
            "product_count": len(products),
            "timestamp": datetime.now().isoformat(),
            "data_sources": self._identify_data_sources(products)
        }
        
        # Anonymiser les données sensibles
        anonymized_products = self._anonymize_product_data(products)
        
        # Faire la requête avec contexte
        response = self.make_request(
            action="llm_analysis",
            parameters={
                "products": anonymized_products,
                "analysis_type": analysis_type,
                "max_tokens": 1000  # Limiter la génération
            },
            context=context
        )
        
        if response.status == "error":
            raise Exception(f"LLM analysis failed: {response.error}")
        
        return {
            "analysis": response.data,
            "context": context,
            "compliance": {
                "data_anonymized": True,
                "purpose_declared": True,
                "retention_limited": True
            }
        }
    
    def generate_insights_summary(self, data: Dict) -> str:
        """Générer un résumé d'insights avec contrôle."""
        
        # Vérifier que les données ne contiennent pas d'infos sensibles
        if self._contains_sensitive_data(data):
            raise Exception("Cannot process sensitive data without explicit consent")
        
        context = {
            **self.usage_context,
            "task": "insight_generation",
            "data_type": "aggregated_metrics"
        }
        
        response = self.make_request(
            action="generate_text",
            parameters={
                "prompt": self._create_insight_prompt(data),
                "max_tokens": 500,
                "temperature": 0.7
            },
            context=context
        )
        
        if response.status == "error":
            raise Exception(f"Insight generation failed: {response.error}")
        
        return response.data.get("text", "")
    
    def _anonymize_product_data(self, products: List[Dict]) -> List[Dict]:
        """Anonymiser les données produit."""
        anonymized = []
        
        for product in products:
            # Garder seulement les données nécessaires pour l'analyse
            anon_product = {
                "price": product.get("price", 0),
                "available": product.get("available", True),
                "rating": product.get("rating", 0),
                "review_count": product.get("review_count", 0),
                "category": product.get("product_type", "unknown"),
                "has_image": product.get("has_image", False),
                "inventory_level": self._categorize_inventory(product.get("total_inventory", 0))
            }
            anonymized.append(anon_product)
        
        return anonymized
    
    def _categorize_inventory(self, inventory: int) -> str:
        """Catégoriser le niveau d'inventaire sans révéler les chiffres exacts."""
        if inventory == 0:
            return "out_of_stock"
        elif inventory < 10:
            return "low"
        elif inventory < 50:
            return "medium"
        else:
            return "high"
    
    def _identify_data_sources(self, products: List[Dict]) -> List[str]:
        """Identifier les sources de données."""
        sources = set()
        for product in products:
            if "store_name" in product:
                sources.add(product["store_name"])
        return list(sources)
    
    def _contains_sensitive_data(self, data: Dict) -> bool:
        """Vérifier la présence de données sensibles."""
        sensitive_fields = ["email", "phone", "address", "payment", "personal"]
        
        data_str = json.dumps(data).lower()
        return any(field in data_str for field in sensitive_fields)
    
    def _create_insight_prompt(self, data: Dict) -> str:
        """Créer un prompt d'analyse responsable."""
        return f"""
        Analyze the following e-commerce data for educational purposes:
        
        Data: {json.dumps(data, indent=2)}
        
        Please provide:
        1. Key trends and patterns
        2. Actionable business insights
        3. Recommendations for improvement
        
        Important: This analysis is for educational research only. 
        Do not include any personal or proprietary information.
        """
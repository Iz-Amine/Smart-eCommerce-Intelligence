from typing import List, Dict, Any
import os
from google import genai
from dotenv import load_dotenv
from pathlib import Path

# Charger les variables d'environnement
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Force reload of module
__version__ = '1.0.1'

class SimpleLLMEnricher:
    """LLM simple pour MVP - avec intégration Gemini"""
    
    def __init__(self):
        self._init_gemini()
    
    def _init_gemini(self):
        """Initialise le client Gemini avec la nouvelle structure"""
        try:
            # Charger la clé API depuis les variables d'environnement
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                print("⚠️ GEMINI_API_KEY non trouvée dans les variables d'environnement")
                print(f"📁 Recherche dans: {env_path}")
                print("🔑 Vérifiez que le fichier .env existe et contient GEMINI_API_KEY")
                self.client = None
                return
            
            # Initialiser le client Gemini avec la nouvelle structure
            self.client = genai.Client(api_key=api_key)
            self.model_name = 'gemini-2.0-flash'
            
            print(f"✅ Client Gemini initialisé avec succès (modèle: {self.model_name})")

        except Exception as e:
            print(f"❌ Erreur lors de l'initialisation de Gemini: {e}")
            self.client = None
    
    def enrich_product_data(self, product: Dict, store: Dict) -> Dict[str, Any]:
        """Enrichit les données du produit avec les insights LLM uniquement"""
        
        # DEBUG: Afficher les données reçues
        print("\n" + "="*50)
        print("🔍 DEBUG - Données reçues dans enrich_product_data:")
        print("="*50)
        print(f"📦 PRODUCT DATA:")
        for key, value in product.items():
            print(f"  {key}: {value} ({type(value).__name__})")
        
        print(f"\n🏪 STORE DATA:")
        for key, value in store.items():
            print(f"  {key}: {value} ({type(value).__name__})")
        print("="*50)
        
        enriched_data = {
            "product": {
                "title": product['title'],
                "price": float(product['price']),
                "max_price": float(product['max_price']) if product.get('max_price') else None,
                "available": bool(product['available']),
                "total_inventory": int(product['total_inventory']) if product.get('total_inventory') else 0,
                "product_type": product['product_type'],
                "vendor": product['vendor'],
                "description": product['description'],
                "variant_count": int(product.get('variant_count', 1)),
                "image_count": int(product.get('image_count', 0)),
                "tags": product.get('tags', []),
                "categories": product.get('categories', [])
            },
            "store": {
                "name": store['name'],
                "domain": store['domain'],
                "url": store['url']
            }
        }
        
        # DEBUG: Afficher les données structurées
        print("\n🔧 STRUCTURED DATA SENT TO LLM:")
        print(f"  Title: {enriched_data['product']['title']}")
        print(f"  Price: ${enriched_data['product']['price']}")
        print(f"  Available: {enriched_data['product']['available']}")
        print(f"  Total Inventory: {enriched_data['product']['total_inventory']}")
        print(f"  Variant Count: {enriched_data['product']['variant_count']}")
        print(f"  Image Count: {enriched_data['product']['image_count']}")
        print(f"  Vendor: {enriched_data['product']['vendor']}")
        print(f"  Product Type: {enriched_data['product']['product_type']}")
        
        # Ajouter les insights LLM
        enriched_data["llm_insights"] = self._generate_llm_insights(enriched_data)
        
        return enriched_data
    
    def _generate_llm_insights(self, enriched_data: Dict[str, Any]) -> str:
        """Génère des insights avec Gemini LLM"""
        if not self.client:
            return "LLM non disponible"
        
        try:
            # Préparer le prompt pour Gemini
            prompt = f"""
            Analyze this e-commerce product data and create a strategic action plan:
            
            Product: {enriched_data['product']['title']}
            Price: ${enriched_data['product']['price']}
            Category: {enriched_data['product']['product_type']}
            Vendor: {enriched_data['product']['vendor']}
            Available: {'Yes' if enriched_data['product']['available'] else 'No'}
            Variants: {enriched_data['product']['variant_count']}
            Images: {enriched_data['product']['image_count']}
            
            Note: Stock levels are not tracked - focus on available data points.
            
            Provide a strategic action plan covering:
            
            **MARKET POSITIONING:**
            - Price competitiveness analysis for this category
            - Brand positioning opportunities
            
            **PRODUCT OPTIMIZATION:**
            - Variant strategy effectiveness 
            - Image presentation quality assessment
            
            **BUSINESS OPPORTUNITIES:**
            - Revenue optimization tactics
            - Market expansion potential
            - Customer acquisition strategies
            
            **DATA UTILIZATION PLAN:**
            - How to leverage scraped product data
            - Competitive intelligence opportunities
            - Trend analysis possibilities
            
            Format as actionable bullet points. Max 300 words.
            """
            
            # DEBUG: Afficher le prompt envoyé
            print("\n📤 PROMPT SENT TO LLM:")
            print("-" * 40)
            print(prompt)
            print("-" * 40)
            
            # Générer la réponse avec Gemini
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            # DEBUG: Afficher la réponse reçue
            print("\n📥 RESPONSE FROM LLM:")
            print("-" * 40)
            print(response.text)
            print("-" * 40)
            print("="*50 + "\n")
            
            return response.text
        except Exception as e:
            error_msg = f"Erreur lors de la génération des insights: {e}"
            print(f"❌ {error_msg}")
            return error_msg
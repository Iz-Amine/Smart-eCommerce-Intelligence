import os
from dotenv import load_dotenv
from Analyse.LLMEnricher import SimpleLLMEnricher

def test_llm_enricher():
    """Test de l'intégration LLM avec un produit fictif"""
    print("🚀 Démarrage du test LLM Enricher...")
    
    # Charger les variables d'environnement
    load_dotenv()
    
    # Vérifier la clé API
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ Erreur: GEMINI_API_KEY non trouvée dans les variables d'environnement")
        return
    
    print("✅ Clé API trouvée")
    
    # Créer un produit fictif pour le test
    test_product = {
        'id': 1,
        'title': 'Smartphone XYZ Pro Max',
        'price': 999.99,
        'max_price': 1099.99,
        'available': True,
        'total_inventory': 50,
        'product_type': 'Electronics',
        'vendor': 'TechStore',
        'description': 'Le dernier smartphone avec IA intégrée',
        'variant_count': 3,
        'image_count': 5,
        'tags': ['smartphone', 'tech', 'ai'],
        'categories': ['Electronics', 'Mobile Phones'],
        'image_url': 'https://example.com/phone.jpg'
    }
    
    test_store = {
        'name': 'TechStore',
        'domain': 'techstore.com',
        'url': 'https://techstore.com'
    }
    
    try:
        # Initialiser l'enricher
        print("📝 Initialisation de LLM Enricher...")
        enricher = SimpleLLMEnricher()
        
        # Enrichir les données
        print("🔄 Enrichissement des données...")
        enriched_data = enricher.enrich_product_data(test_product, test_store)
        
        # Générer les insights
        print("🤖 Génération des insights...")
        insights = enricher.generate_product_insights(enriched_data)
        
        # Afficher les résultats
        print("\n📊 Résultats du test:")
        print("\n1. Résumé du produit:")
        print(insights['summary'])
        
        print("\n2. Recommandations LLM:")
        print(insights['recommendations'])
        
        print("\n3. Données brutes:")
        print("Scores:", enriched_data['analysis']['scores'])
        print("Métriques:", enriched_data['analysis']['metrics'])
        
        print("\n✅ Test terminé avec succès!")
        
    except Exception as e:
        print(f"❌ Erreur lors du test: {str(e)}")

if __name__ == "__main__":
    test_llm_enricher() 
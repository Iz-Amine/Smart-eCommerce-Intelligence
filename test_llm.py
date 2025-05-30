from Analyse.LLMEnricher import SimpleLLMEnricher

def test_llm():
    print("Testing LLM Enricher...")
    try:
        enricher = SimpleLLMEnricher()
        print("Successfully created SimpleLLMEnricher instance")
        
        # Test enrich_product_data
        test_product = {
            'id': 1,
            'title': 'Test Product',
            'price': 99.99,
            'max_price': 129.99,
            'available': True,
            'total_inventory': 10,
            'product_type': 'Test',
            'vendor': 'Test Vendor',
            'description': 'Test Description',
            'variant_count': 1,
            'image_count': 1,
            'tags': ['test'],
            'categories': ['test'],
            'image_url': 'http://test.com/image.jpg'
        }
        
        test_store = {
            'id': 1,
            'name': 'Test Store',
            'url': 'http://test.com',
            'domain': 'test.com'
        }
        
        enriched_data = enricher.enrich_product_data(test_product, test_store)
        print("Successfully enriched product data")
        print("Enriched data:", enriched_data)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    test_llm() 
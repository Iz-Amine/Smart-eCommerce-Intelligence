import streamlit as st
import pandas as pd
from Analyse.simple_analyzer import SimpleTopKAnalyzer
from Analyse.LLMEnricher import SimpleLLMEnricher
from utils import load_data

def add_mvp_analysis_tab():
    """Ajoute l'onglet d'analyse MVP au dashboard"""
    st.title("🎯 Analyse Top-K Produits (MVP)")
    
    # Charger les données
    _, products_df, _ = load_data()
    
    if products_df.empty:
        st.warning("Aucun produit trouvé. Scrapez d'abord des données.")
        return
    
    # Configuration
    col1, col2 = st.columns(2)
    with col1:
        k_value = st.slider("Nombre de top produits", 5, 50, 20)
    with col2:
        min_price = st.number_input("Prix minimum", 0.0, 1000.0, 0.0)
    
    # Filtrer les données
    filtered_df = products_df[products_df['price'] >= min_price]
    
    if filtered_df.empty:
        st.error("Aucun produit correspond aux filtres.")
        return
    
    # Analyse
    analyzer = SimpleTopKAnalyzer()
    llm_enricher = SimpleLLMEnricher()
    
    with st.spinner("Analyse en cours..."):
        results = analyzer.get_top_k(filtered_df, k_value)
        insights = llm_enricher.generate_simple_insights(
            results['top_products'], 
            results['stats']
        )
    
    # Affichage des résultats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Produits analysés", results['stats']['total_analyzed'])
    with col2:
        st.metric("Score moyen Top-K", f"{results['stats']['avg_score']:.1f}")
    with col3:
        st.metric("Prix moyen Top-K", f"{results['stats']['avg_price']:.2f}€")
    
    # Insights LLM
    st.subheader("💡 Insights Automatiques")
    st.markdown(insights)
    
    # Top produits
    st.subheader(f"🏆 Top {k_value} Produits")
    
    for i, product in enumerate(results['top_products'][:10], 1):
        with st.expander(f"#{i} - {product['title'][:50]}... (Score: {product['final_score']:.1f})"):
            col1, col2 = st.columns([1, 2])
            
            with col1:
                if product.get('image_url'):
                    st.image(product['image_url'], width=150)
            
            with col2:
                summary = llm_enricher.create_product_summary(product)
                st.markdown(summary)
                
                if st.button(f"Voir détails", key=f"detail_{product['id']}"):
                    st.session_state['selected_product'] = product['id']
                    st.rerun() 
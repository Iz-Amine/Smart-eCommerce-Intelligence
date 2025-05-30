"""MVP Top-K Analysis Package - Version simplifiée"""

import pandas as pd
from typing import List, Dict, Any, Optional

class SimpleTopKAnalyzer:
    """Analyseur simple pour MVP - identifie les Top-K produits"""
    
    def __init__(self):
        pass
    
    def get_top_k(self, products_df: pd.DataFrame, k: int = 20, 
                  min_price: float = 0.0, category: Optional[str] = None) -> Dict[str, Any]:
        """Retourne les Top-K produits basé sur des critères simples"""
        if products_df.empty:
            return {'top_products': [], 'stats': {}, 'error': 'Aucun produit à analyser'}
        
        # Filtres
        filtered_df = products_df.copy()
        
        if min_price > 0:
            filtered_df = filtered_df[filtered_df['price'] >= min_price]
        
        if category and category != 'Toutes':
            filtered_df = filtered_df[filtered_df['product_type'] == category]
        
        if filtered_df.empty:
            return {'top_products': [], 'stats': {}, 'error': 'Aucun produit après filtrage'}
        
        try:
            # Tri simple : disponibles d'abord, puis par prix croissant
            filtered_df['available'] = filtered_df['available'].fillna(True)
            sorted_df = filtered_df.sort_values(['available', 'price'], ascending=[False, True])
            
            # Top-K produits
            top_k = sorted_df.head(k)
            
            # Stats basiques
            stats = {
                'total_analyzed': len(filtered_df),
                'top_k_count': len(top_k),
                'avg_price': round(top_k['price'].mean(), 2),
                'availability_rate': round((top_k['available'].sum() / len(top_k)) * 100, 1),
                'top_categories': top_k['product_type'].value_counts().head(3).to_dict(),
                'price_range': {
                    'min': float(top_k['price'].min()),
                    'max': float(top_k['price'].max())
                }
            }
            
            return {
                'top_products': top_k.to_dict('records'),
                'stats': stats,
                'success': True
            }
            
        except Exception as e:
            return {
                'top_products': [],
                'stats': {},
                'error': f'Erreur d\'analyse: {str(e)}'
            }

# Exporter les classes pour l'utilisation
__all__ = ['SimpleTopKAnalyzer']
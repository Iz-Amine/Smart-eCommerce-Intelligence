from sqlalchemy.orm import Session
from DB.models import TopKAnalysis, TopKProduct, Product
from DB.db import SessionLocal
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class TopKDBManager:
    """Gestionnaire de base de données pour les analyses Top-K"""
    
    def save_analysis(self, analysis_data: Dict[str, Any], 
                     analysis_name: str, 
                     k_value: int,
                     min_price: float = 0.0,
                     category_filter: Optional[str] = None,
                     store_id: Optional[int] = None) -> Optional[int]:
        """Sauvegarde une analyse Top-K en base"""
        db = SessionLocal()
        
        try:
            # Créer l'analyse principale
            analysis = TopKAnalysis(
                store_id=store_id,
                analysis_name=analysis_name,
                k_value=k_value,
                min_price=min_price,
                category_filter=category_filter,
                total_analyzed=analysis_data['stats'].get('total_analyzed', 0),
                avg_score=analysis_data['stats'].get('avg_score', 0.0),
                avg_price=analysis_data['stats'].get('avg_price', 0.0),
                availability_rate=analysis_data['stats'].get('availability_rate', 0.0)
            )
            
            db.add(analysis)
            db.flush()  # Pour obtenir l'ID
            
            # Sauvegarder chaque produit Top-K
            for rank, product_data in enumerate(analysis_data['top_products'], 1):
                topk_product = TopKProduct(
                    analysis_id=analysis.id,
                    product_id=product_data['id'],
                    final_score=product_data.get('final_score', 0.0),
                    rank_position=rank,
                    price_score=product_data.get('price_score', 0.0),
                    inventory_score=product_data.get('inventory_score', 0.0),
                    availability_score=product_data.get('availability_score', 0.0),
                    image_score=product_data.get('image_score', 0.0)
                )
                db.add(topk_product)
            
            db.commit()
            logger.info(f"Analyse '{analysis_name}' sauvegardée avec ID {analysis.id}")
            return analysis.id
            
        except Exception as e:
            db.rollback()
            logger.error(f"Erreur sauvegarde analyse: {e}")
            return None
        finally:
            db.close()
    
    def get_saved_analyses(self, limit: int = 10) -> List[Dict]:
        """Récupère les analyses sauvegardées"""
        db = SessionLocal()
        
        try:
            analyses = db.query(TopKAnalysis)\
                        .order_by(TopKAnalysis.created_at.desc())\
                        .limit(limit)\
                        .all()
            
            result = []
            for analysis in analyses:
                result.append({
                    'id': analysis.id,
                    'name': analysis.analysis_name,
                    'k_value': analysis.k_value,
                    'total_analyzed': analysis.total_analyzed,
                    'avg_score': analysis.avg_score,
                    'created_at': analysis.created_at,
                    'store_id': analysis.store_id
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur récupération analyses: {e}")
            return []
        finally:
            db.close()
    
    def load_analysis(self, analysis_id: int) -> Optional[Dict]:
        """Charge une analyse complète"""
        db = SessionLocal()
        
        try:
            analysis = db.query(TopKAnalysis).filter(TopKAnalysis.id == analysis_id).first()
            if not analysis:
                return None
            
            # Récupérer les produits Top-K avec leurs détails
            topk_products = db.query(TopKProduct, Product)\
                             .join(Product, TopKProduct.product_id == Product.id)\
                             .filter(TopKProduct.analysis_id == analysis_id)\
                             .order_by(TopKProduct.rank_position)\
                             .all()
            
            products_data = []
            for topk, product in topk_products:
                products_data.append({
                    'id': product.id,
                    'title': product.title,
                    'price': product.price,
                    'vendor': product.vendor,
                    'product_type': product.product_type,
                    'final_score': topk.final_score,
                    'rank_position': topk.rank_position,
                    'image_url': product.image_url,
                    'available': product.available
                })
            
            return {
                'analysis': {
                    'id': analysis.id,
                    'name': analysis.analysis_name,
                    'k_value': analysis.k_value,
                    'created_at': analysis.created_at,
                    'total_analyzed': analysis.total_analyzed,
                    'avg_score': analysis.avg_score,
                    'avg_price': analysis.avg_price
                },
                'products': products_data
            }
            
        except Exception as e:
            logger.error(f"Erreur chargement analyse {analysis_id}: {e}")
            return None
        finally:
            db.close()
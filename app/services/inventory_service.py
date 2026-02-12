import pandas as pd
import numpy as np
import os
import uuid
from datetime import datetime
from flask import session
from app.utils.constants import *

# Almacenamiento en memoria (simulado)
# Estructura: session_id -> { 'inventory_data': df, 'analysis_cache': df, 'metadata': {...} }
SESSIONS = {}

class InventoryService:
    @staticmethod
    def get_user_session():
        """Obtiene o crea el ID de sesión del usuario y retorna sus datos."""
        if 'user_id' not in session:
            session['user_id'] = str(uuid.uuid4())
        
        user_id = session['user_id']
        if user_id not in SESSIONS:
            SESSIONS[user_id] = {
                'inventory_data': None,
                'analysis_cache': None,
                'metadata': {
                    'store_name': 'Sin datos',
                    'upload_date': '-'
                }
            }
        return SESSIONS[user_id]

    @staticmethod
    def load_default_inventory():
        """Carga el archivo de inventario por defecto."""
        user_data = InventoryService.get_user_session()
        
        if user_data['inventory_data'] is not None:
            return True

        default_file = 'inventario.xlsx'
        # Buscar en raíz o directorios superiores si es necesario, 
        # pero por ahora asumimos que está en el CWD donde se corre run.py
        if os.path.exists(default_file):
            try:
                inventory_data = pd.read_excel(default_file, skiprows=1)
                inventory_data.columns = inventory_data.columns.str.strip()
                
                user_data['inventory_data'] = inventory_data
                user_data['analysis_cache'] = None
                user_data['metadata'] = {
                    'store_name': 'Inventario General',
                    'upload_date': datetime.now().strftime("%d/%m/%Y %H:%M")
                }
                return True
            except Exception as e:
                print(f"Error cargando inventario por defecto: {e}")
                return False
        return False

    @staticmethod
    def get_analysis():
        """Genera el análisis completo del inventario (Lazy Loading)."""
        user_data = InventoryService.get_user_session()
        
        # Intentar cargar default si está vacío
        if user_data['inventory_data'] is None:
            InventoryService.load_default_inventory()
            if user_data['inventory_data'] is None:
                return None
                
        if user_data['analysis_cache'] is not None:
            return user_data['analysis_cache']
        
        df = user_data['inventory_data'].copy()
        
        # Helpers seguros para columnas
        def get_col(idx):
             return pd.to_numeric(df.iloc[:, idx], errors='coerce').fillna(0)

        df['_stock'] = get_col(IDX_STOCK)
        df['_cost_u'] = get_col(IDX_COST_U)
        df['_cost_t'] = get_col(IDX_COST_T)
        df['_price'] = get_col(IDX_PRICE)
        
        df['stock_status'] = df['_stock'].apply(InventoryService._classify_stock_status)
        df = InventoryService._apply_abc_classification(df)
        
        df['margin'] = df['_price'] - df['_cost_u']
        df['margin_pct'] = np.where(df['_price'] > 0, (df['margin'] / df['_price'] * 100), 0)
        
        user_data['analysis_cache'] = df
        return df

    @staticmethod
    def _classify_stock_status(stock):
        if stock < 0: return 'negative'
        if stock == 0: return 'out_of_stock'
        if stock <= 5: return 'critical'
        if stock <= 20: return 'low'
        if stock <= 100: return 'optimal'
        return 'overstock'

    @staticmethod
    def _apply_abc_classification(df):
        df_sorted = df.sort_values('_cost_t', ascending=False)
        total_value = df_sorted['_cost_t'].sum()
        df_sorted['cumulative_value'] = df_sorted['_cost_t'].cumsum()
        df_sorted['cumulative_pct'] = (df_sorted['cumulative_value'] / total_value * 100) if total_value > 0 else 0
        
        df_sorted['abc_class'] = df_sorted['cumulative_pct'].apply(
            lambda pct: 'A' if pct <= 80 else ('B' if pct <= 95 else 'C')
        )
        # Retornamos el df original con la columna añadida correctamente mapeada por índice
        df['abc_class'] = df_sorted['abc_class']
        return df

    @staticmethod
    def product_to_dict(row, include_price=False):
        """Convierte una fila de DataFrame a diccionario serializable."""
        created_at = ''
        if 'F. Creación' in row.index and pd.notna(row['F. Creación']):
            try:
                created_at = pd.to_datetime(row['F. Creación']).strftime('%d/%m/%Y')
            except:
                created_at = str(row['F. Creación'])[:10]
        
        result = {
            'id': int(row[COL_ID]) if pd.notna(row[COL_ID]) else 0,
            'sku': str(row.get(COL_SKU, '')),
            'product': str(row.get(COL_PRODUCT, '')),
            'category': str(row.get(COL_CATEGORY, '')),
            'brand': str(row.get(COL_BRAND, '')),
            'stock': int(row['_stock']),
            'value': round(float(row['_cost_t']), 2),
            'status': row['stock_status'],
            'abc_class': row.get('abc_class', 'C'),
            'created_at': created_at
        }
        if include_price:
            result['price'] = round(float(row['_price']), 2) if pd.notna(row['_price']) else 0
        return result

    @staticmethod
    def process_app_upload(file, filename):
        """Procesa la subida de un archivo."""
        import tempfile
        import gc
        
        store_name = os.path.splitext(filename)[0]
        
        # Usar directorio temporal del sistema
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            file.save(tmp_file.name)
            tmp_path = tmp_file.name
        
        gc.collect()
        
        df = None
        # Intentar leer con varios skiprows
        for skiprows in [1, 0, 2]:
            try:
                df = pd.read_excel(tmp_path, skiprows=skiprows, engine='openpyxl')
                df.columns = df.columns.astype(str).str.strip()
                if len(df.columns) >= 10 and len(df) > 0:
                    break
                df = None
            except Exception:
                continue
        
        try:
            os.unlink(tmp_path)
        except:
            pass
            
        if df is None:
            return None, "No se pudo parsear el archivo Excel."
            
        user_data = InventoryService.get_user_session()
        user_data['inventory_data'] = df
        user_data['analysis_cache'] = None
        user_data['metadata'] = {
            'store_name': store_name,
            'upload_date': datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        
        gc.collect()
        return len(df), df.columns.tolist()[:10]

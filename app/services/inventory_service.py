import pandas as pd
import numpy as np
import os
import uuid
import threading
from datetime import datetime
from flask import session
from app.utils.constants import *

# Almacenamiento en memoria (simulado)
# Estructura: session_id -> { 'inventory_data': df, 'analysis_cache': df, 'metadata': {...} }
SESSIONS = {}
_analysis_lock = threading.Lock()

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
        """Genera el análisis completo del inventario (Lazy Loading, thread-safe)."""
        user_data = InventoryService.get_user_session()

        # Intentar cargar default si está vacío
        if user_data['inventory_data'] is None:
            InventoryService.load_default_inventory()
            if user_data['inventory_data'] is None:
                return None

        if user_data['analysis_cache'] is not None:
            return user_data['analysis_cache']

        with _analysis_lock:
            # Double-check después de adquirir el lock
            if user_data['analysis_cache'] is not None:
                return user_data['analysis_cache']

            df = user_data['inventory_data'].copy()

            # Helpers seguros para columnas
            def get_col(idx):
                 s = pd.to_numeric(df.iloc[:, idx], errors='coerce').fillna(0)
                 return s.replace([np.inf, -np.inf], 0)

            # Sanitizar columnas de Texto
            # Asumimos que las constantes de índices (IDX_...) coinciden con posición
            # Pero en process_app_upload ya se asignaron nombres de columnas si se usó header
            # Mejor usar los nombres de columnas definidos en constants si existen en df
            
            if COL_BRAND in df.columns:
                df[COL_BRAND] = df[COL_BRAND].fillna('SIN MARCA').astype(str).replace(['nan', 'NaN', ''], 'SIN MARCA')
            
            if COL_CATEGORY in df.columns:
                df[COL_CATEGORY] = df[COL_CATEGORY].fillna('SIN CATEGORÍA').astype(str).replace(['nan', 'NaN', ''], 'SIN CATEGORÍA')

            if COL_PRODUCT in df.columns:
                 df[COL_PRODUCT] = df[COL_PRODUCT].fillna('').astype(str).replace(['nan', 'NaN'], '')

            if COL_SKU in df.columns:
                 df[COL_SKU] = df[COL_SKU].fillna('').astype(str).replace(['nan', 'NaN'], '')

            df['_stock'] = get_col(IDX_STOCK)
            df['_cost_u'] = get_col(IDX_COST_U)
            df['_cost_t'] = get_col(IDX_COST_T)
            df['_price'] = get_col(IDX_PRICE)

            df['stock_status'] = df['_stock'].apply(InventoryService._classify_stock_status)
            df = InventoryService._apply_abc_classification(df)

            df['margin'] = df['_price'] - df['_cost_u']
            # Evitar división por cero y NaNs
            df['margin_pct'] = np.where(df['_price'] > 0, (df['margin'] / df['_price'] * 100), 0)
            df['margin_pct'] = df['margin_pct'].replace([np.inf, -np.inf, np.nan], 0)

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
        
        def safe_str(val, default=''):
            s = str(val)
            if s.lower() in ['nan', 'none', 'nat', '']:
                return default
            return s

        result = {
            'id': int(row[COL_ID]) if COL_ID in row and pd.notna(row[COL_ID]) else 0,
            'sku': safe_str(row.get(COL_SKU)),
            'product': safe_str(row.get(COL_PRODUCT)),
            'category': safe_str(row.get(COL_CATEGORY), 'SIN CATEGORÍA'),
            'brand': safe_str(row.get(COL_BRAND), 'SIN MARCA'),
            'stock': int(row['_stock']) if pd.notna(row['_stock']) else 0,
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
        """Procesa la subida de un archivo Excel directamente desde memoria."""
        from io import BytesIO
        import gc
        
        store_name = os.path.splitext(filename)[0]
        ext = os.path.splitext(filename)[1].lower()
        
        # Leer archivo directamente a memoria (evita problemas con /tmp en Render)
        try:
            file_bytes = BytesIO(file.read())
        except Exception as e:
            print(f"Error leyendo archivo en memoria: {e}")
            return None, f"Error leyendo el archivo: {str(e)}"
        
        gc.collect()
        
        # Determinar engine según extensión
        engine = 'openpyxl' if ext in ('.xlsx', '') else 'xlrd'
        
        df = None
        errors = []
        
        for skiprows in [1, 0, 2]:
            try:
                file_bytes.seek(0)
                df = pd.read_excel(file_bytes, skiprows=skiprows, engine=engine)
                df.columns = df.columns.astype(str).str.strip()
                
                if len(df.columns) >= 10 and len(df) > 0:
                    print(f"Upload OK: skiprows={skiprows}, {len(df)} filas, {len(df.columns)} cols")
                    print(f"Columnas detectadas: {df.columns.tolist()}")
                    break
                    
                errors.append(f"skiprows={skiprows}: solo {len(df.columns)} columnas o {len(df)} filas")
                df = None
            except Exception as e:
                errors.append(f"skiprows={skiprows}: {type(e).__name__}: {e}")
                print(f"Upload parse intento fallido: skiprows={skiprows}: {e}")
                df = None
                continue
        
        # Si openpyxl falló, intentar con xlrd por si es .xls disfrazado de .xlsx
        if df is None and engine == 'openpyxl':
            try:
                file_bytes.seek(0)
                df = pd.read_excel(file_bytes, skiprows=1, engine='xlrd')
                df.columns = df.columns.astype(str).str.strip()
                if len(df.columns) >= 10 and len(df) > 0:
                    print(f"Upload OK con xlrd fallback: {len(df)} filas, {len(df.columns)} cols")
                else:
                    df = None
            except Exception as e:
                errors.append(f"xlrd fallback: {type(e).__name__}: {e}")
            
        if df is None:
            error_detail = "; ".join(errors) if errors else "Archivo vacío o formato no reconocido"
            print(f"Upload falló completamente: {error_detail}")
            return None, f"No se pudo parsear el archivo Excel. Detalle: {error_detail}"
            
        user_data = InventoryService.get_user_session()
        user_data['inventory_data'] = df
        user_data['analysis_cache'] = None
        user_data['metadata'] = {
            'store_name': store_name,
            'upload_date': datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        
        gc.collect()
        return len(df), df.columns.tolist()[:10]

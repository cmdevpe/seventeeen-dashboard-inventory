from flask import Blueprint, jsonify, request, session
from app.services.inventory_service import InventoryService
from app.utils.constants import *
from datetime import datetime
import pandas as pd
import numpy as np

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.errorhandler(Exception)
def handle_api_error(e):
    """Captura excepciones no manejadas en endpoints de API."""
    print(f"API Error: {type(e).__name__}: {e}")
    return jsonify({'error': f'Error interno: {str(e)}'}), 500

def check_data_loaded():
    """Helper para verificar datos."""
    if 'user_id' not in session:
        print(f"DEBUG: No user_id in session for request {request.path}")
    else:
        print(f"DEBUG: Session user_id: {session['user_id']} for request {request.path}")

    user_data = InventoryService.get_user_session()
    
    if user_data['inventory_data'] is None:
        print(f"DEBUG: inventory_data is None for user {session.get('user_id')}")
        InventoryService.load_default_inventory()
        if user_data['inventory_data'] is None:
            print("DEBUG: Still None after load_default_inventory")
            return jsonify({'error': 'No data loaded'}), 400
    else:
        print(f"DEBUG: Data found for user {session.get('user_id')}")
        
    return None

@api_bp.route('/metadata')
def get_metadata():
    user_data = InventoryService.get_user_session()
    return jsonify(user_data['metadata'])

@api_bp.route('/health')
def health_check():
    user_data = InventoryService.get_user_session()
    inventory_data = user_data['inventory_data']
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'session_id': session.get('user_id'),
        'data_loaded': inventory_data is not None,
        'total_products': len(inventory_data) if inventory_data is not None else 0
    })

@api_bp.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Obtener tamaño aproximado
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    file_size_mb = round(file_size / (1024 * 1024), 2)
    
    try:
        rows, cols_or_error = InventoryService.process_app_upload(file, file.filename)

        if rows is None:
             return jsonify({'error': cols_or_error}), 400

        # Pre-computar análisis para evitar race condition en peticiones paralelas
        try:
            InventoryService.get_analysis()
        except Exception as e:
            print(f"Warning: pre-analysis failed: {e}")

        return jsonify({
            'success': True,
            'message': f'Cargados {rows:,} productos ({file_size_mb} MB)',
            'columns': cols_or_error,
            'total_rows': rows,
            'file_size_mb': file_size_mb
        })
        
    except MemoryError:
        return jsonify({'error': 'Archivo demasiado grande.'}), 507
    except Exception as e:
        return jsonify({'error': f'Error procesando archivo: {str(e)}'}), 500

@api_bp.route('/kpis')
def get_kpis():
    error = check_data_loaded()
    if error: return error
    
    df = InventoryService.get_analysis()
    
    total_skus = len(df)
    active_skus = len(df[df['_stock'] > 0])
    total_stock = int(df['_stock'].sum())
    total_value = float(df['_cost_t'].sum())
    
    out_of_stock = len(df[df['_stock'] == 0])
    negative_stock = len(df[df['_stock'] < 0])
    critical_stock = len(df[df['_stock'].between(1, 5)])
    low_stock = len(df[df['_stock'].between(6, 20)])
    overstock = len(df[df['_stock'] > 100])
    
    df_negative = df[df['_stock'] < 0]
    
    avg_margin_raw = df[df['margin_pct'] > 0]['margin_pct'].mean() if 'margin_pct' in df.columns else 0
    avg_margin = float(avg_margin_raw) if pd.notna(avg_margin_raw) else 0
    
    return jsonify({
        'total_skus': total_skus,
        'active_skus': active_skus,
        'inactive_skus': total_skus - active_skus,
        'total_stock': total_stock,
        'total_value': round(total_value, 2),
        'avg_stock': round(total_stock / total_skus, 2) if total_skus > 0 else 0,
        'avg_margin_pct': round(avg_margin, 2),
        'diferencias_count': len(df_negative),
        'diferencias_units': int(df_negative['_stock'].sum()),
        'diferencias_value': float(df_negative['_cost_t'].sum()),
        'alerts': {
            'out_of_stock': out_of_stock,
            'negative_stock': negative_stock,
            'critical': critical_stock,
            'low': low_stock,
            'overstock': overstock,
            'total_alerts': out_of_stock + negative_stock + critical_stock
        }
    })

@api_bp.route('/stock-status')
def get_stock_status():
    error = check_data_loaded()
    if error: return error
    df = InventoryService.get_analysis()
    if df is None: return jsonify({'error': 'No data loaded'}), 400
    
    status_counts = df['stock_status'].value_counts().to_dict()
    
    status_map = {
        'negative': {'label': 'Stock Negativo', 'color': '#dc2626', 'icon': '🔴'},
        'out_of_stock': {'label': 'Sin Stock', 'color': '#f97316', 'icon': '🟠'},
        'critical': {'label': 'Crítico (1-5)', 'color': '#eab308', 'icon': '🟡'},
        'low': {'label': 'Bajo (6-20)', 'color': '#84cc16', 'icon': '🟢'},
        'optimal': {'label': 'Óptimo (21-100)', 'color': '#22c55e', 'icon': '🟢'},
        'overstock': {'label': 'Exceso (>100)', 'color': '#3b82f6', 'icon': '🔵'}
    }
    
    result = []
    for status, count in status_counts.items():
        info = status_map.get(status, {'label': status, 'color': '#6b7280', 'icon': '⚫'})
        result.append({
            'status': status,
            'label': info['label'],
            'count': int(count),
            'percentage': round(count / len(df) * 100, 1),
            'color': info['color'],
            'icon': info['icon']
        })
    
    order = ['negative', 'out_of_stock', 'critical', 'low', 'optimal', 'overstock']
    result.sort(key=lambda x: order.index(x['status']) if x['status'] in order else 99)
    
    return jsonify(result)

@api_bp.route('/search')
def search_products():
    error = check_data_loaded()
    if error: return error
    
    query = request.args.get('q', '').lower()
    status = request.args.get('status', '')
    category = request.args.get('category', '')
    brand = request.args.get('brand', '')
    sort = request.args.get('sort', '')
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    
    df = InventoryService.get_analysis()
    
    # Filtrado (usando Pandas vectorizado para performance)
    mask = pd.Series([True] * len(df))
    
    if query:
        mask &= (
            df[COL_PRODUCT].astype(str).str.lower().str.contains(query, na=False, regex=False) |
            df[COL_SKU].astype(str).str.lower().str.contains(query, na=False, regex=False) |
            df[COL_CATEGORY].astype(str).str.lower().str.contains(query, na=False, regex=False) |
            df[COL_BRAND].astype(str).str.lower().str.contains(query, na=False, regex=False)
        )
    
    if status:
        mask &= (df['stock_status'] == status)
    
    if category:
        mask &= (df[COL_CATEGORY].astype(str).str.lower() == category.lower())
        
    if brand:
        if brand == 'SIN_MARCA':
             mask &= (df[COL_BRAND].isna() | (df[COL_BRAND].astype(str).str.strip() == '') | (df[COL_BRAND].astype(str).str.lower() == 'nan'))
        else:
             mask &= (df[COL_BRAND].astype(str).str.lower() == brand.lower())

    filtered = df[mask]
    
    # Ordenamiento
    if sort:
        sort_parts = [s.strip() for s in sort.split(',') if s.strip()]
        sort_columns = []
        sort_ascending = []
        added_fecha_dt = False
        
        for s in sort_parts:
            if s in ('date_desc', 'date_asc') and 'F. Creación' in filtered.columns:
                if not added_fecha_dt:
                    filtered = filtered.copy()
                    filtered['_fecha_dt'] = pd.to_datetime(filtered['F. Creación'], dayfirst=True, errors='coerce')
                    added_fecha_dt = True
                sort_columns.append('_fecha_dt')
                sort_ascending.append(s == 'date_asc')
            elif s in ('stock_desc', 'stock_asc'):
                sort_columns.append('_stock')
                sort_ascending.append(s == 'stock_asc')
            elif s in ('value_desc', 'value_asc'):
                sort_columns.append('_cost_t')
                sort_ascending.append(s == 'value_asc')
        
        if sort_columns:
            if not added_fecha_dt:
                filtered = filtered.copy() # Evitar SettingWithCopyWarning
            filtered = filtered.sort_values(sort_columns, ascending=sort_ascending, na_position='last')
            if added_fecha_dt:
                filtered = filtered.drop(columns=['_fecha_dt'])
    
    # Paginación
    total = len(filtered)
    offset = (page - 1) * limit
    paginated_df = filtered.iloc[offset:offset + limit]
    
    results = [InventoryService.product_to_dict(row, include_price=True) for _, row in paginated_df.iterrows()]
    
    return jsonify({
        'results': results,
        'total': total,
        'showing': len(results),
        'page': page,
        'pages': (total + limit - 1) // limit
    })

# Copiar el resto de endpoints (categories, brands, top-products, etc.)
# ... Para brevedad, implementaremos los más importantes y los faltantes se pueden añadir igual
# (En una implementación real migraríamos TODOS uno por uno)

@api_bp.route('/categories')
def get_categories():
    df = InventoryService.get_analysis()
    if df is None: return jsonify({'error': 'No data loaded'}), 400
    
    if COL_CATEGORY not in df.columns: return jsonify({'error': 'Category column not found'}), 400
    
    cat_analysis = df.groupby(COL_CATEGORY).agg({
        'ID': 'count', '_stock': 'sum', '_cost_t': 'sum'
    }).reset_index()
    
    cat_analysis.columns = ['category', 'products', 'stock', 'value']
    cat_analysis = cat_analysis.sort_values('value', ascending=False)
    total_value = cat_analysis['value'].sum()
    
    result = []
    for _, row in cat_analysis.head(15).iterrows():
        result.append({
            'category': row['category'] if pd.notna(row['category']) else 'Sin Categoría',
            'products': int(row['products']),
            'stock': int(row['stock']),
            'value': round(float(row['value']), 2),
            'value_pct': round(row['value'] / total_value * 100, 1) if total_value > 0 else 0
        })
    return jsonify(result)

@api_bp.route('/brands')
def get_brands():
    df = InventoryService.get_analysis()
    if df is None: return jsonify({'error': 'No data loaded'}), 400
    
    brand_analysis = df.groupby(COL_BRAND).agg({
        'ID': 'count', '_stock': 'sum', '_cost_t': 'sum'
    }).reset_index()
    
    brand_analysis.columns = ['brand', 'products', 'stock', 'value']
    brand_analysis = brand_analysis.sort_values('value', ascending=False)
    total_value = brand_analysis['value'].sum()
    
    result = []
    for _, row in brand_analysis.head(15).iterrows():
        result.append({
            'brand': row['brand'],
            'products': int(row['products']),
            'stock': int(row['stock']),
            'value': round(float(row['value']), 2),
            'value_pct': round(row['value'] / total_value * 100, 1) if total_value > 0 else 0
        })
    return jsonify(result)

@api_bp.route('/unique-brands')
def get_unique_brands():
    df = InventoryService.get_analysis()
    if df is None: return jsonify({'error': 'No data loaded'}), 400
    
    category = request.args.get('category')
    if category:
        df = df[df[COL_CATEGORY].astype(str).str.lower() == category.lower()]
        
    unique_brands = df[COL_BRAND].unique()
    cleaned_brands = sorted([str(b).strip() for b in unique_brands if pd.notna(b) and str(b).strip() != '' and str(b).lower() != 'nan'])
    
    mask_no_brand = df[COL_BRAND].isna() | (df[COL_BRAND].astype(str).str.strip() == '') | (df[COL_BRAND].astype(str).str.lower() == 'nan')
    if mask_no_brand.any():
        cleaned_brands.append('SIN_MARCA')
        
    return jsonify(cleaned_brands)

@api_bp.route('/suppliers')
def get_suppliers():
    df = InventoryService.get_analysis()
    if df is None: return jsonify({'error': 'No data loaded'}), 400
    
    if COL_SUPPLIER not in df.columns: return jsonify({'error': 'Supplier column not found'}), 400
    
    supplier_analysis = df.groupby(COL_SUPPLIER).agg({
        'ID': 'count', '_stock': 'sum', '_cost_t': 'sum'
    }).reset_index()
    
    supplier_analysis.columns = ['supplier', 'products', 'stock', 'value']
    supplier_analysis = supplier_analysis.sort_values('value', ascending=False)
    total_value = supplier_analysis['value'].sum()
    
    result = []
    for _, row in supplier_analysis.head(15).iterrows():
        if pd.notna(row['supplier']) and row['supplier'] != '':
             result.append({
                'supplier': row['supplier'],
                'products': int(row['products']),
                'stock': int(row['stock']),
                'value': round(float(row['value']), 2),
                'value_pct': round(row['value'] / total_value * 100, 1) if total_value > 0 else 0
            })
    return jsonify(result)

@api_bp.route('/alerts')
def get_alerts():
    df = InventoryService.get_analysis()
    if df is None: return jsonify({'error': 'No data loaded'}), 400
    
    alerts_df = df[df['stock_status'].isin(['negative', 'out_of_stock', 'critical'])].copy()
    alerts_df = alerts_df.sort_values('_cost_t', ascending=False).head(100)
    
    result = []
    for _, row in alerts_df.iterrows():
        result.append(InventoryService.product_to_dict(row, include_price=True))
    return jsonify(result)

@api_bp.route('/top-products')
def get_top_products():
    df = InventoryService.get_analysis()
    if df is None: return jsonify({'error': 'No data loaded'}), 400
    
    top_df = df[df['_stock'] > 0].sort_values('_cost_t', ascending=False).head(20)
    result = [InventoryService.product_to_dict(row) for _, row in top_df.iterrows()]
    return jsonify(result)

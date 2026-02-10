"""
📦 Dashboard de Análisis de Inventario - Backend Flask
IMPORTACIONES SEVENTEEN PERÚ
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import pandas as pd
import numpy as np
import os
from datetime import datetime

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Configuración para archivos grandes (250MB máximo)
app.config['MAX_CONTENT_LENGTH'] = 250 * 1024 * 1024  # 250MB
app.config['UPLOAD_FOLDER'] = '/tmp'  # Usar directorio temporal

# ==================== CONSTANTS (DRY) ====================
# Índices de columna Excel (O=14, P=15, Q=16, R=17)
IDX_STOCK = 14   # Columna O - Stock
IDX_COST_U = 15  # Columna P - Costo Unitario
IDX_COST_T = 16  # Columna Q - Costo Total
IDX_PRICE = 17   # Columna R - Precio

# Columnas fijas por nombre (no cambian)
COL_CATEGORY = 'Categoría'
COL_BRAND = 'Marca'
COL_PRODUCT = 'Producto'
COL_SKU = 'SKU'
COL_ID = 'ID'

# Estado global
inventory_data = None
analysis_cache = None

def load_default_inventory():
    """Carga el archivo de inventario por defecto"""
    global inventory_data, analysis_cache
    default_file = 'inventario.xlsx'
    if os.path.exists(default_file):
        try:
            inventory_data = pd.read_excel(default_file, skiprows=1)
            # Limpiar nombres de columnas
            inventory_data.columns = inventory_data.columns.str.strip()
            
            # Mostrar columnas detectadas por posición
            cols = inventory_data.columns.tolist()
            print(f"📊 Columnas por posición:")
            print(f"   O (idx {IDX_STOCK}): '{cols[IDX_STOCK]}'")
            print(f"   P (idx {IDX_COST_U}): '{cols[IDX_COST_U]}'")
            print(f"   Q (idx {IDX_COST_T}): '{cols[IDX_COST_T]}'")
            print(f"   R (idx {IDX_PRICE}): '{cols[IDX_PRICE]}'")
            
            analysis_cache = None
            print(f"✅ Cargado inventario: {len(inventory_data)} productos")
            return True
        except Exception as e:
            print(f"❌ Error cargando inventario: {e}")
            return False
    return False

# Funciones helper para acceder a columnas por índice
def get_stock(df):
    """Obtiene la columna Stock (O)"""
    return pd.to_numeric(df.iloc[:, IDX_STOCK], errors='coerce').fillna(0)

def get_cost_u(df):
    """Obtiene la columna Costo Unitario (P)"""
    return pd.to_numeric(df.iloc[:, IDX_COST_U], errors='coerce').fillna(0)

def get_cost_t(df):
    """Obtiene la columna Costo Total (Q)"""
    return pd.to_numeric(df.iloc[:, IDX_COST_T], errors='coerce').fillna(0)

def get_price(df):
    """Obtiene la columna Precio (R)"""
    return pd.to_numeric(df.iloc[:, IDX_PRICE], errors='coerce').fillna(0)

def get_analysis():
    """Genera el análisis completo del inventario (Single Responsibility)"""
    global analysis_cache
    
    if inventory_data is None:
        return None
    
    if analysis_cache is not None:
        return analysis_cache
    
    df = inventory_data.copy()
    
    # Agregar columnas calculadas usando índices (O, P, Q, R)
    df['_stock'] = get_stock(df)
    df['_cost_u'] = get_cost_u(df)
    df['_cost_t'] = get_cost_t(df)
    df['_price'] = get_price(df)
    
    # Clasificación de stock
    df['stock_status'] = df['_stock'].apply(classify_stock_status)
    
    # Análisis ABC
    df = apply_abc_classification(df)
    
    # Margen bruto
    df['margin'] = df['_price'] - df['_cost_u']
    df['margin_pct'] = np.where(df['_price'] > 0, (df['margin'] / df['_price'] * 100), 0)
    
    analysis_cache = df
    return df

# ==================== HELPERS (DRY) ====================

def classify_stock_status(stock):
    """Clasifica el estado del stock (Single Responsibility)"""
    if stock < 0:
        return 'negative'
    elif stock == 0:
        return 'out_of_stock'
    elif stock <= 5:
        return 'critical'
    elif stock <= 20:
        return 'low'
    elif stock <= 100:
        return 'optimal'
    return 'overstock'

def apply_abc_classification(df):
    """Aplica clasificación ABC al DataFrame (Single Responsibility)"""
    df_sorted = df.sort_values('_cost_t', ascending=False)
    total_value = df_sorted['_cost_t'].sum()
    df_sorted['cumulative_value'] = df_sorted['_cost_t'].cumsum()
    df_sorted['cumulative_pct'] = (df_sorted['cumulative_value'] / total_value * 100) if total_value > 0 else 0
    
    df_sorted['abc_class'] = df_sorted['cumulative_pct'].apply(
        lambda pct: 'A' if pct <= 80 else ('B' if pct <= 95 else 'C')
    )
    df['abc_class'] = df_sorted['abc_class']
    return df

def product_to_dict(row, include_price=False):
    """Convierte una fila de producto a diccionario (DRY)"""
    # Formatear fecha si existe
    created_at = ''
    if 'F. Creación' in row.index and pd.notna(row['F. Creación']):
        try:
            created_at = pd.to_datetime(row['F. Creación']).strftime('%d/%m/%Y')
        except:
            created_at = str(row['F. Creación'])[:10]
    
    result = {
        'id': int(row[COL_ID]) if pd.notna(row[COL_ID]) else 0,
        'sku': str(row.get(COL_SKU, '')),
        'product': str(row.get(COL_PRODUCT, ''))[:50],
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

def check_data_loaded():
    """Verifica si hay datos cargados"""
    if inventory_data is None:
        return jsonify({'error': 'No data loaded'}), 400
    return None

# ==================== ENDPOINTS ====================

@app.route('/')
def serve_index():
    """Sirve el dashboard HTML"""
    return send_from_directory('.', 'index.html')

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'data_loaded': inventory_data is not None,
        'total_products': len(inventory_data) if inventory_data is not None else 0
    })

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Sube y procesa un archivo Excel (soporta archivos grandes hasta 250MB)"""
    global inventory_data, analysis_cache
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    global inventory_data, analysis_cache
    
    # Obtener tamaño del archivo
    file.seek(0, 2)  # Ir al final
    file_size = file.tell()
    file.seek(0)  # Volver al inicio
    file_size_mb = round(file_size / (1024 * 1024), 2)
    
    try:
        import tempfile
        import gc
        
        # Guardar archivo temporalmente para procesamiento eficiente
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            file.save(tmp_file.name)
            tmp_path = tmp_file.name
        
        # Liberar memoria antes de procesar
        gc.collect()
        
        # Intentar diferentes configuraciones de lectura
        df = None
        for skiprows in [1, 0, 2]:  # Priorizar skiprows=1 como el archivo por defecto
            try:
                df = pd.read_excel(tmp_path, skiprows=skiprows, engine='openpyxl')
                df.columns = df.columns.astype(str).str.strip()
                
                # Verificar que tiene al menos 10 columnas (mínimo para el formato esperado)
                if len(df.columns) >= 10 and len(df) > 0:
                    print(f"✅ Archivo parseado con skiprows={skiprows}, {len(df)} filas, {len(df.columns)} columnas")
                    break
                df = None
            except Exception as e:
                print(f"Intento con skiprows={skiprows} falló: {e}")
                continue
        
        # Limpiar archivo temporal
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        if df is None:
            return jsonify({'error': 'No se pudo parsear el archivo Excel. Verifica el formato.'}), 400
        
        # Procesar DataFrame
        inventory_data = df
        analysis_cache = None
        
        # Liberar memoria
        gc.collect()
        
        return jsonify({
            'success': True,
            'message': f'Cargados {len(inventory_data):,} productos ({file_size_mb} MB)',
            'columns': inventory_data.columns.tolist()[:10],  # Solo primeras 10 columnas
            'total_rows': len(inventory_data),
            'file_size_mb': file_size_mb
        })
        
    except MemoryError:
        return jsonify({
            'error': 'Archivo demasiado grande para la memoria disponible. Intenta con un archivo más pequeño o actualiza el plan de Render.'
        }), 507
    except Exception as e:
        print(f"Error procesando archivo: {e}")
        return jsonify({'error': f'Error procesando archivo: {str(e)}'}), 500

@app.route('/api/kpis')
def get_kpis():
    """Retorna los KPIs principales del inventario"""
    error = check_data_loaded()
    if error: return error
    
    df = get_analysis()
    
    total_skus = len(df)
    active_skus = len(df[df['_stock'] > 0])
    total_stock = int(df['_stock'].sum())
    total_value = float(df['_cost_t'].sum())
    
    # Alertas
    out_of_stock = len(df[df['_stock'] == 0])
    negative_stock = len(df[df['_stock'] < 0])
    critical_stock = len(df[df['_stock'].between(1, 5)])
    low_stock = len(df[df['_stock'].between(6, 20)])
    overstock = len(df[df['_stock'] > 100])
    
    # Diferencias (stock negativo)
    df_negative = df[df['_stock'] < 0]
    diferencias_count = len(df_negative)  # Cantidad de SKUs
    diferencias_units = int(df_negative['_stock'].sum())  # Total de unidades negativas
    diferencias_value = float(df_negative['_cost_t'].sum())  # Valor total
    
    avg_margin = float(df[df['margin_pct'] > 0]['margin_pct'].mean()) if 'margin_pct' in df.columns else 0
    
    return jsonify({
        'total_skus': total_skus,
        'active_skus': active_skus,
        'inactive_skus': total_skus - active_skus,
        'total_stock': total_stock,
        'total_value': round(total_value, 2),
        'avg_stock': round(total_stock / total_skus, 2) if total_skus > 0 else 0,
        'avg_margin_pct': round(avg_margin, 2),
        'diferencias_count': diferencias_count,
        'diferencias_units': diferencias_units,
        'diferencias_value': round(diferencias_value, 2),
        'alerts': {
            'out_of_stock': out_of_stock,
            'negative_stock': negative_stock,
            'critical': critical_stock,
            'low': low_stock,
            'overstock': overstock,
            'total_alerts': out_of_stock + negative_stock + critical_stock
        }
    })

@app.route('/api/stock-status')
def get_stock_status():
    """Retorna la distribución de productos por estado de stock"""
    if inventory_data is None:
        return jsonify({'error': 'No data loaded'}), 400
    
    df = get_analysis()
    
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
    
    # Ordenar por criticidad
    order = ['negative', 'out_of_stock', 'critical', 'low', 'optimal', 'overstock']
    result.sort(key=lambda x: order.index(x['status']) if x['status'] in order else 99)
    
    return jsonify(result)

@app.route('/api/abc-analysis')
def get_abc_analysis():
    """Retorna el análisis ABC del inventario"""
    if inventory_data is None:
        return jsonify({'error': 'No data loaded'}), 400
    
    df = get_analysis()
    abc_summary = df.groupby('abc_class').agg({
        'ID': 'count',
        '_cost_t': 'sum'
    }).reset_index()
    
    abc_summary.columns = ['class', 'count', 'value']
    total_value = abc_summary['value'].sum()
    total_count = abc_summary['count'].sum()
    
    result = []
    for _, row in abc_summary.iterrows():
        result.append({
            'class': row['class'],
            'count': int(row['count']),
            'value': round(float(row['value']), 2),
            'count_pct': round(row['count'] / total_count * 100, 1),
            'value_pct': round(row['value'] / total_value * 100, 1) if total_value > 0 else 0
        })
    
    # Ordenar A, B, C
    result.sort(key=lambda x: x['class'])
    
    return jsonify({
        'summary': result,
        'total_value': round(total_value, 2),
        'total_products': int(total_count)
    })

@app.route('/api/categories')
def get_categories():
    """Retorna el análisis por categoría"""
    if inventory_data is None:
        return jsonify({'error': 'No data loaded'}), 400
    
    df = get_analysis()
    
    if COL_CATEGORY not in df.columns:
        return jsonify({'error': 'Category column not found'}), 400
    
    cat_analysis = df.groupby(COL_CATEGORY).agg({
        'ID': 'count',
        '_stock': 'sum',
        '_cost_t': 'sum'
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

@app.route('/api/brands')
def get_brands():
    """Retorna el análisis por marca"""
    if inventory_data is None:
        return jsonify({'error': 'No data loaded'}), 400
    
    df = get_analysis()
    
    if COL_BRAND not in df.columns:
        return jsonify({'error': 'Brand column not found'}), 400
    
    brand_analysis = df.groupby(COL_BRAND).agg({
        'ID': 'count',
        '_stock': 'sum',
        '_cost_t': 'sum'
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

@app.route('/api/suppliers')
def get_suppliers():
    """Retorna el análisis por proveedor"""
    if inventory_data is None:
        return jsonify({'error': 'No data loaded'}), 400
    
    df = get_analysis()
    
    # Columna de proveedor
    COL_SUPPLIER = 'Proveedor'
    if COL_SUPPLIER not in df.columns:
        return jsonify({'error': 'Supplier column not found'}), 400
    
    supplier_analysis = df.groupby(COL_SUPPLIER).agg({
        'ID': 'count',
        '_stock': 'sum',
        '_cost_t': 'sum'
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

@app.route('/api/alerts')
def get_alerts():
    """Retorna los productos en estado de alerta"""
    if inventory_data is None:
        return jsonify({'error': 'No data loaded'}), 400
    
    df = get_analysis()
    
    # Filtrar productos en alerta
    alerts_df = df[df['stock_status'].isin(['negative', 'out_of_stock', 'critical'])].copy()
    alerts_df = alerts_df.sort_values('_cost_t', ascending=False).head(100)
    
    status_priority = {'negative': 0, 'out_of_stock': 1, 'critical': 2}
    alerts_df['priority'] = alerts_df['stock_status'].map(status_priority)
    alerts_df = alerts_df.sort_values('priority')
    
    result = []
    for _, row in alerts_df.iterrows():
        result.append({
            'id': int(row['ID']) if pd.notna(row['ID']) else 0,
            'sku': str(row.get('SKU', '')),
            'product': str(row.get('Producto', ''))[:50],
            'category': str(row.get('Categoría', '')),
            'brand': str(row.get('Marca', '')),
            'stock': int(row['_stock']),
            'value': round(float(row['_cost_t']), 2),
            'price': round(float(row['_price']), 2) if pd.notna(row['_price']) else 0,
            'status': row['stock_status'],
            'abc_class': row.get('abc_class', 'C')
        })
    
    return jsonify(result)

@app.route('/api/top-products')
def get_top_products():
    """Retorna los productos con mayor valor de inventario"""
    if inventory_data is None:
        return jsonify({'error': 'No data loaded'}), 400
    
    df = get_analysis()
    
    top_df = df[df['_stock'] > 0].sort_values('_cost_t', ascending=False).head(20)
    
    result = []
    for _, row in top_df.iterrows():
        result.append({
            'id': int(row['ID']) if pd.notna(row['ID']) else 0,
            'sku': str(row.get('SKU', '')),
            'product': str(row.get('Producto', ''))[:40],
            'category': str(row.get('Categoría', '')),
            'stock': int(row['_stock']),
            'value': round(float(row['_cost_t']), 2),
            'abc_class': row.get('abc_class', 'C')
        })
    
    return jsonify(result)

@app.route('/api/analysis')
def get_full_analysis():
    """Retorna el análisis completo"""
    if inventory_data is None:
        return jsonify({'error': 'No data loaded'}), 400
    
    return jsonify({
        'kpis': get_kpis().get_json(),
        'stock_status': get_stock_status().get_json(),
        'abc': get_abc_analysis().get_json(),
        'categories': get_categories().get_json(),
        'brands': get_brands().get_json()
    })

@app.route('/api/search')
def search_products():
    """Busca productos con paginación"""
    error = check_data_loaded()
    if error: return error
    
    # Parámetros
    query = request.args.get('q', '').lower()
    status = request.args.get('status', '')
    category = request.args.get('category', '')
    sort = request.args.get('sort', '')
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    
    df = get_analysis()
    
    # Aplicar filtros (DRY - construcción incremental de máscara)
    mask = pd.Series([True] * len(df))
    
    if query:
        mask &= (
            df[COL_PRODUCT].astype(str).str.lower().str.contains(query, na=False) |
            df[COL_SKU].astype(str).str.lower().str.contains(query, na=False) |
            df[COL_CATEGORY].astype(str).str.lower().str.contains(query, na=False) |
            df[COL_BRAND].astype(str).str.lower().str.contains(query, na=False)
        )
    
    if status:
        mask &= (df['stock_status'] == status)
    
    if category:
        mask &= (df[COL_CATEGORY].astype(str).str.lower() == category.lower())
    
    filtered = df[mask]
    
    # Aplicar ordenamiento
    if sort in ('date_desc', 'date_asc') and 'F. Creación' in filtered.columns:
        filtered = filtered.copy()
        filtered['_fecha_dt'] = pd.to_datetime(filtered['F. Creación'], errors='coerce')
        filtered = filtered.sort_values('_fecha_dt', ascending=(sort == 'date_asc'), na_position='last')
        filtered = filtered.drop(columns=['_fecha_dt'])
    elif sort == 'stock_desc':
        filtered = filtered.sort_values('_stock', ascending=False)
    elif sort == 'stock_asc':
        filtered = filtered.sort_values('_stock', ascending=True)
    elif sort == 'value_desc':
        filtered = filtered.sort_values('_cost_t', ascending=False)
    elif sort == 'value_asc':
        filtered = filtered.sort_values('_cost_t', ascending=True)
    
    # Paginación
    total = len(filtered)
    offset = (page - 1) * limit
    paginated_df = filtered.iloc[offset:offset + limit]
    
    # Usar helper DRY para convertir a dict
    results = [product_to_dict(row, include_price=True) for _, row in paginated_df.iterrows()]
    
    return jsonify({
        'results': results,
        'total': total,
        'showing': len(results),
        'page': page,
        'pages': (total + limit - 1) // limit
    })

# Ya no se carga inventario al iniciar - el usuario debe subir su archivo

# Ejecutar
if __name__ == '__main__':
    print("🚀 Servidor iniciando en http://localhost:5000")
    app.run(debug=True, port=5000)

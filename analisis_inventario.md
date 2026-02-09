# 📦 Análisis de Inventario - IMPORTACIONES SEVENTEEN PERÚ

## Resumen Ejecutivo

| Métrica             | Valor              |
| ------------------- | ------------------ |
| 📦 Total SKUs       | 10,651             |
| 📊 Stock Total      | 1,198,548 unidades |
| 💰 Valor Inventario | S/ 6,171,993.71    |
| 🔴 Sin Stock        | 9,594 (90%)        |
| ⚠️ Stock Negativo   | 4 productos        |
| 📈 Stock Promedio   | 112.53 unidades    |
| 📉 Stock Mínimo     | -4                 |
| 📈 Stock Máximo     | 999,709            |

---

## Estructura de Datos

### Columnas Detectadas (18)

| #   | Campo                   | Tipo    |
| --- | ----------------------- | ------- |
| 0   | ID                      | Entero  |
| 1   | F. Creación             | Fecha   |
| 2   | SKU                     | Texto   |
| 3   | Código de barras        | Texto   |
| 4   | Tipo                    | Texto   |
| 5   | Categoría               | Texto   |
| 6   | Producto                | Texto   |
| 7   | Descripción             | Vacío   |
| 8   | Proveedor               | Texto   |
| 9   | Modelo                  | Texto   |
| 10  | Marca                   | Texto   |
| 11  | Afectación              | Texto   |
| 12  | Unid. Medida            | Texto   |
| 13  | Último precio de compra | Decimal |
| 14  | Stock ALMACEN           | Entero  |
| 15  | Costo U. ALMACEN        | Decimal |
| 16  | Costo T. ALMACEN        | Decimal |
| 17  | Precio U. ALMACEN       | Decimal |

---

## Alertas Críticas

> [!CAUTION]
> **4 productos con stock negativo** - Requiere revisión inmediata de registros

> [!WARNING]
> **9,594 productos sin stock (90%)** - Alto porcentaje de productos agotados

---

## Categorías Detectadas

- ACCESORIO
- MENAJE
- HOGAR
- JUGUETE
- CUIDADO PERSONAL
- Otras...

## Marcas Detectadas

- DEXE
- GF HOGAR
- NANCY
- SAMANTHA
- BALERIA VIDRIOS
- SUNTON
- Otras...

---

## Dimensiones Disponibles para Análisis

| Dimensión               | Campo                           | Disponible       |
| ----------------------- | ------------------------------- | ---------------- |
| **Productos**           | SKU, Código de barras, Producto | ✅               |
| **Categorías**          | Categoría                       | ✅               |
| **Marcas**              | Marca                           | ✅               |
| **Proveedores**         | Proveedor                       | ✅               |
| **Stock**               | Stock ALMACEN                   | ✅               |
| **Valoración**          | Costo U., Costo T., Precio U.   | ✅               |
| **Ubicaciones**         | -                               | ❌ No disponible |
| **Stock Mínimo/Máximo** | -                               | ❌ No disponible |
| **Movimientos**         | -                               | ❌ No disponible |

---

## Análisis Posibles

### ✅ Disponibles

- Clasificación ABC por valor de inventario
- Distribución de stock por categoría
- Top marcas por valor/cantidad
- Productos sin stock (alerta de compra)
- Stock negativo (corrección de datos)
- Margen bruto por producto (Precio - Costo)
- Análisis por proveedor

### ❌ No Disponibles (datos faltantes)

- Rotación de inventario (requiere histórico de ventas)
- Días de inventario (requiere ventas promedio)
- Punto de reorden (no hay stock mínimo definido)
- Inventario muerto por tiempo (requiere última venta)

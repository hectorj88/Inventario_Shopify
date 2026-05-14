import streamlit as st
import sheet  # Importamos tu lógica del archivo anterior
import pandas as pd
import time
from datetime import datetime
import pytz

#pip freeze > requirements.txt
#streamlit run main.py
# Definir la zona horaria de Colombia
bogota_tz = pytz.timezone('America/Bogota')

# Configuración de la página
st.set_page_config(page_title="Control de Inventario Redi Food", layout="wide")

st.title("📊 Estado del Inventario")
st.markdown("Visualización en tiempo real de existencias desde Redi Food.")

# --- BARRA LATERAL: FILTROS ---
st.sidebar.header("Filtros de Búsqueda")

# Cargamos los datos crudos inicialmente
data = sheet.get_inventory_data("Inventario")

def resetear_formulario():
    for i in range(5):
        # Al eliminar la llave, el widget vuelve a su valor por defecto ('---' o 0)
        if f"prod_{i}" in st.session_state:
            del st.session_state[f"prod_{i}"]
        if f"num_{i}" in st.session_state:
            del st.session_state[f"num_{i}"]

# Creamos las dos pestañas
tab_visualizacion, tab_actualizacion = st.tabs(["👁️ Visualización de Stock", "📝 Actualizar Inventario"])

# --- PESTAÑA 1: VISUALIZACIÓN ---
with tab_visualizacion:
    st.markdown("### Estado en tiempo real")

    if not data.empty:
        #################################################################
        # Filtros
        #################################################################
        # Nuevo filtro: Excluir negativos
        exclude_neg = st.sidebar.checkbox("Excluir stock negativo", value=False)

        # Extraemos valores únicos para las listas desplegables, eliminando nulos
        list_skus = sorted(data['sku'].astype(str).unique())
        list_titles = sorted(data['product_title'].dropna().unique())
        list_variants = sorted(data['variant_title'].dropna().unique())

        # Sustituimos text_input por multiselect
        search_product = st.sidebar.multiselect("Seleccionar Productos", options=list_titles)
        search_sku = st.sidebar.multiselect("Seleccionar SKUs", options=list_skus)
        search_variant = st.sidebar.multiselect("Seleccionar Gramajes", options=list_variants)

        # Filtro de Rango Numérico (se mantiene igual)
        min_val = int(data['inventory_quantity'].min())
        max_val = int(data['inventory_quantity'].max())
        
        qty_range = st.sidebar.slider(
            "Rango de Cantidad",
            min_value=min_val,
            max_value=max_val,
            value=(min_val, max_val)
        )

        # Llamamos a la función de filtrado incluyendo el nuevo parámetro
        filtered_data = sheet.filter_data(
            data, 
            search_sku, 
            search_product, 
            search_variant, 
            qty_range,
            exclude_negative=exclude_neg # Pasamos el valor del checkbox
        )

        #################################################################
        # CUERPO PRINCIPAL: VISUALIZACIÓN
        #################################################################

        # Obtenemos los segmentos para las tablas
        low, medium, high = sheet.get_status_segments(filtered_data)

        # Columnas para métricas rápidas
        m1, m2, m3 = st.columns(3)
        m1.metric("Agotándose (<50)", len(low), delta_color="inverse")
        m2.metric("Stock Medio (51-100)", len(medium))
        m3.metric("Stock Óptimo (>100)", len(high))

        # Calculamos el máximo para que la barra llegue al 100% en el producto con más stock
        max_stock_global = int(data['inventory_quantity'].max()) if not data.empty else 100

        config_visual = {
            "product_title": st.column_config.TextColumn("Producto", width="large"),
            "variant_title": st.column_config.TextColumn("Gramaje", width="medium"),
            "Visual": st.column_config.ProgressColumn(
                "Nivel de Stock",
                help="Vista horizontal del inventario disponible",
                format="%d", # Muestra el número dentro o junto a la barra
                min_value=0,
                max_value=max_stock_global,
            )
        }

        #Columnas a mostrar
        display_cols = ['product_title', 'variant_title', 'Visual']

        # --- TABLA 1: MENOS DE 50 UNIDADES ---
        st.subheader("🔴 Crítico: Menos de 50 unidades")
        if not low.empty:
            # Creamos la columna 'Visual' duplicando el valor numérico
            low_viz = low.assign(Visual=low['inventory_quantity'])
            st.dataframe(
                low_viz[display_cols], 
                column_config=config_visual,
                width='stretch',
                hide_index=True
            )

        st.divider()

        # --- TABLA 2: ENTRE 51 Y 100 UNIDADES ---
        st.subheader("🟡 Atención: Entre 51 y 100 unidades")
        if not medium.empty:
            medium_viz = medium.assign(Visual=medium['inventory_quantity'])
            st.dataframe(
                medium_viz[display_cols], 
                column_config=config_visual,
                width='stretch',
                hide_index=True
            )

        st.divider()

        # --- TABLA 3: MÁS DE 100 UNIDADES ---
        st.subheader("🟢 Saludable: Más de 100 unidades")
        if not high.empty:
            high_viz = high.assign(Visual=high['inventory_quantity'])
            st.dataframe(
                high_viz[display_cols], 
                column_config=config_visual,
                width='stretch',
                hide_index=True
            )

    else:
        st.warning("No se pudieron cargar los datos. Por favor intenta de nuevo mas tarde.")

# --- PESTAÑA 2: ACTUALIZACIÓN ---
with tab_actualizacion:
    st.subheader("Actualizar Cantidades de Inventario")
    st.info("Selecciona el producto para ver su SKU y stock actual, luego ingresa la nueva cantidad.")

    if not data.empty:
        # Usamos una lista para recolectar las actualizaciones fuera de un st.form
        updates = {}
        
        # Encabezados de columna con st.columns
        cols_header = st.columns([3, 1, 1, 2])
        cols_header[0].write("**Producto**")
        cols_header[1].write("**SKU**")
        cols_header[2].write("**Inventario Actual**")
        cols_header[3].write("**Cantidad a Agregar**")

        # Generamos las 5 filas (Sin st.form para permitir reactividad)
        for i in range(5):
            c1, c2, c3, c4 = st.columns([3, 1, 1, 2])
            
            selected_prod = c1.selectbox(
                f"Seleccionar producto {i+1}", 
                options=["---"] + list_titles, 
                label_visibility="collapsed", 
                key=f"prod_{i}"
            )
            
            sku_val = ""
            qty_curr = 0
            
            # Al NO estar en un form, esto se ejecutará inmediatamente al cambiar el selectbox
            if selected_prod != "---":
                row_info = data[data['product_title'] == selected_prod].iloc[0]
                sku_val = row_info['sku']
                qty_curr = row_info['inventory_quantity']
                
                c2.write(f"`{sku_val}`")
                c3.write(f"{qty_curr}")
                
                # El valor por defecto (value) del number_input puede ser qty_curr
                new_qty = c4.number_input(
                    "Cantidad", 
                    min_value=0, 
                    value=int(0), 
                    key=f"num_{i}", 
                    label_visibility="collapsed"
                )
                
                # Guardamos la actualización en un diccionario usando el nombre del producto como llave
                updates[selected_prod] = new_qty
            else:
                c2.write("---")
                c3.write("---")
                c4.write("")

        st.markdown("---")
        
        if st.button("🚀 Agregando Inventario", use_container_width=True):
            if updates:
                with st.spinner("Enviando datos..."):
                    filas_para_agregar = []

                    for prod_name, new_val in updates.items():
                        # Extraemos la fila completa como Serie
                        info_fila = data[data['product_title'] == prod_name].iloc[0]
                        
                        filas_para_agregar.append({
                            "inventory_item_id": info_fila.get('inventory_item_id', ''),
                            "product_id": info_fila.get('product_id', ''),
                            "sku": info_fila.get('sku', ''),
                            "inventory_quantity": new_val, # La cantidad nueva ingresada
                            "inv_antes": info_fila.get('inventory_quantity', 0), # La cantidad que había
                            "variant_title": info_fila.get('variant_title', ''),
                            "product_title": prod_name
                        })

                    # 1. Creamos el DataFrame base
                    df_final = pd.DataFrame(filas_para_agregar)

                    # 2. Calculamos el inventario final (Suma de lo nuevo + lo anterior)
                    df_final['inv_final'] = df_final['inventory_quantity'] + df_final['inv_antes']
                    
                    # 3. Agregamos la fecha
                    df_final["fecha_registro"] = datetime.now(bogota_tz).strftime("%d/%m/%Y %H:%M:%S")

                    # 4. Actualizar hoja "Agregar_Inventario" (Solo las columnas necesarias)
                    cols_hoja_agregar = ['inventory_item_id', 'product_id', 'sku', 'inventory_quantity']
                    sheet.update_inventory("Agregar_Inventario", df_final[cols_hoja_agregar])

                    # 5. Actualizar hoja "Registro_Inventario" (Historial completo)
                    # Puedes enviar el df_final completo o seleccionar columnas específicas
                    df_final = df_final[['inventory_item_id', 'product_id', 'sku', 'inventory_quantity', 'inv_antes', 'inv_final', 'fecha_registro']]
                    sheet.update_inventory("Registro_Inventario", df_final)
                    print(df_final.info())
                    
                    st.success(f"¡Se han registrado los productos!")
                    st.info("En unos 5 min quedarán actualizados en Shopify.")
                    
                    resetear_formulario()
                    time.sleep(5)
                    st.rerun()

# Botón para refrescar datos manualmente
if st.sidebar.button("🔄 Actualizar Datos"):
    st.rerun()
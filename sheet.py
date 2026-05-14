#from streamlit_gsheets import GSheetsConnection


#pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib pandas python-dotenv gspread oauth2client pytz streamlit

from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import os
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

# Construimos el diccionario de credenciales
'''
creds_dict = {
    "type": os.getenv("GOOGLE_SHEETS_TYPE"),
    "project_id": os.getenv("GOOGLE_SHEETS_PROJECT_ID"),
    "private_key_id": os.getenv("GOOGLE_SHEETS_PRIVATE_KEY_ID"),
    "private_key": os.getenv("GOOGLE_SHEETS_PRIVATE_KEY").replace('\\n', '\n'),
    "client_email": os.getenv("GOOGLE_SHEETS_CLIENT_EMAIL"),
    "client_id": os.getenv("GOOGLE_SHEETS_CLIENT_ID"),
    "auth_uri": os.getenv("GOOGLE_SHEETS_AUTH_URI"),
    "token_uri": os.getenv("GOOGLE_SHEETS_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("GOOGLE_SHEETS_AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.getenv("GOOGLE_SHEETS_CLIENT_X509_CERT_URL"),
    "universe_domain": "googleapis.com"
}
'''
creds_dict = {
    "type": st.secrets["GOOGLE_SHEETS_TYPE"],
    "project_id": st.secrets["GOOGLE_SHEETS_PROJECT_ID"],
    "private_key_id": st.secrets["GOOGLE_SHEETS_PRIVATE_KEY_ID"],
    "private_key": st.secrets["GOOGLE_SHEETS_PRIVATE_KEY"].replace('\\n', '\n'),
    "client_email": st.secrets["GOOGLE_SHEETS_CLIENT_EMAIL"],
    "client_id": st.secrets["GOOGLE_SHEETS_CLIENT_ID"],
    "auth_uri": st.secrets["GOOGLE_SHEETS_AUTH_URI"],
    "token_uri": st.secrets["GOOGLE_SHEETS_TOKEN_URI"],
    "auth_provider_x509_cert_url": st.secrets["GOOGLE_SHEETS_AUTH_PROVIDER_X509_CERT_URL"],
    "client_x509_cert_url": st.secrets["GOOGLE_SHEETS_CLIENT_X509_CERT_URL"],
    "universe_domain": "googleapis.com"
}

# Definir el scope
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# Nueva forma de autenticar (Recomendada)
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)

# Abrir la hoja de cálculo usando el ID y el nombre de la pestaña
#spreadsheet = client.open_by_key(os.getenv("SPREADSHEET_ID"))
spreadsheet = client.open_by_key(st.secrets["SPREADSHEET_ID"])


def get_inventory_data(hoja):

    """
    Envía una petición a la API de Google Cloud para extraer datos sobre una hoja.

    Parámetros:
        hoja (str): se debe indicar el nombre de la hoja y el rango inicial y final, por
                                    Ejemplo: Citas

    Retorna:
        df: dataframe con los datos en la hoja de calculo y Respuesta 'Datos Extraidos con Exito' o mensaje de error.
    """
    sheet = spreadsheet.worksheet(f"{hoja}")
    try:
        # Extraemos los datos de la hoja de calculo
        data = sheet.get_all_values() # Trae todo como una lista de listas
        
        # Creamos el DataFrame: la primera fila son las cabeceras
        df = pd.DataFrame(data[1:], columns=data[0]) 

        print(f"\nDatos Extraidos con Exito")
        df['inventory_quantity'] = df['inventory_quantity'].astype(int)
        df['variant_title'] = df['variant_title'].replace("Default Title", "Sin Info.").replace("¡Si quiero!", "Sin Info.")
        return df
    except Exception as e:
        print(f"\nOcurrió un error al intentar extraer los datos:\n {e}")
        return None

def filter_data(df, sku_list, title_list, variant_list, qty_range, exclude_negative=True):
    """
    Filtra el DataFrame basándose en selecciones y opcionalmente quita negativos.
    """
    filtered_df = df.copy()

    # --- NUEVO: Filtro para eliminar negativos ---
    if exclude_negative:
        filtered_df = filtered_df[filtered_df['inventory_quantity'] >= 0]

    # Filtro por SKU
    if sku_list:
        filtered_df = filtered_df[filtered_df['sku'].astype(str).isin(sku_list)]

    # Filtro por Nombre de Producto
    if title_list:
        filtered_df = filtered_df[filtered_df['product_title'].isin(title_list)]

    # Filtro por Gramaje / Variante
    if variant_list:
        filtered_df = filtered_df[filtered_df['variant_title'].isin(variant_list)]

    # Filtro por Rango de Cantidad
    min_qty, max_qty = qty_range
    filtered_df = filtered_df[
        (filtered_df['inventory_quantity'] >= min_qty) & 
        (filtered_df['inventory_quantity'] <= max_qty)
    ]

    return filtered_df

def get_status_segments(df):
    """
    Divide el DataFrame en los tres segmentos solicitados,
    ordenados de menor a mayor cantidad.
    """
    # Segmento 1: Menos de 50 unidades
    low_stock = df[df['inventory_quantity'] < 50].sort_values(by='inventory_quantity', ascending=True)
    
    # Segmento 2: Entre 51 y 100 unidades
    medium_stock = df[(df['inventory_quantity'] >= 50) & (df['inventory_quantity'] <= 100)].sort_values(by='inventory_quantity', ascending=True)
    
    # Segmento 3: Más de 100 unidades
    high_stock = df[df['inventory_quantity'] > 100].sort_values(by='inventory_quantity', ascending=True)
    
    return low_stock, medium_stock, high_stock

def update_inventory(nombre_hoja, df):
    """
    Limpia la hoja de cálculo desde A2 hacia abajo y carga un DataFrame.
    
    Parámetros:
    - nombre_hoja (str): El nombre de la pestaña.
    - df (pd.DataFrame): El DataFrame con la información a subir.
    """
    try:
        sheet = spreadsheet.worksheet(nombre_hoja)
        
        # 1. Obtener el número total de filas para saber qué borrar
        # Si la hoja está vacía (solo encabezados), esto evita errores.
        num_filas = sheet.row_count        

        valores = df.fillna("").values.tolist()

        # 3. Insertar los datos empezando en A2
        if valores:
            sheet.append_rows(valores, value_input_option='USER_ENTERED')
            print(f"\nÉxito: Se han cargado {len(valores)} filas'.")
        else:
            print("\nEl DataFrame está vacío, no hay datos para cargar.")

    except Exception as e:
        print(f"\nOcurrió un error al intentar cargar los datos:\n {e}")

def limpiar_inputs():
    """Borra las llaves del session_state para reiniciar los formularios"""
    for i in range(5):
        if f"prod_{i}" in st.session_state:
            st.session_state[f"prod_{i}"] = "---"
        if f"num_{i}" in st.session_state:
            # Aquí lo reiniciamos a 0 o al valor que prefieras
            st.session_state[f"num_{i}"] = 0

'''
df = get_inventory_data("Inventario")
print(df.info())
print(df["variant_title"].unique())
'''
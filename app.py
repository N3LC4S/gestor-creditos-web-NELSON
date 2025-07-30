import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl import load_workbook
from openpyxl.styles import PatternFill

st.set_page_config(layout="wide")

st.title("💼 Sistema de Créditos - Versión Web")

TIPOS_VALIDOS = ['diario', 'semanal', 'quincenal', 'mensual']
PAGO_DIAS = {'diario': 1, 'semanal': 7, 'quincenal': 15, 'mensual': 30}

@st.cache_data

def cargar_excel(archivo):
    df = pd.read_excel(archivo)
    if 'Fecha' in df.columns:
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
    if 'Próximo pago' in df.columns:
        df['Próximo pago'] = pd.to_datetime(df['Próximo pago'], errors='coerce')
    return df

def calcular_estatus(row):
    hoy = datetime.now().date()
    if pd.isnull(row['Próximo pago']):
        return 'Sin fecha'
    dias_restantes = (row['Próximo pago'].date() - hoy).days
    if dias_restantes < 0:
        return 'Vencido'
    elif dias_restantes == 0:
        return 'Pagan hoy'
    else:
        return 'Al día'

def actualizar_calculos(df):
    df['Saldo restante'] = df['Valor'] - df['Pagos realizados']
    df['Estatus'] = df.apply(calcular_estatus, axis=1)
    return df

def guardar_excel(df):
    output = BytesIO()
    df_to_save = df.copy()
    df_to_save['Fecha'] = df_to_save['Fecha'].dt.strftime('%Y-%m-%d')
    df_to_save['Próximo pago'] = df_to_save['Próximo pago'].dt.strftime('%Y-%m-%d')
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_to_save.to_excel(writer, index=False, sheet_name='Pagos')
        wb = writer.book
        ws = writer.sheets['Pagos']
        for i, row in df.iterrows():
            color = None
            if row['Estatus'] == 'Vencido':
                color = 'FF9999'
            elif row['Estatus'] == 'Pagan hoy':
                color = 'FFFF99'
            elif row['Estatus'] == 'Al día':
                color = 'CCFFCC'
            if color:
                for col in range(1, len(df.columns) + 1):
                    ws.cell(row=i+2, column=col).fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
    output.seek(0)
    return output

archivo_excel = st.file_uploader("Sube tu archivo Excel de créditos:", type=['xlsx'])
if archivo_excel:
    df = cargar_excel(archivo_excel)
    df = actualizar_calculos(df)

    st.subheader("🔍 Buscar y filtrar")
    col1, col2 = st.columns(2)
    with col1:
        filtro_nombre = st.text_input("Filtrar por nombre:")
    with col2:
        filtro_estatus = st.selectbox("Filtrar por estatus:", options=["Todos"] + sorted(df['Estatus'].unique().tolist()))

    if filtro_nombre:
        df = df[df['Cliente'].str.contains(filtro_nombre, case=False, na=False)]

    if filtro_estatus != "Todos":
        df = df[df['Estatus'] == filtro_estatus]

    st.subheader("📅 Datos de Créditos")
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        num_rows="dynamic",
        key="tabla_creditos",
        column_config={
            "Fecha": st.column_config.DateColumn("Fecha"),
            "Próximo pago": st.column_config.DateColumn("Próximo pago"),
            "Tipo de pago": st.column_config.TextColumn("Tipo de pago"),
        }
    )

    if st.button("🔄 Guardar cambios en memoria"):
        df_actualizado = edited_df.copy()
        for i, row in df_actualizado.iterrows():
            tipo = str(row['Tipo de pago']).lower()
            if tipo not in PAGO_DIAS:
                st.error(f"Fila {i+2}: Tipo de pago inválido: {tipo}")
                st.stop()
            if pd.notnull(row['Fecha']):
                df_actualizado.at[i, 'Próximo pago'] = row['Fecha'] + timedelta(days=PAGO_DIAS[tipo])
        df_actualizado = actualizar_calculos(df_actualizado)
        st.session_state.df_actualizado = df_actualizado
        st.success("Cambios guardados en memoria. Puedes exportarlos si deseas.")

    if 'df_actualizado' in st.session_state:
        st.subheader("🗂️ Descargar archivo actualizado")
        excel_bytes = guardar_excel(st.session_state.df_actualizado)
        st.download_button("🔧 Descargar Excel", data=excel_bytes, file_name="creditos_actualizado.xlsx")


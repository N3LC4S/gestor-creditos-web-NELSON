import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Alignment, PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows

# Configuración inicial
st.set_page_config(page_title="Gestor de Créditos", layout="wide")
st.title("📋 Gestor de Créditos Web")

# Configuración de días según tipo de pago
PAGO_DIAS = {
    'diario': 1,
    'semanal': 7,
    'quincenal': 15
}

# Colores para exportación según estatus
ESTATUS_COLORES = {
    'Al día': 'C6EFCE',
    'Vencido': 'FFC7CE',
    'Pagan hoy': 'ADD8E6',
    'Próximo a vencer': 'FFEB9C',
    'Pagado': 'DDBEA9'
}

# Cargar archivo Excel
uploaded_file = st.file_uploader("📄 Sube tu archivo Excel de créditos", type=["xlsx"])

# Inicializar sesión
if 'df' not in st.session_state:
    st.session_state.df = None

# Calcular estatus y próxima fecha
def preparar_dataframe(df):
    hoy = datetime.now().date()
    for i, row in df.iterrows():
        tipo = str(row['Tipo de pago']).lower()
        fecha_credito = row['Fecha']
        prox_pago = row['Próximo pago']
        pagos = row['Pagos realizados']
        valor = row['Valor']
        saldo = valor - pagos
        df.at[i, 'Saldo restante'] = saldo

        if saldo <= 0:
            df.at[i, 'Estatus'] = 'Pagado'
            continue

        if pd.isnull(prox_pago) and pd.notnull(fecha_credito):
            if tipo in PAGO_DIAS:
                df.at[i, 'Próximo pago'] = fecha_credito + timedelta(days=PAGO_DIAS[tipo])
                prox_pago = df.at[i, 'Próximo pago']

        if pd.notnull(prox_pago):
            dias_dif = (prox_pago.date() - hoy).days
            if dias_dif < 0:
                df.at[i, 'Estatus'] = 'Vencido'
            elif dias_dif == 0:
                df.at[i, 'Estatus'] = 'Pagan hoy'
            elif dias_dif <= 2:
                df.at[i, 'Estatus'] = 'Próximo a vencer'
            else:
                df.at[i, 'Estatus'] = 'Al día'
        else:
            df.at[i, 'Estatus'] = 'Sin fecha'
    return df

# Exportar Excel con formato

def exportar_excel_con_formato(df):
    output = BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Créditos"

    for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), 1):
        for c_idx, value in enumerate(row, 1):
            celda = ws.cell(row=r_idx, column=c_idx, value=value)
            celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            if r_idx > 1 and df.columns[c_idx - 1] == "Estatus":
                color = ESTATUS_COLORES.get(value, None)
                if color:
                    fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
                    for col in range(1, len(df.columns) + 1):
                        ws.cell(row=r_idx, column=col).fill = fill

    for col in ws.columns:
        max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col)
        ws.column_dimensions[col[0].column_letter].width = max_length + 2

    wb.save(output)
    output.seek(0)
    return output

# Procesamiento principal
if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df.columns = [col.strip().capitalize() for col in df.columns]

    for col in ['Tipo de pago', 'Próximo pago', 'Pagos realizados', 'Saldo restante', 'Estatus']:
        if col not in df.columns:
            if col == 'Tipo de pago':
                df[col] = 'diario'
            elif col == 'Pagos realizados':
                df[col] = 0.0
            elif col == 'Saldo restante':
                df[col] = df['Valor']
            elif col == 'Próximo pago':
                df[col] = pd.NaT
            elif col == 'Estatus':
                df[col] = ''

    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
    df['Próximo pago'] = pd.to_datetime(df['Próximo pago'], errors='coerce')
    df['Pagos realizados'] = pd.to_numeric(df['Pagos realizados'], errors='coerce').fillna(0)
    df['Saldo restante'] = pd.to_numeric(df['Saldo restante'], errors='coerce').fillna(df['Valor'])

    df = preparar_dataframe(df)
    st.session_state.df = df

# Si hay DataFrame cargado
if st.session_state.df is not None:
    df = st.session_state.df

    col1, col2 = st.columns([3, 1])
    with col1:
        filtro = st.selectbox("🔍 Filtrar por estatus", ["Todos"] + sorted(df['Estatus'].unique()))
    with col2:
        busqueda = st.text_input("Buscar cliente")

    df_vista = df.copy()
    if filtro != "Todos":
        df_vista = df_vista[df_vista['Estatus'] == filtro]
    if busqueda:
        df_vista = df_vista[df_vista['Cliente'].astype(str).str.lower().str.contains(busqueda.lower())]

    st.subheader("💳 Créditos")
    edited_df = st.data_editor(df_vista, key="editor", use_container_width=True, hide_index=True, num_rows="dynamic")

    if st.button("✅ Aplicar cambios"):
        for i, row in edited_df.iterrows():
            index = df[df['Cliente'] == row['Cliente']].index[0]
            df.at[index, 'Pagos realizados'] = row['Pagos realizados']
            df.at[index, 'Saldo restante'] = df.at[index, 'Valor'] - row['Pagos realizados']
            df.at[index, 'Fecha'] = datetime.now()
            dias = PAGO_DIAS.get(str(df.at[index, 'Tipo de pago']).lower(), 1)
            df.at[index, 'Próximo pago'] = datetime.now() + timedelta(days=dias)
        df = preparar_dataframe(df)
        st.session_state.df = df
        st.success("Cambios aplicados correctamente")

    st.subheader("➕ Agregar nuevo cobro")
    with st.form("form_nuevo"):
        cliente = st.text_input("Cliente")
        valor = st.number_input("Valor", min_value=0.0)
        tipo_pago = st.selectbox("Tipo de pago", list(PAGO_DIAS.keys()))
        fecha = st.date_input("Fecha del crédito", value=datetime.now().date())
        submitted = st.form_submit_button("Agregar")

        if submitted:
            nuevo = {
                'Fecha': fecha,
                'Cliente': cliente,
                'Valor': valor,
                'Tipo de pago': tipo_pago,
                'Pagos realizados': 0.0,
                'Saldo restante': valor,
                'Próximo pago': fecha + timedelta(days=PAGO_DIAS[tipo_pago]),
                'Estatus': 'Al día'
            }
            st.session_state.df.loc[len(st.session_state.df)] = nuevo
            st.session_state.df = preparar_dataframe(st.session_state.df)
            st.success("Cobro agregado exitosamente")

    st.subheader("📥 Descargar archivo actualizado")
    archivo = exportar_excel_con_formato(st.session_state.df)
    st.download_button("📄 Descargar Excel con formato", archivo, file_name="creditos_actualizados.xlsx")

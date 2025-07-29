# creditos_app_streamlit.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Alignment, PatternFill

st.set_page_config(page_title="Gestor de Créditos", layout="wide")
st.title("📋 Gestor de Créditos Web")

PAGO_DIAS = {
    'diario': 1,
    'semanal': 7,
    'quincenal': 15
}

COLORES = {
    'Vencido': 'FFC7CE',
    'Pagan hoy': 'ADD8E6',
    'Próximo a vencer': 'FFEB9C',
    'Al día': 'C6EFCE',
    'Pagado': 'DDBEA9'
}

# === Funciones ===
def preparar_dataframe(df):
    df.columns = [col.strip().capitalize() for col in df.columns]

    if 'Tipo de pago' not in df.columns:
        df['Tipo de pago'] = 'diario'
    if 'Próximo pago' not in df.columns:
        df['Próximo pago'] = pd.NaT
    if 'Pagos realizados' not in df.columns:
        df['Pagos realizados'] = 0
    if 'Saldo restante' not in df.columns:
        df['Saldo restante'] = df['Valor']
    if 'Estatus' not in df.columns:
        df['Estatus'] = ''
    if 'Fecha' not in df.columns:
        df['Fecha'] = datetime.now().date()

    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
    df['Próximo pago'] = pd.to_datetime(df['Próximo pago'], errors='coerce')
    df['Pagos realizados'] = pd.to_numeric(df['Pagos realizados'], errors='coerce').fillna(0)

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

        if pd.isnull(prox_pago) and not pd.isnull(fecha_credito):
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

def exportar_excel_con_formato(df):
    output = BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Créditos"

    ws.append(list(df.columns))
    for i, row in df.iterrows():
        ws.append(row.tolist())

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        estatus = row[df.columns.get_loc('Estatus')].value
        color = COLORES.get(estatus, None)
        for cell in row:
            cell.alignment = Alignment(horizontal="center", vertical="center")
            if color:
                cell.fill = PatternFill(start_color=color, end_color=color, fill_type="solid")

    for col in ws.columns:
        max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col)
        ws.column_dimensions[col[0].column_letter].width = max_length + 2

    wb.save(output)
    output.seek(0)
    return output

# === Aplicación ===
uploaded_file = st.file_uploader("📄 Sube tu archivo Excel de créditos", type=["xlsx"])
if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df = preparar_dataframe(df)

    if 'df' not in st.session_state:
        st.session_state.df = df.copy()

    # Filtros
    estatus_sel = st.selectbox("🔍 Filtrar por estatus", ["Todos"] + list(df['Estatus'].unique()))
    texto_busqueda = st.text_input("🔎 Buscar por cliente (nombre completo o parcial):")

    df_base = st.session_state.df

    if texto_busqueda:
        df_base = df_base[df_base['Cliente'].astype(str).str.lower().str.contains(texto_busqueda.lower())]

    if estatus_sel != "Todos":
        df_base = df_base[df_base['Estatus'] == estatus_sel]

    st.subheader("📊 Tabla de Créditos (editable)")
    edited_df = st.data_editor(df_base, use_container_width=True, hide_index=True, num_rows="dynamic", key="tabla_creditos")

    if st.button("✅ Aplicar cambios"):
        for _, row in edited_df.iterrows():
            idx = st.session_state.df[st.session_state.df['Cliente'] == row['Cliente']].index[0]
            st.session_state.df.loc[idx, 'Pagos realizados'] = row['Pagos realizados']
            st.session_state.df.loc[idx, 'Saldo restante'] = row['Valor'] - row['Pagos realizados']
            st.session_state.df.loc[idx, 'Fecha'] = datetime.now()
            tipo_pago = st.session_state.df.loc[idx, 'Tipo de pago']
            dias = PAGO_DIAS.get(str(tipo_pago).lower(), 1)
            st.session_state.df.loc[idx, 'Próximo pago'] = datetime.now() + timedelta(days=dias)

        st.session_state.df = preparar_dataframe(st.session_state.df)
        st.success("Cambios aplicados correctamente.")

    with st.expander("➕ Agregar nuevo cobro"):
        with st.form("form_nuevo_cobro"):
            col1, col2 = st.columns(2)
            with col1:
                nuevo_cliente = st.text_input("Cliente")
                nuevo_valor = st.number_input("Valor del crédito", min_value=0.0)
            with col2:
                tipo_pago_nuevo = st.selectbox("Tipo de pago", list(PAGO_DIAS.keys()))
                fecha_inicio = st.date_input("Fecha de inicio", value=datetime.now())

            submitted = st.form_submit_button("Agregar")
            if submitted:
                prox_pago = fecha_inicio + timedelta(days=PAGO_DIAS[tipo_pago_nuevo])
                nuevo_row = {
                    'Fecha': fecha_inicio,
                    'Cliente': nuevo_cliente,
                    'Valor': nuevo_valor,
                    'Tipo de pago': tipo_pago_nuevo,
                    'Pagos realizados': 0,
                    'Saldo restante': nuevo_valor,
                    'Próximo pago': prox_pago,
                    'Estatus': 'Al día'
                }
                st.session_state.df.loc[len(st.session_state.df)] = nuevo_row
                st.session_state.df = preparar_dataframe(st.session_state.df)
                st.success("Nuevo cobro agregado correctamente.")

    st.subheader("📥 Descargar archivo actualizado")
    archivo_excel = exportar_excel_con_formato(st.session_state.df)
    st.download_button("📄 Descargar Excel con formato", archivo_excel, file_name="creditos_actualizados.xlsx")

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Alignment, PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows

st.set_page_config(page_title="Gestor de Créditos", layout="wide")

PAGO_DIAS = {
    'diario': 1,
    'semanal': 7,
    'quincenal': 15,
    'mensual': 30
}

COLORES = {
    'Vencido': 'FFC7CE',
    'Pagan hoy': 'ADD8E6',
    'Próximo a vencer': 'FFEB9C',
    'Al día': 'C6EFCE',
    'Pagado': 'DDBEA9'
}

if "df" not in st.session_state:
    st.session_state.df = None

st.title("📋 Gestor de Créditos")
uploaded_file = st.file_uploader("📄 Cargar archivo Excel", type=["xlsx"])


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
    df['Saldo restante'] = pd.to_numeric(df['Saldo restante'], errors='coerce').fillna(df['Valor'])

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

    for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), 1):
        for c_idx, value in enumerate(row, 1):
            celda = ws.cell(row=r_idx, column=c_idx, value=value)
            celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

            if r_idx > 1 and df.columns[c_idx - 1] == "Estatus":
                estatus = value
                color = COLORES.get(estatus, None)
                if color:
                    fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
                    for col in range(1, len(df.columns) + 1):
                        ws.cell(row=r_idx, column=col).fill = fill

    for col in ws.columns:
        max_length = 0
        col_letter = col[0].column_letter
        for cell in col:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass
        ws.column_dimensions[col_letter].width = max_length + 2

    wb.save(output)
    output.seek(0)
    return output


if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df = preparar_dataframe(df)
    st.session_state.df = df

if st.session_state.df is not None:
    df = st.session_state.df

    filtro = st.selectbox("🔍 Filtrar por estatus", ["Todos"] + list(COLORES.keys()))
    texto_busqueda = st.text_input("🔎 Buscar cliente por nombre")

    df_mostrar = df.copy()
    if filtro != "Todos":
        df_mostrar = df_mostrar[df_mostrar['Estatus'] == filtro]
    if texto_busqueda:
        df_mostrar = df_mostrar[df_mostrar['Cliente'].astype(str).str.contains(texto_busqueda, case=False)]

    st.subheader("📊 Créditos actuales")
    edited_df = st.data_editor(df_mostrar, key="edicion", num_rows="dynamic", use_container_width=True)

    if st.button("💾 Aplicar cambios"):
        for i, row in edited_df.iterrows():
            index = df[df['Cliente'] == row['Cliente']].index[0]
            df.at[index, 'Pagos realizados'] = row['Pagos realizados']
            df.at[index, 'Saldo restante'] = df.at[index, 'Valor'] - row['Pagos realizados']
            df.at[index, 'Fecha'] = datetime.now()

            tipo = str(df.at[index, 'Tipo de pago']).lower()
            dias = PAGO_DIAS.get(tipo, 1)
            df.at[index, 'Próximo pago'] = datetime.now() + timedelta(days=dias)

        df = preparar_dataframe(df)
        st.session_state.df = df
        st.success("✅ Cambios aplicados correctamente")

    st.subheader("➕ Agregar nuevo cobro")
    with st.form("nuevo_cobro"):
        cliente = st.text_input("Nombre del cliente")
        valor = st.number_input("Valor del crédito", min_value=0.0, step=100.0)
        tipo_pago = st.selectbox("Tipo de pago", list(PAGO_DIAS.keys()))
        fecha_inicio = st.date_input("Fecha de inicio", value=datetime.now().date())
        enviado = st.form_submit_button("Agregar")

        if enviado and cliente and valor:
            nuevo = {
                'Fecha': fecha_inicio,
                'Cliente': cliente,
                'Valor': valor,
                'Tipo de pago': tipo_pago,
                'Pagos realizados': 0,
                'Saldo restante': valor,
                'Próximo pago': fecha_inicio + timedelta(days=PAGO_DIAS[tipo_pago]),
                'Estatus': 'Al día'
            }
            df = df.append(nuevo, ignore_index=True)
            df = preparar_dataframe(df)
            st.session_state.df = df
            st.success("✅ Cobro agregado correctamente")

    st.subheader("📥 Descargar archivo actualizado")
    archivo_excel = exportar_excel_con_formato(df)
    st.download_button("📄 Descargar Excel", archivo_excel, file_name="creditos_actualizados.xlsx")

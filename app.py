import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Alignment, PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows

PAGO_DIAS = {
    'diario': 1,
    'semanal': 7,
    'quincenal': 15,
    'mensual': 30
}

ESTATUS_COLORES = {
    'Al día': 'C6EFCE',
    'Vencido': 'FFC7CE',
    'Pagan hoy': 'ADD8E6',
    'Próximo a vencer': 'FFEB9C',
    'Pagado': 'D9C3B0'
}

st.set_page_config(page_title="Gestor de Créditos", layout="wide")
st.title("📋 Gestor de Créditos Web")

uploaded_file = st.file_uploader("📄 Sube tu archivo Excel", type=["xlsx"])

def calcular_proximo_pago(fecha_base, tipo_pago):
    dias = PAGO_DIAS.get(tipo_pago, 1)
    if pd.isnull(fecha_base):
        return pd.NaT
    return fecha_base + timedelta(days=dias)

def actualizar_estatus_y_fecha(df):
    hoy = datetime.now().date()
    for i, row in df.iterrows():
        tipo = str(row['Tipo de pago']).strip().lower()
        valor = row['Valor']
        pagos = row['Pagos realizados']
        saldo = valor - pagos
        df.at[i, 'Saldo restante'] = saldo

        if saldo <= 0:
            df.at[i, 'Estatus'] = 'Pagado'
            df.at[i, 'Próximo pago'] = pd.NaT
            continue

        fecha_base = row['Próximo pago'] if pd.notnull(row['Próximo pago']) else row['Fecha']
        fecha_base = pd.to_datetime(fecha_base, errors='coerce')

        if pd.notnull(fecha_base):
            if fecha_base.date() <= hoy:
                fecha_base = pd.Timestamp(hoy)
            proximo = calcular_proximo_pago(fecha_base, tipo)
            df.at[i, 'Próximo pago'] = proximo
            dias_dif = (proximo.date() - hoy).days

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
                color = ESTATUS_COLORES.get(estatus, None)
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
    if "df_original" not in st.session_state:
        df = pd.read_excel(uploaded_file)
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

        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df['Próximo pago'] = pd.to_datetime(df['Próximo pago'], errors='coerce')
        df['Pagos realizados'] = pd.to_numeric(df['Pagos realizados'], errors='coerce').fillna(0)
        df['Saldo restante'] = pd.to_numeric(df['Saldo restante'], errors='coerce').fillna(df['Valor'])

        df = actualizar_estatus_y_fecha(df)
        st.session_state.df_original = df.copy()
        st.session_state.df_editable = df.copy()

    filtro = st.selectbox("🔍 Filtrar por estatus", ["Todos"] + sorted(st.session_state.df_editable['Estatus'].unique()))
    df_filtrado = st.session_state.df_editable if filtro == "Todos" else st.session_state.df_editable[st.session_state.df_editable['Estatus'] == filtro]

    st.subheader("📊 Editar abonos directamente")
    edited_df = st.data_editor(
        df_filtrado,
        use_container_width=True,
        hide_index=True,
        key="tabla_creditos"
    )

    if st.button("✅ Aplicar cambios"):
        for i, row in edited_df.iterrows():
            index = st.session_state.df_editable[st.session_state.df_editable['Cliente'] == row['Cliente']].index[0]
            st.session_state.df_editable.at[index, 'Pagos realizados'] = row['Pagos realizados']

        st.session_state.df_editable = actualizar_estatus_y_fecha(st.session_state.df_editable)
        st.success("✔️ Datos actualizados correctamente.")

    st.subheader("📥 Descargar archivo actualizado")
    excel_file = exportar_excel_con_formato(st.session_state.df_editable)
    st.download_button("📄 Descargar Excel con formato", excel_file, file_name="creditos_actualizados.xlsx")


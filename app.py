import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from openpyxl import Workbook
from openpyxl.styles import Alignment
from openpyxl.utils.dataframe import dataframe_to_rows

PAGO_DIAS = {
    'diario': 1,
    'semanal': 7,
    'quincenal': 15,
    'mensual': 30
}

st.set_page_config(page_title="Gestor de Créditos", layout="wide")
st.title("📋 Gestor de Créditos Web")

uploaded_file = st.file_uploader("📤 Sube tu archivo Excel", type=["xlsx"])

if uploaded_file:
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

    hoy = datetime.now().date()

    def actualizar_estatus(df):
        for i, row in df.iterrows():
            tipo = str(row['Tipo de pago']).lower()
            fecha_credito = row['Fecha']
            prox_pago = row['Próximo pago']
            pagos = row['Pagos realizados']
            valor = row['Valor']
            saldo = valor - pagos
            df.at[i, 'Saldo restante'] = saldo

            if saldo == 0:
                df.at[i, 'Estatus'] = 'Pagado'
                continue

            if pd.isnull(prox_pago) and pd.notnull(fecha_credito) and tipo in PAGO_DIAS:
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

    df = actualizar_estatus(df)

    filtro = st.selectbox("🔍 Filtrar por estatus", ["Todos"] + sorted(df['Estatus'].unique()))
    df_filtrado = df if filtro == "Todos" else df[df['Estatus'] == filtro]

    st.dataframe(df_filtrado, use_container_width=True)

    st.subheader("💰 Registrar pago")
    nombre = st.selectbox("Selecciona el cliente", df['Cliente'].astype(str).unique())
    monto = st.number_input("Monto a abonar", min_value=0.0, step=100.0)

    if st.button("Registrar pago"):
        index = df[df['Cliente'] == nombre].index[0]
        df.at[index, 'Pagos realizados'] += monto
        df.at[index, 'Saldo restante'] = df.at[index, 'Valor'] - df.at[index, 'Pagos realizados']

        tipo_pago = df.at[index, 'Tipo de pago']
        dias = PAGO_DIAS.get(str(tipo_pago).lower(), 1)

        if pd.notnull(df.at[index, 'Próximo pago']):
            df.at[index, 'Próximo pago'] += timedelta(days=dias)
        else:
            df.at[index, 'Próximo pago'] = datetime.now() + timedelta(days=dias)

        df = actualizar_estatus(df)
        st.success("✅ Pago registrado y actualizado.")

        st.dataframe(df if filtro == "Todos" else df[df['Estatus'] == filtro], use_container_width=True)

    st.subheader("📥 Descargar archivo actualizado")

    def exportar_excel_con_formato(df, nombre_archivo="creditos_actualizados.xlsx"):
        wb = Workbook()
        ws = wb.active
        for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), 1):
            for c_idx, value in enumerate(row, 1):
                celda = ws.cell(row=r_idx, column=c_idx, value=value)
                celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
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
        output_file = nombre_archivo
        wb.save(output_file)
        return output_file

    archivo_excel = exportar_excel_con_formato(df)
    with open(archivo_excel, "rb") as f:
        st.download_button("Descargar Excel", f, file_name=archivo_excel)

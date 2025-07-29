import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Alignment

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

    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
    df['Próximo pago'] = pd.to_datetime(df['Próximo pago'], errors='coerce')

    hoy = datetime.now().date()
    for i, row in df.iterrows():
        tipo = str(row['Tipo de pago']).lower()
        fecha_credito = row['Fecha']
        prox_pago = row['Próximo pago']
        pagos = row['Pagos realizados']
        valor = row['Valor']
        saldo = valor - pagos
        df.at[i, 'Saldo restante'] = saldo

        if pd.isnull(prox_pago) and not pd.isnull(fecha_credito):
            if tipo in PAGO_DIAS:
                df.at[i, 'Próximo pago'] = fecha_credito + timedelta(days=PAGO_DIAS[tipo])
                prox_pago = df.at[i, 'Próximo pago']

        if saldo <= 0:
            df.at[i, 'Estatus'] = 'Pagado'
        elif pd.notnull(prox_pago):
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
    df_export = df.copy()
    df_export['Fecha'] = df_export['Fecha'].dt.strftime('%Y-%m-%d')
    df_export['Próximo pago'] = df_export['Próximo pago'].dt.strftime('%Y-%m-%d')
    df_export.to_excel(output, index=False)
    output.seek(0)
    wb = load_workbook(output)
    ws = wb.active
    estatus_col = list(df_export.columns).index('Estatus') + 1
    for row in range(2, ws.max_row + 1):
        estatus = ws.cell(row=row, column=estatus_col).value
        color = COLORES.get(estatus)
        for col in range(1, ws.max_column + 1):
            celda = ws.cell(row=row, column=col)
            celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            if color:
                celda.fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
    for col in ws.columns:
        max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col)
        ws.column_dimensions[col[0].column_letter].width = max_length + 2
    final_output = BytesIO()
    wb.save(final_output)
    final_output.seek(0)
    return final_output

st.set_page_config(page_title="Gestor de Créditos", layout="wide")
st.title("📋 Gestor de Créditos Web")

uploaded_file = st.file_uploader("📄 Sube tu archivo Excel", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df = preparar_dataframe(df)
    if 'df_original' not in st.session_state:
        st.session_state.df_original = df.copy()

    filtro = st.selectbox("🔍 Filtrar por estatus", ["Todos"] + sorted(df['Estatus'].unique()))
    df_filtrado = df if filtro == "Todos" else df[df['Estatus'] == filtro]

    st.subheader("💳 Tabla de Créditos - Edita directamente los abonos")
    edited_df = st.data_editor(
        df_filtrado,
        use_container_width=True,
        hide_index=True,
        key="tabla_creditos"
    )

    if st.button("✅ Aplicar cambios y actualizar tabla"):
        for i, row in edited_df.iterrows():
            index = df[df['Cliente'] == row['Cliente']].index[0]
            df.at[index, 'Pagos realizados'] = row['Pagos realizados']
            df.at[index, 'Saldo restante'] = df.at[index, 'Valor'] - row['Pagos realizados']

            tipo_pago = df.at[index, 'Tipo de pago']
            dias = PAGO_DIAS.get(str(tipo_pago).lower(), 1)
            df.at[index, 'Fecha'] = datetime.now()
            df.at[index, 'Próximo pago'] = datetime.now() + timedelta(days=dias)

        df = preparar_dataframe(df)
        st.session_state.df_original = df.copy()
        st.success("✔️ Cambios aplicados correctamente.")

    st.subheader("📥 Descargar archivo actualizado")
    excel_file = exportar_excel_con_formato(st.session_state.df_original)
    st.download_button("📄 Descargar Excel con formato", excel_file, file_name="creditos_actualizados.xlsx")



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

st.set_page_config(layout="wide")
st.title("Gestor de Créditos")

@st.cache_data(show_spinner=False)
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

    for i in df.index:
        df = actualizar_fila(df, i)
    return df

def actualizar_fila(df, index):
    row = df.loc[index]
    tipo = str(row['Tipo de pago']).lower()
    fecha_credito = row['Fecha']
    pagos = row['Pagos realizados']
    valor = row['Valor']
    saldo = valor - pagos
    df.at[index, 'Saldo restante'] = saldo

    if not pd.isnull(fecha_credito) and tipo in PAGO_DIAS:
        df.at[index, 'Próximo pago'] = datetime.now() + timedelta(days=PAGO_DIAS[tipo])

    hoy = datetime.now().date()
    prox_pago = df.at[index, 'Próximo pago']
    if saldo <= 0:
        df.at[index, 'Estatus'] = 'Pagado'
    elif pd.notnull(prox_pago):
        dias_dif = (prox_pago.date() - hoy).days
        if dias_dif < 0:
            df.at[index, 'Estatus'] = 'Vencido'
        elif dias_dif == 0:
            df.at[index, 'Estatus'] = 'Pagan hoy'
        elif dias_dif <= 2:
            df.at[index, 'Estatus'] = 'Próximo a vencer'
        else:
            df.at[index, 'Estatus'] = 'Al día'
    else:
        df.at[index, 'Estatus'] = 'Sin fecha'

    return df

def exportar_excel_con_formato(df):
    df_export = df.copy()
    df_export['Fecha'] = df_export['Fecha'].dt.strftime('%Y-%m-%d')
    df_export['Próximo pago'] = df_export['Próximo pago'].dt.strftime('%Y-%m-%d')

    buffer = BytesIO()
    df_export.to_excel(buffer, index=False)
    buffer.seek(0)

    wb = load_workbook(buffer)
    ws = wb.active
    estatus_col = list(df_export.columns).index('Estatus') + 1

    for row in range(2, ws.max_row + 1):
        estatus = ws.cell(row=row, column=estatus_col).value
        color = COLORES.get(estatus)
        for col in range(1, ws.max_column + 1):
            cell = ws.cell(row=row, column=col)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            if color:
                cell.fill = PatternFill(start_color=color, end_color=color, fill_type="solid")

    final_buffer = BytesIO()
    wb.save(final_buffer)
    final_buffer.seek(0)
    return final_buffer

if "df" not in st.session_state:
    st.session_state.df = None
if "ediciones" not in st.session_state:
    st.session_state.ediciones = {}

archivo = st.file_uploader("Carga tu archivo Excel", type=["xlsx"])
if archivo:
    df = pd.read_excel(archivo)
    st.session_state.df = preparar_dataframe(df)
    st.session_state.ediciones = {}

if st.session_state.df is not None:
    df = st.session_state.df

    col1, col2 = st.columns([3, 1])
    with col2:
        filtro = st.selectbox("Filtrar por estatus", ["Todos"] + list(COLORES.keys()))
        busqueda = st.text_input("Buscar por nombre de cliente").lower()

    df_filtrado = df.copy()
    if filtro != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Estatus'] == filtro]
    if busqueda:
        df_filtrado = df_filtrado[df_filtrado['Cliente'].astype(str).str.lower().str.contains(busqueda)]

    edited_df = st.data_editor(
        df_filtrado,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Pagos realizados": st.column_config.NumberColumn("Pagos realizados", step=1000),
            "Fecha": st.column_config.DateColumn("Fecha")
        },
        disabled=[col for col in df.columns if col not in ["Pagos realizados", "Fecha"]]
    )

    if edited_df is not None:
        for i, row in edited_df.iterrows():
            cliente_editado = row['Cliente']
            fecha_editada = pd.to_datetime(row['Fecha'], errors='coerce')

            idx_original = df[(df['Cliente'] == cliente_editado) & (df['Fecha'].dt.date == fecha_editada.date())].index
            if not idx_original.empty:
                idx = idx_original[0]
                cambios = False

                if df.at[idx, 'Pagos realizados'] != row['Pagos realizados']:
                    df.at[idx, 'Pagos realizados'] = row['Pagos realizados']
                    cambios = True

                if df.at[idx, 'Fecha'].date() != fecha_editada.date():
                    df.at[idx, 'Fecha'] = fecha_editada
                    cambios = True

                if cambios:
                    df = actualizar_fila(df, idx)

        st.session_state.df = df

    with st.expander("Agregar nuevo crédito"):
        with st.form("nuevo_credito"):
            col1, col2, col3 = st.columns(3)
            with col1:
                nuevo_cliente = st.text_input("Cliente")
                nuevo_valor = st.number_input("Valor", min_value=0.0, format="%.2f")
            with col2:
                nuevo_tipo = st.selectbox("Tipo de pago", list(PAGO_DIAS.keys()))
                nueva_fecha = st.date_input("Fecha del crédito", value=datetime.now().date())
            with col3:
                agregar = st.form_submit_button("Agregar")

        if agregar and nuevo_cliente:
            nuevo = {
                'Fecha': pd.to_datetime(nueva_fecha),
                'Cliente': nuevo_cliente,
                'Valor': nuevo_valor,
                'Tipo de pago': nuevo_tipo,
                'Pagos realizados': 0,
                'Saldo restante': nuevo_valor,
                'Próximo pago': pd.to_datetime(nueva_fecha) + timedelta(days=PAGO_DIAS[nuevo_tipo]),
                'Estatus': 'Al día'
            }
            df.loc[len(df)] = nuevo
            df = actualizar_fila(df, len(df) - 1)
            st.session_state.df = df
            st.success("Nuevo crédito agregado")
            st.rerun()

    st.download_button(
        label="📅 Descargar archivo actualizado",
        data=exportar_excel_con_formato(df),
        file_name=f"creditos_actualizado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

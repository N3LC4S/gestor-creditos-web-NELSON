import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Alignment

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

st.set_page_config(page_title="Gestor de Créditos", layout="wide")
st.title("Gestor de Créditos")

if "df_global" not in st.session_state:
    st.session_state.df_global = None


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

    hoy = datetime.now().date()
    for i, row in df.iterrows():
        tipo = str(row['Tipo de pago']).lower()
        fecha_credito = row['Fecha']
        pagos = row['Pagos realizados']
        valor = row['Valor']
        saldo = valor - pagos
        df.at[i, 'Saldo restante'] = saldo

        if pd.isnull(row['Próximo pago']) and not pd.isnull(fecha_credito):
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


archivo = st.file_uploader("Cargar archivo Excel", type=['xlsx'])
if archivo:
    df = pd.read_excel(archivo)
    df = preparar_dataframe(df)
    st.session_state.df_global = df.copy()

if st.session_state.df_global is not None:
    df = st.session_state.df_global

    col1, col2 = st.columns([3, 2])
    with col1:
        filtro_estatus = st.selectbox("Filtrar por estatus", ["Todos"] + list(COLORES.keys()))
    with col2:
        filtro_nombre = st.text_input("Buscar por nombre de cliente")

    df_mostrar = df.copy()
    if filtro_estatus != "Todos":
        df_mostrar = df_mostrar[df_mostrar['Estatus'] == filtro_estatus]
    if filtro_nombre:
        df_mostrar = df_mostrar[df_mostrar['Cliente'].str.lower().str.contains(filtro_nombre.lower())]

    st.write("### Datos de Créditos")
    edited = st.data_editor(df_mostrar,
                            num_rows="dynamic",
                            use_container_width=True,
                            column_config={
                                "Fecha": st.column_config.DateColumn(),
                                "Próximo pago": st.column_config.DateColumn()
                            },
                            disabled=[col for col in df.columns if col not in ["Pagos realizados"]]
                            )

    if st.button("Actualizar cambios"):
        for i, row in edited.iterrows():
            index_original = df[df['Cliente'] == row['Cliente']].index[0]
            st.session_state.df_global.at[index_original, 'Pagos realizados'] = row['Pagos realizados']
            valor = df.at[index_original, 'Valor']
            nuevo_saldo = valor - row['Pagos realizados']
            st.session_state.df_global.at[index_original, 'Saldo restante'] = nuevo_saldo
            st.session_state.df_global.at[index_original, 'Fecha'] = datetime.now()
            tipo = str(df.at[index_original, 'Tipo de pago']).lower()
            st.session_state.df_global.at[index_original, 'Próximo pago'] = datetime.now() + timedelta(days=PAGO_DIAS.get(tipo, 1))

        st.session_state.df_global = preparar_dataframe(st.session_state.df_global)
        st.success("Cambios actualizados correctamente")

    with st.expander("Agregar nuevo crédito"):
        col1, col2, col3 = st.columns(3)
        with col1:
            cliente_nuevo = st.text_input("Cliente")
        with col2:
            valor_nuevo = st.number_input("Valor", min_value=0.0)
        with col3:
            tipo_pago_nuevo = st.selectbox("Tipo de pago", list(PAGO_DIAS.keys()))

        if st.button("Agregar crédito"):
            if cliente_nuevo.strip():
                nuevo = {
                    'Fecha': datetime.now(),
                    'Cliente': cliente_nuevo,
                    'Valor': valor_nuevo,
                    'Tipo de pago': tipo_pago_nuevo,
                    'Pagos realizados': 0,
                    'Saldo restante': valor_nuevo,
                    'Próximo pago': datetime.now() + timedelta(days=PAGO_DIAS[tipo_pago_nuevo]),
                    'Estatus': 'Al día'
                }
                st.session_state.df_global.loc[len(df)] = nuevo
                st.session_state.df_global = preparar_dataframe(st.session_state.df_global)
                st.success("Nuevo crédito agregado")
            else:
                st.warning("Debe ingresar el nombre del cliente")

    def generar_excel_con_formato(df):
        output = BytesIO()
        df_export = df.copy()
        df_export['Fecha'] = df_export['Fecha'].dt.strftime('%Y-%m-%d')
        df_export['Próximo pago'] = df_export['Próximo pago'].dt.strftime('%Y-%m-%d')
        df_export.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)

        wb = load_workbook(output)
        ws = wb.active
        estatus_col = list(df.columns).index('Estatus') + 1
        for row in range(2, ws.max_row + 1):
            estatus = ws.cell(row=row, column=estatus_col).value
            color = COLORES.get(estatus)
            for col in range(1, ws.max_column + 1):
                celda = ws.cell(row=row, column=col)
                celda.alignment = Alignment(horizontal="center", vertical="center")
                if color:
                    celda.fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
        final_output = BytesIO()
        wb.save(final_output)
        return final_output.getvalue()

    st.download_button(
        label="🔮 Descargar archivo actualizado",
        data=generar_excel_con_formato(st.session_state.df_global),
        file_name=f"creditos_actualizado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

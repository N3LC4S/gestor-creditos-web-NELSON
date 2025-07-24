import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

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

    hoy = datetime.now().date()

    for i, row in df.iterrows():
        tipo = str(row['Tipo de pago']).lower()
        fecha_credito = row['Fecha']
        prox_pago = row['Próximo pago']
        pagos = row['Pagos realizados']
        valor = row['Valor']
        saldo = valor - pagos
        df.at[i, 'Saldo restante'] = saldo

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

    filtro = st.selectbox("🔍 Filtrar por estatus", ["Todos"] + sorted(df['Estatus'].unique()))
    if filtro != "Todos":
        df = df[df['Estatus'] == filtro]

    st.dataframe(df, use_container_width=True)

    st.subheader("💰 Registrar pago")
    nombre = st.selectbox("Selecciona el cliente", df['Cliente'].unique())
    monto = st.number_input("Monto a abonar", min_value=0.0, step=100.0)

    if st.button("Registrar pago"):
        index = df[df['Cliente'] == nombre].index[0]
        df.at[index, 'Pagos realizados'] += monto
        df.at[index, 'Saldo restante'] = df.at[index, 'Valor'] - df.at[index, 'Pagos realizados']

        tipo_pago = df.at[index, 'Tipo de pago']
        dias = PAGO_DIAS.get(tipo_pago.lower(), 1)

        if pd.notnull(df.at[index, 'Próximo pago']):
            df.at[index, 'Próximo pago'] += timedelta(days=dias)
        else:
            df.at[index, 'Próximo pago'] = datetime.now() + timedelta(days=dias)

        prox_fecha = df.at[index, 'Próximo pago'].date()
        dias_dif = (prox_fecha - hoy).days
        if dias_dif < 0:
            df.at[index, 'Estatus'] = 'Vencido'
        elif dias_dif == 0:
            df.at[index, 'Estatus'] = 'Pagan hoy'
        elif dias_dif <= 2:
            df.at[index, 'Estatus'] = 'Próximo a vencer'
        else:
            df.at[index, 'Estatus'] = 'Al día'

        st.success("✅ Pago registrado y actualizado.")

    st.subheader("📥 Descargar archivo actualizado")
    output = df.copy()
    output_file = "creditos_actualizados.xlsx"
    output.to_excel(output_file, index=False)
    with open(output_file, "rb") as f:
        st.download_button("Descargar Excel", f, file_name=output_file)

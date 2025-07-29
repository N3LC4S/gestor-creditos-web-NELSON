import streamlit as st
import pandas as pd
from tkinter import filedialog, ttk, messagebox
from datetime import datetime, timedelta
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Alignment
import os

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

df_global = None
file_actual = None
tree = None
filtro_actual = ""
df_filtrado = None

def formato_monto(valor):
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    return valor

def cargar_excel():
    global df_global, file_actual
    file_path = filedialog.askopenfilename(filetypes=[('Excel Files', '*.xlsx *.xls')])
    if not file_path:
        return
    file_actual = file_path
    df = pd.read_excel(file_path)
    df = preparar_dataframe(df)
    df_global = df.copy()
    mostrar_tabla(df_global, file_path)

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

        hoy = datetime.now().date()
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

def guardar(selected_item, nuevo_valor, columna):
    global df_global, df_filtrado
    try:
        idx_real = int(selected_item)

        nuevo_valor = float(nuevo_valor)
        nuevo_valor = formato_monto(nuevo_valor)

        if columna == 'Pagos realizados':
            df_global.at[idx_real, 'Pagos realizados'] = nuevo_valor
        elif columna == 'Valor':
            df_global.at[idx_real, 'Valor'] = nuevo_valor

        valor = float(df_global.at[idx_real, 'Valor'])
        pagos = float(df_global.at[idx_real, 'Pagos realizados'])
        saldo = valor - pagos
        saldo = formato_monto(saldo)
        df_global.at[idx_real, 'Saldo restante'] = saldo

        if columna == 'Pagos realizados':
            df_global.at[idx_real, 'Fecha'] = datetime.now()
            tipo_pago = df_global.at[idx_real, 'Tipo de pago']
            dias = PAGO_DIAS.get(str(tipo_pago).lower(), 1)
            df_global.at[idx_real, 'Próximo pago'] = datetime.now() + timedelta(days=dias)

        df_global = preparar_dataframe(df_global)

        if filtro_actual:
            buscar_nombre(None)
        else:
            cargar_datos_en_tabla(df_global)

    except Exception as e:
        messagebox.showerror("Error", f"No se pudo actualizar: {str(e)}")

def cargar_datos_en_tabla(dataframe):
    for row in tree.get_children():
        tree.delete(row)
    for idx, row in dataframe.iterrows():
        tag = row['Estatus']
        valores = []
        for col in dataframe.columns:
            val = row[col]
            if isinstance(val, (float, int)):
                val = formato_monto(val)
            elif isinstance(val, pd.Timestamp):
                val = val.strftime('%Y-%m-%d') if not pd.isnull(val) else ''
            valores.append(val)
        tree.insert('', 'end', iid=str(idx), values=valores, tags=(tag,))

def aplicar_filtro_auto(event=None):
    global filtro_actual, df_filtrado
    filtro = combo_filtro.get()
    if filtro == "Todos":
        filtro_actual = ""
        df_filtrado = df_global
    else:
        filtro_actual = filtro.lower()
        df_filtrado = df_global[df_global['Estatus'].astype(str).str.lower() == filtro_actual]
    cargar_datos_en_tabla(df_filtrado)

def buscar_nombre(event):
    global df_filtrado, filtro_actual
    texto = entry_busqueda.get().lower()
    filtro_actual = texto
    if texto == "":
        df_filtrado = df_global
    else:
        df_filtrado = df_global[df_global['Cliente'].astype(str).str.lower().str.contains(texto)]
    cargar_datos_en_tabla(df_filtrado)

def guardar_como():
    if not file_actual:
        messagebox.showwarning("Atención", "Primero carga un archivo Excel para poder guardar.")
        return
    fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_nuevo = os.path.splitext(file_actual)[0] + f"_actualizado_{fecha}.xlsx"

    # Exportar fechas sin hora
    df_export = df_global.copy()
    df_export['Fecha'] = df_export['Fecha'].dt.strftime('%Y-%m-%d')
    df_export['Próximo pago'] = df_export['Próximo pago'].dt.strftime('%Y-%m-%d')
    df_export.to_excel(nombre_nuevo, index=False)

    wb = load_workbook(nombre_nuevo)
    ws = wb.active
    estatus_col = list(df_global.columns).index('Estatus') + 1
    for row in range(2, ws.max_row + 1):
        estatus = ws.cell(row=row, column=estatus_col).value
        color = COLORES.get(estatus)
        for col in range(1, ws.max_column + 1):
            cell = ws.cell(row=row, column=col)
            cell.alignment = Alignment(horizontal="left", vertical="center")
            if color:
                cell.fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
    wb.save(nombre_nuevo)
    messagebox.showinfo("Guardado", f"Archivo guardado como: {nombre_nuevo}")

def editar_pago(event):
    item = tree.identify_row(event.y)
    column = tree.identify_column(event.x)
    if not item:
        return

    col_index = int(column.replace('#', '')) - 1
    columnas = list(df_global.columns)
    if col_index >= len(columnas):
        return
    col_name = columnas[col_index]

    if col_name not in ['Valor', 'Pagos realizados']:
        return

    valor_actual = tree.set(item, col_name)
    entry = tk.Entry(tree)
    x, y, width, height = tree.bbox(item, column)
    entry.place(x=x, y=y, width=width, height=height)
    entry.insert(0, valor_actual)
    entry.focus()

    def guardar_cambio(event):
        try:
            nuevo_valor = float(entry.get())
            entry.destroy()
            guardar(item, nuevo_valor, col_name)
        except ValueError:
            messagebox.showerror("Error", "El valor ingresado no es válido.")
            entry.destroy()

    entry.bind('<Return>', guardar_cambio)
    entry.bind('<FocusOut>', lambda e: entry.destroy())

def agregar_nuevo_cobro():
    global df_global

    ventana_nuevo = tk.Toplevel()
    ventana_nuevo.title("Agregar Nuevo Cobro")
    ventana_nuevo.geometry("300x300")

    ttk.Label(ventana_nuevo, text="Fecha (YYYY-MM-DD):").pack(pady=2)
    entry_fecha = ttk.Entry(ventana_nuevo)
    entry_fecha.insert(0, datetime.now().strftime("%Y-%m-%d"))
    entry_fecha.pack()

    ttk.Label(ventana_nuevo, text="Cliente:").pack(pady=2)
    clientes_existentes = sorted(df_global['Cliente'].dropna().unique().tolist())
    combo_cliente = ttk.Combobox(ventana_nuevo, values=clientes_existentes)
    combo_cliente.pack()

    ttk.Label(ventana_nuevo, text="Valor:").pack(pady=2)
    entry_valor = ttk.Entry(ventana_nuevo)
    entry_valor.pack()

    ttk.Label(ventana_nuevo, text="Tipo de pago (diario/semanal/quincenal):").pack(pady=2)
    combo_tipo = ttk.Combobox(ventana_nuevo, values=list(PAGO_DIAS.keys()))
    combo_tipo.set("diario")
    combo_tipo.pack()

    def guardar_nuevo():
        global df_global
        try:
            fecha = datetime.strptime(entry_fecha.get(), "%Y-%m-%d")
            cliente = combo_cliente.get().strip()
            valor = float(entry_valor.get())
            valor = formato_monto(valor)
            tipo = combo_tipo.get().strip().lower()

            if cliente == "" or tipo not in PAGO_DIAS:
                raise ValueError("Datos incompletos o tipo de pago inválido.")

            nuevo = {
                'Fecha': fecha,
                'Cliente': cliente,
                'Valor': valor,
                'Tipo de pago': tipo,
                'Pagos realizados': 0,
                'Saldo restante': valor,
                'Próximo pago': fecha + timedelta(days=PAGO_DIAS[tipo]),
                'Estatus': 'Al día'
            }

            df_global.loc[len(df_global)] = nuevo
            df_global = preparar_dataframe(df_global)
            cargar_datos_en_tabla(df_global)
            ventana_nuevo.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo agregar el nuevo cobro: {e}")

    ttk.Button(ventana_nuevo, text="Guardar", command=guardar_nuevo).pack(pady=10)

def mostrar_tabla(df, file_path):
    global tree, combo_filtro, entry_busqueda
    ventana = tk.Toplevel()
    ventana.title("Gestor de Créditos")
    ventana.geometry("1100x600")

    columns = list(df.columns)
    tree = ttk.Treeview(ventana, columns=columns, show='headings')
    tree.pack(expand=True, fill='both')

    style = ttk.Style()
    style.configure("Treeview", rowheight=25)

    for estatus, color in COLORES.items():
        tree.tag_configure(estatus, background=f'#{color}')

    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=130)

    tree.bind('<Double-1>', editar_pago)
    cargar_datos_en_tabla(df)

    entry_busqueda = ttk.Entry(ventana)
    entry_busqueda.pack(pady=5)
    entry_busqueda.bind("<KeyRelease>", buscar_nombre)

    combo_filtro = ttk.Combobox(ventana, values=["Todos"] + list(COLORES.keys()))
    combo_filtro.set("Todos")
    combo_filtro.pack(pady=5)
    combo_filtro.bind("<<ComboboxSelected>>", aplicar_filtro_auto)

    ttk.Button(ventana, text="Agregar nuevo cobro", command=agregar_nuevo_cobro).pack(pady=5)
    ttk.Button(ventana, text="Guardar como nuevo archivo", command=guardar_como).pack(pady=5)

root = tk.Tk()
root.title("Gestor de Créditos")
root.geometry("400x200")
ttk.Button(root, text="Cargar archivo Excel", command=cargar_excel).pack(expand=True)
root.mainloop()

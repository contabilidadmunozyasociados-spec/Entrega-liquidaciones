import sqlite3
from datetime import date
import streamlit as st
import pandas as pd

DB = "control_vehiculo.db"

# ---------------------- DB ----------------------
def get_conn():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS registros (
            fecha TEXT PRIMARY KEY,
            recaudacion INTEGER,
            conductor INTEGER,
            bono INTEGER,
            combustible INTEGER,
            liquidacion INTEGER,
            repuestos INTEGER,
            detalle_repuestos TEXT
        )
    """)
    conn.commit()
    conn.close()

def guardar_o_actualizar(fecha, recaudacion, conductor, bono, combustible, liquidacion, repuestos, detalle):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO registros VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(fecha) DO UPDATE SET
            recaudacion=excluded.recaudacion,
            conductor=excluded.conductor,
            bono=excluded.bono,
            combustible=excluded.combustible,
            liquidacion=excluded.liquidacion,
            repuestos=excluded.repuestos,
            detalle_repuestos=excluded.detalle_repuestos
    """, (fecha, int(recaudacion), int(conductor), int(bono), int(combustible), int(liquidacion), int(repuestos), detalle))
    conn.commit()
    conn.close()

def obtener_datos():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM registros ORDER BY fecha ASC", conn)
    conn.close()

    if not df.empty:
        cols = ["recaudacion","conductor","bono","combustible","liquidacion","repuestos"]
        for col in cols:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df

# ---------------------- CALCULOS ----------------------
def calcular(df):
    df["total_conductor"] = df["conductor"] + df["bono"]
    df["total_gastos"] = df["total_conductor"] + df["combustible"] + df["liquidacion"] + df["repuestos"]
    df["ganancia"] = df["recaudacion"] - df["total_gastos"]
    df["acumulado"] = df["ganancia"].cumsum()
    return df

# ---------------------- APP ----------------------
def main():
    st.set_page_config(page_title="Control Vehículo", layout="wide")
    init_db()

    st.title("🚕 Control Diario de Vehículo")

    # -------- FORM --------
    with st.form("form", clear_on_submit=True):
        fecha = st.date_input("Fecha", value=date.today())
        recaudacion = st.number_input("Recaudación", min_value=0, step=1000)

        # NUEVO: Opciones para elegir si se aplica conductor y/o bono
        col_opcion1, col_opcion2 = st.columns(2)
        with col_opcion1:
            aplicar_conductor = st.checkbox("Agregar % conductor (30%)", value=True)
        with col_opcion2:
            aplicar_bono = st.checkbox("Agregar Bono ($4.000)", value=True)

        # Lógica de cálculo basada en los clicks
        conductor = int(recaudacion * 0.3) if aplicar_conductor else 0
        bono = 4000 if aplicar_bono else 0
        total_conductor = conductor + bono

        st.info(f"Porcentaje conductor: ${conductor:,}".replace(",","."))
        st.info(f"Bono: ${bono:,}".replace(",","."))
        st.write(f"**Total conductor: ${total_conductor:,}**".replace(",","."))

        col1, col2 = st.columns(2)
        with col1:
            combustible = st.number_input("Combustible", min_value=0, step=1000)
            liquidacion = st.number_input("Liquidación", min_value=0, step=1000)
        with col2:
            repuestos = st.number_input("Repuestos", min_value=0, step=1000)
            detalle = st.text_input("Detalle repuestos")

        if st.form_submit_button("Guardar / Actualizar día"):
            guardar_o_actualizar(
                fecha.isoformat(), recaudacion, conductor, bono,
                combustible, liquidacion, repuestos, detalle
            )
            st.success("Guardado correctamente")
            st.rerun()

    # -------- DATA --------
    df = obtener_datos()

    if df.empty:
        st.warning("Sin datos")
        return

    df = calcular(df)

    # -------- FILTRO --------
    st.subheader("Filtro")
    fechas = pd.to_datetime(df["fecha"])
    min_f, max_f = fechas.min(), fechas.max()
    rango = st.date_input("Rango fechas", [min_f, max_f])

    if len(rango) == 2:
        df = df[(fechas >= pd.to_datetime(rango[0])) & (fechas <= pd.to_datetime(rango[1]))]

    # -------- RESUMEN --------
    total_recaudado = int(df["recaudacion"].sum())
    total_conductor = int(df["total_conductor"].sum())
    total_gastos = int(df["total_gastos"].sum())
    ganancia_total = int(df["ganancia"].sum())

    st.subheader("Resumen")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Recaudado", f"${total_recaudado:,}".replace(",","."))
    c2.metric("Conductor", f"${total_conductor:,}".replace(",","."))
    c3.metric("Gastos", f"${total_gastos:,}".replace(",","."))
    c4.metric("Ganancia", f"${ganancia_total:,}".replace(",","."))

    # -------- ALERTAS --------
    if ganancia_total < 0:
        st.error("Estás en pérdida en el periodo seleccionado")

    # -------- HISTORIAL --------
    st.subheader("Historial")
    st.dataframe(df, use_container_width=True)

    # -------- EXPORT --------
    csv = df.to_csv(index=False).encode()
    st.download_button("Descargar CSV", csv, "reporte.csv", "text/csv")

    # -------- GRAFICO --------
    st.subheader("Evolución")
    st.line_chart(df.set_index("fecha")["acumulado"])

if __name__ == "__main__":
    main()
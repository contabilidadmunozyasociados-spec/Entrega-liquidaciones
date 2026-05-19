import streamlit as st
import pandas as pd
from datetime import date, datetime
import firebase_admin
from firebase_admin import credentials, firestore
import requests

# ---------------------- CONFIGURACIÓN FIREBASE ----------------------
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)

db = firestore.client()
COLLECTION_NAME = "registros"
API_KEY = st.secrets["firebase"]["api_key"]

# ---------------------- AUTENTICACIÓN ----------------------
def login_usuario(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    response = requests.post(url, json=payload)
    return response.json()

def registrar_usuario(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    response = requests.post(url, json=payload)
    return response.json()

def check_login():
    if "user" not in st.session_state:
        st.session_state.user = None

    if st.session_state.user is None:
        st.title("🔐 Acceso al Sistema")
        
        tab1, tab2 = st.tabs(["Iniciar Sesión", "Crear Cuenta Nueva"])
        
        with tab1:
            st.subheader("Ingresa con tu cuenta")
            email_login = st.text_input("Correo electrónico", key="login_email")
            password_login = st.text_input("Contraseña", type="password", key="login_pass")
            
            if st.button("Iniciar Sesión"):
                result = login_usuario(email_login, password_login)
                if "idToken" in result:
                    st.session_state.user = email_login
                    st.success("¡Acceso concedido!")
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas. Intenta de nuevo.")
                    
        with tab2:
            st.subheader("Registro de nuevos conductores")
            email_reg = st.text_input("Correo electrónico", key="reg_email")
            password_reg = st.text_input("Contraseña (mínimo 6 caracteres)", type="password", key="reg_pass")
            
            if st.button("Crear mi cuenta"):
                if len(password_reg) < 6:
                    st.warning("La contraseña debe tener al menos 6 caracteres.")
                else:
                    result = registrar_usuario(email_reg, password_reg)
                    if "idToken" in result:
                        db.collection("usuarios_registrados").document(email_reg).set({
                            "email": email_reg,
                            "fecha_registro": datetime.now().isoformat()
                        })
                        st.success("✅ Cuenta creada exitosamente. Ve a la pestaña 'Iniciar Sesión' para entrar.")
                    else:
                        error_msg = result.get("error", {}).get("message", "Error desconocido")
                        if error_msg == "EMAIL_EXISTS":
                            st.error("Este correo ya está registrado en el sistema.")
                        else:
                            st.error(f"Error al crear cuenta: {error_msg}")
                            
        st.stop()

# ---------------------- BASE DE DATOS FIRESTORE ----------------------
def guardar_o_actualizar(fecha, recaudacion, conductor, bono, combustible, liquidacion, repuestos, detalle):
    doc_ref = db.collection(COLLECTION_NAME).document(fecha)
    doc_ref.set({
        "recaudacion": int(recaudacion),
        "conductor": int(conductor),
        "bono": int(bono),
        "combustible": int(combustible),
        "liquidacion": int(liquidacion),
        "repuestos": int(repuestos),
        "detalle_repuestos": detalle
    }, merge=True)

def obtener_datos():
    docs = db.collection(COLLECTION_NAME).stream()
    data = []
    for doc in docs:
        row = doc.to_dict()
        row["fecha"] = doc.id
        data.append(row)
        
    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values(by="fecha", ascending=True)
        cols = ["recaudacion", "conductor", "bono", "combustible", "liquidacion", "repuestos"]
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

# ---------------------- APP PRINCIPAL ----------------------
def main():
    st.set_page_config(page_title="Control Vehículo", layout="wide")
    
    # Validar acceso primero
    check_login()

    # Botón para cerrar sesión
    st.sidebar.write(f"👤 Usuario: {st.session_state.user}")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.user = None
        st.rerun()

    st.title("🚕 Control Diario de Vehículo (Cloud)")

    # -------- FORMULARIO --------
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
            st.success("Guardado correctamente en la nube ☁️")
            st.rerun()

    # -------- DATOS --------
    df = obtener_datos()
    if df.empty:
        st.warning("Sin datos en Firebase")
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
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Recaudado", f"${total_recaudado:,}".replace(",","."))
    c2.metric("Conductor", f"${total_conductor:,}".replace(",","."))
    c3.metric("Gastos", f"${total_gastos:,}".replace(",","."))
    c4.metric("Ganancia", f"${ganancia_total:,}".replace(",","."))

    if ganancia_total < 0:
        st.error("Estás en pérdida en el periodo seleccionado")

    # -------- HISTORIAL Y GRAFICO --------
    st.subheader("Historial")
    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode()
    st.download_button("Descargar CSV", csv, "reporte.csv", "text/csv")

    st.subheader("Evolución")
    st.line_chart(df.set_index("fecha")["acumulado"])

if __name__ == "__main__":
    main()
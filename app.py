"""
app.py - Interfaz web para graficar ensayos GDS.

Ejecutar localmente:  streamlit run app.py
"""
import io

import streamlit as st

from gds_core import ESCALAS, graficar, leer_gds, opciones_ejes, resumen

st.set_page_config(page_title="Visualizador GDS", layout="wide")
st.title("Visualizador de ensayos GDS")

archivo = st.sidebar.file_uploader("Archivo .gds", type=["gds", "csv"])
if archivo is None:
    st.info("Sube un archivo .gds para empezar.")
    st.stop()

try:
    ensayo = leer_gds(archivo.getvalue(), nombre=archivo.name.rsplit(".", 1)[0])
except ValueError as err:
    st.error(f"No se pudo leer el archivo: {err}")
    st.stop()

ejes = opciones_ejes(ensayo)
claves = list(ejes)
etiquetas = [ejes[k] for k in claves]

def _indice(clave, por_defecto):
    return claves.index(clave) if clave in claves else por_defecto

st.sidebar.subheader("Ejes")
x = st.sidebar.selectbox(
    "Eje X", claves, index=_indice("t", 0), format_func=lambda k: ejes[k]
)
y = st.sidebar.selectbox(
    "Eje Y", claves, index=_indice("desp_axial", 0), format_func=lambda k: ejes[k]
)
intercambiar = st.sidebar.checkbox("Intercambiar X e Y")
escalas = list(ESCALAS)
escala_x = st.sidebar.radio("Escala X", escalas, horizontal=True)
escala_y = st.sidebar.radio("Escala Y", escalas, horizontal=True)

st.sidebar.subheader("Stages")
stages = st.sidebar.multiselect(
    "Stages a mostrar",
    sorted(ensayo.df["stage"].unique().tolist()),
    default=sorted(ensayo.df["stage"].unique().tolist()),
)
modo = st.sidebar.radio(
    "Modo",
    ["conjunto", "superpuesto"],
    help="Conjunto: tiempo absoluto. Superpuesto: cada stage arranca en t = 0.",
)
desplazamiento = 0.0
if modo == "superpuesto":
    desplazamiento = st.sidebar.number_input(
        "Separación vertical entre stages", value=0.0, step=0.5
    )

st.sidebar.subheader("Filtro")
mediana = st.sidebar.slider("Mediana móvil (1 = sin filtro)", 1, 21, 1, step=2)

fig, avisos = graficar(
    ensayo, x, y,
    intercambiar=intercambiar,
    escala_x=escala_x, escala_y=escala_y,
    stages=stages or None, modo=modo,
    desplazamiento=desplazamiento, mediana=mediana,
)
for aviso in avisos:
    st.warning(aviso)
st.pyplot(fig)

buf = io.BytesIO()
fig.savefig(buf, format="png", dpi=150)
st.download_button("Descargar figura (PNG)", buf.getvalue(), file_name="grafico.png", mime="image/png")

with st.expander("Resumen de lectura"):
    st.json(resumen(ensayo), expanded=True)
with st.expander("Datos"):
    st.dataframe(ensayo.df)

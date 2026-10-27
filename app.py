"""
app.py - Interfaz web para graficar ensayos GDS.

Ejecutar localmente:  streamlit run app.py
"""
import io

import pandas as pd
import streamlit as st

from gds_core import ESCALAS, ajustes_union, graficar, leer_gds, opciones_ejes, resumen

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
invertir_y = st.sidebar.checkbox(
    "Invertir eje Y (valores hacia abajo)",
    help="Útil para perfiles de profundidad: el origen queda arriba.",
)

# Eje mostrado en X e Y (después del intercambio)
xc, yc = (y, x) if intercambiar else (x, y)

st.sidebar.subheader("Zoom")
limites = {}
if st.sidebar.checkbox("Límites manuales"):
    c1, c2 = st.sidebar.columns(2)
    limites["xmin"] = c1.number_input("X mín", value=float(ensayo.df[xc].min()), key=f"xmin_{xc}")
    limites["xmax"] = c2.number_input("X máx", value=float(ensayo.df[xc].max()), key=f"xmax_{xc}")
    limites["ymin"] = c1.number_input("Y mín", value=float(ensayo.df[yc].min()), key=f"ymin_{yc}")
    limites["ymax"] = c2.number_input("Y máx", value=float(ensayo.df[yc].max()), key=f"ymax_{yc}")

st.sidebar.subheader("Stages")
todas = sorted(ensayo.df["stage"].unique().tolist())
stages = st.sidebar.multiselect("Stages a mostrar", todas, default=todas)
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

st.sidebar.subheader("Unir stages")
with st.sidebar.expander("Desplazar cada stage"):
    st.caption(
        "Suma un valor a cada stage, en las unidades del eje mostrado. "
        "Por ejemplo, para colocar un stage debajo de otro, usa Desp. Y "
        "con el valor del final del stage anterior."
    )
    eje_union = st.radio("Unir sobre el eje", ["Y", "X"], horizontal=True)
    if st.button("Calcular unión automática"):
        st.session_state["base_ajustes"] = ajustes_union(
            ensayo, x, y, intercambiar, todas, eje=eje_union.lower()
        )
        st.session_state["version_ajuste"] = st.session_state.get("version_ajuste", 0) + 1
    base = st.session_state.get("base_ajustes", {})
    version = st.session_state.get("version_ajuste", 0)
    tabla = pd.DataFrame({
        "Stage": todas,
        "Desp. X": [base.get(s, (0.0, 0.0))[0] for s in todas],
        "Desp. Y": [base.get(s, (0.0, 0.0))[1] for s in todas],
    })
    # La clave cambia al recalcular, así la tabla muestra los valores nuevos
    editada = st.data_editor(
        tabla, hide_index=True, disabled=["Stage"], key=f"ajustes_{version}"
    )
ajustes = {
    int(f["Stage"]): (float(f["Desp. X"]), float(f["Desp. Y"]))
    for _, f in editada.iterrows()
}

st.sidebar.subheader("Filtro")
mediana = st.sidebar.slider("Mediana móvil (1 = sin filtro)", 1, 21, 1, step=2)

fig, avisos = graficar(
    ensayo, x, y,
    intercambiar=intercambiar,
    escala_x=escala_x, escala_y=escala_y,
    stages=stages or None, modo=modo,
    desplazamiento=desplazamiento, mediana=mediana,
    invertir_y=invertir_y, limites=limites or None, ajustes=ajustes,
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

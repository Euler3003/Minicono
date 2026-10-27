"""
gds_core.py - Lectura y graficado de ensayos GDS (triaxial).

Sin dependencia de la interfaz: se usa desde app.py o desde la línea de comandos.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# Número válido con punto decimal. Una coma nunca es decimal en este formato.
NUM_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")

CLAVES = {
    "Stage Number": "stage",
    "Time since start of test": "t",
    "Time since start of stage": "t_stage",
    "Radial Pressure": "camara",
    "Radial Volume": "vol_camara",
    "Back Pressure": "contrapresion",
    "Back Volume": "vol_contrapresion",
    "Load Cell": "carga",
    "Pore Pressure": "presion_poros",
    "Axial Displacement": "desp_axial",
    "Total Volume Change": "delta_vol",
}

ETIQUETAS = {
    "t": "Tiempo",
    "t_stage": "Tiempo en el stage",
    "stage": "Stage",
    "desp_axial": "Deformación axial",
    "eps_a": "Deformación axial",
    "carga": "Load cell",
    "presion_poros": "Presión de poros",
    "camara": "Presión de cámara",
    "contrapresion": "Contrapresión",
    "delta_vol": "Cambio de volumen total",
}

ESCALAS = {"lineal": "linear", "log": "log", "symlog": "symlog"}


@dataclass
class Ensayo:
    nombre: str
    meta: dict
    df: pd.DataFrame
    unidades: dict
    descartadas: list = field(default_factory=list)
    problemas: list = field(default_factory=list)


def _decodificar(b: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    raise ValueError("No se pudo decodificar el archivo")


def _separar(col: str) -> tuple[str, str]:
    """'Axial Displacement (mm)' -> ('Axial Displacement', 'mm')"""
    m = re.match(r"^(.*?)\s*\((.*)\)$", col)
    return (m.group(1).strip(), m.group(2).strip()) if m else (col.strip(), "")


def _unidad(u: str) -> str:
    # En el archivo, U+FFFD (�) sustituye a ³ o °
    return u.replace("�C", "°C").replace("�", "³")


def leer_gds(origen, nombre: str | None = None, estricto: bool = True) -> Ensayo:
    """Acepta una ruta (str/Path) o bytes del archivo subido."""
    if isinstance(origen, (bytes, bytearray)):
        b, nombre = bytes(origen), nombre or "ensayo"
    else:
        ruta = Path(origen)
        b, nombre = ruta.read_bytes(), ruta.stem

    filas = list(csv.reader(io.StringIO(_decodificar(b))))

    # 1) Metadatos: líneas "clave","valor" antes del encabezado de la tabla
    meta, inicio = {}, None
    for i, f in enumerate(filas):
        if f and f[0].strip() == "Stage Number":
            inicio = i
            break
        if len(f) >= 2 and f[0].strip():
            meta[f[0].strip().rstrip(":")] = f[1].strip()
    if inicio is None:
        raise ValueError("No se encontró el encabezado 'Stage Number'. ¿Es un archivo GDS?")

    # 2) Tabla: cada fila debe tener exactamente tantos campos como el encabezado
    cab = [c.strip() for c in filas[inicio]]
    n = len(cab)
    cuerpo, problemas = [], []
    for j, f in enumerate(filas[inicio + 1:], start=inicio + 2):
        if not any(c.strip() for c in f):
            continue
        if len(f) != n:
            problemas.append(
                f"línea {j}: {len(f)} campos, se esperaban {n} (¿coma decimal sin comillas?)"
            )
            continue
        cuerpo.append(f)

    if problemas and estricto:
        raise ValueError(
            "Filas con formato inesperado:\n" + "\n".join(problemas[:20])
            + "\nDesactiva la validación estricta para omitirlas."
        )

    crudo = pd.DataFrame(cuerpo, columns=cab)

    # 3) Conversión numérica estricta; vacíos -> NaN; descarte de columnas sin información
    datos, unidades, descartadas = {}, {}, []
    for col in cab:
        nombre_col, unidad = _separar(col)
        clave = CLAVES.get(nombre_col, re.sub(r"\W+", "_", nombre_col).strip("_").lower())
        v = crudo[col].str.strip()
        vacio = v.eq("")
        invalido = ~(vacio | v.str.match(NUM_RE))
        if invalido.any():
            raise ValueError(f"{col}: valores no numéricos {v[invalido].unique()[:5].tolist()}")
        s = pd.to_numeric(v.mask(vacio))
        if clave != "stage" and (s.isna().all() or s.nunique(dropna=True) <= 1):
            descartadas.append(col)
            continue
        datos[clave] = s
        unidades[clave] = _unidad(unidad)

    df = pd.DataFrame(datos).reset_index(drop=True)
    df["stage"] = df["stage"].astype(int)

    # 4) Deformación axial en % con la altura inicial del espécimen
    if "Initial Height (mm)" in meta and "desp_axial" in df:
        h0 = float(meta["Initial Height (mm)"])
        df["eps_a"] = df["desp_axial"] / h0 * 100
        unidades["eps_a"] = "%"

    return Ensayo(nombre, meta, df, unidades, descartadas, problemas)


def resumen(e: Ensayo) -> dict:
    d = e.df
    nan = d.isna().sum()
    return {
        "Archivo": e.nombre,
        "Lecturas": len(d),
        "Stages": sorted(d["stage"].unique().tolist()),
        "Columnas usadas": list(e.unidades),
        "Columnas descartadas (vacías o constantes)": e.descartadas,
        "Vacíos convertidos a NaN": {k: int(v) for k, v in nan.items() if v > 0},
        "Filas omitidas por formato": e.problemas,
    }


def etiqueta(e: Ensayo, clave: str) -> str:
    base = ETIQUETAS.get(clave, clave)
    u = e.unidades.get(clave, "")
    return f"{base} [{u}]" if u else base


def opciones_ejes(e: Ensayo) -> dict:
    """Claves disponibles para ejes, con su etiqueta legible."""
    return {k: etiqueta(e, k) for k in e.df.columns if k != "stage"}


def preparar(e: Ensayo, x: str, y: str, intercambiar: bool, escala_x: str, escala_y: str,
             stages, modo: str, mediana: int):
    d = e.df
    avisos = []
    if stages:
        d = d[d["stage"].isin(stages)]

    if intercambiar:
        x, y = y, x
        escala_x, escala_y = escala_y, escala_x
    if modo == "superpuesto" and x == "t":
        x = "t_stage"

    if mediana > 1:
        d = d.copy()
        d[y] = d.groupby("stage")[y].transform(
            lambda s: s.rolling(mediana, center=True, min_periods=1).median()
        )

    for eje, esc in ((x, escala_x), (y, escala_y)):
        if esc == "log":
            malos = d[eje] <= 0
            if malos.any():
                avisos.append(f"{eje}: {int(malos.sum())} puntos ≤ 0 omitidos (escala log)")
            d = d[~malos]

    return d.dropna(subset=[x, y]), x, y, escala_x, escala_y, avisos


def graficar(e: Ensayo, x: str, y: str, intercambiar=False, escala_x="lineal",
             escala_y="lineal", stages=None, modo="conjunto", desplazamiento=0.0,
             mediana=1, leyenda=True, titulo=None, invertir_y=False,
             limites=None, ajustes=None):
    """
    ajustes: {stage: (desp_x, desp_y)} en unidades del eje mostrado.
             Permite colocar cada stage a continuación de otra.
    limites: {"xmin", "xmax", "ymin", "ymax"}; None = automático.
    invertir_y: el valor mayor queda abajo (perfiles de profundidad).
    """
    d, x, y, ex, ey, avisos = preparar(
        e, x, y, intercambiar, escala_x, escala_y, stages, modo, mediana
    )
    ajustes = ajustes or {}
    limites = limites or {}
    fig, ax = plt.subplots(figsize=(9, 6))
    for k, (st, g) in enumerate(d.groupby("stage")):
        dx, dy = ajustes.get(int(st), (0.0, 0.0))
        off = k * desplazamiento if modo == "superpuesto" else 0.0
        ax.plot(g[x] + dx, g[y] + dy + off, lw=0.9, label=f"Stage {st}")
    ax.set_xscale(ESCALAS[ex])
    ax.set_yscale(ESCALAS[ey])
    ax.set_xlabel(etiqueta(e, x))
    ax.set_ylabel(etiqueta(e, y))
    ax.set_title(titulo or f"{e.nombre} ({modo})")
    ax.grid(True, which="both", alpha=0.3)
    # Zoom: None mantiene el límite automático
    ax.set_xlim(limites.get("xmin"), limites.get("xmax"))
    ax.set_ylim(limites.get("ymin"), limites.get("ymax"))
    if invertir_y:
        ax.invert_yaxis()  # después de set_ylim, para que los límites sigan siendo válidos
    if leyenda:
        ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    return fig, avisos


def ajustes_union(e: Ensayo, x: str, y: str, intercambiar: bool, stages, eje: str = "y"):
    """
    Calcula desplazamientos para que el inicio de cada stage quede donde
    terminó el anterior, sobre el eje indicado ('x' o 'y', en el eje mostrado).
    Usa el promedio de las primeras y últimas 5 lecturas para reducir el ruido.
    Devuelve {stage: (desp_x, desp_y)}; ajustarlo a mano después es normal.
    """
    xc, yc = (y, x) if intercambiar else (x, y)
    col = yc if eje == "y" else xc
    ajustes, acumulado, fin_anterior = {}, 0.0, None
    for st in sorted(stages):
        g = e.df[e.df["stage"] == st][col].dropna()
        if g.empty:
            continue
        inicio = g.iloc[:5].mean()
        fin = g.iloc[-5:].mean()
        if fin_anterior is not None:
            acumulado = fin_anterior - inicio
        ajustes[int(st)] = (acumulado if eje == "x" else 0.0,
                            acumulado if eje == "y" else 0.0)
        fin_anterior = fin + acumulado
    return ajustes

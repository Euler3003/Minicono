# Minicono - Visualizador de ensayos GDS

Aplicación en Streamlit para leer archivos `.gds` (triaxial) y graficar cualquier par de variables.

## Funciones

- Ejes X e Y elegibles, con opción de intercambiarlos.
- Escala lineal, logarítmica o symlog en cada eje.
- Selección de stages.
- Modo **conjunto** (tiempo absoluto) o **superpuesto** (cada stage desde t = 0, con separación vertical opcional).
- Mediana móvil opcional para quitar picos.
- Validación estricta: una coma decimal sin comillas se reporta como error, no se interpreta mal.

## Ejecutar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Publicar en Streamlit Community Cloud

1. Entra a share.streamlit.io con tu cuenta de GitHub.
2. Elige este repositorio, rama `main` y archivo `app.py`.
3. Publica. Cada `push` al repositorio actualiza la aplicación.

## Archivos

- `gds_core.py`: lectura, validación y graficado (sin interfaz).
- `app.py`: interfaz web.

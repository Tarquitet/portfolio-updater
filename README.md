# Portfolio Updater — carpeta `portfolio-updater.py`

Descripción

- Conjunto de scripts para editar y mantener los datasets JS del portafolio desde una interfaz gráfica. Los archivos están versionados por prefijo numérico; el más alto suele ser la versión más reciente y estable.

Características principales (versión más reciente)

- Interfaz GUI basada en `ttkbootstrap` que permite abrir ficheros `.js`, explorar datasets, editar items, añadir/eliminar elementos y guardar cambios.
- Parser robusto para extraer arrays y objetos literales desde archivos JS, incluyendo limpieza de comentarios y manejo de constantes.
- Editor de constantes y edición de listas con autocompletado/sugerencias basadas en datos existentes.
- Previsualización de imágenes y descarga/visualización remota con `requests`.
- Auto-instalador de dependencias (`ttkbootstrap`, `Pillow`, `requests`).

Requisitos

- Python 3.8+
- Paquetes: `ttkbootstrap`, `Pillow`, `requests` (el script intenta instalarlos si faltan).

Uso

- Ejecutar la versión más reciente (ejemplo):

```bash
python dev/scripts/portfolio-updater.py/9_fixed-selected-item-not-show.py
```

Flujo típico

1. Abrir el script y usar `📂 Abrir JS` para seleccionar el archivo `cv_data.js` o similar.
2. Elegir el dataset en la pestaña `Datasets` y seleccionar un item en la lista.
3. Editar campos en el formulario: campos simples, listas (botón `Editar`) o activar/desactivar claves con toggle.
4. Guardar cambios con `💾 GUARDAR CAMBIOS`.

Evolución (detalle)

- V1: `1_image_preview_implemented.py` — Implementación inicial de previsualizado de imágenes.
- V2: `2_no-need-to-modify-manual-data-all-read-by-script.py` — Lectura automática de datos desde JS sin modificar manualmente.
- V3: `3_more_automatization.py` — Más automatizaciones en carga y guardado.
- V4..V6: Correcciones de arrays inválidos, nombres de archivo y mejoras en la UI.
- V7: `7_better-edit-config-and-unlock.py` — Mejoras en editor de constantes y desbloqueo de campos.
- V8: `8_fixed-not-recognize-all-const-properties.py` — Mejor detección de propiedades constantes.
- V9: `9_fixed-selected-item-not-show.py` — Corrección de problemas de selección y refinamiento del parser (mejor manejo de comentarios, strings y arrays).

Notas finales

- Mantén siempre una copia del JS original antes de guardar cambios.
- Para integrar con el flujo automatizado, usa `dev/manager/manager.py` que selecciona la versión más reciente automáticamente.

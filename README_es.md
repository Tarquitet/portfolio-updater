# 🗄️ Universal Portfolio DB Manager (v17)

> **Un gestor visual (CMS local) en Python para editar archivos de configuración JavaScript de forma segura y automatizada.**

Universal Portfolio DB Manager es una herramienta con interfaz gráfica para leer, visualizar, editar y reescribir objetos y arrays complejos de JS sin errores de sintaxis, gestionando recursos visuales en tiempo real.

## ✨ Características Principales (v17)

- **🧠 Parser JS Inteligente (V18):** Algoritmo de extracción que ignora strings y comentarios y convierte objetos JS a diccionarios Python de forma no destructiva.
- **⚡ Recarga Dinámica y "Sticky Settings":** Al agregar un nuevo proyecto, el sistema clona automáticamente la configuración anterior.
- **🖼️ Gestor de Imágenes Robusto:** Localiza imágenes y copia/normaliza rutas automáticamente.
- **🏷️ Sistema de Tags Dinámico:** Restringe menús a los campos necesarios y recarga herramientas en memoria.
- **🛠️ Editor CRUD Visual y Multihilo:** Agrega, elimina y reordena items sin congelar la interfaz.

---

## ⚙️ Requisitos e Instalación

- Python 3.8 o superior.

El auto-instalador descarga dependencias: `ttkbootstrap`, `Pillow`, `requests`.

Ejecución:

```bash
python 17_fixed_unnecesary_dropsowns.py
```

[![Read in English](https://img.shields.io/badge/Read%20in%20English-EN-blue?style=flat-square&logo=github)](README.md)

## Uso Rápido

1. Cargar Base de Datos: Abre la aplicación y usa "Buscar Archivo" para seleccionar tu archivo de datos (por ejemplo `js/cv_data.js`).
2. Selección de Lista: El programa detectará automáticamente los arrays disponibles; selecciona uno en el menú lateral.
3. Edición Rápida: Haz clic en cualquier proyecto para ver y editar sus campos. Presiona `Enter` para guardar cambios rápidos.
4. Nuevo Item: Usa `+ New Item` para agregar uno nuevo (hereda las configuraciones del último item seleccionado).
5. Guardar: Haz clic en "💾 Guardar JS" para escribir los cambios en el archivo original; la UI se recarga sin perder la posición.

## Changelog

- v1–v4: Interfaz inicial con previsualización y auto-descubrimiento de datos JS.
- v5–v9: Diálogos avanzados (MultiSelect, Autocomplete), manejo de constantes y correcciones de multithreading.
- v10–v12: Arreglos del motor de scroll y recarga dinámica del JS tras guardar.
- v13–v15: Sticky Settings y mayor robustez del parser.
- v16–v17: Copia robusta de imágenes y restricciones mejoradas en dropdowns.

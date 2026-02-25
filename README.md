# 🗄️ Universal Portfolio DB Manager (v17)

> **A local desktop DB manager (CMS-like) for safely editing JavaScript configuration files used as static databases.**

Universal Portfolio DB Manager is a GUI tool to read, view, edit and rewrite complex JS objects/arrays safely. It prevents syntax errors and manages visual resources in real time.

![1769443128324](images/README/1769443128324.png)

## ✨ Main Features (v17)

- **Smart JS Parser:** Extracts JS objects safely, ignoring strings and comments.
- **Sticky Settings & Dynamic Reload:** New items inherit previous settings and the UI reloads without losing selection.
- **Robust Image Manager:** Finds local images and copies them, normalizing paths and creating destination folders.
- **Dynamic Tag System:** Restricts dropdowns to necessary fields and reloads tools in memory instantly.
- **Multithreaded CRUD UI:** Add, edit, reorder, and save items without freezing the GUI.

---

## ⚙️ Requirements & Installation

- Python 3.8 or newer.

Auto-installer will install dependencies (`ttkbootstrap`, `Pillow`, `requests`) on first run.

Run:

```bash
python 17_fixed_unnecesary_dropsowns.py
```

[![Leer en Español](https://img.shields.io/badge/Leer%20en%20Espa%C3%B1ol-ES-blue?style=flat-square&logo=github)](README_es.md)

## Quick Usage

1. Load a data file via the app's "Browse File" control (for example `js/cv_data.js`).
2. Select an array from the side menu to view its items.
3. Click any item to edit fields inline. Press `Enter` to save quick edits.
4. Use `+ New Item` to add a new entry (it inherits settings from the last selected item).
5. Click **Save JS** to write changes back to the source file; the UI reloads without losing position.

## Changelog

- v1–v4: Initial UI with previews and auto-discovery of JS data.
- v5–v9: Advanced dialogs (MultiSelect/Autocomplete), constant handling, and threading fixes.
- v10–v12: Scroll-engine fixes and dynamic JS reload after save.
- v13–v15: Sticky Settings and parser hardening.
- v16–v17: Robust image copying and improved dropdown restrictions.

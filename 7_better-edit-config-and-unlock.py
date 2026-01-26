import sys
import os
import subprocess
import re
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import io
import glob
import threading 

# --- AUTO-INSTALADOR ---
def setup_dependencies():
    required_libs = {
        'ttkbootstrap': 'ttkbootstrap',
        'Pillow': 'PIL',
        'requests': 'requests'
    }
    installed = False
    for package, import_name in required_libs.items():
        try:
            __import__(import_name)
        except ImportError:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                installed = True
            except: pass
    if installed: os.execv(sys.executable, ['python'] + sys.argv)

setup_dependencies()

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from PIL import Image, ImageTk
import requests

# ============================================================
# WIDGET: AUTOCOMPLETE COMBOBOX (Buscador tipo Google)
# ============================================================
class AutocompleteCombobox(ttk.Combobox):
    def __init__(self, parent, all_options, **kwargs):
        super().__init__(parent, **kwargs)
        self._hits = []
        self._hit_index = 0
        self.position = 0
        self.all_options = sorted(list(set(all_options))) # Unique & Sorted
        self['values'] = self.all_options
        
        self.bind('<KeyRelease>', self.handle_keyrelease)
        self.bind('<<ComboboxSelected>>', self.handle_select)

    def handle_keyrelease(self, event):
        if event.keysym in ('BackSpace', 'Left', 'Right', 'Up', 'Down', 'Return', 'Tab'): return
        
        typed = self.get()
        if typed == '':
            self['values'] = self.all_options
        else:
            # Filtrar opciones que contengan el texto (case insensitive)
            self._hits = [x for x in self.all_options if typed.lower() in x.lower()]
            self['values'] = self._hits
        
        self.event_generate('<Down>') # Abrir dropdown automáticamente

    def handle_select(self, event):
        self.selection_clear()
        self.icursor('end')

# ============================================================
# WIDGET: CAMPO INTELIGENTE (Enabled/Disabled toggle)
# ============================================================
class SmartField(ttk.Frame):
    def __init__(self, parent, key, value, schema_suggestions, is_enabled, on_change_callback):
        super().__init__(parent)
        self.key = key
        self.enabled = tk.BooleanVar(value=is_enabled)
        self.callback = on_change_callback
        
        # Checkbox/Botón de estado
        self.btn_toggle = ttk.Checkbutton(
            self, 
            text=key.upper(), 
            variable=self.enabled, 
            bootstyle="round-toggle",
            command=self.toggle_state
        )
        self.btn_toggle.pack(side="left", padx=(0, 10))
        
        # Contenedor del input
        self.input_frame = ttk.Frame(self)
        self.input_frame.pack(side="left", fill="x", expand=True)
        
        self.widget = None
        self.suggestions = schema_suggestions

        # Decidir tipo de widget
        if isinstance(value, list) or key in ['tools', 'tags', 'skills']:
            self.type = 'list'
            self.current_val = value if isinstance(value, list) else []
            
            self.lbl_preview = ttk.Label(self.input_frame, text=", ".join(self.current_val), font=("Consolas", 8), foreground="#888")
            self.lbl_preview.pack(side="left", fill="x", expand=True)
            
            self.btn_edit = ttk.Button(self.input_frame, text="Editar Lista", command=self.open_list_editor, bootstyle="outline", width=12)
            self.btn_edit.pack(side="right")
            
        else:
            self.type = 'text'
            # Usar Autocomplete si hay sugerencias
            if self.suggestions:
                self.widget = AutocompleteCombobox(self.input_frame, all_options=self.suggestions)
                self.widget.set(str(value))
            else:
                self.widget = ttk.Entry(self.input_frame)
                self.widget.insert(0, str(value))
            
            self.widget.pack(fill="x", expand=True)
            # Bind para auto-guardar o detectar cambios si se desea
        
        self.update_visual_state()

    def toggle_state(self):
        self.update_visual_state()
        if self.callback: self.callback()

    def update_visual_state(self):
        state = "normal" if self.enabled.get() else "disabled"
        if self.type == 'text':
            self.widget.configure(state=state)
        else:
            self.btn_edit.configure(state=state)
            if not self.enabled.get(): self.lbl_preview.configure(foreground="#333")
            else: self.lbl_preview.configure(foreground="#ccc")

    def get_value(self):
        if not self.enabled.get(): return None # Señal para borrar la key
        if self.type == 'text': return self.widget.get().strip()
        return self.current_val

    def open_list_editor(self):
        # Lógica simplificada de llamada al editor de listas
        # Recolectamos todas las opciones posibles de las sugerencias
        all_opts = self.suggestions
        
        def on_save(new_list):
            self.current_val = new_list
            self.lbl_preview.config(text=", ".join(new_list))
            if self.callback: self.callback()

        ListEditorDialog(self.winfo_toplevel(), f"Editar {self.key}", self.current_val, all_opts, on_save)

# ============================================================
# DIÁLOGOS AUXILIARES
# ============================================================
class ListEditorDialog(ttk.Toplevel):
    def __init__(self, parent, title, current_list, all_options, callback):
        super().__init__(parent)
        self.title(title)
        self.geometry("450x600")
        self.callback = callback
        
        clean_options = set()
        for opt in all_options + current_list:
            clean = opt.replace("'", "").replace('"', "").strip()
            if clean: clean_options.add(clean)
        self.all_options = sorted(list(clean_options))
        self.vars = {}

        ttk.Label(self, text="Selección Múltiple:", font=("Arial", 10, "bold")).pack(pady=10)

        frame_canvas = ttk.Frame(self)
        frame_canvas.pack(fill="both", expand=True, padx=10)
        canvas = tk.Canvas(frame_canvas, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame_canvas, orient="vertical", command=canvas.yview)
        self.scroll_inner = ttk.Frame(canvas)
        self.scroll_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Permitir scroll con rueda
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        for opt in self.all_options:
            var = tk.BooleanVar(value=opt in [x.replace("'","").replace('"',"") for x in current_list])
            self.vars[opt] = var
            ttk.Checkbutton(self.scroll_inner, text=opt, variable=var).pack(anchor="w", pady=2)

        # Add New
        add_frame = ttk.Frame(self, padding=10)
        add_frame.pack(fill="x")
        self.entry_new = ttk.Entry(add_frame)
        self.entry_new.pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(add_frame, text="Añadir", command=self.add_new).pack(side="right")

        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill="x", side="bottom")
        ttk.Button(btn_frame, text="Guardar", command=self.save, bootstyle="success").pack(fill="x")

    def add_new(self):
        val = self.entry_new.get().strip()
        if val: 
            var = tk.BooleanVar(value=True)
            self.vars[val] = var
            ttk.Checkbutton(self.scroll_inner, text=val, variable=var).pack(anchor="w", pady=2)
            self.entry_new.delete(0, tk.END)

    def save(self):
        self.callback([k for k, v in self.vars.items() if v.get()])
        self.destroy()

class ConstantsEditor(ttk.Toplevel):
    def __init__(self, parent, constants_data, callback):
        super().__init__(parent)
        self.title("Editor de Constantes")
        self.geometry("600x500")
        self.data = constants_data # Dict { "CTX": {"PROF": "PROFESSIONAL"}, ... }
        self.callback = callback
        
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.entries = {} # { "CTX": { "PROF": EntryWidget } }

        for group_name, values in self.data.items():
            frame = ttk.Frame(self.nb, padding=10)
            self.nb.add(frame, text=group_name)
            
            # Scrollable frame for constants
            canvas = tk.Canvas(frame)
            sb = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
            inner = ttk.Frame(canvas)
            
            inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0,0), window=inner, anchor="nw")
            canvas.configure(yscrollcommand=sb.set)
            
            canvas.pack(side="left", fill="both", expand=True)
            sb.pack(side="right", fill="y")
            
            self.entries[group_name] = {}
            self.render_group(group_name, values, inner)
            
            # Add Button
            btn_add = ttk.Button(inner, text="➕ Nueva Clave", command=lambda g=group_name, i=inner: self.add_field(g, i))
            btn_add.pack(pady=10)

        ttk.Button(self, text="GUARDAR CAMBIOS", command=self.save, bootstyle="success").pack(fill="x", padx=10, pady=10)

    def render_group(self, group, values, container):
        for k, v in values.items():
            self.add_row(group, container, k, v)

    def add_row(self, group, container, k="", v=""):
        row = ttk.Frame(container)
        row.pack(fill="x", pady=2)
        
        k_ent = ttk.Entry(row, width=15)
        k_ent.insert(0, k)
        k_ent.pack(side="left", padx=2)
        
        ttk.Label(row, text=":").pack(side="left")
        
        v_ent = ttk.Entry(row)
        v_ent.insert(0, v)
        v_ent.pack(side="left", fill="x", expand=True, padx=2)
        
        # Referencia para guardar después
        # Guardamos tuplas de widgets (KeyWidget, ValueWidget)
        if group not in self.entries: self.entries[group] = []
        self.entries[group].append((k_ent, v_ent))

    def add_field(self, group, container):
        self.add_row(group, container)

    def save(self):
        new_data = {}
        for group, widget_list in self.entries.items():
            new_data[group] = {}
            for k_w, v_w in widget_list:
                k = k_w.get().strip()
                v = v_w.get().strip()
                if k: new_data[group][k] = v
        self.callback(new_data)
        self.destroy()

# ============================================================
# MAIN APP (V11)
# ============================================================
class UniversalDBManagerV11:
    def __init__(self, root):
        self.root = root
        self.root.title("Tarquitet - Universal Manager V11 (Intelligent Edition)")
        self.root.geometry("1400x900")
        
        self.filepath = ""
        self.file_content = ""
        self.datasets = {}
        self.dataset_schemas = {}
        self.constants = {} # { "CAT": {...}, "CTX": {...} }
        
        self.current_key = None 
        self.selected_index = None
        self.smart_fields = {} # Referencias a los widgets SmartField
        
        self.image_cache = {}
        self.loading_thread = None
        self.discovered_paths = []

        self.build_ui()
        self.smart_auto_load()

    def build_ui(self):
        main = ttk.Frame(self.root, padding=15)
        main.pack(fill="both", expand=True)

        # --- HEADER ---
        head = ttk.Frame(main)
        head.pack(fill="x", pady=(0,10))
        ttk.Label(head, text="UNIVERSAL DATA V11", font=("Helvetica", 16, "bold"), bootstyle="primary").pack(side="left")
        
        h_right = ttk.Frame(head)
        h_right.pack(side="right")
        ttk.Button(h_right, text="⚙️ CONSTANTES", command=self.open_constants_editor, bootstyle="secondary-outline").pack(side="left", padx=5)
        ttk.Button(h_right, text="📂 Abrir JS", command=self.browse_file).pack(side="left", padx=5)
        self.lbl_status = ttk.Label(h_right, text="-", font=("Consolas", 9), foreground="gray")
        self.lbl_status.pack(side="left")

        # --- BODY ---
        paned = ttk.PanedWindow(main, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # LEFT
        left = ttk.Frame(paned, padding=(0,0,10,0))
        paned.add(left, weight=1)

        self.tabs_frame = ttk.Labelframe(left, text="Datasets", padding=5)
        self.tabs_frame.pack(fill="x", pady=(0,5))

        lst_frame = ttk.Frame(left)
        lst_frame.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(lst_frame)
        scroll.pack(side="right", fill="y")
        self.listbox = tk.Listbox(lst_frame, font=("Consolas", 10), borderwidth=0, selectmode="SINGLE")
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.config(yscrollcommand=scroll.set)
        scroll.config(command=self.listbox.yview)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        btns = ttk.Frame(left, padding=(0,10,0,0))
        btns.pack(fill="x")
        ttk.Button(btns, text="➕ NUEVO", command=self.add_item, bootstyle="success").pack(side="left", fill="x", expand=True)
        ttk.Button(btns, text="🗑️ BORRAR", command=self.delete_item, bootstyle="danger").pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(btns, text="▲", width=3, command=lambda: self.move(-1)).pack(side="left")
        ttk.Button(btns, text="▼", width=3, command=lambda: self.move(1)).pack(side="left", padx=2)

        # RIGHT
        right = ttk.Frame(paned, padding=(10,0,0,0))
        paned.add(right, weight=3)

        # Preview Image
        self.prev_frame = ttk.Labelframe(right, text="Vista Previa", padding=10, height=200)
        self.prev_frame.pack(fill="x", pady=(0,10))
        self.prev_frame.pack_propagate(False)
        self.lbl_img = ttk.Label(self.prev_frame, text="Selecciona un item", anchor="center")
        self.lbl_img.pack(fill="both", expand=True)
        self.lbl_img_info = ttk.Label(self.prev_frame, text="", font=("Arial", 7), foreground="gray")
        self.lbl_img_info.pack(side="bottom", anchor="e")

        # Scrollable Form
        self.canvas = tk.Canvas(right, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(right, orient="vertical", command=self.canvas.yview)
        self.form_frame = ttk.Frame(self.canvas)
        
        self.form_win = self.canvas.create_window((0,0), window=self.form_frame, anchor="nw")
        self.form_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.form_win, width=e.width))
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Mousewheel binding
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Actions
        acts = ttk.Frame(right, padding=(0,10,0,0))
        acts.pack(fill="x", side="bottom")
        ttk.Button(acts, text="✔ APLICAR (Memoria)", command=self.save_memory, bootstyle="warning").pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(acts, text="💾 GUARDAR ARCHIVO", command=self.save_file, bootstyle="success").pack(side="left", fill="x", expand=True)

    # ============================================================
    # PARSING & LOADING
    # ============================================================
    def smart_auto_load(self):
        candidates = glob.glob("*.js") + glob.glob("*/*.js") + glob.glob("../js/*.js")
        target = None
        for p in candidates:
            if "min.js" in p and "opti" not in p: continue
            if "utils" in p or "config" in p: continue
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    c = f.read()
                    if "mainPortfolio" in c or "galleryData" in c:
                        target = p; break
            except: pass
        if target: self.load_file(os.path.abspath(target))

    def browse_file(self):
        f = filedialog.askopenfilename(filetypes=[("JS", "*.js")])
        if f: self.load_file(f)

    def load_file(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.file_content = f.read()
            self.filepath = path
            self.lbl_status.config(text=os.path.basename(path), bootstyle="success")
            self.discover_paths(self.file_content, path)
            self.parse_constants() # Parsear const X = {...}
            self.parse_data()
            self.build_tabs()
            self.image_cache = {}
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def parse_constants(self):
        # Regex para bloques const X = { ... }
        regex = r"const\s+(\w+)\s*=\s*\{(.*?)\};"
        matches = re.finditer(regex, self.file_content, re.DOTALL)
        self.constants = {}
        
        for m in matches:
            name = m.group(1)
            content = m.group(2)
            # Parsear clave: valor dentro del bloque
            # Soporta 'KEY': 'VAL', KEY: 'VAL', KEY: "VAL"
            props = re.findall(r"(\w+):\s*(?:'([^']*)'|\"([^\"]*)\")", content)
            const_dict = {}
            for k, v1, v2 in props:
                const_dict[k] = v1 or v2
            if const_dict:
                self.constants[name] = const_dict
        print("Constantes detectadas:", self.constants.keys())

    def parse_data(self):
        self.datasets = {}
        self.dataset_schemas = {}
        regex = r"(?:const\s+|let\s+|var\s+|window\.)\s*(\w+)\s*=\s*\[(.*?)\];"
        matches = re.finditer(regex, self.file_content, re.DOTALL)
        for m in matches:
            name = m.group(1)
            # Fix URLs: no borrar https://
            raw = re.sub(r"(?<!:)\/\/.*", "", m.group(2))
            if "{" in raw:
                data = self.parse_array_body(raw)
                if data:
                    self.datasets[name] = data
                    # Esquema completo (todas las keys posibles en este array)
                    all_keys = set()
                    for item in data: all_keys.update(item.keys())
                    self.dataset_schemas[name] = list(all_keys)

    def parse_array_body(self, content):
        items = content.split('},')
        res = []
        for item in items:
            if not item.strip(): continue
            clean = item.replace('{', '').replace('}', '').strip()
            obj = {}
            # Regex poderoso: Clave: 'Valor' | "Valor" | Constante.Propiedad | Constante
            props = re.findall(r"(\w+):\s*(?:'([^']*)'|\"([^\"]*)\"|([a-zA-Z0-9_.]+))", clean)
            for k, v1, v2, v3 in props:
                obj[k] = v1 or v2 or v3
            
            arrays = re.findall(r"(\w+):\s*\[(.*?)\]", clean)
            for k, v in arrays:
                elems = [x.strip().replace("'", "").replace('"', "") for x in v.split(',')]
                obj[k] = [e for e in elems if e]
            
            if obj: res.append(obj)
        return res

    # ============================================================
    # FORMULARIO INTELIGENTE
    # ============================================================
    def build_tabs(self):
        for w in self.tabs_frame.winfo_children(): w.destroy()
        keys = list(self.datasets.keys())
        if not keys: return
        self.var_tab = tk.StringVar(value=keys[0])
        for k in keys:
            ttk.Radiobutton(self.tabs_frame, text=k, variable=self.var_tab, value=k, 
                           command=self.load_list, bootstyle="toolbutton-outline").pack(side="left", fill="x", expand=True, padx=2)
        self.load_list()

    def load_list(self):
        self.current_key = self.var_tab.get()
        self.listbox.delete(0, tk.END)
        data = self.datasets.get(self.current_key, [])
        for i, item in enumerate(data):
            title = item.get('title') or item.get('fileName') or f"Item {i}"
            cat = item.get('category', '?').replace("CAT.", "")
            self.listbox.insert(tk.END, f"[{cat}] {title}")
        for w in self.form_frame.winfo_children(): w.destroy()
        self.lbl_img.config(image='', text="Selecciona un item")

    def on_select(self, e):
        sel = self.listbox.curselection()
        if not sel: return
        self.selected_index = sel[0]
        item = self.datasets[self.current_key][self.selected_index]
        self.build_form(item)
        self.load_image(item)

    def get_suggestions_for_field(self, field_name):
        """Genera lista de opciones para el Autocomplete"""
        options = set()
        
        # 1. Valores existentes en el dataset actual
        for item in self.datasets.get(self.current_key, []):
            val = item.get(field_name)
            if isinstance(val, str): options.add(val)
            elif isinstance(val, list): options.update(val)
            
        # 2. Constantes relacionadas
        # Mapeo inteligente: si el campo es 'category', buscar en self.constants['CAT']
        mapping = {'category': 'CAT', 'context': 'CTX', 'tools': 'T'}
        const_group = mapping.get(field_name)
        if const_group and const_group in self.constants:
            # Agregar tanto "CAT.DEV" como el valor real "DEV"
            for k in self.constants[const_group].keys():
                options.add(f"{const_group}.{k}")
        
        return sorted(list(options))

    def build_form(self, item):
        for w in self.form_frame.winfo_children(): w.destroy()
        self.smart_fields = {}
        
        # Obtener TODOS los campos posibles (Esquema)
        schema_keys = self.dataset_schemas.get(self.current_key, [])
        prio = ['title', 'category', 'context', 'fileName', 'date', 'link', 'desc']
        sorted_keys = sorted(schema_keys, key=lambda x: prio.index(x) if x in prio else 99)
        
        for k in sorted_keys:
            # Determinar si el item tiene este campo
            has_field = k in item
            val = item.get(k, []) if k in ['tools', 'tags'] and k not in item else item.get(k, "")
            
            # Obtener sugerencias para autocomplete
            suggestions = self.get_suggestions_for_field(k)
            
            # Crear Widget Inteligente
            field = SmartField(
                self.form_frame, 
                key=k, 
                value=val, 
                schema_suggestions=suggestions,
                is_enabled=has_field,
                on_change_callback=None
            )
            field.pack(fill="x", pady=2)
            self.smart_fields[k] = field

    # ============================================================
    # CONSTANTS EDITOR
    # ============================================================
    def open_constants_editor(self):
        if not self.constants:
            messagebox.showinfo("Info", "No se detectaron constantes (const X = {}) en el archivo.")
            return
        
        def on_save_consts(new_data):
            self.constants = new_data
            self.save_file() # Guardar cambios en disco inmediatamente
            self.build_form(self.datasets[self.current_key][self.selected_index]) # Refrescar form para ver nuevas opciones

        ConstantsEditor(self.root, self.constants, on_save_consts)

    # ============================================================
    # IMÁGENES (THREADED)
    # ============================================================
    def discover_paths(self, content, js_path):
        base = os.path.dirname(js_path)
        self.discovered_paths = [os.path.join(base, "../assets/images")]
        match = re.search(r"paths:\s*\{(.*?)\}", content, re.DOTALL)
        if match:
            raw = re.findall(r"['\"](.*?)['\"]", match.group(1))
            for p in raw:
                if len(p) > 2: self.discovered_paths.append(os.path.normpath(os.path.join(base, p)))
        final = []
        for p in self.discovered_paths:
            final.append(p)
            if os.path.exists(p):
                try: final.extend([os.path.join(p, d) for d in os.listdir(p) if os.path.isdir(os.path.join(p,d))])
                except: pass
        self.discovered_paths = list(set(final))

    def load_image(self, item):
        fname = item.get('fileName') or item.get('image')
        if not fname: 
            self.show_img(None, "Sin archivo")
            return
        self.lbl_img.config(image='', text="⌛ Cargando...")
        threading.Thread(target=self._load_img_thread, args=(fname,), daemon=True).start()

    def _load_img_thread(self, fname):
        path = None
        mode = "FILE"
        if fname.startswith("http"):
            path = fname
            mode = "URL"
        else:
            clean = fname.replace("../", "").replace("./", "")
            if clean.startswith(("CAT.", "CTX.")): 
                self.root.after(0, lambda: self.show_img(None, f"Referencia: {fname}"))
                return
            for folder in self.discovered_paths:
                if not os.path.exists(folder): continue
                for ext in ['', '.avif', '.webp', '.png', '.jpg']:
                    f = os.path.join(folder, clean + ext)
                    if os.path.exists(f): path = f; break
                if path: break
        
        if not path:
            self.root.after(0, lambda: self.show_img(None, f"No encontrado: {fname}"))
            return

        if path in self.image_cache:
            self.root.after(0, lambda: self.show_img(self.image_cache[path], path))
            return

        try:
            if mode == "URL":
                r = requests.get(path, timeout=3)
                pil = Image.open(io.BytesIO(r.content))
            else:
                pil = Image.open(path)
            
            aspect = 200 / float(pil.size[1])
            w = int(float(pil.size[0]) * aspect)
            pil = pil.resize((w, 200), Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(pil)
            self.image_cache[path] = tk_img
            self.root.after(0, lambda: self.show_img(tk_img, path))
        except:
            self.root.after(0, lambda: self.show_img(None, "Error formato"))

    def show_img(self, tk_img, text):
        if tk_img:
            self.lbl_img.config(image=tk_img, text="")
            self.lbl_img.image = tk_img
            self.lbl_img_info.config(text=text[-40:])
        else:
            self.lbl_img.config(image='', text=text)
            self.lbl_img_info.config(text="")

    # ============================================================
    # SAVING
    # ============================================================
    def add_item(self):
        if not self.current_key: return
        # Item vacío, el form mostrará los campos deshabilitados por defecto (o habilitados según prefieras)
        # Aquí forzamos habilitar titulo y categoría
        new_item = {'title': 'NUEVO ITEM', 'category': 'CAT.DEV'}
        self.datasets[self.current_key].insert(0, new_item)
        self.load_list()
        self.listbox.select_set(0)
        self.on_select(None)

    def delete_item(self):
        if self.selected_index is None: return
        del self.datasets[self.current_key][self.selected_index]
        self.selected_index = None
        self.load_list()

    def move(self, d):
        if self.selected_index is None: return
        i = self.selected_index
        n = i + d
        l = self.datasets[self.current_key]
        if 0 <= n < len(l):
            l[i], l[n] = l[n], l[i]
            self.load_list()
            self.listbox.select_set(n)
            self.selected_index = n

    def save_memory(self):
        if self.selected_index is None: return
        item = {}
        for k, field_obj in self.smart_fields.items():
            val = field_obj.get_value()
            if val is not None: # Si es None, estaba deshabilitado -> No guardar
                item[k] = val
        
        self.datasets[self.current_key][self.selected_index] = item
        # Actualizar esquema si apareció campo nuevo
        self.dataset_schemas[self.current_key] = list(set(self.dataset_schemas[self.current_key] + list(item.keys())))
        self.load_list()
        self.listbox.select_set(self.selected_index)

    def save_file(self):
        if not self.filepath: return
        shutil.copy(self.filepath, self.filepath + ".bak")
        content = self.file_content
        
        # 1. Guardar Arrays
        for name, data in self.datasets.items():
            js_str = self.py_to_js(data)
            regex = r"((?:const\s+|let\s+|var\s+|window\.)\s*" + name + r"\s*=\s*\[).*?(\];)"
            content = re.sub(regex, f"\\1\n{js_str}\\2", content, flags=re.DOTALL)
            
        # 2. Guardar Constantes
        for const_name, values in self.constants.items():
            # Reconstruir string JS: const CTX = { K: 'V', ... };
            lines = []
            for k, v in values.items():
                lines.append(f"    {k}: '{v}',")
            block_str = f"const {const_name} = {{\n" + "\n".join(lines) + "\n};"
            
            regex_const = r"const\s+" + const_name + r"\s*=\s*\{(.*?)\};"
            content = re.sub(regex_const, block_str, content, flags=re.DOTALL)

        try:
            with open(self.filepath, 'w', encoding='utf-8') as f: f.write(content)
            self.file_content = content
            messagebox.showinfo("Guardado", "Archivo actualizado exitosamente.")
        except Exception as e: messagebox.showerror("Error", str(e))

    def py_to_js(self, data):
        lines = []
        consts = tuple(self.constants.keys()) # ("CAT", "CTX", "T")
        # Agregar prefijos comunes para detección
        prefixes = tuple([f"{c}." for c in consts] + ["PROJECT_CONFIG"])
        
        for item in data:
            lines.append("  {")
            for k, v in item.items():
                if isinstance(v, list):
                    els = []
                    for x in v:
                        if x.startswith(prefixes): els.append(x)
                        else: els.append(f"'{x.replace("'", "\\'")}'")
                    lines.append(f"    {k}: [{', '.join(els)}],")
                else:
                    s = str(v).strip()
                    if s.startswith(prefixes): lines.append(f"    {k}: {s},")
                    else: lines.append(f"    {k}: '{s.replace("'", "\\'")}',")
            lines.append("  },")
        return "\n".join(lines)

if __name__ == "__main__":
    app_window = ttk.Window(themename="superhero")
    app = UniversalDBManagerV11(app_window)
    app_window.mainloop()
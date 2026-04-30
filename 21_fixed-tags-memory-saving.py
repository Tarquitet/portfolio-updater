"""
Universal Manager V24 - Modo RAM Seguro (Memory-First)
- Arquitectura adaptada para no interferir con File Watchers externos (manager.py).
- TODOS los cambios ocurren en RAM.
- El archivo solo se escribe al presionar "GUARDAR ARCHIVO" o al confirmar al salir.
- Advertencia de cierre si hay cambios sin guardar.
"""
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
import time

def setup_dependencies():
    required_libs = {'ttkbootstrap': 'ttkbootstrap', 'Pillow': 'PIL', 'requests': 'requests'}
    installed = False
    for package, import_name in required_libs.items():
        try:
            __import__(import_name)
        except ImportError:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                installed = True
            except:
                pass
    if installed:
        os.execv(sys.executable, ['python'] + sys.argv)
setup_dependencies()

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from PIL import Image, ImageTk
import requests

# --- COMPONENTES UI ---
class AutocompleteCombobox(ttk.Combobox):
    def __init__(self, parent, all_options, **kwargs):
        super().__init__(parent, **kwargs)
        self._hits = []
        self.all_options = sorted(list(set(all_options)))
        self['values'] = self.all_options
        self.bind('<KeyRelease>', self.handle_keyrelease)
    def handle_keyrelease(self, event):
        if event.keysym in ('BackSpace','Left','Right','Up','Down','Return','Tab'): return
        typed = self.get()
        if typed == '': self['values'] = self.all_options
        else:
            self._hits = [x for x in self.all_options if typed.lower() in x.lower()]
            self['values'] = self._hits
        self.event_generate('<Down>')

class ListEditorDialog(ttk.Toplevel):
    """Ventana para asignar tags/tools a un proyecto específico."""
    def __init__(self, parent, title, current_list, all_options, callback):
        super().__init__(parent)
        self.title(f"Editor: {title}")
        self.geometry("450x600")
        self.callback = callback
        
        safe_current = [str(x).replace("'","").replace('"',"").strip() for x in current_list if x]
        safe_opts = [str(x).replace("'","").replace('"',"").strip() for x in all_options if x]
        self.all_options = sorted(list(set(safe_opts + safe_current)))
        self.vars = {}
        
        ttk.Label(self, text=f"Asignar {title} al Proyecto", font=("Arial", 10, "bold")).pack(pady=10)
        
        bottom_frame = ttk.Frame(self, padding=10)
        bottom_frame.pack(side="bottom", fill="x")
        input_frame = ttk.Frame(bottom_frame)
        input_frame.pack(fill="x", pady=(0, 10))
        
        self.en = ttk.Entry(input_frame)
        self.en.pack(side="left", fill="x", expand=True, padx=5)
        self.en.bind("<Return>", lambda e: self.add_manual())
        
        ttk.Button(input_frame, text="Añadir", command=self.add_manual, bootstyle="info-outline").pack(side="right")
        
        # Botón para confirmar en MEMORIA
        ttk.Button(bottom_frame, text="APLICAR A ESTE PROYECTO", command=self.save, bootstyle="success").pack(fill="x")
        
        container = ttk.Frame(self)
        container.pack(side="top", fill="both", expand=True, padx=10)
        c = tk.Canvas(container, highlightthickness=0)
        sb = ttk.Scrollbar(container, orient="vertical", command=c.yview)
        self.f = ttk.Frame(c)
        self.f.bind("<Configure>", lambda e: c.configure(scrollregion=c.bbox("all")))
        c.create_window((0,0), window=self.f, anchor="nw")
        c.configure(yscrollcommand=sb.set)
        c.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        c.bind("<MouseWheel>", lambda e: c.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        for opt in self.all_options: 
            self.add_checkbox(opt, opt in safe_current)

    def add_checkbox(self, text, checked=False):
        if text in self.vars: return
        v = tk.BooleanVar(value=checked)
        self.vars[text] = v
        ttk.Checkbutton(self.f, text=text, variable=v).pack(anchor="w", pady=2)

    def add_manual(self):
        val = self.en.get().strip()
        if val:
            self.add_checkbox(val, checked=True)
            self.en.delete(0, tk.END)
            self.f.update_idletasks()

    def save(self):
        if self.en.get().strip(): self.vars[self.en.get().strip()] = tk.BooleanVar(value=True)
        self.callback([k for k,v in self.vars.items() if v.get()])
        self.destroy()

class PathChooserDialog(ttk.Toplevel):
    def __init__(self, parent, paths, filename, callback):
        super().__init__(parent)
        self.title("Destino de Imagen")
        self.geometry("600x450")
        self.callback = callback
        ttk.Label(self, text="⚠️ Imagen Externa Detectada", bootstyle="warning", font=("Arial", 12, "bold")).pack(pady=(15,5))
        ttk.Label(self, text=f"El archivo '{filename}' no está en el proyecto.", justify="center").pack()
        lb_frame = ttk.Frame(self, padding=10); lb_frame.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(lb_frame); sb.pack(side="right", fill="y")
        self.lb = tk.Listbox(lb_frame, font=("Consolas", 10))
        self.lb.pack(side="left", fill="both", expand=True)
        self.lb.config(yscrollcommand=sb.set); sb.config(command=self.lb.yview)
        unique_paths = sorted(list(set(paths)))
        for p in unique_paths: self.lb.insert(tk.END, p)
        btn_frame = ttk.Frame(self, padding=20); btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="CANCELAR", command=self.destroy, bootstyle="secondary").pack(side="left", expand=True)
        ttk.Button(btn_frame, text="COPIAR AQUÍ", command=self.confirm, bootstyle="success").pack(side="left", expand=True, padx=10)

    def confirm(self):
        sel = self.lb.curselection()
        if not sel: return
        self.callback(self.lb.get(sel[0]))
        self.destroy()

class ConstantsEditor(ttk.Toplevel):
    """Ventana para editar TODAS las variables globales (Tools, Categorías)"""
    def __init__(self, parent, constants_data, callback):
        super().__init__(parent)
        self.title("Editor Global de Variables (Memoria)")
        self.geometry("700x600")
        
        self.valid_groups = ['CTX', 'CAT', 'T']
        self.data = {k: v for k, v in constants_data.items() if k in self.valid_groups}
        self.callback = callback
        self.entries = {}
        
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)
        
        for grp, vals in self.data.items():
            f = ttk.Frame(nb, padding=10); nb.add(f, text=grp)
            c = tk.Canvas(f); sb = ttk.Scrollbar(f, orient="vertical", command=c.yview)
            inn = ttk.Frame(c); inn.bind("<Configure>", lambda e: c.configure(scrollregion=c.bbox("all")))
            c.create_window((0,0), window=inn, anchor="nw"); c.configure(yscrollcommand=sb.set)
            c.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
            c.bind("<MouseWheel>", lambda e, canvas=c: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
            self.entries[grp] = []
            for k,v in vals.items(): self.add_row(grp, inn, k, v)
            ttk.Button(inn, text="➕ Añadir Fila", command=lambda g=grp, i=inn: self.add_row(g,i)).pack(pady=10)
            
        ttk.Button(self, text="✔️ GUARDAR EN MEMORIA (No escribe en disco aún)", command=self.save, bootstyle="success").pack(fill="x", padx=10, pady=10)

    def add_row(self, grp, cont, k="", v=""):
        r = ttk.Frame(cont); r.pack(fill="x", pady=2)
        ke = ttk.Entry(r, width=15); ke.insert(0, k); ke.pack(side="left")
        ttk.Label(r, text=":").pack(side="left", padx=5)
        ve = ttk.Entry(r); ve.insert(0, v); ve.pack(side="left", fill="x", expand=True)
        # Bóton para Eliminar
        btn_del = ttk.Button(r, text="🗑️", bootstyle="danger", command=lambda frm=r, g=grp, key_ent=ke: self.del_row(frm, g, key_ent))
        btn_del.pack(side="right", padx=5)
        self.entries[grp].append((ke, ve, r))

    def del_row(self, frame, grp, key_entry):
        frame.destroy()
        self.entries[grp] = [item for item in self.entries[grp] if item[0] != key_entry]

    def save(self):
        new_d = {}
        for g, rows in self.entries.items():
            new_d[g] = {}
            for ke, ve, _ in rows:
                if ke.get().strip(): new_d[g][ke.get().strip()] = ve.get().strip()
        self.callback(new_d)
        self.destroy()

# --- PARSER JS ---
class JSParser:
    @staticmethod
    def remove_comments(text):
        def replacer(match):
            s = match.group(0)
            if s.startswith('/'): return " "
            else: return s
        pattern = re.compile(r'//[^\n]*|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|\"(?:\\.|[^\\\"])*\"', re.DOTALL | re.MULTILINE)
        return re.sub(pattern, replacer, text)

    @staticmethod
    def extract_objects(content):
        content = JSParser.remove_comments(content)
        objects = {}
        regex_start = re.compile(r"(?:const|let|var|window\.)\s*(\w+)\s*=\s*([\[\{])", re.DOTALL)
        for match in regex_start.finditer(content):
            var_name = match.group(1); start_char = match.group(2); start_idx = match.start(2)
            balance = 0; end_idx = -1; in_string = False; string_char = ''
            for i in range(start_idx, len(content)):
                char = content[i]
                if char in ["'", '"', "`"] and (i==0 or content[i-1] != "\\"):
                    if not in_string: in_string = True; string_char = char
                    elif char == string_char: in_string = False
                if not in_string:
                    if char == start_char: balance += 1
                    elif char == (']' if start_char == '[' else '}'):
                        balance -= 1; 
                        if balance == 0: end_idx = i + 1; break
            if end_idx != -1: objects[var_name] = content[start_idx:end_idx]
        return objects

    @staticmethod
    def parse_kv_inside_object(raw_content):
        data = {}
        regex_prop = re.compile(r"(\w+|\[.*?\])\s*:\s*(?:'([^']*)'|\"([^\"]*)\")", re.DOTALL)
        for m in regex_prop.finditer(raw_content):
            key = m.group(1); val = m.group(2) or m.group(3)
            data[key] = val
        return data

    @staticmethod
    def parse_array_of_objects(raw_array):
        inner = raw_array.strip()
        if inner.startswith("["): inner = inner[1:]
        if inner.endswith("]"): inner = inner[:-1]
        if not inner.strip(): return []
        raw_objs = re.split(r"\}\s*,\s*\{", inner)
        items = []
        for raw in raw_objs:
            clean = raw.strip()
            if not clean.startswith("{"): clean = "{" + clean
            if not clean.endswith("}"): clean = clean + "}"
            obj_data = JSParser.parse_kv_inside_object(clean)
            
            regex_arrays = re.compile(r"(\w+)\s*:\s*\[(.*?)\]", re.DOTALL)
            for m in regex_arrays.finditer(clean):
                k = m.group(1); v_raw = m.group(2)
                elems = [x.strip().replace("'", "").replace('"', '') for x in v_raw.split(',') if x.strip()]
                obj_data[k] = elems
            
            masked_clean = re.sub(r"('(?:\.|[^'])*'|\"(?:\.|[^\"])*\")", "''", clean)
            regex_const = re.compile(r"(\w+)\s*:\s*(?!['\"\[])([a-zA-Z0-9_.]+)(?!['\"\]])", re.DOTALL)
            for m in regex_const.finditer(masked_clean):
                k = m.group(1); v = m.group(2)
                if k not in obj_data: obj_data[k] = v
            items.append(obj_data)
        return items

# --- MANAGER PRINCIPAL ---
class UniversalDBManagerV24:
    def __init__(self, root):
        self.root = root
        self.base_title = "Tarquitet - DB Editor"
        self.root.geometry("1400x900")
        
        # Interceptar el cierre de ventana
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.has_unsaved_changes = False
        self.file_content = ""
        self.filepath = ""
        
        self.datasets = {}
        self.constants = {}
        self.schemas = {}
        
        self.image_search_paths = []
        self.current_key = None
        self.selected_index = None
        self.form_widgets = {}
        self.image_cache = {}
        
        self.build_ui()
        self.update_title()
        self.smart_load()

    def mark_unsaved(self):
        """Activa la bandera de cambios y pone un asterisco en el título"""
        self.has_unsaved_changes = True
        self.update_title()

    def mark_saved(self):
        """Limpia la bandera tras guardar físicamente"""
        self.has_unsaved_changes = False
        self.update_title()

    def update_title(self):
        star = "*" if self.has_unsaved_changes else ""
        self.root.title(f"{self.base_title} {star}")

    def on_closing(self):
        """Previene accidentes preguntando si hay cambios pendientes."""
        if self.has_unsaved_changes:
            ans = messagebox.askyesnocancel(
                "Cambios sin guardar", 
                "Tienes cambios pendientes en memoria.\n¿Deseas guardar todo en el archivo JS antes de salir?\n\n(Esto lanzará tu flujo de construcción en manager.py)"
            )
            if ans is True: # Presionó 'Sí'
                self.save_to_disk(silent=True)
                self.root.destroy()
            elif ans is False: # Presionó 'No'
                self.root.destroy()
            else: # Presionó 'Cancelar'
                return 
        else:
            self.root.destroy()

    def build_ui(self):
        main = ttk.Frame(self.root, padding=15); main.pack(fill="both", expand=True)
        h = ttk.Frame(main); h.pack(fill="x", pady=(0,10))
        ttk.Label(h, text="MANAGER V24 (Modo RAM)", font=("Helvetica", 16, "bold"), bootstyle="primary").pack(side="left")
        
        ttk.Button(h, text="⚙️ VAR GLOBALES", command=self.edit_constants, bootstyle="info-outline").pack(side="right", padx=5)
        ttk.Button(h, text="📂 Abrir JS", command=self.browse).pack(side="right")
        self.lbl_status = ttk.Label(h, text="-", foreground="gray"); self.lbl_status.pack(side="right", padx=10)

        paned = ttk.PanedWindow(main, orient="horizontal"); paned.pack(fill="both", expand=True)
        left = ttk.Frame(paned, padding=(0,0,10,0)); paned.add(left, weight=1)
        self.tabs_frame = ttk.Labelframe(left, text="Datasets", padding=5); self.tabs_frame.pack(fill="x")
        
        ls_f = ttk.Frame(left); ls_f.pack(fill="both", expand=True, pady=5)
        sb = ttk.Scrollbar(ls_f); sb.pack(side="right", fill="y")
        self.listbox = tk.Listbox(ls_f, font=("Consolas", 10), borderwidth=0, selectmode="SINGLE")
        self.listbox.pack(side="left", fill="both", expand=True); self.listbox.config(yscrollcommand=sb.set); sb.config(command=self.listbox.yview)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)
        
        bf = ttk.Frame(left); bf.pack(fill="x")
        ttk.Button(bf, text="➕ NUEVO", command=self.add_item, bootstyle="success").pack(side="left", fill="x", expand=True)
        ttk.Button(bf, text="🗑️", command=self.del_item, bootstyle="danger").pack(side="left", padx=5)

        right = ttk.Frame(paned, padding=(10,0,0,0)); paned.add(right, weight=3)
        imgf = ttk.Labelframe(right, text="Preview", padding=5, height=220); imgf.pack(fill="x"); imgf.pack_propagate(False)
        self.lbl_img = ttk.Label(imgf, text="-", anchor="center"); self.lbl_img.pack(fill="both", expand=True)
        self.lbl_path = ttk.Label(imgf, text="", font=("Arial", 7), foreground="gray"); self.lbl_path.pack(side="bottom", anchor="e")

        self.c = tk.Canvas(right, highlightthickness=0); sbf = ttk.Scrollbar(right, orient="vertical", command=self.c.yview)
        self.ff = ttk.Frame(self.c); self.ff.bind("<Configure>", lambda e: self.c.configure(scrollregion=self.c.bbox("all")))
        self.c.create_window((0,0), window=self.ff, anchor="nw"); self.c.configure(yscrollcommand=sbf.set)
        self.c.pack(side="left", fill="both", expand=True); sbf.pack(side="right", fill="y")
        self.c.bind("<MouseWheel>", lambda e: self.c.yview_scroll(int(-1*(e.delta/120)), "units"))

        af = ttk.Frame(right, padding=(0,10,0,0)); af.pack(fill="x", side="bottom")
        
        # ÚNICO BOTÓN QUE TOCA EL DISCO DURO
        ttk.Button(af, text="💾 GUARDAR TODO EN EL ARCHIVO ORIGINAL", command=self.save_to_disk, bootstyle="warning").pack(fill="x")

    def smart_load(self):
        candidates = glob.glob("*.js") + glob.glob("*/*.js") + glob.glob("../js/*.js")
        for p in candidates:
            if "min.js" not in p and "utils" not in p: self.load_file(os.path.abspath(p)); return

    def browse(self):
        if self.has_unsaved_changes:
            if not messagebox.askyesno("Confirmar", "Tienes cambios sin guardar. ¿Abrir otro archivo y perderlos?"): return
        f = filedialog.askopenfilename(filetypes=[("JS", "*.js")])
        if f: self.load_file(f)

    def load_file(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f: self.file_content = f.read()
            self.filepath = os.path.abspath(path)
            self.lbl_status.config(text=os.path.basename(path), bootstyle="success")
            
            raw_objects = JSParser.extract_objects(self.file_content)
            self.datasets = {}; self.constants = {}; self.schemas = {}
            for name, raw_content in raw_objects.items():
                if raw_content.strip().startswith('['):
                    data = JSParser.parse_array_of_objects(raw_content)
                    if data:
                        self.datasets[name] = data
                        keys = set(); [keys.update(i.keys()) for i in data]; self.schemas[name] = list(keys)
                elif raw_content.strip().startswith('{'):
                    data = JSParser.parse_kv_inside_object(raw_content)
                    if data: self.constants[name] = data
                    
            self.scan_image_paths()
            self.refresh_tabs()
            self.mark_saved() # Acabamos de cargar, memoria limpia
        except Exception as e:
            messagebox.showerror("Error Carga", str(e))

    def scan_image_paths(self):
        base = os.path.dirname(self.filepath)
        self.image_search_paths = [
            os.path.normpath(os.path.join(base, "../assets/images")),
            os.path.normpath(os.path.join(base, "assets/images")),
            base
        ]
        paths_found = re.findall(r"['\"](\.\./assets/.*?)['\"]", self.file_content)
        for p in paths_found:
            full_path = os.path.normpath(os.path.join(base, p))
            if full_path not in self.image_search_paths:
                self.image_search_paths.append(full_path)
        self.image_search_paths = [p for p in self.image_search_paths if os.path.exists(p)]

    def refresh_tabs(self):
        for w in self.tabs_frame.winfo_children(): w.destroy()
        if not self.datasets: ttk.Label(self.tabs_frame, text="No se encontraron arrays.").pack(pady=5); return
        self.var_tab = tk.StringVar(value=list(self.datasets.keys())[0])
        for k in self.datasets.keys():
            ttk.Radiobutton(self.tabs_frame, text=k, variable=self.var_tab, value=k, command=self.load_list, bootstyle="toolbutton-outline").pack(side="left", fill="x", expand=True)
        self.load_list()

    def load_list(self):
        self.current_key = self.var_tab.get()
        self.listbox.delete(0, tk.END)
        data = self.datasets.get(self.current_key, [])
        for i, item in enumerate(data):
            t = item.get('title') or item.get('fileName') or f"#{i}"
            c = item.get('category', '?').replace('CAT.', '')
            self.listbox.insert(tk.END, f"[{c}] {t}")
        for w in self.ff.winfo_children(): w.destroy()
        self.lbl_img.config(image='', text="Selecciona un item")

    def on_select(self, e):
        sel = self.listbox.curselection()
        if not sel: return
        
        # Volcar inputs actuales a memoria antes de cambiar
        self.save_to_memory(quiet=True)
        
        self.selected_index = sel[0]
        item = self.datasets[self.current_key][self.selected_index]
        self.build_form(item)
        self.load_image(item)

    def get_suggestions(self, key):
        map_c = {'category': 'CAT', 'context': 'CTX', 'tools': 'T'}
        if key in map_c and map_c[key] in self.constants:
            c_name = map_c[key]
            return sorted([f"{c_name}.{k}" for k in self.constants[c_name].keys()])
        opts = set()
        for i in self.datasets.get(self.current_key, []):
            v = i.get(key)
            if isinstance(v, str): opts.add(v)
            elif isinstance(v, list): opts.update(v)
        return sorted(list(opts))

    def build_form(self, item):
        for w in self.ff.winfo_children(): w.destroy()
        self.form_widgets = {}
        schema = self.schemas.get(self.current_key, [])
        prio = ['title', 'category', 'context', 'fileName', 'image', 'date', 'link', 'desc']
        sorted_keys = sorted(schema, key=lambda x: prio.index(x) if x in prio else 99)
        
        for k in sorted_keys:
            row = ttk.Frame(self.ff); row.pack(fill="x", pady=2)
            is_present = k in item
            chk_var = tk.BooleanVar(value=is_present)
            
            def toggle(var=chk_var, key=k):
                st = "normal" if var.get() else "disabled"
                if 'widget' in self.form_widgets[key]: self.form_widgets[key]['widget'].configure(state=st)
                if 'btn_edit' in self.form_widgets[key]: self.form_widgets[key]['btn_edit'].configure(state=st)
                self.save_to_memory()
                
            ttk.Checkbutton(row, text=k.upper(), width=15, variable=chk_var, bootstyle="round-toggle", command=toggle).pack(side="left")
            val = item.get(k, []) if k in ['tools', 'tags'] and k not in item else item.get(k, "")
            is_list = isinstance(val, list) or k in ['tools', 'tags']
            
            if is_list:
                lbl_text = ", ".join(val) if val else "(Vacío)"
                lbl = ttk.Label(row, text=lbl_text, foreground="#888")
                lbl.pack(side="left", fill="x", expand=True, padx=5)
                
                btn = ttk.Button(row, text="Editar", width=8, bootstyle="outline")
                btn.pack(side="right")
                
                def open_l(key_name=k, label_widget=lbl):
                    # Pasamos el valor actual DESDE la memoria
                    current_val = self.datasets[self.current_key][self.selected_index].get(key_name, [])
                    sug = self.get_suggestions(key_name)
                    
                    def callback_save(result_list):
                        label_widget.config(text=", ".join(result_list) if result_list else "(Vacío)")
                        self.form_widgets[key_name]['value'] = result_list
                        self.save_to_memory() # Guardar en RAM
                        
                    ListEditorDialog(self.root, key_name, current_val, sug, callback_save)
                    
                btn.config(command=open_l)
                if not is_present: btn.configure(state="disabled")
                self.form_widgets[k] = {'type': 'list', 'widget': lbl, 'var': chk_var, 'value': val, 'btn_edit': btn}
            else:
                if k in ['fileName', 'image']:
                    ent = ttk.Entry(row)
                    ent.insert(0, str(val))
                    ent.pack(side="left", fill="x", expand=True)
                    btn_br = ttk.Button(row, text="📂", width=3, bootstyle="info-outline")
                    btn_br.pack(side="right", padx=2)
                    
                    def pick_file(entry=ent):
                        f_path = filedialog.askopenfilename(filetypes=[("Imágenes", "*.jpg *.png *.webp *.avif")])
                        if f_path:
                            f_path = os.path.normpath(f_path)
                            base_dir = os.path.dirname(self.filepath)
                            fname = os.path.basename(f_path)
                            
                            is_external = not f_path.startswith(base_dir)
                            if is_external:
                                def on_path_selected(target_folder):
                                    dst = os.path.join(target_folder, fname)
                                    if os.path.exists(dst):
                                        self.lbl_img.config(image=''); self.image_cache = {}; self.root.update_idletasks(); time.sleep(0.1)
                                    try:
                                        if not os.path.exists(target_folder): os.makedirs(target_folder, exist_ok=True)
                                        shutil.copy2(f_path, dst)
                                        messagebox.showinfo("Éxito", f"Imagen copiada a:\n{target_folder}")
                                    except PermissionError: messagebox.showerror("Bloqueado", f"Windows no permite sobreescribir:\n{dst}")
                                    except Exception as ex: messagebox.showerror("Error", str(ex))
                                PathChooserDialog(self.root, self.image_search_paths, fname, on_path_selected)

                            entry.delete(0, tk.END)
                            entry.insert(0, fname)
                            self.save_to_memory()
                            try: self.load_image({'fileName': f_path})
                            except: pass

                    btn_br.config(command=pick_file)
                    ent.bind("<FocusOut>", lambda e: self.save_to_memory())
                    ent.bind("<Return>", lambda e: self.save_to_memory())
                    
                    if not is_present: ent.configure(state="disabled"); btn_br.configure(state="disabled")
                    self.form_widgets[k] = {'type': 'text', 'widget': ent, 'var': chk_var, 'btn_edit': btn_br}
                else:
                    sug = self.get_suggestions(k) if k in ['category', 'context'] else []
                    if sug:
                        ent = AutocompleteCombobox(row, all_options=sug, state='normal')
                        ent.set(str(val))
                    else:
                        ent = ttk.Entry(row); ent.insert(0, str(val))
                    ent.pack(side="left", fill="x", expand=True)
                    ent.bind("<FocusOut>", lambda e: self.save_to_memory())
                    ent.bind("<Return>", lambda e: self.save_memory())
                    if not is_present: ent.configure(state="disabled")
                    self.form_widgets[k] = {'type': 'text', 'widget': ent, 'var': chk_var}
        self.ff.update_idletasks(); self.c.configure(scrollregion=self.c.bbox("all"))

    def save_to_memory(self, quiet=False):
        """Vuelca lo que haya en la UI a los diccionarios en RAM. Solo activa bandera."""
        if self.selected_index is None: return
        new_item = {}
        for k, data in self.form_widgets.items():
            if data['var'].get():
                if data['type'] == 'list': 
                    new_item[k] = data['value']
                else: 
                    new_item[k] = data['widget'].get().strip()
                    
        # Verificar si realmente hubo cambios
        old_item = self.datasets[self.current_key][self.selected_index]
        if old_item != new_item:
            self.datasets[self.current_key][self.selected_index] = new_item
            for k in new_item.keys():
                if k not in self.schemas[self.current_key]: self.schemas[self.current_key].append(k)
            self.mark_unsaved()
        
        if not quiet:
            # Actualiza el título en el listbox
            current_text = self.listbox.get(self.selected_index)
            t = new_item.get('title') or new_item.get('fileName') or f"#{self.selected_index}"
            c = new_item.get('category', '?').replace('CAT.', '')
            new_text = f"[{c}] {t}"
            if current_text != new_text:
                self.listbox.delete(self.selected_index)
                self.listbox.insert(self.selected_index, new_text)
                self.listbox.select_set(self.selected_index)

    def save_to_disk(self, silent=False):
        """
        EL ÚNICO MÉTODO QUE ESCRIBE AL DISCO.
        Recopila la memoria (Proyectos + Constantes) y reescribe el archivo.
        """
        if not self.filepath:
            if not silent: messagebox.showwarning("Atención", "No hay archivo JS cargado.")
            return

        self.save_to_memory(quiet=True) # Asegurar último cambio de input

        content = self.file_content
        
        # 1. Empaquetar Proyectos
        for name, data in self.datasets.items():
            js_str = self.py_to_js_array(data)
            regex = r"((?:const|let|var|window\.)\s*" + name + r"\s*=\s*\[).*?(\];)"
            content = re.sub(regex, f"\\1\n{js_str}\\2", content, flags=re.DOTALL)
            
        # 2. Empaquetar Variables
        for name in ['CTX', 'CAT', 'T']:
            if name in self.constants:
                js_str = self.py_to_js_obj(self.constants[name])
                regex = r"((?:const|let|var|window\.)\s+" + name + r"\s*=\s*\{).*?(\};)"
                content = re.sub(regex, f"\\1\n{js_str}\\2", content, flags=re.DOTALL)
                
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f: 
                f.write(content)
                
            self.file_content = content 
            self.mark_saved()
            
            if not silent:
                messagebox.showinfo("Éxito", "El archivo se guardó correctamente.\n¡manager.py ahora construirá tu portafolio!")
                
        except Exception as e: 
            if not silent: messagebox.showerror("Error al guardar", str(e))

    def py_to_js_array(self, data):
        lines = []
        consts = tuple(list(self.constants.keys()) + ["PROJECT_CONFIG"])
        prefixes = tuple([f"{c}." for c in consts])
        for item in data:
            lines.append("  {")
            for k, v in item.items():
                if isinstance(v, list):
                    els = []
                    for x in v:
                        if x.startswith(prefixes) or x in consts: els.append(x)
                        else: els.append(f"'{x.replace('\'', '\\\'')}'")
                    lines.append(f"    {k}: [{', '.join(els)}],")
                else:
                    s = str(v).strip()
                    if s.startswith(prefixes) or s in consts: lines.append(f"    {k}: {s},")
                    else: lines.append(f"    {k}: '{s.replace('\'', '\\\'')}',")
            lines.append("  },")
        return "\n".join(lines)

    def py_to_js_obj(self, data):
        lines = []
        for k, v in data.items():
            key_str = k if (k.startswith('[') or re.match(r'^\w+$', k)) else f"'{k}'"
            lines.append(f"  {key_str}: '{v}',")
        return "\n".join(lines)

    def edit_constants(self):
        """Abre el editor de variables globales."""
        if not self.constants: return messagebox.showinfo("Info", "No hay variables en memoria.")
        
        def callback_save_constants(new_c):
            # Guardar a memoria y prender bandera de cambios pendientes
            for key, dic in new_c.items(): self.constants[key] = dic
            self.mark_unsaved()
            
            # Recargar UI de formulario para el Autocomplete
            if self.selected_index is not None:
                self.build_form(self.datasets[self.current_key][self.selected_index])
                
        ConstantsEditor(self.root, self.constants, callback_save_constants)

    def add_item(self):
        if not self.current_key: return
        self.save_to_memory()
        
        if self.selected_index is not None:
             base_item = self.datasets[self.current_key][self.selected_index]
             new = {}
             for k, v in base_item.items():
                 if isinstance(v, list): new[k] = list(v)
                 else: new[k] = v
             new['title'] = f"{new.get('title', '')} (COPIA)"; 
             if 'fileName' in new: new['fileName'] = ""
        else:
            sch = self.schemas[self.current_key]
            new = {k: ("" if k not in ['tools','tags'] else []) for k in sch}
            new['title'] = "NUEVO"
        self.datasets[self.current_key].insert(0, new)
        self.mark_unsaved()
        self.load_list(); self.listbox.select_set(0); self.on_select(None)

    def del_item(self):
        if self.selected_index is None: return
        del self.datasets[self.current_key][self.selected_index]
        self.selected_index = None
        self.mark_unsaved()
        self.load_list()

    def auto_fix_extension(self, key_name, found_name):
        if key_name in self.form_widgets and self.form_widgets[key_name]['type'] == 'text':
            widget = self.form_widgets[key_name]['widget']
            if widget.get().strip() != found_name:
                widget.delete(0, tk.END); widget.insert(0, found_name)
                self.save_to_memory(quiet=True)

    def load_image(self, item):
        fn = item.get('fileName') or item.get('image')
        key_used = 'fileName' if item.get('fileName') else 'image'
        if not fn: self.lbl_img.config(image='', text="Sin Imagen"); return
        self.lbl_img.config(image='', text="⏳...")
        threading.Thread(target=self._img_th, args=(fn, key_used), daemon=True).start()

    def _img_th(self, fn, key_used):
        if isinstance(fn, dict): fn = fn.get('fileName')
        if str(fn).startswith("http"):
            try:
                r = requests.get(fn, timeout=2)
                self.show_img(Image.open(io.BytesIO(r.content)), "URL")
            except: self.show_img(None, "Error URL")
        else:
            clean = str(fn).replace("../", "").replace("./", "")
            if clean.startswith(("CAT.", "CTX.")):
                self.root.after(0, lambda: self.show_img(None, f"Referencia: {clean}")); return
                
            found = None
            for p in self.image_search_paths:
                for ext in ['', '.png', '.jpg', '.jpeg', '.webp', '.avif', '.gif']:
                    candidate = os.path.join(p, clean + ext)
                    if os.path.exists(candidate):
                        found = candidate; break
                if found: break
                
            if found:
                try:
                    with open(found, "rb") as f_obj: img_bytes = f_obj.read()
                    self.show_img(Image.open(io.BytesIO(img_bytes)), found)
                    if os.path.basename(found) != clean: 
                        self.root.after(0, lambda: self.auto_fix_extension(key_used, os.path.basename(found)))
                except Exception: self.root.after(0, lambda: self.show_img(None, "Error Lectura"))
            else: self.root.after(0, lambda: self.show_img(None, "No encontrado (Escaneado)"))

    def show_img(self, pil, txt):
        if pil:
            asp = 200/float(pil.size[1]); w = int(float(pil.size[0])*asp)
            tk_img = ImageTk.PhotoImage(pil.resize((w, 200)))
            self.root.after(0, lambda: self._upd_img(tk_img, txt))
        else: self.root.after(0, lambda: self._upd_img(None, txt))

    def _upd_img(self, img, txt):
        if img:
            self.lbl_img.config(image=img, text="")
            self.image_cache['curr'] = img
            self.lbl_path.config(text=os.path.basename(txt))
        else:
            self.lbl_img.config(image='', text=txt)
            self.lbl_path.config(text="")

if __name__ == "__main__":
    app_window = ttk.Window(themename="superhero")
    app = UniversalDBManagerV24(app_window)
    app_window.mainloop()
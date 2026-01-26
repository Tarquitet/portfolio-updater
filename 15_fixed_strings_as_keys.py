"""
Universal Manager V18 - Versión 15 (Fixed Parser)
- Fix: JSParser ahora ignora el contenido de los strings al buscar constantes.
       Esto evita que textos como "Title: Subtitle" creen claves basura.
- Fix: get_suggestions ahora es ESTRICTO para constantes.
- UI Fix: ListEditorDialog botones fijos.
- Feature: Sticky Settings (Clonar al crear nuevo).
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
            except:
                pass
    if installed:
        os.execv(sys.executable, ['python'] + sys.argv)

setup_dependencies()

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from PIL import Image, ImageTk
import requests


class AutocompleteCombobox(ttk.Combobox):
    def __init__(self, parent, all_options, **kwargs):
        super().__init__(parent, **kwargs)
        self._hits = []
        self.all_options = sorted(list(set(all_options)))
        self['values'] = self.all_options
        self.bind('<KeyRelease>', self.handle_keyrelease)

    def handle_keyrelease(self, event):
        if event.keysym in ('BackSpace','Left','Right','Up','Down','Return','Tab'):
            return
        typed = self.get()
        if typed == '':
            self['values'] = self.all_options
        else:
            self._hits = [x for x in self.all_options if typed.lower() in x.lower()]
            self['values'] = self._hits
        self.event_generate('<Down>')


class ListEditorDialog(ttk.Toplevel):
    def __init__(self, parent, title, current_list, all_options, callback):
        super().__init__(parent)
        self.title(f"Editor: {title}")
        self.geometry("450x600")
        self.callback = callback
        
        # 1. Limpieza de datos
        safe_current = [str(x).replace("'","").replace('"',"").strip() for x in current_list if x]
        safe_opts = [str(x).replace("'","").replace('"',"").strip() for x in all_options if x]
        
        # 2. Combinar
        self.all_options = sorted(list(set(safe_opts + safe_current)))
        self.vars = {}

        # --- UI LAYOUT (Botones fijos abajo) ---
        
        # Header
        ttk.Label(self, text=f"Seleccionar {title}", font=("Arial", 10, "bold")).pack(pady=10)

        # Bottom Frame (Botones) - Se empaqueta PRIMERO con side=bottom para que quede fijo
        bottom_frame = ttk.Frame(self, padding=10)
        bottom_frame.pack(side="bottom", fill="x")

        # Input manual en el bottom frame
        input_frame = ttk.Frame(bottom_frame)
        input_frame.pack(fill="x", pady=(0, 10))
        
        self.en = ttk.Entry(input_frame)
        self.en.pack(side="left", fill="x", expand=True, padx=5)
        self.en.bind("<Return>", lambda e: self.add_manual())
        
        ttk.Button(input_frame, text="Añadir Manual", command=self.add_manual, bootstyle="info-outline").pack(side="right")
        
        # Botón Guardar Principal
        ttk.Button(bottom_frame, text="GUARDAR SELECCIÓN", command=self.save, bootstyle="success").pack(fill="x")

        # Scrollable Area (Toma el resto del espacio)
        container = ttk.Frame(self)
        container.pack(side="top", fill="both", expand=True, padx=10)
        
        c = tk.Canvas(container, highlightthickness=0)
        sb = ttk.Scrollbar(container, orient="vertical", command=c.yview)
        
        self.f = ttk.Frame(c)
        self.f.bind("<Configure>", lambda e: c.configure(scrollregion=c.bbox("all")))
        
        c.create_window((0,0), window=self.f, anchor="nw")
        c.configure(yscrollcommand=sb.set)
        
        c.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Scroll Mouse
        def _wheel(e):
            if c.winfo_exists(): c.yview_scroll(int(-1*(e.delta/120)), "units")
        c.bind("<MouseWheel>", _wheel)

        # Generar Checkboxes
        for opt in self.all_options:
            self.add_checkbox(opt, opt in safe_current)

    def add_checkbox(self, text, checked=False):
        if text in self.vars: return
        v = tk.BooleanVar(value=checked)
        self.vars[text] = v
        cb = ttk.Checkbutton(self.f, text=text, variable=v)
        cb.pack(anchor="w", pady=2)

    def add_manual(self):
        val = self.en.get().strip()
        if val:
            self.add_checkbox(val, checked=True)
            self.en.delete(0, tk.END)
            self.f.update_idletasks()

    def save(self):
        # Si quedó texto pendiente en el input, añadirlo
        pending = self.en.get().strip()
        if pending:
            self.vars[pending] = tk.BooleanVar(value=True)
            
        result = [k for k,v in self.vars.items() if v.get()]
        self.callback(result)
        self.destroy()


class PathChooserDialog(ttk.Toplevel):
    """Dialogo para elegir dónde copiar la imagen"""
    def __init__(self, parent, paths, filename, callback):
        super().__init__(parent)
        self.title("Destino de Imagen")
        self.geometry("500x400")
        self.callback = callback
        
        ttk.Label(self, text="Imagen externa detectada", bootstyle="warning").pack(pady=10)
        ttk.Label(self, text=f"¿En qué carpeta de assets quieres guardar:\n'{filename}'?", justify="center").pack(pady=5)
        
        lb_frame = ttk.Frame(self, padding=10)
        lb_frame.pack(fill="both", expand=True)
        
        sb = ttk.Scrollbar(lb_frame)
        sb.pack(side="right", fill="y")
        
        self.lb = tk.Listbox(lb_frame, font=("Consolas", 9))
        self.lb.pack(side="left", fill="both", expand=True)
        self.lb.config(yscrollcommand=sb.set); sb.config(command=self.lb.yview)
        
        # Filtrar rutas relevantes
        valid_paths = [p for p in paths if "assets" in p or "images" in p]
        if not valid_paths: valid_paths = paths
        
        for p in valid_paths:
            self.lb.insert(tk.END, p)
            
        ttk.Button(self, text="COPIAR AQUÍ", command=self.confirm, bootstyle="success").pack(fill="x", padx=20, pady=20)

    def confirm(self):
        sel = self.lb.curselection()
        if not sel: return
        path = self.lb.get(sel[0])
        self.callback(path)
        self.destroy()


class ConstantsEditor(ttk.Toplevel):
    def __init__(self, parent, constants_data, callback):
        super().__init__(parent)
        self.title("Editor Constantes")
        self.geometry("700x600")
        self.data = constants_data
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
            ttk.Button(inn, text="➕ Nueva Clave", command=lambda g=grp, i=inn: self.add_row(g,i)).pack(pady=10)
        ttk.Button(self, text="GUARDAR TODO", command=self.save, bootstyle="success").pack(fill="x", padx=10, pady=10)

    def add_row(self, grp, cont, k="", v=""):
        r = ttk.Frame(cont); r.pack(fill="x", pady=2)
        ke = ttk.Entry(r, width=15); ke.insert(0, k); ke.pack(side="left")
        ttk.Label(r, text=":").pack(side="left", padx=5)
        ve = ttk.Entry(r); ve.insert(0, v); ve.pack(side="left", fill="x", expand=True)
        self.entries[grp].append((ke, ve))

    def save(self):
        new_d = {}
        for g, rows in self.entries.items():
            new_d[g] = {}
            for k,v in rows:
                if k.get().strip(): new_d[g][k.get().strip()] = v.get().strip()
        self.callback(new_d); self.destroy()


class JSParser:
    @staticmethod
    def remove_comments(text):
        # Elimina comentarios pero respeta los strings, evitando romper URLs o Textos
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
        # Detecta declaraciones tipo: const x = [...], window.x = [...], var x = [...]
        regex_start = re.compile(r"(?:const|let|var|window\.)\s*(\w+)\s*=\s*([\[\{])", re.DOTALL)
        for match in regex_start.finditer(content):
            var_name = match.group(1)
            start_char = match.group(2)
            start_idx = match.start(2)
            balance = 0; end_idx = -1; in_string = False; string_char = ''
            
            # Algoritmo de balanceo que respeta strings para encontrar el cierre ] o }
            for i in range(start_idx, len(content)):
                char = content[i]
                if char in ["'", '"', "`"] and (i==0 or content[i-1] != "\\"):
                    if not in_string: in_string = True; string_char = char
                    elif char == string_char: in_string = False
                
                if not in_string:
                    if char == start_char: balance += 1
                    elif char == (']' if start_char == '[' else '}'):
                        balance -= 1
                        if balance == 0: end_idx = i + 1; break
            
            if end_idx != -1: objects[var_name] = content[start_idx:end_idx]
        return objects

    @staticmethod
    def parse_kv_inside_object(raw_content):
        data = {}
        # Extrae pares Clave: 'Valor' (Solo Strings explícitos)
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
        
        # Divide objetos por "}, {"
        raw_objs = re.split(r"\}\s*,\s*\{", inner)
        items = []
        
        for raw in raw_objs:
            clean = raw.strip()
            if not clean.startswith("{"): clean = "{" + clean
            if not clean.endswith("}"): clean = clean + "}"
            
            # A. Obtener datos tipo String normales
            obj_data = JSParser.parse_kv_inside_object(clean)
            
            # B. Obtener Arrays (ej: tools: [...])
            regex_arrays = re.compile(r"(\w+)\s*:\s*\[(.*?)\]", re.DOTALL)
            for m in regex_arrays.finditer(clean):
                k = m.group(1); v_raw = m.group(2)
                elems = [x.strip().replace("'", "").replace('"', '') for x in v_raw.split(',') if x.strip()]
                obj_data[k] = elems
            
            # C. Obtener Constantes (ej: category: CAT.DEV)
            # FIX: Creamos una versión "enmascarada" donde vaciamos los strings.
            # Así, si el título es 'Planty: Video', el parser verá 'title: ""' y no se confundirá.
            masked_clean = re.sub(r"('(?:\.|[^'])*'|\"(?:\.|[^\"])*\")", "''", clean)
            
            regex_const = re.compile(r"(\w+)\s*:\s*(?!['\"\[])([a-zA-Z0-9_.]+)(?!['\"\]])", re.DOTALL)
            for m in regex_const.finditer(masked_clean):
                k = m.group(1); v = m.group(2)
                # Solo agregamos si no existe ya (dando prioridad a lo que se encontró como string real)
                if k not in obj_data: obj_data[k] = v
                
            items.append(obj_data)
        return items


class UniversalDBManagerV18:
    def __init__(self, root):
        self.root = root
        self.root.title("Tarquitet - Universal Manager V18 (Fixed Parser)")
        self.root.geometry("1400x900")
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
        self.smart_load()

    def build_ui(self):
        main = ttk.Frame(self.root, padding=15); main.pack(fill="both", expand=True)
        h = ttk.Frame(main); h.pack(fill="x", pady=(0,10))
        ttk.Label(h, text="UNIVERSAL DATA V18", font=("Helvetica", 16, "bold"), bootstyle="primary").pack(side="left")
        ttk.Button(h, text="⚙️ CONSTANTES", command=self.edit_constants, bootstyle="info-outline").pack(side="right", padx=5)
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
        ttk.Button(bf, text="➕ NUEVO (CLONAR)", command=self.add_item, bootstyle="success").pack(side="left", fill="x", expand=True)
        ttk.Button(bf, text="🗑️", command=self.del_item, bootstyle="danger").pack(side="left", padx=5)

        right = ttk.Frame(paned, padding=(10,0,0,0)); paned.add(right, weight=3)
        imgf = ttk.Labelframe(right, text="Preview", padding=5, height=220); imgf.pack(fill="x"); imgf.pack_propagate(False)
        self.lbl_img = ttk.Label(imgf, text="-", anchor="center"); self.lbl_img.pack(fill="both", expand=True)
        self.lbl_path = ttk.Label(imgf, text="", font=("Arial", 7), foreground="gray"); self.lbl_path.pack(side="bottom", anchor="e")

        self.c = tk.Canvas(right, highlightthickness=0); sbf = ttk.Scrollbar(right, orient="vertical", command=self.c.yview)
        self.ff = ttk.Frame(self.c); self.ff.bind("<Configure>", lambda e: self.c.configure(scrollregion=self.c.bbox("all")))
        self.c.create_window((0,0), window=self.ff, anchor="nw"); self.c.configure(yscrollcommand=sbf.set)
        self.c.pack(side="left", fill="both", expand=True); sbf.pack(side="right", fill="y")

        def _main_wheel(e, canvas=self.c):
            try:
                if canvas.winfo_exists(): canvas.yview_scroll(int(-1*(e.delta/120)), "units")
            except Exception: pass
        self.c.bind("<MouseWheel>", _main_wheel)

        af = ttk.Frame(right, padding=(0,10,0,0)); af.pack(fill="x", side="bottom")
        ttk.Button(af, text="💾 GUARDAR CAMBIOS", command=self.save_file, bootstyle="warning").pack(fill="x")

    def smart_load(self):
        candidates = glob.glob("*.js") + glob.glob("*/*.js") + glob.glob("../js/*.js")
        for p in candidates:
            if "min.js" not in p and "utils" not in p:
                self.load_file(os.path.abspath(p)); return

    def browse(self):
        f = filedialog.askopenfilename(filetypes=[("JS", "*.js")])
        if f: self.load_file(f)

    def load_file(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f: self.file_content = f.read()
            self.filepath = path
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
            self.image_cache = {}
        except Exception as e:
            messagebox.showerror("Error Carga", str(e))

    def scan_image_paths(self):
        base = os.path.dirname(self.filepath)
        self.image_search_paths = [os.path.join(base, "../assets/images"), os.path.join(base, "assets/images"), base]
        paths_found = re.findall(r"['\"](\.\./assets/.*?)['\"]", self.file_content)
        for p in paths_found:
            full_path = os.path.normpath(os.path.join(base, p))
            if full_path not in self.image_search_paths: self.image_search_paths.append(full_path)
        subfolders = []
        for p in self.image_search_paths:
            if os.path.exists(p):
                try:
                    subs = [os.path.join(p, d) for d in os.listdir(p) if os.path.isdir(os.path.join(p, d))]
                    subfolders.extend(subs)
                except: pass
        self.image_search_paths.extend(subfolders)
        self.image_search_paths = list(set([os.path.normpath(p) for p in self.image_search_paths]))

    def refresh_tabs(self):
        for w in self.tabs_frame.winfo_children(): w.destroy()
        if not self.datasets:
            ttk.Label(self.tabs_frame, text="No se encontraron arrays.").pack(pady=5)
            return
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
        try:
            sel = self.listbox.curselection()
            if not sel: return
            self.selected_index = sel[0]
            item = self.datasets[self.current_key][self.selected_index]
            self.build_form(item)
            self.load_image(item)
        except Exception as err: print(err)

    def get_suggestions(self, key):
        # Mapeo de campos a grupos de Constantes
        map_c = {'category': 'CAT', 'context': 'CTX', 'tools': 'T'}
        
        # 1. Si el campo está mapeado (Es una constante estricta)
        if key in map_c and map_c[key] in self.constants:
            c_name = map_c[key]
            # SOLO devolvemos las claves de la constante (ej: T.HTML, CAT.DEV)
            return sorted([f"{c_name}.{k}" for k in self.constants[c_name].keys()])

        # 2. Si NO es constante estricta (ej: tags), escaneamos lo existente
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
        prio = ['title', 'category', 'context', 'fileName', 'date', 'link', 'desc']
        sorted_keys = sorted(schema, key=lambda x: prio.index(x) if x in prio else 99)
        for k in sorted_keys:
            row = ttk.Frame(self.ff); row.pack(fill="x", pady=2)
            is_present = k in item
            chk_var = tk.BooleanVar(value=is_present)
            def toggle(var=chk_var, key=k):
                st = "normal" if var.get() else "disabled"
                self.form_widgets[key]['widget'].configure(state=st)
                if key in ['fileName', 'image'] and 'btn_browse' in self.form_widgets[key]:
                    self.form_widgets[key]['btn_browse'].configure(state=st)
                self.save_memory()
            ttk.Checkbutton(row, text=k.upper(), width=15, variable=chk_var, bootstyle="round-toggle", command=toggle).pack(side="left")
            val = item.get(k, []) if k in ['tools', 'tags'] and k not in item else item.get(k, "")
            is_list = isinstance(val, list) or k in ['tools', 'tags']
            if is_list:
                lbl = ttk.Label(row, text=", ".join(val) if val else "(Vacío)", foreground="#888")
                lbl.pack(side="left", fill="x", expand=True)
                btn = ttk.Button(row, text="Editar", width=8, bootstyle="outline")
                btn.pack(side="right")
                def open_l(key=k, current=val, l_w=lbl):
                    sug = self.get_suggestions(key)
                    def save_l(res):
                        self.form_widgets[key]['value'] = res
                        l_w.config(text=", ".join(res)); self.save_memory()
                    ListEditorDialog(self.root, key, current, sug, save_l)
                btn.config(command=open_l)
                if not is_present: btn.configure(state="disabled")
                self.form_widgets[k] = {'type': 'list', 'widget': btn, 'var': chk_var, 'value': val}
            else:
                if k in ['fileName', 'image']:
                    ent = ttk.Entry(row)
                    ent.insert(0, str(val))
                    ent.pack(side="left", fill="x", expand=True)
                    btn_br = ttk.Button(row, text="📂", width=3, bootstyle="info-outline")
                    btn_br.pack(side="right", padx=2)
                    
                    def pick_file(entry=ent):
                        f = filedialog.askopenfilename(filetypes=[("Imágenes", "*.jpg *.png *.webp *.avif")])
                        if f:
                            fname = os.path.basename(f); name_no_ext = os.path.splitext(fname)[0]
                            # Preguntar destino si es fuera del proyecto
                            base_dir = os.path.dirname(self.filepath) if self.filepath else ""
                            if base_dir and base_dir not in f:
                                def on_path_selected(target_folder):
                                    try:
                                        shutil.copy(f, target_folder)
                                        messagebox.showinfo("Copiado", f"Imagen copiada a:\n{target_folder}")
                                    except Exception as ex:
                                        messagebox.showerror("Error Copia", str(ex))
                                PathChooserDialog(self.root, self.image_search_paths, fname, on_path_selected)

                            sample = self.datasets[self.current_key][0].get(k, "")
                            if "." in sample: entry.delete(0, tk.END); entry.insert(0, fname)
                            else: entry.delete(0, tk.END); entry.insert(0, name_no_ext)
                            self.save_memory()
                            try: self.load_image({'fileName': f})
                            except: pass
                            
                    btn_br.config(command=pick_file)
                    ent.bind("<FocusOut>", lambda e: self.save_memory())
                    ent.bind("<KeyRelease>", lambda e: self.save_memory())
                    if not is_present: ent.configure(state="disabled"); btn_br.configure(state="disabled")
                    self.form_widgets[k] = {'type': 'text', 'widget': ent, 'var': chk_var, 'btn_browse': btn_br}
                else:
                    sug = self.get_suggestions(k)
                    if sug:
                        ent = AutocompleteCombobox(row, all_options=sug, state='normal')
                        ent.set(str(val))
                    else:
                        ent = ttk.Entry(row); ent.insert(0, str(val))
                    ent.pack(side="left", fill="x", expand=True)
                    ent.bind("<FocusOut>", lambda e: self.save_memory())
                    ent.bind("<KeyRelease>", lambda e: self.save_memory())
                    if not is_present: ent.configure(state="disabled")
                    self.form_widgets[k] = {'type': 'text', 'widget': ent, 'var': chk_var}
        self.ff.update_idletasks(); self.c.configure(scrollregion=self.c.bbox("all"))

    def save_memory(self):
        if self.selected_index is None: return
        new_item = {}
        for k, data in self.form_widgets.items():
            if data['var'].get():
                if data['type'] == 'list': new_item[k] = data['value']
                else: new_item[k] = data['widget'].get().strip()
        self.datasets[self.current_key][self.selected_index] = new_item
        for k in new_item.keys():
            if k not in self.schemas[self.current_key]: self.schemas[self.current_key].append(k)
        self.load_image(new_item)

    def save_file(self):
        prev_key = self.current_key
        prev_ident = None
        if self.selected_index is not None and prev_key in self.datasets:
            cur = self.datasets[prev_key][self.selected_index]
            prev_ident = cur.get('title') or cur.get('fileName')

        content = self.file_content
        for name, data in self.datasets.items():
            js_str = self.py_to_js_array(data)
            regex = r"((?:const|let|var|window\.)\s*" + name + r"\s*=\s*\[).*?(\];)"
            content = re.sub(regex, f"\\1\n{js_str}\\2", content, flags=re.DOTALL)
        for name, data in self.constants.items():
            js_str = self.py_to_js_obj(data)
            regex = r"((?:const|let|var|window\.)\s+" + name + r"\s*=\s*\{).*?(\};)"
            content = re.sub(regex, f"\\1\n{js_str}\\2", content, flags=re.DOTALL)
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f: f.write(content)
            self.file_content = content
            messagebox.showinfo("Guardado", "Archivo actualizado.")
            self.load_file(self.filepath)
            if prev_key and prev_ident and prev_key in self.datasets:
                for idx, itm in enumerate(self.datasets[prev_key]):
                    if itm.get('title') == prev_ident or itm.get('fileName') == prev_ident:
                        self.var_tab.set(prev_key)
                        self.load_list()
                        self.listbox.select_set(idx)
                        self.on_select(None)
                        break
        except Exception as e:
            messagebox.showerror("Error", str(e))

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
                        else: els.append(f"'{x.replace("'", "\\'")}'")
                    lines.append(f"    {k}: [{', '.join(els)}],")
                else:
                    s = str(v).strip()
                    if s.startswith(prefixes) or s in consts: lines.append(f"    {k}: {s},")
                    else: lines.append(f"    {k}: '{s.replace("'", "\\'")}',")
            lines.append("  },")
        return "\n".join(lines)

    def py_to_js_obj(self, data):
        lines = []
        for k, v in data.items():
            key_str = k if (k.startswith('[') or re.match(r'^\w+$', k)) else f"'{k}'"
            lines.append(f"  {key_str}: '{v}',")
        return "\n".join(lines)

    def edit_constants(self):
        if not self.constants: return messagebox.showinfo("Info", "No hay constantes editables.")
        def save(new_c):
            self.constants = new_c; self.save_file(); self.smart_load()
        ConstantsEditor(self.root, self.constants, save)

    def add_item(self):
        if not self.current_key: return
        
        # Sticky Settings: Clonar el seleccionado o crear vacío
        if self.selected_index is not None:
             base_item = self.datasets[self.current_key][self.selected_index]
             new = {}
             for k, v in base_item.items():
                 if isinstance(v, list): new[k] = list(v)
                 else: new[k] = v
             new['title'] = f"{new.get('title', '')} (COPIA)"
             if 'fileName' in new: new['fileName'] = ""
        else:
            sch = self.schemas[self.current_key]
            new = {k: ("" if k not in ['tools','tags'] else []) for k in sch}
            new['title'] = "NUEVO"
            
        self.datasets[self.current_key].insert(0, new)
        self.load_list(); self.listbox.select_set(0); self.on_select(None)

    def del_item(self):
        if self.selected_index is None: return
        del self.datasets[self.current_key][self.selected_index]
        self.selected_index = None; self.load_list()

    def load_image(self, item):
        fn = item.get('fileName') or item.get('image')
        if not fn: self.lbl_img.config(image='', text="Sin Imagen"); return
        self.lbl_img.config(image='', text="⌛")
        threading.Thread(target=self._img_th, args=(fn,), daemon=True).start()

    def _img_th(self, fn):
        if isinstance(fn, dict): fn = fn.get('fileName')
        if str(fn).startswith("http"):
            try:
                r = requests.get(fn, timeout=2)
                self.show_img(Image.open(io.BytesIO(r.content)), "URL")
            except: self.show_img(None, "Error URL")
        else:
            clean = str(fn).replace("../", "").replace("./", "")
            if clean.startswith(("CAT.", "CTX.")):
                self.root.after(0, lambda: self.show_img(None, f"Referencia: {clean}"))
                return
            found = None
            for p in self.image_search_paths:
                if not os.path.exists(p): continue
                for ext in ['', '.avif', '.webp', '.jpg', '.png']:
                    f = os.path.join(p, clean+ext)
                    if os.path.exists(f): found = f; break
                if found: break
            if found: self.show_img(Image.open(found), found)
            else: self.root.after(0, lambda: self.show_img(None, "No encontrado en assets"))

    def show_img(self, pil, txt):
        if pil:
            asp = 200/float(pil.size[1])
            w = int(float(pil.size[0])*asp)
            tk_img = ImageTk.PhotoImage(pil.resize((w, 200)))
            self.root.after(0, lambda: self._upd_img(tk_img, txt))
        else:
            self.root.after(0, lambda: self._upd_img(None, txt))

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
    app = UniversalDBManagerV18(app_window)
    app_window.mainloop()
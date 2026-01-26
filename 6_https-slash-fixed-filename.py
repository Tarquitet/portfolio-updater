import sys
import os
import subprocess
import re
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
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
# VENTANA FLOTANTE PARA SELECCIONAR TAGS (MULTI-SELECT)
# ============================================================
class ListEditorDialog(ttk.Toplevel):
    def __init__(self, parent, title, current_list, all_options, callback):
        super().__init__(parent)
        self.title(title)
        self.geometry("450x600")
        self.callback = callback
        
        # Unificar opciones existentes con las actuales del item
        # Limpiamos duplicados y ordenamos
        clean_options = set()
        for opt in all_options + current_list:
            # Limpiar comillas extras si se colaron
            clean = opt.replace("'", "").replace('"', "").strip()
            if clean: clean_options.add(clean)
            
        self.all_options = sorted(list(clean_options))
        self.vars = {}

        # UI Header
        ttk.Label(self, text="Marca las opciones activas:", font=("Arial", 10, "bold")).pack(pady=10)

        # Scroll Area
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
        
        # Checkboxes
        self.render_checkboxes(current_list)

        # Añadir Nuevo
        add_frame = ttk.Labelframe(self, text="Crear Nuevo Tag", padding=10)
        add_frame.pack(fill="x", padx=10, pady=10)
        
        self.entry_new = ttk.Entry(add_frame)
        self.entry_new.pack(side="left", fill="x", expand=True, padx=(0,5))
        self.entry_new.bind("<Return>", lambda e: self.add_new())
        ttk.Button(add_frame, text="Añadir", command=self.add_new, bootstyle="info-outline").pack(side="right")

        # Botones Finales
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill="x", side="bottom")
        ttk.Button(btn_frame, text="Cancelar", command=self.destroy, bootstyle="secondary").pack(side="left", expand=True, fill="x")
        ttk.Button(btn_frame, text="GUARDAR CAMBIOS", command=self.save, bootstyle="success").pack(side="left", expand=True, fill="x")

        self.transient(parent)
        self.grab_set()

    def render_checkboxes(self, active_list):
        for w in self.scroll_inner.winfo_children(): w.destroy()
        self.vars = {}
        # Normalizar lista activa para comparar sin comillas
        active_clean = [x.replace("'", "").replace('"', "").strip() for x in active_list]
        
        for opt in self.all_options:
            var = tk.BooleanVar(value=opt in active_clean)
            self.vars[opt] = var
            cb = ttk.Checkbutton(self.scroll_inner, text=opt, variable=var)
            cb.pack(anchor="w", pady=2, padx=5)

    def add_new(self):
        val = self.entry_new.get().strip()
        if val and val not in self.all_options:
            self.all_options.append(val)
            self.all_options.sort()
            # Guardar estado actual
            current_active = [k for k, v in self.vars.items() if v.get()]
            current_active.append(val) # Activar el nuevo automáticamente
            self.render_checkboxes(current_active)
            self.entry_new.delete(0, tk.END)

    def save(self):
        selected = [k for k, v in self.vars.items() if v.get()]
        self.callback(selected)
        self.destroy()

# ============================================================
# APLICACIÓN PRINCIPAL (V10)
# ============================================================
class UniversalDBManagerV10:
    def __init__(self, root):
        self.root = root
        self.root.title("Tarquitet - Universal Manager V10 (Fix URLs + Smart Lists)")
        self.root.geometry("1400x900")
        
        self.filepath = ""
        self.file_content = ""
        self.datasets = {} 
        self.dataset_schemas = {} # Para saber qué campos usar en "Nuevo Item"
        
        self.current_key = None 
        self.selected_index = None
        self.form_widgets = {}
        
        self.image_cache = {}
        self.loading_thread = None
        self.discovered_paths = []

        self.build_ui()
        self.smart_auto_load()

    def build_ui(self):
        main = ttk.Frame(self.root, padding=15)
        main.pack(fill="both", expand=True)

        # Header
        head = ttk.Frame(main)
        head.pack(fill="x", pady=(0,10))
        ttk.Label(head, text="UNIVERSAL DATA MANAGER V10", font=("Helvetica", 16, "bold"), bootstyle="primary").pack(side="left")
        
        h_right = ttk.Frame(head)
        h_right.pack(side="right")
        ttk.Button(h_right, text="📂 Abrir JS", command=self.browse_file).pack(side="left", padx=5)
        self.lbl_status = ttk.Label(h_right, text="Inactivo", font=("Consolas", 9), foreground="gray")
        self.lbl_status.pack(side="left")

        # Paneles
        paned = ttk.PanedWindow(main, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # --- PANEL IZQUIERDO (Lista) ---
        left = ttk.Frame(paned, padding=(0,0,10,0))
        paned.add(left, weight=1)

        self.tabs_frame = ttk.Labelframe(left, text="Tablas Detectadas", padding=5)
        self.tabs_frame.pack(fill="x", pady=(0,5))
        self.lbl_nodata = ttk.Label(self.tabs_frame, text="Carga un archivo JS para empezar")
        self.lbl_nodata.pack()

        # Lista Scroll
        lst_frame = ttk.Frame(left)
        lst_frame.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(lst_frame)
        scroll.pack(side="right", fill="y")
        self.listbox = tk.Listbox(lst_frame, font=("Consolas", 10), borderwidth=0, highlightthickness=0, selectmode="SINGLE")
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.config(yscrollcommand=scroll.set)
        scroll.config(command=self.listbox.yview)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        # Botones CRUD
        btns = ttk.Frame(left, padding=(0,10,0,0))
        btns.pack(fill="x")
        ttk.Button(btns, text="➕ NUEVO", command=self.add_item, bootstyle="success").pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(btns, text="❌ BORRAR", command=self.delete_item, bootstyle="danger").pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(btns, text="▲", width=3, command=lambda: self.move(-1)).pack(side="left", padx=1)
        ttk.Button(btns, text="▼", width=3, command=lambda: self.move(1)).pack(side="left", padx=1)

        # --- PANEL DERECHO (Editor) ---
        right = ttk.Frame(paned, padding=(10,0,0,0))
        paned.add(right, weight=3)

        # Preview Imagen
        self.prev_frame = ttk.Labelframe(right, text="Vista Previa", padding=10, height=200)
        self.prev_frame.pack(fill="x", pady=(0,10))
        self.prev_frame.pack_propagate(False)
        self.lbl_img = ttk.Label(self.prev_frame, text="Selecciona un item", anchor="center")
        self.lbl_img.pack(fill="both", expand=True)
        self.lbl_img_info = ttk.Label(self.prev_frame, text="", font=("Arial", 7), foreground="gray")
        self.lbl_img_info.pack(side="bottom", anchor="e")

        # Formulario Dinámico (Canvas Scroll)
        self.canvas = tk.Canvas(right, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(right, orient="vertical", command=self.canvas.yview)
        self.form_frame = ttk.Frame(self.canvas)
        
        self.form_win = self.canvas.create_window((0,0), window=self.form_frame, anchor="nw")
        self.form_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.form_win, width=e.width))
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Acciones Finales
        acts = ttk.Frame(right, padding=(0,10,0,0))
        acts.pack(fill="x", side="bottom")
        ttk.Button(acts, text="💾 APLICAR CAMBIOS", command=self.save_memory, bootstyle="warning").pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(acts, text="💾 GUARDAR ARCHIVO JS", command=self.save_file, bootstyle="success").pack(side="left", fill="x", expand=True, padx=5)

    # ============================================================
    # LÓGICA DE CARGA Y PARSEO (FIXED)
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
            self.parse_data()
            self.build_tabs()
            self.image_cache = {}
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def parse_data(self):
        self.datasets = {}
        self.dataset_schemas = {}
        
        # Regex para encontrar variables array
        regex = r"(?:const\s+|let\s+|var\s+|window\.)\s*(\w+)\s*=\s*\[(.*?)\];"
        matches = re.finditer(regex, self.file_content, re.DOTALL)
        
        for m in matches:
            name = m.group(1)
            raw = m.group(2)
            
            # --- CORRECCIÓN CRÍTICA PARA URLs ---
            # Solo borrar comentarios si NO están precedidos por dos puntos (evita borrar https://)
            clean = re.sub(r"(?<!:)\/\/.*", "", raw)
            
            if "{" in clean:
                data = self.parse_array_body(clean)
                if data:
                    self.datasets[name] = data
                    # Guardar esquema (todos los campos únicos encontrados)
                    keys = set()
                    for item in data: keys.update(item.keys())
                    self.dataset_schemas[name] = list(keys)

    def parse_array_body(self, content):
        items = content.split('},')
        res = []
        for item in items:
            if not item.strip(): continue
            item_clean = item.replace('{', '').replace('}', '').strip()
            
            obj = {}
            # 1. Capturar propiedades simples (incluyendo constantes y URLs)
            # Clave : 'Valor' | "Valor" | Constante
            props = re.findall(r"(\w+):\s*(?:'([^']*)'|\"([^\"]*)\"|([a-zA-Z0-9_.]+))", item_clean)
            for k, v1, v2, v3 in props:
                obj[k] = v1 or v2 or v3
            
            # 2. Capturar Arrays (Tools, Tags)
            arrays = re.findall(r"(\w+):\s*\[(.*?)\]", item_clean)
            for k, v in arrays:
                # Limpiar elementos
                elems = [x.strip().replace("'", "").replace('"', "") for x in v.split(',')]
                obj[k] = [e for e in elems if e]
            
            if obj: res.append(obj)
        return res

    # ============================================================
    # UI DINÁMICA
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
        
        # Limpiar editor
        for w in self.form_frame.winfo_children(): w.destroy()
        self.lbl_img.config(image='', text="Selecciona un item")

    def on_select(self, e):
        sel = self.listbox.curselection()
        if not sel: return
        self.selected_index = sel[0]
        item = self.datasets[self.current_key][self.selected_index]
        self.build_form(item)
        self.load_image(item)

    def build_form(self, item):
        for w in self.form_frame.winfo_children(): w.destroy()
        self.form_widgets = {}
        
        # Obtener TODOS los campos posibles para este dataset (para rellenar nuevos items)
        all_fields = self.dataset_schemas.get(self.current_key, [])
        
        # Ordenar campos con prioridad visual
        prio = ['title', 'category', 'context', 'fileName', 'date', 'link', 'desc']
        fields = sorted(all_fields, key=lambda x: prio.index(x) if x in prio else 99)
        
        row = 0
        for k in fields:
            val = item.get(k, "")
            is_list = isinstance(val, list) or k in ['tools', 'tags', 'skills']
            
            lbl_txt = k.upper() + (" (LISTA)" if is_list else "")
            ttk.Label(self.form_frame, text=lbl_txt, font=("Arial", 7, "bold"), foreground="#666").grid(row=row, column=0, sticky="w", pady=(10,0))
            
            if is_list:
                # --- WIDGET DE LISTA INTELIGENTE ---
                f_list = ttk.Frame(self.form_frame)
                f_list.grid(row=row+1, column=0, sticky="ew")
                
                # Preview de texto
                txt_val = ", ".join(val) if val else "(Vacío)"
                lbl_val = ttk.Label(f_list, text=txt_val, font=("Consolas", 9), wraplength=300)
                lbl_val.pack(side="left", fill="x", expand=True)
                
                # Botón Editar
                btn = ttk.Button(f_list, text="Editar", width=8, bootstyle="info-outline")
                btn.pack(side="right")
                
                # Callback para abrir el popup
                def open_editor(key=k, current=val if isinstance(val, list) else [], label=lbl_val):
                    # Recolectar TODAS las opciones usadas en este dataset para sugerirlas
                    all_opts = set()
                    for i in self.datasets[self.current_key]:
                        if isinstance(i.get(key), list): all_opts.update(i[key])
                    
                    def on_save(new_list):
                        self.form_widgets[key] = new_list # Guardar nueva lista
                        label.config(text=", ".join(new_list))
                        self.save_memory() # Auto-guardar en memoria
                        
                    ListEditorDialog(self.root, f"Editar {key}", current, list(all_opts), on_save)
                
                btn.config(command=open_editor)
                self.form_widgets[k] = val if isinstance(val, list) else []
                
            else:
                # --- WIDGET DE TEXTO NORMAL ---
                ent = ttk.Entry(self.form_frame)
                ent.insert(0, str(val))
                ent.grid(row=row+1, column=0, sticky="ew", ipady=3)
                self.form_widgets[k] = ent
                
            row += 2
        
        self.form_frame.columnconfigure(0, weight=1)

    # ============================================================
    # IMÁGENES THREADED (NO SE TRABA)
    # ============================================================
    def discover_paths(self, content, js_path):
        base = os.path.dirname(js_path)
        # Rutas por defecto + Búsqueda en config
        self.discovered_paths = [os.path.join(base, "../assets/images")]
        match = re.search(r"paths:\s*\{(.*?)\}", content, re.DOTALL)
        if match:
            raw = re.findall(r"['\"](.*?)['\"]", match.group(1))
            for p in raw:
                if len(p) > 2: self.discovered_paths.append(os.path.normpath(os.path.join(base, p)))
        
        # Auto-descubrir subcarpetas
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
        
        # Loader
        self.lbl_img.config(image='', text="⌛ Cargando...")
        
        # Thread
        threading.Thread(target=self._load_img_thread, args=(fname,), daemon=True).start()

    def _load_img_thread(self, fname):
        # 1. Buscar
        path = None
        mode = "FILE"
        if fname.startswith("http"):
            path = fname
            mode = "URL"
        else:
            # Buscar localmente
            clean = fname.replace("../", "").replace("./", "")
            if clean.startswith(("CAT.", "CTX.")): # Es constante JS
                self.root.after(0, lambda: self.show_img(None, f"Referencia JS: {fname}"))
                return

            for folder in self.discovered_paths:
                if not os.path.exists(folder): continue
                for ext in ['', '.avif', '.webp', '.png', '.jpg']:
                    f = os.path.join(folder, clean + ext)
                    if os.path.exists(f):
                        path = f
                        break
                if path: break
        
        if not path:
            self.root.after(0, lambda: self.show_img(None, f"No encontrado: {fname}"))
            return

        # 2. Cargar
        if path in self.image_cache:
            self.root.after(0, lambda: self.show_img(self.image_cache[path], path))
            return

        try:
            if mode == "URL":
                r = requests.get(path, timeout=3)
                pil = Image.open(io.BytesIO(r.content))
            else:
                pil = Image.open(path)
            
            # Resize
            aspect = 200 / float(pil.size[1])
            w = int(float(pil.size[0]) * aspect)
            pil = pil.resize((w, 200), Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(pil)
            
            self.image_cache[path] = tk_img
            self.root.after(0, lambda: self.show_img(tk_img, path))
            
        except Exception as e:
            self.root.after(0, lambda: self.show_img(None, "Error formato"))

    def show_img(self, tk_img, text):
        if tk_img:
            self.lbl_img.config(image=tk_img, text="")
            self.lbl_img.image = tk_img # Keep ref
            self.lbl_img_info.config(text=text[-40:])
        else:
            self.lbl_img.config(image='', text=text)
            self.lbl_img_info.config(text="")

    # ============================================================
    # CRUD
    # ============================================================
    def add_item(self):
        if not self.current_key: return
        # Crear item con TODOS los campos vacíos detectados en el esquema
        schema = self.dataset_schemas.get(self.current_key, [])
        new_item = {k: [] if k in ['tools', 'tags'] else "" for k in schema}
        new_item['title'] = "NUEVO ITEM" # Default
        
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
        for k, w in self.form_widgets.items():
            if isinstance(w, list): # Es widget de lista
                item[k] = w
            else: # Es Entry
                val = w.get().strip()
                item[k] = val
        
        self.datasets[self.current_key][self.selected_index] = item
        self.load_list()
        self.listbox.select_set(self.selected_index)

    def save_file(self):
        if not self.filepath: return
        shutil.copy(self.filepath, self.filepath + ".bak")
        
        content = self.file_content
        for name, data in self.datasets.items():
            js_str = self.py_to_js(data)
            # Reemplazar bloque entero
            regex = r"((?:const\s+|let\s+|var\s+|window\.)\s*" + name + r"\s*=\s*\[).*?(\];)"
            content = re.sub(regex, f"\\1\n{js_str}\\2", content, flags=re.DOTALL)
            
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f: f.write(content)
            self.file_content = content
            messagebox.showinfo("Guardado", "Archivo actualizado correctamente.")
        except Exception as e: messagebox.showerror("Error", str(e))

    def py_to_js(self, data):
        lines = []
        consts = ("CAT.", "CTX.", "T.", "PROJECT_CONFIG")
        for item in data:
            lines.append("  {")
            for k, v in item.items():
                if isinstance(v, list):
                    # Arrays
                    els = []
                    for x in v:
                        if x.startswith(consts): els.append(x)
                        else: els.append(f"'{x.replace("'", "\\'")}'")
                    lines.append(f"    {k}: [{', '.join(els)}],")
                else:
                    # Strings / Constantes
                    s = str(v).strip()
                    if s.startswith(consts): lines.append(f"    {k}: {s},")
                    else: lines.append(f"    {k}: '{s.replace("'", "\\'")}',")
            lines.append("  },")
        return "\n".join(lines)

if __name__ == "__main__":
    app_window = ttk.Window(themename="cyborg")
    app = UniversalDBManagerV10(app_window)
    app_window.mainloop()
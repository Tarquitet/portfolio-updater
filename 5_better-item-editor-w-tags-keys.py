import sys
import os
import subprocess
import re
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import io
import glob
import threading # IMPORTANTE: Para que no se trabe

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
from PIL import Image, ImageTk, ImageSequence
import requests

# ============================================================
# CLASE AUXILIAR: DIÁLOGO DE MULTISELECCIÓN (TAGS/TOOLS)
# ============================================================
class MultiSelectDialog(ttk.Toplevel):
    def __init__(self, parent, title, current_selection, all_options, callback):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x500")
        self.result = None
        self.callback = callback
        
        # Asegurar que todas las opciones actuales estén en la lista global
        self.all_options = sorted(list(set(all_options + current_selection)))
        self.vars = {}

        # UI del Diálogo
        ttk.Label(self, text="Selecciona opciones o añade nuevas:", font=("Arial", 10, "bold")).pack(pady=10)

        # Area de scroll para checkboxes
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="top", fill="both", expand=True, padx=10)
        scrollbar.pack(side="right", fill="y")
        
        self.populate_checkboxes(current_selection)

        # Sección Añadir Nuevo
        add_frame = ttk.Frame(self, padding=10)
        add_frame.pack(fill="x")
        self.new_entry = ttk.Entry(add_frame)
        self.new_entry.pack(side="left", fill="x", expand=True, padx=(0,5))
        ttk.Button(add_frame, text="Añadir Nuevo", command=self.add_new_option, bootstyle="info-outline").pack(side="right")

        # Botones de Acción
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill="x", side="bottom")
        ttk.Button(btn_frame, text="Cancelar", command=self.destroy, bootstyle="secondary").pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(btn_frame, text="✔ GUARDAR SELECCIÓN", command=self.save_selection, bootstyle="success").pack(side="left", expand=True, fill="x", padx=2)

        # Hacer modal
        self.transient(parent)
        self.grab_set()
        self.parent.wait_window(self)

    def populate_checkboxes(self, current_selection):
        for widget in self.scrollable_frame.winfo_children(): widget.destroy()
        self.vars = {}
        for opt in self.all_options:
            var = tk.BooleanVar(value=opt in current_selection)
            self.vars[opt] = var
            cb = ttk.Checkbutton(self.scrollable_frame, text=opt, variable=var)
            cb.pack(anchor="w", pady=2)
            
    def add_new_option(self):
        new_val = self.new_entry.get().strip()
        if new_val and new_val not in self.all_options:
            self.all_options.append(new_val)
            self.all_options.sort()
            # Re-renderizar checkboxes manteniendo selección actual
            current_state = [k for k, v in self.vars.items() if v.get()]
            self.populate_checkboxes(current_state)
            self.new_entry.delete(0, tk.END)

    def save_selection(self):
        selected = [k for k, v in self.vars.items() if v.get()]
        self.callback(selected)
        self.destroy()

# ============================================================
# CLASE PRINCIPAL
# ============================================================
class UniversalDBManagerV9:
    def __init__(self, root):
        self.root = root
        self.root.title("Tarquitet - Universal DB Editor V9 (Threaded & Smart UI)")
        self.root.geometry("1350x900")
        
        self.filepath = ""
        self.file_content = ""
        self.datasets = {} 
        # Esquemas detectados para saber qué campos tiene cada dataset
        self.dataset_schemas = {} 

        self.current_key = None 
        self.selected_index = None
        self.discovered_paths = []
        
        # Cache de imágenes para no recargar lo mismo
        self.image_cache = {} 
        self.loading_thread = None

        self.build_ui()
        # Orden de campos estándar para que se vea bonito
        self.STANDARD_SCHEMA = ['title', 'category', 'context', 'fileName', 'image', 'date', 'link', 'id', 'desc', 'tools', 'tags']
        self.smart_auto_load()

    def build_ui(self):
        main_container = ttk.Frame(self.root, padding=20)
        main_container.pack(fill="both", expand=True)

        # HEADER
        header = ttk.Frame(main_container)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="UNIVERSAL EDITOR V9", font=("Helvetica", 16, "bold"), bootstyle="primary").pack(side="left")
        
        right_head = ttk.Frame(header)
        right_head.pack(side="right")
        ttk.Button(right_head, text="📂 Abrir JS", command=self.browse_file, bootstyle="outline-secondary").pack(side="left", padx=5)
        self.lbl_file = ttk.Label(right_head, text="Esperando...", font=("Consolas", 9), bootstyle="inverse-secondary")
        self.lbl_file.pack(side="left", padx=5)

        # PANEL
        paned = ttk.PanedWindow(main_container, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # LEFT
        left_frame = ttk.Frame(paned, padding=(0,0,10,0))
        paned.add(left_frame, weight=1)

        self.dataset_selector_frame = ttk.Labelframe(left_frame, text="Datasets", padding=5)
        self.dataset_selector_frame.pack(fill="x", pady=(0, 5))
        self.lbl_no_data = ttk.Label(self.dataset_selector_frame, text="Sin datos")
        self.lbl_no_data.pack()

        list_scroll = ttk.Frame(left_frame)
        list_scroll.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_scroll)
        scrollbar.pack(side="right", fill="y")
        self.listbox = tk.Listbox(list_scroll, font=("Consolas", 10), selectmode="SINGLE", borderwidth=0)
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.listbox.yview)
        self.listbox.bind('<<ListboxSelect>>', self.on_select)

        btns = ttk.Frame(left_frame, padding=(0,10,0,0))
        btns.pack(fill="x")
        ttk.Button(btns, text="➕ NUEVO ITEM", command=self.add_item, bootstyle="success", width=12).pack(side="left", padx=2)
        ttk.Button(btns, text="➖ BORRAR", command=self.delete_item, bootstyle="danger").pack(side="left", padx=2)
        ttk.Button(btns, text="▲", width=3, command=lambda: self.move_item(-1), bootstyle="secondary").pack(side="left", padx=2)
        ttk.Button(btns, text="▼", width=3, command=lambda: self.move_item(1), bootstyle="secondary").pack(side="left", padx=2)

        # RIGHT
        right_frame = ttk.Frame(paned, padding=(10,0,0,0))
        paned.add(right_frame, weight=3)

        # PREVIEW IMAGEN (Con loader)
        self.img_frame = ttk.Labelframe(right_frame, text="Preview", padding=10, height=220)
        self.img_frame.pack(fill="x", pady=(0, 10))
        self.img_frame.pack_propagate(False)
        
        self.loading_label = ttk.Label(self.img_frame, text="⌛ Cargando...", font=("Arial", 12), bootstyle="info", anchor="center")
        self.lbl_image = ttk.Label(self.img_frame, text="...", anchor="center")
        self.lbl_image.pack(fill="both", expand=True)
        self.lbl_img_path = ttk.Label(self.img_frame, text="", font=("Arial", 7), foreground="gray")
        self.lbl_img_path.pack(side="bottom", anchor="e")

        # FORMULARIO DINÁMICO SCROLLEABLE
        self.form_canvas = tk.Canvas(right_frame, highlightthickness=0)
        self.form_scrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=self.form_canvas.yview)
        self.form_inner = ttk.Frame(self.form_canvas)
        self.form_inner.bind("<Configure>", lambda e: self.form_canvas.configure(scrollregion=self.form_canvas.bbox("all")))
        self.form_window = self.form_canvas.create_window((0, 0), window=self.form_inner, anchor="nw")
        self.form_canvas.bind("<Configure>", lambda e: self.form_canvas.itemconfig(self.form_window, width=e.width))
        self.form_canvas.configure(yscrollcommand=self.form_scrollbar.set)
        self.form_canvas.pack(side="left", fill="both", expand=True)
        self.form_scrollbar.pack(side="right", fill="y")
        
        self.form_widgets = {} # Guarda referencias a entradas y sus datos

        # ACCIONES
        action_frame = ttk.Frame(right_frame, padding=(0,10,0,0))
        action_frame.pack(fill="x", side="bottom")
        ttk.Button(action_frame, text="✔ APLICAR A MEMORIA (Enter)", command=self.save_to_memory, bootstyle="warning").pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(action_frame, text="💾 GUARDAR ARCHIVO JS", command=self.save_to_disk, bootstyle="success").pack(side="left", fill="x", expand=True, padx=2)
        
        self.root.bind('<Return>', lambda e: self.save_to_memory())

    # ============================================================
    # CARGA Y PARSEO
    # ============================================================
    def smart_auto_load(self):
        print("Escaneando archivos JS...")
        candidates = glob.glob("*.js") + glob.glob("*/*.js") + glob.glob("../js/*.js")
        best_candidate = None
        
        for path in candidates:
            if "min.js" in path and "opti" not in path: continue 
            if "utils" in path or "config" in path: continue
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    count = len(re.findall(r"(?:const\s+|let\s+|var\s+|window\.)\s*(\w+)\s*=\s*\[", content))
                    if count > 0:
                        best_candidate = path
                        break 
            except: pass
            
        if best_candidate:
            print(f"Cargando automático: {best_candidate}")
            self.load_file(os.path.abspath(best_candidate))

    def load_file(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.file_content = f.read()
            self.filepath = path
            self.lbl_file.config(text=os.path.basename(path), bootstyle="success")
            self.discover_paths_from_js(self.file_content, path)
            self.parse_all_datasets()
            self.generate_dataset_tabs()
            self.image_cache = {} # Limpiar caché al cargar nuevo archivo
        except Exception as e:
            Messagebox.show_error(str(e), "Error de Carga")

    def parse_all_datasets(self):
        self.datasets = {}
        self.dataset_schemas = {}
        regex_datasets = r"(?:const\s+|let\s+|var\s+|window\.)\s*(\w+)\s*=\s*\[(.*?)\];"
        matches = re.finditer(regex_datasets, self.file_content, re.DOTALL)
        
        for match in matches:
            var_name = match.group(1)
            raw_content = match.group(2)
            clean_content = re.sub(r"\/\/.*", "", raw_content)
            
            if "{" in clean_content:
                data = self.parse_js_array_content(clean_content)
                if data:
                    self.datasets[var_name] = data
                    # Descubrir esquema (todos los campos posibles en este dataset)
                    schema = set()
                    for item in data: schema.update(item.keys())
                    self.dataset_schemas[var_name] = list(schema)
                
    def parse_js_array_content(self, content):
        items = content.split('},')
        parsed_list = []
        for item in items:
            if not item.strip(): continue
            clean_item = item.replace('{', '').replace('}', '').strip()
            obj = {}
            props = re.findall(r"(\w+):\s*(?:'([^']*)'|\"([^\"]*)\"|([a-zA-Z0-9_.]+))", clean_item)
            for k, v1, v2, v3 in props: obj[k] = v1 or v2 or v3 
            arrays = re.findall(r"(\w+):\s*\[(.*?)\]", clean_item)
            for k, v in arrays:
                elements = [x.strip().strip("'\"") for x in v.split(',') if x.strip()]
                obj[k] = elements
            if obj: parsed_list.append(obj)
        return parsed_list

    # ============================================================
    # UI DINÁMICA Y FORMULARIO INTELIGENTE
    # ============================================================
    def generate_dataset_tabs(self):
        for widget in self.dataset_selector_frame.winfo_children(): widget.destroy()
        keys = list(self.datasets.keys())
        if not keys:
            ttk.Label(self.dataset_selector_frame, text="No se detectaron arrays válidos.").pack()
            return

        self.var_dataset = tk.StringVar(value=keys[0])
        for key in keys:
            btn = ttk.Radiobutton(self.dataset_selector_frame, text=key, variable=self.var_dataset, value=key,
                command=self.switch_dataset, bootstyle="toolbutton-outline")
            btn.pack(side="left", fill="x", expand=True, padx=2)
        self.switch_dataset()

    def switch_dataset(self):
        self.current_key = self.var_dataset.get()
        self.refresh_list()
        self.lbl_image.config(image='', text="-")
        for w in self.form_inner.winfo_children(): w.destroy()

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        data = self.datasets.get(self.current_key, [])
        for i, item in enumerate(data):
            label = item.get('title') or item.get('fileName') or f"Item {i}"
            cat = item.get('category') or "?"
            cat = cat.replace("CAT.", "").replace("CTX.", "")
            self.listbox.insert(tk.END, f"[{cat}] {label}")
        if self.selected_index is not None and self.selected_index < len(data):
             self.listbox.select_set(self.selected_index)

    def on_select(self, event):
        sel = self.listbox.curselection()
        if not sel: return
        self.selected_index = sel[0]
        item = self.datasets[self.current_key][self.selected_index]
        self.build_dynamic_form(item)
        self.trigger_image_loading(item)

    def build_dynamic_form(self, item):
        for w in self.form_inner.winfo_children(): w.destroy()
        self.form_widgets = {}
        
        # Usar el esquema completo del dataset para asegurar que aparezcan todos los campos
        schema = self.dataset_schemas.get(self.current_key, [])
        # Ordenar: primero los estándar, luego los desconocidos alfabéticamente
        keys = sorted(schema, key=lambda x: self.STANDARD_SCHEMA.index(x) if x in self.STANDARD_SCHEMA else 99 + schema.index(x))
        
        row = 0
        for key in keys:
            val = item.get(key, "") # Usar vacío si el item actual no tiene ese campo
            
            # Etiqueta
            lbl_txt = key.upper()
            if key in ['tools', 'tags']: lbl_txt += " (Lista)"
            ttk.Label(self.form_inner, text=lbl_txt, font=("Arial", 7, "bold"), foreground="#555").grid(row=row, column=0, sticky="w", padx=5, pady=(5,0))
            
            # Detector de Tipo de Campo
            is_list_field = isinstance(val, list) or key in ['tools', 'tags', 'skills']
            
            if is_list_field:
                # --- Campo de Lista (Botón de Edición) ---
                frame_list = ttk.Frame(self.form_inner)
                frame_list.grid(row=row+1, column=0, sticky="ew", padx=5, pady=(0,5))
                
                current_list_val = val if isinstance(val, list) else []
                lbl_preview = ttk.Label(frame_list, text=", ".join(current_list_val) if current_list_val else "(Vacío)", font=("Consolas", 8), wraplength=250)
                lbl_preview.pack(side="left", fill="x", expand=True)
                
                btn_edit = ttk.Button(frame_list, text="Editar Lista...", bootstyle="info-outline", width=12)
                btn_edit.pack(side="right")
                
                # Callback para abrir el diálogo modal
                def open_dialog(k=key, current=current_list_val, label_widget=lbl_preview):
                    # Recolectar todas las opciones existentes en este dataset para este campo
                    all_options = set()
                    for i in self.datasets[self.current_key]:
                        if isinstance(i.get(k), list): all_options.update(i[k])
                    
                    # Función que se ejecuta al cerrar el diálogo
                    def on_dialog_close(new_selection):
                        self.form_widgets[k]['value'] = new_selection # Actualizar valor en memoria del form
                        label_widget.config(text=", ".join(new_selection) if new_selection else "(Vacío)")
                        self.save_to_memory() # Guardar automáticamente al cerrar diálogo

                    MultiSelectDialog(self.root, f"Editar {k}", current, list(all_options), on_dialog_close)

                btn_edit.configure(command=open_dialog)
                # Guardamos el valor actual y el tipo
                self.form_widgets[key] = {'type': 'list', 'value': current_list_val}

            else:
                # --- Campo de Texto Normal ---
                entry = ttk.Entry(self.form_inner)
                entry.grid(row=row+1, column=0, sticky="ew", padx=5, pady=(0,5))
                entry.insert(0, str(val))
                self.form_widgets[key] = {'type': 'entry', 'widget': entry}

            row += 2
        self.form_inner.columnconfigure(0, weight=1)

    # ============================================================
    # 🧵 CARGA DE IMÁGENES EN HILO (NO SE TRABA)
    # ============================================================
    def trigger_image_loading(self, item):
        fname = item.get('fileName') or item.get('image')
        if not fname:
            self.set_preview_image(None, "[Sin archivo]")
            return

        # Mostrar loader inmediatamente
        self.lbl_image.pack_forget()
        self.loading_label.pack(fill="both", expand=True)
        self.lbl_img_path.config(text="Cargando...")
        
        # Cancelar hilo anterior si existe
        if self.loading_thread and self.loading_thread.is_alive():
           # No podemos matar hilos en Python fácilmente, pero podemos ignorar su resultado.
           pass

        # Iniciar nuevo hilo
        self.loading_thread = threading.Thread(target=self.load_image_thread, args=(fname,), daemon=True)
        self.loading_thread.start()

    def load_image_thread(self, fname):
        # Esta función corre en segundo plano
        path, type = self.find_image_path(fname)
        tk_img = None
        status_text = ""

        if fname in self.image_cache:
            tk_img = self.image_cache[fname]
            status_text = "Desde Caché"
            type = "CACHE"
        else:
            try:
                pil_img = None
                if type == "URL":
                    r = requests.get(path, timeout=5) # Timeout para no colgarse eternamente
                    pil_img = Image.open(io.BytesIO(r.content))
                elif type == "LOCAL":
                    pil_img = Image.open(path)
                
                if pil_img:
                    # Redimensionar
                    aspect = 220 / float(pil_img.size[1])
                    new_w = int(float(pil_img.size[0]) * aspect)
                    pil_img = pil_img.resize((new_w, 220), Image.Resampling.LANCZOS)
                    tk_img = ImageTk.PhotoImage(pil_img)
                    # Guardar en caché solo si es URL (las locales son rápidas)
                    if type == "URL": self.image_cache[fname] = tk_img
            except Exception as e:
                print(f"Error cargando imagen {fname}: {e}")
                type = "ERROR"

        # Actualizar la UI desde el hilo principal (IMPORTANTE usar root.after)
        self.root.after(0, lambda: self.set_preview_image(tk_img, fname, type))

    def set_preview_image(self, tk_img, fname, type="OK"):
        # Ocultar loader y mostrar imagen
        self.loading_label.pack_forget()
        self.lbl_image.pack(fill="both", expand=True)

        if tk_img:
            self.lbl_image.config(image=tk_img, text="")
            self.current_image_ref = tk_img # Mantener referencia para que no la borre el garbage collector
            self.lbl_img_path.config(text=f"{type}: {fname}")
        else:
            self.lbl_image.config(image='', text=f"No disponible ({type})")
            self.lbl_img_path.config(text=fname)


    # ============================================================
    # GUARDADO Y CRUD
    # ============================================================
    def save_to_memory(self):
        if self.selected_index is None: return
        new_item = {}
        for key, data in self.form_widgets.items():
            if data['type'] == 'list':
                new_item[key] = data['value'] # Valor guardado por el diálogo modal
            else:
                # Campo de texto normal
                val = data['widget'].get().strip()
                # Intento básico de detectar si el usuario escribió una lista a mano
                if "," in val and "[" not in val and key not in ['desc', 'title']:
                     new_item[key] = [x.strip() for x in val.split(',') if x.strip()]
                else:
                    new_item[key] = val
        
        self.datasets[self.current_key][self.selected_index] = new_item
        # Actualizar esquema por si se añadieron campos nuevos
        self.dataset_schemas[self.current_key].update(new_item.keys())
        
        self.refresh_list()
        # Restaurar selección y foco
        self.listbox.select_set(self.selected_index)
        self.listbox.event_generate("<<ListboxSelect>>")

    def save_to_disk(self):
        if not self.filepath: return
        shutil.copy(self.filepath, self.filepath + ".bak")
        new_content = self.file_content
        
        for var_name, data_list in self.datasets.items():
            js_string = self.py_to_js(data_list)
            pattern = r"((?:const\s+|let\s+|var\s+|window\.)\s*" + var_name + r"\s*=\s*\[).*?(\];)"
            new_content = re.sub(pattern, f"\\1\n{js_string}\\2", new_content, flags=re.DOTALL)
            
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f: f.write(new_content)
            self.file_content = new_content
            Messagebox.show_info("Archivo JS actualizado correctamente.", "Guardado")
        except Exception as e: Messagebox.show_error(str(e), "Error de Escritura")

    def py_to_js(self, data):
        lines = []
        consts = ("CAT.", "CTX.", "T.", "PROJECT_CONFIG") 
        for item in data:
            lines.append("  {")
            for k, v in item.items():
                # No guardar campos vacíos o nulos
                if v is None or v == "": continue
                if isinstance(v, list):
                    if not v: continue # No guardar listas vacías
                    els = []
                    for x in v:
                        if x.startswith(consts): els.append(x)
                        else: els.append(f"'{x.replace("'", "\\'")}'")
                    lines.append(f"    {k}: [{', '.join(els)}],")
                else:
                    s = str(v).strip()
                    if s.startswith(consts): lines.append(f"    {k}: {s},")
                    else: lines.append(f"    {k}: '{s.replace("'", "\\'")}',")
            lines.append("  },")
        return "\n".join(lines)

    # --- HELPERS DE RUTAS ---
    def discover_paths_from_js(self, content, path):
        base = os.path.dirname(path)
        self.discovered_paths = [os.path.join(base, "../assets/images"), os.path.join(base, "assets/images")]
        match = re.search(r"paths:\s*\{(.*?)\}", content, re.DOTALL)
        if match:
            raw = re.findall(r"['\"](.*?)['\"]", match.group(1))
            for p in raw:
                if len(p)>2: self.discovered_paths.append(os.path.normpath(os.path.join(base, p)))
        final = []
        for p in self.discovered_paths:
            final.append(p)
            if os.path.exists(p):
                try: final.extend([os.path.join(p,d) for d in os.listdir(p) if os.path.isdir(os.path.join(p,d))])
                except: pass
        self.discovered_paths = list(set(final))

    def find_image_path(self, filename):
        if not filename: return None, "No file"
        if filename.startswith("http"): return filename, "URL"
        clean = filename.replace("../", "").replace("./", "")
        if clean.startswith(("CAT.", "CTX.")): return None, "CONST"
        for folder in self.discovered_paths:
            if not os.path.exists(folder): continue
            for ext in ['', '.avif', '.webp', '.jpg', '.png']:
                f = os.path.join(folder, clean + ext)
                if os.path.exists(f): return f, "LOCAL"
        return None, "404"

    # --- CRUD ---
    def browse_file(self):
        f = filedialog.askopenfilename(filetypes=[("JS", "*.js")])
        if f: self.load_file(f)
    def add_item(self):
        if not self.current_key: return
        # Crear item vacío pero se llenará con el esquema al seleccionarlo
        self.datasets[self.current_key].insert(0, {'title': 'NUEVO ITEM', 'category': 'CAT.DEV'})
        self.refresh_list()
        self.listbox.select_set(0)
        self.on_select(None) # Disparar selección para construir el form
    def delete_item(self):
        if self.selected_index is None: return
        del self.datasets[self.current_key][self.selected_index]
        self.selected_index = None; self.refresh_list(); self.set_preview_image(None, "")
    def move_item(self, d):
        if self.selected_index is None: return
        i = self.selected_index; n = i + d
        l = self.datasets[self.current_key]
        if 0 <= n < len(l):
            l[i], l[n] = l[n], l[i]
            self.refresh_list(); self.listbox.select_set(n); self.selected_index = n

if __name__ == "__main__":
    # Usar un tema más moderno
    app_window = ttk.Window(themename="superhero") 
    app = UniversalDBManagerV9(app_window)
    app_window.mainloop()
import sys
import os
import subprocess
import re
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import io
import glob

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
from PIL import Image, ImageTk
import requests

class UniversalDBManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Tarquitet - Universal DB Manager")
        self.root.geometry("1300x850")
        
        # --- ESTADO DINÁMICO ---
        self.filepath = ""
        self.file_content = ""
        
        # Diccionario principal: { "mainPortfolio": [...], "galleryData": [...] }
        self.datasets = {} 
        
        # Clave actual seleccionada (ej: "mainPortfolio")
        self.current_key = None 
        
        self.selected_index = None
        self.current_image_ref = None 
        self.discovered_paths = []
        
        self.build_ui()
        self.smart_auto_load()

    def build_ui(self):
        main_container = ttk.Frame(self.root, padding=20)
        main_container.pack(fill="both", expand=True)

        # HEADER
        header = ttk.Frame(main_container)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="UNIVERSAL DATA MANAGER", font=("Helvetica", 16, "bold"), bootstyle="primary").pack(side="left")
        
        right_head = ttk.Frame(header)
        right_head.pack(side="right")
        ttk.Button(right_head, text="📂 Buscar JS Manual", command=self.browse_file, bootstyle="outline-secondary").pack(side="left", padx=5)
        self.lbl_file = ttk.Label(right_head, text="Esperando archivo...", font=("Consolas", 9), bootstyle="inverse-secondary")
        self.lbl_file.pack(side="left", padx=5)

        # PANEL PRINCIPAL
        paned = ttk.PanedWindow(main_container, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # === IZQUIERDA: LISTA Y SELECTOR ===
        left_frame = ttk.Frame(paned, padding=(0,0,10,0))
        paned.add(left_frame, weight=1)

        # 1. SELECTOR DINÁMICO DE DATASETS (TABS)
        # Aquí se generarán botones según las variables encontradas en el JS
        self.dataset_selector_frame = ttk.Labelframe(left_frame, text="Datasets Encontrados", padding=5)
        self.dataset_selector_frame.pack(fill="x", pady=(0, 5))
        
        # Placeholder si no hay datos
        self.lbl_no_data = ttk.Label(self.dataset_selector_frame, text="Carga un archivo JS para ver datos")
        self.lbl_no_data.pack()

        # 2. LISTA DE ITEMS
        list_scroll = ttk.Frame(left_frame)
        list_scroll.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_scroll)
        scrollbar.pack(side="right", fill="y")
        self.listbox = tk.Listbox(list_scroll, font=("Consolas", 10), selectmode="SINGLE", borderwidth=0)
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.listbox.yview)
        self.listbox.bind('<<ListboxSelect>>', self.on_select)

        # 3. CONTROLES CRUD
        btns = ttk.Frame(left_frame, padding=(0,10,0,0))
        btns.pack(fill="x")
        ttk.Button(btns, text="➕", width=4, command=self.add_item, bootstyle="success").pack(side="left", padx=2)
        ttk.Button(btns, text="➖", width=4, command=self.delete_item, bootstyle="danger").pack(side="left", padx=2)
        ttk.Button(btns, text="▲", width=4, command=lambda: self.move_item(-1), bootstyle="secondary").pack(side="left", padx=2)
        ttk.Button(btns, text="▼", width=4, command=lambda: self.move_item(1), bootstyle="secondary").pack(side="left", padx=2)

        # === DERECHA: EDICIÓN ===
        right_frame = ttk.Frame(paned, padding=(10,0,0,0))
        paned.add(right_frame, weight=3)

        # PREVIEW IMAGEN
        self.img_frame = ttk.Labelframe(right_frame, text="Vista Previa", padding=10, height=220)
        self.img_frame.pack(fill="x", pady=(0, 10))
        self.img_frame.pack_propagate(False)
        self.lbl_image = ttk.Label(self.img_frame, text="...", anchor="center")
        self.lbl_image.pack(fill="both", expand=True)
        self.lbl_img_path = ttk.Label(self.img_frame, text="", font=("Arial", 7), foreground="gray")
        self.lbl_img_path.pack(side="bottom", anchor="e")

        # FORMULARIO DINÁMICO
        self.form_canvas = tk.Canvas(right_frame, highlightthickness=0)
        self.form_scrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=self.form_canvas.yview)
        self.form_inner = ttk.Frame(self.form_canvas)

        self.form_inner.bind(
            "<Configure>",
            lambda e: self.form_canvas.configure(scrollregion=self.form_canvas.bbox("all"))
        )
        self.form_window = self.form_canvas.create_window((0, 0), window=self.form_inner, anchor="nw")
        
        # Resize canvas with window
        self.form_canvas.bind("<Configure>", lambda e: self.form_canvas.itemconfig(self.form_window, width=e.width))

        self.form_canvas.configure(yscrollcommand=self.form_scrollbar.set)
        
        self.form_canvas.pack(side="left", fill="both", expand=True)
        self.form_scrollbar.pack(side="right", fill="y")

        # Diccionario para guardar referencias a los inputs generados dinámicamente
        self.form_entries = {} 

        # ACCIONES
        action_frame = ttk.Frame(right_frame, padding=(0,10,0,0))
        action_frame.pack(fill="x", side="bottom")
        ttk.Button(action_frame, text="✔ APLICAR CAMBIOS", command=self.save_to_memory, bootstyle="warning").pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(action_frame, text="💾 GUARDAR ARCHIVO", command=self.save_to_disk, bootstyle="success").pack(side="left", fill="x", expand=True, padx=2)

    # ============================================================
    # 🧠 LÓGICA DE AUTO-DESCUBRIMIENTO (EL CEREBRO)
    # ============================================================
    def smart_auto_load(self):
        """Escanea la carpeta actual y subcarpetas buscando archivos JS con arrays de datos."""
        print("Iniciando escaneo inteligente...")
        
        # Buscar todos los .js en la carpeta actual y 1 nivel abajo
        candidates = glob.glob("*.js") + glob.glob("*/*.js") + glob.glob("../js/*.js")
        
        best_candidate = None
        max_arrays_found = 0
        
        for path in candidates:
            # Ignorar librerías y minificados ilegibles (opcional)
            if "min.js" in path and "opti" not in path: continue 
            if "utils" in path or "config" in path: continue
            
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Contamos cuántos arrays potenciales tiene
                    # Busca patrones como: const X = [ {  o  window.X = [ {
                    count = len(re.findall(r"(?:const|window\.|let|var)\s+(\w+)\s*=\s*\[\s*\{", content))
                    
                    if count > max_arrays_found:
                        max_arrays_found = count
                        best_candidate = path
            except: pass
            
        if best_candidate:
            print(f"Mejor candidato encontrado: {best_candidate} ({max_arrays_found} datasets)")
            self.load_file(os.path.abspath(best_candidate))
        else:
            messagebox.showinfo("Info", "No se encontraron archivos JS de datos automáticamente.\nPor favor carga uno manualmente.")

    def load_file(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.file_content = f.read()
            self.filepath = path
            self.lbl_file.config(text=os.path.basename(path), bootstyle="success")
            
            # 1. Descubrir Rutas de Imágenes (para el preview)
            self.discover_paths_from_js(self.file_content, path)
            
            # 2. Parsear TODOS los datasets encontrados
            self.parse_all_datasets()
            
            # 3. Generar Botones de Datasets
            self.generate_dataset_tabs()
            
        except Exception as e:
            messagebox.showerror("Error de Carga", str(e))

    def parse_all_datasets(self):
        """Busca CUALQUIER variable que sea un array de objetos."""
        self.datasets = {}
        
        # Regex Maestra: Captura el nombre de la variable y su contenido [...]
        # Soporta: const name = [...], window.name = [...], let name = [...]
        regex_datasets = r"(?:const|window\.|let|var)\s+(\w+)\s*=\s*\[(.*?)\];"
        
        matches = re.finditer(regex_datasets, self.file_content, re.DOTALL)
        
        for match in matches:
            var_name = match.group(1)
            raw_content = match.group(2)
            
            # Verificación simple: ¿Parece un array de objetos?
            if "{" in raw_content and "}" in raw_content:
                print(f"Dataset detectado: {var_name}")
                data = self.parse_js_array_content(raw_content)
                self.datasets[var_name] = data
                
    def parse_js_array_content(self, content):
        """Convierte el string interno del JS a lista de dicts Python."""
        items = content.split('},')
        parsed_list = []
        for item in items:
            if not item.strip(): continue
            clean_item = item.replace('{', '').replace('}', '').strip()
            
            obj = {}
            # Captura clave: valor (soportando constantes sin comillas)
            props = re.findall(r"(\w+):\s*(?:'([^']*)'|\"([^\"]*)\"|([a-zA-Z0-9_.]+))", clean_item)
            for k, v1, v2, v3 in props:
                obj[k] = v1 or v2 or v3
                
            # Captura arrays internos (tools: [...])
            arrays = re.findall(r"(\w+):\s*\[(.*?)\]", clean_item)
            for k, v in arrays:
                elements = [x.strip().strip("'\"") for x in v.split(',') if x.strip()]
                obj[k] = elements
                
            if obj: parsed_list.append(obj)
        return parsed_list

    # ============================================================
    # 🎨 UI DINÁMICA
    # ============================================================
    def generate_dataset_tabs(self):
        # Limpiar botones anteriores
        for widget in self.dataset_selector_frame.winfo_children():
            widget.destroy()
            
        keys = list(self.datasets.keys())
        if not keys:
            ttk.Label(self.dataset_selector_frame, text="No se encontraron arrays.").pack()
            return

        # Variable de control
        self.var_dataset = tk.StringVar(value=keys[0])
        
        # Crear un botón por cada dataset encontrado
        for key in keys:
            btn = ttk.Radiobutton(
                self.dataset_selector_frame, 
                text=key, # Nombre de la variable (ej: "mainPortfolio")
                variable=self.var_dataset, 
                value=key,
                command=self.switch_dataset,
                bootstyle="toolbutton-outline"
            )
            btn.pack(side="left", fill="x", expand=True, padx=2)
            
        self.switch_dataset()

    def switch_dataset(self):
        self.current_key = self.var_dataset.get()
        self.refresh_list()
        self.lbl_image.config(image='', text="Selecciona un item")
        # Limpiar formulario
        for widget in self.form_inner.winfo_children(): widget.destroy()

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        data = self.datasets.get(self.current_key, [])
        for i, item in enumerate(data):
            # Intentar encontrar un título o nombre para mostrar
            label = item.get('title') or item.get('name') or item.get('fileName') or f"Item {i}"
            cat = item.get('category') or item.get('type') or "?"
            self.listbox.insert(tk.END, f"[{cat}] {label}")

    def on_select(self, event):
        sel = self.listbox.curselection()
        if not sel: return
        self.selected_index = sel[0]
        item = self.datasets[self.current_key][self.selected_index]
        
        self.build_dynamic_form(item)
        self.load_image_preview(item)

    def build_dynamic_form(self, item):
        """Crea campos de texto basados en las claves del objeto."""
        for widget in self.form_inner.winfo_children(): widget.destroy()
        self.form_entries = {}
        
        # Ordenar claves: poner title, category, filename primero
        keys = list(item.keys())
        priority = ['title', 'category', 'context', 'fileName', 'date', 'link']
        keys.sort(key=lambda x: priority.index(x) if x in priority else 99)
        
        row = 0
        for key in keys:
            val = item[key]
            
            lbl = ttk.Label(self.form_inner, text=key.upper(), font=("Arial", 7, "bold"), foreground="#555")
            lbl.grid(row=row, column=0, sticky="w", padx=5, pady=(5,0))
            
            entry = ttk.Entry(self.form_inner)
            entry.grid(row=row+1, column=0, sticky="ew", padx=5, pady=(0,5))
            
            # Si es lista, unir con comas
            if isinstance(val, list):
                entry.insert(0, ", ".join(val))
            else:
                entry.insert(0, str(val))
                
            self.form_entries[key] = entry
            row += 2
            
        self.form_inner.columnconfigure(0, weight=1)

    # ============================================================
    # 💾 GUARDADO UNIVERSAL
    # ============================================================
    def save_to_memory(self):
        if self.selected_index is None or not self.current_key: return
        
        new_item = {}
        for key, entry in self.form_entries.items():
            val = entry.get().strip()
            # Detectar si era lista originalmente o si contiene comas
            # (Heurística simple: si tiene comas, es lista. Si no, string)
            if "," in val:
                new_item[key] = [x.strip() for x in val.split(',') if x.strip()]
            else:
                new_item[key] = val
        
        self.datasets[self.current_key][self.selected_index] = new_item
        self.refresh_list()
        self.listbox.select_set(self.selected_index)
        self.load_image_preview(new_item)

    def save_to_disk(self):
        if not self.filepath: return
        shutil.copy(self.filepath, self.filepath + ".bak")
        
        new_content = self.file_content
        
        # Reconstruir y reemplazar cada dataset encontrado
        for var_name, data_list in self.datasets.items():
            js_string = self.py_to_js(data_list)
            # Regex segura para reemplazar solo el contenido del array específico
            pattern = r"((?:const|window\.|let|var)\s+" + var_name + r"\s*=\s*\[).*?(\];)"
            new_content = re.sub(pattern, f"\\1\n{js_string}\\2", new_content, flags=re.DOTALL)
            
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f: f.write(new_content)
            self.file_content = new_content
            messagebox.showinfo("Guardado", "Archivo JS actualizado con todos los datasets.")
        except Exception as e: messagebox.showerror("Error", str(e))

    def py_to_js(self, data):
        lines = []
        const_patterns = ("CAT.", "CTX.", "T.", "PROJECT_CONFIG") # Patrones de constantes conocidas
        for item in data:
            lines.append("  {")
            for k, v in item.items():
                if isinstance(v, list):
                    # Arrays: Revisar si los elementos son constantes o strings
                    els = []
                    for x in v:
                        if x.startswith(const_patterns): els.append(x)
                        else: els.append(f"'{x}'")
                    lines.append(f"    {k}: [{', '.join(els)}],")
                else:
                    # Strings: Revisar si es constante
                    s = str(v).strip()
                    if s.startswith(const_patterns): lines.append(f"    {k}: {s},")
                    else: lines.append(f"    {k}: '{s.replace("'", "\\'")}',")
            lines.append("  },")
        return "\n".join(lines)

    # --- RUTAS E IMÁGENES (IDÉNTICO A V7) ---
    def discover_paths_from_js(self, content, path):
        # ... (Código de descubrimiento igual al anterior) ...
        # Copia la lógica de V7 aquí o usa la simplificada abajo:
        base_dir = os.path.dirname(path)
        self.discovered_paths = [
            os.path.join(base_dir, "assets/images"),
            os.path.join(base_dir, "../assets/images")
        ]
        # Regex para buscar 'paths': { ... }
        match = re.search(r"paths:\s*\{(.*?)\}", content, re.DOTALL)
        if match:
            raw_paths = re.findall(r"['\"](.*?)['\"]", match.group(1))
            for p in raw_paths:
                if len(p) > 2: self.discovered_paths.append(os.path.normpath(os.path.join(base_dir, p)))
        
        # Expandir subcarpetas
        expanded = []
        for p in self.discovered_paths:
            expanded.append(p)
            if os.path.exists(p):
                try: expanded.extend([os.path.join(p, d) for d in os.listdir(p) if os.path.isdir(os.path.join(p, d))])
                except: pass
        self.discovered_paths = list(set(expanded))

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

    def load_image_preview(self, item):
        fname = item.get('fileName') or item.get('image')
        path, type = self.find_image_path(fname)
        
        if type == "URL":
            try:
                r = requests.get(path, timeout=1)
                img = Image.open(io.BytesIO(r.content))
            except: img = None
        elif type == "LOCAL":
            img = Image.open(path)
        else:
            self.lbl_image.config(image='', text=f"No imagen ({type})")
            self.lbl_img_path.config(text=fname)
            return

        if img:
            aspect = 220 / float(img.size[1])
            new_w = int(float(img.size[0]) * aspect)
            img = img.resize((new_w, 220), Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(img)
            self.lbl_image.config(image=tk_img, text="")
            self.current_image_ref = tk_img
            self.lbl_img_path.config(text=path if type == "LOCAL" else "URL Externa")

    # --- CRUD ---
    def browse_file(self):
        f = filedialog.askopenfilename(filetypes=[("Javascript", "*.js")])
        if f: self.load_file(f)
    def add_item(self):
        if not self.current_key: return
        self.datasets[self.current_key].insert(0, {'title': 'NUEVO ITEM'})
        self.refresh_list(); self.listbox.select_set(0); self.on_select(None)
    def delete_item(self):
        if self.selected_index is None: return
        del self.datasets[self.current_key][self.selected_index]
        self.selected_index = None; self.refresh_list(); self.lbl_image.config(image='', text="-")
    def move_item(self, d):
        if self.selected_index is None: return
        i = self.selected_index; n = i + d
        l = self.datasets[self.current_key]
        if 0 <= n < len(l):
            l[i], l[n] = l[n], l[i]
            self.refresh_list(); self.listbox.select_set(n); self.selected_index = n

if __name__ == "__main__":
    app_window = ttk.Window(themename="darkly") 
    app = UniversalDBManager(app_window)
    app_window.mainloop()
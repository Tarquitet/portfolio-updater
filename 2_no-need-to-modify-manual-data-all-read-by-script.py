import sys
import os
import subprocess
import re
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import io

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

class ProjectDBManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Tarquitet - DB Manager (Auto-Discovery Mode)")
        self.root.geometry("1200x850")
        
        self.filepath = ""
        self.file_content = ""
        self.portfolio_data = [] 
        self.gallery_data = []   
        self.current_list = "PORTFOLIO" 
        self.selected_index = None
        self.current_image_ref = None 
        
        # Lista dinámica (se llenará al leer el JS)
        self.discovered_paths = []
        
        self.build_ui()
        self.auto_load_file()

    def build_ui(self):
        main_container = ttk.Frame(self.root, padding=20)
        main_container.pack(fill="both", expand=True)

        # Header con info de rutas
        header = ttk.Frame(main_container)
        header.pack(fill="x", pady=(0, 15))
        ttk.Label(header, text="VISUAL ASSET MANAGER V7", font=("Helvetica", 16, "bold"), bootstyle="primary").pack(side="left")
        
        right_header = ttk.Frame(header)
        right_header.pack(side="right")
        ttk.Button(right_header, text="📂 Cargar JS", command=self.browse_file, bootstyle="outline-primary").pack(side="right", padx=5)
        self.lbl_path = ttk.Label(right_header, text="...", font=("Arial", 9))
        self.lbl_path.pack(side="right", padx=10)
        
        # Indicador de rutas detectadas
        self.lbl_routes = ttk.Label(main_container, text="Rutas detectadas: 0", font=("Consolas", 8), foreground="gray")
        self.lbl_routes.pack(anchor="e", pady=(0,5))

        paned = ttk.PanedWindow(main_container, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # LEFT
        left_frame = ttk.Frame(paned, padding=(0,0,10,0))
        paned.add(left_frame, weight=1)

        self.list_type_var = tk.StringVar(value="PORTFOLIO")
        sel_frame = ttk.Frame(left_frame)
        sel_frame.pack(fill="x", pady=5)
        ttk.Radiobutton(sel_frame, text="Portfolio", variable=self.list_type_var, value="PORTFOLIO", command=self.switch_list_type, bootstyle="toolbutton-primary").pack(side="left", fill="x", expand=True)
        ttk.Radiobutton(sel_frame, text="Galería", variable=self.list_type_var, value="GALLERY", command=self.switch_list_type, bootstyle="toolbutton-info").pack(side="left", fill="x", expand=True)

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
        ttk.Button(btns, text="+", width=3, command=self.add_item, bootstyle="success").pack(side="left", padx=2)
        ttk.Button(btns, text="-", width=3, command=self.delete_item, bootstyle="danger").pack(side="left", padx=2)
        ttk.Button(btns, text="▲", width=3, command=lambda: self.move_item(-1)).pack(side="left", padx=2)
        ttk.Button(btns, text="▼", width=3, command=lambda: self.move_item(1)).pack(side="left", padx=2)

        # RIGHT
        right_frame = ttk.Frame(paned, padding=(10,0,0,0))
        paned.add(right_frame, weight=3)

        self.img_frame = ttk.Labelframe(right_frame, text="Vista Previa", padding=10, height=250)
        self.img_frame.pack(fill="x", pady=(0, 10))
        self.img_frame.pack_propagate(False)

        self.lbl_image = ttk.Label(self.img_frame, text="Sin Imagen", anchor="center")
        self.lbl_image.pack(fill="both", expand=True)
        self.lbl_img_status = ttk.Label(self.img_frame, text="", font=("Arial", 8), foreground="gray")
        self.lbl_img_status.pack(side="bottom", anchor="e")

        form_frame = ttk.Labelframe(right_frame, text="Datos", padding=10)
        form_frame.pack(fill="both", expand=True)

        self.fields = {}
        keys = [("Título", "title", 0), ("Categoría", "category", 0),
                ("Nombre Archivo", "fileName", 1), ("Enlace", "link", 1),
                ("Descripción", "desc", 2), ("Contexto", "context", 2),
                ("Fecha", "date", 3), ("ID Youtube", "id", 3)]
        
        for label, key, row in keys:
            col = 0 if keys.index((label, key, row)) % 2 == 0 else 2
            ttk.Label(form_frame, text=label, font=("Arial", 8, "bold")).grid(row=row*2, column=col, sticky="w", padx=5)
            entry = ttk.Entry(form_frame)
            entry.grid(row=row*2+1, column=col, sticky="ew", padx=5, pady=(0, 10))
            self.fields[key] = entry

        ttk.Label(form_frame, text="Herramientas [Tools]", font=("Arial", 8, "bold"), foreground="#3498db").grid(row=8, column=0, sticky="w", padx=5)
        self.entry_tools = ttk.Entry(form_frame)
        self.entry_tools.grid(row=9, column=0, columnspan=3, sticky="ew", padx=5, pady=(0, 10))

        ttk.Label(form_frame, text="Etiquetas [Tags]", font=("Arial", 8, "bold"), foreground="#9b59b6").grid(row=10, column=0, sticky="w", padx=5)
        self.entry_tags = ttk.Entry(form_frame)
        self.entry_tags.grid(row=11, column=0, columnspan=3, sticky="ew", padx=5)

        form_frame.columnconfigure(0, weight=1)
        form_frame.columnconfigure(2, weight=1)

        action_frame = ttk.Frame(right_frame, padding=(0, 10, 0, 0))
        action_frame.pack(fill="x", side="bottom")
        ttk.Button(action_frame, text="✔ Aplicar (Memoria)", command=self.save_item, bootstyle="warning").pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(action_frame, text="💾 GUARDAR JS", command=self.save_to_file, bootstyle="success").pack(side="left", fill="x", expand=True, padx=5)

    # ============================================================
    # 🧠 SISTEMA DE AUTO-DESCUBRIMIENTO DE RUTAS
    # ============================================================
    def discover_paths_from_js(self, content, js_file_path):
        """Lee el objeto PROJECT_CONFIG del JS y calcula rutas reales en disco."""
        
        # 1. Encontrar el bloque paths: { ... }
        # Busca "paths:" seguido de "{" y captura lo de adentro hasta "}"
        # Funciona con 'paths: {' y 'paths:{' (minificado)
        match = re.search(r"paths:\s*\{(.*?)\}", content, re.DOTALL)
        
        detected_paths = []
        base_dir = os.path.dirname(js_file_path) # Carpeta donde está el .js
        
        if match:
            inner_block = match.group(1)
            # Extraer todo lo que parezca una ruta (cadena de texto)
            # Busca 'ruta' o "ruta"
            raw_paths = re.findall(r"['\"](.*?)['\"]", inner_block)
            
            for p in raw_paths:
                # Filtrar basura corta o claves
                if len(p) > 2 and "/" in p:
                    # Convertir ruta relativa (../assets) a absoluta del sistema
                    # os.path.normpath resuelve los ".." automáticamente
                    full_path = os.path.normpath(os.path.join(base_dir, p))
                    if full_path not in detected_paths:
                        detected_paths.append(full_path)
        
        # Fallback: Si falla el regex o no hay config, agregar rutas estándar relativas al JS
        fallback_dirs = ["../assets/images", "./assets/images"]
        for d in fallback_dirs:
            p = os.path.normpath(os.path.join(base_dir, d))
            if p not in detected_paths:
                detected_paths.append(p)
                
        # Subcarpetas comunes (dev, design, etc) se buscan automáticamente 
        # si la ruta base existe
        final_list = []
        for p in detected_paths:
            final_list.append(p)
            if os.path.exists(p):
                # Agregar subcarpetas de primer nivel automáticamente
                try:
                    subs = [os.path.join(p, d) for d in os.listdir(p) if os.path.isdir(os.path.join(p, d))]
                    final_list.extend(subs)
                except: pass
        
        self.discovered_paths = list(set(final_list)) # Eliminar duplicados
        self.lbl_routes.config(text=f"Rutas de imagen activas: {len(self.discovered_paths)}")
        print("Rutas detectadas:", self.discovered_paths)

    def find_image_path(self, filename):
        if not filename: return None, "No filename"
        if filename.startswith("http"): return filename, "URL"
        
        clean_name = filename.replace("../", "").replace("./", "")
        # Si es constante JS (CAT.DEV), ignorar
        if clean_name.startswith(("CAT.", "CTX.", "T.")): return None, "CONSTANT"
        
        extensions = ['', '.avif', '.webp', '.jpg', '.png', '.jpeg']
        
        # USAR LAS RUTAS DESCUBIERTAS
        for folder in self.discovered_paths:
            if not os.path.exists(folder): continue
            
            for ext in extensions:
                potential_path = os.path.join(folder, clean_name + ext)
                if os.path.exists(potential_path) and os.path.isfile(potential_path):
                    return potential_path, "LOCAL"
        return None, "NOT FOUND"

    # ============================================================
    # PARSING JS (HÍBRIDO: OPTIMIZADO + CLÁSICO)
    # ============================================================
    def extract_js_array(self, var_name, content):
        # Regex mejorada para soportar minificados y espacios variados
        pattern = re.compile(r"(?:const|window\.)\s+" + var_name + r"\s*=\s*\[(.*?)\];", re.DOTALL)
        match = pattern.search(content)
        if not match: return []
        
        raw_items = match.group(1).split('},')
        parsed = []
        for item in raw_items:
            if not item.strip(): continue
            d = {}
            clean = item.replace('{', '').replace('}', '').strip()
            
            # Captura clave: valor (con o sin comillas)
            # Grupo 1: Clave
            # Grupo 2: Valor '...'
            # Grupo 3: Valor "..."
            # Grupo 4: Valor Constante (CAT.DEV)
            matches = re.findall(r"(\w+):\s*(?:'([^']*)'|\"([^\"]*)\"|([a-zA-Z0-9_.]+))", clean)
            
            for k, v1, v2, v3 in matches:
                d[k] = v1 or v2 or v3

            # Captura Arrays [ ... ]
            array_matches = re.findall(r"(\w+):\s*\[(.*?)\]", clean)
            for k, v in array_matches:
                raw_elements = v.split(',')
                clean_elements = []
                for el in raw_elements:
                    el = el.strip()
                    if not el: continue
                    if (el.startswith("'") and el.endswith("'")) or (el.startswith('"') and el.endswith('"')):
                        clean_elements.append(el[1:-1])
                    else:
                        clean_elements.append(el)
                d[k] = clean_elements
                
            if d: parsed.append(d)
        return parsed

    def load_file(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.file_content = f.read()
            self.filepath = path
            self.lbl_path.config(text=os.path.basename(path), bootstyle="success")
            
            # 1. AUTODESCUBRIR RUTAS
            self.discover_paths_from_js(self.file_content, path)
            
            # 2. PARSEAR DATOS
            self.portfolio_data = self.extract_js_array("mainPortfolio", self.file_content)
            self.gallery_data = self.extract_js_array("galleryData", self.file_content)
            
            self.refresh_list()
            messagebox.showinfo("Listo", "Archivo cargado y rutas escaneadas.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # --- RESTO IGUAL (UI HELPERS) ---
    def load_image_preview(self, item):
        filename = item.get('fileName') or item.get('image')
        if not filename:
            self.lbl_image.config(image='', text="[Sin archivo]")
            self.lbl_img_status.config(text="")
            return

        path, source_type = self.find_image_path(filename)
        
        if source_type == "CONSTANT":
            self.lbl_image.config(image='', text="[Variable JS]")
            self.lbl_img_status.config(text=filename)
            return

        try:
            pil_image = None
            if source_type == "URL":
                self.lbl_img_status.config(text="🌐 Descargando...")
                self.root.update()
                try:
                    response = requests.get(path, timeout=2)
                    pil_image = Image.open(io.BytesIO(response.content))
                except:
                    self.lbl_image.config(image='', text="Error URL")
                    return
            elif source_type == "LOCAL":
                self.lbl_img_status.config(text=f"📂 {os.path.basename(path)}")
                pil_image = Image.open(path)
            else:
                self.lbl_image.config(image='', text=f"❌ No encontrado")
                self.lbl_img_status.config(text=f"{filename}")
                return

            if pil_image:
                base_height = 220
                w_percent = (base_height / float(pil_image.size[1]))
                w_size = int((float(pil_image.size[0]) * float(w_percent)))
                pil_image = pil_image.resize((w_size, base_height), Image.Resampling.LANCZOS)
                tk_img = ImageTk.PhotoImage(pil_image)
                self.lbl_image.config(image=tk_img, text="")
                self.current_image_ref = tk_img
        except:
            self.lbl_image.config(image='', text="Error Formato")

    # (Funciones CRUD y Save idénticas a V6, solo cambia load_file y discover_paths)
    def auto_load_file(self):
        paths = ["projects-opti.js", "projects.js", "js/projects.js"]
        for p in paths:
            if os.path.exists(p): self.load_file(os.path.abspath(p)); return
    def browse_file(self):
        f = filedialog.askopenfilename(filetypes=[("Javascript", "*.js")]); 
        if f: self.load_file(f)
    def on_select(self, e):
        sel = self.listbox.curselection()
        if not sel: return
        item = (self.portfolio_data if self.current_list == "PORTFOLIO" else self.gallery_data)[sel[0]]
        self.selected_index = sel[0]
        for k, v in self.fields.items():
            v.delete(0, tk.END); v.insert(0, str(item.get(k, '')))
        self.entry_tools.delete(0, tk.END); self.entry_tools.insert(0, ", ".join(item.get('tools', [])))
        self.entry_tags.delete(0, tk.END); self.entry_tags.insert(0, ", ".join(item.get('tags', [])))
        self.load_image_preview(item)
    def switch_list_type(self):
        self.current_list = self.list_type_var.get()
        self.refresh_list()
        self.lbl_image.config(image='', text="-")
    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        d = self.portfolio_data if self.current_list == "PORTFOLIO" else self.gallery_data
        for i in d: self.listbox.insert(tk.END, f"[{i.get('category','?')}] {i.get('title','?')}")
    def save_item(self):
        if self.selected_index is None: return
        new = {}
        for k, v in self.fields.items(): 
            if v.get().strip(): new[k] = v.get().strip()
        if self.entry_tools.get().strip(): new['tools'] = [x.strip() for x in self.entry_tools.get().split(',')]
        if self.entry_tags.get().strip(): new['tags'] = [x.strip() for x in self.entry_tags.get().split(',')]
        target = self.portfolio_data if self.current_list == "PORTFOLIO" else self.gallery_data
        target[self.selected_index] = new
        self.refresh_list(); self.listbox.select_set(self.selected_index); self.load_image_preview(new)
    def add_item(self):
        target = self.portfolio_data if self.current_list == "PORTFOLIO" else self.gallery_data
        target.insert(0, {'title': 'NUEVO', 'category': 'DEV'})
        self.refresh_list(); self.listbox.select_set(0); self.on_select(None)
    def delete_item(self):
        if self.selected_index is None: return
        target = self.portfolio_data if self.current_list == "PORTFOLIO" else self.gallery_data
        del target[self.selected_index]; self.selected_index = None; self.refresh_list(); self.lbl_image.config(image='', text="-")
    def move_item(self, d):
        if self.selected_index is None: return
        idx = self.selected_index
        t = self.portfolio_data if self.current_list == "PORTFOLIO" else self.gallery_data
        n = idx + d
        if 0 <= n < len(t):
            t[idx], t[n] = t[n], t[idx]; self.refresh_list(); self.listbox.select_set(n); self.selected_index = n
    def py_to_js(self, data):
        lines = []
        consts = ("CAT.", "CTX.", "T.", "PROJECT_CONFIG")
        for item in data:
            lines.append("  {")
            for k, v in item.items():
                if isinstance(v, list): 
                    els = [x if x.startswith(consts) else f"'{x}'" for x in v]
                    lines.append(f"    {k}: [{', '.join(els)}],")
                else:
                    s = str(v).strip()
                    val = s if s.startswith(consts) else f"'{s.replace("'", "\\'")}'"
                    lines.append(f"    {k}: {val},")
            lines.append("  },")
        return "\n".join(lines)
    def save_to_file(self):
        if not self.filepath: return
        shutil.copy(self.filepath, self.filepath + ".bak")
        jp = self.py_to_js(self.portfolio_data); jg = self.py_to_js(self.gallery_data)
        nc = re.sub(r"((?:const|window\.)\s+mainPortfolio\s*=\s*\[).*?(\];)", f"\\1\n{jp}\\2", self.file_content, flags=re.DOTALL)
        nc = re.sub(r"((?:const|window\.)\s+galleryData\s*=\s*\[).*?(\];)", f"\\1\n{jg}\\2", nc, flags=re.DOTALL)
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f: f.write(nc)
            self.file_content = nc
            messagebox.showinfo("Guardado", "Archivo actualizado.")
        except Exception as e: messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    app_window = ttk.Window(themename="darkly") 
    app = ProjectDBManager(app_window)
    app_window.mainloop()
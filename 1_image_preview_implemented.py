import sys
import os
import subprocess
import re
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import io

# --- 1. AUTO-INSTALADOR CON SOPORTE DE IMÁGENES ---
def setup_dependencies():
    """Descarga librerías para GUI moderna y manejo de imágenes."""
    required_libs = {
        'ttkbootstrap': 'ttkbootstrap',
        'Pillow': 'PIL',   # Para manipular imágenes
        'requests': 'requests' # Para descargar imágenes web
    }
    
    installed = False
    for package, import_name in required_libs.items():
        try:
            __import__(import_name)
        except ImportError:
            print(f"[SISTEMA] Instalando {package}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                installed = True
            except Exception as e:
                print(f"[ERROR] Falló instalación de {package}: {e}")

    if installed:
        print("[SISTEMA] Reiniciando...")
        os.execv(sys.executable, ['python'] + sys.argv)

setup_dependencies()

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from PIL import Image, ImageTk
import requests

class ProjectDBManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Tarquitet - DB Visual Manager")
        self.root.geometry("1200x800")
        
        # Estado
        self.filepath = ""
        self.file_content = ""
        self.portfolio_data = [] 
        self.gallery_data = []   
        self.current_list = "PORTFOLIO" 
        self.selected_index = None
        self.current_image_ref = None # Referencia para evitar Garbage Collection
        
        # Rutas de búsqueda de imágenes (ajusta si tu estructura cambia)
        self.image_search_paths = [
            "assets/images",
            "assets/images/dev",
            "assets/images/design",
            "assets/images/video",
            "assets/images/ilustraciones",
            "assets/images/portfolio"
        ]
        
        self.build_ui()
        self.auto_load_file()

    def build_ui(self):
        main_container = ttk.Frame(self.root, padding=20)
        main_container.pack(fill="both", expand=True)

        # HEADER
        header = ttk.Frame(main_container)
        header.pack(fill="x", pady=(0, 15))
        ttk.Label(header, text="VISUAL ASSET MANAGER", font=("Helvetica", 16, "bold"), bootstyle="primary").pack(side="left")
        ttk.Button(header, text="📂 Cargar JS", command=self.browse_file, bootstyle="outline-primary").pack(side="right")
        self.lbl_path = ttk.Label(header, text="...", font=("Arial", 9))
        self.lbl_path.pack(side="right", padx=10)

        # PANEL DIVIDIDO
        paned = ttk.PanedWindow(main_container, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # === IZQUIERDA: LISTA ===
        left_frame = ttk.Frame(paned, padding=(0,0,10,0))
        paned.add(left_frame, weight=1)

        # Selector
        self.list_type_var = tk.StringVar(value="PORTFOLIO")
        sel_frame = ttk.Frame(left_frame)
        sel_frame.pack(fill="x", pady=5)
        ttk.Radiobutton(sel_frame, text="Portfolio", variable=self.list_type_var, value="PORTFOLIO", command=self.switch_list_type, bootstyle="toolbutton-primary").pack(side="left", fill="x", expand=True)
        ttk.Radiobutton(sel_frame, text="Galería", variable=self.list_type_var, value="GALLERY", command=self.switch_list_type, bootstyle="toolbutton-info").pack(side="left", fill="x", expand=True)

        # Lista
        list_scroll = ttk.Frame(left_frame)
        list_scroll.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_scroll)
        scrollbar.pack(side="right", fill="y")
        self.listbox = tk.Listbox(list_scroll, font=("Consolas", 10), selectmode="SINGLE", borderwidth=0)
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.listbox.yview)
        self.listbox.bind('<<ListboxSelect>>', self.on_select)

        # Botones CRUD
        btns = ttk.Frame(left_frame, padding=(0,10,0,0))
        btns.pack(fill="x")
        ttk.Button(btns, text="+", width=3, command=self.add_item, bootstyle="success").pack(side="left", padx=2)
        ttk.Button(btns, text="-", width=3, command=self.delete_item, bootstyle="danger").pack(side="left", padx=2)
        ttk.Button(btns, text="▲", width=3, command=lambda: self.move_item(-1)).pack(side="left", padx=2)
        ttk.Button(btns, text="▼", width=3, command=lambda: self.move_item(1)).pack(side="left", padx=2)

        # === DERECHA: VISUALIZADOR Y FORM ===
        right_frame = ttk.Frame(paned, padding=(10,0,0,0))
        paned.add(right_frame, weight=3)

        # 1. ÁREA DE IMAGEN (NUEVO)
        self.img_frame = ttk.Labelframe(right_frame, text="Vista Previa", padding=10, height=250)
        self.img_frame.pack(fill="x", pady=(0, 10))
        self.img_frame.pack_propagate(False) # Forzar altura fija

        self.lbl_image = ttk.Label(self.img_frame, text="Sin Imagen Seleccionada", anchor="center")
        self.lbl_image.pack(fill="both", expand=True)
        
        self.lbl_img_status = ttk.Label(self.img_frame, text="", font=("Arial", 8), foreground="gray")
        self.lbl_img_status.pack(side="bottom", anchor="e")

        # 2. FORMULARIO
        form_frame = ttk.Labelframe(right_frame, text="Datos del Proyecto", padding=10)
        form_frame.pack(fill="both", expand=True)

        self.fields = {}
        # Layout Grid
        keys = [
            ("Título", "title", 0), ("Categoría", "category", 0),
            ("Nombre Archivo", "fileName", 1), ("Enlace", "link", 1),
            ("Descripción", "desc", 2), ("Contexto", "context", 2),
            ("Fecha", "date", 3), ("ID Youtube", "id", 3)
        ]
        
        for label, key, row in keys:
            # Lógica simple para columnas
            col = 0 if keys.index((label, key, row)) % 2 == 0 else 2
            ttk.Label(form_frame, text=label, font=("Arial", 8, "bold")).grid(row=row*2, column=col, sticky="w", padx=5)
            entry = ttk.Entry(form_frame)
            entry.grid(row=row*2+1, column=col, sticky="ew", padx=5, pady=(0, 10))
            self.fields[key] = entry

        # Arrays
        ttk.Label(form_frame, text="Herramientas [Tools]", font=("Arial", 8, "bold"), foreground="#3498db").grid(row=8, column=0, sticky="w", padx=5)
        self.entry_tools = ttk.Entry(form_frame)
        self.entry_tools.grid(row=9, column=0, columnspan=3, sticky="ew", padx=5, pady=(0, 10))

        ttk.Label(form_frame, text="Etiquetas [Tags]", font=("Arial", 8, "bold"), foreground="#9b59b6").grid(row=10, column=0, sticky="w", padx=5)
        self.entry_tags = ttk.Entry(form_frame)
        self.entry_tags.grid(row=11, column=0, columnspan=3, sticky="ew", padx=5)

        form_frame.columnconfigure(0, weight=1)
        form_frame.columnconfigure(2, weight=1)

        # Botones Finales
        action_frame = ttk.Frame(right_frame, padding=(0, 10, 0, 0))
        action_frame.pack(fill="x", side="bottom")
        ttk.Button(action_frame, text="✔ Aplicar (Memoria)", command=self.save_item, bootstyle="warning").pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(action_frame, text="💾 GUARDAR JS", command=self.save_to_file, bootstyle="success").pack(side="left", fill="x", expand=True, padx=5)

    # --- LÓGICA DE IMÁGENES INTELIGENTE ---
    def find_image_path(self, filename):
        """Busca la imagen probando extensiones y carpetas."""
        if not filename: return None, "No filename"
        
        # CASO 1: Es una URL
        if filename.startswith("http"):
            return filename, "URL"

        # CASO 2: Archivo Local
        # Extensiones posibles a probar si el archivo no tiene
        extensions = ['', '.jpg', '.jpeg', '.png', '.webp', '.avif', '.gif']
        
        # Limpiar rutas relativas del JS (ej: remove "../")
        clean_name = filename.replace("../", "").replace("./", "")
        
        # Buscar en todas las carpetas configuradas
        for folder in self.image_search_paths:
            base_path = os.path.join(os.getcwd(), folder)
            
            # Probar cada extensión
            for ext in extensions:
                # Si el nombre ya tiene extensión, el '' lo encuentra.
                # Si no tiene, prueba .jpg, .png, etc.
                potential_path = os.path.join(base_path, clean_name + ext)
                
                if os.path.exists(potential_path) and os.path.isfile(potential_path):
                    return potential_path, "LOCAL"
                    
        return None, "NOT FOUND"

    def load_image_preview(self, item):
        """Carga y muestra la imagen en el GUI."""
        filename = item.get('fileName') or item.get('image') # Soporte legacy
        
        if not filename:
            self.lbl_image.config(image='', text="[Sin archivo definido]")
            self.lbl_img_status.config(text="")
            return

        path, source_type = self.find_image_path(filename)
        
        try:
            pil_image = None
            
            if source_type == "URL":
                self.lbl_img_status.config(text=f"🌐 Descargando vista previa...")
                self.root.update() # Refrescar UI
                response = requests.get(path, timeout=3)
                image_data = io.BytesIO(response.content)
                pil_image = Image.open(image_data)
                
            elif source_type == "LOCAL":
                self.lbl_img_status.config(text=f"📂 {os.path.basename(path)}")
                pil_image = Image.open(path)
                
            else:
                self.lbl_image.config(image='', text=f"❌ No encontrado: {filename}\n(Probado jpg, png, webp...)")
                self.lbl_img_status.config(text="Revisa la carpeta assets")
                return

            # Redimensionar para Vista Previa (Mantener Aspect Ratio)
            if pil_image:
                base_height = 220
                w_percent = (base_height / float(pil_image.size[1]))
                w_size = int((float(pil_image.size[0]) * float(w_percent)))
                pil_image = pil_image.resize((w_size, base_height), Image.Resampling.LANCZOS)
                
                tk_img = ImageTk.PhotoImage(pil_image)
                self.lbl_image.config(image=tk_img, text="")
                self.current_image_ref = tk_img # IMPORTANTE: Mantener referencia

        except Exception as e:
            self.lbl_image.config(image='', text=f"⚠️ Error al cargar imagen\n{str(e)}")

    # --- LÓGICA CORE (Igual que antes) ---
    def auto_load_file(self):
        paths = ["projects.js", "js/projects.js", "../js/projects.js"]
        for p in paths:
            if os.path.exists(p):
                self.load_file(os.path.abspath(p))
                return

    def browse_file(self):
        f = filedialog.askopenfilename(filetypes=[("Javascript", "*.js")])
        if f: self.load_file(f)

    def load_file(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.file_content = f.read()
            self.filepath = path
            self.lbl_path.config(text=os.path.basename(path), bootstyle="success")
            self.portfolio_data = self.extract_js_array("mainPortfolio", self.file_content)
            self.gallery_data = self.extract_js_array("galleryData", self.file_content)
            self.refresh_list()
            messagebox.showinfo("Listo", "Base de datos visual cargada.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def extract_js_array(self, var_name, content):
        pattern = re.compile(r"const\s+" + var_name + r"\s*=\s*\[(.*?)\];", re.DOTALL)
        match = pattern.search(content)
        if not match: return []
        raw_items = match.group(1).split('},')
        parsed = []
        for item in raw_items:
            if not item.strip(): continue
            d = {}
            clean = item.replace('{', '').replace('}', '').strip()
            
            # Strings
            for k, v in re.findall(r"(\w+):\s*'([^']*)'", clean): d[k] = v
            for k, v in re.findall(r'(\w+):\s*"([^"]*)"', clean): d[k] = v
            # Arrays
            for k, v in re.findall(r"(\w+):\s*\[(.*?)\]", clean):
                cl = [x.strip().replace("'", "").replace('"', "") for x in v.split(',')]
                d[k] = [x for x in cl if x]
            if d: parsed.append(d)
        return parsed

    def on_select(self, event):
        sel = self.listbox.curselection()
        if not sel: return
        idx = sel[0]
        self.selected_index = idx
        data = self.portfolio_data if self.current_list == "PORTFOLIO" else self.gallery_data
        item = data[idx]
        
        # Cargar Formulario
        for key, entry in self.fields.items():
            entry.delete(0, tk.END)
            if key in item: entry.insert(0, str(item[key]))
        
        self.entry_tools.delete(0, tk.END)
        if 'tools' in item: self.entry_tools.insert(0, ", ".join(item['tools']))
        self.entry_tags.delete(0, tk.END)
        if 'tags' in item: self.entry_tags.insert(0, ", ".join(item['tags']))

        # CARGAR IMAGEN VISUAL
        self.load_image_preview(item)

    # (Resto de funciones CRUD y Guardado idénticas al anterior)
    def switch_list_type(self):
        self.current_list = self.list_type_var.get()
        self.refresh_list()
        self.lbl_image.config(image='', text="Selecciona un proyecto")
        
    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        data = self.portfolio_data if self.current_list == "PORTFOLIO" else self.gallery_data
        for item in data:
            self.listbox.insert(tk.END, f"[{item.get('category','?')}] {item.get('title','Sin Título')}")

    def save_item(self):
        if self.selected_index is None: return
        new_item = {}
        for key, entry in self.fields.items():
            if entry.get().strip(): new_item[key] = entry.get().strip()
        
        t = self.entry_tools.get().strip()
        if t: new_item['tools'] = [x.strip() for x in t.split(',')]
        g = self.entry_tags.get().strip()
        if g: new_item['tags'] = [x.strip() for x in g.split(',')]
        
        target = self.portfolio_data if self.current_list == "PORTFOLIO" else self.gallery_data
        target[self.selected_index] = new_item
        self.refresh_list()
        self.listbox.select_set(self.selected_index)
        self.load_image_preview(new_item) # Actualizar preview si cambió nombre

    def add_item(self):
        target = self.portfolio_data if self.current_list == "PORTFOLIO" else self.gallery_data
        target.insert(0, {'title': 'NUEVO', 'category': 'DEV'})
        self.refresh_list()
        self.listbox.select_set(0)
        self.on_select(None)

    def delete_item(self):
        if self.selected_index is None: return
        target = self.portfolio_data if self.current_list == "PORTFOLIO" else self.gallery_data
        del target[self.selected_index]
        self.selected_index = None
        self.refresh_list()
        self.lbl_image.config(image='', text="Item eliminado")

    def move_item(self, d):
        if self.selected_index is None: return
        idx = self.selected_index
        target = self.portfolio_data if self.current_list == "PORTFOLIO" else self.gallery_data
        n_idx = idx + d
        if 0 <= n_idx < len(target):
            target[idx], target[n_idx] = target[n_idx], target[idx]
            self.refresh_list()
            self.listbox.select_set(n_idx)
            self.selected_index = n_idx

    def save_to_file(self):
        if not self.filepath: return
        shutil.copy(self.filepath, self.filepath + ".bak")
        js_port = self.py_to_js(self.portfolio_data)
        js_gall = self.py_to_js(self.gallery_data)
        
        nc = re.sub(r"(const\s+mainPortfolio\s*=\s*\[).*?(\];)", f"\\1\n{js_port}\\2", self.file_content, flags=re.DOTALL)
        nc = re.sub(r"(const\s+galleryData\s*=\s*\[).*?(\];)", f"\\1\n{js_gall}\\2", nc, flags=re.DOTALL)
        
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f: f.write(nc)
            self.file_content = nc
            messagebox.showinfo("Guardado", "Archivo actualizado.")
        except Exception as e: messagebox.showerror("Error", str(e))

    def py_to_js(self, data):
        lines = []
        for item in data:
            lines.append("  {")
            for k, v in item.items():
                if isinstance(v, list): lines.append(f"    {k}: [" + ", ".join([f"'{x}'" for x in v]) + "],")
                else: lines.append(f"    {k}: '{v.replace("'", "\\'")}',")
            lines.append("  },")
        return "\n".join(lines)

if __name__ == "__main__":
    app_window = ttk.Window(themename="darkly") 
    app = ProjectDBManager(app_window)
    app_window.mainloop()
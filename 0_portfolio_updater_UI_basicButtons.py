import sys
import os
import subprocess
import re
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox

# --- 1. ZONA DE AUTO-INSTALACIÓN DE DEPENDENCIAS ---
def setup_dependencies():
    """Analiza si faltan librerías y las descarga automáticamente."""
    # Lista de librerías externas requeridas
    # Formato: 'nombre_paquete_pip': 'nombre_importacion'
    required_libs = {
        'ttkbootstrap': 'ttkbootstrap' 
    }
    
    installed = False
    for package, import_name in required_libs.items():
        try:
            __import__(import_name)
        except ImportError:
            print(f"[SISTEMA] Instalando dependencia faltante: {package}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                installed = True
                print(f"[SISTEMA] {package} instalado correctamente.")
            except Exception as e:
                print(f"[ERROR] No se pudo instalar {package}: {e}")

    if installed:
        print("[SISTEMA] Reiniciando script para aplicar cambios...")
        os.execv(sys.executable, ['python'] + sys.argv)

# Ejecutamos el chequeo antes de importar nada externo
setup_dependencies()

# --- 2. IMPORTACIONES EXTERNAS (AHORA SEGURAS) ---
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

class ProjectDBManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Tarquitet - DB Manager Pro")
        self.root.geometry("1100x750")
        
        # Estado
        self.filepath = ""
        self.file_content = ""
        self.portfolio_data = [] 
        self.gallery_data = []   
        self.current_list = "PORTFOLIO" 
        self.selected_index = None
        
        self.build_ui()
        self.auto_load_file()

    def build_ui(self):
        # Frame principal con padding
        main_container = ttk.Frame(self.root, padding=20)
        main_container.pack(fill="both", expand=True)

        # --- HEADER ---
        header_frame = ttk.Frame(main_container)
        header_frame.pack(fill="x", pady=(0, 20))
        
        ttk.Label(header_frame, text="PROJECTS.JS MANAGER", font=("Helvetica", 16, "bold"), bootstyle="primary").pack(side="left")
        
        path_frame = ttk.Frame(header_frame)
        path_frame.pack(side="right")
        
        self.lbl_path = ttk.Label(path_frame, text="Esperando archivo...", font=("Arial", 9), bootstyle="secondary")
        self.lbl_path.pack(side="right", padx=10)
        ttk.Button(path_frame, text="📂 Cargar JS", command=self.browse_file, bootstyle="outline-primary").pack(side="right")

        # --- PANEL DIVIDIDO ---
        paned = ttk.PanedWindow(main_container, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # === IZQUIERDA: LISTA ===
        left_frame = ttk.Frame(paned, padding=(0,0,10,0))
        paned.add(left_frame, weight=1)

        # Selector
        self.list_type_var = tk.StringVar(value="PORTFOLIO")
        sel_frame = ttk.Labelframe(left_frame, text="Seleccionar Sección", padding=10)
        sel_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Radiobutton(sel_frame, text="Main Portfolio", variable=self.list_type_var, value="PORTFOLIO", command=self.switch_list_type, bootstyle="toolbutton-primary").pack(side="left", fill="x", expand=True, padx=2)
        ttk.Radiobutton(sel_frame, text="Galería (Arte)", variable=self.list_type_var, value="GALLERY", command=self.switch_list_type, bootstyle="toolbutton-info").pack(side="left", fill="x", expand=True, padx=2)

        # Listbox con Scrollbar
        list_scroll = ttk.Frame(left_frame)
        list_scroll.pack(fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(list_scroll)
        scrollbar.pack(side="right", fill="y")
        
        self.listbox = tk.Listbox(list_scroll, font=("Consolas", 10), selectmode="SINGLE", borderwidth=0, highlightthickness=0)
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.listbox.yview)
        
        self.listbox.bind('<<ListboxSelect>>', self.on_select)

        # Botones CRUD
        crud_frame = ttk.Frame(left_frame, padding=(0, 10, 0, 0))
        crud_frame.pack(fill="x")
        ttk.Button(crud_frame, text="+ Nuevo", command=self.add_item, bootstyle="success").pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(crud_frame, text="Borrar", command=self.delete_item, bootstyle="danger").pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(crud_frame, text="▲", width=3, command=lambda: self.move_item(-1), bootstyle="secondary-outline").pack(side="left", padx=1)
        ttk.Button(crud_frame, text="▼", width=3, command=lambda: self.move_item(1), bootstyle="secondary-outline").pack(side="left", padx=1)

        # === DERECHA: FORMULARIO ===
        right_frame = ttk.Frame(paned, padding=(10,0,0,0))
        paned.add(right_frame, weight=2)

        form_frame = ttk.Labelframe(right_frame, text="Editar Propiedades", padding=15)
        form_frame.pack(fill="both", expand=True)

        self.fields = {}
        field_keys = [
            ("Título del Proyecto", "title"),
            ("Descripción Corta", "desc"),
            ("Nombre Archivo / URL Imagen", "fileName"),
            ("Enlace (Link)", "link"),
            ("Categoría (DEV, DESIGN, ART, VIDEO)", "category"),
            ("Contexto (PROFESSIONAL, PERSONAL)", "context"),
            ("Fecha (YYYY-MM-DD)", "date"),
            ("ID Youtube (Si aplica)", "id"),
            ("Canal Youtube", "channel")
        ]

        # Grid layout para inputs
        r = 0
        for label, key in field_keys:
            ttk.Label(form_frame, text=label, font=("Arial", 8, "bold")).grid(row=r, column=0, sticky="w", pady=(5,0))
            entry = ttk.Entry(form_frame)
            entry.grid(row=r+1, column=0, sticky="ew", pady=(0, 5))
            self.fields[key] = entry
            r += 2

        # Arrays especiales
        ttk.Label(form_frame, text="Herramientas (Separar por comas)", font=("Arial", 8, "bold"), bootstyle="primary").grid(row=r, column=0, sticky="w", pady=(10,0))
        self.entry_tools = ttk.Entry(form_frame)
        self.entry_tools.grid(row=r+1, column=0, sticky="ew")
        r += 2

        ttk.Label(form_frame, text="Tags / Etiquetas (Separar por comas)", font=("Arial", 8, "bold"), bootstyle="info").grid(row=r, column=0, sticky="w", pady=(5,0))
        self.entry_tags = ttk.Entry(form_frame)
        self.entry_tags.grid(row=r+1, column=0, sticky="ew")

        form_frame.columnconfigure(0, weight=1)

        # Botones de Acción Final
        action_frame = ttk.Frame(right_frame, padding=(0, 20, 0, 0))
        action_frame.pack(fill="x", side="bottom")
        
        ttk.Button(action_frame, text="✔ Aplicar Cambios (Memoria)", command=self.save_item, bootstyle="warning").pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(action_frame, text="💾 GUARDAR ARCHIVO JS", command=self.save_to_file, bootstyle="success").pack(side="left", fill="x", expand=True, padx=5)

    # --- LÓGICA DE ARCHIVOS (Igual que antes) ---
    def auto_load_file(self):
        potential_paths = ["projects.js", "js/projects.js", "../js/projects.js", "assets/js/projects.js"]
        for p in potential_paths:
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
            messagebox.showinfo("Cargado", "Base de datos leída correctamente")
        except Exception as e:
            messagebox.showerror("Error", f"Fallo al leer:\n{e}")

    # --- PARSEO ---
    def extract_js_array(self, var_name, content):
        pattern = re.compile(r"const\s+" + var_name + r"\s*=\s*\[(.*?)\];", re.DOTALL)
        match = pattern.search(content)
        if not match: return []
        raw_array = match.group(1)
        raw_items = raw_array.split('},')
        parsed_items = []
        for item in raw_items:
            if not item.strip(): continue
            item_dict = {}
            clean_item = item.replace('{', '').replace('}', '').strip()
            
            # Regex Mejorado
            str_props = re.findall(r"(\w+):\s*'([^']*)'", clean_item)
            for k, v in str_props: item_dict[k] = v
            str_props_dbl = re.findall(r'(\w+):\s*"([^"]*)"', clean_item)
            for k, v in str_props_dbl: item_dict[k] = v
            
            list_props = re.findall(r"(\w+):\s*\[(.*?)\]", clean_item)
            for k, v in list_props:
                clean_list = [x.strip().replace("'", "").replace('"', "") for x in v.split(',')]
                item_dict[k] = [x for x in clean_list if x]
            
            if item_dict: parsed_items.append(item_dict)
        return parsed_items

    # --- UI INTERACTION ---
    def switch_list_type(self):
        self.current_list = self.list_type_var.get()
        self.refresh_list()
        self.clear_form()

    def clear_form(self):
        for entry in self.fields.values(): entry.delete(0, tk.END)
        self.entry_tools.delete(0, tk.END)
        self.entry_tags.delete(0, tk.END)
        self.selected_index = None

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        data = self.portfolio_data if self.current_list == "PORTFOLIO" else self.gallery_data
        for item in data:
            title = item.get('title', '--- Sin Título ---')
            cat = item.get('category', '???')
            self.listbox.insert(tk.END, f"[{cat}] {title}")

    def on_select(self, event):
        sel = self.listbox.curselection()
        if not sel: return
        idx = sel[0]
        self.selected_index = idx
        data = self.portfolio_data if self.current_list == "PORTFOLIO" else self.gallery_data
        item = data[idx]
        
        for key, entry in self.fields.items():
            entry.delete(0, tk.END)
            if key in item: entry.insert(0, str(item[key]))
        
        self.entry_tools.delete(0, tk.END)
        if 'tools' in item: self.entry_tools.insert(0, ", ".join(item['tools']))
        self.entry_tags.delete(0, tk.END)
        if 'tags' in item: self.entry_tags.insert(0, ", ".join(item['tags']))

    # --- CRUD ---
    def save_item(self):
        if self.selected_index is None: return
        new_item = {}
        for key, entry in self.fields.items():
            val = entry.get().strip()
            if val: new_item[key] = val
        
        t_val = self.entry_tools.get().strip()
        if t_val: new_item['tools'] = [t.strip() for t in t_val.split(',')]
        g_val = self.entry_tags.get().strip()
        if g_val: new_item['tags'] = [t.strip() for t in g_val.split(',')]
        
        target = self.portfolio_data if self.current_list == "PORTFOLIO" else self.gallery_data
        target[self.selected_index] = new_item
        self.refresh_list()
        self.listbox.select_set(self.selected_index)

    def add_item(self):
        new_item = {'title': 'NUEVO ITEM', 'category': 'DEV'}
        target = self.portfolio_data if self.current_list == "PORTFOLIO" else self.gallery_data
        target.insert(0, new_item)
        self.refresh_list()
        self.listbox.select_set(0)
        self.on_select(None)

    def delete_item(self):
        if self.selected_index is None: return
        target = self.portfolio_data if self.current_list == "PORTFOLIO" else self.gallery_data
        del target[self.selected_index]
        self.selected_index = None
        self.refresh_list()
        self.clear_form()

    def move_item(self, direction):
        if self.selected_index is None: return
        idx = self.selected_index
        target = self.portfolio_data if self.current_list == "PORTFOLIO" else self.gallery_data
        new_idx = idx + direction
        if 0 <= new_idx < len(target):
            target[idx], target[new_idx] = target[new_idx], target[idx]
            self.refresh_list()
            self.listbox.select_set(new_idx)
            self.selected_index = new_idx

    # --- SAVE FILE ---
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
            messagebox.showinfo("Guardado", "Archivo actualizado con éxito.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

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
    # Usamos el tema moderno gracias al auto-instalador
    app_window = ttk.Window(themename="darkly") 
    app = ProjectDBManager(app_window)
    app_window.mainloop()
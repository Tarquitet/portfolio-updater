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
        self.root.title("Tarquitet - Universal DB Manager V8")
        self.root.geometry("1300x850")
        
        self.filepath = ""
        self.file_content = ""
        self.datasets = {} 
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
        ttk.Button(btns, text="➕", width=4, command=self.add_item, bootstyle="success").pack(side="left", padx=2)
        ttk.Button(btns, text="➖", width=4, command=self.delete_item, bootstyle="danger").pack(side="left", padx=2)
        ttk.Button(btns, text="▲", width=4, command=lambda: self.move_item(-1), bootstyle="secondary").pack(side="left", padx=2)
        ttk.Button(btns, text="▼", width=4, command=lambda: self.move_item(1), bootstyle="secondary").pack(side="left", padx=2)

        # RIGHT
        right_frame = ttk.Frame(paned, padding=(10,0,0,0))
        paned.add(right_frame, weight=3)

        self.img_frame = ttk.Labelframe(right_frame, text="Preview", padding=10, height=220)
        self.img_frame.pack(fill="x", pady=(0, 10))
        self.img_frame.pack_propagate(False)
        self.lbl_image = ttk.Label(self.img_frame, text="...", anchor="center")
        self.lbl_image.pack(fill="both", expand=True)
        self.lbl_img_path = ttk.Label(self.img_frame, text="", font=("Arial", 7), foreground="gray")
        self.lbl_img_path.pack(side="bottom", anchor="e")

        self.form_canvas = tk.Canvas(right_frame, highlightthickness=0)
        self.form_scrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=self.form_canvas.yview)
        self.form_inner = ttk.Frame(self.form_canvas)
        self.form_inner.bind("<Configure>", lambda e: self.form_canvas.configure(scrollregion=self.form_canvas.bbox("all")))
        self.form_window = self.form_canvas.create_window((0, 0), window=self.form_inner, anchor="nw")
        self.form_canvas.bind("<Configure>", lambda e: self.form_canvas.itemconfig(self.form_window, width=e.width))
        self.form_canvas.configure(yscrollcommand=self.form_scrollbar.set)
        self.form_canvas.pack(side="left", fill="both", expand=True)
        self.form_scrollbar.pack(side="right", fill="y")
        self.form_entries = {} 

        action_frame = ttk.Frame(right_frame, padding=(0,10,0,0))
        action_frame.pack(fill="x", side="bottom")
        ttk.Button(action_frame, text="✔ APLICAR", command=self.save_to_memory, bootstyle="warning").pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(action_frame, text="💾 GUARDAR JS", command=self.save_to_disk, bootstyle="success").pack(side="left", fill="x", expand=True, padx=2)

    # ============================================================
    # 🧠 LÓGICA CORREGIDA (FIX REGEX)
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
                    # REGEX FIX: Permite window.variable sin espacio
                    # Busca asignaciones a arrays [ ... ]
                    count = len(re.findall(r"(?:const\s+|let\s+|var\s+|window\.)\s*(\w+)\s*=\s*\[", content))
                    if count > 0:
                        best_candidate = path
                        break # Encontrar el primero válido
            except: pass
            
        if best_candidate:
            print(f"Cargando: {best_candidate}")
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
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def parse_all_datasets(self):
        self.datasets = {}
        # REGEX FIX: Soporta "const x =" y "window.x ="
        regex_datasets = r"(?:const\s+|let\s+|var\s+|window\.)\s*(\w+)\s*=\s*\[(.*?)\];"
        matches = re.finditer(regex_datasets, self.file_content, re.DOTALL)
        
        for match in matches:
            var_name = match.group(1)
            raw_content = match.group(2)
            # Limpiar comentarios JS (// ...) para que no rompan el parseo
            clean_content = re.sub(r"\/\/.*", "", raw_content)
            
            if "{" in clean_content:
                data = self.parse_js_array_content(clean_content)
                if data:
                    self.datasets[var_name] = data
                
    def parse_js_array_content(self, content):
        items = content.split('},')
        parsed_list = []
        for item in items:
            if not item.strip(): continue
            clean_item = item.replace('{', '').replace('}', '').strip()
            
            obj = {}
            # Captura flexible de claves y valores (constantes o strings)
            props = re.findall(r"(\w+):\s*(?:'([^']*)'|\"([^\"]*)\"|([a-zA-Z0-9_.]+))", clean_item)
            for k, v1, v2, v3 in props:
                obj[k] = v1 or v2 or v3 # Toma el grupo que haya coincidido
                
            # Captura arrays internos (ej: tools: [...])
            arrays = re.findall(r"(\w+):\s*\[(.*?)\]", clean_item)
            for k, v in arrays:
                # Limpia comillas extra si las hay
                elements = [x.strip().strip("'\"") for x in v.split(',') if x.strip()]
                obj[k] = elements
                
            if obj: parsed_list.append(obj)
        return parsed_list

    # ============================================================
    # UI DINÁMICA
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
            # Limpiar constantes visualmente (CAT.DEV -> DEV)
            cat = cat.replace("CAT.", "").replace("CTX.", "")
            self.listbox.insert(tk.END, f"[{cat}] {label}")

    def on_select(self, event):
        sel = self.listbox.curselection()
        if not sel: return
        self.selected_index = sel[0]
        item = self.datasets[self.current_key][self.selected_index]
        self.build_dynamic_form(item)
        self.load_image_preview(item)

    def build_dynamic_form(self, item):
        for w in self.form_inner.winfo_children(): w.destroy()
        self.form_entries = {}
        
        # Prioridad visual
        keys = list(item.keys())
        prio = ['title', 'category', 'context', 'fileName', 'date', 'link']
        keys.sort(key=lambda x: prio.index(x) if x in prio else 99)
        
        row = 0
        for key in keys:
            val = item[key]
            ttk.Label(self.form_inner, text=key.upper(), font=("Arial", 7, "bold"), foreground="#555").grid(row=row, column=0, sticky="w", padx=5, pady=(5,0))
            entry = ttk.Entry(self.form_inner)
            entry.grid(row=row+1, column=0, sticky="ew", padx=5, pady=(0,5))
            
            if isinstance(val, list): entry.insert(0, ", ".join(val))
            else: entry.insert(0, str(val))
            self.form_entries[key] = entry
            row += 2
        self.form_inner.columnconfigure(0, weight=1)

    # ============================================================
    # GUARDADO INTELIGENTE
    # ============================================================
    def save_to_memory(self):
        if self.selected_index is None: return
        new_item = {}
        for key, entry in self.form_entries.items():
            val = entry.get().strip()
            if "," in val and "[" not in val: # Simple heurística de lista
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
        
        for var_name, data_list in self.datasets.items():
            js_string = self.py_to_js(data_list)
            # Reemplazo seguro usando el nombre de la variable
            pattern = r"((?:const\s+|let\s+|var\s+|window\.)\s*" + var_name + r"\s*=\s*\[).*?(\];)"
            new_content = re.sub(pattern, f"\\1\n{js_string}\\2", new_content, flags=re.DOTALL)
            
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f: f.write(new_content)
            self.file_content = new_content
            messagebox.showinfo("Guardado", "Archivo JS actualizado.")
        except Exception as e: messagebox.showerror("Error", str(e))

    def py_to_js(self, data):
        lines = []
        # Patrones que sabemos que NO llevan comillas
        consts = ("CAT.", "CTX.", "T.", "PROJECT_CONFIG") 
        
        for item in data:
            lines.append("  {")
            for k, v in item.items():
                if isinstance(v, list):
                    els = []
                    for x in v:
                        if x.startswith(consts): els.append(x)
                        else: els.append(f"'{x}'")
                    lines.append(f"    {k}: [{', '.join(els)}],")
                else:
                    s = str(v).strip()
                    if s.startswith(consts): lines.append(f"    {k}: {s},")
                    else: lines.append(f"    {k}: '{s.replace("'", "\\'")}',")
            lines.append("  },")
        return "\n".join(lines)

    # --- IMÁGENES ---
    def discover_paths_from_js(self, content, path):
        base = os.path.dirname(path)
        self.discovered_paths = [os.path.join(base, "../assets/images")]
        
        match = re.search(r"paths:\s*\{(.*?)\}", content, re.DOTALL)
        if match:
            raw = re.findall(r"['\"](.*?)['\"]", match.group(1))
            for p in raw:
                if len(p)>2: self.discovered_paths.append(os.path.normpath(os.path.join(base, p)))
        
        # Expandir
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
            self.lbl_image.config(image='', text=f"({type})")
            self.lbl_img_path.config(text=fname)
            return

        if img:
            aspect = 220 / float(img.size[1])
            new_w = int(float(img.size[0]) * aspect)
            img = img.resize((new_w, 220), Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(img)
            self.lbl_image.config(image=tk_img, text="")
            self.current_image_ref = tk_img
            self.lbl_img_path.config(text="OK")

    # --- CRUD SIMPLE ---
    def browse_file(self):
        f = filedialog.askopenfilename(filetypes=[("JS", "*.js")])
        if f: self.load_file(f)
    def add_item(self):
        if not self.current_key: return
        self.datasets[self.current_key].insert(0, {'title': 'NUEVO'})
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
import os
import math
import string
import datetime
import threading
import time
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Windowsの場合の最小化・リサイズ用API定義
if os.name == 'nt':
    import ctypes
    from ctypes import windll

# ==========================================
# 1. SSSA ＆ 拡張フィルター付きスコア計算 Engine (10区分ソート・複合スコア対応版)
# ==========================================
def calculate_file_scores(query_str, file_info, filter_params=None):
    if filter_params:
        target_ext = filter_params.get("ext", "").strip().lower()
        if target_ext:
            if not target_ext.startswith('.'):
                target_ext = '.' + target_ext
            if file_info['ext'].lower() != target_ext:
                return -1.0, -1.0, 0.0

        size_kb = file_info['size'] / 1024.0
        min_size = filter_params.get("min_size")
        max_size = filter_params.get("max_size")
        if min_size is not None and size_kb < min_size:
            return -1.0, -1.0, 0.0
        if max_size is not None and size_kb > max_size:
            return -1.0, -1.0, 0.0

        mtime_str = file_info['mtime']
        ctime_str = file_info['ctime']
        
        start_date = filter_params.get("start_date", "").strip()
        end_date = filter_params.get("end_date", "").strip()
        date_target_type = filter_params.get("date_type", "mtime")
        
        target_date_str = mtime_str if date_target_type == "mtime" else ctime_str
        if start_date and target_date_str[:10] < start_date:
            return -1.0, -1.0, 0.0
        if end_date and target_date_str[:10] > end_date:
            return -1.0, -1.0, 0.0

        artist_q = filter_params.get("artist", "").strip().lower()
        creator_q = filter_params.get("creator", "").strip().lower()
        
        if artist_q and artist_q not in file_info['artist'].lower():
            return -1.0, -1.0, 0.0
        if creator_q and creator_q not in file_info['creator'].lower():
            return -1.0, -1.0, 0.0

    query_words = [w.strip().lower() for w in query_str.split() if w.strip()]
    if not query_words:
        return 0.5, 0.5, 100.0 if not file_info['is_dir'] else 0.0

    name_txt = file_info['name'].lower()
    path_txt = file_info['path'].lower()
    ext_txt = file_info['ext'].lower()

    fields = [name_txt, path_txt, ext_txt]
    hit_fields = sum(1 for f in fields if any(word in f for word in query_words))
    p_field = (hit_fields / len(fields)) * 100.0

    all_text = f"{name_txt} {path_txt}"
    matched_words = sum(1 for word in query_words if word in all_text)
    match_rate = matched_words / len(query_words) if query_words else 0.0

    dir_bonus = 0.1 if file_info['is_dir'] else 0.0
    base_score = min(1.0, (match_rate * 0.85) + dir_bonus)
    sssa_score = base_score * (p_field / 100.0)

    return round(sssa_score, 4), round(base_score, 4), round(p_field, 1)


# ==========================================
# 2. 絵文字アイコン & デバイス判定
# ==========================================
def get_system_drives():
    drives = []
    if os.name == 'nt':
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                drives.append(drive)
    else:
        drives.append("/")
    return drives

def get_desktop_path():
    user_home = os.path.expanduser("~")
    candidates = [
        os.path.join(user_home, "OneDrive", "デスクトップ"),
        os.path.join(user_home, "OneDrive", "Desktop"),
        os.path.join(user_home, "デスクトップ"),
        os.path.join(user_home, "Desktop"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return user_home

def get_file_icon_symbol(is_dir, ext):
    if is_dir:
        return "📁"
    ext = ext.lower()
    if ext == '.pdf': return "📑"
    elif ext == '.ymmp': return "🎬"
    elif ext == '.pdn': return "🎨"
    elif ext in ['.jar', '.java', '.class']: return "☕"
    elif ext == '.json': return "📋"
    elif ext == '.toml': return "⚙️"
    elif ext == '.bat': return "⚡"
    elif ext in ['.zip', '.rar', '.7z']: return "📦"
    elif ext in ['.tar', '.gz', '.bz2', '.xz']: return "🗂️"
    elif ext == '.iso': return "💿"
    elif ext in ['.exe', '.cmd', '.msi']: return "⚙️"
    elif ext in ['.py', '.js', '.html', '.css', '.c', '.cpp']: return "📜"
    elif ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg']: return "🖼️"
    elif ext in ['.mp3', '.wav', '.flac', '.aac']: return "🎵"
    elif ext in ['.mp4', '.mkv', '.avi', '.mov']: return "🎬"
    elif ext in ['.txt', '.doc', '.docx']: return "📄"
    else: return "📄"

def get_device_icon(name_lower, path_lower):
    if "ssd" in name_lower or "ssd" in path_lower: return "💽"
    elif "hdd" in name_lower or "hdd" in path_lower or "hd" in path_lower: return "🗄️"
    elif "sd" in name_lower or "card" in name_lower: return "💾"
    elif "phone" in name_lower or "android" in name_lower or "iphone" in name_lower: return "📱"
    elif "nas" in name_lower or "network" in name_lower: return "🌐"
    elif "ubuntu" in name_lower: return "🟠"
    elif "linux" in name_lower: return "🐧"
    elif "mac" in name_lower or "apple" in name_lower: return "🍏"
    elif "windows" in name_lower or ":" in path_lower: return "🪟"
    return "💻"


# ==========================================
# 3. 棒グラフ型ソーティングビューワー Widget
# ==========================================
class BarChartSortViewer(ttk.LabelFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="📊 スコア棒グラフビューワー", **kwargs)
        self.canvas_height = 140
        self.canvas = tk.Canvas(self, height=self.canvas_height, bg="#10141C", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=2, pady=2)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.status_label = ttk.Label(self, text="順位: ---", font=("Consolas", 8))
        self.status_label.pack(anchor="w", padx=2)

    def _on_mouse_wheel(self, event):
        if os.name == 'nt':
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def update_bars(self, active_items, sort_col, reverse):
        self.canvas.delete("all")
        if not active_items:
            self.canvas.create_text(100, 70, text="NO DATA", fill="#00ffb0", font=("Consolas", 10, "bold"))
            self.status_label.config(text="順位: 0 件")
            return

        top_items = active_items[:8]
        max_val = 0.0001
        for item in top_items:
            val = item["score"] if sort_col == "score" else (item["info"]["size"] if sort_col == "size" else item["base"])
            if val > max_val: max_val = val

        c_width = self.canvas.winfo_width() or 220
        bar_count = len(top_items)
        spacing = 4
        bar_width = max(8, (c_width - (spacing * (bar_count + 1))) // bar_count)

        for i, item in enumerate(top_items):
            val = item["score"] if sort_col == "score" else (item["info"]["size"] if sort_col == "size" else item["base"])
            norm_ratio = min(1.0, val / max_val)
            bar_h = int(norm_ratio * (self.canvas_height - 25))

            x0 = spacing + i * (bar_width + spacing)
            y1 = self.canvas_height - 15
            y0 = y1 - bar_h
            x1 = x0 + bar_width

            color_intensity = int(140 + 115 * norm_ratio)
            hex_color = f"#00{color_intensity:02x}ff"

            bar_id = self.canvas.create_rectangle(x0, y0, x1, y1, fill=hex_color, outline="#78c2ff", width=1)
            self.canvas.create_text(x0 + bar_width/2, y1 + 8, text=f"#{i+1}", fill="#e0f0ff", font=("Consolas", 7))

            fname = item["info"]["name"]
            score_txt = f"{item['score']:.3f}"
            def _on_hover(e, name=fname, sc=score_txt, idx=i):
                self.status_label.config(text=f"#{idx+1}: {name[:12]}.. ({sc})")
            self.canvas.tag_bind(bar_id, "<Enter>", _on_hover)

        order_str = "降順" if reverse else "昇順"
        self.status_label.config(text=f"ソート: {sort_col} ({order_str}) / Top {len(top_items)}")


# ==========================================
# 4. 自動整理ダイアログ
# ==========================================
class AutoOrganizeDialog(tk.Toplevel):
    def __init__(self, parent, current_dir, callback):
        super().__init__(parent)
        self.overrideredirect(True)
        self.geometry("520x460+200+150")
        self.current_dir = current_dir
        self.callback = callback
        self.resizable(False, False)
        
        self.old_x = 0
        self.old_y = 0
        self._build_ui()

    def _build_ui(self):
        container_outer = tk.Frame(self, bg="#1E4B72", padx=1, pady=1)
        container_outer.pack(fill="both", expand=True)

        main_frame = tk.Frame(container_outer, bg="#E4F1FA")
        main_frame.pack(fill="both", expand=True)

        title_bar = tk.Frame(main_frame, bg="#D4EDFC", height=36)
        title_bar.pack(fill="x")
        title_bar.bind("<Button-1>", self.start_window_drag)
        title_bar.bind("<B1-Motion>", self.do_window_drag)

        close_btn = tk.Button(title_bar, text="✕", bg="#D4EDFC", fg="#103050", relief="flat", width=4, bd=0, command=self.destroy, activebackground="#E81123", activeforeground="#FFFFFF")
        close_btn.pack(side="right", fill="y")

        title_lbl = tk.Label(title_bar, text="🧹 ファイル自動整理マネージャー", bg="#D4EDFC", fg="#1E4B72", font=("Segoe UI", 9, "bold"))
        title_lbl.pack(side="left", padx=12)
        title_lbl.bind("<Button-1>", self.start_window_drag)
        title_lbl.bind("<B1-Motion>", self.do_window_drag)

        body_frame = ttk.Frame(main_frame, padding=12)
        body_frame.pack(fill="both", expand=True)

        ttk.Label(body_frame, text="📁 現在の対象フォルダ:", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=5, pady=(5, 2))
        ttk.Label(body_frame, text=self.current_dir, font=("Consolas", 8), foreground="#004488").pack(anchor="w", padx=5, pady=(0, 8))

        mode_frame = ttk.LabelFrame(body_frame, text=" ⚙️ 整理ルール・指定方法 ", padding=10)
        mode_frame.pack(fill="x", padx=5, pady=5)

        self.organize_mode = tk.StringVar(value="ext_group")
        
        ttk.Radiobutton(mode_frame, text="拡張子グループ別に自動分類して整理 (画像、動画、文書など)", variable=self.organize_mode, value="ext_group").pack(anchor="w", pady=3)
        ttk.Radiobutton(mode_frame, text="拡張子を指定して特定の形式のみ整理 (例: .png や .txt)", variable=self.organize_mode, value="specific_ext").pack(anchor="w", pady=3)
        
        ext_sub = ttk.Frame(mode_frame)
        ext_sub.pack(fill="x", padx=20, pady=2)
        ttk.Label(ext_sub, text="対象拡張子:").pack(side="left")
        self.target_ext_entry = ttk.Entry(ext_sub, width=15)
        self.target_ext_entry.pack(side="left", padx=5)

        ttk.Radiobutton(mode_frame, text="ファイル名キーワード（部分一致）で指定して整理", variable=self.organize_mode, value="keyword").pack(anchor="w", pady=(6, 3))
        
        kw_sub = ttk.Frame(mode_frame)
        kw_sub.pack(fill="x", padx=20, pady=2)
        ttk.Label(kw_sub, text="キーワード:").pack(side="left")
        self.target_kw_entry = ttk.Entry(kw_sub, width=22)
        self.target_kw_entry.pack(side="left", padx=5)

        btn_frame = ttk.Frame(body_frame)
        btn_frame.pack(fill="x", padx=5, pady=10)

        ttk.Button(btn_frame, text="✨ 整理を実行する", command=self.execute_organization).pack(side="right", padx=3)
        ttk.Button(btn_frame, text="キャンセル", command=self.destroy).pack(side="right", padx=3)

    def start_window_drag(self, event):
        self.old_x = event.x_root
        self.old_y = event.y_root

    def do_window_drag(self, event):
        x = self.winfo_x() + (event.x_root - self.old_x)
        y = self.winfo_y() + (event.y_root - self.old_y)
        self.geometry(f"+{x}+{y}")
        self.old_x = event.x_root
        self.old_y = event.y_root

    def execute_organization(self):
        mode = self.organize_mode.get()
        moved_count = 0
        try:
            items = os.listdir(self.current_dir)
            for item in items:
                src_path = os.path.join(self.current_dir, item)
                if os.path.isdir(src_path):
                    continue

                target_folder_name = ""
                if mode == "ext_group":
                    ext = os.path.splitext(item)[1].lower()
                    if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg']: target_folder_name = "Images"
                    elif ext in ['.mp4', '.mkv', '.avi', '.mov', '.ymmp']: target_folder_name = "Videos"
                    elif ext in ['.mp3', '.wav', '.flac', '.aac']: target_folder_name = "Music"
                    elif ext in ['.pdf', '.txt', '.doc', '.docx']: target_folder_name = "Documents"
                    elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz']: target_folder_name = "Archives"
                    elif ext in ['.py', '.js', '.html', '.css', '.java', '.jar', '.json', '.toml']: target_folder_name = "SourceCodes"
                    else: target_folder_name = "Others"
                elif mode == "specific_ext":
                    target_ext = self.target_ext_entry.get().strip().lower()
                    if not target_ext:
                        messagebox.showwarning("警告", "対象の拡張子を入力してください。")
                        return
                    if not target_ext.startswith('.'): target_ext = '.' + target_ext
                    if os.path.splitext(item)[1].lower() == target_ext:
                        target_folder_name = f"Ext_{target_ext[1:]}"
                    else:
                        continue
                elif mode == "keyword":
                    kw = self.target_kw_entry.get().strip().lower()
                    if not kw:
                        messagebox.showwarning("警告", "キーワードを入力してください。")
                        return
                    if kw in item.lower():
                        target_folder_name = f"Keyword_{kw}"
                    else:
                        continue

                if target_folder_name:
                    dest_dir = os.path.join(self.current_dir, target_folder_name)
                    if not os.path.exists(dest_dir): os.makedirs(dest_dir)
                    shutil.move(src_path, os.path.join(dest_dir, item))
                    moved_count += 1

            messagebox.showinfo("完了", f"自動整理が完了しました。\n合計 {moved_count} 個のファイルを整理しました！")
            self.callback()
            self.destroy()
        except Exception as e:
            messagebox.showerror("エラー", f"エラーが発生しました:\n{e}")


# ==========================================
# 5. タブページ（非同期軽量検索・アニメーション・サブディレクトリ検索対応）
# ==========================================
class ExplorerTabPage(ttk.Frame):
    def __init__(self, parent, master_app, initial_dir=None):
        super().__init__(parent)
        self.master_app = master_app
        self.current_dir = initial_dir or os.path.expanduser("~")
        self.view_mode = "detail"
        self.active_items = []
        self.sort_column = "name"
        self.sort_reverse = False
        self.one_click_open = False
        self.clipboard = None
        
        self.marquee_offset = 0.0
        self.filter_visible = False

        self._build_tab_ui()
        self._setup_context_menus()
        self.load_directory(self.current_dir)

    def _build_tab_ui(self):
        nav_frame = ttk.Frame(self, padding=(6, 4))
        nav_frame.pack(fill="x")

        ttk.Button(nav_frame, text="⬆ 上へ", width=6, command=self.go_up).pack(side="left", padx=2)
        ttk.Button(nav_frame, text="🔄 更新", width=6, command=self.refresh).pack(side="left", padx=2)
        ttk.Button(nav_frame, text="🧹 自動整理", width=10, command=self.open_auto_organize_dialog).pack(side="left", padx=6)

        ttk.Label(nav_frame, text=" パス:").pack(side="left")
        self.path_entry = ttk.Entry(nav_frame)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=4)
        self.path_entry.bind("<Return>", lambda e: self.load_directory(self.path_entry.get()))

        ttk.Button(nav_frame, text="移動", width=5, command=lambda: self.load_directory(self.path_entry.get())).pack(side="left", padx=2)

        search_frame = ttk.Frame(self, padding=(6, 2))
        search_frame.pack(fill="x")

        ttk.Label(search_frame, text="🔍 検索:").pack(side="left")
        self.query_entry = ttk.Entry(search_frame, width=15)
        self.query_entry.pack(side="left", padx=4)
        self.query_entry.bind("<Return>", lambda e: self.start_async_search())

        self.sub_dir_search_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(search_frame, text="サブディレクトリも検索", variable=self.sub_dir_search_var).pack(side="left", padx=4)

        ttk.Button(search_frame, text="高速検索", command=self.start_async_search).pack(side="left", padx=2)
        ttk.Button(search_frame, text="⚙️ 詳細フィルター", command=self.toggle_filter_panel_animated).pack(side="left", padx=5)

        ttk.Label(search_frame, text=" 表示:").pack(side="left", padx=(6, 2))
        ttk.Button(search_frame, text="詳細", width=4, command=lambda: self.change_view_mode("detail")).pack(side="left", padx=1)
        ttk.Button(search_frame, text="一覧", width=4, command=lambda: self.change_view_mode("list")).pack(side="left", padx=1)
        ttk.Button(search_frame, text="小アイコン", width=8, command=lambda: self.change_view_mode("sm_icon")).pack(side="left", padx=1)
        ttk.Button(search_frame, text="中アイコン", width=8, command=lambda: self.change_view_mode("md_icon")).pack(side="left", padx=1)
        ttk.Button(search_frame, text="大アイコン", width=8, command=lambda: self.change_view_mode("icon")).pack(side="left", padx=1)

        self.progress_bar = ttk.Progressbar(search_frame, mode="indeterminate", length=120)

        self.filter_container = ttk.Frame(self)
        self.filter_frame = ttk.LabelFrame(self.filter_container, text="🎯 拡張検索フィルター条件", padding=8)
        self.filter_frame.pack(fill="x", padx=5, pady=2)
        self._build_filter_panel_widgets()

        self.content_frame = ttk.Frame(self, padding=5)
        self.content_frame.pack(fill="both", expand=True)

        self._setup_views()

    def _build_filter_panel_widgets(self):
        f = self.filter_frame
        row1 = ttk.Frame(f)
        row1.pack(fill="x", pady=2)
        ttk.Label(row1, text="拡張子:").pack(side="left")
        self.filter_ext_entry = ttk.Entry(row1, width=8)
        self.filter_ext_entry.pack(side="left", padx=(2, 10))

        ttk.Label(row1, text="サイズ(KB):").pack(side="left")
        self.filter_minsize_entry = ttk.Entry(row1, width=6)
        self.filter_minsize_entry.pack(side="left", padx=2)
        ttk.Label(row1, text="～").pack(side="left")
        self.filter_maxsize_entry = ttk.Entry(row1, width=6)
        self.filter_maxsize_entry.pack(side="left", padx=2)

        row2 = ttk.Frame(f)
        row2.pack(fill="x", pady=2)
        ttk.Label(row2, text="日付基準:").pack(side="left")
        self.date_type_var = tk.StringVar(value="mtime")
        ttk.Radiobutton(row2, text="最終更新日", variable=self.date_type_var, value="mtime").pack(side="left", padx=2)
        ttk.Radiobutton(row2, text="ファイル作成日", variable=self.date_type_var, value="ctime").pack(side="left", padx=2)

        ttk.Label(row2, text="  期間(YYYY-MM-DD):").pack(side="left")
        self.filter_startdate_entry = ttk.Entry(row2, width=10)
        self.filter_startdate_entry.pack(side="left", padx=2)
        ttk.Label(row2, text="～").pack(side="left")
        self.filter_enddate_entry = ttk.Entry(row2, width=10)
        self.filter_enddate_entry.pack(side="left", padx=2)

        row3 = ttk.Frame(f)
        row3.pack(fill="x", pady=2)
        ttk.Label(row3, text="アーティスト:").pack(side="left")
        self.filter_artist_entry = ttk.Entry(row3, width=15)
        self.filter_artist_entry.pack(side="left", padx=(2, 10))

        ttk.Label(row3, text="製作者:").pack(side="left")
        self.filter_creator_entry = ttk.Entry(row3, width=15)
        self.filter_creator_entry.pack(side="left", padx=(2, 10))

        ttk.Button(row3, text="フィルター適用", command=self.start_async_search).pack(side="left", padx=5)
        ttk.Button(row3, text="クリア", command=self.clear_filters).pack(side="left", padx=2)

    def toggle_filter_panel_animated(self):
        self.filter_visible = not self.filter_visible
        if self.filter_visible:
            self.filter_container.pack(fill="x", before=self.content_frame, padx=5, pady=2)
        else:
            self.filter_container.pack_forget()

    def clear_filters(self):
        self.filter_ext_entry.delete(0, tk.END)
        self.filter_minsize_entry.delete(0, tk.END)
        self.filter_maxsize_entry.delete(0, tk.END)
        self.filter_startdate_entry.delete(0, tk.END)
        self.filter_enddate_entry.delete(0, tk.END)
        self.filter_artist_entry.delete(0, tk.END)
        self.filter_creator_entry.delete(0, tk.END)
        self.start_async_search()

    def _get_current_filter_params(self):
        params = {}
        try:
            min_s = self.filter_minsize_entry.get().strip()
            params["min_size"] = float(min_s) if min_s else None
        except ValueError:
            params["min_size"] = None
        try:
            max_s = self.filter_maxsize_entry.get().strip()
            params["max_size"] = float(max_s) if max_s else None
        except ValueError:
            params["max_size"] = None

        params["ext"] = self.filter_ext_entry.get()
        params["date_type"] = self.date_type_var.get()
        params["start_date"] = self.filter_startdate_entry.get()
        params["end_date"] = self.filter_enddate_entry.get()
        params["artist"] = self.filter_artist_entry.get()
        params["creator"] = self.filter_creator_entry.get()
        return params

    def _setup_views(self):
        cols = ("icon", "name", "size", "mtime", "path")
        self.tree = ttk.Treeview(self.content_frame, columns=cols, show="headings", selectmode="browse")
        
        headers = [
            ("icon", "🏷️", 40), ("name", "名前", 320), ("size", "サイズ", 95), ("mtime", "更新日時", 140), ("path", "パス", 300)
        ]

        for col_id, text, width in headers:
            self.tree.heading(col_id, text=text, command=lambda c=col_id: self.sort_by_column(c))
            anchor = "center" if col_id in ["icon", "mtime"] else ("e" if col_id == "size" else "w")
            self.tree.column(col_id, width=width, anchor=anchor)

        self.tree.bind("<ButtonRelease-1>", self.on_item_click)
        self.tree.bind("<Double-1>", self.on_item_double_click)
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<Return>", lambda e: self.open_selected())
        self.tree.bind("<Delete>", lambda e: self.delete_selected())
        self.tree.bind("<MouseWheel>", self._on_tree_mouse_wheel)

        self.tree_scroll = ttk.Scrollbar(self.content_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=self.tree_scroll.set)

        self.canvas_view = tk.Canvas(self.content_frame, bg="#FFFFFF", highlightthickness=0)
        self.canvas_view.bind("<MouseWheel>", self._on_canvas_mouse_wheel)
        self.canvas_view.bind("<Button-3>", self.show_blank_context_menu)
        
        self.canvas_scroll = ttk.Scrollbar(self.content_frame, orient="vertical", command=self.canvas_view.yview)
        self.canvas_view.configure(yscrollcommand=self.canvas_scroll.set)

    def _on_tree_mouse_wheel(self, event):
        if os.name == 'nt':
            self.tree.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_canvas_mouse_wheel(self, event):
        if os.name == 'nt':
            self.canvas_view.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _setup_context_menus(self):
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="📁 開く", command=self.open_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="✂️ 切り取り", command=lambda: self.set_clipboard("cut"))
        self.context_menu.add_command(label="📋 コピー", command=lambda: self.set_clipboard("copy"))
        self.context_menu.add_command(label="📌 貼り付け", command=self.paste_clipboard)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🗑️ 削除", command=self.delete_selected)
        self.context_menu.add_command(label="✏️ 名前の変更", command=self.rename_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="📂 新規作成 (フォルダー/ファイル)", command=self.create_new_item_dialog)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="ℹ️ プロパティ", command=self.show_properties)

        self.blank_context_menu = tk.Menu(self, tearoff=0)
        self.blank_context_menu.add_command(label="📂 新規作成 (フォルダー/ファイル)", command=self.create_new_item_dialog)
        self.blank_context_menu.add_command(label="📌 貼り付け", command=self.paste_clipboard)
        self.blank_context_menu.add_separator()
        self.blank_context_menu.add_command(label="🧹 このフォルダを自動整理", command=self.open_auto_organize_dialog)
        self.blank_context_menu.add_separator()
        self.blank_context_menu.add_command(label="🔄 更新", command=self.refresh)

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
        else:
            self.blank_context_menu.post(event.x_root, event.y_root)

    def show_blank_context_menu(self, event):
        self.blank_context_menu.post(event.x_root, event.y_root)

    def set_clipboard(self, action_type):
        selected = self.tree.selection()
        if selected:
            vals = self.tree.item(selected[0], "values")
            self.clipboard = (action_type, vals[4])

    def paste_clipboard(self):
        if not self.clipboard: 
            messagebox.showwarning("情報", "クリップボードにファイルがありません。")
            return
        action, src_path = self.clipboard
        filename = os.path.basename(src_path)
        dest_path = os.path.join(self.current_dir, filename)

        try:
            if action == "copy":
                if os.path.isdir(src_path): shutil.copytree(src_path, dest_path)
                else: shutil.copy2(src_path, dest_path)
            elif action == "cut":
                shutil.move(src_path, dest_path)
                self.clipboard = None
            self.refresh()
        except Exception as e:
            messagebox.showerror("エラー", f"貼り付けに失敗しました:\n{e}")

    def create_new_item_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("新規作成")
        dlg.geometry("340x180+250+200")
        dlg.resizable(False, False)

        ttk.Label(dlg, text="種類を選択して名前を入力してください:", font=("Segoe UI", 9)).pack(padx=10, pady=10, anchor="w")
        
        mode_var = tk.StringVar(value="folder")
        f_frame = ttk.Frame(dlg)
        f_frame.pack(fill="x", padx=10)
        ttk.Radiobutton(f_frame, text="フォルダー", variable=mode_var, value="folder").pack(side="left", padx=5)
        ttk.Radiobutton(f_frame, text="空のファイル (.txt 等)", variable=mode_var, value="file").pack(side="left", padx=5)

        entry_name = ttk.Entry(dlg, width=30)
        entry_name.pack(padx=10, pady=10)
        entry_name.insert(0, "新しい項目")

        def _execute():
            name = entry_name.get().strip()
            if not name: return
            target_p = os.path.join(self.current_dir, name)
            try:
                if mode_var.get() == "folder":
                    os.makedirs(target_p, exist_ok=True)
                else:
                    with open(target_p, "w", encoding="utf-8") as f:
                        f.write("")
                dlg.destroy()
                self.refresh()
            except Exception as e:
                messagebox.showerror("エラー", f"作成できませんでした:\n{e}")

        ttk.Button(dlg, text="作成", command=_execute).pack(pady=5)

    def rename_selected(self):
        selected = self.tree.selection()
        if not selected: return
        vals = self.tree.item(selected[0], "values")
        target_path = vals[4]
        old_name = os.path.basename(target_path)

        new_name = filedialog.asksaveasfilename(initialdir=self.current_dir, initialfile=old_name, title="名前の変更")
        if new_name and new_name != target_path:
            try:
                os.rename(target_path, new_name)
                self.refresh()
            except Exception as e:
                messagebox.showerror("エラー", f"名前を変更できませんでした:\n{e}")

    def sort_by_column(self, col):
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False
        self.render_current_items()

    def change_view_mode(self, mode):
        self.view_mode = mode
        self.render_current_items()

    def load_directory(self, target_dir):
        if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
            messagebox.showerror("エラー", "指定されたフォルダが存在しません。")
            return

        self.current_dir = os.path.abspath(target_dir)
        self.path_entry.delete(0, tk.END)
        self.path_entry.insert(0, self.current_dir)
        self.query_entry.delete(0, tk.END)

        raw_files = []
        try:
            for item in os.listdir(self.current_dir):
                full_path = os.path.join(self.current_dir, item)
                raw_files.append(self._get_file_info(full_path))
        except Exception as e:
            messagebox.showerror("エラー", f"アクセスできませんでした:\n{e}")
            return

        self._process_items(raw_files, query="")
        try:
            tab_title = os.path.basename(self.current_dir) or self.current_dir
            self.master_app.notebook.tab(self, text=f" 📁 {tab_title} ")
        except Exception:
            pass

    def start_async_search(self):
        query = self.query_entry.get().strip()
        filter_params = self._get_current_filter_params()
        sub_search_enabled = self.sub_dir_search_var.get()

        self.progress_bar.pack(side="right", padx=8)
        self.progress_bar.start(12)

        def _async_task():
            found_files = []
            max_results = 500

            if sub_search_enabled:
                for root_path, dirs, files in os.walk(self.current_dir):
                    for d in dirs:
                        found_files.append(self._get_file_info(os.path.join(root_path, d)))
                    for f in files:
                        found_files.append(self._get_file_info(os.path.join(root_path, f)))
                    if len(found_files) >= max_results: 
                        break
            else:
                try:
                    for item in os.listdir(self.current_dir):
                        found_files.append(self._get_file_info(os.path.join(self.current_dir, item)))
                except Exception:
                    pass

            self.after(0, lambda: self._on_search_complete(found_files, query, filter_params))

        threading.Thread(target=_async_task, daemon=True).start()

    def _on_search_complete(self, raw_files, query, filter_params):
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self._process_items(raw_files, query, filter_params)

    def _get_file_info(self, full_path):
        is_dir = os.path.isdir(full_path)
        name = os.path.basename(full_path)
        ext = "" if is_dir else os.path.splitext(name)[1]

        try:
            stat = os.stat(full_path)
            size = stat.st_size
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            ctime = datetime.datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            size, mtime, ctime = 0, "----", "----"

        artist, creator = "一般ファイル", "システム"
        name_lower = name.lower()
        if "ymmp" in name_lower or "mp4" in name_lower:
            artist, creator = "Studio-A", "AuthorX"
        elif "java" in name_lower or "jar" in name_lower:
            artist, creator = "DevTeam", "CoderY"

        return {"name": name, "path": full_path, "ext": ext, "is_dir": is_dir, "size": size, "mtime": mtime, "ctime": ctime, "artist": artist, "creator": creator}

    def _process_items(self, raw_files, query, filter_params=None):
        processed = []
        for f in raw_files:
            sssa_score, base_score, p_field = calculate_file_scores(query, f, filter_params)
            if sssa_score < 0: continue
            processed.append({"info": f, "score": sssa_score, "base": base_score, "p_field": p_field})

        self.active_items = processed
        self.render_current_items()

    def _get_pixel_scrolling_name(self, name, max_len=16, offset=0.0):
        if len(name) <= max_len:
            return name
        padded = name + "     "
        rot = int(offset) % len(padded)
        return (padded + padded)[rot:rot + max_len]

    def render_current_items(self, update_only_marquee=False, marquee_offset=0.0):
        if not update_only_marquee:
            self.tree.pack_forget()
            self.tree_scroll.pack_forget()
            self.canvas_view.pack_forget()
            self.canvas_scroll.pack_forget()

            def sort_key(x):
                f = x["info"]
                if self.sort_column == "name": return f["name"].lower()
                elif self.sort_column == "size": return f["size"]
                elif self.sort_column == "mtime": return f["mtime"]
                elif self.sort_column == "frequency": return x["score"]
                elif self.sort_column == "type": return f["ext"].lower()
                else: return f["name"].lower()

            self.active_items.sort(key=sort_key, reverse=self.sort_reverse)
            self.master_app.bar_viewer.update_bars(self.active_items, self.sort_column, self.sort_reverse)

        if self.view_mode == "detail":
            if not update_only_marquee:
                self.tree.pack(side="left", fill="both", expand=True)
                self.tree_scroll.pack(side="right", fill="y")
            
            rows = self.tree.get_children()
            if not self.active_items:
                if not rows:
                    self.tree.insert("", "end", values=("⚠️", "[!] 該当するファイルがありません [!]", "---", "---", ""))
                return

            for i, res in enumerate(self.active_items):
                f = res["info"]
                icon_sym = get_file_icon_symbol(f["is_dir"], f["ext"])
                size_str = "<DIR>" if f["is_dir"] else f"{f['size'] / 1024:.1f} KB"
                name_disp = self._get_pixel_scrolling_name(f["name"], max_len=30, offset=marquee_offset)

                values = (icon_sym, name_disp, size_str, f["mtime"], f["path"])
                if i < len(rows):
                    self.tree.item(rows[i], values=values)
                else:
                    self.tree.insert("", "end", values=values)
        else:
            if not update_only_marquee:
                self.canvas_view.pack(side="left", fill="both", expand=True)
                self.canvas_scroll.pack(side="right", fill="y")

            self.canvas_view.delete("all")
            if not self.active_items:
                self.canvas_view.create_text(250, 100, text="[!] 該当するファイルがありません [!]", fill="#00aa66", font=("Consolas", 14, "bold"))
                return

            canvas_width = self.canvas_view.winfo_width() or 700
            box_w, box_h = 120, 100
            cols_count = max(1, canvas_width // (box_w + 8))

            for idx, res in enumerate(self.active_items):
                f = res["info"]
                r = idx // cols_count
                c = idx % cols_count
                x0 = 8 + c * (box_w + 8)
                y0 = 8 + r * (box_h + 8)
                rect_id = self.canvas_view.create_rectangle(x0, y0, x0 + box_w, y0 + box_h, fill="#F2F9FC", outline="#A0C0E0", width=1)
                t1 = self.canvas_view.create_text(x0 + box_w/2, y0 + 30, text=get_file_icon_symbol(f["is_dir"], f["ext"]), font=("Helvetica", 22))
                t2 = self.canvas_view.create_text(x0 + box_w/2, y0 + 65, text=self._get_pixel_scrolling_name(f["name"], 10, offset=marquee_offset), font=("Helvetica", 9))
                
                for elem in [rect_id, t1, t2]:
                    self.canvas_view.tag_bind(elem, "<Double-1>", lambda e, p=f["path"]: self.open_target_path(p))

    def on_item_click(self, event):
        if self.one_click_open: self.open_selected()

    def on_item_double_click(self, event):
        if not self.one_click_open: self.open_selected()

    def open_selected(self):
        selected = self.tree.selection()
        if not selected: return
        vals = self.tree.item(selected[0], "values")
        if vals and len(vals) >= 5 and vals[4]:
            self.open_target_path(vals[4])

    def open_target_path(self, target_path):
        if os.path.isdir(target_path):
            self.load_directory(target_path)
        elif os.path.isfile(target_path):
            try: os.startfile(target_path)
            except Exception as e: messagebox.showerror("エラー", f"起動できませんでした:\n{e}")

    def delete_selected(self):
        selected = self.tree.selection()
        if not selected: return
        vals = self.tree.item(selected[0], "values")
        target_path = vals[4]

        if messagebox.askyesno("削除の確認", f"以下の項目を削除しますか？\n{target_path}"):
            try:
                if os.path.isdir(target_path): os.rmdir(target_path)
                else: os.remove(target_path)
                self.refresh()
            except Exception as e: messagebox.showerror("エラー", f"削除できませんでした:\n{e}")

    def show_properties(self):
        selected = self.tree.selection()
        if not selected: return
        vals = self.tree.item(selected[0], "values")
        target_path = vals[4]

        try:
            stat = os.stat(target_path)
            target_info = next((item["info"] for item in self.active_items if item["info"]["path"] == target_path), None)
            
            info = (
                f"【ファイル名】 {os.path.basename(target_path)}\n"
                f"【格納場所】 {os.path.dirname(target_path)}\n"
                f"【ファイル形式】 {'フォルダー' if os.path.isdir(target_path) else target_info.get('ext', '不明')}\n"
                f"【サイズ】 {stat.st_size:,} バイト ({stat.st_size / 1024:.2f} KB)\n"
                f"【最終更新日時】 {datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"【ファイル作成日時】 {datetime.datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"【最終アクセス日時】 {datetime.datetime.fromtimestamp(stat.st_atime).strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"【アーティスト / 作者】 {target_info['artist'] if target_info else '---'}\n"
                f"【製作者 / 開発元】 {target_info['creator'] if target_info else '---'}\n"
                f"【システム属性】 読み取り専用: {not os.access(target_path, os.W_OK)}"
            )
            messagebox.showinfo("詳細プロパティ", info)
        except Exception as e:
            messagebox.showerror("エラー", f"プロパティを取得できませんでした:\n{e}")

    def go_up(self):
        parent_p = os.path.dirname(self.current_dir)
        if parent_p and os.path.exists(parent_p):
            self.load_directory(parent_p)

    def refresh(self):
        self.load_directory(self.current_dir)

    def open_auto_organize_dialog(self):
        AutoOrganizeDialog(self, self.current_dir, self.refresh)


# ==========================================
# 6. メインウィンドウ ＆ 拡張ソート機能統合 (VSync同期・リサイズ対応版)
# ==========================================
class ArcexplorerMainApp:
    def __init__(self, root):
        self.root = root
        self.root.overrideredirect(True)
        self.root.geometry("1300x820+100+60")
        self.is_maximized = False
        self.normal_geometry = "1300x820+100+60"
        
        self.old_x = 0
        self.old_y = 0
        
        # リサイズ用の状態変数
        self.resize_edge = None
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.window_start_geometry = ""

        # VSync風 UI同期制御用変数 (ターゲット 60 FPS = 約 16ms 周期)
        self.target_fps = 60
        self.frame_interval_ms = int(1000 / self.target_fps)
        self.marquee_offset = 0.0

        self._apply_aero_theme_styles()
        self._build_aero_window_frame()
        self._start_vsync_ui_loop()
        
        # タスクバーに確実にアイコン・ウィンドウを表示させるための遅延適用
        self.root.after(100, self._ensure_taskbar_presence)

    def _ensure_taskbar_presence(self):
        # Windows環境等でタスクバーに常時表示させるための一時的なポップアップ解除・再設定ハック
        if os.name == 'nt':
            try:
                self.root.update_idletasks()
                # 윈도우 스타일을 툴/일반 윈도우 속성으로 다듬기
                hwnd = windll.user32.GetParent(self.root.winfo_id())
                # GWL_EXSTYLE = -20, WS_EX_APPWINDOW = 0x00040000
                style = windll.user32.GetWindowLongW(hwnd, -20)
                windll.user32.SetWindowLongW(hwnd, -20, style | 0x00040000)
            except Exception:
                pass

    def _apply_aero_theme_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background="#E4F1FA", foreground="#112233", font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#D8EDFC", foreground="#103050", font=("Segoe UI", 9, "bold"))

    def _build_aero_window_frame(self):
        container_outer = tk.Frame(self.root, bg="#1E4B72", padx=1, pady=1)
        container_outer.pack(fill="both", expand=True)

        # ウィンドウの端を検出してリサイズするためのダミー透明枠 / バインド領域
        container_outer.bind("<Button-1>", self.on_edge_press)
        container_outer.bind("<B1-Motion>", self.on_edge_drag)
        container_outer.bind("<Motion>", self.update_resize_cursor)

        main_paned = ttk.PanedWindow(container_outer, orient="horizontal")
        main_paned.pack(fill="both", expand=True, padx=4, pady=4)

        sidebar_frame = ttk.Frame(main_paned, width=240)
        main_paned.add(sidebar_frame, weight=1)

        self.nav_tree = ttk.Treeview(sidebar_frame, show="tree", selectmode="browse")
        self.nav_tree.pack(fill="both", expand=True, padx=2, pady=2)
        self.nav_tree.bind("<<TreeviewSelect>>", self.on_nav_tree_select)

        self._populate_nav_tree()

        sort_control_frame = ttk.LabelFrame(sidebar_frame, text=" 🔄 並び替え設定 ", padding=6)
        sort_control_frame.pack(fill="x", padx=4, pady=4, side="bottom")

        self.sort_col_var = tk.StringVar(value="name")
        sort_combobox = ttk.Combobox(sort_control_frame, textvariable=self.sort_col_var, state="readonly", values=[
            "name", "size", "frequency", "mtime", "type"
        ])
        sort_combobox.pack(fill="x", pady=2)
        sort_combobox.bind("<<ComboboxSelected>>", self.on_sort_combobox_changed)

        self.sort_order_var = tk.StringVar(value="昇順")
        order_frame = ttk.Frame(sort_control_frame)
        order_frame.pack(fill="x", pady=2)
        ttk.Radiobutton(order_frame, text="昇順", variable=self.sort_order_var, value="昇順", command=self.on_sort_combobox_changed).pack(side="left")
        ttk.Radiobutton(order_frame, text="降順", variable=self.sort_order_var, value="降順", command=self.on_sort_combobox_changed).pack(side="left", padx=10)

        self.bar_viewer = BarChartSortViewer(sidebar_frame, padding=4)
        self.bar_viewer.pack(fill="x", padx=4, pady=4, side="bottom")

        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=5)

        tab_ctrl_frame = tk.Frame(right_frame, bg="#D4EDFC", height=38)
        tab_ctrl_frame.pack(fill="x")
        tab_ctrl_frame.bind("<Button-1>", self.start_window_drag)
        tab_ctrl_frame.bind("<B1-Motion>", self.do_window_drag)
        tab_ctrl_frame.bind("<Double-Button-1>", lambda e: self.toggle_maximize())

        # ウィンドウ操作ボタン（最小化・最大化/元に戻す・閉じる）
        close_btn = tk.Button(tab_ctrl_frame, text="✕", bg="#D4EDFC", fg="#103050", relief="flat", width=4, bd=0, command=self.root.destroy, activebackground="#E81123", activeforeground="#FFFFFF")
        close_btn.pack(side="right", fill="y")

        self.max_btn = tk.Button(tab_ctrl_frame, text="🗖", bg="#D4EDFC", fg="#103050", relief="flat", width=4, bd=0, command=self.toggle_maximize, activebackground="#C0D0E0", activeforeground="#103050")
        self.max_btn.pack(side="right", fill="y")

        min_btn = tk.Button(tab_ctrl_frame, text="🗕", bg="#D4EDFC", fg="#103050", relief="flat", width=4, bd=0, command=self.minimize_window, activebackground="#C0D0E0", activeforeground="#103050")
        min_btn.pack(side="right", fill="y")

        new_tab_btn = tk.Button(tab_ctrl_frame, text="＋ 新規タブ", bg="#C0E0F8", fg="#103050", font=("Segoe UI", 8, "bold"), relief="flat", padx=8, pady=2, command=self.add_new_tab)
        new_tab_btn.pack(side="left", padx=8, pady=4)

        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill="both", expand=True)
        self.add_new_tab()

    # --- VSync (垂直同期) 風のUIフレームレート制御・更新ループ ---
    def _start_vsync_ui_loop(self):
        def vsync_tick():
            if not self.root.winfo_exists():
                return
            t_start = time.time()
            
            # アニメーション等の進行量を更新
            self.marquee_offset += 0.25
            
            # 現在アクティブなタブの描画更新を垂直同期フレームに合わせる
            try:
                curr_tab = self.get_current_tab()
                if curr_tab and curr_tab.active_items:
                    curr_tab.render_current_items(update_only_marquee=True, marquee_offset=self.marquee_offset)
            except Exception:
                pass

            # 次のフレームまでの経過時間を調整 (VSync同期エミュレーション)
            elapsed_ms = int((time.time() - t_start) * 1000)
            sleep_time = max(1, self.frame_interval_ms - elapsed_ms)
            self.root.after(sleep_time, vsync_tick)

        self.root.after(self.frame_interval_ms, vsync_tick)

    # --- フレームレスウィンドウ向けリサイズ・ドラッグ処理 ---
    def _get_resize_edge(self, event):
        if self.is_maximized:
            return None
        border = 6
        # eventの座標はバインドされているウィジェット（container_outer）内基準になる場合があるため、
        # ウィンドウ全体に対する相対位置を計算するか、またはウィジェット内での端判定を厳密に行う
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x, y = event.x, event.y

        left = x < border
        right = x > w - border
        top = y < border
        bottom = y > h - border

        if top and left: return "top_left"
        if top and right: return "top_right"
        if bottom and left: return "bottom_left"
        if bottom and right: return "bottom_right"
        if top: return "top"
        if bottom: return "bottom"
        if left: return "left"
        if right: return "right"
        return None

    def update_resize_cursor(self, event):
        if self.is_maximized:
            self.root.config(cursor="")
            return
        edge = self._get_resize_edge(event)
        cursors = {
            "top": "top_side", "bottom": "bottom_side",
            "left": "left_side", "right": "right_side",
            "top_left": "top_left_corner", "top_right": "top_right_corner",
            "bottom_left": "bottom_left_corner", "bottom_right": "bottom_right_corner"
        }
        # マウスカーソルが正しく反映されるように対応する形状を設定
        target_cursor = cursors.get(edge, "")
        if self.root.cget("cursor") != target_cursor:
            self.root.config(cursor=target_cursor)

    def on_edge_press(self, event):
        self.resize_edge = self._get_resize_edge(event)
        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root
        self.window_start_geometry = self.root.geometry()

    def on_edge_drag(self, event):
        if not self.resize_edge or self.is_maximized:
            return

        dx = event.x_root - self.drag_start_x
        dy = event.y_root - self.drag_start_y

        try:
            parts = self.window_start_geometry.replace('+', 'x').replace('-', 'x').split('x')
            w, h, x, y = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
        except Exception:
            return

        min_w, min_h = 400, 300

        if "right" in self.resize_edge:
            w = max(min_w, w + dx)
        if "bottom" in self.resize_edge:
            h = max(min_h, h + dy)
        if "left" in self.resize_edge:
            new_w = max(min_w, w - dx)
            if new_w != min_w:
                x += dx
                w = new_w
        if "top" in self.resize_edge:
            new_h = max(min_h, h - dy)
            if new_h != min_h:
                y += dy
                h = new_h

        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def minimize_window(self):
        self.root.update_idletasks()
        self.root.overrideredirect(False)
        self.root.iconify()
        self.root.bind("<Map>", self._on_window_restored)

    def _on_window_restored(self, event):
        self.root.unbind("<Map>")
        self.root.overrideredirect(True)
        self._ensure_taskbar_presence()

    def toggle_maximize(self):
        if not self.is_maximized:
            self.normal_geometry = self.root.geometry()
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            self.root.geometry(f"{sw}x{sh}+0+0")
            self.is_maximized = True
            self.max_btn.config(text="🗗")
        else:
            self.root.geometry(self.normal_geometry)
            self.is_maximized = False
            self.max_btn.config(text="🗖")

    def on_sort_combobox_changed(self, event=None):
        try:
            current_tab = self.get_current_tab()
            current_tab.sort_column = self.sort_col_var.get()
            current_tab.sort_reverse = (self.sort_order_var.get() == "降順")
            current_tab.render_current_items()
        except Exception:
            pass

    def start_window_drag(self, event):
        if not self.is_maximized:
            self.old_x = event.x_root
            self.old_y = event.y_root

    def do_window_drag(self, event):
        if not self.is_maximized:
            x = self.root.winfo_x() + (event.x_root - self.old_x)
            y = self.root.winfo_y() + (event.y_root - self.old_y)
            self.root.geometry(f"+{x}+{y}")
            self.old_x = event.x_root
            self.old_y = event.y_root

    def _populate_nav_tree(self):
        user_home = os.path.expanduser("~")
        desktop_path = get_desktop_path()

        qa_node = self.nav_tree.insert("", "end", text="⭐ クイックアクセス", open=True)
        self.nav_tree.insert(qa_node, "end", text="🏠 ホーム", values=(user_home,))
        self.nav_tree.insert(qa_node, "end", text="🖥️ デスクトップ", values=(desktop_path,))
        self.nav_tree.insert(qa_node, "end", text="📥 ダウンロード", values=(os.path.join(user_home, "Downloads"),))
        self.nav_tree.insert(qa_node, "end", text="📄 ドキュメント", values=(os.path.join(user_home, "Documents"),))

        pc_node = self.nav_tree.insert("", "end", text="💻 PC", open=True)
        for drive in get_system_drives():
            dev_icon = get_device_icon(drive.lower(), drive.lower())
            self.nav_tree.insert(pc_node, "end", text=f"{dev_icon} ローカルディスク ({drive})", values=(drive,))

    def on_nav_tree_select(self, event):
        selected = self.nav_tree.selection()
        if selected:
            vals = self.nav_tree.item(selected[0], "values")
            if vals and len(vals) >= 1 and os.path.exists(vals[0]):
                self.get_current_tab().load_directory(vals[0])

    def add_new_tab(self, path=None):
        tab_page = ExplorerTabPage(self.notebook, master_app=self, initial_dir=path)
        tab_title = os.path.basename(tab_page.current_dir) or tab_page.current_dir
        self.notebook.add(tab_page, text=f" 📁 {tab_title} ")
        self.notebook.select(tab_page)

    def get_current_tab(self):
        selected_id = self.notebook.select()
        return self.notebook.nametowidget(selected_id)


if __name__ == "__main__":
    root = tk.Tk()
    app = ArcexplorerMainApp(root)
    root.mainloop()
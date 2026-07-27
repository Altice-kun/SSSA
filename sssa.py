import math
import random
import time
import threading
import tkinter as tk
from tkinter import ttk

# 効果音ライブラリ（Windows標準）
try:
    import winsound
    HAS_SOUND = True
except ImportError:
    HAS_SOUND = False


# ==========================================
# 1. SSSA スコア & カバー率計算
# ==========================================
def calculate_sssa_score(query_str, doc):
    query_words = [w.strip().lower() for w in query_str.split() if w.strip()]
    if not query_words:
        return 0.0, 0.0, 0.0

    name_txt = doc['name'].lower()
    content_txt = doc['content'].lower()
    desc_txt = doc['description'].lower()

    # ① キーワード一致数
    all_text = f"{name_txt} {content_txt} {desc_txt}"
    matched_words = sum(1 for word in query_words if word in all_text)
    match_count_score = matched_words / len(query_words)

    # ② キーワード出現数
    total_tf = sum(all_text.count(word) for word in query_words)
    term_freq_score = min(1.0, math.log1p(total_tf) / 3.0)

    # ③ 類語・文脈スコア
    context_score = doc.get('context_score', 0.5)

    base_score = (match_count_score + term_freq_score + context_score) / 3.0

    # ④ カバー率
    fields = [name_txt, content_txt, desc_txt]
    hit_fields = sum(1 for f in fields if any(word in f for word in query_words))
    p_field = (hit_fields / len(fields)) * 100.0

    sssa_score = base_score * (p_field / 100.0)

    return round(sssa_score, 4), round(base_score, 4), round(p_field, 1)


# ==========================================
# 2. サンプルデータ生成
# ==========================================
SAMPLE_KEYWORDS = ["Python", "AI", "データ", "アルゴリズム", "Web", "高速化", "検索", "サーバー", "開発", "クラウド", "セキュリティ"]

def generate_sample_data(count=40):
    docs = []
    for i in range(1, count + 1):
        if random.random() < 0.2:
            doc = {
                "id": f"DOC-{i:03d}",
                "name": f"全般仕様書 #{i}",
                "content": "社内システム運用管理マニュアル。キーワード非該当。",
                "description": "システム管理者用アーカイブ資料。",
                "context_score": round(random.uniform(0.1, 0.3), 2)
            }
        else:
            k1, k2 = random.sample(SAMPLE_KEYWORDS, 2)
            doc = {
                "id": f"DOC-{i:03d}",
                "name": f"{k1}活用 {k2}システム構築モジュール",
                "content": f"本仕様書は{k1}環境で{k2}を最適化する内部ロジックを規定します。",
                "description": f"{k1}アーキテクチャ設計者向け文書。",
                "context_score": round(random.uniform(0.4, 0.95), 2)
            }
        docs.append(doc)
    return docs


# ==========================================
# 3. GUI & ソーティングアプリケーション
# ==========================================
class SSSAGuiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SSSA ソーティングビューワー (SSSAスコア ＋ 基本スコア 複合ソート版)")
        self.root.geometry("1380x850")

        self.documents = generate_sample_data(40)
        self.active_items = []
        self.is_sorting = False
        self.last_sound_time = 0

        self.sound_enabled = tk.BooleanVar(value=True)
        self.session_status = tk.StringVar(value="待機中")
        self.session_info = tk.StringVar(value="パス: 0 | 交換回数: 0 | 確定数: 0")

        self._build_ui()
        self.run_search(animate=False)

    def play_beep_async(self, score_val, duration=15):
        if not self.sound_enabled.get() or not HAS_SOUND:
            return

        def _sound_thread():
            try:
                freq = int(400 + score_val * 1200)
                freq = max(37, min(32767, freq))
                winsound.Beep(freq, duration)
            except Exception:
                pass

        threading.Thread(target=_sound_thread, daemon=True).start()

    def _build_ui(self):
        ctrl_frame = ttk.LabelFrame(self.root, text="検索 & ソート設定", padding=8)
        ctrl_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(ctrl_frame, text="キーワード:").pack(side="left", padx=2)
        self.query_entry = ttk.Entry(ctrl_frame, width=18)
        self.query_entry.insert(0, "Python AI")
        self.query_entry.pack(side="left", padx=5)

        ttk.Button(ctrl_frame, text="🔍 検索・10区分分け＆ソート開始", command=lambda: self.run_search(animate=True)).pack(side="left", padx=5)

        ttk.Label(ctrl_frame, text="件数:").pack(side="left", padx=(10, 2))
        self.count_spinbox = ttk.Spinbox(ctrl_frame, from_=5, to=300, width=5)
        self.count_spinbox.set(40)
        self.count_spinbox.pack(side="left", padx=2)

        ttk.Button(ctrl_frame, text="🎲 データ再生成", command=self.reload_sample_data).pack(side="left", padx=5)

        ttk.Label(ctrl_frame, text="速度:").pack(side="left", padx=(10, 2))
        self.speed_scale = ttk.Scale(ctrl_frame, from_=0.001, to=0.1, value=0.015, length=70)
        self.speed_scale.pack(side="left")

        ttk.Checkbutton(ctrl_frame, text="🔊 効果音", variable=self.sound_enabled).pack(side="left", padx=(10, 0))

        # セッション状態表示バー
        status_frame = ttk.Frame(self.root, padding=(10, 2))
        status_frame.pack(fill="x")
        ttk.Label(status_frame, text="セッション状態: ", font=("Helvetica", 9, "bold")).pack(side="left")
        ttk.Label(status_frame, textvariable=self.session_status, foreground="#0066CC", font=("Helvetica", 9, "bold")).pack(side="left", padx=(0, 20))
        ttk.Label(status_frame, textvariable=self.session_info).pack(side="left")

        # メインパネル
        main_pane = ttk.PanedWindow(self.root, orient="horizontal")
        main_pane.pack(fill="both", expand=True, padx=10, pady=5)

        table_frame = ttk.LabelFrame(main_pane, text="データ一覧 (コンテンツ名表示)", padding=5)
        main_pane.add(table_frame, weight=4)

        cols = ("rank", "id", "name", "score", "base", "p_field", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        
        self.tree.heading("rank", text="順位")
        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="コンテンツ名")
        self.tree.heading("score", text="SSSAスコア")
        self.tree.heading("base", text="基本スコア")
        self.tree.heading("p_field", text="カバー率")
        self.tree.heading("status", text="状態")

        self.tree.column("rank", width=40, anchor="center")
        self.tree.column("id", width=60, anchor="center")
        self.tree.column("name", width=140, anchor="w")
        self.tree.column("score", width=75, anchor="e")
        self.tree.column("base", width=65, anchor="e")
        self.tree.column("p_field", width=60, anchor="e")
        self.tree.column("status", width=50, anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        visual_frame = ttk.LabelFrame(main_pane, text="10区分 (左100% 〜 右10%) ＆ ビューワー", padding=5)
        main_pane.add(visual_frame, weight=6)

        self.canvas = tk.Canvas(visual_frame, bg="#121212")
        self.canvas.pack(fill="both", expand=True)

    def reload_sample_data(self):
        try:
            count = int(self.count_spinbox.get())
            count = max(5, count)
        except ValueError:
            count = 40
        self.documents = generate_sample_data(count)
        self.run_search(animate=True)

    def partition_into_10_buckets(self):
        """10区分分け (SSSAスコア ＋ 基本スコアを複合考慮)"""
        buckets = [[] for _ in range(10)]

        for item in self.active_items:
            # 評価値: SSSAスコア70% + 基本スコア30% で大まかなバケット配置
            composite_score = item["score"] * 0.7 + item["base"] * 0.3
            bucket_idx = int((1.0 - min(1.0, max(0.0, composite_score))) * 10)
            if bucket_idx >= 10:
                bucket_idx = 9
            buckets[bucket_idx].append(item)

        partitioned = []
        for b in buckets:
            random.shuffle(b)
            partitioned.extend(b)

        self.active_items = partitioned

    def run_search(self, animate=True):
        if self.is_sorting:
            return

        query = self.query_entry.get()
        all_scored = []
        for doc in self.documents:
            sssa_score, base_score, p_field = calculate_sssa_score(query, doc)
            all_scored.append({
                "doc": doc,
                "score": sssa_score,
                "base": base_score,
                "p_field": p_field,
                "locked": False
            })

        self.active_items = all_scored

        if animate:
            self.partition_into_10_buckets()
            self.animate_custom_sort()
        else:
            # SSSAスコア(第1優先)、基本スコア(第2優先)でソート
            self.active_items.sort(key=lambda x: (x["score"], x["base"]), reverse=True)
            self.session_status.set("完了")
            self.update_table()
            self.draw_viewer()

    def animate_custom_sort(self):
        self.is_sorting = True
        self.session_status.set("10区分分け完了 -> 細部ソート(SSSA+基本スコア)実行中...")

        n = len(self.active_items)
        concurrent_count = max(1, 1 + (n // 10))

        step_state = {
            "pass": 1,
            "total_swaps": 0,
            "curr_idx": 0
        }

        def step():
            if not self.root.winfo_exists():
                return

            active_indices = []
            processed = 0

            # ① ソート処理 (SSSAスコアと基本スコアの組み合わせタプルで比較)
            while step_state["curr_idx"] < n - 1 and processed < concurrent_count:
                i = step_state["curr_idx"]
                step_state["curr_idx"] += 1

                max_j = min(n, i + 6)
                for j in range(i + 1, max_j):
                    active_indices.extend([i, j])

                    # 比較ロジック: (SSSAスコア, 基本スコア) が 左 < 右 の場合にスワップ
                    left_key = (self.active_items[i]["score"], self.active_items[i]["base"])
                    right_key = (self.active_items[j]["score"], self.active_items[j]["base"])

                    if left_key < right_key:
                        self.active_items[i]["locked"] = False
                        self.active_items[j]["locked"] = False

                        self.active_items[i], self.active_items[j] = self.active_items[j], self.active_items[i]
                        step_state["total_swaps"] += 1
                        self.play_beep_async(self.active_items[i]["score"], duration=15)
                        processed += 1
                        break

            # 1パス完了時
            if step_state["curr_idx"] >= n - 1:
                step_state["curr_idx"] = 0
                step_state["pass"] += 1

                # ② 確定 ＆ 解除ロジック (タプル比較)
                for i in range(n):
                    min_k = max(0, i - 25)
                    max_k = min(n, i + 26)

                    key_i = (self.active_items[i]["score"], self.active_items[i]["base"])

                    has_error = False
                    for k in range(min_k, max_k):
                        key_k = (self.active_items[k]["score"], self.active_items[k]["base"])
                        if k < i and key_k < key_i:
                            has_error = True
                            break
                        if k > i and key_k > key_i:
                            has_error = True
                            break

                    if has_error:
                        self.active_items[i]["locked"] = False
                    else:
                        self.active_items[i]["locked"] = True

            # UI更新
            locked_count = sum(1 for item in self.active_items if item["locked"])
            self.session_info.set(f"パス: {step_state['pass']} | 総交換回数: {step_state['total_swaps']} | 確定: {locked_count}/{n}")

            self.draw_viewer(highlight_indices=active_indices)
            self.update_table()

            # ③ 完全整列チェック ((SSSAスコア, 基本スコア) が完全な降順になっているか)
            is_strictly_sorted = all(
                (self.active_items[k]["score"], self.active_items[k]["base"]) >=
                (self.active_items[k+1]["score"], self.active_items[k+1]["base"])
                for k in range(n-1)
            )

            if is_strictly_sorted:
                for item in self.active_items:
                    item["locked"] = True
                self.session_status.set("ソート完了！左→右スキャン実行中...")
                self.session_info.set(f"パス: {step_state['pass']} | 総交換回数: {step_state['total_swaps']} | 確定: {n}/{n}")
                
                self.play_completion_scan()
            else:
                delay = int(self.speed_scale.get() * 1000)
                self.root.after(delay, step)

        step()

    def play_completion_scan(self):
        """ソート完了後に左から右へ1つずつ順に選択・ハイライト表示しながら音を鳴らす"""
        n = len(self.active_items)
        if n == 0:
            self.is_sorting = False
            return

        def scan_step(scan_idx):
            if not self.root.winfo_exists():
                return

            if scan_idx < n:
                children = self.tree.get_children()
                if scan_idx < len(children):
                    self.tree.selection_set(children[scan_idx])
                    self.tree.see(children[scan_idx])

                self.draw_viewer(highlight_indices=[scan_idx])

                item_score = self.active_items[scan_idx]["score"]
                self.play_beep_async(item_score, duration=25)

                scan_delay = max(10, int(self.speed_scale.get() * 600))
                self.root.after(scan_delay, lambda: scan_step(scan_idx + 1))
            else:
                self.draw_viewer(highlight_indices=[])
                self.session_status.set("完了 (スキャンチェック終了)")
                self.is_sorting = False

        scan_step(0)

    def draw_viewer(self, highlight_indices=None):
        if highlight_indices is None:
            highlight_indices = []

        self.canvas.delete("all")
        c_w = self.canvas.winfo_width()
        c_h = self.canvas.winfo_height()

        if c_w <= 1 or c_h <= 1:
            c_w, c_h = 700, 400

        # 10区分ゾーン背景描画
        zone_w = c_w / 10
        for z_idx in range(10):
            zx0 = z_idx * zone_w
            zx1 = zx0 + zone_w
            bg_val = max(10, int(35 - z_idx * 2.5))
            bg_hex = f"#{bg_val:02x}{bg_val+5:02x}{bg_val+10:02x}"

            self.canvas.create_rectangle(zx0, 0, zx1, c_h, fill=bg_hex, outline="#222222")

            label_pct = f"{(10 - z_idx) * 10}%"
            self.canvas.create_text(
                zx0 + zone_w / 2, 20,
                text=label_pct, fill="#888888", font=("Helvetica", 8, "bold")
            )
            if z_idx > 0:
                self.canvas.create_line(zx0, 0, zx0, c_h, fill="#333333", dash=(2, 4))

        # 棒グラフ描画
        n = len(self.active_items)
        if n == 0:
            return

        pad_x = 10
        draw_area_w = c_w - (pad_x * 2)
        draw_area_h = c_h - 60

        bar_w = max(1, (draw_area_w / n) - 2)
        max_score = max([r["score"] for r in self.active_items], default=1.0)
        if max_score == 0:
            max_score = 1.0

        for i, res in enumerate(self.active_items):
            score = res["score"]
            pf = res["p_field"]
            is_locked = res["locked"]

            bar_h = max(4, (score / max_score) * draw_area_h)
            bx0 = pad_x + i * (draw_area_w / n)
            by0 = c_h - 20 - bar_h
            bx1 = bx0 + bar_w
            by1 = c_h - 20

            if i in highlight_indices:
                bar_color = "#FF1744"  # 選択・スキャン中（赤）
            elif is_locked:
                bar_color = "#555555"  # 確定（グレー）
            else:
                if pf > 80.0:
                    bar_color = "#00E676"
                elif pf > 60.0:
                    bar_color = "#00B0FF"
                elif pf > 40.0:
                    bar_color = "#FFD600"
                elif pf > 20.0:
                    bar_color = "#FF9100"
                else:
                    bar_color = "#FF5252"

            self.canvas.create_rectangle(bx0, by0, bx1, by1, fill=bar_color, outline="")

            if is_locked and bar_w > 3:
                self.canvas.create_rectangle(bx0, by0 - 3, bx1, by0, fill="#00E676", outline="")

    def update_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for rank, res in enumerate(self.active_items, 1):
            doc = res["doc"]
            status_str = "🔒確定" if res["locked"] else "可動"
            self.tree.insert("", "end", values=(
                f"#{rank}",
                doc["id"],
                doc["name"],
                f"{res['score']:.4f}",
                f"{res['base']:.4f}",
                f"{res['p_field']:.1f}%",
                status_str
            ))


if __name__ == "__main__":
    root = tk.Tk()
    app = SSSAGuiApp(root)
    root.mainloop()
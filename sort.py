import random
import time
import sys
import tkinter as tk
from tkinter import ttk, messagebox

# --- 音声再生機能の設定 ---
if sys.platform == "win32":
    import winsound
    import threading

    def _play_beep_async(freq, duration):
        try:
            winsound.Beep(freq, duration)
        except Exception:
            pass

    def play_sound(val, max_val):
        # 左（小さい値）を高い音にする処理
        ratio = val / max_val if max_val > 0 else 0
        inverse_ratio = 1.0 - ratio 
        freq = int(300 + (inverse_ratio * 1700))
        threading.Thread(target=_play_beep_async, args=(freq, 10), daemon=True).start()

else:
    def play_sound(val, max_val):
        print("\a", end="", flush=True)


# --- GUI アプリケーション ---
class SoundSortVisualizer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ソート可視化 (マージ / ティム / イントロ追加版)")
        self.geometry("820x480")
        self.resizable(False, False)

        self.is_sorting = False
        self.data = []
        self.sound_enabled = tk.BooleanVar(value=True)

        self.create_widgets()

    def create_widgets(self):
        # --- 操作ツールバー ---
        toolbar = ttk.Frame(self, padding=5)
        toolbar.pack(fill="x")

        # アルゴリズム選択 (追加アルゴリズムを含める)
        ttk.Label(toolbar, text="方式:").pack(side="left", padx=2)
        self.algo_combo = ttk.Combobox(
            toolbar, 
            values=["バブル", "選択", "挿入", "クイック", "マージ", "ティム", "イントロ"], 
            state="readonly", 
            width=10
        )
        self.algo_combo.current(3)
        self.algo_combo.pack(side="left", padx=2)

        # データ件数入力
        ttk.Label(toolbar, text="件数:").pack(side="left", padx=(10, 2))
        self.num_entry = ttk.Entry(toolbar, width=6)
        self.num_entry.insert(0, "60")
        self.num_entry.pack(side="left", padx=2)

        # 速度スライダー
        ttk.Label(toolbar, text="遅延:").pack(side="left", padx=(10, 2))
        self.speed_scale = ttk.Scale(toolbar, from_=1, to=100, value=15)
        self.speed_scale.pack(side="left", padx=2)

        # 音 ON/OFF
        ttk.Checkbutton(toolbar, text="音", variable=self.sound_enabled).pack(side="left", padx=(10, 2))

        # ボタン類
        self.btn_run = ttk.Button(toolbar, text="実行", command=self.start_sort, width=6)
        self.btn_run.pack(side="right", padx=5)

        self.btn_reset = ttk.Button(toolbar, text="シャッフル", command=self.reset_data, width=8)
        self.btn_reset.pack(side="right", padx=2)

        # --- 描画キャンバス ---
        self.canvas = tk.Canvas(self, bg="#111111", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=5, pady=5)

        self.after(100, self.reset_data)

    def get_num_elements(self):
        try:
            n = int(self.num_entry.get())
            if n <= 0: raise ValueError
            if n > 300:
                messagebox.showwarning("警告", "件数が多すぎます。300以下推奨です。")
                self.num_entry.delete(0, tk.END)
                self.num_entry.insert(0, "300")
                return 300
            return n
        except ValueError:
            messagebox.showerror("エラー", "件数は1以上の整数を入力してください。")
            return None

    def reset_data(self):
        if self.is_sorting: return
        n = self.get_num_elements()
        if n is None: return

        self.data = [random.randint(10, 100) for _ in range(n)]
        self.draw(active_idx=-1)

    def draw(self, active_idx=-1, pivot_idx=-1):
        self.canvas.delete("all")
        w = self.canvas.winfo_width() or 810
        h = self.canvas.winfo_height() or 420
        
        n = len(self.data)
        if n == 0: return

        bar_w = w / n
        max_val = max(self.data)

        for i, val in enumerate(self.data):
            x0 = i * bar_w
            y0 = h - (val / max_val * (h - 30)) 
            x1 = (i + 1) * bar_w - (1 if bar_w > 3 else 0)
            y1 = h

            if i == active_idx:
                color = "#ff4757" # 赤 (選択中)
            elif i == pivot_idx:
                color = "#ffa502" # オレンジ (ピボット/基準値)
            else:
                color = "#70a1ff" # 青

            self.canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="")

    def step(self, active_idx=-1, pivot_idx=-1):
        if not self.is_sorting: return

        self.draw(active_idx, pivot_idx)
        self.update() # フリーズ防止

        if self.sound_enabled.get() and active_idx >= 0 and active_idx < len(self.data):
            play_sound(self.data[active_idx], 100)

        delay = self.speed_scale.get() / 1000.0
        time.sleep(delay)

    def start_sort(self):
        if self.is_sorting: return
        
        n = self.get_num_elements()
        if n is None: return
        if len(self.data) != n:
            self.reset_data()

        self.is_sorting = True
        self.btn_run.config(state="disabled")
        self.btn_reset.config(state="disabled")
        self.num_entry.config(state="disabled")

        algo = self.algo_combo.get()
        
        # ソート切り替え
        if algo == "バブル":
            self.bubble_sort()
        elif algo == "選択":
            self.selection_sort()
        elif algo == "挿入":
            self.insertion_sort()
        elif algo == "クイック":
            self.quick_sort(0, len(self.data) - 1)
        elif algo == "マージ":
            self.merge_sort(0, len(self.data) - 1)
        elif algo == "ティム":
            self.timsort()
        elif algo == "イントロ":
            import math
            max_depth = 2 * int(math.log2(len(self.data)))
            self.introsort(0, len(self.data) - 1, max_depth)

        # 完了時スキャン
        if self.is_sorting:
            for i in range(len(self.data)):
                self.step(active_idx=i)
        
        self.draw(active_idx=-1)
        self.is_sorting = False
        self.btn_run.config(state="normal")
        self.btn_reset.config(state="normal")
        self.num_entry.config(state="normal")

    # -------------------------------------------------------------
    # 基本ソート群
    # -------------------------------------------------------------

    def bubble_sort(self):
        n = len(self.data)
        for i in range(n):
            for j in range(0, n - i - 1):
                if not self.is_sorting: return
                if self.data[j] > self.data[j + 1]:
                    self.data[j], self.data[j + 1] = self.data[j + 1], self.data[j]
                    self.step(active_idx=j+1)
                else:
                    self.step(active_idx=j)

    def selection_sort(self):
        n = len(self.data)
        for i in range(n):
            min_i = i
            for j in range(i + 1, n):
                if not self.is_sorting: return
                self.step(active_idx=j, pivot_idx=min_i)
                if self.data[j] < self.data[min_i]:
                    min_i = j
            self.data[i], self.data[min_i] = self.data[min_i], self.data[i]
            self.step(active_idx=i)

    def insertion_sort_range(self, left, right):
        """指定範囲を挿入ソート（ティム/イントロ用）"""
        for i in range(left + 1, right + 1):
            key = self.data[i]
            j = i - 1
            while j >= left and self.data[j] > key:
                if not self.is_sorting: return
                self.data[j + 1] = self.data[j]
                self.step(active_idx=j, pivot_idx=i)
                j -= 1
            self.data[j + 1] = key
            self.step(active_idx=j+1)

    def insertion_sort(self):
        self.insertion_sort_range(0, len(self.data) - 1)

    def quick_sort(self, low, high):
        if low < high:
            if not self.is_sorting: return
            p = self.partition(low, high)
            self.quick_sort(low, p - 1)
            self.quick_sort(p + 1, high)

    def partition(self, low, high):
        pivot = self.data[high]
        i = low - 1
        for j in range(low, high):
            if not self.is_sorting: return high
            self.step(active_idx=j, pivot_idx=high)
            if self.data[j] < pivot:
                i += 1
                self.data[i], self.data[j] = self.data[j], self.data[i]
                self.step(active_idx=i, pivot_idx=high)
        self.data[i + 1], self.data[high] = self.data[high], self.data[i + 1]
        self.step(active_idx=i+1, pivot_idx=high)
        return i + 1

    # -------------------------------------------------------------
    # 1. マージソート (Merge Sort)
    # -------------------------------------------------------------
    def merge_sort(self, l, r):
        if l < r:
            if not self.is_sorting: return
            m = (l + r) // 2
            self.merge_sort(l, m)
            self.merge_sort(m + 1, r)
            self.merge(l, m, r)

    def merge(self, l, m, r):
        left_sub = self.data[l:m + 1]
        right_sub = self.data[m + 1:r + 1]

        i = j = 0
        k = l

        while i < len(left_sub) and j < len(right_sub):
            if not self.is_sorting: return
            self.step(active_idx=k, pivot_idx=r)
            if left_sub[i] <= right_sub[j]:
                self.data[k] = left_sub[i]
                i += 1
            else:
                self.data[k] = right_sub[j]
                j += 1
            k += 1

        while i < len(left_sub):
            if not self.is_sorting: return
            self.data[k] = left_sub[i]
            self.step(active_idx=k)
            i += 1
            k += 1

        while j < len(right_sub):
            if not self.is_sorting: return
            self.data[k] = right_sub[j]
            self.step(active_idx=k)
            j += 1
            k += 1

    # -------------------------------------------------------------
    # 2. ティムソート (Timsort)
    # -------------------------------------------------------------
    def timsort(self):
        n = len(self.data)
        RUN = 16  # 可視化用に小さめのブロック幅に設定

        # 1. 小さなブロックごとに挿入ソート
        for start in range(0, n, RUN):
            if not self.is_sorting: return
            end = min(start + RUN - 1, n - 1)
            self.insertion_sort_range(start, end)

        # 2. ブロック同士をマージ
        size = RUN
        while size < n:
            for left in range(0, n, 2 * size):
                if not self.is_sorting: return
                mid = min(n - 1, left + size - 1)
                right = min((left + 2 * size - 1), (n - 1))
                if mid < right:
                    self.merge(left, mid, right)
            size *= 2

    # -------------------------------------------------------------
    # 3. イントロソート (Introsort)
    # -------------------------------------------------------------
    def introsort(self, low, high, depth_limit):
        n = high - low + 1
        if n < 16:
            # 範囲が小さくなったら挿入ソートへ切り替え
            self.insertion_sort_range(low, high)
        elif depth_limit == 0:
            # 再帰が深くなりすぎたらヒープソートへ切り替え
            self.heap_sort_range(low, high)
        else:
            # 通常はクイックソートを実行
            if not self.is_sorting: return
            p = self.partition(low, high)
            self.introsort(low, p - 1, depth_limit - 1)
            self.introsort(p + 1, high, depth_limit - 1)

    def heap_sort_range(self, low, high):
        """範囲指定ヒープソート（イントロソートのバックアップ用）"""
        n = high - low + 1

        def heapify(n, i, offset):
            largest = i
            l = 2 * i + 1
            r = 2 * i + 2

            if l < n and self.data[offset + l] > self.data[offset + largest]:
                largest = l
            if r < n and self.data[offset + r] > self.data[offset + largest]:
                largest = r

            if largest != i:
                self.data[offset + i], self.data[offset + largest] = self.data[offset + largest], self.data[offset + i]
                self.step(active_idx=offset + largest)
                heapify(n, largest, offset)

        # ヒープ構築
        for i in range(n // 2 - 1, -1, -1):
            if not self.is_sorting: return
            heapify(n, i, low)

        # 要素を1つずつ取り出し
        for i in range(n - 1, 0, -1):
            if not self.is_sorting: return
            self.data[low], self.data[low + i] = self.data[low + i], self.data[low]
            self.step(active_idx=low + i)
            heapify(i, 0, low)


if __name__ == "__main__":
    app = SoundSortVisualizer()
    def on_closing():
        app.is_sorting = False
        app.destroy()
    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()
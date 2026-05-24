import hashlib
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import wave
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

SECRET = "Степанчук Павло"
KEY_HINT = "наприклад: lab4key"

BG = "#f0f0f0"
BG_PANEL = "#ffffff"
FG = "#1a1a1a"
FG_DIM = "#5a5a5a"
FG_HINT = "#9a9a9a"
BORDER = "#c8c8c8"
SELECT_BG = "#cce4f7"
BTN_BG = "#e1e1e1"
BTN_ACTIVE = "#d0d0d0"
BTN_ON = "#0078d4"
FONT_UI = ("Times New Roman", 11)
FONT_TITLE = ("Times New Roman", 12, "bold")
PLOT_POINTS = 4000
MAX_PRNG_SAMPLES = 800_000
PRNG_ERR = "Для PRNG файл занадто довгий. Скоротіть WAV або оберіть LSB."


def enable_dpi():
    if sys.platform != "win32":
        return
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def downloads():
    p = os.path.join(os.environ.get("USERPROFILE", ""), "Downloads")
    return p if os.path.isdir(p) else os.path.expanduser("~")


def stamp():
    return datetime.now().strftime("%H%M%S_%d%m")


def temp_path(suffix):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path


def load_matplotlib():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "matplotlib"])
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    if sys.platform == "win32":
        plt.rcParams["font.family"] = "sans-serif"
        plt.rcParams["font.sans-serif"] = ["Segoe UI", "Arial", "DejaVu Sans"]
    plt.rcParams.update({"font.size": 9, "axes.unicode_minus": False})
    return plt


def read_wav_bytes(path):
    with wave.open(path, "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError("Потрібен WAV 16-біт.")
        params, raw = w.getparams(), bytearray(w.readframes(w.getnframes()))
    return params, raw


def write_wav_bytes(path, params, raw):
    with wave.open(path, "wb") as w:
        w.setparams(params)
        w.writeframes(raw)


def preview_samples(path, max_pts):
    with wave.open(path, "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError("Потрібен WAV 16-біт.")
        sr, n = w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if n <= max_pts:
        return sr, 1, [struct.unpack_from("<h", raw, i * 2)[0] for i in range(n)]
    step = max(1, n // max_pts)
    out = []
    for i in range(0, n, step):
        out.append(struct.unpack_from("<h", raw, i * 2)[0])
        if len(out) >= max_pts:
            break
    return sr, step, out


def message_bits(message):
    bits = []
    for b in (message + "\0").encode("utf-8"):
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1)
    return bits


def bits_to_message(raw, positions):
    data, val, cnt = bytearray(), 0, 0
    for pos in positions:
        val = (val << 1) | (raw[pos * 2] & 1)
        cnt += 1
        if cnt == 8:
            if val == 0:
                break
            data.append(val)
            val, cnt = 0, 0
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Не вдалося вилучити текст. Перевірте ключ і метод PRNG.")


def prng_rng(key, length):
    if length > MAX_PRNG_SAMPLES:
        raise ValueError(PRNG_ERR)
    seed = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:16], 16)
    return random.Random(seed)


def prng_order(n, key):
    if n > MAX_PRNG_SAMPLES:
        raise ValueError(PRNG_ERR)
    pos = list(range(n))
    prng_rng(key, n).shuffle(pos)
    return pos


def embed_bits(raw, positions, bits):
    for p, b in zip(positions, bits):
        raw[p * 2] = (raw[p * 2] & 0xFE) | int(b)


def embed_message(input_wav, output_wav, message):
    bits = message_bits(message)
    params, raw = read_wav_bytes(input_wav)
    if len(bits) > len(raw) // 2:
        raise ValueError("Повідомлення занадто довге для цього аудіо.")
    embed_bits(raw, range(len(bits)), bits)
    write_wav_bytes(output_wav, params, raw)


def extract_message(stego_wav):
    _, raw = read_wav_bytes(stego_wav)
    return bits_to_message(raw, range(len(raw) // 2))


def embed_message_prng(input_wav, output_wav, message, key):
    if not key.strip():
        raise ValueError("Введіть ключ для LSB + PRNG.")
    bits = message_bits(message)
    params, raw = read_wav_bytes(input_wav)
    n = len(raw) // 2
    if len(bits) > n:
        raise ValueError("Повідомлення занадто довге для цього аудіо.")
    embed_bits(raw, prng_order(n, key)[: len(bits)], bits)
    write_wav_bytes(output_wav, params, raw)


def extract_message_prng(stego_wav, key):
    if not key.strip():
        raise ValueError("Введіть ключ для LSB + PRNG.")
    _, raw = read_wav_bytes(stego_wav)
    n = len(raw) // 2
    return bits_to_message(raw, prng_order(n, key))


def plot_waveforms(wav1, wav2, out_png):
    plt = load_matplotlib()
    fig = plt.figure(figsize=(10, 5.5))
    fig.patch.set_facecolor(BG)
    for i, (path, color, style) in enumerate(
        ((wav1, "#3c74ed", "-"), (wav2, "#f05211", "--")), start=1
    ):
        sr, step, samples = preview_samples(path, PLOT_POINTS)
        t = [j * step / sr for j in range(len(samples))]
        ax = fig.add_subplot(2, 1, i)
        ax.plot(t, samples, color=color, linewidth=0.7, linestyle=style)
        ax.set_title(os.path.basename(path), fontsize=10, pad=8)
        ax.set_ylabel("Амплітуда", fontsize=10)
        if i == 2:
            ax.set_xlabel("Час (с)", fontsize=10)
        ax.set_facecolor(BG_PANEL)
        ax.tick_params(colors=FG, labelsize=9)
        ax.title.set_color(FG)
        ax.xaxis.label.set_color(FG_DIM)
        ax.yaxis.label.set_color(FG_DIM)
    fig.tight_layout(pad=1.0, h_pad=1.2)
    fig.savefig(out_png, dpi=110, facecolor=BG, bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)


class App:
    def _entry(self, parent, **kw):
        return tk.Entry(
            parent, bg=BG_PANEL, fg=FG, insertbackground=FG, font=FONT_UI,
            relief=tk.SOLID, bd=1, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=BTN_ON, **kw,
        )

    def _btn(self, parent, text, cmd):
        return tk.Button(
            parent, text=text, command=cmd, bg=BTN_BG, fg=FG, font=FONT_UI,
            activebackground=BTN_ACTIVE, relief=tk.GROOVE, padx=10, pady=5,
        )

    def __init__(self):
        enable_dpi()
        self.orig_path = self.stego_path = self.plot_png_path = ""
        self.use_prng = self.busy = False
        self._plot_photo = self._resize_job = None

        self.root = tk.Tk()
        self.root.title("Лабораторна 4 — LSB аудіо")
        self.root.geometry("1000x700")
        self.root.minsize(800, 650)
        self.root.configure(bg=BG)
        self.root.option_add("*Font", FONT_UI)

        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=20, pady=(14, 6))
        tk.Label(top, text="Стеганографія 4", font=FONT_TITLE, bg=BG, fg=FG).pack(anchor="w")

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=8)

        left = tk.LabelFrame(
            body, text=" Налаштування ", bg=BG_PANEL, fg=FG, font=FONT_UI,
            padx=14, pady=12, highlightbackground=BORDER, highlightthickness=1,
        )
        left.pack(side=tk.LEFT, fill="y", padx=(0, 10))

        tk.Label(left, text="Метод", bg=BG_PANEL, fg=FG_DIM, font=FONT_UI).pack(anchor="w")
        sw = tk.Frame(left, bg=BORDER, padx=1, pady=1)
        sw.pack(fill="x", pady=(4, 10))
        inner = tk.Frame(sw, bg=BG_PANEL)
        inner.pack(fill="x")
        self.btn_lsb = tk.Button(
            inner, text="LSB", command=lambda: self.set_method(False),
            bg=BTN_ON, fg="#ffffff", font=FONT_UI, relief=tk.FLAT, padx=16, pady=6,
        )
        self.btn_lsb.pack(side=tk.LEFT, fill="x", expand=True)
        self.btn_prng = tk.Button(
            inner, text="PRNG", command=lambda: self.set_method(True),
            bg=BG_PANEL, fg=FG, font=FONT_UI, relief=tk.FLAT, padx=16, pady=6,
        )
        self.btn_prng.pack(side=tk.LEFT, fill="x", expand=True)

        for label, attr, extra in (
            ("Повідомлення", "msg", {"insert": SECRET}),
            ("Ключ (лише для PRNG)", "key", {"insert": KEY_HINT, "hint": True}),
        ):
            tk.Label(left, text=label, bg=BG_PANEL, fg=FG_DIM, font=FONT_UI).pack(anchor="w")
            e = self._entry(left, width=32)
            if "insert" in extra:
                e.insert(0, extra["insert"])
            if extra.get("hint"):
                e.config(fg=FG_HINT)
                e.bind("<FocusIn>", self.key_focus_in)
                e.bind("<FocusOut>", self.key_focus_out)
            e.pack(fill="x", ipady=4, pady=(2, 10))
            setattr(self, attr, e)

        tk.Label(left, text="WAV-файл", bg=BG_PANEL, fg=FG_DIM, font=FONT_UI).pack(anchor="w")
        row = tk.Frame(left, bg=BG_PANEL)
        row.pack(fill="x", pady=(2, 10))
        self.wav_path = self._entry(row)
        self.wav_path.pack(side=tk.LEFT, fill="x", expand=True, ipady=4)
        self._btn(row, "...", self.pick_wav).pack(side=tk.LEFT, padx=(6, 0))

        btns = tk.Frame(left, bg=BG_PANEL)
        btns.pack(fill="x", pady=4)
        self._busy_widgets = []
        self.btn_embed = self._btn(btns, "Приховати", self.do_embed)
        self.btn_embed.pack(fill="x", pady=3)
        self._busy_widgets.append(self.btn_embed)

        tk.Label(btns, text="Стего WAV", bg=BG_PANEL, fg=FG_DIM, font=FONT_UI).pack(anchor="w", pady=(4, 0))
        stego_row = tk.Frame(btns, bg=BG_PANEL)
        stego_row.pack(fill="x", pady=(2, 8))
        self.stego_wav = self._entry(stego_row)
        self.stego_wav.pack(side=tk.LEFT, fill="x", expand=True, ipady=4)
        self._btn(stego_row, "...", self.pick_stego).pack(side=tk.LEFT, padx=(6, 0))

        for text, cmd in (
            ("Вилучити", self.do_extract),
            ("Порівняти графіки", self.do_plot),
            ("Зберегти звук…", self.save_audio),
            ("Зберегти графік…", self.save_plot),
        ):
            b = self._btn(btns, text, cmd)
            b.pack(fill="x", pady=3)
            self._busy_widgets.append(b)

        right = tk.LabelFrame(
            body, text=" Результат ", bg=BG_PANEL, fg=FG, font=FONT_UI,
            padx=14, pady=12, highlightbackground=BORDER, highlightthickness=1,
        )
        right.pack(side=tk.LEFT, fill="both", expand=True)

        self.log = scrolledtext.ScrolledText(
            right, height=5, wrap=tk.WORD, bg=BG_PANEL, fg=FG, font=FONT_UI,
            insertbackground=FG, selectbackground=SELECT_BG, relief=tk.SOLID, bd=1,
        )
        self.log.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        self.plot_box = tk.Frame(right, bg=BG_PANEL)
        self.plot_box.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.plot_label = tk.Label(
            self.plot_box, text="Графік з’явиться після «Порівняти графіки»",
            bg=BG_PANEL, fg=FG_DIM, font=FONT_UI, anchor="center",
        )
        self.plot_label.pack(fill=tk.BOTH, expand=True)
        self.plot_box.bind("<Configure>", self._on_plot_resize)
        self._busy_widgets.extend(
            [self.btn_lsb, self.btn_prng, self.msg, self.key, self.wav_path, self.stego_wav]
        )

    def set_method(self, prng):
        self.use_prng = prng
        self.btn_lsb.config(bg=BG_PANEL if prng else BTN_ON, fg=FG if prng else "#ffffff")
        self.btn_prng.config(bg=BTN_ON if prng else BG_PANEL, fg="#ffffff" if prng else FG)

    def key_focus_in(self, event):
        if self.key.get() == KEY_HINT:
            self.key.delete(0, tk.END)
            self.key.config(fg=FG)

    def key_focus_out(self, event):
        if not self.key.get().strip():
            self.key.insert(0, KEY_HINT)
            self.key.config(fg=FG_HINT)

    def get_key(self):
        k = self.key.get().strip()
        return "" if k == KEY_HINT or not k else k

    def log_line(self, text):
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)

    def _plot_size(self):
        self.root.update_idletasks()
        w = max(self.plot_box.winfo_width() - 12, 960)
        h = max(self.plot_box.winfo_height() - 12, 540)
        return w, h

    def _photo_fit(self, path, max_w, max_h):
        try:
            from PIL import Image, ImageTk
            img = Image.open(path)
            img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
        except ImportError:
            photo = tk.PhotoImage(file=path)
            r = max((photo.width() + max_w - 1) // max_w, (photo.height() + max_h - 1) // max_h, 1)
            return photo.subsample(r, r) if r > 1 else photo

    def _display_plot(self):
        if not self.plot_png_path or not os.path.isfile(self.plot_png_path):
            return
        try:
            self._plot_photo = self._photo_fit(self.plot_png_path, *self._plot_size())
            self.plot_label.config(image=self._plot_photo, text="", bg=BG_PANEL)
        except (tk.TclError, OSError):
            self.log_line("Не вдалося показати графік.")

    def _on_plot_resize(self, event):
        if event.widget != self.plot_box or not self.plot_png_path:
            return
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(120, self._resize_plot)

    def _resize_plot(self):
        self._resize_job = None
        self._display_plot()

    def _remove_temp(self, path):
        if path and os.path.isfile(path) and os.path.dirname(path) == tempfile.gettempdir():
            try:
                os.remove(path)
            except OSError:
                pass

    def _save_as(self, src, title, initial, types, ok_msg, need_msg):
        if not src or not os.path.isfile(src):
            messagebox.showinfo("", need_msg)
            return
        path = filedialog.asksaveasfilename(
            title=title, initialdir=downloads(), initialfile=initial,
            defaultextension=types[0][1], filetypes=types + [("Усі", "*.*")],
        )
        if path:
            shutil.copy2(src, path)
            self.log_line(ok_msg + path)

    def save_audio(self):
        self._save_as(
            self.get_stego(need=False), "Зберегти звук", "stego_audio_" + stamp() + ".wav",
            [("WAV", "*.wav")], "Звук збережено: ",
            "Спочатку натисніть «Приховати».",
        )

    def save_plot(self):
        self._save_as(
            self.plot_png_path, "Зберегти графік", "waves_" + stamp() + ".png",
            [("PNG", "*.png")], "Графік збережено: ",
            "Спочатку натисніть «Порівняти графіки».",
        )

    def set_busy(self, on):
        self.busy = on
        state = tk.DISABLED if on else tk.NORMAL
        for w in self._busy_widgets:
            w.config(state=state)

    def run_bg(self, job):
        if self.busy:
            return
        self.set_busy(True)
        self.log_line("Обробка...")

        def work():
            err, result = None, None
            try:
                result = job()
            except Exception as e:
                err = e
            self.root.after(0, lambda: self._job_done(err, result))

        threading.Thread(target=work, daemon=True).start()

    def _job_done(self, err, result):
        self.set_busy(False)
        if err:
            messagebox.showerror("", str(err))
            self.log_line(str(err))
            return
        if not result:
            return
        if result.get("stego"):
            self._remove_temp(self.stego_path)
            self.orig_path = result["orig"]
            self.set_stego_path(result["stego"])
        for line in result.get("lines", []):
            self.log_line(line)
        if result.get("png"):
            self._remove_temp(self.plot_png_path)
            self.plot_png_path = result["png"]
            self._display_plot()

    def set_stego_path(self, path):
        self.stego_path = path
        self.stego_wav.delete(0, tk.END)
        if path:
            self.stego_wav.insert(0, path)

    def pick_wav(self):
        path = filedialog.askopenfilename(
            initialdir=downloads(), filetypes=[("WAV", "*.wav"), ("Усі", "*.*")],
        )
        if path:
            self.wav_path.delete(0, tk.END)
            self.wav_path.insert(0, path)
            self.orig_path = path

    def pick_stego(self):
        path = filedialog.askopenfilename(
            initialdir=downloads(), filetypes=[("WAV", "*.wav"), ("Усі", "*.*")],
        )
        if path:
            self.set_stego_path(path)

    def get_stego(self, need=True):
        path = self.stego_wav.get().strip()
        if not path:
            if need:
                raise ValueError("Спочатку натисніть «Приховати».")
            return ""
        if not os.path.isfile(path):
            raise ValueError("Стего-файл не знайдено.")
        return path

    def get_wav(self):
        path = self.wav_path.get().strip()
        if not path:
            raise ValueError("Оберіть WAV-файл.")
        if not os.path.isfile(path):
            raise ValueError("Файл не знайдено.")
        return path

    def _action(self, fn):
        if self.busy:
            return
        try:
            self.run_bg(fn)
        except Exception as e:
            messagebox.showerror("", str(e))
            self.log_line(str(e))

    def do_embed(self):
        use_prng, key = self.use_prng, self.get_key()

        def job():
            text = self.msg.get().strip()
            if not text:
                raise ValueError("Введіть повідомлення.")
            src = self.get_wav()
            out = temp_path(".wav")
            if use_prng:
                embed_message_prng(src, out, text, key)
            else:
                embed_message(src, out, text)
            return {"lines": ["Приховано.", "«Зберегти звук…» — зберегти WAV."], "stego": out, "orig": src}

        self._action(job)

    def do_extract(self):
        try:
            path = self.get_stego()
        except ValueError as e:
            messagebox.showerror("", str(e))
            return
        use_prng, key = self.use_prng, self.get_key()

        def job():
            if use_prng:
                text = extract_message_prng(path, key)
            else:
                text = extract_message(path)
            return {"lines": ["Вилучено:", text or "(порожньо)"]}

        self._action(job)

    def do_plot(self):
        try:
            stego = self.get_stego()
            orig = self.orig_path or self.get_wav()
        except ValueError as e:
            messagebox.showerror("", str(e))
            return

        def job():
            png = temp_path(".png")
            plot_waveforms(orig, stego, png)
            return {"lines": ["Графік готовий."], "png": png}

        self._action(job)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()

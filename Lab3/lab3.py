import os
import re
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

Z0 = "\u200b"
Z1 = "\u200c"
STOP = "\u200d"
ALPHA = re.compile(r"[a-zA-Zа-яА-ЯіїєґІЇЄҐ]")

SECRET = "Степанчук Павло"
CARRIER = (
    "Куріння шкодить здоров'ю людини. "
    "Воно руйнує легень, серце та судини. "
    "Лікарі кажуть, що тютюн вбиває мільйони щороку. "
    "Краще взагалі не починати палити."
)

EN_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
EN_LOWER = EN_UPPER.lower()
UA_UPPER = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"
UA_LOWER = UA_UPPER.lower()
ALPHABETS = (EN_UPPER, EN_LOWER, UA_UPPER, UA_LOWER)

BG = "#1e1e1e"
BG_PANEL = "#252526"
BG_INPUT = "#3c3c3c"
FG = "#cccccc"
FG_DIM = "#858585"
BORDER = "#3e3e42"
SELECT_BG = "#264f78"
BTN_BG = "#3c3c3c"
BTN_ACTIVE = "#505050"
ERR_CARRIER = "Текст-носія недостатній. Збільште носій або скоротіть секретне повідомлення."


def downloads():
    p = os.path.join(os.environ.get("USERPROFILE", ""), "Downloads")
    if os.path.isdir(p):
        return p
    return os.path.expanduser("~")


def to_bits(text):
    s = ""
    for ch in text:
        s += format(ord(ch), "016b")
    return s


def from_bits(bits):
    out = ""
    for i in range(0, len(bits), 16):
        part = bits[i:i + 16]
        if len(part) == 16:
            out += chr(int(part, 2))
    return out


def pack(text):
    body = to_bits(text)
    head = format(len(body), "032b")
    return head + body


def unpack(bits):
    if len(bits) < 32:
        return ""
    ln = int(bits[:32], 2)
    return from_bits(bits[32:32 + ln])


def shift_char(ch, step):
    for abc in ALPHABETS:
        if ch in abc:
            return abc[(abc.index(ch) + step) % len(abc)]
    return ch


def shift_text(text, step):
    return "".join(shift_char(ch, step) for ch in text)


def check_carrier(cover, msg, mode):
    if mode == "zero":
        return
    bits_len = len(pack(msg))
    text = cover.strip()
    if mode == "case":
        if sum(1 for ch in text if ALPHA.match(ch)) < bits_len:
            raise ValueError(ERR_CARRIER)
    elif mode == "spaces":
        if len(text.split()) - 1 < bits_len:
            raise ValueError(ERR_CARRIER)
    elif sum(1 for ch in text if ch != " ") < bits_len:
        raise ValueError(ERR_CARRIER)


def embed_zero(base, msg):
    bits = pack(msg)
    hidden = ""
    for b in bits:
        hidden += Z0 if b == "0" else Z1
    hidden += STOP
    return base + hidden


def read_zero(text):
    bits = ""
    for ch in text:
        if ch == Z0:
            bits += "0"
        elif ch == Z1:
            bits += "1"
        elif ch == STOP:
            break
    return unpack(bits)


def embed_case(base, msg):
    bits = pack(msg)
    pos = 0
    out = ""
    for ch in base:
        if ALPHA.match(ch) and pos < len(bits):
            out += ch.upper() if bits[pos] == "1" else ch.lower()
            pos += 1
        else:
            out += ch
    return out


def read_case(text):
    bits = ""
    for ch in text:
        if ALPHA.match(ch):
            bits += "1" if ch.isupper() else "0"
    return unpack(bits)


def embed_spaces(base, msg):
    bits = pack(msg)
    words = base.strip().split()
    out = words[0]
    for i in range(len(bits)):
        out += "  " if bits[i] == "1" else " "
        out += words[i + 1]
    for i in range(len(bits) + 1, len(words)):
        out += " " + words[i]
    return out


def read_spaces(text):
    gaps = re.findall(r" +", text)
    bits = ""
    for g in gaps:
        bits += "1" if len(g) > 1 else "0"
    return unpack(bits)


def embed_color(base, msg):
    bits = pack(msg)
    pos = 0
    out = ""
    for ch in base:
        if ch != " " and pos < len(bits):
            col = "#0A0A0A" if bits[pos] == "1" else "#000000"
            out += '<span style="color:' + col + '">' + ch + "</span>"
            pos += 1
        else:
            out += ch
    return out


def read_color(html):
    bits = ""
    for m in re.finditer(r'<span style="color:\s*([^"]+)">', html, re.I):
        col = m.group(1).replace(" ", "").lower()
        if col == "#000000":
            bits += "0"
        else:
            bits += "1"
    return unpack(bits)


def setup_edit(widget, readonly=False):
    menu = tk.Menu(
        widget,
        tearoff=0,
        bg=BG_PANEL,
        fg=FG,
        activebackground=SELECT_BG,
        activeforeground="#ffffff",
    )

    def get_sel():
        if isinstance(widget, tk.Text):
            try:
                return widget.get(tk.SEL_FIRST, tk.SEL_LAST)
            except tk.TclError:
                return ""
        if widget.selection_present():
            return widget.selection_get()
        return ""

    def do_copy():
        s = get_sel()
        if s:
            widget.clipboard_clear()
            widget.clipboard_append(s)

    def do_cut():
        if readonly:
            return
        s = get_sel()
        if not s:
            return
        widget.clipboard_clear()
        widget.clipboard_append(s)
        widget.delete(tk.SEL_FIRST, tk.SEL_LAST)

    def do_paste():
        if readonly:
            return
        try:
            s = widget.clipboard_get()
        except tk.TclError:
            return
        if isinstance(widget, tk.Text):
            try:
                widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
            except tk.TclError:
                pass
            widget.insert(tk.INSERT, s)
        else:
            if widget.selection_present():
                widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
            widget.insert(tk.INSERT, s)

    def do_select_all():
        if isinstance(widget, tk.Text):
            widget.tag_add("sel", "1.0", "end-1c")
            widget.mark_set("insert", "end-1c")
            widget.see("insert")
        else:
            widget.select_range(0, tk.END)
            widget.icursor(tk.END)

    def show_menu(event):
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    menu.add_command(label="Копіювати", command=do_copy)
    if not readonly:
        menu.add_command(label="Вставити", command=do_paste)
        menu.add_command(label="Вирізати", command=do_cut)
    menu.add_separator()
    menu.add_command(label="Виділити все", command=do_select_all)

    def bind_ctrl(keys, func):
        for key in keys:
            widget.bind("<Control-" + key + ">", lambda e, f=func: (f(), "break")[1])

    bind_ctrl(("c", "C"), do_copy)
    widget.bind("<Control-Insert>", lambda e: (do_copy(), "break")[1])
    if not readonly:
        bind_ctrl(("v", "V"), do_paste)
        bind_ctrl(("x", "X"), do_cut)
        widget.bind("<Shift-Insert>", lambda e: (do_paste(), "break")[1])
    bind_ctrl(("a", "A"), do_select_all)

    widget.bind("<Button-3>", show_menu)


class App:
    def _text(self, parent, **kw):
        opts = dict(
            bg=BG_INPUT,
            fg=FG,
            insertbackground=FG,
            selectbackground=SELECT_BG,
            selectforeground="#ffffff",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
        )
        opts.update(kw)
        return tk.Text(parent, **opts)

    def _label(self, parent, text, **kw):
        opts = dict(bg=BG_PANEL, fg=FG_DIM, anchor="w")
        opts.update(kw)
        return tk.Label(parent, text=text, **opts)

    def _button(self, parent, text, command):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=BTN_BG,
            fg=FG,
            activebackground=BTN_ACTIVE,
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=4,
        )

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Стеганографія")
        self.root.geometry("900x700")
        self.root.configure(bg=BG)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "TCombobox",
            fieldbackground=BG_INPUT,
            background=BG_PANEL,
            foreground=FG,
            arrowcolor=FG,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", BG_INPUT)],
            foreground=[("readonly", FG)],
        )

        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=20, pady=(16, 6))
        tk.Label(
            top,
            text="Лабораторна робота 3",
            font=("Segoe UI", 18, "bold"),
            bg=BG,
            fg=FG,
        ).pack(anchor="w")

        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=20, pady=10)

        left = tk.LabelFrame(
            main,
            text="Вхідні дані",
            padx=12,
            pady=12,
            bg=BG_PANEL,
            fg=FG,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
        )
        left.pack(side=tk.LEFT, fill="y", padx=(0, 10))

        self._label(left, "Метод приховування").pack(anchor="w")
        self.method = ttk.Combobox(left, state="readonly", width=28)
        self.method["values"] = (
            "Символи нульової ширини — ZWC",
            "Зміна регістру — Case",
            "Маніпуляція пробілами — Spaces",
            "Колір шрифту — Color",
        )
        self.method.current(0)
        self.method.pack(fill="x", pady=(0, 10))

        self._label(left, "Секретне повідомлення").pack(anchor="w")
        self.secret = tk.Entry(
            left,
            width=30,
            bg=BG_INPUT,
            fg=FG,
            insertbackground=FG,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        self.secret.insert(0, SECRET)
        self.secret.pack(fill="x", pady=(0, 10))

        self._label(left, "Текст-носій").pack(anchor="w")
        self.carrier = self._text(left, width=36, height=12, wrap=tk.WORD)
        self.carrier.insert("1.0", CARRIER)
        self.carrier.pack(pady=(0, 10))

        row = tk.Frame(left, bg=BG_PANEL)
        row.pack(fill="x")
        self.cipher_on = tk.BooleanVar(value=False)
        tk.Checkbutton(
            row,
            text="Шифр Цезаря",
            variable=self.cipher_on,
            bg=BG_PANEL,
            fg=FG,
            selectcolor=BG_INPUT,
            activebackground=BG_PANEL,
            activeforeground=FG,
        ).pack(side=tk.LEFT)
        self._label(row, "Зсув", fg=FG_DIM).pack(side=tk.LEFT, padx=(10, 0))
        self.shift = tk.Entry(
            row,
            width=5,
            bg=BG_INPUT,
            fg=FG,
            insertbackground=FG,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        self.shift.insert(0, "3")
        self.shift.pack(side=tk.LEFT, padx=4)

        btns = tk.Frame(left, bg=BG_PANEL)
        btns.pack(fill="x", pady=8)
        self._button(btns, "Приховати", self.encode).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        self._button(btns, "Вилучити", self.decode).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        self._button(btns, "Зберегти", self.save_file).grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        self._button(btns, "Відкрити", self.open_file).grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)

        right = tk.LabelFrame(
            main,
            text="Результати роботи",
            padx=12,
            pady=12,
            bg=BG_PANEL,
            fg=FG,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
        )
        right.pack(side=tk.LEFT, fill="both", expand=True)

        self._label(right, "Бінарний вигляд").pack(anchor="w")
        self.bin_view = scrolledtext.ScrolledText(
            right,
            height=8,
            wrap=tk.WORD,
            bg=BG_INPUT,
            fg=FG,
            insertbackground=FG,
            selectbackground=SELECT_BG,
            selectforeground="#ffffff",
        )
        self.bin_view.pack(fill="x", pady=(0, 8))

        self._label(right, "Стеготекст").pack(anchor="w")
        self.stego_view = scrolledtext.ScrolledText(
            right,
            height=10,
            wrap=tk.WORD,
            bg=BG_INPUT,
            fg=FG,
            insertbackground=FG,
            selectbackground=SELECT_BG,
            selectforeground="#ffffff",
        )
        self.stego_view.pack(fill="both", expand=True, pady=(0, 8))

        self._label(right, "Вилучене повідомлення").pack(anchor="w")
        self.dec_view = scrolledtext.ScrolledText(
            right,
            height=6,
            wrap=tk.WORD,
            bg=BG_INPUT,
            fg=FG,
            insertbackground=FG,
            selectbackground=SELECT_BG,
            selectforeground="#ffffff",
        )
        self.dec_view.pack(fill="x")

        setup_edit(self.secret)
        setup_edit(self.carrier)
        setup_edit(self.bin_view, readonly=True)
        setup_edit(self.stego_view)
        setup_edit(self.dec_view, readonly=True)

    def method_key(self):
        i = self.method.current()
        if i == 1:
            return "case"
        if i == 2:
            return "spaces"
        if i == 3:
            return "color"
        return "zero"

    def get_stego(self):
        return self.stego_view.get("1.0", "end-1c")

    def protect(self, text):
        if self.cipher_on.get():
            return shift_text(text, int(self.shift.get() or 3))
        return text

    def restore(self, text):
        if self.cipher_on.get():
            return shift_text(text, -int(self.shift.get() or 3))
        return text

    def encode(self):
        try:
            m = self.method_key()
            msg = self.protect(self.secret.get()).strip()
            if not msg:
                raise ValueError("Введіть секретне повідомлення.")
            cover = self.carrier.get("1.0", tk.END)
            check_carrier(cover, msg, m)

            if m == "zero":
                result = embed_zero(cover, msg)
            elif m == "case":
                result = embed_case(cover, msg)
            elif m == "spaces":
                result = embed_spaces(cover, msg)
            else:
                result = embed_color(cover, msg)

            self.bin_view.delete("1.0", tk.END)
            self.bin_view.insert(tk.END, pack(msg))

            self.stego_view.delete("1.0", tk.END)
            self.stego_view.insert(tk.END, result)

            self.dec_view.delete("1.0", tk.END)
        except Exception as e:
            self.dec_view.delete("1.0", tk.END)
            self.dec_view.insert(tk.END, str(e))
            messagebox.showerror("", str(e))

    def decode(self):
        try:
            data = self.get_stego()
            if not data.strip():
                messagebox.showwarning("", "Немає стеготексту. Спочатку «Приховати» або «Відкрити» файл.")
                return

            m = self.method_key()

            if m == "zero":
                msg = read_zero(data)
            elif m == "case":
                msg = read_case(data)
            elif m == "spaces":
                msg = read_spaces(data)
            else:
                msg = read_color(data)

            msg = self.restore(msg)
            self.dec_view.delete("1.0", tk.END)
            if msg:
                self.dec_view.insert(tk.END, msg)
            else:
                self.dec_view.insert(tk.END, "Не знайдено")
        except Exception:
            self.dec_view.delete("1.0", tk.END)
            self.dec_view.insert(tk.END, "Помилка")

    def save_file(self):
        stego = self.get_stego()
        if not stego.strip():
            messagebox.showwarning("", "Спочатку натисніть «Приховати»")
            return
        ext = "html" if self.method_key() == "color" else "txt"
        now = datetime.now()
        name = "stego" + now.strftime("%H%M%S_%d%m") + "." + ext
        path = os.path.join(downloads(), name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(stego)
        messagebox.showinfo("", path)

    def open_file(self):
        path = filedialog.askopenfilename(initialdir=downloads())
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        self.stego_view.delete("1.0", tk.END)
        self.stego_view.insert("1.0", text)
        self.dec_view.delete("1.0", tk.END)
        self.bin_view.delete("1.0", tk.END)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    App().run()
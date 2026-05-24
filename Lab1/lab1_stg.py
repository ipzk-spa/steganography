import os
import sys
import subprocess


def load_pillow():
    try:
        from PIL import Image
        return Image
    except ImportError:
        print("Бібліотеку Pillow не знайдено. Встановлюю...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])
            from PIL import Image
            print("Pillow успішно встановлено.")
            return Image
        except Exception:
            print("Не вдалося встановити Pillow автоматично.")
            print("Спробуй вручну: pip install pillow")
            sys.exit(1)


Image = load_pillow()

END_MARK = "|||END|||"


def check_image_path(image_path):
    if not image_path:
        return False, "Файл не вибрано."
    if not os.path.exists(image_path):
        return False, "Файл не знайдено."
    ext = os.path.splitext(image_path)[1].lower()
    if ext not in [".png", ".bmp"]:
        return False, "Потрібен файл PNG або BMP."
    return True, ""


def make_output_path(image_path):
    folder = os.path.dirname(image_path)
    name, ext = os.path.splitext(os.path.basename(image_path))
    return os.path.join(folder, name + "_stego" + ext)


def text_to_bits(text):
    data = text.encode("utf-8")
    bits = ""
    for byte in data:
        bits += format(byte, "08b")
    return bits


def encode_image(image_path, message):
    ok, err = check_image_path(image_path)
    if not ok:
        return False, err

    if not message.strip():
        return False, "Введіть текст для приховування."

    output_path = make_output_path(image_path)

    img = Image.open(image_path).convert("RGB")
    pixels = list(img.getdata())

    full_message = message + END_MARK
    bits = text_to_bits(full_message)

    capacity = len(pixels) * 3
    if len(bits) > capacity:
        return False, "У зображенні замало місця для цього тексту."

    new_pixels = []
    bit_index = 0

    for pixel in pixels:
        r, g, b = pixel
        colors = [r, g, b]

        for i in range(3):
            if bit_index < len(bits):
                bit = int(bits[bit_index])
                colors[i] = (colors[i] & ~1) | bit
                bit_index += 1

        new_pixels.append(tuple(colors))

    new_img = Image.new("RGB", img.size)
    new_img.putdata(new_pixels)
    new_img.save(output_path)

    report = "Повідомлення приховано.\n"
    report += "Збережено: " + output_path + "\n\n"
    report += compare_images(image_path, output_path)
    return True, report


def decode_image(image_path):
    ok, err = check_image_path(image_path)
    if not ok:
        return False, err

    img = Image.open(image_path).convert("RGB")
    marker = END_MARK.encode("utf-8")
    data = bytearray()
    bit_value = 0
    bit_count = 0

    for r, g, b in img.getdata():
        for color in (r, g, b):
            bit_value = (bit_value << 1) | (color & 1)
            bit_count += 1

            if bit_count == 8:
                data.append(bit_value)
                bit_value = 0
                bit_count = 0

                pos = data.find(marker)
                if pos != -1:
                    msg = data[:pos].decode("utf-8", errors="replace")
                    return True, "Приховане повідомлення:\n" + msg

    return False, "Приховане повідомлення не знайдено. Відкрийте файл *_stego.png з прихованим текстом."


def compare_images(original_path, encoded_path):
    img1 = Image.open(original_path).convert("RGB")
    img2 = Image.open(encoded_path).convert("RGB")

    if img1.size != img2.size:
        return "Неможливо порівняти зображення різного розміру."

    pixels1 = list(img1.getdata())
    pixels2 = list(img2.getdata())

    changed_pixels = 0
    changed_channels = 0

    for i in range(len(pixels1)):
        p1 = pixels1[i]
        p2 = pixels2[i]
        if p1 != p2:
            changed_pixels += 1
        for j in range(3):
            if p1[j] != p2[j]:
                changed_channels += 1

    total_pixels = len(pixels1)
    total_channels = total_pixels * 3

    report = "Порівняння зображень:\n"
    report += "Розмір: " + str(img1.size[0]) + " x " + str(img1.size[1]) + "\n"
    report += "Змінено пікселів: " + str(changed_pixels) + " з " + str(total_pixels) + "\n"
    report += "Змінено компонент RGB: " + str(changed_channels) + " з " + str(total_channels)
    return report


def get_capacity(image_path):
    ok, err = check_image_path(image_path)
    if not ok:
        return False, err

    img = Image.open(image_path).convert("RGB")
    width, height = img.size
    capacity_bits = width * height * 3
    capacity_bytes = capacity_bits // 8

    report = "Розмір: " + str(width) + " x " + str(height) + "\n"
    report += "Максимальна ємність: " + str(capacity_bits) + " біт\n"
    report += "Приблизно: " + str(capacity_bytes) + " байт"
    return True, report


def run_gui():
    import threading
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext

    root = tk.Tk()
    root.title("LSB стеганографія — лаб. 1")
    root.geometry("620x480")
    root.minsize(500, 400)

    image_path = tk.StringVar()

    def log(text):
        result_box.delete("1.0", tk.END)
        result_box.insert(tk.END, text)

    def browse_image():
        path = filedialog.askopenfilename(
            title="Виберіть зображення",
            filetypes=[("Зображення", "*.png *.bmp"), ("Усі файли", "*.*")]
        )
        if path:
            image_path.set(path)

    busy = {"on": False}

    def run_in_thread(label, work):
        if busy["on"]:
            return
        if not image_path.get():
            messagebox.showwarning("Увага", "Спочатку виберіть зображення.")
            return

        busy["on"] = True
        log(label + "\nЗачекайте...")

        def task():
            ok, text = work()
            def finish():
                busy["on"] = False
                log(text)
                if not ok:
                    messagebox.showerror("Помилка", text.split("\n")[0])
            root.after(0, finish)

        threading.Thread(target=task, daemon=True).start()

    def do_encode():
        msg = msg_box.get("1.0", tk.END).strip()
        path = image_path.get()
        run_in_thread("Приховування...", lambda: encode_image(path, msg))

    def do_decode():
        path = image_path.get()
        run_in_thread("Вилучення тексту...", lambda: decode_image(path))

    def do_capacity():
        path = image_path.get()
        run_in_thread("Розрахунок ємності...", lambda: get_capacity(path))

    pad = {"padx": 8, "pady": 4}

    tk.Label(root, text="Зображення (PNG / BMP):").grid(row=0, column=0, sticky="w", **pad)
    tk.Entry(root, textvariable=image_path, width=50).grid(row=0, column=1, **pad)
    tk.Button(root, text="Огляд...", command=browse_image).grid(row=0, column=2, **pad)

    tk.Label(root, text="Текст для приховування:").grid(row=1, column=0, sticky="nw", **pad)
    msg_box = tk.Text(root, height=4, width=50)
    msg_box.grid(row=1, column=1, columnspan=2, sticky="we", **pad)
    msg_box.insert("1.0", "Pavlo Stepanchuk")

    btn_frame = tk.Frame(root)
    btn_frame.grid(row=2, column=0, columnspan=3, **pad)

    tk.Button(btn_frame, text="Приховати текст", width=18, command=do_encode).pack(side=tk.LEFT, padx=4)
    tk.Button(btn_frame, text="Вилучити текст", width=18, command=do_decode).pack(side=tk.LEFT, padx=4)
    tk.Button(btn_frame, text="Ємність", width=12, command=do_capacity).pack(side=tk.LEFT, padx=4)

    tk.Label(root, text="Результат:").grid(row=3, column=0, sticky="nw", **pad)
    result_box = scrolledtext.ScrolledText(root, height=14, width=60, state="normal")
    result_box.grid(row=3, column=1, columnspan=2, sticky="nsew", **pad)

    root.grid_columnconfigure(1, weight=1)
    root.grid_rowconfigure(3, weight=1)

    tk.Label(
        root,
        text="Після приховування файл зберігається поруч: photo.png → photo_stego.png",
        fg="gray"
    ).grid(row=4, column=0, columnspan=3, sticky="w", padx=8)

    root.mainloop()


def run_console():
    while True:
        print("\nLSB стеганографія")
        print("1 - приховати текст")
        print("2 - вилучити текст")
        print("3 - ємність")
        print("0 - вихід")

        choice = input("Вибір: ").strip()

        if choice == "1":
            path = input("Шлях до PNG/BMP: ").strip().strip('"')
            msg = input("Текст: ")
            ok, text = encode_image(path, msg)
            print(text)

        elif choice == "2":
            path = input("Шлях до зображення: ").strip().strip('"')
            ok, text = decode_image(path)
            print(text)

        elif choice == "3":
            path = input("Шлях до PNG/BMP: ").strip().strip('"')
            ok, text = get_capacity(path)
            print(text)

        elif choice == "0":
            break


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--console":
        run_console()
    else:
        run_gui()

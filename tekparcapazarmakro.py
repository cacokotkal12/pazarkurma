# -*- coding: utf-8 -*-
"""
AHMET2 - Slot Checker + Güvenli Pano & Yapıştır (tek dosya)
- Envanter boş slot sayımı + 3 eşikli sıralı tetik
- Telegram ile uyarı gönderme
- Güvenli pano (clipboard kilidi) ve KO'ya hızlı yapıştırma (F8)
- Windows 10 / PyInstaller (EXE) uyumlu.
"""

# =================== AYARLAR (ÜSTTE DEĞİŞTİR) ===================
# --- Slot checker / Telegram ---
TELEGRAM_TOKEN = '8009866329:AAFyeuZvrwe5klEii66bW10X-_2Uh4BElvk'  # Telegram bot token
CHAT_ID = '1520623463'                                             # Varsayılan sohbet ID
INVENTORY_REGION = (661, 446, 1012, 647)  # (x,y,genişlik,yükseklik)
DEFAULT_CHECK_INTERVAL = 2             # Tarama aralığı (sn)
DEFAULT_THRESHOLD_1 = 1               # 1. eşik (LOW)
DEFAULT_THRESHOLD_2 = 9               # 2. eşik (MID)
DEFAULT_THRESHOLD_3 = 18              # 3. eşik (HIGH)
DEFAULT_TELEGRAM_THRESHOLD = 25       # Telegram için eşik
KEY_DELAY = 0.20                      # Klavye bekleme (sn)
MOUSE_DELAY = 0.10                    # Mouse bekleme (sn)
TEMPLATE_PATH = "bos_slot.png"        # Boş slot şablon dosyası
TEMPLATE_THRESH = 0.97                # Şablon benzerlik eşiği

# --- Pano / Yapıştırıcı ---
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"  # Tesseract yolu
BRING_KO_BEFORE_PASTE = True    # Yapıştırma öncesi KO penceresini öne al
PASTE_DELAY = 0.15               # Pano->Ctrl+V gecikme (sn)
CLIPBOARD_LOCK_DEFAULT = True   # Pano kilidi başlangıçta açık
CLIPBOARD_POLL_MS = 400         # Pano guard aralığı (ms)
POSSIBLE_KO_TITLES = [          # KO pencere başlıkları
    "Knight OnLine Client", "Knight Online", "KnightOnline",
    "Knight OnLine", "KnightOnLine Client"
]
# =================================================================

import time, threading, traceback, requests
import pyautogui, cv2, numpy as np
from pynput.mouse import Controller as MouseController
from pynput.keyboard import Controller as KeyboardController, Key
import win32api, win32con

import pygetwindow as gw
import pytesseract
from PIL import ImageGrab
import tkinter as tk
from tkinter import messagebox
from tkinter import *  # SlotCheckerGUI'de kullanılan kısa isimler için (Frame, Label, Entry, Button, BooleanVar,...)
from tkinter import ttk

# Tesseract yolunu ata
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

# pyautogui ayarları
pyautogui.FAILSAFE = False
pyautogui.PAUSE = MOUSE_DELAY

# Global denetleyiciler
mouse = MouseController()
keyboard = KeyboardController()

# ================== DÜŞÜK SEVİYE MOUSE / TELEGRAM ==================
def click_win32(x, y, clicks=1):  # düşük seviyeli sol tık
    win32api.SetCursorPos((x, y)); time.sleep(MOUSE_DELAY)
    for _ in range(clicks):
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0); time.sleep(MOUSE_DELAY)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0);   time.sleep(MOUSE_DELAY)

def pick_and_drop(sx, sy, dx, dy):  # sürükle-bırak
    win32api.SetCursorPos((sx, sy)); time.sleep(MOUSE_DELAY)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0); time.sleep(MOUSE_DELAY)
    win32api.SetCursorPos((dx, dy)); time.sleep(MOUSE_DELAY)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0);  time.sleep(MOUSE_DELAY)

def send_telegram(msg):  # telegram mesaj gönder
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={'chat_id': CHAT_ID, 'text': msg},
            timeout=5
        )
    except Exception as e:
        print(f"[TELEGRAM] Hata: {e}")

# ================== SLOT CHECKER AKSİYONLARI ==================
def pazar_kur_aksiyonu(gui):  # Tek bir aksiyon; 3 eşik de bunu kullanıyor
    click_win32(769, 281, clicks=4); time.sleep(1.5)             # panel aç
    keyboard.press('h'); time.sleep(KEY_DELAY); keyboard.release('h'); time.sleep(KEY_DELAY)
    click_win32(917, 432, clicks=2); time.sleep(KEY_DELAY)        # alanlar
    click_win32(917, 432, clicks=2); time.sleep(KEY_DELAY)
    for row_y in (375, 425, 475, 525):                            # 4 satır × 7 sütun
        for i in range(7):
            sx = 365 + 50 * i
            pick_and_drop(sx, row_y, 383, 237)                    # itemi yukarı taşı
            keyboard.press(Key.ctrl); time.sleep(KEY_DELAY)
            keyboard.press('v'); keyboard.release('v'); keyboard.release(Key.ctrl); time.sleep(KEY_DELAY)
            keyboard.press(Key.enter); time.sleep(KEY_DELAY); keyboard.release(Key.enter); time.sleep(KEY_DELAY)
            keyboard.press(Key.enter); time.sleep(KEY_DELAY); keyboard.release(Key.enter); time.sleep(KEY_DELAY)
    click_win32(656, 610, clicks=2); time.sleep(KEY_DELAY)        # geri silme alanı
    for _ in range(50):
        keyboard.press(Key.backspace); time.sleep(0.2); keyboard.release(Key.backspace); time.sleep(0.2)
    click_win32(476, 644, clicks=1); time.sleep(61)               # pazar bekleme
    click_win32(476, 644, clicks=1); time.sleep(2)
    click_win32(806, 776, clicks=1); time.sleep(KEY_DELAY)        # pazar kapat

def esik1_aksiyonu(gui): pazar_kur_aksiyonu(gui)  # LOW tetikte
def esik2_aksiyonu(gui): pazar_kur_aksiyonu(gui)  # MID tetikte
def esik3_aksiyonu(gui): pazar_kur_aksiyonu(gui)  # HIGH tetikte

# ================== SAYIM & SIRALI TETİKLEME ==================
def kontrol_et(gui):
    try:
        ss = pyautogui.screenshot(region=INVENTORY_REGION)          # envanter SS
        ekran = cv2.cvtColor(np.array(ss), cv2.COLOR_RGB2BGR)       # BGR'e çevir
        tpl = cv2.imread(TEMPLATE_PATH)                             # boş slot şablonu
        if tpl is None:
            print(f"[WARN] '{TEMPLATE_PATH}' bulunamadı! Sayım atlandı."); return
        res = cv2.matchTemplate(ekran, tpl, cv2.TM_CCOEFF_NORMED)   # şablon eşleştirme
        yer = np.where(res >= TEMPLATE_THRESH)
        adet = len(yer[0])  # basit sayım (eşik üstü piksel kümeleri)
        gui.update_slot_count(adet)

        # Reset: eşiğin altına inince ilgili “done” sıfırlansın (tekrar tetik için)
        if adet < gui.threshold_1: gui.stage1_done = False
        if adet < gui.threshold_2: gui.stage2_done = False
        if adet < gui.threshold_3: gui.stage3_done = False

        # Sıra mantığı: 1 → 2 → 3 (aynı turda tek aksiyon)
        if not gui.stage1_done and (adet >= gui.threshold_1):
            esik1_aksiyonu(gui); gui.stage1_done = True
        elif gui.stage1_done and (not gui.stage2_done) and (adet >= gui.threshold_2):
            esik2_aksiyonu(gui); gui.stage2_done = True
        elif gui.stage2_done and (not gui.stage3_done) and (adet >= gui.threshold_3):
            esik3_aksiyonu(gui); gui.stage3_done = True

        # Telegram
        if adet >= gui.telegram_threshold and not gui.telegram_sent:
            name = gui.name_entry.get().strip() or "Varsayılan Ad"
            send_telegram(f"{name}: Envanterde {adet} boş slot var!")
            gui.telegram_sent = True
        elif adet < gui.telegram_threshold:
            gui.telegram_sent = False

    except Exception as e:
        print("[ERROR] kontrol_et:", e); traceback.print_exc()

def bot_loop(gui):
    while gui.running:
        kontrol_et(gui)
        for t in range(gui.check_interval, 0, -1):
            if not gui.running:
                break
            gui.update_timer(t); time.sleep(1)

# ========================= SLOT CHECKER TKINTER GUI =========================
class SlotCheckerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        try:
            self.tk.call('tk', 'scaling', 1.0)   # DPI düzeltme
        except Exception:
            pass
        self.title("Slot Checker - Ahmet2 (Sıralı 3 Eşik: 1->2->3)")
        self.geometry("480x920")
        self.resizable(False, False)

        # Durum değişkenleri
        self.running = False
        self.check_interval = DEFAULT_CHECK_INTERVAL
        self.threshold_1 = DEFAULT_THRESHOLD_1
        self.threshold_2 = DEFAULT_THRESHOLD_2
        self.threshold_3 = DEFAULT_THRESHOLD_3
        self.telegram_threshold = DEFAULT_TELEGRAM_THRESHOLD
        self.stage1_done = False
        self.stage2_done = False
        self.stage3_done = False
        self.telegram_sent = False

        # Başlık / sayaç
        self.slot_label = tk.Label(self, text="Boş Slot Sayısı: -", font=("Arial", 16, 'bold'))
        self.slot_label.pack(pady=10)

        # Kimlik
        fr_id = tk.LabelFrame(self, text="Kimlik", padx=8, pady=6)
        fr_id.pack(fill="x", padx=12, pady=6)
        tk.Label(fr_id, text="Bilgisayar/Sunucu Adı:", font=("Arial", 12)).grid(row=0, column=0, sticky="w")
        self.name_entry = tk.Entry(fr_id, justify="center", font=("Arial", 12), width=24)
        self.name_entry.insert(0, "Varsayılan Ad")
        self.name_entry.grid(row=0, column=1, padx=6)

        # Eşikler (3 kutucuk)
        fr_thr = tk.LabelFrame(self, text="Eşikler (slot ≥ ... tetikler)", padx=8, pady=8)
        fr_thr.pack(fill="x", padx=12, pady=6)
        tk.Label(fr_thr, text="1) LOW:", font=("Arial", 12)).grid(row=0, column=0, sticky="w")
        self.entry_t1 = tk.Entry(fr_thr, justify="center", font=("Arial", 12), width=8)
        self.entry_t1.insert(0, str(DEFAULT_THRESHOLD_1))
        self.entry_t1.grid(row=0, column=1, padx=6)

        tk.Label(fr_thr, text="2) MID:", font=("Arial", 12)).grid(row=1, column=0, sticky="w", pady=4)
        self.entry_t2 = tk.Entry(fr_thr, justify="center", font=("Arial", 12), width=8)
        self.entry_t2.insert(0, str(DEFAULT_THRESHOLD_2))
        self.entry_t2.grid(row=1, column=1, padx=6)

        tk.Label(fr_thr, text="3) HIGH:", font=("Arial", 12)).grid(row=2, column=0, sticky="w", pady=4)
        self.entry_t3 = tk.Entry(fr_thr, justify="center", font=("Arial", 12), width=8)
        self.entry_t3.insert(0, str(DEFAULT_THRESHOLD_3))
        self.entry_t3.grid(row=2, column=1, padx=6)

        tk.Label(fr_thr, text="Telegram (≥):", font=("Arial", 12)).grid(row=3, column=0, sticky="w", pady=4)
        self.entry_tel = tk.Entry(fr_thr, justify="center", font=("Arial", 12), width=8)
        self.entry_tel.insert(0, str(DEFAULT_TELEGRAM_THRESHOLD))
        self.entry_tel.grid(row=3, column=1, padx=6)

        tk.Button(
            fr_thr, text="Eşikleri Kaydet", font=("Arial", 12, 'bold'),
            command=self.save_thresholds, bg="#6C63FF", fg="white"
        ).grid(row=0, column=2, rowspan=4, padx=10, sticky="ns")

        # Süre
        fr_it = tk.LabelFrame(self, text="Tarama Süresi", padx=8, pady=8)
        fr_it.pack(fill="x", padx=12, pady=6)
        tk.Label(fr_it, text="Süre (sn):", font=("Arial", 12)).grid(row=0, column=0, sticky="w")
        self.entry_interval = tk.Entry(fr_it, justify="center", font=("Arial", 12), width=8)
        self.entry_interval.insert(0, str(DEFAULT_CHECK_INTERVAL))
        self.entry_interval.grid(row=0, column=1, padx=6)
        tk.Button(
            fr_it, text="Süreyi Kaydet", font=("Arial", 12),
            command=self.save_check_interval, bg="#2196F3", fg="white"
        ).grid(row=0, column=2, padx=10)

        # Sayaç
        self.timer_label = tk.Label(self, text="Sonraki taramaya kalan süre: - saniye",
                                    font=("Arial", 12), fg="navy")
        self.timer_label.pack(pady=6)

        # Kontrol
        fr_ctrl = tk.Frame(self)
        fr_ctrl.pack(pady=10)
        tk.Button(
            fr_ctrl, text="Başlat", width=14, command=self.start_bot,
            bg="#2E7D32", fg="white", font=("Arial", 12, 'bold')
        ).grid(row=0, column=0, padx=10)
        tk.Button(
            fr_ctrl, text="Durdur", width=14, command=self.stop_bot,
            bg="#C62828", fg="white", font=("Arial", 12, 'bold')
        ).grid(row=0, column=1, padx=10)

    # UI yardımcıları
    def update_slot_count(self, n: int):
        self.slot_label.config(text=f"Boş Slot Sayısı: {n}")

    def update_timer(self, t: int):
        self.timer_label.config(text=f"Sonraki taramaya kalan süre: {t} saniye")

    def save_thresholds(self):
        try:
            t1 = int(self.entry_t1.get())
            t2 = int(self.entry_t2.get())
            t3 = int(self.entry_t3.get())
            tel = int(self.entry_tel.get())
            if min(t1, t2, t3, tel) < 1:
                raise ValueError("Eşikler 1'den küçük olamaz.")
            if not (t1 < t2 < t3):
                raise ValueError("Sıra şartı: T1 < T2 < T3 olmalı.")
            self.threshold_1 = t1
            self.threshold_2 = t2
            self.threshold_3 = t3
            self.telegram_threshold = tel
            # Üst seviyeleri güvenli sıfırla
            self.stage2_done = False if self.stage1_done else self.stage2_done
            self.stage3_done = False
            messagebox.showinfo("OK", f"Eşikler kaydedildi: {t1} / {t2} / {t3}, TEL={tel}")
        except Exception as e:
            messagebox.showerror("Hata", str(e))

    def save_check_interval(self):
        try:
            v = int(self.entry_interval.get())
            if v < 1:
                raise ValueError("Süre 1'den küçük olamaz.")
            self.check_interval = v
            messagebox.showinfo("OK", f"Süre {v} sn")
        except Exception as e:
            messagebox.showerror("Hata", f"Geçerli sayı girin. {e}")

    def start_bot(self):
        if not self.running:
            self.running = True
            threading.Thread(target=bot_loop, args=(self,), daemon=True).start()

    def stop_bot(self):
        self.running = False

# =================== KO PENCERE / OCR YARDIMCILARI ===================
def bring_knight_online_to_front():
    """KO penceresini öne al, bulunamazsa False döner."""
    for title in POSSIBLE_KO_TITLES:
        wins = gw.getWindowsWithTitle(title)
        if wins:
            try:
                wins[0].activate()
                time.sleep(0.5)
                return True
            except Exception:
                pass
    print("Knight Online penceresi bulunamadı.")
    return False

def get_coordinates_from_screen():
    """Koordinat OCR (örnek ROI). Projede gerekiyorsa kullanılır."""
    bbox = (38, 104, 163, 123)              # sağ üst koordinat alanı (örnek)
    img = ImageGrab.grab(bbox)
    text = pytesseract.image_to_string(img)
    try:
        parts = text.strip().replace('\n', ' ').replace(',', ' ').split()
        if len(parts) >= 2:
            return (int(parts[0]), int(parts[1]))
    except Exception as e:
        print(f"Koordinat okuyamadı: {e}")
    return None

# =================== GELİŞMİŞ APP (PANO + SLOT CHECKER) ===================
class SlotCheckerApp(SlotCheckerGUI):
    """Kaydedilen metni her zaman panoda tutar ve güvenli yapıştır yapar."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Durum
        self.saved_text = ""                 # Sürekli korunacak metin
        self.lock_var = BooleanVar(value=CLIPBOARD_LOCK_DEFAULT)

        # --- Telegram ID alanı (sadece gösterim/manuel kayıt) ---
        frm_top = Frame(self); frm_top.pack(pady=6)
        Label(frm_top, text="Telegram ID:", font=("Arial", 11)).grid(row=0, column=0, padx=4)
        self.telegram_entry = Entry(frm_top, font=("Arial", 11), width=28)
        self.telegram_entry.grid(row=0, column=1, padx=4)
        Button(frm_top, text="Kaydet", font=("Arial", 10),
               command=self.save_telegram_id).grid(row=0, column=2, padx=4)

        # --- Yapıştırılacak Metin alanı ---
        frm_mid = Frame(self); frm_mid.pack(pady=6)
        Label(frm_mid, text="Yapıştırılacak Metin:", font=("Arial", 11)).grid(row=0, column=0, padx=4)
        self.text_entry = Entry(frm_mid, font=("Arial", 12), width=36)
        self.text_entry.grid(row=0, column=1, padx=4)

        Button(self, text="Metni Kaydet & Panoya Kopyala", font=("Arial", 11),
               command=self.save_and_copy_text).pack(pady=6)

        # Pano kilidi anahtarı
        ttk.Checkbutton(self, text="Panoyu kilitle (auto-yenile)",
                        variable=self.lock_var, command=self._on_lock_toggle).pack(pady=2)

        # Yapıştırma butonu / kısayol
        Button(self, text="Yapıştır (Ctrl+V) — F8", font=("Arial", 11),
               command=self.safe_paste_to_foreground).pack(pady=6)

        # F8 global kısayol
        self.bind_all("<F8>", lambda e: self.safe_paste_to_foreground())

        # Pano bekçisi başlat
        self.after(CLIPBOARD_POLL_MS, self._clipboard_guard_loop)

    # ----- Telegram -----
    def save_telegram_id(self):
        tid = self.telegram_entry.get().strip()
        if tid:
            self.telegram_id = tid           # şimdilik sadece hafızada tutuyor
            print(f"Telegram ID kaydedildi: {tid}")
        else:
            print("Lütfen bir Telegram ID girin!")

    # ----- Metin Kaydet & Panoya Yaz -----
    def save_and_copy_text(self):
        """
        Entry'deki metni kaydeder ve panoya yazar.
        Not: Yazdıktan HEMEN SONRA tekrar yazar (ikileme) ki pano daima bu içerik kalsın.
        """
        val = self.text_entry.get().strip()
        if not val:
            print("Lütfen yapıştırılacak metni girin!")
            return

        self.saved_text = val            # 1) metni hafızada tut
        self._reassert_clipboard()       # 2) panoya yaz
        self._reassert_clipboard()       # 3) hemen tekrar yaz (ikileme)
        print("Metin kaydedildi ve panoya kopyalandı (yeniden teyit edildi).")

    # ----- Güvenli Yapıştır -----
    def safe_paste_to_foreground(self):
        """
        Her yapıştırmadan önce saved_text panoya YENİDEN yazılır,
        Ctrl+V yapılır, ardından panoya tekrar yazılarak pano korunur.
        """
        # saved_text yoksa entry'den çek
        if not self.saved_text:
            val = self.text_entry.get().strip()
            if not val:
                print("Kaydedilmiş metin yok!")
                return
            self.saved_text = val

        if BRING_KO_BEFORE_PASTE:
            bring_knight_online_to_front()

        # 1) Yapıştırmadan hemen önce panoyu yeniden yaz
        self._reassert_clipboard()
        time.sleep(PASTE_DELAY)

        # 2) Ctrl+V
        try:
            keyboard.press(Key.ctrl); keyboard.press('v')
            keyboard.release('v'); keyboard.release(Key.ctrl)
        except Exception as e:
            print(f"Yapıştırma (Ctrl+V) hatası: {e}")
            return

        # 3) Yapıştırma sonrası panoyu tekrar saved_text ile doldur
        self._reassert_clipboard()
        print("Yapıştırma tamam, pano yeniden kilitlendi.")

    # ----- Pano kilidi bekçisi -----
    def _clipboard_guard_loop(self):
        """
        Pano kilidi açıksa belli aralıklarla panoyu denetler.
        Pano saved_text'ten farklı ise saved_text'i geri yazar.
        """
        try:
            if self.lock_var.get() and self.saved_text:
                try:
                    cur = self.clipboard_get()
                except Exception:
                    cur = ""
                if cur != self.saved_text:
                    # Dışarıdan Ctrl+C vs. olmuş → geri çevir
                    self._reassert_clipboard()
        except Exception as e:
            print(f"Pano bekçisi hatası: {e}")
        finally:
            self.after(CLIPBOARD_POLL_MS, self._clipboard_guard_loop)

    def _on_lock_toggle(self):
        print("Pano kilidi:", "Açık" if self.lock_var.get() else "Kapalı")

    # ----- Yardımcı: panoyu saved_text ile doldur -----
    def _reassert_clipboard(self):
        """saved_text'i panoya yazar (tek yer)."""
        try:
            self.clipboard_clear()
            self.clipboard_append(self.saved_text)
            self.update()  # Tk pano güncelle
        except Exception as e:
            print(f"Pano yazma hatası: {e}")

# =================== ÇALIŞTIR ===================
if __name__ == "__main__":
    app = SlotCheckerApp()
    app.title("AHMET2 — Slot Checker + Güvenli Pano")
    app.mainloop()

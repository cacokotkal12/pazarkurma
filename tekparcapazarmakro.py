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
SETTINGS_PATH = "ayarlar.json"        # Kalıcı ayar dosyası

# --- Launcher / Oyun Giriş ---
LAUNCHER_EXE = r"C:\\NTTGame\\KnightOnlineEn\\Launcher.exe"
FALLBACK_LAUNCHERS = [r"C:\\NTTGame\\KnightOnLineEn\\Launcher.exe"]
LAUNCHER_START_CLICK_POS = (974, 726)
WINDOW_TITLE_KEYWORD = "Knight Online"
WINDOW_APPEAR_TIMEOUT = 120.0
LOGIN_USERNAME_CLICK_POS = (579, 326)
LOGIN_PASSWORD_CLICK_POS = (579, 378)
SERVER_OPEN_POS = (455, 231)
SPLASH_CLICK_POS = (700, 550)

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

import time, threading, traceback, requests, json, os, subprocess, ctypes, sys
import pyautogui, cv2, numpy as np, keyboard
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


def _read_settings_store():
    if not os.path.exists(SETTINGS_PATH):
        return {}
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_settings_store(data: dict):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] Ayarlar kaydedilemedi: {e}")

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


def pause_aware_sleep(gui, seconds, chunk: float = 0.1):
    """Duraklatma/durdurmaya duyarlı bekleme."""
    end = time.time() + seconds
    while time.time() < end:
        if not getattr(gui, "running", False):
            break
        gui.wait_if_paused()
        remaining = end - time.time()
        time.sleep(min(chunk, max(remaining, 0)))

# ================== SLOT CHECKER AKSİYONLARI ==================
def pazar_kur_aksiyonu(gui):  # Tek bir aksiyon; 3 eşik de bunu kullanıyor
    if not gui.running:
        return
    click_win32(769, 281, clicks=4); pause_aware_sleep(gui, 1.5)             # panel aç
    keyboard.press('h'); pause_aware_sleep(gui, KEY_DELAY); keyboard.release('h'); pause_aware_sleep(gui, KEY_DELAY)
    click_win32(917, 432, clicks=2); pause_aware_sleep(gui, KEY_DELAY)        # alanlar
    click_win32(917, 432, clicks=2); pause_aware_sleep(gui, KEY_DELAY)
    for row_y in (375, 425, 475, 525):                            # 4 satır × 7 sütun
        if not gui.running:
            return
        for i in range(7):
            if not gui.running:
                return
            sx = 365 + 50 * i
            pick_and_drop(sx, row_y, 383, 237)                    # itemi yukarı taşı
            keyboard.press(Key.ctrl); pause_aware_sleep(gui, KEY_DELAY)
            keyboard.press('v'); keyboard.release('v'); keyboard.release(Key.ctrl); pause_aware_sleep(gui, KEY_DELAY)
            keyboard.press(Key.enter); pause_aware_sleep(gui, KEY_DELAY); keyboard.release(Key.enter); pause_aware_sleep(gui, KEY_DELAY)
            keyboard.press(Key.enter); pause_aware_sleep(gui, KEY_DELAY); keyboard.release(Key.enter); pause_aware_sleep(gui, KEY_DELAY)
            gui.wait_if_paused()
            if not gui.running:
                return
    click_win32(656, 610, clicks=2); pause_aware_sleep(gui, KEY_DELAY)        # geri silme alanı
    for _ in range(50):
        if not gui.running:
            return
        keyboard.press(Key.backspace); pause_aware_sleep(gui, 0.2); keyboard.release(Key.backspace); pause_aware_sleep(gui, 0.2)
        gui.wait_if_paused()
    click_win32(476, 644, clicks=1); pause_aware_sleep(gui, 61)               # pazar bekleme
    if not gui.running:
        return
    click_win32(476, 644, clicks=1); pause_aware_sleep(gui, 2)
    if not gui.running:
        return
    click_win32(806, 776, clicks=1); pause_aware_sleep(gui, KEY_DELAY)        # pazar kapat

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
        gui.wait_if_paused()
        if not gui.running:
            break
        kontrol_et(gui)
        for t in range(gui.check_interval, 0, -1):
            if not gui.running:
                break
            gui.wait_if_paused()
            if not gui.running:
                break
            gui.update_timer(t); time.sleep(1)

# ========================= SLOT CHECKER TKINTER GUI =========================
class SlotCheckerGUI(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        try:
            self.tk.call('tk', 'scaling', 1.0)   # DPI düzeltme
        except Exception:
            pass

        toplevel = self.winfo_toplevel()
        if isinstance(toplevel, tk.Tk):
            try:
                toplevel.title("Slot Checker - Ahmet2 (Sıralı 3 Eşik: 1->2->3)")
                toplevel.geometry("480x920")
                toplevel.resizable(False, False)
            except Exception:
                pass
        self.pack(fill="both", expand=True)

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
        self.paused = False
        self.key_delay = KEY_DELAY
        self.mouse_delay = MOUSE_DELAY

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

        # Hız
        fr_spd = tk.LabelFrame(self, text="Tuş / Mouse Hızı (sn gecikme)", padx=8, pady=8)
        fr_spd.pack(fill="x", padx=12, pady=6)
        tk.Label(fr_spd, text="Klavye:", font=("Arial", 12)).grid(row=0, column=0, sticky="w")
        self.entry_key_delay = tk.Entry(fr_spd, justify="center", font=("Arial", 12), width=8)
        self.entry_key_delay.insert(0, str(KEY_DELAY))
        self.entry_key_delay.grid(row=0, column=1, padx=6)

        tk.Label(fr_spd, text="Mouse:", font=("Arial", 12)).grid(row=1, column=0, sticky="w", pady=4)
        self.entry_mouse_delay = tk.Entry(fr_spd, justify="center", font=("Arial", 12), width=8)
        self.entry_mouse_delay.insert(0, str(MOUSE_DELAY))
        self.entry_mouse_delay.grid(row=1, column=1, padx=6)

        tk.Button(
            fr_spd, text="Hızları Kaydet", font=("Arial", 12),
            command=self.save_speeds, bg="#009688", fg="white"
        ).grid(row=0, column=2, rowspan=2, padx=10, sticky="ns")

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

        tk.Button(
            fr_ctrl, text="Duraklat", width=14, command=lambda: self.pause_bot(source="Buton"),
            bg="#F9A825", fg="black", font=("Arial", 12, 'bold')
        ).grid(row=1, column=0, padx=10, pady=4)
        tk.Button(
            fr_ctrl, text="Devam", width=14, command=lambda: self.resume_bot(source="Buton"),
            bg="#1565C0", fg="white", font=("Arial", 12, 'bold')
        ).grid(row=1, column=1, padx=10, pady=4)

        tk.Button(self, text="Tüm Ayarları Kaydet", font=("Arial", 12, 'bold'),
                  command=self.save_all_settings, bg="#512DA8", fg="white").pack(pady=8)

        self.status_label = tk.Label(self, text="Durum: Hazır", font=("Arial", 11), fg="darkgreen")
        self.status_label.pack(pady=4)

        threading.Thread(target=self._capslock_watchdog, daemon=True).start()

    # UI yardımcıları
    def update_slot_count(self, n: int):
        self.slot_label.config(text=f"Boş Slot Sayısı: {n}")

    def update_timer(self, t: int):
        self.timer_label.config(text=f"Sonraki taramaya kalan süre: {t} saniye")

    def _set_status(self, text: str, color: str = "navy"):
        if hasattr(self, "status_label"):
            self.status_label.config(text=f"Durum: {text}", fg=color)

    def _set_thresholds_from_values(self, t1: int, t2: int, t3: int, tel: int, show_message: bool = True):
        if min(t1, t2, t3, tel) < 1:
            raise ValueError("Eşikler 1'den küçük olamaz.")
        if not (t1 < t2 < t3):
            raise ValueError("Sıra şartı: T1 < T2 < T3 olmalı.")
        self.threshold_1 = t1
        self.threshold_2 = t2
        self.threshold_3 = t3
        self.telegram_threshold = tel
        self.stage2_done = False if self.stage1_done else self.stage2_done
        self.stage3_done = False
        if show_message:
            messagebox.showinfo("OK", f"Eşikler kaydedildi: {t1} / {t2} / {t3}, TEL={tel}")

    def _set_check_interval(self, value: int, show_message: bool = True):
        if value < 1:
            raise ValueError("Süre 1'den küçük olamaz.")
        self.check_interval = value
        if show_message:
            messagebox.showinfo("OK", f"Süre {value} sn")

    def persist_settings(self):
        data = _read_settings_store()
        data["slot_checker"] = {
            "name": self.name_entry.get().strip(),
            "threshold_1": self.threshold_1,
            "threshold_2": self.threshold_2,
            "threshold_3": self.threshold_3,
            "telegram_threshold": self.telegram_threshold,
            "check_interval": self.check_interval,
            "key_delay": self.key_delay,
            "mouse_delay": self.mouse_delay,
        }
        if hasattr(self, "telegram_entry"):
            data["slot_checker"]["telegram_id"] = self.telegram_entry.get().strip()
        if hasattr(self, "saved_text"):
            data["slot_checker"]["saved_text"] = self.saved_text
        if hasattr(self, "lock_var"):
            data["slot_checker"]["clipboard_lock"] = bool(self.lock_var.get())
        _write_settings_store(data)

    def load_settings(self):
        store = _read_settings_store()
        data = store.get("slot_checker", store)

        # Kimlik
        name_val = data.get("name")
        if name_val is not None:
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, str(name_val))

        # Eşikler
        try:
            t1 = int(data.get("threshold_1", self.threshold_1))
            t2 = int(data.get("threshold_2", self.threshold_2))
            t3 = int(data.get("threshold_3", self.threshold_3))
            tel = int(data.get("telegram_threshold", self.telegram_threshold))
            self._set_thresholds_from_values(t1, t2, t3, tel, show_message=False)
            self.entry_t1.delete(0, tk.END); self.entry_t1.insert(0, str(t1))
            self.entry_t2.delete(0, tk.END); self.entry_t2.insert(0, str(t2))
            self.entry_t3.delete(0, tk.END); self.entry_t3.insert(0, str(t3))
            self.entry_tel.delete(0, tk.END); self.entry_tel.insert(0, str(tel))
        except Exception as e:
            print(f"[WARN] Eşikler yüklenemedi: {e}")

        # Süre
        try:
            interval_val = int(data.get("check_interval", self.check_interval))
            self._set_check_interval(interval_val, show_message=False)
            self.entry_interval.delete(0, tk.END)
            self.entry_interval.insert(0, str(interval_val))
        except Exception as e:
            print(f"[WARN] Süre yüklenemedi: {e}")

        try:
            k_delay = float(data.get("key_delay", self.key_delay))
            m_delay = float(data.get("mouse_delay", self.mouse_delay))
            self._set_speed_settings(k_delay, m_delay, show_message=False)
            self.entry_key_delay.delete(0, tk.END); self.entry_key_delay.insert(0, str(k_delay))
            self.entry_mouse_delay.delete(0, tk.END); self.entry_mouse_delay.insert(0, str(m_delay))
        except Exception as e:
            print(f"[WARN] Hız ayarları yüklenemedi: {e}")

        # Ek alanlar (varsa)
        if hasattr(self, "telegram_entry"):
            tid = data.get("telegram_id")
            if tid is not None:
                self.telegram_entry.delete(0, tk.END)
                self.telegram_entry.insert(0, str(tid))
                self.telegram_id = tid
        if hasattr(self, "text_entry"):
            saved_text_val = data.get("saved_text", "")
            if saved_text_val:
                self.text_entry.delete(0, tk.END)
                self.text_entry.insert(0, saved_text_val)
                self.saved_text = saved_text_val
                if hasattr(self, "_reassert_clipboard"):
                    try:
                        self._reassert_clipboard()
                    except Exception:
                        pass
        if hasattr(self, "lock_var"):
            lock_state = data.get("clipboard_lock")
            if lock_state is not None:
                try:
                    self.lock_var.set(bool(lock_state))
                except Exception:
                    pass

    def save_thresholds(self):
        try:
            t1 = int(self.entry_t1.get())
            t2 = int(self.entry_t2.get())
            t3 = int(self.entry_t3.get())
            tel = int(self.entry_tel.get())
            self._set_thresholds_from_values(t1, t2, t3, tel, show_message=True)
            self.persist_settings()
        except Exception as e:
            messagebox.showerror("Hata", str(e))

    def save_check_interval(self):
        try:
            v = int(self.entry_interval.get())
            self._set_check_interval(v, show_message=True)
            self.persist_settings()
        except Exception as e:
            messagebox.showerror("Hata", f"Geçerli sayı girin. {e}")

    def _set_speed_settings(self, key_delay: float, mouse_delay: float, show_message: bool = True):
        if key_delay <= 0 or mouse_delay <= 0:
            raise ValueError("Gecikmeler 0'dan büyük olmalı.")
        global KEY_DELAY, MOUSE_DELAY
        KEY_DELAY = float(key_delay)
        MOUSE_DELAY = float(mouse_delay)
        self.key_delay = KEY_DELAY
        self.mouse_delay = MOUSE_DELAY
        pyautogui.PAUSE = MOUSE_DELAY
        if show_message:
            messagebox.showinfo("OK", f"Klavye gecikmesi: {KEY_DELAY} sn\nMouse gecikmesi: {MOUSE_DELAY} sn")

    def save_speeds(self):
        try:
            k = float(self.entry_key_delay.get())
            m = float(self.entry_mouse_delay.get())
            self._set_speed_settings(k, m, show_message=True)
            self.persist_settings()
        except Exception as e:
            messagebox.showerror("Hata", f"Hız ayarları kaydedilemedi: {e}")

    def save_all_settings(self):
        errors = []
        try:
            t1 = int(self.entry_t1.get()); t2 = int(self.entry_t2.get()); t3 = int(self.entry_t3.get()); tel = int(self.entry_tel.get())
            self._set_thresholds_from_values(t1, t2, t3, tel, show_message=False)
        except Exception as e:
            errors.append(f"Eşikler: {e}")
        try:
            v = int(self.entry_interval.get())
            self._set_check_interval(v, show_message=False)
        except Exception as e:
            errors.append(f"Süre: {e}")
        try:
            k = float(self.entry_key_delay.get()); m = float(self.entry_mouse_delay.get())
            self._set_speed_settings(k, m, show_message=False)
        except Exception as e:
            errors.append(f"Hız: {e}")
        self.persist_settings()
        if errors:
            messagebox.showerror("Hata", "\n".join(errors))
        else:
            messagebox.showinfo("OK", "Tüm ayarlar kaydedildi.")

    def start_bot(self):
        if not self.running:
            self.running = True
            self.paused = False
            self._set_status("Çalışıyor", "darkgreen")
            threading.Thread(target=bot_loop, args=(self,), daemon=True).start()

    def stop_bot(self):
        self.running = False
        self.paused = False
        self._set_status("Durduruldu", "darkred")

    def pause_bot(self, source: str = ""):
        if self.running and not self.paused:
            self.paused = True
            src = f" ({source})" if source else ""
            self.timer_label.config(text=f"Duraklatıldı{src}")
            self._set_status(f"Duraklatıldı{src}", "orange")

    def resume_bot(self, source: str = ""):
        if self.running and self.paused:
            self.paused = False
            src = f" ({source})" if source else ""
            self._set_status(f"Devam ediyor{src}", "darkgreen")

    def wait_if_paused(self):
        while self.running and self.paused:
            self.timer_label.config(text="Duraklatıldı — Caps Lock ile aç/kapat")
            time.sleep(0.2)

    def _capslock_watchdog(self):
        try:
            last = win32api.GetKeyState(win32con.VK_CAPITAL)
        except Exception:
            return
        while True:
            try:
                cur = win32api.GetKeyState(win32con.VK_CAPITAL)
                if cur != last:
                    if cur & 1:
                        self.pause_bot(source="Caps Lock")
                    else:
                        self.resume_bot(source="Caps Lock")
                    last = cur
            except Exception:
                pass
            time.sleep(0.15)

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
    def __init__(self, master=None, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

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

        # Kayıtlı ayarları (varsa) yükle
        self.load_settings()

    # ----- Telegram -----
    def save_telegram_id(self):
        tid = self.telegram_entry.get().strip()
        if tid:
            self.telegram_id = tid           # şimdilik sadece hafızada tutuyor
            print(f"Telegram ID kaydedildi: {tid}")
            self.persist_settings()
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
        self.persist_settings()
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
        self.persist_settings()

    # ----- Yardımcı: panoyu saved_text ile doldur -----
    def _reassert_clipboard(self):
        """saved_text'i panoya yazar (tek yer)."""
        try:
            self.clipboard_clear()
            self.clipboard_append(self.saved_text)
            self.update()  # Tk pano güncelle
        except Exception as e:
            print(f"Pano yazma hatası: {e}")

# =================== OYUN GİRİŞ MAKROSU (TAB) ===================
APP_NAME = "KOLogin"
VK_CAPITAL = 0x14


def _kb_pressed(name: str) -> bool:
    try:
        return keyboard.is_pressed(name)
    except Exception:
        return False


def is_capslock_on():
    return bool(ctypes.windll.user32.GetKeyState(VK_CAPITAL) & 1)


def wait_if_paused():
    while is_capslock_on():
        time.sleep(0.1)


def pause_point(ui_abort: threading.Event):
    if ui_abort.is_set():
        raise KeyboardInterrupt("UI abort")
    wait_if_paused()
    if _kb_pressed("f12"):
        raise KeyboardInterrupt("F12 abort")
    return True


def sleep_respect_pause(ui_abort: threading.Event, seconds: float):
    end = time.time() + float(seconds)
    while time.time() < end:
        pause_point(ui_abort)
        time.sleep(0.05)


def mouse_move(x: int, y: int, delay: float):
    pause_point(LoginMacroTab.UI_ABORT)
    ctypes.windll.user32.SetCursorPos(int(x), int(y))
    time.sleep(delay)


def mouse_click(delay: float, button: str = "left"):
    pause_point(LoginMacroTab.UI_ABORT)
    flags_down, flags_up = (win32con.MOUSEEVENTF_LEFTDOWN, win32con.MOUSEEVENTF_LEFTUP) if button == "left" else (
        win32con.MOUSEEVENTF_RIGHTDOWN, win32con.MOUSEEVENTF_RIGHTUP)
    win32api.mouse_event(flags_down, 0, 0)
    time.sleep(delay / 2)
    win32api.mouse_event(flags_up, 0, 0)
    time.sleep(delay / 2)


def press_vk(vk: int, delay: float):
    pause_point(LoginMacroTab.UI_ABORT)
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
    time.sleep(delay)
    ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
    time.sleep(delay)


class LoginMacroTab(tk.Frame):
    UI_ABORT = threading.Event()

    def __init__(self, master=None):
        super().__init__(master)
        self.pack(fill="both", expand=True)
        ttk.Label(self, text="Knight Online - Oyuna Giriş (StartPNG)", font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, columnspan=6, pady=(8, 12))

        self.username = ttk.Entry(self, width=32)
        self.password = ttk.Entry(self, width=32, show="*")
        ttk.Label(self, text="Kullanıcı Adı:").grid(row=1, column=0, sticky="w", pady=4)
        self.username.grid(row=1, column=1, columnspan=2, sticky="w")
        ttk.Label(self, text="Şifre:").grid(row=2, column=0, sticky="w", pady=4)
        self.password.grid(row=2, column=1, columnspan=2, sticky="w")

        ttk.Label(self, text="Hedef Server:").grid(row=1, column=3, sticky="e")
        self.server_target = tk.StringVar(value="1")
        ttk.Radiobutton(self, text="1", variable=self.server_target, value="1").grid(row=1, column=4, sticky="w")
        ttk.Radiobutton(self, text="2", variable=self.server_target, value="2").grid(row=1, column=5, sticky="w")

        self.s1x = ttk.Entry(self, width=8); self.s1y = ttk.Entry(self, width=8)
        self.s2x = ttk.Entry(self, width=8); self.s2y = ttk.Entry(self, width=8)
        ttk.Label(self, text="Server 1 X:").grid(row=3, column=0, sticky="e"); self.s1x.grid(row=3, column=1, sticky="w")
        ttk.Label(self, text="Server 1 Y:").grid(row=3, column=2, sticky="e"); self.s1y.grid(row=3, column=3, sticky="w")
        ttk.Label(self, text="Server 2 X:").grid(row=4, column=0, sticky="e"); self.s2x.grid(row=4, column=1, sticky="w")
        ttk.Label(self, text="Server 2 Y:").grid(row=4, column=2, sticky="e"); self.s2y.grid(row=4, column=3, sticky="w")

        self.s1x.insert(0, "671"); self.s1y.insert(0, "254")
        self.s2x.insert(0, "676"); self.s2y.insert(0, "281")

        self.tus_hizi = tk.DoubleVar(value=0.05)
        self.mouse_hizi = tk.DoubleVar(value=0.1)
        ttk.Label(self, text="Klavye Gecikme (sn):").grid(row=5, column=0, sticky="e", pady=4)
        ttk.Entry(self, textvariable=self.tus_hizi, width=8).grid(row=5, column=1, sticky="w")
        ttk.Label(self, text="Mouse Gecikme (sn):").grid(row=5, column=2, sticky="e", pady=4)
        ttk.Entry(self, textvariable=self.mouse_hizi, width=8).grid(row=5, column=3, sticky="w")

        self.btn_start = ttk.Button(self, text="Başlat", command=self.start_flow, width=18)
        self.btn_stop = ttk.Button(self, text="Durdur", command=self.stop_flow, width=18, state="disabled")
        self.btn_save = ttk.Button(self, text="Ayarları Kaydet", command=self.save_settings, width=18)
        self.btn_start.grid(row=6, column=0, pady=10, sticky="w")
        self.btn_stop.grid(row=6, column=1, pady=10, sticky="w")
        self.btn_save.grid(row=6, column=2, pady=10, sticky="w")

        ttk.Label(self, text="Log:").grid(row=7, column=0, sticky="w")
        lf = ttk.Frame(self); lf.grid(row=8, column=0, columnspan=6, sticky="nsew")
        self.txt = tk.Text(lf, width=86, height=14, font=("Consolas", 9))
        self.txt.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.txt.yview); sb.pack(side="right", fill="y")
        self.txt.configure(yscrollcommand=sb.set)
        hook_ui_logger(self.add_log)
        ttk.Label(self, text="CapsLock: Dur/Devam  |  F12: İptal", foreground="#777").grid(row=9, column=0, columnspan=6, pady=(6, 0))

        self.load_settings()

    def add_log(self, msg: str):
        self.txt.insert("end", f"{msg}\n"); self.txt.see("end"); self.update_idletasks()

    def load_settings(self):
        data = _read_settings_store().get("ko_login", {})
        self.username.delete(0, "end"); self.username.insert(0, data.get("username", ""))
        self.password.delete(0, "end"); self.password.insert(0, data.get("password", ""))
        self.server_target.set(str(data.get("target_server", "1")))
        s1 = data.get("server1_xy", [671, 254]); s2 = data.get("server2_xy", [676, 281])
        self.s1x.delete(0, "end"); self.s1x.insert(0, str(s1[0] if len(s1) >= 2 else 671))
        self.s1y.delete(0, "end"); self.s1y.insert(0, str(s1[1] if len(s1) >= 2 else 254))
        self.s2x.delete(0, "end"); self.s2x.insert(0, str(s2[0] if len(s2) >= 2 else 676))
        self.s2y.delete(0, "end"); self.s2y.insert(0, str(s2[1] if len(s2) >= 2 else 281))
        self.tus_hizi.set(float(data.get("key_delay", self.tus_hizi.get())))
        self.mouse_hizi.set(float(data.get("mouse_delay", self.mouse_hizi.get())))
        self.add_log("[Ayar] Giriş makro ayarları yüklendi.")

    def save_settings(self):
        def _to_int(v, d):
            try:
                return int(str(v).strip())
            except Exception:
                return d

        store = _read_settings_store()
        store["ko_login"] = {
            "username": self.username.get().strip(),
            "password": self.password.get().strip(),
            "target_server": self.server_target.get(),
            "server1_xy": [_to_int(self.s1x.get(), 671), _to_int(self.s1y.get(), 254)],
            "server2_xy": [_to_int(self.s2x.get(), 676), _to_int(self.s2y.get(), 281)],
            "key_delay": float(self.tus_hizi.get()),
            "mouse_delay": float(self.mouse_hizi.get()),
        }
        _write_settings_store(store)
        self.add_log("[Ayar] Ayarlar kaydedildi.")
        messagebox.showinfo("Bilgi", "Ayarlar kaydedildi.")

    def start_flow(self):
        u = self.username.get().strip(); p = self.password.get().strip()
        if not u or not p:
            messagebox.showwarning("Uyarı", "Kullanıcı adı ve şifre boş olamaz!"); return
        LoginMacroTab.UI_ABORT.clear()
        self.btn_start.config(state="disabled"); self.btn_stop.config(state="normal"); self.btn_save.config(state="disabled")
        s1 = (int(self.s1x.get()), int(self.s1y.get())); s2 = (int(self.s2x.get()), int(self.s2y.get()))
        threading.Thread(target=self._run_flow, args=(u, p, self.server_target.get(), s1, s2), daemon=True).start()

    def stop_flow(self):
        LoginMacroTab.UI_ABORT.set()
        self.add_log("[UI] Durdur istendi.")

    def _run_flow(self, u, p, t, s1_xy, s2_xy):
        ok = self.run_to_character(u, p, t, s1_xy, s2_xy)
        if ok:
            self.add_log("✓ Tamamlandı (StartPNG'ye kadar).")
            messagebox.showinfo("Tamam", "Karakter ekranına kadar giriş tamamlandı.")
        else:
            self.add_log("✗ Başarısız. Koordinat/şablon/yolları kontrol edin.")
        self.btn_start.config(state="normal"); self.btn_stop.config(state="disabled"); self.btn_save.config(state="normal")

    # ---- Akış ----
    def close_all_game_instances(self, max_wait: float = 8.0):
        self.add_log("Mevcut KO/Launcher süreçleri kapatılıyor...")
        os.system('taskkill /F /T /IM "KnightOnline.exe"')
        os.system('taskkill /F /T /IM "Launcher.exe"')
        end = time.time() + max_wait
        while time.time() < end:
            pause_point(LoginMacroTab.UI_ABORT)
            time.sleep(0.2)

    def start_launcher(self):
        path = LAUNCHER_EXE if os.path.exists(LAUNCHER_EXE) else next((p for p in FALLBACK_LAUNCHERS if os.path.exists(p)), None)
        if not path:
            self.add_log("HATA: Launcher bulunamadı.")
            return False
        try:
            os.startfile(path)
        except Exception:
            subprocess.Popen([path], shell=False)
        self.add_log("Launcher başlatıldı")
        return True

    def bring_launcher_window_to_front(self):
        wins = gw.getWindowsWithTitle("Launcher") or gw.getWindowsWithTitle("Knight Online Launcher")
        if not wins:
            return None
        w = wins[0]
        try:
            if w.isMinimized:
                w.restore()
            w.activate(); time.sleep(0.3)
            ctypes.windll.user32.SetForegroundWindow(int(w._hWnd))
        except Exception:
            pass
        return w

    def find_game_window(self, timeout=WINDOW_APPEAR_TIMEOUT):
        self.add_log("Oyun penceresi bekleniyor...")
        t0 = time.time()
        while time.time() - t0 < timeout:
            pause_point(LoginMacroTab.UI_ABORT)
            wins = gw.getWindowsWithTitle(WINDOW_TITLE_KEYWORD)
            cand = [w for w in wins if "launcher" not in w.title.lower() and "patch" not in w.title.lower()]
            if cand:
                cand.sort(key=lambda w: (w.width * w.height), reverse=True)
                return cand[0]
            time.sleep(0.3)
        return None

    def perform_login_inputs(self, username: str, password: str):
        self.add_log("Kullanıcı adı yazılıyor...")
        mouse_move(*LOGIN_USERNAME_CLICK_POS, delay=self.mouse_hizi.get()); mouse_click(self.mouse_hizi.get())
        keyboard.write(username)
        self.add_log("Şifre yazılıyor...")
        mouse_move(*LOGIN_PASSWORD_CLICK_POS, delay=self.mouse_hizi.get()); mouse_click(self.mouse_hizi.get())
        keyboard.write(password)
        press_vk(win32con.VK_RETURN, self.tus_hizi.get())
        press_vk(win32con.VK_RETURN, self.tus_hizi.get())
        self.add_log("[LOGIN] Kimlik bilgileri girildi ve Enter basıldı.")

    def select_server_by_coords(self, target: str, xy1: tuple[int, int], xy2: tuple[int, int]):
        sel_xy = xy1 if str(target) == "1" else xy2
        self.add_log(f"Server seçimi (hedef={target}) → {sel_xy}")
        mouse_move(*SERVER_OPEN_POS, delay=self.mouse_hizi.get()); mouse_click(self.mouse_hizi.get())
        if sel_xy and isinstance(sel_xy, tuple) and len(sel_xy) == 2:
            mouse_move(*sel_xy, delay=self.mouse_hizi.get()); mouse_click(self.mouse_hizi.get())

    def run_to_character(self, username: str, password: str, target_server: str, s1_xy: tuple[int, int], s2_xy: tuple[int, int]):
        try:
            self.close_all_game_instances()
            self.add_log("Launcher açılıyor...")
            if not self.start_launcher():
                return False
            time.sleep(2.0)
            self.bring_launcher_window_to_front()
            mouse_move(*LAUNCHER_START_CLICK_POS, delay=self.mouse_hizi.get()); mouse_click(self.mouse_hizi.get())
            w = self.find_game_window(timeout=WINDOW_APPEAR_TIMEOUT)
            if not w:
                self.add_log("HATA: Oyun penceresi gelmedi.")
                return False
            mouse_move(*SPLASH_CLICK_POS, delay=self.mouse_hizi.get()); mouse_click(self.mouse_hizi.get())
            mouse_click(self.mouse_hizi.get())
            press_vk(win32con.VK_RETURN, self.tus_hizi.get())
            press_vk(win32con.VK_RETURN, self.tus_hizi.get())
            sleep_respect_pause(LoginMacroTab.UI_ABORT, 5.0)
            self.perform_login_inputs(username, password)
            self.select_server_by_coords(target_server, s1_xy, s2_xy)
            press_vk(win32con.VK_RETURN, self.tus_hizi.get())
            self.add_log("Karakter ekranı (StartPNG) bekleniyor...")
            press_vk(win32con.VK_RETURN, self.tus_hizi.get())
            return True
        except KeyboardInterrupt:
            return False
        except Exception as e:
            self.add_log(f"HATA: {e}")
            return False


# =================== ANA UYGULAMA ===================
class MultiMacroApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tek Exe - Pazar + Oyuna Giriş Makroları")
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        self.slot_tab = SlotCheckerApp(notebook)
        self.login_tab = LoginMacroTab(notebook)
        notebook.add(self.slot_tab, text="Pazar Makrosu")
        notebook.add(self.login_tab, text="Oyuna Giriş Makrosu")


if __name__ == "__main__":
    app = MultiMacroApp()
    app.mainloop()

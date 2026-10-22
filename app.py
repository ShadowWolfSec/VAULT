"""
   
"""
import time
import csv
import json
import secrets
import shutil
from pathlib import Path
from pathlib import Path as _Path
from typing import Dict
from collections import deque

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

import constants as _c
from constants import C, FONT_MAIN, FONT_BOLD, FONT_TITLE, FONT_MONO, FONT_SMALL, VAULT_FILE, VERSION
import i18n as _i18n
from i18n import get_text, set_language
from theme import apply_theme
from exceptions import VaultError
from crypto import encrypt_vault, decrypt_vault
from security import SecureString, SecureLogger, ErrorHandler, LockManager
from storage import SecureFileManager
from performance import PerformanceOptimizer, LazyAccountLoader, cached_icon_lookup
from password_utils import pw_strength, pw_strength_icon, validate_master_pw, analyze_vault_security
from ui_widgets import styled_btn, apply_treeview_style
from ui_dialogs import (
    LoginWindow, CreateVaultDialog,
    AccountDialog, AccountDetailDialog, GeneratorWindow
)

# ────────────────────────────────────────────────────────────
#  ثوابت
# ────────────────────────────────────────────────────────────
CLIPBOARD_CLEAR_DELAY = 30   # ثانية
ACTIVITY_MAX = 50            # أقصى عدد سجلات النشاط


class VaultApp:
    def __init__(self):
        self.theme_mode = "system"
        apply_theme(self.theme_mode)

        self.vault_path   = Path(VAULT_FILE)
        self.locker       = LockManager(self.vault_path)
        self.file_manager = SecureFileManager(self.vault_path)

        self.logger        = SecureLogger(Path(_c.APP_DIR) / "vault_security.log")
        self.error_handler = ErrorHandler(self.logger)

        self.performance_optimizer = PerformanceOptimizer()
        self.account_loader        = None

        self.master_pw           = None
        self.vault               = None
        self._session_start_time = time.time()
        self._session_timer      = None
        self._clipboard_timer    = None

        # ميزة 1: إعداد عداد الحافظة
        self._clipboard_countdown = 0
        self._clipboard_label     = None
        self._is_locked           = False  # flag لإيقاف الـ ticks فوراً
        self._timer_gen           = 0      # generation counter — يزيد عند كل قفل/دخول

        # ميزة 3: قفل عند التصغير
        self.lock_on_minimize = False

        # ميزة 9: سجل النشاط (deque بحجم ثابت)
        self._activity_log: deque = deque(maxlen=ACTIVITY_MAX)

        self._load_settings()

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("VAULT — خزنة كلمات المرور")
        self.root.configure(bg=C["bg"])
        try:
            self.root.attributes('-rtl', True)
        except Exception:
            pass
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._set_icon()
        self._show_login()
        self.root.mainloop()

    # ════════════════════════════════════════════════════════
    #  تحميل / حفظ الإعدادات
    # ════════════════════════════════════════════════════════
    def _load_settings(self):
        try:
            sf = Path(_c.APP_DIR) / "vault_settings.json"
            if sf.exists():
                s = json.loads(sf.read_text())
                set_language(s.get("language", "ar"))
                self.theme_mode = s.get("theme", "system")
                apply_theme(self.theme_mode)
                try:
                    _c.SESSION_TIMEOUT = int(s.get("session_timeout", 15)) * 60
                except Exception:
                    pass
                self.lock_on_minimize = bool(s.get("lock_on_minimize", False))
        except Exception:
            pass

    def _save_settings(self):
        try:
            sf = Path(_c.APP_DIR) / "vault_settings.json"
            s = {
                "language":        _i18n.current_language,
                "theme":           self.theme_mode,
                "session_timeout": _c.SESSION_TIMEOUT // 60,
                "lock_on_minimize": self.lock_on_minimize,
            }
            sf.write_text(json.dumps(s, ensure_ascii=False, indent=2))
        except Exception:
            pass

    # ════════════════════════════════════════════════════════
    #  تسجيل الدخول
    # ════════════════════════════════════════════════════════
    def _show_login(self):
        LoginWindow(self.vault_path, self.locker, self._on_login_success)

    def _on_login_success(self, master_pw: str, vault: Dict, vault_path=None):
        self._is_locked = False  # إعادة تفعيل الـ ticks
        self._timer_gen += 1   # جيل جديد — يُبطل كل الـ ticks القديمة
        self.master_pw = SecureString(master_pw)
        self.vault     = vault

        # تحديث vault_path إذا فُتحت خزنة مختلفة عن الافتراضية
        if vault_path is not None:
            self.vault_path   = Path(vault_path)
            self.locker       = LockManager(self.vault_path)
            self.file_manager = SecureFileManager(self.vault_path)

        self._reset_account_loader()
        self._log_activity("activity_unlocked", "")
        try:
            self.root.attributes('-rtl', _i18n.current_language == "ar")
        except Exception:
            pass
        self._build_main_ui()
        self.root.deiconify()
        # ميزة 3: قفل عند التصغير
        self.root.bind("<Unmap>", self._on_minimize)
        self._refresh_accounts()
        self._start_session_timer()

    # ════════════════════════════════════════════════════════
    #  بناء الواجهة الرئيسية
    # ════════════════════════════════════════════════════════
    def _destroy_all_widgets(self):
        """تدمير كامل وآمن لكل widgets قبل إعادة البناء"""
        # إلغاء كل الـ pending afters أولاً
        try:
            for after_id in self.root.tk.call('after', 'info').split():
                try:
                    self.root.after_cancel(after_id)
                except Exception:
                    pass
        except Exception:
            pass
        # تدمير الـ widgets
        for widget in list(self.root.winfo_children()):
            try:
                widget.destroy()
            except Exception:
                pass
        # تحديث للتأكد من اكتمال التدمير
        try:
            self.root.update_idletasks()
        except Exception:
            pass

    def _build_main_ui(self):
        # تنظيف كامل قبل البناء
        self._destroy_all_widgets()

        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = 1020, 700
        self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        self.root.minsize(820, 580)

        # ── الرأس ──────────────────────────────────────────
        header = tk.Frame(self.root, bg=C["bg2"], height=64)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Frame(header, bg=C["accent"], width=4).pack(side=tk.RIGHT, fill=tk.Y)
        tk.Label(header, text=get_text("app_title"), font=("Consolas", 18, "bold"),
                 bg=C["bg2"], fg=C["accent"]).pack(side=tk.RIGHT, padx=16)
        tk.Label(header, text=get_text("app_subtitle"), font=FONT_MAIN,
                 bg=C["bg2"], fg=C["text_dim"]).pack(side=tk.RIGHT)

        self.session_lbl = tk.Label(header, text="", font=("Consolas", 10),
                                    bg=C["bg2"], fg=C["accent2"])
        self.session_lbl.pack(side=tk.RIGHT, padx=16)

        # ── شريط تبويبات مخصص ─────────────────────────────
        tab_container = tk.Frame(self.root, bg=C["bg"])
        tab_container.pack(fill=tk.BOTH, expand=True)

        tab_bar = tk.Frame(tab_container, bg=C["bg3"], height=42)
        tab_bar.pack(fill=tk.X)
        tab_bar.pack_propagate(False)

        self.current_tab = None
        self.tab_frames  = {}
        is_ar = _i18n.current_language == "ar"

        tabs_def = [
            (get_text("accounts_tab"),  "accounts"),
            (get_text("generator_tab"), "generator"),
            (get_text("settings_tab"),  "settings"),
        ]
        tabs = tabs_def if is_ar else list(reversed(tabs_def))
        pack_side = tk.RIGHT if is_ar else tk.LEFT

        self.tab_buttons = {}
        for i, (text, name) in enumerate(tabs):
            btn = tk.Button(
                tab_bar, text=text, font=FONT_BOLD,
                bg=C["bg2"] if name == "accounts" else C["bg3"],
                fg=C["accent"] if name == "accounts" else C["text"],
                bd=0, padx=18, pady=9, relief="flat", cursor="hand2",
                command=lambda n=name: self._switch_tab(n)
            )
            btn.pack(side=pack_side, padx=2, pady=4)
            self.tab_buttons[name] = btn
            if i == 0:
                self.current_tab = name

        self.content_area = tk.Frame(tab_container, bg=C["bg"])
        self.content_area.pack(fill=tk.BOTH, expand=True)

        self._build_accounts_tab_content()
        self._build_generator_tab_content()
        self._build_settings_tab_content()
        self._switch_tab("accounts")

    def _switch_tab(self, tab_name: str):
        if self.current_tab and self.current_tab in self.tab_frames:
            self.tab_frames[self.current_tab].pack_forget()
        if tab_name in self.tab_frames:
            self.tab_frames[tab_name].pack(fill=tk.BOTH, expand=True)
            self.current_tab = tab_name
        for name, btn in self.tab_buttons.items():
            btn.config(
                bg=C["bg2"] if name == tab_name else C["bg3"],
                fg=C["accent"] if name == tab_name else C["text"]
            )

    # ════════════════════════════════════════════════════════
    #  تبويب الحسابات
    # ════════════════════════════════════════════════════════
    def _build_accounts_tab_content(self):
        tab = tk.Frame(self.content_area, bg=C["bg"])
        self.tab_frames["accounts"] = tab
        is_ar = _i18n.current_language == "ar"

        # ── شريط الأدوات ───────────────────────────────────
        toolbar = tk.Frame(tab, bg=C["bg2"], pady=8, padx=12)
        toolbar.pack(fill=tk.X)

        btns_right = [
            (get_text("add_account"),  self._add_account,     C["accent2"]),
            (get_text("refresh"),      self._refresh_accounts, C["bg3"]),
            (get_text("export"),       self._export,           C["bg3"]),
            (get_text("export_csv"),   self._export_csv,       C["bg3"]),
            (get_text("import"),       self._import,           C["bg3"]),
            (get_text("import_csv"),   self._import_csv,       C["bg3"]),
        ]
        if is_ar:
            for text, cmd, col in btns_right:
                styled_btn(toolbar, text, cmd, col).pack(side=tk.RIGHT, padx=3)
        else:
            for text, cmd, col in reversed(btns_right):
                styled_btn(toolbar, text, cmd, col).pack(side=tk.LEFT, padx=3)

        # ── تنبيه تحليل الأمان (ميزة 6) ───────────────────
        self.audit_bar = tk.Frame(tab, bg=C["warning"], pady=0)
        self.audit_lbl = tk.Label(self.audit_bar, text="", font=FONT_SMALL,
                                  bg=C["warning"], fg="#000", cursor="hand2")
        self.audit_lbl.pack(side=tk.LEFT, padx=12, pady=4)
        tk.Button(self.audit_bar, text="✕", font=FONT_SMALL, relief="flat",
                  bg=C["warning"], fg="#000", bd=0, cursor="hand2",
                  command=lambda: self.audit_bar.pack_forget()).pack(side=tk.RIGHT, padx=8)
        # مخفي حتى يوجد مشاكل

        # ── بحث ────────────────────────────────────────────
        sf_frame = tk.Frame(tab, bg=C["bg"], padx=12, pady=6)
        sf_frame.pack(fill=tk.X)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *a: self._filter_accounts())

        srch_wrap = tk.Frame(sf_frame, bg=C["bg3"], highlightthickness=1,
                             highlightbackground=C["border"])
        if is_ar:
            tk.Label(sf_frame, text="🔍", font=FONT_MAIN,
                     bg=C["bg"], fg=C["text_dim"]).pack(side=tk.RIGHT)
            srch_wrap.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(0, 6))
        else:
            srch_wrap.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
            tk.Label(sf_frame, text="🔍", font=FONT_MAIN,
                     bg=C["bg"], fg=C["text_dim"]).pack(side=tk.LEFT)

        tk.Entry(srch_wrap, textvariable=self.search_var, font=FONT_MONO,
                 bg=C["bg3"], fg=C["text_bright"], insertbackground=C["accent"],
                 relief="flat", bd=5).pack(fill=tk.X)

        # ── عدد الحسابات ───────────────────────────────────
        self.count_lbl = tk.Label(tab, text="", font=FONT_SMALL,
                                  bg=C["bg"], fg=C["text_dim"])
        self.count_lbl.pack(anchor="e" if is_ar else "w", padx=14)

        # ── جدول الحسابات مع عمود القوة (ميزة 5) ──────────
        apply_treeview_style()
        tree_frame = tk.Frame(tab, bg=C["bg"], padx=12, pady=2)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("icon", "name", "username", "url", "strength", "modified")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                  style="Dark.Treeview")
        sb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        heads = {
            "icon":     ("",                      36,  "center"),
            "name":     (get_text("account_name"), 200, "w"),
            "username": (get_text("username"),      190, "w"),
            "url":      (get_text("url"),           180, "w"),
            "strength": (get_text("strength_col"),  80,  "center"),  # ميزة 5
            "modified": (get_text("modified"),      130, "center"),
        }
        for col, (text, width, anchor) in heads.items():
            self.tree.heading(col, text=text,
                              command=lambda c=col: self._sort_tree(c))  # ميزة 7
            self.tree.column(col, width=width, anchor=anchor,
                             stretch=(col not in ("icon", "strength")))

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Return>",   self._on_double_click)
        self.tree.bind("<Delete>",   self._delete_selected)

        # قائمة السياق
        self.ctx_menu = tk.Menu(self.root, tearoff=0, bg=C["bg2"], fg=C["text"],
                                activebackground=C["select"],
                                activeforeground=C["text_bright"],
                                font=FONT_MAIN, bd=0)
        self.ctx_menu.add_command(
            label="👁 " + ("عرض التفاصيل" if is_ar else "View Details"),
            command=self._view_selected)
        self.ctx_menu.add_command(
            label=get_text("clipboard_copy_pw"),
            command=self._copy_pw)
        self.ctx_menu.add_command(
            label=get_text("clipboard_copy_user"),
            command=self._copy_user)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(
            label="✏️ " + ("تعديل" if is_ar else "Edit"),
            command=self._edit_selected)
        self.ctx_menu.add_command(
            label="🗑 " + ("حذف" if is_ar else "Delete"),
            command=self._delete_selected)
        self.tree.bind("<Button-3>", self._show_ctx)

        # ── شريط الحالة + الحافظة ──────────────────────────
        status_bar = tk.Frame(tab, bg=C["bg3"], pady=5)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_lbl = tk.Label(status_bar, text=get_text("ready"),
                                   font=FONT_SMALL, bg=C["bg3"], fg=C["text_dim"])
        self.status_lbl.pack(side=tk.RIGHT if is_ar else tk.LEFT, padx=14)

        # عداد الحافظة (ميزة 1)
        self._clipboard_label = tk.Label(status_bar, text="", font=FONT_SMALL,
                                         bg=C["bg3"], fg=C["warning"])
        self._clipboard_label.pack(side=tk.LEFT if is_ar else tk.RIGHT, padx=14)

        tk.Label(status_bar, text="AES-256-GCM + Scrypt",
                 font=FONT_SMALL, bg=C["bg3"], fg=C["text_dim"]).pack(
            side=tk.LEFT if is_ar else tk.RIGHT, padx=14)

        # ترتيب الأعمدة
        self._sort_col = None
        self._sort_rev = False

    # ── فرز الأعمدة (ميزة 7) ─────────────────────────────
    def _sort_tree(self, col: str):
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = False
        accounts = self.vault.get("accounts", [])
        key_map = {
            "name": lambda a: a.get("name", "").lower(),
            "username": lambda a: a.get("username", "").lower(),
            "url": lambda a: a.get("url", "").lower(),
            "modified": lambda a: a.get("last_modified", 0),
            "strength": lambda a: pw_strength(a.get("password", ""))[0],
            "icon": lambda a: a.get("name", "").lower(),
        }
        key_fn = key_map.get(col, lambda a: "")
        accounts.sort(key=key_fn, reverse=self._sort_rev)
        self._filter_accounts()

    # ════════════════════════════════════════════════════════
    #  تبويب مولد كلمات المرور
    # ════════════════════════════════════════════════════════
    def _build_generator_tab_content(self):
        tab = tk.Frame(self.content_area, bg=C["bg"])
        self.tab_frames["generator"] = tab

        center = tk.Frame(tab, bg=C["bg"])
        center.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(center, text="⚡", font=("Segoe UI", 48),
                 bg=C["bg"], fg=C["accent"]).pack()
        tk.Label(center, text=get_text("password_generator"), font=FONT_TITLE,
                 bg=C["bg"], fg=C["text_bright"]).pack(pady=(0, 16))
        styled_btn(center, get_text("password_generator"),
                   lambda: GeneratorWindow(self.root), C["accent2"],
                   width=28).pack()

    # ════════════════════════════════════════════════════════
    #  تبويب الإعدادات
    # ════════════════════════════════════════════════════════
    def _build_settings_tab_content(self):
        tab = tk.Frame(self.content_area, bg=C["bg"])
        self.tab_frames["settings"] = tab
        is_ar = _i18n.current_language == "ar"

        outer = tk.Frame(tab, bg=C["bg"])
        outer.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(outer, bg=C["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=C["bg"])
        scroll_frame.bind("<Configure>",
                          lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        cwin = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(cwin, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        pad = tk.Frame(scroll_frame, bg=C["bg"])
        pad.pack(fill=tk.BOTH, expand=True, padx=28, pady=20)

        # ══ مساعدات ══════════════════════════════════════
        def card(icon, ar, en):
            c = tk.Frame(pad, bg=C["bg2"],
                         highlightthickness=1, highlightbackground=C["border"])
            c.pack(fill=tk.X, pady=(0, 12))
            hdr = tk.Frame(c, bg=C["bg3"])
            hdr.pack(fill=tk.X)
            tk.Frame(hdr, bg=C["accent"], width=3).pack(side=tk.LEFT, fill=tk.Y)
            hi = tk.Frame(hdr, bg=C["bg3"], pady=9, padx=12)
            hi.pack(fill=tk.X)
            txt = f"{icon}  {ar if is_ar else en}"
            tk.Label(hi, text=txt, font=FONT_BOLD, bg=C["bg3"],
                     fg=C["text_bright"]).pack(side=tk.RIGHT if is_ar else tk.LEFT)
            body = tk.Frame(c, bg=C["bg2"], padx=18, pady=12)
            body.pack(fill=tk.X)
            return body

        def info_row(parent, ico, ar, en, val):
            r = tk.Frame(parent, bg=C["bg2"])
            r.pack(fill=tk.X, pady=2)
            tk.Label(r, text=f"{ico}  {ar if is_ar else en}",
                     font=FONT_SMALL, bg=C["bg2"], fg=C["text_dim"],
                     width=22, anchor="e" if is_ar else "w").pack(
                side=tk.RIGHT if is_ar else tk.LEFT)
            tk.Label(r, text=val, font=("Consolas", 9), bg=C["bg2"],
                     fg=C["accent2"], anchor="w").pack(
                side=tk.LEFT if is_ar else tk.RIGHT, padx=8, fill=tk.X, expand=True)

        def action_btn(parent, text, cmd, color):
            r = tk.Frame(parent, bg=C["bg2"])
            r.pack(fill=tk.X, pady=2)
            b = tk.Button(r, text=text, command=cmd, bg=color,
                          fg=C["text_bright"], font=FONT_MAIN, relief="flat",
                          bd=0, padx=14, pady=8, cursor="hand2",
                          activebackground=C["btn_hover"],
                          activeforeground=C["text_bright"],
                          anchor="e" if is_ar else "w")
            b.pack(fill=tk.X)
            b.bind("<Enter>", lambda e: b.config(bg=C["btn_hover"] if color in (C["bg3"],"#2d333b") else color))
            b.bind("<Leave>", lambda e: b.config(bg=color))

        def setting_row(parent, ar, en, widget_fn):
            r = tk.Frame(parent, bg=C["bg2"])
            r.pack(fill=tk.X, pady=4)
            tk.Label(r, text=ar if is_ar else en, font=FONT_MAIN,
                     bg=C["bg2"], fg=C["text_dim"],
                     width=24, anchor="e" if is_ar else "w").pack(
                side=tk.RIGHT if is_ar else tk.LEFT)
            w = widget_fn(r)
            w.pack(side=tk.LEFT if is_ar else tk.RIGHT, padx=(0, 6))
            return w

        # ════════════════════════════════════════════════
        # 1 ▸ معلومات الخزنة (مختصرة ومركّزة)
        # ════════════════════════════════════════════════
        b_info = card("🗄️", "معلومات الخزنة", "Vault Information")

        vault    = self.vault or {}
        accounts = vault.get("accounts", [])
        created  = time.strftime("%Y-%m-%d  %H:%M",
                                 time.localtime(vault.get("created_at", 0))) if vault.get("created_at") else "—"
        modified = time.strftime("%Y-%m-%d  %H:%M",
                                 time.localtime(vault.get("last_modified", 0))) if vault.get("last_modified") else "—"

        info_row(b_info, "🔑", "عدد الحسابات", "Accounts",    str(len(accounts)))
        info_row(b_info, "📅", "تاريخ الإنشاء", "Created",    created)
        info_row(b_info, "✏️", "آخر تعديل",     "Last Modified", modified)
        info_row(b_info, "🔒", "التشفير",        "Encryption",  "AES-256-GCM")
        info_row(b_info, "✅", "التحقق",         "Integrity",   "HMAC-SHA256")
        self.info_text = tk.Entry(b_info, state="disabled", bg=C["bg2"], relief="flat", bd=0)

        # ════════════════════════════════════════════════
        # 2 ▸ تحليل الأمان (ميزة 6) — بطاقة احترافية
        # ════════════════════════════════════════════════
        b_audit = card("🔍", "تحليل الأمان", "Security Audit")

        self._audit_result_frame = tk.Frame(b_audit, bg=C["bg2"])
        self._audit_result_frame.pack(fill=tk.X)

        def run_audit():
            for w in self._audit_result_frame.winfo_children():
                w.destroy()
            audit = analyze_vault_security(self.vault.get("accounts", []))
            weak   = audit["weak"]
            reused = audit["reused"]

            if not weak and not reused:
                tk.Label(self._audit_result_frame,
                         text=get_text("audit_all_good"), font=FONT_MAIN,
                         bg=C["bg2"], fg=C["accent2"]).pack(anchor="w", pady=4)
                self.audit_bar.pack_forget()
                return

            # تنبيه في شريط الأعلى
            msgs = []
            if weak:
                msgs.append(get_text("audit_weak_count").format(n=len(weak)))
            if reused:
                msgs.append(get_text("audit_reused_count").format(n=len(reused)))
            self.audit_lbl.config(text="⚠️  " + "  |  ".join(msgs))
            self.audit_bar.pack(fill=tk.X, after=self.tab_frames["accounts"].winfo_children()[0]
                                if "accounts" in self.tab_frames else self.audit_bar)

            # عرض نتائج تفصيلية
            if weak:
                grp = tk.Frame(self._audit_result_frame, bg=C["bg2"])
                grp.pack(fill=tk.X, pady=(4, 0))
                tk.Label(grp, text=f"🔴  {get_text('audit_weak')} ({len(weak)})",
                         font=FONT_BOLD, bg=C["bg2"], fg=C["danger"]).pack(anchor="w")
                for nm in weak[:8]:
                    tk.Label(grp, text=f"   • {nm}", font=FONT_SMALL,
                             bg=C["bg2"], fg=C["text_dim"]).pack(anchor="w")
                if len(weak) > 8:
                    tk.Label(grp, text=f"   ... و{len(weak)-8} آخرين",
                             font=FONT_SMALL, bg=C["bg2"], fg=C["text_dim"]).pack(anchor="w")

            if reused:
                grp2 = tk.Frame(self._audit_result_frame, bg=C["bg2"])
                grp2.pack(fill=tk.X, pady=(8, 0))
                tk.Label(grp2, text=f"🟡  {get_text('audit_reused')} ({len(reused)})",
                         font=FONT_BOLD, bg=C["bg2"], fg=C["warning"]).pack(anchor="w")
                for group in reused[:4]:
                    tk.Label(grp2, text=f"   • {', '.join(group)}",
                             font=FONT_SMALL, bg=C["bg2"], fg=C["text_dim"]).pack(anchor="w")

        styled_btn(b_audit, get_text("security_audit"), run_audit, C["bg3"]).pack(
            anchor="w" if not is_ar else "e", pady=(0, 8))

        # ════════════════════════════════════════════════
        # 3 ▸ الإجراءات
        # ════════════════════════════════════════════════
        b_acts = card("⚡", "الإجراءات", "Actions")
        actions_list = [
            (get_text("change_master_password"), self._change_pw,  C["warning"]),
            (get_text("lock_vault"),             self._lock,       "#2d333b"),
            (get_text("export_vault"),           self._export,     "#2d333b"),
            (get_text("export_csv"),             self._export_csv, "#2d333b"),
            (get_text("import_vault"),           self._import,     "#2d333b"),
            (get_text("import_csv"),             self._import_csv, "#2d333b"),
            (get_text("new_vault"),              self._new_vault,  C["danger"]),
        ]
        for txt, cmd, col in actions_list:
            action_btn(b_acts, txt, cmd, col)

        # ════════════════════════════════════════════════
        # 4 ▸ إعدادات الجلسة
        # ════════════════════════════════════════════════
        b_sess = card("⏱️", "إعدادات الجلسة", "Session Settings")

        self.session_timeout_var = tk.StringVar(value=str(_c.SESSION_TIMEOUT // 60))

        def _sess_menu(parent):
            m = ttk.Combobox(parent, textvariable=self.session_timeout_var,
                             state="readonly",
                             values=("1", "5", "10", "15", "30", "60"), width=10)
            def _on_sess(e=None):
                try:
                    _c.SESSION_TIMEOUT = int(self.session_timeout_var.get()) * 60
                    if self.master_pw and self.vault:
                        self._session_start_time = time.time()
                        self._start_session_timer()
                    self._save_settings()
                except ValueError:
                    pass
            m.bind("<<ComboboxSelected>>", _on_sess)
            return m
        setting_row(b_sess, "مدة الجلسة (دقائق)", "Session Duration (min)", _sess_menu)

        # ميزة 3: قفل عند التصغير
        self._lock_min_var = tk.BooleanVar(value=self.lock_on_minimize)
        def _lock_min_check(parent):
            chk = tk.Checkbutton(parent, variable=self._lock_min_var,
                                  bg=C["bg2"], fg=C["text"],
                                  selectcolor=C["bg3"],
                                  activebackground=C["bg2"],
                                  relief="flat", bd=0, cursor="hand2",
                                  command=self._toggle_lock_minimize)
            return chk
        setting_row(b_sess, "قفل عند التصغير", "Lock on Minimize", _lock_min_check)

        # ════════════════════════════════════════════════
        # 5 ▸ المظهر واللغة
        # ════════════════════════════════════════════════
        b_appear = card("🎨", "المظهر واللغة", "Appearance & Language")

        self.language_var = tk.StringVar(value=_i18n.current_language)
        def _lang_menu(parent):
            m = ttk.Combobox(parent, textvariable=self.language_var,
                             state="readonly", values=("ar", "en"), width=10)
            m.bind("<<ComboboxSelected>>",
                   lambda e: self._change_language_and_rebuild(self.language_var.get()))
            return m
        setting_row(b_appear, "اللغة", "Language", _lang_menu)

        self.theme_var = tk.StringVar(value=self.theme_mode)
        def _theme_menu(parent):
            m = ttk.Combobox(parent, textvariable=self.theme_var,
                             state="readonly",
                             values=("system", "dark", "light"), width=10)
            def _on_theme(e=None):
                self.theme_mode = self.theme_var.get()
                apply_theme(self.theme_mode)
                self._save_settings()
                for w in self.root.winfo_children():
                    w.destroy()
                self.root.configure(bg=C["bg"])
                self._build_main_ui()
                self._refresh_accounts()
                self._switch_tab("settings")
            m.bind("<<ComboboxSelected>>", _on_theme)
            return m
        setting_row(b_appear, "المظهر", "Theme", _theme_menu)

        # ════════════════════════════════════════════════
        # 6 ▸ سجل النشاط (ميزة 9)
        # ════════════════════════════════════════════════
        b_log = card("📋", "سجل النشاط", "Activity Log")

        log_box = tk.Frame(b_log, bg=C["bg"], highlightthickness=1,
                           highlightbackground=C["border"])
        log_box.pack(fill=tk.X)

        log_canvas = tk.Canvas(log_box, bg=C["bg"], height=160, highlightthickness=0)
        log_sb = ttk.Scrollbar(log_box, orient="vertical", command=log_canvas.yview)
        log_inner = tk.Frame(log_canvas, bg=C["bg"])
        log_inner.bind("<Configure>",
                       lambda e: log_canvas.configure(scrollregion=log_canvas.bbox("all")))
        log_canvas.create_window((0, 0), window=log_inner, anchor="nw")
        log_canvas.configure(yscrollcommand=log_sb.set)
        log_canvas.pack(side="left", fill="both", expand=True)
        log_sb.pack(side="right", fill="y")

        if not self._activity_log:
            tk.Label(log_inner, text=get_text("activity_empty"), font=FONT_SMALL,
                     bg=C["bg"], fg=C["text_dim"]).pack(padx=12, pady=8, anchor="w")
        else:
            for entry in reversed(list(self._activity_log)):
                ts  = entry.get("time", "")
                key = entry.get("key", "")
                det = entry.get("detail", "")
                txt = f"{get_text(key)}  {det}".strip()
                r = tk.Frame(log_inner, bg=C["bg"])
                r.pack(fill=tk.X, padx=8, pady=1)
                tk.Label(r, text=ts, font=("Consolas", 8),
                         bg=C["bg"], fg=C["text_dim"], width=14).pack(side=tk.LEFT)
                tk.Label(r, text=txt, font=FONT_SMALL,
                         bg=C["bg"], fg=C["text"]).pack(side=tk.LEFT, padx=4)

        # ════════════════════════════════════════════════
        # 7 ▸ الدعم
        # ════════════════════════════════════════════════
        b_sup = card("📞", "الدعم", "Support")

        tk.Label(b_sup, text=get_text("support_desc"),
                 font=FONT_SMALL, bg=C["bg2"], fg=C["text_dim"],
                 wraplength=580, justify="right" if is_ar else "left",
                 anchor="e" if is_ar else "w").pack(fill=tk.X, pady=(0, 10))

        cc = tk.Frame(b_sup, bg=C["bg3"],
                      highlightthickness=1, highlightbackground=C["border"])
        cc.pack(fill=tk.X)
        tk.Frame(cc, bg=C["accent"], width=4).pack(
            side=tk.RIGHT if is_ar else tk.LEFT, fill=tk.Y)
        ci = tk.Frame(cc, bg=C["bg3"], padx=16, pady=12)
        ci.pack(fill=tk.X)

        nr = tk.Frame(ci, bg=C["bg3"])
        nr.pack(fill=tk.X, pady=(0, 6))
        tk.Label(nr, text="👤", bg=C["bg3"], fg=C["accent"],
                 font=("Segoe UI", 11)).pack(side=tk.RIGHT if is_ar else tk.LEFT, padx=(0, 6))
        tk.Label(nr, text=get_text("support_name"),
                 font=("Segoe UI", 10, "bold"), bg=C["bg3"],
                 fg=C["text_bright"]).pack(side=tk.RIGHT if is_ar else tk.LEFT)

        tk.Frame(ci, bg=C["border"], height=1).pack(fill=tk.X, pady=4)

        pr = tk.Frame(ci, bg=C["bg3"])
        pr.pack(fill=tk.X)
        tk.Label(pr, text="📱", bg=C["bg3"], fg=C["accent2"],
                 font=("Segoe UI", 11)).pack(side=tk.RIGHT if is_ar else tk.LEFT, padx=(0, 6))
        phone_num = get_text("support_phone")
        pl = tk.Label(pr, text=phone_num, font=("Consolas", 11, "bold"),
                      bg=C["bg3"], fg=C["accent2"], cursor="hand2")
        pl.pack(side=tk.RIGHT if is_ar else tk.LEFT)
        tk.Label(pr, text=f"  — {get_text('support_click_copy')}",
                 font=FONT_SMALL, bg=C["bg3"], fg=C["text_dim"]).pack(
            side=tk.RIGHT if is_ar else tk.LEFT)

        def _copy_phone(e=None):
            self.root.clipboard_clear()
            self.root.clipboard_append(phone_num)
            pl.config(fg=C["warning"], text="✅ " + ("تم النسخ!" if is_ar else "Copied!"))
            self.root.after(1800, lambda: pl.config(fg=C["accent2"], text=phone_num))
        pl.bind("<Button-1>", _copy_phone)

        tk.Frame(pad, bg=C["bg"], height=16).pack()

    # ════════════════════════════════════════════════════════
    #  عمليات الحسابات
    # ════════════════════════════════════════════════════════
    def _reset_account_loader(self):
        if self.vault is None:
            self.account_loader = None
        else:
            self.account_loader = LazyAccountLoader(self.vault)
        if hasattr(self, "performance_optimizer"):
            self.performance_optimizer._account_cache.clear()
            self.performance_optimizer._search_cache.clear()

    def _refresh_accounts(self):
        self._filter_accounts()
        self._update_info()

    def _filter_accounts(self):
        if not hasattr(self, "search_var") or not self.vault:
            return
        q = self.search_var.get().lower()

        if self.account_loader:
            if q:
                filtered = self.account_loader.search_accounts(q, self.performance_optimizer)
            else:
                all_acc = self.account_loader.get_all_accounts()
                filtered = all_acc
        else:
            accounts = self.vault.get("accounts", [])
            filtered = [a for a in accounts
                        if not q or q in a["name"].lower() or q in a["username"].lower()]

        for row in self.tree.get_children():
            self.tree.delete(row)

        for acc in filtered:
            modified = time.strftime("%Y-%m-%d %H:%M",
                                     time.localtime(acc.get("last_modified", 0)))
            score, _, color = pw_strength(acc.get("password", ""))
            icon_str = pw_strength_icon(score)  # ميزة 5

            self.tree.insert("", tk.END, iid=acc["id"], values=(
                cached_icon_lookup(acc["name"]),
                acc["name"], acc["username"],
                acc.get("url", "") or "—",
                icon_str,
                modified
            ), tags=(f"str_{score}",))

        # ألوان صفوف الجدول بناءً على قوة كلمة المرور
        self.tree.tag_configure("str_weak",   foreground=C["danger"])

        total = len(self.vault.get("accounts", [])) if self.vault else 0
        shown = len(filtered)
        is_ar = _i18n.current_language == "ar"
        if is_ar:
            self.count_lbl.config(
                text=f"{'🔍 ' if q else ''}{shown} حساب {'من '+str(total) if q else ''}")
        else:
            self.count_lbl.config(
                text=f"{'🔍 ' if q else ''}{shown} account{'s' if shown!=1 else ''}{' of '+str(total) if q else ''}")

        self.performance_optimizer.cleanup_cache()

    def _get_selected_account(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return next((a for a in self.vault["accounts"] if a["id"] == sel[0]), None)

    def _add_account(self):
        def on_save(acc):
            try:
                accounts = self.vault.setdefault("accounts", [])
                if any(a["name"].lower() == acc["name"].lower() for a in accounts):
                    messagebox.showerror("خطأ", f"الحساب '{acc['name']}' موجود بالفعل")
                    return
                accounts.append(acc)
                self._reset_account_loader()
                self._save_vault()
                self._refresh_accounts()
                self._log_activity("activity_added", acc["name"])
                self._set_status(f"✅ تمت إضافة: {acc['name']}")
            except VaultError as e:
                messagebox.showerror("خطأ في الحفظ", str(e))
        AccountDialog(self.root, on_save=on_save)

    def _view_selected(self, event=None):
        acc = self._get_selected_account()
        if not acc:
            return
        AccountDetailDialog(self.root, acc,
                            on_edit=self._edit_account,
                            on_delete=self._delete_account)

    def _on_double_click(self, event=None):
        self._view_selected()

    def _edit_selected(self, event=None):
        acc = self._get_selected_account()
        if acc:
            self._edit_account(acc)

    def _edit_account(self, acc):
        def on_save(updated):
            if not messagebox.askyesno("تأكيد", f"حفظ التعديلات على '{updated['name']}'؟"):
                return
            for i, a in enumerate(self.vault["accounts"]):
                if a["id"] == updated["id"]:
                    self.vault["accounts"][i] = updated
                    break
            self._reset_account_loader()
            self._save_vault()
            self._refresh_accounts()
            self._log_activity("activity_edited", updated["name"])
            self._set_status(f"✅ تم تحديث: {updated['name']}")
        AccountDialog(self.root, account=acc, on_save=on_save)

    def _delete_selected(self, event=None):
        acc = self._get_selected_account()
        if acc:
            self._delete_account(acc["id"])

    def _delete_account(self, acc_id):
        acc = next((a for a in self.vault["accounts"] if a["id"] == acc_id), None)
        if not acc:
            return
        if messagebox.askyesno("⚠️ تأكيد", f"حذف '{acc['name']}'؟"):
            self.vault["accounts"] = [a for a in self.vault["accounts"] if a["id"] != acc_id]
            self._reset_account_loader()
            self._save_vault()
            self._refresh_accounts()
            self._log_activity("activity_deleted", acc["name"])
            self._set_status(f"✅ تم حذف: {acc['name']}")

    # ════════════════════════════════════════════════════════
    #  الحافظة مع عداد (ميزة 1)
    # ════════════════════════════════════════════════════════
    def _copy_to_clipboard(self, text: str, label_key: str):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

        if self._clipboard_timer:
            self.root.after_cancel(self._clipboard_timer)

        self._clipboard_countdown = CLIPBOARD_CLEAR_DELAY
        gen = self._timer_gen
        self._clipboard_timer = self.root.after(1000, lambda: self._tick_clipboard(gen))
        is_ar = _i18n.current_language == "ar"
        self._set_status(f"{get_text(label_key)}  ⏱ {CLIPBOARD_CLEAR_DELAY}s")

    def _tick_clipboard(self, gen: int):
        if gen != self._timer_gen or self._is_locked:
            return
        if self._clipboard_countdown <= 0:
            try:
                self.root.clipboard_clear()
                if self._clipboard_label and self._clipboard_label.winfo_exists():
                    self._clipboard_label.config(text=get_text("clipboard_cleared"))
                    g = gen
                    self.root.after(2000, lambda: (
                        self._clipboard_label.config(text="")
                        if self._clipboard_label and self._clipboard_label.winfo_exists()
                        and g == self._timer_gen else None
                    ))
            except Exception:
                pass
            return
        try:
            if self._clipboard_label and self._clipboard_label.winfo_exists():
                clr_txt = get_text("clipboard_clear_in")
                sec_txt = get_text("clipboard_seconds")
                self._clipboard_label.config(
                    text=f"🕐 {clr_txt} {self._clipboard_countdown} {sec_txt}")
        except Exception:
            return
        self._clipboard_countdown -= 1
        self._clipboard_timer = self.root.after(1000, lambda: self._tick_clipboard(gen))

    def _copy_pw(self):
        acc = self._get_selected_account()
        if acc:
            self._copy_to_clipboard(acc["password"], "clipboard_copy_pw")

    def _copy_user(self):
        acc = self._get_selected_account()
        if acc:
            self._copy_to_clipboard(acc["username"], "clipboard_copy_user")

    def _show_ctx(self, event):
        sel = self.tree.identify_row(event.y)
        if sel:
            self.tree.selection_set(sel)
            self.ctx_menu.post(event.x_root, event.y_root)

    # ════════════════════════════════════════════════════════
    #  حفظ / تصدير / استيراد / CSV (ميزة 4)
    # ════════════════════════════════════════════════════════
    def _save_vault(self):
        try:
            if self.master_pw and isinstance(self.master_pw, SecureString):
                pw   = self.master_pw.get()
                blob = encrypt_vault(pw, self.vault)
                self.file_manager.atomic_write_with_backup(blob)
                self.logger.log_security_event("VAULT_SAVED", "تم الحفظ بنجاح")
            else:
                raise VaultError("كلمة المرور الرئيسية غير متوفرة")
        except VaultError:
            raise
        except PermissionError as e:
            raise VaultError(f"لا توجد صلاحيات الكتابة: {e}")
        except OSError as e:
            raise VaultError(f"خطأ في نظام الملفات: {e}")
        except Exception as e:
            raise VaultError(f"خطأ في حفظ الخزنة: {e}")

    def _export(self):
        dest = filedialog.asksaveasfilename(
            title="تصدير الخزنة", defaultextension=".dat",
            filetypes=[("Vault Files", "*.dat"), ("All Files", "*.*")]
        )
        if dest:
            shutil.copy2(self.vault_path, dest)
            try:
                Path(dest).chmod(0o600)
            except Exception:
                pass
            self._log_activity("activity_exported", Path(dest).name)
            self._set_status(f"✅ تم التصدير: {dest}")
            messagebox.showinfo("✅ تصدير", f"تم تصدير الخزنة:\n{dest}")

    def _export_csv(self):
        is_ar = _i18n.current_language == "ar"
        warn_ar = "تحذير أمني" + chr(10) + chr(10) + "ملف CSV يحتوي كلمات المرور بشكل واضح غير مشفر." + chr(10) + "احذف الملف فوراً بعد الاستخدام." + chr(10) + chr(10) + "هل تريد المتابعة؟"
        warn_en = "Security Warning" + chr(10) + chr(10) + "CSV file contains passwords in plain text." + chr(10) + "Delete the file immediately after use." + chr(10) + chr(10) + "Do you want to continue?"
        warn_msg = warn_ar if is_ar else warn_en
        title_w  = "⚠️ تحذير" if is_ar else "⚠️ Warning"
        if not messagebox.askyesno(title_w, warn_msg):
            return
        dest = filedialog.asksaveasfilename(
            title=get_text("export_csv"),
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialfile="vault_export.csv"
        )
        if not dest:
            return
        try:
            accounts   = self.vault.get("accounts", [])
            fieldnames = ["name", "url", "username", "password", "notes"]
            with open(dest, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for acc in accounts:
                    writer.writerow({
                        "name":     acc.get("name", ""),
                        "url":      acc.get("url", ""),
                        "username": acc.get("username", ""),
                        "password": acc.get("password", ""),
                        "notes":    acc.get("notes", ""),
                    })
            self._log_activity("activity_exported", "CSV: " + str(len(accounts)))
            n = len(accounts)
            ok_ar = "تم تصدير " + str(n) + " حساب." + chr(10) + chr(10) + "⚠️ احذف الملف بعد الاستخدام فوراً!" + chr(10) + dest
            ok_en = "Exported " + str(n) + " accounts." + chr(10) + chr(10) + "⚠️ Delete this file immediately after use!" + chr(10) + dest
            self._set_status(get_text("export_csv") + ": " + str(n))
            messagebox.showinfo("✅ CSV", ok_ar if is_ar else ok_en)
        except Exception as e:
            messagebox.showerror("❌ خطأ", "فشل التصدير: " + str(e))

    def _import(self):
        src = filedialog.askopenfilename(
            title="استيراد خزنة",
            filetypes=[("Vault Files", "*.dat"), ("All Files", "*.*")]
        )
        if not src:
            return
        pw = simpledialog.askstring("كلمة المرور",
                                    "أدخل كلمة مرور الخزنة المستوردة:", show="●")
        if not pw:
            return
        try:
            src_path = Path(src)
            vault = decrypt_vault(pw, src_path.read_bytes())
            n = len(vault.get("accounts", []))
            if messagebox.askyesno("تأكيد الاستيراد",
                                   f"سيتم دمج {n} حسابات. هل تريد المتابعة؟"):
                existing = {a["name"].lower() for a in self.vault["accounts"]}
                added = 0
                for acc in vault.get("accounts", []):
                    if acc["name"].lower() not in existing:
                        acc["id"] = secrets.token_hex(8)
                        self.vault["accounts"].append(acc)
                        added += 1
                if added > 0:
                    self._save_vault()
                    self._refresh_accounts()
                    self._log_activity("activity_imported", f"{added}")
                    self._set_status(f"✅ تم استيراد {added} حساب")
                    messagebox.showinfo("✅ استيراد", f"تم استيراد {added} حساب جديد")
                else:
                    messagebox.showinfo("معلومات", "لا توجد حسابات جديدة لاستيرادها")
        except Exception as e:
            error_msg, _ = self.error_handler.handle_vault_error(e, "استيراد")
            messagebox.showerror("❌ خطأ", f"فشل الاستيراد: {error_msg}")

    def _import_csv(self):
        """ميزة 4: استيراد CSV من Chrome / Firefox"""
        is_ar = _i18n.current_language == "ar"
        src = filedialog.askopenfilename(
            title=get_text("import_csv_title"),
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if not src:
            return
        try:
            added = 0
            existing = {a["name"].lower() for a in self.vault.get("accounts", [])}

            with open(src, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # دعم أعمدة Chrome وFirefox
            # Chrome: name, url, username, password
            # Firefox: url, username, password, httpRealm, formActionOrigin, guid, timeCreated, timeLastUsed, timePasswordChanged
            if not rows:
                messagebox.showinfo("معلومات", get_text("import_csv_none"))
                return

            for row in rows:
                # نُعيّن اسم الحساب
                name = (row.get("name") or
                        row.get("title") or
                        row.get("url", "").replace("https://","").replace("http://","").split("/")[0] or
                        "imported")
                username = row.get("username") or row.get("login") or ""
                password = row.get("password") or ""
                url      = row.get("url") or row.get("origin_url") or ""

                if not username and not password:
                    continue
                if name.lower() in existing:
                    continue

                acc = {
                    "id":            secrets.token_hex(8),
                    "name":          name,
                    "username":      username,
                    "password":      password,
                    "url":           url,
                    "notes":         "",
                    "last_modified": time.time(),
                }
                self.vault.setdefault("accounts", []).append(acc)
                existing.add(name.lower())
                added += 1

            if added > 0:
                self._save_vault()
                self._reset_account_loader()
                self._refresh_accounts()
                self._log_activity("activity_imported", f"CSV: {added}")
                msg = get_text("import_csv_success").format(n=added)
                self._set_status(f"✅ {msg}")
                messagebox.showinfo("✅ استيراد", msg)
            else:
                messagebox.showinfo("معلومات", get_text("import_csv_none"))

        except Exception as e:
            messagebox.showerror("❌ خطأ", f"{get_text('import_csv_error')}\n{e}")

    # ════════════════════════════════════════════════════════
    #  تغيير كلمة المرور
    # ════════════════════════════════════════════════════════
    def _change_pw(self):
        dlg = tk.Toplevel(self.root)
        dlg.title(get_text("change_master_password_dialog"))
        dlg.configure(bg=C["bg"])
        dlg.resizable(False, False)
        try:
            dlg.attributes('-rtl', _i18n.current_language == "ar")
        except Exception:
            pass
        dlg.grab_set()
        sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
        dlg.geometry(f"400x410+{(sw-400)//2}+{(sh-410)//2}")

        tk.Frame(dlg, bg=C["warning"], height=4).pack(fill=tk.X)
        body = tk.Frame(dlg, bg=C["bg"], padx=28, pady=18)
        body.pack(fill=tk.BOTH, expand=True)
        tk.Label(body, text=get_text("change_master_password_dialog"),
                 font=FONT_TITLE, bg=C["bg"], fg=C["text_bright"]).pack(pady=(0, 14))

        entries = {}
        is_ar = _i18n.current_language == "ar"
        for label, key in [(get_text("current_password"), "old"),
                           (get_text("new_password"),     "new"),
                           (get_text("confirm_password"), "confirm")]:
            tk.Label(body, text=label, font=FONT_SMALL, bg=C["bg"],
                     fg=C["text_dim"], anchor="e" if is_ar else "w").pack(fill=tk.X)
            f = tk.Frame(body, bg=C["bg3"], highlightthickness=1,
                         highlightbackground=C["border"])
            f.pack(fill=tk.X, pady=(2, 9))
            e = tk.Entry(f, show="●", font=FONT_MONO, bg=C["bg3"], fg=C["text_bright"],
                         insertbackground=C["accent"], relief="flat", bd=6,
                         justify="right" if is_ar else "left")
            e.pack(fill=tk.X)
            entries[key] = e

        bar = tk.Canvas(body, height=4, bg=C["border"], highlightthickness=0)
        bar.pack(fill=tk.X, pady=(0, 8))

        def _update_bar(e=None):
            pw = entries["new"].get()
            if not pw:
                bar.delete("all")
                return
            s, _, col = pw_strength(pw)
            w = bar.winfo_width() or 344
            bar.delete("all")
            bar.create_rectangle(0, 0, int(w * s / 100), 4, fill=col, outline="")
        entries["new"].bind("<KeyRelease>", _update_bar)

        err_lbl = tk.Label(body, text="", font=FONT_SMALL, bg=C["bg"], fg=C["danger"])
        err_lbl.pack()

        def do_change():
            old, new, conf = entries["old"].get(), entries["new"].get(), entries["confirm"].get()
            if not self.master_pw or not isinstance(self.master_pw, SecureString):
                err_lbl.config(text=get_text("current_password_error")); return
            try:
                if old != self.master_pw.get():
                    err_lbl.config(text=get_text("current_password_wrong")); return
            except Exception:
                err_lbl.config(text=get_text("password_access_error")); return
            if new != conf:
                err_lbl.config(text=get_text("passwords_not_match")); return
            ok, msg = validate_master_pw(new)
            if not ok:
                err_lbl.config(text=msg); return
            try:
                self.master_pw.wipe()
                self.master_pw = SecureString(new)
                self._save_vault()
                self._log_activity("activity_pw_changed", "")
                dlg.destroy()
                messagebox.showinfo(get_text("password_changed_success"),
                                    get_text("password_changed_msg"))
            except Exception as ex:
                try:
                    self.master_pw.wipe()
                    self.master_pw = SecureString(old)
                except Exception:
                    pass
                err_lbl.config(text=f"Error: {ex}")

        styled_btn(body, get_text("change_password_btn"), do_change, C["warning"]).pack(fill=tk.X, pady=6)
        entries["old"].focus()

    # ════════════════════════════════════════════════════════
    #  قفل / نافذة جديدة
    # ════════════════════════════════════════════════════════
    def _lock(self, auto: bool = False):
        if not auto and not messagebox.askyesno(
            get_text("lock_vault_confirm"), get_text("lock_vault_msg")
        ):
            return
        self._log_activity("activity_locked", "auto" if auto else "")

        # 0: وقف كل الـ ticks فوراً
        self._is_locked = True
        self._timer_gen += 1  # يُبطل كل callbacks معلقة

        # 1: إلغاء كل الـ timers أولاً قبل أي تدمير
        if self._session_timer:
            self.root.after_cancel(self._session_timer)
            self._session_timer = None
        if self._clipboard_timer:
            self.root.after_cancel(self._clipboard_timer)
            self._clipboard_timer = None

        # 2: مسح البيانات الحساسة
        if self.master_pw and isinstance(self.master_pw, SecureString):
            self.master_pw.wipe()
        self.master_pw = None
        self.vault     = None

        # 3: مسح الحافظة
        try:
            self.root.clipboard_clear()
        except Exception:
            pass

        # 4: تدمير كامل وآمن ثم عرض نافذة الدخول
        self.root.withdraw()
        self._destroy_all_widgets()
        self._show_login()

    def _new_vault(self):
        dest = filedialog.asksaveasfilename(
            title="حفظ خزنة جديدة", defaultextension=".dat",
            filetypes=[("Vault Files", "*.dat"), ("All Files", "*.*")],
            initialfile="vault.dat",
        )
        if dest:
            CreateVaultDialog(Path(dest), self.locker, self._on_login_success)

    # ════════════════════════════════════════════════════════
    #  ميزة 3: قفل عند التصغير
    # ════════════════════════════════════════════════════════
    def _on_minimize(self, event=None):
        if self.lock_on_minimize and self.master_pw:
            if self.root.state() == "iconic":
                self._lock(auto=True)

    def _toggle_lock_minimize(self):
        self.lock_on_minimize = self._lock_min_var.get()
        self._save_settings()

    # ════════════════════════════════════════════════════════
    #  مؤقت الجلسة
    # ════════════════════════════════════════════════════════
    def _start_session_timer(self):
        self._session_start_time = time.time()
        gen = self._timer_gen
        self._schedule_session_tick(gen)

    def _schedule_session_tick(self, gen: int):
        self._session_timer = self.root.after(1000, lambda: self._tick_session(gen))

    def _tick_session(self, gen: int):
        # تجاهل إذا كان الجيل قديماً أو التطبيق مقفل
        if gen != self._timer_gen or self._is_locked:
            return
        remaining = int(_c.SESSION_TIMEOUT - (time.time() - self._session_start_time))
        if remaining <= 0:
            self._lock(auto=True)
            return
        m, s = remaining // 60, remaining % 60
        try:
            if hasattr(self, "session_lbl") and self.session_lbl.winfo_exists():
                color = C["danger"] if remaining < 60 else C["warning"] if remaining < 120 else C["accent2"]
                self.session_lbl.config(text=f"⏱ {m:02d}:{s:02d}", fg=color)
        except Exception:
            return
        self._schedule_session_tick(gen)

    # ════════════════════════════════════════════════════════
    #  سجل النشاط (ميزة 9)
    # ════════════════════════════════════════════════════════
    def _log_activity(self, key: str, detail: str):
        self._activity_log.append({
            "time":   time.strftime("%m-%d %H:%M"),
            "key":    key,
            "detail": detail,
        })

    # ════════════════════════════════════════════════════════
    #  تغيير اللغة
    # ════════════════════════════════════════════════════════
    def _change_language_and_rebuild(self, lang: str):
        set_language(lang)
        self._save_settings()
        try:
            self.root.attributes('-rtl', lang == "ar")
        except Exception:
            pass
        self.root.configure(bg=C["bg"])
        self._build_main_ui()
        self._refresh_accounts()
        self._switch_tab("settings")

    # ════════════════════════════════════════════════════════
    #  مساعدات
    # ════════════════════════════════════════════════════════
    def _set_status(self, msg: str):
        if hasattr(self, "status_lbl"):
            self.status_lbl.config(text=msg)

    def _update_info(self):
        pass  # المعلومات داخل بطاقة الإعدادات

    def _set_icon(self):
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

    def _on_close(self):
        if messagebox.askyesno(get_text("exit"), get_text("exit_confirm")):
            if self._session_timer:
                self.root.after_cancel(self._session_timer)
            if self._clipboard_timer:
                self.root.after_cancel(self._clipboard_timer)
            self.root.clipboard_clear()
            if self.master_pw and isinstance(self.master_pw, SecureString):
                self.master_pw.wipe()
            self._save_settings()
            self.logger.log_security_event("APPLICATION_EXIT", "تم إغلاق التطبيق")
            # إلغاء الـ timers قبل الإغلاق
            if self._session_timer:
                self.root.after_cancel(self._session_timer)
            if self._clipboard_timer:
                self.root.after_cancel(self._clipboard_timer)
            try:
                self.root.destroy()
            except Exception:
                pass
            import os
            os._exit(0)

"""

"""
import time
import secrets
import threading
import shutil
from pathlib import Path
from typing import Dict

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from constants import C, FONT_MAIN, FONT_BOLD, FONT_TITLE, FONT_MONO, FONT_SMALL, VERSION
import i18n as _i18n
from i18n import get_text, set_language
from exceptions import AuthError, LockedError, VaultError
from crypto import encrypt_vault, decrypt_vault
from storage import atomic_write
from password_utils import gen_password, pw_strength, validate_master_pw
from ui_widgets import styled_btn


# ════════════════════════════════════════════════════════════
class LoginWindow:
    def __init__(self, vault_path: Path, locker, on_success):
        self.vault_path = vault_path
        self.locker = locker
        self.on_success = on_success

        self.win = tk.Toplevel()
        self.win.title(get_text("login_title"))
        self.win.resizable(False, False)
        self.win.configure(bg=C["bg"])
        try:
            self.win.attributes('-rtl', True)
        except Exception:
            pass
        self.win.grab_set()
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"420x580+{(sw - 420) // 2}+{(sh - 580) // 2}")
        self._build()

    def _build(self):
        tk.Frame(self.win, bg=C["accent"], height=4).pack(fill=tk.X)
        body = tk.Frame(self.win, bg=C["bg"], padx=40, pady=30)
        body.pack(fill=tk.BOTH, expand=True)

        # العنوان
        tk.Label(body, text=get_text("app_title"), font=("Consolas", 22, "bold"),
                 bg=C["bg"], fg=C["accent"]).pack()
        tk.Label(body, text=get_text("secure_password_vault"), font=FONT_MAIN,
                 bg=C["bg"], fg=C["text_dim"]).pack(pady=(0, 20))

        # حالة الخزنة
        exists = self.vault_path.exists()
        self.status_lbl = tk.Label(
            body,
            text=get_text("vault_exists") if exists else get_text("no_vault"),
            font=FONT_SMALL, bg=C["bg"],
            fg=C["accent2"] if exists else C["warning"]
        )
        self.status_lbl.pack(pady=(0, 16))

        pw_frame = tk.Frame(body, bg=C["bg3"], highlightthickness=1,
                            highlightbackground=C["border"], highlightcolor=C["accent"])
        pw_frame.pack(fill=tk.X, pady=4)
        self.pw_entry = tk.Entry(
            pw_frame, show="●", font=FONT_MONO,
            bg=C["bg3"], fg=C["text_bright"],
            insertbackground=C["accent"], relief="flat", bd=8,
            justify="right" if _i18n.current_language == "ar" else "left"
        )
        self.pw_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(pw_frame, text="👁", bg=C["bg3"], fg=C["text_dim"],
                  relief="flat", bd=0, command=self._toggle_pw,
                  cursor="hand2").pack(side=tk.RIGHT, padx=4)
        self.pw_entry.bind("<Return>", lambda e: self._login())

        self.err_lbl = tk.Label(body, text="", font=FONT_SMALL, bg=C["bg"], fg=C["danger"])
        self.err_lbl.pack(pady=4)

        btn_frame = tk.Frame(body, bg=C["bg"])
        btn_frame.pack(fill=tk.X, pady=8)

        self.login_btn = styled_btn(btn_frame, get_text("unlock_vault"), self._login, C["accent"], width=20)
        self.login_btn.pack(fill=tk.X, pady=3)
        styled_btn(btn_frame, get_text("create_new_vault"), self._create_new, C["bg3"], width=20).pack(fill=tk.X, pady=3)
        styled_btn(btn_frame, get_text("open_existing_vault"), self._open_existing, C["bg3"], width=20).pack(fill=tk.X, pady=3)

        self._build_settings(body)

        try:
            self.locker.check()
        except LockedError as e:
            self._set_err(str(e))
            self.login_btn.config(state="disabled")

        self.pw_entry.focus()

    def _build_settings(self, body):
        import constants as _c

        settings_container = tk.Frame(body, bg=C["bg"])
        settings_container.pack(fill=tk.X, pady=(20, 0))

        title_frame = tk.Frame(settings_container, bg=C["bg"])
        title_frame.pack(fill=tk.X)
        tk.Label(title_frame, text=f"  {get_text('login_settings')}  ",
                 font=FONT_SMALL, bg=C["bg"], fg=C["text_dim"]).pack(side=tk.LEFT, pady=(0, 4))
        scroll_hint_text = "اسحب للأسفل للمزيد ⬇️" if _i18n.current_language == "ar" else "Scroll down for more ⬇️"
        tk.Label(title_frame, text=scroll_hint_text, font=FONT_SMALL, bg=C["bg"],
                 fg=C["accent2"]).pack(side=tk.RIGHT, pady=(0, 4))

        visible_frame = tk.Frame(settings_container, bg=C["bg3"], bd=1, relief="solid",
                                 highlightbackground=C["border"], highlightthickness=1)
        visible_frame.pack(fill=tk.X, pady=(0, 8))

        canvas = tk.Canvas(visible_frame, bg=C["bg3"], highlightthickness=0, height=100)
        scrollbar = ttk.Scrollbar(visible_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=C["bg3"])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # اللغة
        lang_row = tk.Frame(scrollable_frame, bg=C["bg"])
        lang_row.pack(fill=tk.X, padx=16, pady=8)
        tk.Label(lang_row, text=get_text("language"), font=FONT_MAIN,
                 bg=C["bg"], fg=C["text"]).pack(side=tk.RIGHT if _i18n.current_language == "ar" else tk.LEFT)
        self.language_var = tk.StringVar(value=_i18n.current_language)
        lang_menu = ttk.Combobox(lang_row, textvariable=self.language_var,
                                 state="readonly", values=("ar", "en"), width=8)
        lang_menu.pack(side=tk.LEFT if _i18n.current_language == "ar" else tk.RIGHT)
        lang_menu.bind("<<ComboboxSelected>>",
                       lambda e: self._change_language_and_rebuild(self.language_var.get()))

        theme_row = tk.Frame(scrollable_frame, bg=C["bg"])
        theme_row.pack(fill=tk.X, padx=16, pady=8)
        tk.Label(theme_row, text=get_text("theme"), font=FONT_MAIN,
                 bg=C["bg"], fg=C["text"]).pack(side=tk.RIGHT if _i18n.current_language == "ar" else tk.LEFT)
        self.theme_var = tk.StringVar(value="dark")
        theme_menu = ttk.Combobox(theme_row, textvariable=self.theme_var,
                                  state="readonly", values=("dark", "light"), width=8)
        theme_menu.pack(side=tk.LEFT if _i18n.current_language == "ar" else tk.RIGHT)
        theme_menu.bind("<<ComboboxSelected>>",
                        lambda e: self._apply_theme(self.theme_var.get()))

        session_row = tk.Frame(scrollable_frame, bg=C["bg"])
        session_row.pack(fill=tk.X, padx=16, pady=8)
        tk.Label(session_row, text=get_text("session_duration"), font=FONT_MAIN,
                 bg=C["bg"], fg=C["text"]).pack(side=tk.RIGHT if _i18n.current_language == "ar" else tk.LEFT)
        self.session_var = tk.StringVar(value="15")
        session_menu = ttk.Combobox(session_row, textvariable=self.session_var,
                                    state="readonly", values=("5", "10", "15", "30", "60"), width=8)
        session_menu.pack(side=tk.LEFT if _i18n.current_language == "ar" else tk.RIGHT)

        def on_session_change(event=None):
            try:
                _c.SESSION_TIMEOUT = int(self.session_var.get()) * 60
            except ValueError:
                pass

        session_menu.bind("<<ComboboxSelected>>", on_session_change)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    def _on_close(self):
        import os
        self.win.destroy()
        os._exit(0)

    def _toggle_pw(self):
        cur = self.pw_entry.cget("show")
        self.pw_entry.config(show="" if cur else "●")

    def _set_err(self, msg):
        self.err_lbl.config(text=msg)

    def _change_language_and_rebuild(self, lang):
        from i18n import set_language
        set_language(lang)
        self._save_settings(lang=lang)
        self.win.destroy()
        self.__init__(self.vault_path, self.locker, self.on_success)

    def _apply_theme(self, theme):
        from theme import apply_theme
        apply_theme(theme)
        self._save_settings(theme=theme)
        self.win.destroy()
        self.__init__(self.vault_path, self.locker, self.on_success)

    def _save_settings(self, lang=None, theme=None):
        try:
            import json
            sf = Path("vault_settings.json")
            settings = json.loads(sf.read_text()) if sf.exists() else {}
            if lang:    settings['language'] = lang
            if theme:   settings['theme'] = theme
            with open(sf, 'w') as f:
                json.dump(settings, f)
        except Exception:
            pass

    def _login(self):
        pw = self.pw_entry.get()
        if not pw:
            self._set_err("أدخل كلمة المرور")
            return
        if not self.vault_path.exists():
            self._set_err("الخزنة غير موجودة — أنشئ واحدة أولاً")
            return

        self.login_btn.config(state="disabled", text="⏳ جارٍ الفتح...")
        self.win.update()

        def do():
            try:
                self.locker.check()

                from storage import SecureFileManager as _SFM
                _tmp_fm = _SFM(self.vault_path)
                is_valid, integrity_info = _tmp_fm.verify_integrity(self.vault_path)
                # إذا لم يوجد سجل integrity بعد نعتبره سليماً (خزنة جديدة أو مستوردة)
                if not is_valid and "checksum غير متطابق" in str(integrity_info):
                    self.win.after(0, lambda: self._set_err(f"الملف تالف: {integrity_info}"))
                    self.win.after(0, lambda: self.login_btn.config(state="normal", text="🔓 فتح الخزنة"))
                    return

                vault = decrypt_vault(pw, self.vault_path.read_bytes())
                self.locker.success()
                self.win.after(0, lambda: self._success(pw, vault))
            except LockedError as e:
                self.win.after(0, lambda: self._set_err(str(e)))
                self.win.after(0, lambda: self.login_btn.config(state="disabled", text="🔒 مقفلة"))
            except AuthError:
                try:
                    rem = self.locker.fail()
                    msg = f"كلمة المرور خاطئة — متبقٍ: {rem} محاولة"
                except LockedError as le:
                    msg = str(le)
                self.win.after(0, lambda: self._set_err(msg))
                self.win.after(0, lambda: self.login_btn.config(state="normal", text="🔓 فتح الخزنة"))
            except Exception as e:
                self.win.after(0, lambda: self._set_err(f"خطأ: {e}"))
                self.win.after(0, lambda: self.login_btn.config(state="normal", text="🔓 فتح الخزنة"))

        threading.Thread(target=do, daemon=True).start()

    def _success(self, pw, vault):
        self.win.destroy()
        self.on_success(pw, vault, self.vault_path)

    def _create_new(self):
        dest = filedialog.asksaveasfilename(
            title=get_text("save_new_vault"),
            defaultextension=".dat",
            filetypes=[("Vault Files", "*.dat"), ("All Files", "*.*")],
            initialfile="vault.dat",
        )
        if dest:
            CreateVaultDialog(Path(dest), self.locker, self.on_success)

    def _open_existing(self):
        dest = filedialog.askopenfilename(
            title=get_text("open_existing_vault"),
            filetypes=[("Vault Files", "*.dat"), ("All Files", "*.*")],
        )
        if dest:
            self.vault_path = Path(dest)
            self.status_lbl.config(text=get_text("vault_exists"), fg=C["accent2"])
            self.pw_entry.focus()
            self.pw_entry.delete(0, tk.END)


# ════════════════════════════════════════════════════════════
#  نافذة إنشاء خزنة جديدة
# ════════════════════════════════════════════════════════════
class CreateVaultDialog:
    def __init__(self, vault_path: Path, locker, on_success):
        self.vault_path = vault_path
        self.locker = locker
        self.on_success = on_success

        self.win = tk.Toplevel()
        self.win.title("إنشاء خزنة جديدة")
        self.win.resizable(False, False)
        self.win.configure(bg=C["bg"])
        try:
            self.win.attributes('-rtl', True)
        except Exception:
            pass
        self.win.grab_set()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"420x480+{(sw - 420) // 2}+{(sh - 480) // 2}")
        self._build()

    def _build(self):
        tk.Frame(self.win, bg=C["accent2"], height=4).pack(fill=tk.X)
        body = tk.Frame(self.win, bg=C["bg"], padx=40, pady=30)
        body.pack(fill=tk.BOTH, expand=True)

        tk.Label(body, text="✨ خزنة جديدة", font=FONT_TITLE,
                 bg=C["bg"], fg=C["text_bright"]).pack(pady=(0, 20))

        for label, attr in [("كلمة المرور الرئيسية", "pw1"), ("تأكيد كلمة المرور", "pw2")]:
            tk.Label(body, text=label, font=FONT_SMALL, bg=C["bg"],
                     fg=C["text_dim"], anchor="w").pack(fill=tk.X)
            f = tk.Frame(body, bg=C["bg3"], highlightthickness=1,
                         highlightbackground=C["border"])
            f.pack(fill=tk.X, pady=(2, 10))
            e = tk.Entry(f, show="●", font=FONT_MONO, bg=C["bg3"],
                         fg=C["text_bright"], insertbackground=C["accent"],
                         relief="flat", bd=8)
            e.pack(fill=tk.X)
            setattr(self, attr, e)
            if attr == "pw1":
                e.bind("<KeyRelease>", self._check_strength)

        self.str_bar = tk.Canvas(body, height=6, bg=C["border"], highlightthickness=0)
        self.str_bar.pack(fill=tk.X, pady=(0, 4))
        self.str_lbl = tk.Label(body, text="", font=FONT_SMALL, bg=C["bg"], fg=C["text_dim"])
        self.str_lbl.pack(anchor="w")

        self.err_lbl = tk.Label(body, text="", font=FONT_SMALL, bg=C["bg"], fg=C["danger"])
        self.err_lbl.pack(pady=4)

        styled_btn(body, "🏗️ إنشاء الخزنة", self._create, C["accent2"]).pack(fill=tk.X, pady=8)
        self.pw1.focus()

    def _check_strength(self, event=None):
        pw = self.pw1.get()
        if not pw:
            self.str_bar.delete("all")
            self.str_lbl.config(text="")
            return
        score, label, color = pw_strength(pw)
        w = self.str_bar.winfo_width() or 340
        self.str_bar.delete("all")
        self.str_bar.create_rectangle(0, 0, int(w * score / 100), 6, fill=color, outline="")
        self.str_lbl.config(text=f"القوة: {label} ({score}%)", fg=color)

    def _create(self):
        pw1, pw2 = self.pw1.get(), self.pw2.get()
        if pw1 != pw2:
            self.err_lbl.config(text="كلمتا المرور غير متطابقتين")
            return
        ok, msg = validate_master_pw(pw1)
        if not ok:
            self.err_lbl.config(text=msg)
            return
        if self.vault_path.exists():
            if not messagebox.askyesno("تأكيد", "خزنة موجودة! هل تريد استبدالها؟"):
                return
            shutil.copy2(self.vault_path, self.vault_path.with_suffix(".dat.bak"))

        payload = {"accounts": [], "created_at": int(time.time()), "version": VERSION}
        try:
            blob = encrypt_vault(pw1, payload)
            atomic_write(self.vault_path, blob)
            self.locker.reset()
            messagebox.showinfo("✅ تم", f"تم إنشاء الخزنة: {self.vault_path}")
            self.win.destroy()
            self.on_success(pw1, payload)
        except Exception as e:
            self.err_lbl.config(text=f"خطأ: {e}")


# ════════════════════════════════════════════════════════════

class AccountDialog:
    def __init__(self, parent, account: Dict = None, on_save=None):
        self.editing = account
        self.on_save = on_save

        self.win = tk.Toplevel(parent)
        self.win.title(
            get_text("edit_account") if account else get_text("add_account_title")
        )
        self.win.resizable(False, False)
        self.win.configure(bg=C["bg"])
        try:
            self.win.attributes('-rtl', _i18n.current_language == "ar")
        except Exception:
            pass
        self.win.grab_set()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"460x540+{(sw - 460) // 2}+{(sh - 540) // 2}")
        self._build()

    def _build(self):
        title = self.editing["name"] if self.editing else ("➕ حساب جديد" if _i18n.current_language == "ar" else "➕ New Account")
        tk.Frame(self.win, bg=C["accent2"], height=4).pack(fill=tk.X)
        body = tk.Frame(self.win, bg=C["bg"], padx=30, pady=20)
        body.pack(fill=tk.BOTH, expand=True)
        tk.Label(body, text=title, font=FONT_TITLE, bg=C["bg"],
                 fg=C["text_bright"]).pack(pady=(0, 16))

        self.fields = {}
        field_defs = [
            (get_text("account_name_label"), "name"),
            (get_text("username_label"), "username"),
            ("🌐 URL:", "url"),
            (get_text("notes_label"), "notes"),
        ]
        for label, key in field_defs:
            tk.Label(body, text=label, font=FONT_SMALL, bg=C["bg"],
                     fg=C["text_dim"], anchor="e" if _i18n.current_language == "ar" else "w").pack(fill=tk.X)
            f = tk.Frame(body, bg=C["bg3"], highlightthickness=1, highlightbackground=C["border"])
            f.pack(fill=tk.X, pady=(2, 8))
            e = tk.Entry(f, font=FONT_MONO, bg=C["bg3"], fg=C["text_bright"],
                         insertbackground=C["accent"], relief="flat", bd=6,
                         justify="right" if _i18n.current_language == "ar" else "left")
            e.pack(fill=tk.X)
            if self.editing:
                e.insert(0, self.editing.get(key, ""))
            self.fields[key] = e

        tk.Label(body, text=get_text("password_label"), font=FONT_SMALL, bg=C["bg"],
                 fg=C["text_dim"], anchor="e" if _i18n.current_language == "ar" else "w").pack(fill=tk.X)
        pw_frame = tk.Frame(body, bg=C["bg3"], highlightthickness=1, highlightbackground=C["border"])
        pw_frame.pack(fill=tk.X, pady=(2, 4))

        self.pw_entry = tk.Entry(pw_frame, show="●", font=FONT_MONO, bg=C["bg3"],
                                 fg=C["text_bright"], insertbackground=C["accent"],
                                 relief="flat", bd=6,
                                 justify="right" if _i18n.current_language == "ar" else "left")
        self.pw_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        if self.editing:
            self.pw_entry.insert(0, self.editing.get("password", ""))

        tk.Button(pw_frame, text="👁", bg=C["bg3"], fg=C["text_dim"],
                  relief="flat", bd=0, cursor="hand2",
                  command=self._toggle_pw).pack(side=tk.RIGHT, padx=2)
        styled_btn(pw_frame, get_text("generate_password"),
                   self._gen_pw, C["accent2"], small=True).pack(side=tk.RIGHT, padx=2)

        self.str_canvas = tk.Canvas(body, height=4, bg=C["border"], highlightthickness=0)
        self.str_canvas.pack(fill=tk.X, pady=(0, 8))
        self.pw_entry.bind("<KeyRelease>", self._update_strength)

        self.err_lbl = tk.Label(body, text="", font=FONT_SMALL, bg=C["bg"], fg=C["danger"])
        self.err_lbl.pack()

        btn_row = tk.Frame(body, bg=C["bg"])
        btn_row.pack(fill=tk.X, pady=8)
        styled_btn(btn_row, get_text("save"), self._save, C["accent2"]).pack(side=tk.RIGHT, padx=4)
        styled_btn(btn_row, get_text("cancel"), self.win.destroy, C["bg3"]).pack(side=tk.RIGHT, padx=4)

        self.fields["name"].focus()

    def _on_close(self):
        import os
        self.win.destroy()
        os._exit(0)

    def _toggle_pw(self):
        self.pw_entry.config(show="" if self.pw_entry.cget("show") else "●")

    def _gen_pw(self):
        pw = gen_password()
        self.pw_entry.delete(0, tk.END)
        self.pw_entry.insert(0, pw)
        self._update_strength()

    def _update_strength(self, event=None):
        pw = self.pw_entry.get()
        if not pw:
            self.str_canvas.delete("all")
            return
        score, _, color = pw_strength(pw)
        w = self.str_canvas.winfo_width() or 340
        self.str_canvas.delete("all")
        self.str_canvas.create_rectangle(0, 0, int(w * score / 100), 4, fill=color, outline="")

    def _save(self):
        name = self.fields["name"].get().strip()
        user = self.fields["username"].get().strip()
        pw   = self.pw_entry.get()

        if not name: self.err_lbl.config(text="اسم الحساب مطلوب" if _i18n.current_language == "ar" else "Account name required"); return
        if not user: self.err_lbl.config(text="اسم المستخدم مطلوب" if _i18n.current_language == "ar" else "Username required"); return
        if not pw:   self.err_lbl.config(text="كلمة المرور مطلوبة" if _i18n.current_language == "ar" else "Password required"); return

        account = {
            "id":            self.editing["id"] if self.editing else secrets.token_hex(8),
            "name":          name,
            "username":      user,
            "password":      pw,
            "url":           self.fields["url"].get().strip(),
            "notes":         self.fields["notes"].get().strip(),
            "created_at":    self.editing["created_at"] if self.editing else int(time.time()),
            "last_modified": int(time.time()),
        }
        if self.on_save:
            self.on_save(account)
        self.win.destroy()


# ════════════════════════════════════════════════════════════

class AccountDetailDialog:
    def __init__(self, parent, account: Dict, on_edit=None, on_delete=None):
        self.account = account
        self.win = tk.Toplevel(parent)
        self.win.title(f"🔑 {account['name']}")
        self.win.resizable(False, False)
        self.win.configure(bg=C["bg"])
        try:
            self.win.attributes('-rtl', _i18n.current_language == "ar")
        except Exception:
            pass
        self.win.grab_set()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"460x420+{(sw - 460) // 2}+{(sh - 420) // 2}")
        self._build(on_edit, on_delete)

    def _build(self, on_edit, on_delete):
        tk.Frame(self.win, bg=C["accent"], height=4).pack(fill=tk.X)
        body = tk.Frame(self.win, bg=C["bg"], padx=30, pady=20)
        body.pack(fill=tk.BOTH, expand=True)
        tk.Label(body, text=f"🔑 {self.account['name']}", font=FONT_TITLE,
                 bg=C["bg"], fg=C["text_bright"]).pack(pady=(0, 16))

        pw_visible = [False]
        is_ar = _i18n.current_language == "ar"
        label_anchor = "e" if is_ar else "w"

        fields = [
            (get_text("account_name"), self.account.get("name", ""),         False),
            (get_text("username"),     self.account.get("username", ""),      False),
            (get_text("password"),     self.account.get("password", ""),      True),
            (get_text("url"),          self.account.get("url", "") or "—",    False),
            (get_text("notes"),        self.account.get("notes", "") or "—",  False),
            (get_text("created"),      time.ctime(self.account.get("created_at", 0)), False),
        ]

        for label, value, is_pw in fields:
            row = tk.Frame(body, bg=C["panel"], pady=6, padx=12)
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=label, font=FONT_SMALL, bg=C["panel"],
                     fg=C["text_dim"], width=12, anchor=label_anchor).pack(side=tk.LEFT)

            display = "●●●●●●●●●●" if is_pw else value
            val_lbl = tk.Label(row, text=display, font=FONT_MONO, bg=C["panel"],
                               fg=C["accent2"] if is_pw else C["text_bright"], anchor="w")
            val_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)

            def make_copy(v=value):
                styled_btn(row, "📋", lambda: self._copy(v), C["panel"], small=True).pack(side=tk.RIGHT, padx=2)
            make_copy()

            if is_pw:
                def toggle(lbl=val_lbl, v=value, vis=pw_visible):
                    vis[0] = not vis[0]
                    lbl.config(
                        text=v if vis[0] else "●●●●●●●●●●",
                        fg=C["text_bright"] if vis[0] else C["accent2"]
                    )
                styled_btn(row, "👁", toggle, C["panel"], small=True).pack(side=tk.RIGHT, padx=2)

        btn_frame = tk.Frame(body, bg=C["bg"])
        btn_frame.pack(fill=tk.X, pady=12)
        styled_btn(btn_frame, "🗑 " + ("حذف" if is_ar else "Delete"),
                   lambda: self._delete(on_delete), C["danger"]).pack(side=tk.LEFT)
        styled_btn(btn_frame, "✏️ " + ("تعديل" if is_ar else "Edit"),
                   lambda: self._edit(on_edit), C["warning"]).pack(side=tk.LEFT, padx=8)
        styled_btn(btn_frame, get_text("close"), self.win.destroy, C["bg3"]).pack(side=tk.RIGHT)

    def _copy(self, text):
        self.win.clipboard_clear()
        self.win.clipboard_append(text)
        self.win.after(1500, self.win.clipboard_clear)

    def _edit(self, on_edit):
        self.win.destroy()
        if on_edit:
            on_edit(self.account)

    def _delete(self, on_delete):
        if messagebox.askyesno(
            get_text("delete_account_confirm"),
            get_text("delete_account_msg").format(name=self.account['name'])
        ):
            self.win.destroy()
            if on_delete:
                on_delete(self.account["id"])


# ════════════════════════════════════════════════════════════
class GeneratorWindow:
    def __init__(self, parent):
        self.win = tk.Toplevel(parent)
        self.win.title(get_text("password_generator"))
        self.win.resizable(False, False)
        self.win.configure(bg=C["bg"])
        try:
            self.win.attributes('-rtl', _i18n.current_language == "ar")
        except Exception:
            pass
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"480x560+{(sw - 480) // 2}+{(sh - 560) // 2}")
        self._build()

    def _build(self):
        is_ar = _i18n.current_language == "ar"
        tk.Frame(self.win, bg=C["accent2"], height=4).pack(fill=tk.X)
        body = tk.Frame(self.win, bg=C["bg"], padx=30, pady=20)
        body.pack(fill=tk.BOTH, expand=True)
        tk.Label(body, text=get_text("password_generator"), font=FONT_TITLE,
                 bg=C["bg"], fg=C["text_bright"]).pack(pady=(0, 20))

        out_frame = tk.Frame(body, bg=C["bg3"], highlightthickness=1,
                             highlightbackground=C["accent2"])
        out_frame.pack(fill=tk.X, pady=(0, 12))
        self.result_var = tk.StringVar(
            value="اضغط توليد ⚡" if is_ar else "Press Generate ⚡"
        )
        tk.Label(out_frame, textvariable=self.result_var, font=("Consolas", 14),
                 bg=C["bg3"], fg=C["accent2"], pady=14).pack(fill=tk.X)

        self.str_canvas = tk.Canvas(body, height=6, bg=C["border"], highlightthickness=0)
        self.str_canvas.pack(fill=tk.X, pady=(0, 4))
        self.str_lbl = tk.Label(body, text="", font=FONT_SMALL, bg=C["bg"], fg=C["text_dim"])
        self.str_lbl.pack(anchor="e" if is_ar else "w", pady=(0, 12))

        len_frame = tk.Frame(body, bg=C["bg"])
        len_frame.pack(fill=tk.X, pady=4)
        self.len_var = tk.IntVar(value=20)
        self.len_lbl = tk.Label(len_frame, text="20", font=FONT_MONO, bg=C["bg"],
                                fg=C["accent"], width=4)

        lbl_side = tk.RIGHT if is_ar else tk.LEFT
        num_side = tk.LEFT if is_ar else tk.RIGHT
        tk.Label(len_frame, text=get_text("length"), font=FONT_BOLD,
                 bg=C["bg"], fg=C["text_bright"]).pack(side=lbl_side)
        self.len_lbl.pack(side=num_side)
        tk.Scale(len_frame, from_=8, to=64, variable=self.len_var, orient=tk.HORIZONTAL,
                 bg=C["bg"], fg=C["text_bright"], troughcolor=C["bg3"], highlightthickness=0,
                 command=lambda v: self.len_lbl.config(text=str(int(float(v))))).pack(
            side=lbl_side, fill=tk.X, expand=True, padx=8
        )

        opts_label = "  الخيارات  " if is_ar else f"  {get_text('options')}  "
        opts_frame = tk.LabelFrame(body, text=opts_label, font=FONT_SMALL,
                                   bg=C["bg"], fg=C["text_dim"], bd=1, relief="flat",
                                   highlightthickness=1, highlightbackground=C["border"])
        opts_frame.pack(fill=tk.X, pady=12)

        self.upper_v   = tk.BooleanVar(value=True)
        self.lower_v   = tk.BooleanVar(value=True)
        self.digits_v  = tk.BooleanVar(value=True)
        self.symbols_v = tk.BooleanVar(value=True)

        options = [
            (get_text("include_uppercase"), self.upper_v),
            (get_text("include_lowercase"), self.lower_v),
            (get_text("include_numbers"),   self.digits_v),
            (get_text("include_symbols"),   self.symbols_v),
        ]
        for text, var in options:
            tk.Checkbutton(opts_frame, text=text, variable=var, bg=C["bg"],
                           fg=C["text"], activebackground=C["bg"],
                           selectcolor=C["bg3"], font=FONT_MAIN).pack(
                anchor=tk.E if is_ar else tk.W, padx=12, pady=2
            )

        # أزرار
        btn_frame = tk.Frame(body, bg=C["bg"])
        btn_frame.pack(fill=tk.X, pady=8)
        b_side1 = tk.RIGHT if is_ar else tk.LEFT
        b_side2 = tk.RIGHT if is_ar else tk.LEFT
        styled_btn(btn_frame, get_text("generate"), self._generate, C["accent2"]).pack(side=b_side1, padx=4)
        styled_btn(btn_frame, get_text("copy"), self._copy, C["accent"]).pack(side=b_side2, padx=4)

        multi_label = "توليد متعدد:" if is_ar else get_text("generated_passwords")
        tk.Label(body, text=multi_label, font=FONT_SMALL, bg=C["bg"],
                 fg=C["text_dim"]).pack(anchor="e" if is_ar else "w", pady=(8, 4))
        self.multi_frame = tk.Frame(body, bg=C["bg"])
        self.multi_frame.pack(fill=tk.X)
        multi_btn_text = "توليد 5 كلمات" if is_ar else "Generate 5 passwords"
        styled_btn(body, multi_btn_text, self._gen_multi, C["bg3"]).pack(
            anchor="e" if is_ar else "w", pady=4
        )
        self._generate()

    def _generate(self):
        pw = gen_password(
            self.len_var.get(),
            self.upper_v.get(), self.lower_v.get(),
            self.digits_v.get(), self.symbols_v.get()
        )
        if not pw:
            messagebox.showwarning("تنبيه", "اختر نوعاً واحداً على الأقل")
            return
        self.result_var.set(pw)
        s, lbl, color = pw_strength(pw)
        w = self.str_canvas.winfo_width() or 420
        self.str_canvas.delete("all")
        self.str_canvas.create_rectangle(0, 0, int(w * s / 100), 6, fill=color, outline="")
        strength_text = f"القوة: {lbl} ({s}%)" if _i18n.current_language == "ar" else f"Strength: {lbl} ({s}%)"
        self.str_lbl.config(text=strength_text, fg=color)

    def _copy(self):
        pw = self.result_var.get()
        placeholder = "اضغط توليد ⚡" if _i18n.current_language == "ar" else "Press Generate ⚡"
        if pw and pw != placeholder:
            self.win.clipboard_clear()
            self.win.clipboard_append(pw)
            copy_text = "✅ تم النسخ!" if _i18n.current_language == "ar" else "✅ Copied!"
            self.str_lbl.config(text=copy_text, fg=C["accent2"])
            self.win.after(1500, self._generate)

    def _gen_multi(self):
        for w in self.multi_frame.winfo_children():
            w.destroy()
        is_ar = _i18n.current_language == "ar"
        for _ in range(5):
            pw = gen_password(
                self.len_var.get(),
                self.upper_v.get(), self.lower_v.get(),
                self.digits_v.get(), self.symbols_v.get()
            )
            row = tk.Frame(self.multi_frame, bg=C["panel"])
            row.pack(fill=tk.X, pady=1)
            anchor_side = tk.RIGHT if is_ar else tk.LEFT
            lbl_side    = tk.RIGHT if is_ar else tk.LEFT
            btn_side    = tk.LEFT  if is_ar else tk.RIGHT
            tk.Label(row, text=pw, font=("Consolas", 9), bg=C["panel"],
                     fg=C["accent2"], anchor="e" if is_ar else "w").pack(
                side=lbl_side, padx=8, pady=4, fill=tk.X, expand=True
            )
            def make_copy(p=pw):
                return lambda: [self.win.clipboard_clear(), self.win.clipboard_append(p)]
            styled_btn(row, "📋", make_copy(), C["panel"], small=True).pack(side=btn_side, padx=4)

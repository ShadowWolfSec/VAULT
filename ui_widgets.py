"""

"""
import tkinter as tk
from tkinter import ttk

from constants import C, FONT_BOLD, FONT_SMALL, FONT_MONO


def styled_btn(parent, text: str, command, color=None, width=None, small: bool = False):
    bg = color or C["btn_bg"]
    font = FONT_SMALL if small else FONT_BOLD
    b = tk.Button(
        parent, text=text, command=command,
        bg=bg, fg=C["text_bright"], font=font,
        relief="flat", bd=0, padx=12,
        pady=4 if small else 6,
        activebackground=C["btn_hover"],
        activeforeground=C["text_bright"],
        cursor="hand2"
    )
    if width:
        b.config(width=width)
    return b


def styled_entry(parent, show=None, font=None, width=None):
    e = tk.Entry(
        parent,
        bg=C["entry_bg"], fg=C["text_bright"],
        font=font or FONT_MONO,
        insertbackground=C["accent"],
        relief="flat", bd=0,
        highlightthickness=1,
        highlightcolor=C["accent"],
        highlightbackground=C["border"]
    )
    if show:
        e.config(show=show)
    if width:
        e.config(width=width)
    return e


def section_label(parent, text: str):
    return tk.Label(
        parent, text=text, font=FONT_BOLD,
        bg=C["bg2"], fg=C["text_dim"], anchor="w"
    )


def divider(parent):
    return tk.Frame(parent, bg=C["border"], height=1)


def apply_treeview_style():
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        style.theme_use("default")

    style.configure(
        "Dark.Treeview",
        background=C["bg2"], foreground=C["text"],
        fieldbackground=C["bg2"], borderwidth=0,
        rowheight=36, font=("Segoe UI", 10)
    )
    style.configure(
        "Dark.Treeview.Heading",
        background=C["bg3"], foreground=C["text_dim"],
        font=("Segoe UI", 10, "bold"), borderwidth=0, relief="flat"
    )
    style.map(
        "Dark.Treeview",
        background=[("selected", C["select"])],
        foreground=[("selected", C["text_bright"])]
    )

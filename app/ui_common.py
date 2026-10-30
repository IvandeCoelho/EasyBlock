"""Tema, dialogos e utilidades de interface do Bloqueador."""
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

PALETTES = {
    "claro": {"bg": "#f0f0f0", "fg": "#1a1a1a", "muted": "#555555", "field": "#ffffff",
              "ok": "#2a6f2a", "err": "#b03030", "link": "#0a58ca", "warn": "#b35c00",
              "sel": "#0078d4", "btn": "#e1e1e1", "border": "#c8c8c8"},
    "escuro": {"bg": "#1e1f22", "fg": "#e6e6e6", "muted": "#a0a0a0", "field": "#2b2d31",
               "ok": "#6fcf8a", "err": "#ff7b72", "link": "#6cb6ff", "warn": "#e3b341",
               "sel": "#3b6ea8", "btn": "#32343a", "border": "#3a3c40"},
}
CUR = {"name": "claro", "size": 10}
REVERSE = {col.lower(): tone for pal in PALETTES.values() for tone, col in pal.items()}


def C(tone: str) -> str:
    """Cor do tema atual (bg, fg, muted, field, ok, err, link, warn, sel, btn, border)."""
    return PALETTES[CUR["name"]][tone]


def apply_theme(root, name: str, size: int):
    CUR["name"], CUR["size"] = name, size
    pal = PALETTES[name]
    for fname in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont",
                  "TkCaptionFont", "TkTooltipFont"):
        try:
            tkfont.nametofont(fname).configure(size=size)
        except tk.TclError:
            pass
    s = ttk.Style(root)
    try:
        s.theme_use("clam")
    except tk.TclError:
        pass
    bg, fg, field, btn, border, sel, muted = (pal[k] for k in ("bg", "fg", "field", "btn", "border", "sel", "muted"))
    s.configure(".", background=bg, foreground=fg, fieldbackground=field, bordercolor=border,
                lightcolor=bg, darkcolor=bg, troughcolor=field, selectbackground=sel,
                selectforeground="#ffffff", insertcolor=fg, focuscolor=sel)
    s.configure("TButton", padding=(14, 8), background=btn, foreground=fg, bordercolor=border)
    s.map("TButton", background=[("pressed", sel), ("active", border), ("disabled", bg)],
          foreground=[("disabled", muted)])
    s.configure("TMenubutton", padding=(14, 8), background=btn, foreground=fg, bordercolor=border)
    s.map("TMenubutton", background=[("active", border)])
    s.configure("TCheckbutton", background=bg, foreground=fg, indicatorbackground=field,
                indicatorforeground=fg, padding=3)
    s.map("TCheckbutton", background=[("active", bg)], indicatorbackground=[("selected", sel)])
    s.configure("TLabel", background=bg, foreground=fg)
    s.configure("TLabelframe", background=bg, bordercolor=border)
    s.configure("TLabelframe.Label", background=bg, foreground=fg)
    s.configure("TEntry", fieldbackground=field, foreground=fg, insertcolor=fg, padding=5)
    s.configure("TSpinbox", fieldbackground=field, foreground=fg, arrowcolor=fg, padding=5)
    s.configure("TCombobox", fieldbackground=field, background=btn, foreground=fg,
                arrowcolor=fg, padding=5)
    s.map("TCombobox", fieldbackground=[("readonly", field)], foreground=[("readonly", fg)],
          selectbackground=[("readonly", field)], selectforeground=[("readonly", fg)])
    s.configure("Treeview", background=field, fieldbackground=field, foreground=fg,
                rowheight=int(size * 2.4), bordercolor=border)
    s.map("Treeview", background=[("selected", sel)], foreground=[("selected", "#ffffff")])
    s.configure("Treeview.Heading", background=btn, foreground=fg, padding=6, relief="flat")
    s.map("Treeview.Heading", background=[("active", border)])
    s.configure("TNotebook", background=bg, bordercolor=border)
    s.configure("TNotebook.Tab", background=btn, foreground=fg, padding=(8, 6))
    s.map("TNotebook.Tab", background=[("selected", bg)], foreground=[("selected", fg)])
    s.configure("TScrollbar", background=btn, troughcolor=bg, bordercolor=border, arrowcolor=fg)
    s.configure("Title.TLabel", font=("Segoe UI", size + 10, "bold"))
    s.configure("Bold.TLabel", font=("Segoe UI", size, "bold"))
    root.configure(background=bg)
    for opt, val in (("background", field), ("foreground", fg),
                     ("selectBackground", sel), ("selectForeground", "#ffffff")):
        root.option_add(f"*TCombobox*Listbox.{opt}", val)


def retheme(w):
    """Reaplica as cores do tema nos widgets que nao seguem o estilo ttk."""
    try:
        cls = w.winfo_class()
        if cls in ("Text", "Listbox"):
            w.configure(background=C("field"), foreground=C("fg"), insertbackground=C("fg"),
                        selectbackground=C("sel"), highlightbackground=C("border"),
                        highlightcolor=C("sel"))
        elif cls in ("Toplevel", "Tk"):
            w.configure(background=C("bg"))
        elif cls == "TLabel":
            tone = REVERSE.get(str(w.cget("foreground")).lower())
            if tone:
                w.configure(foreground=C(tone))
    except tk.TclError:
        pass
    for child in w.winfo_children():
        retheme(child)


def make_dialog(parent, title: str):
    """Janela modal simples. Retorna (dialogo, frame interno)."""
    top = parent.winfo_toplevel()
    dlg = tk.Toplevel(top)
    dlg.title(title)
    dlg.transient(top)
    dlg.resizable(False, False)
    dlg.configure(background=C("bg"))
    frm = ttk.Frame(dlg, padding=16)
    frm.pack(fill="both", expand=True)
    return dlg, frm


def show_modal(dlg, parent):
    dlg.update_idletasks()
    top = parent.winfo_toplevel()
    try:
        x = top.winfo_rootx() + max(0, (top.winfo_width() - dlg.winfo_width()) // 2)
        y = top.winfo_rooty() + max(0, (top.winfo_height() - dlg.winfo_height()) // 3)
        dlg.geometry(f"+{x}+{y}")
    except tk.TclError:
        pass
    dlg.grab_set()
    dlg.focus_set()
    dlg.wait_window()


def ask_text(parent, title: str, prompt: str, show: str = "", initial: str = "",
             extra_text: str = "", extra_cmd=None):
    """Pede um texto (ou senha, com show='•'). Retorna a string ou None se cancelar."""
    dlg, frm = make_dialog(parent, title)
    ttk.Label(frm, text=prompt, wraplength=380, justify="left").pack(anchor="w")
    var = tk.StringVar(value=initial)
    ent = ttk.Entry(frm, textvariable=var, show=show, width=42)
    ent.pack(fill="x", pady=12)
    ent.focus_set()
    result = {"v": None}

    def ok(_=None):
        result["v"] = var.get()
        dlg.destroy()

    row = ttk.Frame(frm)
    row.pack(fill="x")
    if extra_text and extra_cmd:
        def extra():
            dlg.destroy()
            extra_cmd()
        ttk.Button(row, text=extra_text, command=extra).pack(side="left")
    ttk.Button(row, text="Cancelar", command=dlg.destroy).pack(side="right")
    ttk.Button(row, text="OK", command=ok).pack(side="right", padx=6)
    dlg.bind("<Return>", ok)
    dlg.bind("<Escape>", lambda e: dlg.destroy())
    show_modal(dlg, parent)
    return result["v"]


def tone_label(parent, text="", tone="muted", **kw):
    return ttk.Label(parent, text=text, foreground=C(tone), **kw)

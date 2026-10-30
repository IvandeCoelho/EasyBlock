"""Abas e dialogos do Bloqueador."""
import csv
import os
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse

import core
from ui_common import (C, CUR, ask_text, make_dialog, show_modal, tone_label)

WRAP = 800
KIND_LABELS = {"app": "Aplicativo", "termo": "Termo (processo)", "janela": "Janela",
               "site": "Site (janela)", "limite": "Limite diário"}


def fmt_minutes(seconds: float) -> str:
    return f"{int(seconds // 60)} min"


# ======================================================================= dialogos
def pick_programs(parent, multi=True) -> list:
    """Lista os programas abertos e devolve os nomes escolhidos."""
    dlg, frm = make_dialog(parent, "Programas em execução")
    dlg.resizable(True, True)
    tone_label(frm, "Abra o programa/jogo, selecione-o aqui e clique em Adicionar.",
               wraplength=560).pack(anchor="w")
    top = ttk.Frame(frm)
    top.pack(fill="x", pady=8)
    only = tk.BooleanVar(value=True)
    q = tk.StringVar()
    data = []
    ttk.Checkbutton(top, text="Só com janela aberta", variable=only,
                    command=lambda: load()).pack(side="left")
    ttk.Entry(top, textvariable=q).pack(side="left", fill="x", expand=True, padx=8)
    ttk.Button(top, text="Atualizar", command=lambda: load()).pack(side="left")

    lf = ttk.Frame(frm)
    lf.pack(fill="both", expand=True)
    tree = ttk.Treeview(lf, columns=("p", "t"), show="headings", height=14,
                        selectmode="extended" if multi else "browse")
    tree.heading("p", text="Programa", anchor="w")
    tree.heading("t", text="Janela", anchor="w")
    tree.column("p", width=200, stretch=False)
    tree.column("t", width=360)
    sb = ttk.Scrollbar(lf, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    result = []

    def render():
        tree.delete(*tree.get_children())
        f = q.get().strip().lower()
        for name, title in data:
            if not f or f in name.lower() or f in title.lower():
                tree.insert("", "end", values=(name, title))

    def load():
        data[:] = core.list_programs(only.get())
        render()

    def add():
        result.extend(str(tree.item(i, "values")[0]) for i in tree.selection())
        dlg.destroy()

    q.trace_add("write", lambda *a: render())
    row = ttk.Frame(frm)
    row.pack(fill="x", pady=(10, 0))
    ttk.Button(row, text="Cancelar", command=dlg.destroy).pack(side="right")
    ttk.Button(row, text="➕ Adicionar selecionados", command=add).pack(side="right", padx=6)
    tree.bind("<Double-1>", lambda e: add())
    load()
    show_modal(dlg, parent)
    return result


def source_dialog(parent, sources, name="", url="", secret="", editing_url=None):
    """Adicionar/editar uma lista online. Retorna dict {name,url,secret} ou None."""
    dlg, frm = make_dialog(parent, "Lista online")
    n, u, s = tk.StringVar(value=name), tk.StringVar(value=url), tk.StringVar(value=secret)
    for i, (label, var, width) in enumerate((("Nome da lista:", n, 52), ("Endereço (https://):", u, 52),
                                             ("Chave secreta (opcional):", s, 52))):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=3)
        ttk.Entry(frm, textvariable=var, width=width).grid(row=i, column=1, pady=3, padx=(10, 0))
    tone_label(frm, "Com chave secreta, o app só aceita a lista se ela terminar com uma linha "
                    "'# hmac: …' gerada com essa mesma chave (use o editor_lista.html). Assim ninguém "
                    "consegue trocar o conteúdo no caminho.", wraplength=520).grid(
        row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
    err = ttk.Label(frm, text="", foreground=C("err"))
    err.grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))
    result = {}

    def ok(_=None):
        uu, nn, ss = u.get().strip(), n.get().strip(), s.get().strip()
        if not uu.lower().startswith("https://") or len(uu) < 12:
            err.config(text="O endereço precisa começar com https://")
            return
        if any(x["url"] == uu and x["url"] != editing_url for x in sources):
            err.config(text="Essa lista já foi adicionada.")
            return
        nn = nn or urlparse(uu).hostname or "Lista online"
        base, i = nn, 2
        while any(x["name"].lower() == nn.lower() and x["url"] != editing_url for x in sources):
            nn, i = f"{base} ({i})", i + 1
        result.update(name=nn, url=uu, secret=ss)
        dlg.destroy()

    row = ttk.Frame(frm)
    row.grid(row=5, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(row, text="Cancelar", command=dlg.destroy).pack(side="right")
    ttk.Button(row, text="Salvar", command=ok).pack(side="right", padx=6)
    dlg.bind("<Return>", ok)
    dlg.bind("<Escape>", lambda e: dlg.destroy())
    show_modal(dlg, parent)
    return result or None


def wizard_dialog(parent) -> list:
    """Assistente de primeira abertura. Retorna as categorias escolhidas."""
    dlg, frm = make_dialog(parent, "Bem-vindo ao EasyBlock")
    ttk.Label(frm, text="Bem-vindo!", style="Title.TLabel").pack(anchor="w")
    tone_label(frm, "O que você quer bloquear? Marque as categorias e eu já carrego as listas prontas. "
                    "Você pode mudar tudo depois.", wraplength=460).pack(anchor="w", pady=(4, 10))
    vars_ = {}
    for cat in core.WIZARD:
        vars_[cat] = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text=cat, variable=vars_[cat]).pack(anchor="w")
    chosen = []

    def apply():
        chosen.extend(c for c, v in vars_.items() if v.get())
        dlg.destroy()

    row = ttk.Frame(frm)
    row.pack(fill="x", pady=(14, 0))
    ttk.Button(row, text="Pular", command=dlg.destroy).pack(side="right")
    ttk.Button(row, text="Aplicar", command=apply).pack(side="right", padx=6)
    show_modal(dlg, parent)
    return chosen


# ===================================================================== lista local
class ListTab(ttk.Frame):
    def __init__(self, parent, app, key, title, hint, example):
        super().__init__(parent, padding=12)
        self.app, self.key, self.title, self.example = app, key, title, example
        self.normalize = core.NORMALIZERS[key]
        self.sort_rev = False

        ttk.Label(self, text=hint, wraplength=WRAP, foreground=C("muted")).pack(anchor="w")
        box = ttk.LabelFrame(self, text=" Adicionar ", padding=8)
        box.pack(fill="x", pady=(10, 8))
        tone_label(box, "Cole um ou vários itens (um por linha, ou separados por vírgula):").pack(anchor="w")
        self.text = tk.Text(box, height=3, wrap="word", relief="solid", borderwidth=1)
        self.text.pack(fill="x", pady=6)
        self.text.bind("<Control-Return>", lambda e: (self.add_from_text(), "break")[1])

        btns = ttk.Frame(box)
        btns.pack(fill="x")
        ttk.Button(btns, text="➕ Adicionar", command=self.add_from_text).pack(side="left")
        ttk.Button(btns, text="📂 Importar arquivo…", command=self.import_file).pack(side="left", padx=6)
        mb = ttk.Menubutton(btns, text="📋 Listas prontas ▾")
        menu = tk.Menu(mb, tearoff=False)
        for name, items in core.PRESETS[key].items():
            menu.add_command(label=f"{name}  ({len(items)})",
                             command=lambda n=name, i=items: self.add_preset(n, i))
        mb["menu"] = menu
        mb.pack(side="left")
        if key == "apps":
            ttk.Button(btns, text="🖥 Programas abertos…", command=self.pick).pack(side="left", padx=6)
        tone_label(btns, "Ctrl+Enter adiciona").pack(side="right")

        self.msg = ttk.Label(self, text=f"Exemplo: {example}", foreground=C("ok"))
        self.msg.pack(anchor="w")

        frow = ttk.Frame(self)
        frow.pack(fill="x", pady=(8, 4))
        ttk.Label(frow, text="🔍 Filtrar:").pack(side="left")
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *a: self.refresh())
        ttk.Entry(frow, textvariable=self.filter_var).pack(side="left", fill="x", expand=True, padx=6)
        self.count = tone_label(frow)
        self.count.pack(side="right")

        lf = ttk.Frame(self)
        lf.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(lf, columns=("item",), show="headings", selectmode="extended", height=8)
        self.tree.column("item", anchor="w")
        self.tree.heading("item", command=self.toggle_sort)
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Delete>", lambda e: self.remove_selected())
        self.tree.bind("<Control-a>", lambda e: (self.tree.selection_set(self.tree.get_children()), "break")[1])

        bot = ttk.Frame(self)
        bot.pack(fill="x", pady=(8, 0))
        ttk.Button(bot, text="🗑 Remover selecionados", command=self.remove_selected).pack(side="left")
        ttk.Button(bot, text="Limpar tudo", command=self.clear_all).pack(side="left", padx=6)
        ttk.Button(bot, text="💾 Exportar lista…", command=self.export_file).pack(side="right")
        self.refresh()

    @property
    def items(self):
        return self.app.cfg[self.key]

    def toggle_sort(self):
        self.sort_rev = not self.sort_rev
        self.refresh()

    def refresh(self):
        q = self.filter_var.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        shown = 0
        for item in sorted(self.items, key=str.lower, reverse=self.sort_rev):
            if q and q not in item.lower():
                continue
            self.tree.insert("", "end", values=(item,))
            shown += 1
        total = len(self.items)
        self.count.config(text=f"{shown} de {total}" if q else f"{total} itens")
        self.tree.heading("item", text=f"{self.title} bloqueados {'▼' if self.sort_rev else '▲'}", anchor="w")
        self.app.refresh_titles()

    def set_msg(self, text, ok=True):
        self.msg.config(text=text, foreground=C("ok" if ok else "err"))

    def changed(self):
        self.app.lists_changed(self.key == "sites")
        self.refresh()

    def add_items(self, raw_items):
        existing = {x.lower() for x in self.items}
        added = dup = invalid = 0
        for raw in raw_items:
            value = self.normalize(raw)
            if not value:
                invalid += 1
            elif value.lower() in existing:
                dup += 1
            else:
                self.items.append(value)
                existing.add(value.lower())
                added += 1
        if added:
            self.changed()
        parts = [f"{added} adicionado(s)"]
        if dup:
            parts.append(f"{dup} já existia(m)")
        if invalid:
            parts.append(f"{invalid} inválido(s)")
        self.set_msg(" • ".join(parts), ok=(invalid == 0))
        return added

    def add_from_text(self):
        entries = core.parse_entries(self.text.get("1.0", "end"))
        if not entries:
            self.set_msg(f"Digite algo para adicionar. Exemplo: {self.example}", ok=False)
            return
        self.add_items(entries)
        self.text.delete("1.0", "end")

    def add_preset(self, name, items):
        n = self.add_items(items)
        self.set_msg(f"Lista \"{name}\": {n} novo(s) item(ns) adicionado(s).")

    def pick(self):
        names = pick_programs(self)
        if names:
            self.add_items(names)

    def import_file(self):
        path = filedialog.askopenfilename(
            title="Importar lista", filetypes=[("Texto/CSV", "*.txt *.csv *.list"), ("Todos", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror(core.APP_NAME, f"Não foi possível ler o arquivo:\n{e}")
            return
        self.add_items([l for l in core.parse_entries(content) if not l.startswith("#")])

    def export_file(self):
        if not self.items:
            self.set_msg("A lista está vazia.", ok=False)
            return
        path = filedialog.asksaveasfilename(title="Exportar lista", defaultextension=".txt",
                                            initialfile=f"{self.key}.txt", filetypes=[("Texto", "*.txt")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(sorted(self.items, key=str.lower)) + "\n")
            self.set_msg(f"Lista exportada ({len(self.items)} itens).")
        except Exception as e:
            messagebox.showerror(core.APP_NAME, f"Erro ao salvar:\n{e}")

    def remove_selected(self):
        sel = [str(self.tree.item(i, "values")[0]) for i in self.tree.selection()]
        if not sel:
            self.set_msg("Selecione itens na lista (Ctrl/Shift para vários).", ok=False)
            return
        if not self.app.auth("Remover itens da lista"):
            return
        drop = {s.lower() for s in sel}
        self.app.cfg[self.key] = [x for x in self.items if x.lower() not in drop]
        self.changed()
        self.set_msg(f"{len(sel)} removido(s).")

    def clear_all(self):
        if not self.items:
            return
        if not self.app.auth("Limpar a lista"):
            return
        if not messagebox.askyesno(core.APP_NAME, f"Remover TODOS os {len(self.items)} itens desta lista?"):
            return
        self.app.cfg[self.key] = []
        self.changed()
        self.set_msg("Lista limpa.")


# ======================================================================== limites
class LimitsTab(ttk.Frame):
    TYPES = {"Aplicativo (.exe)": "app", "Termo na janela": "term"}

    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        ttk.Label(self, wraplength=WRAP, foreground=C("muted"), text=(
            "Em vez de bloquear sempre, libere um tempo por dia. O app conta o tempo em que o programa "
            "(ou a janela com o termo) fica aberto e, ao esgotar, encerra-o até o dia seguinte. "
            "Itens que também estão nas listas de bloqueio continuam sempre bloqueados.")).pack(anchor="w")
        box = ttk.LabelFrame(self, text=" Novo limite ", padding=8)
        box.pack(fill="x", pady=10)
        self.type = tk.StringVar(value="Aplicativo (.exe)")
        ttk.Combobox(box, textvariable=self.type, values=list(self.TYPES), state="readonly",
                     width=18).grid(row=0, column=0, padx=(0, 8))
        self.value = tk.StringVar()
        ttk.Entry(box, textvariable=self.value, width=30).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(box, text="🖥", width=3, command=self.pick).grid(row=0, column=2, padx=(0, 8))
        self.minutes = tk.StringVar(value="60")
        ttk.Spinbox(box, from_=1, to=1440, width=6, textvariable=self.minutes).grid(row=0, column=3)
        ttk.Label(box, text="min/dia").grid(row=0, column=4, padx=(4, 12))
        ttk.Button(box, text="➕ Adicionar", command=self.add).grid(row=0, column=5)
        self.msg = ttk.Label(self, text="", foreground=C("ok"))
        self.msg.pack(anchor="w")

        lf = ttk.Frame(self)
        lf.pack(fill="both", expand=True, pady=(6, 0))
        self.tree = ttk.Treeview(lf, columns=("tipo", "item", "limite", "usado", "estado"),
                                 show="headings", height=10, selectmode="extended")
        for col, text, w in (("tipo", "Tipo", 120), ("item", "Item", 240), ("limite", "Limite/dia", 100),
                             ("usado", "Usado hoje", 100), ("estado", "Estado", 110)):
            self.tree.heading(col, text=text, anchor="w")
            self.tree.column(col, width=w, stretch=(col == "item"))
        self.tree.tag_configure("full", foreground=C("err"))
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        bot = ttk.Frame(self)
        bot.pack(fill="x", pady=(8, 0))
        ttk.Button(bot, text="🗑 Remover selecionados", command=self.remove).pack(side="left")
        ttk.Button(bot, text="↺ Zerar uso de hoje", command=self.reset_usage).pack(side="left", padx=6)
        self.tree.bind("<Delete>", lambda e: self.remove())
        self.refresh()

    @staticmethod
    def key_of(lim):
        return f"{lim['type']}:{lim['value'].lower()}"

    def used(self, lim) -> float:
        u = self.app.cfg["usage"]
        if u.get("date") != time.strftime("%Y-%m-%d"):
            return 0.0
        return float(u["seconds"].get(self.key_of(lim), 0.0))

    def refresh(self):
        sel = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        for lim in self.app.cfg["limits"]:
            used, cap = self.used(lim), lim["minutes"] * 60
            full = used >= cap
            iid = self.key_of(lim)
            self.tree.insert("", "end", iid=iid, tags=("full",) if full else (), values=(
                "Aplicativo" if lim["type"] == "app" else "Termo", lim["value"],
                f"{lim['minutes']} min", fmt_minutes(used), "Esgotado" if full else "Liberado"))
            if iid in sel:
                self.tree.selection_add(iid)
        self.app.refresh_titles()

    def pick(self):
        if self.TYPES[self.type.get()] != "app":
            self.type.set("Aplicativo (.exe)")
        names = pick_programs(self, multi=False)
        if names:
            self.value.set(names[0])

    def add(self):
        kind = self.TYPES[self.type.get()]
        value = (core.normalize_app if kind == "app" else core.normalize_term)(self.value.get())
        try:
            minutes = int(self.minutes.get())
        except ValueError:
            minutes = 0
        if not value or minutes < 1:
            self.msg.config(text="Informe o item e um limite de pelo menos 1 minuto.", foreground=C("err"))
            return
        if kind == "term" and len(value) < 3:
            self.msg.config(text="O termo precisa ter ao menos 3 letras.", foreground=C("err"))
            return
        lims = self.app.cfg["limits"]
        existing = next((l for l in lims if self.key_of(l) == f"{kind}:{value.lower()}"), None)
        if existing:
            if minutes > existing["minutes"] and not self.app.auth("Aumentar um limite"):
                return
            existing["minutes"] = minutes
        else:
            lims.append({"type": kind, "value": value, "minutes": minutes})
        self.app.save()
        self.value.set("")
        self.msg.config(text=f"Limite salvo: {value} — {minutes} min/dia.", foreground=C("ok"))
        self.refresh()

    def remove(self):
        sel = set(self.tree.selection())
        if not sel:
            self.msg.config(text="Selecione um limite na lista.", foreground=C("err"))
            return
        if not self.app.auth("Remover limites"):
            return
        self.app.cfg["limits"] = [l for l in self.app.cfg["limits"] if self.key_of(l) not in sel]
        self.app.save()
        self.refresh()

    def reset_usage(self):
        if not self.app.auth("Zerar o uso de hoje"):
            return
        with core.CFG_LOCK:
            self.app.cfg["usage"] = {"date": time.strftime("%Y-%m-%d"), "seconds": {}}
        self.app.save()
        self.refresh()


# ======================================================================== agenda
class ScheduleTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        sch = app.cfg["schedule"]
        ttk.Label(self, wraplength=WRAP, foreground=C("muted"), text=(
            "Com a agenda ligada, o bloqueio só vale nos horários abaixo; fora deles nada é bloqueado "
            "(nem sites, nem aplicativos, nem limites). Horários que passam da meia-noite, como "
            "22:00–06:00, funcionam.")).pack(anchor="w")
        self.enabled = tk.BooleanVar(value=sch["enabled"])
        ttk.Checkbutton(self, text="Usar agenda (bloquear só nos horários abaixo)", variable=self.enabled,
                        command=self.toggle).pack(anchor="w", pady=(10, 2))
        self.state = ttk.Label(self, text="")
        self.state.pack(anchor="w")

        box = ttk.LabelFrame(self, text=" Novo horário ", padding=8)
        box.pack(fill="x", pady=10)
        days = ttk.Frame(box)
        days.pack(anchor="w")
        self.days = []
        for i, name in enumerate(core.DAY_NAMES):
            v = tk.BooleanVar(value=i < 5)
            self.days.append(v)
            ttk.Checkbutton(days, text=name, variable=v).pack(side="left", padx=(0, 6))
        row = ttk.Frame(box)
        row.pack(anchor="w", pady=(8, 0))
        ttk.Label(row, text="Das").pack(side="left")
        self.start = tk.StringVar(value="08:00")
        ttk.Entry(row, textvariable=self.start, width=7).pack(side="left", padx=6)
        ttk.Label(row, text="às").pack(side="left")
        self.end = tk.StringVar(value="18:00")
        ttk.Entry(row, textvariable=self.end, width=7).pack(side="left", padx=6)
        ttk.Button(row, text="➕ Adicionar horário", command=self.add).pack(side="left", padx=(12, 0))
        quick = ttk.Frame(box)
        quick.pack(anchor="w", pady=(8, 0))
        tone_label(quick, "Atalhos:").pack(side="left")
        for label, days_, s, e in (("Dias úteis 08–18", [0, 1, 2, 3, 4], "08:00", "18:00"),
                                   ("Todos os dias", list(range(7)), "00:00", "23:59"),
                                   ("Noite 22–06", list(range(7)), "22:00", "06:00")):
            ttk.Button(quick, text=label, command=lambda d=days_, a=s, b=e: self.add_rule(d, a, b)
                       ).pack(side="left", padx=6)
        self.msg = ttk.Label(self, text="", foreground=C("ok"))
        self.msg.pack(anchor="w")

        lf = ttk.Frame(self)
        lf.pack(fill="both", expand=True, pady=(6, 0))
        self.tree = ttk.Treeview(lf, columns=("regra",), show="headings", height=8, selectmode="extended")
        self.tree.heading("regra", text="Horários em que o bloqueio vale", anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        ttk.Button(self, text="🗑 Remover selecionados", command=self.remove).pack(anchor="w", pady=(8, 0))
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self.app.cfg["schedule"]["rules"]):
            self.tree.insert("", "end", iid=str(i), values=(core.rule_text(r),))
        self.update_state()
        self.app.refresh_titles()

    def update_state(self):
        sch = self.app.cfg["schedule"]
        if not sch["enabled"] or not sch["rules"]:
            self.state.config(text="Agenda desligada: o bloqueio vale o tempo todo.", foreground=C("muted"))
        elif core.in_schedule(self.app.cfg):
            self.state.config(text="Agora: ✔ dentro do horário — bloqueio valendo.", foreground=C("ok"))
        else:
            self.state.config(text="Agora: ⏸ fora do horário — nada está sendo bloqueado.", foreground=C("warn"))

    def toggle(self):
        if not self.app.auth("Alterar a agenda"):
            self.enabled.set(not self.enabled.get())
            return
        self.app.cfg["schedule"]["enabled"] = self.enabled.get()
        self.app.save()
        self.app.sync_hosts()
        self.update_state()

    def add(self):
        days = [i for i, v in enumerate(self.days) if v.get()]
        if not days:
            self.msg.config(text="Marque ao menos um dia.", foreground=C("err"))
            return
        self.add_rule(days, self.start.get().strip(), self.end.get().strip())

    def add_rule(self, days, start, end):
        if core.parse_hhmm(start) is None or core.parse_hhmm(end) is None:
            self.msg.config(text="Use o formato HH:MM (ex.: 08:00).", foreground=C("err"))
            return
        rules = self.app.cfg["schedule"]["rules"]
        rule = {"days": sorted(days), "start": start, "end": end}
        if rule not in rules:
            rules.append(rule)
        self.app.save()
        self.app.sync_hosts()
        self.msg.config(text="Horário adicionado.", foreground=C("ok"))
        self.refresh()

    def remove(self):
        sel = {int(i) for i in self.tree.selection()}
        if not sel:
            self.msg.config(text="Selecione um horário.", foreground=C("err"))
            return
        if not self.app.auth("Remover horários"):
            return
        rules = self.app.cfg["schedule"]["rules"]
        self.app.cfg["schedule"]["rules"] = [r for i, r in enumerate(rules) if i not in sel]
        self.app.save()
        self.app.sync_hosts()
        self.refresh()


# ================================================================ listas online
class RemoteTab(ttk.Frame):
    LABELS = {"Site": "sites", "Aplicativo": "apps", "Termo": "terms"}
    HEADINGS = {"origem": "Lista", "tipo": "Tipo", "item": "Item", "estado": "Estado"}

    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        self.sort_col, self.sort_rev = "estado", False
        ttk.Label(self, wraplength=WRAP, foreground=C("muted"), text=(
            "Listas mantidas online (por você ou por outra pessoa). Várias podem ficar ativas ao mesmo "
            "tempo e se somam à lista local. Se a internet cair, vale a última versão baixada.")).pack(anchor="w")

        lf = ttk.Frame(self)
        lf.pack(fill="x", pady=(10, 4))
        self.src = ttk.Treeview(lf, columns=("on", "nome", "itens", "sync", "estado"), show="headings",
                                height=4, selectmode="browse")
        for col, text, w in (("on", "Ativa", 55), ("nome", "Lista", 230), ("itens", "Itens", 55),
                             ("sync", "Última sincronização", 140), ("estado", "Estado", 250)):
            self.src.heading(col, text=text, anchor="w")
            self.src.column(col, width=w, stretch=(col == "estado"))
        self.src.pack(fill="x")
        self.src.bind("<Double-1>", lambda e: self.edit_source())
        self.src.bind("<<TreeviewSelect>>", lambda e: self.refresh_items())

        row = ttk.Frame(self)
        row.pack(fill="x", pady=4)
        for text, cmd in (("➕ Adicionar…", self.add_source), ("✏ Editar…", self.edit_source),
                          ("🗑 Remover", self.remove_source), ("⏯ Ativar/Desativar", self.toggle_source),
                          ("🔄 Sincronizar agora", self.sync_now)):
            ttk.Button(row, text=text, command=cmd).pack(side="left", padx=(0, 6))
        row2 = ttk.Frame(self)
        row2.pack(fill="x", pady=(2, 0))
        ttk.Label(row2, text="Atualizar a cada:").pack(side="left")
        cur = next((l for l, m in core.INTERVALS if m == app.cfg["remote"]["interval"]), "30 minutos")
        self.interval = tk.StringVar(value=cur)
        cb = ttk.Combobox(row2, textvariable=self.interval, values=[l for l, _ in core.INTERVALS],
                          state="readonly", width=14)
        cb.pack(side="left", padx=8)
        cb.bind("<<ComboboxSelected>>", lambda e: self.save_interval())
        self.msg = ttk.Label(self, text="")
        self.msg.pack(anchor="w", pady=(6, 0))

        lf2 = ttk.Frame(self)
        lf2.pack(fill="both", expand=True, pady=(6, 0))
        self.tree = ttk.Treeview(lf2, columns=tuple(self.HEADINGS), show="headings", height=8,
                                 selectmode="extended")
        for col, w in (("origem", 150), ("tipo", 100), ("item", 300), ("estado", 90)):
            self.tree.column(col, width=w, stretch=(col == "item"))
        for col, title in self.HEADINGS.items():
            self.tree.heading(col, text=title, anchor="w", command=lambda c=col: self.sort_by(c))
        self.tree.tag_configure("ignored", foreground=C("muted"))
        sb = ttk.Scrollbar(lf2, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        bot = ttk.Frame(self)
        bot.pack(fill="x", pady=(8, 0))
        ttk.Button(bot, text="🚫 Ignorar selecionados", command=self.ignore_selected).pack(side="left")
        ttk.Button(bot, text="↩ Restaurar selecionados", command=self.restore_selected).pack(side="left", padx=6)
        ttk.Button(bot, text="Restaurar todos", command=self.restore_all).pack(side="left")
        tone_label(self, "Ignorar vale só neste computador: o item continua na lista online, mas não é "
                         "bloqueado aqui. Para apagar de vez, remova a linha no arquivo online.",
                   wraplength=WRAP).pack(anchor="w", pady=(6, 0))
        self.tree.bind("<Delete>", lambda e: self.ignore_selected())
        self.refresh()

    # ---- listas
    @property
    def sources(self):
        return self.app.cfg["remote"]["sources"]

    def selected_source(self):
        sel = self.src.selection()
        return next((s for s in self.sources if s["url"] == sel[0]), None) if sel else None

    def source_state(self, s) -> tuple:
        st = self.app.sync_status.get(s["url"])
        if not s["enabled"]:
            return "desativada", "muted"
        if st is None:
            return ("aguardando sincronização" if not s["last_sync"] else "ok"), "muted"
        kind, msg = st
        return {"run": ("sincronizando…", "muted"), "ok": ("ok", "ok")}.get(kind, (f"erro: {msg}", "err"))

    def refresh(self):
        sel = self.src.selection()
        self.src.delete(*self.src.get_children())
        for s in self.sources:
            n = sum(len(v) for v in s["cache"].values())
            state, _ = self.source_state(s)
            self.src.insert("", "end", iid=s["url"], values=(
                "✔" if s["enabled"] else "—", s["name"] + (" 🔒" if s["secret"] else ""), n,
                s["last_sync"] or "—", state))
        if sel and self.src.exists(sel[0]):
            self.src.selection_set(sel[0])
        elif self.sources:
            self.src.selection_set(self.sources[0]["url"])
        self.refresh_items()

    def is_ignored(self, key, item) -> bool:
        return item.lower() in {x.lower() for x in self.app.cfg["remote"]["ignored"][key]}

    def total(self) -> int:
        seen = set()
        for s in self.sources:
            if s["enabled"]:
                for k in core.KEYS:
                    seen.update((k, x.lower()) for x in s["cache"][k] if not self.is_ignored(k, x))
        return len(seen)

    def sort_by(self, col):
        self.sort_rev = (not self.sort_rev) if col == self.sort_col else False
        self.sort_col = col
        self.refresh_items()

    def refresh_items(self, message=None, ok=True):
        self.tree.delete(*self.tree.get_children())
        rows = []
        for s in self.sources:
            for key, label in (("sites", "Site"), ("apps", "Aplicativo"), ("terms", "Termo")):
                for item in s["cache"][key]:
                    rows.append((s["name"], label, item, self.is_ignored(key, item)))
        keyfn = {"estado": lambda t: (t[3], t[1], t[2].lower()), "tipo": lambda t: (t[1], t[3], t[2].lower()),
                 "item": lambda t: (t[2].lower(), t[1]), "origem": lambda t: (t[0].lower(), t[3], t[2].lower())
                 }[self.sort_col]
        for origem, label, item, ig in sorted(rows, key=keyfn, reverse=self.sort_rev):
            self.tree.insert("", "end", values=(origem, label, item, "ignorado" if ig else "ativo"),
                             tags=("ignored",) if ig else ())
        for col, title in self.HEADINGS.items():
            arrow = (" ▼" if self.sort_rev else " ▲") if col == self.sort_col else ""
            self.tree.heading(col, text=title + arrow)
        if message is None:
            message = f"{self.total()} itens ativos vindos das listas online."
        self.msg.config(text=message, foreground=C("ok" if ok else "err"))
        self.app.refresh_titles()

    def save_interval(self):
        if not self.app.auth("Alterar a frequência de atualização"):
            cur = next((l for l, m in core.INTERVALS if m == self.app.cfg["remote"]["interval"]), "30 minutos")
            self.interval.set(cur)
            return
        self.app.cfg["remote"]["interval"] = dict(core.INTERVALS).get(self.interval.get(), 30)
        self.app.save()

    # ---- acoes
    def add_source(self):
        r = source_dialog(self, self.sources)
        if not r:
            return
        self.sources.append(core._source(r["name"], r["url"], True, r["secret"]))
        self.app.save()
        self.refresh()
        self.src.selection_set(r["url"])
        self.app.start_sync(force=True)

    def edit_source(self):
        s = self.selected_source()
        if not s or not self.app.auth("Editar listas online"):
            return
        r = source_dialog(self, self.sources, s["name"], s["url"], s["secret"], editing_url=s["url"])
        if not r:
            return
        if r["url"] != s["url"]:
            s["cache"], s["last_sync"] = core.empty_lists(), ""
        s.update(name=r["name"], url=r["url"], secret=r["secret"])
        self.app.save()
        self.app.sync_hosts()
        self.refresh()
        self.app.start_sync(force=True)

    def remove_source(self):
        s = self.selected_source()
        if not s:
            return
        if not self.app.auth("Remover listas online"):
            return
        if not messagebox.askyesno(core.APP_NAME, f"Remover a lista \"{s['name']}\"?"):
            return
        self.app.cfg["remote"]["sources"] = [x for x in self.sources if x["url"] != s["url"]]
        self.app.save()
        self.app.sync_hosts()
        self.refresh()

    def toggle_source(self):
        s = self.selected_source()
        if not s:
            return
        if s["enabled"] and not self.app.auth("Desativar uma lista online"):
            return
        s["enabled"] = not s["enabled"]
        self.app.save()
        self.app.sync_hosts()
        self.refresh()
        if s["enabled"]:
            self.app.start_sync(force=True)

    def sync_now(self):
        self.app.start_sync(force=True)
        self.refresh_items("Sincronizando…")

    # ---- ignorar
    def selected_entries(self):
        out = []
        for iid in self.tree.selection():
            _o, label, item, _e = self.tree.item(iid, "values")
            out.append((self.LABELS[str(label)], str(item)))
        return out

    def ignore_selected(self):
        sel = self.selected_entries()
        if not sel:
            self.refresh_items("Selecione itens na lista (Ctrl/Shift para vários).", ok=False)
            return
        if not self.app.auth("Ignorar itens da lista online"):
            return
        ign = self.app.cfg["remote"]["ignored"]
        for key, item in sel:
            if not self.is_ignored(key, item):
                ign[key].append(item)
        self.apply_change(f"{len(sel)} item(ns) ignorado(s).")

    def restore_selected(self):
        sel = self.selected_entries()
        if not sel:
            self.refresh_items("Selecione itens na lista.", ok=False)
            return
        ign = self.app.cfg["remote"]["ignored"]
        for key, item in sel:
            ign[key] = [x for x in ign[key] if x.lower() != item.lower()]
        self.apply_change(f"{len(sel)} item(ns) restaurado(s).")

    def restore_all(self):
        ign = self.app.cfg["remote"]["ignored"]
        n = sum(len(v) for v in ign.values())
        for key in ign:
            ign[key] = []
        self.apply_change(f"{n} item(ns) restaurado(s).")

    def apply_change(self, message):
        self.app.save()
        self.app.sync_hosts()
        self.refresh_items(message)


# ====================================================================== historico
class HistoryTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        ttk.Label(self, wraplength=WRAP, foreground=C("muted"), text=(
            "Registro do que foi encerrado ou fechado (aplicativos, termos e limites). "
            "Sites bloqueados pelo arquivo hosts não geram registro, pois o navegador nem chega a abrir a página.")
                  ).pack(anchor="w")
        frow = ttk.Frame(self)
        frow.pack(fill="x", pady=(10, 4))
        ttk.Label(frow, text="🔍 Filtrar:").pack(side="left")
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *a: self.render())
        ttk.Entry(frow, textvariable=self.q).pack(side="left", fill="x", expand=True, padx=6)
        self.count = tone_label(frow)
        self.count.pack(side="right")
        lf = ttk.Frame(self)
        lf.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(lf, columns=("t", "tipo", "item"), show="headings", height=14)
        for col, text, w in (("t", "Quando", 150), ("tipo", "Tipo", 140), ("item", "Item", 420)):
            self.tree.heading(col, text=text, anchor="w")
            self.tree.column(col, width=w, stretch=(col == "item"))
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        bot = ttk.Frame(self)
        bot.pack(fill="x", pady=(8, 0))
        ttk.Button(bot, text="🗑 Limpar histórico", command=self.clear).pack(side="left")
        ttk.Button(bot, text="💾 Exportar CSV…", command=self.export).pack(side="left", padx=6)
        self.records = list(reversed(app.history.load(500)))  # mais novos primeiro
        self.render()

    def add_records(self, recs):
        self.records = list(reversed(recs)) + self.records
        self.records = self.records[:1000]
        self.render()

    def render(self):
        f = self.q.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        shown = 0
        for r in self.records:
            label = KIND_LABELS.get(r["kind"], r["kind"])
            if f and f not in r["item"].lower() and f not in label.lower():
                continue
            self.tree.insert("", "end", values=(r["t"], label, r["item"]))
            shown += 1
        self.count.config(text=f"{shown} registro(s)")

    def clear(self):
        if not self.app.auth("Limpar o histórico"):
            return
        self.app.history.clear()
        self.records = []
        self.render()

    def export(self):
        path = filedialog.asksaveasfilename(title="Exportar histórico", defaultextension=".csv",
                                            initialfile="historico.csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["Quando", "Tipo", "Item"])
                for r in self.records:
                    w.writerow([r["t"], KIND_LABELS.get(r["kind"], r["kind"]), r["item"]])
        except OSError as e:
            messagebox.showerror(core.APP_NAME, f"Erro ao salvar:\n{e}")


# ================================================================== configuracoes
class SettingsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        cfg = app.cfg

        # ---- seguranca
        sec = ttk.LabelFrame(self, text=" Segurança ", padding=10)
        sec.pack(fill="x", pady=(0, 10))
        self.pw_state = ttk.Label(sec, text="")
        self.pw_state.pack(anchor="w")
        tone_label(sec, "Com senha, pausar o bloqueio, sair do app e remover/alterar listas, horários e "
                        "limites exigem a senha. Adicionar itens continua livre.",
                   wraplength=WRAP).pack(anchor="w", pady=(2, 6))
        row = ttk.Frame(sec)
        row.pack(anchor="w")
        self.pw_btn = ttk.Button(row, text="Definir senha", command=self.set_password)
        self.pw_btn.pack(side="left")
        self.pw_rm = ttk.Button(row, text="Remover senha", command=self.remove_password)
        self.pw_rm.pack(side="left", padx=6)
        ttk.Button(row, text="🔒 Bloquear agora", command=self.app.lock_now).pack(side="left")
        row2 = ttk.Frame(sec)
        row2.pack(anchor="w", pady=(8, 0))
        ttk.Label(row2, text="Lembrar a senha por").pack(side="left")
        self.unlock = tk.StringVar(value=str(cfg["security"]["unlock_minutes"]))
        cb = ttk.Combobox(row2, textvariable=self.unlock, values=["1", "5", "15", "30", "60"],
                          state="readonly", width=5)
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self.save_unlock())
        ttk.Label(row2, text="minutos").pack(side="left")

        # ---- sistema
        sysf = ttk.LabelFrame(self, text=" Sistema ", padding=10)
        sysf.pack(fill="x", pady=(0, 10))
        self.vars = {}
        for key, text, hint in (
                ("autostart", "Iniciar com o Windows",
                 "Cria uma tarefa agendada que abre o app ao entrar no Windows, já como administrador."),
                ("watchdog", "Reabrir automaticamente se for encerrado",
                 "Uma tarefa verifica a cada minuto e reabre o app se ele for fechado (ex.: pelo "
                 "Gerenciador de Tarefas). Sair pelo próprio app, com a senha, não reabre."),
                ("block_doh", "Reforçar bloqueio de sites (desligar DNS seguro nos navegadores)",
                 "O DNS seguro do Chrome/Edge/Firefox/Brave ignora o arquivo hosts. Isto aplica uma política "
                 "do Windows que o desliga (os navegadores passam a mostrar \"gerenciado pela organização\"). "
                 "Reinicie o navegador."),
                ("title_match_sites", "Também fechar janelas com o nome do site no título",
                 "Ex.: fecha janelas cujo título contém \"youtube\" se youtube.com estiver bloqueado. "
                 "Pode fechar janelas que apenas mencionem o nome.")):
            v = tk.BooleanVar(value=cfg["system"][key])
            self.vars[key] = v
            ttk.Checkbutton(sysf, text=text, variable=v,
                            command=lambda k=key, t=text: self.toggle_system(k, t)).pack(anchor="w")
            tone_label(sysf, hint, wraplength=WRAP - 30).pack(anchor="w", padx=(26, 0), pady=(0, 6))

        # ---- interface
        ui = ttk.LabelFrame(self, text=" Interface ", padding=10)
        ui.pack(fill="x", pady=(0, 10))
        row = ttk.Frame(ui)
        row.pack(anchor="w")
        ttk.Label(row, text="Tema:").pack(side="left")
        self.theme = tk.StringVar(value=cfg["ui"]["theme"].capitalize())
        cb = ttk.Combobox(row, textvariable=self.theme, values=["Claro", "Escuro"], state="readonly", width=8)
        cb.pack(side="left", padx=(6, 18))
        cb.bind("<<ComboboxSelected>>", lambda e: self.save_ui())
        ttk.Label(row, text="Tamanho da fonte:").pack(side="left")
        self.size = tk.StringVar(value=str(cfg["ui"]["font_size"]))
        cb = ttk.Combobox(row, textvariable=self.size, values=[str(i) for i in range(9, 16)],
                          state="readonly", width=4)
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self.save_ui())
        self.notify = tk.BooleanVar(value=cfg["ui"]["notify"])
        ttk.Checkbutton(ui, text="Mostrar notificação quando algo for bloqueado",
                        variable=self.notify, command=self.save_ui).pack(anchor="w", pady=(8, 0))

        ttk.Button(self, text="📁 Abrir pasta de configurações", command=self.open_folder).pack(anchor="w")
        self.refresh_pw()

    # ---- seguranca
    def refresh_pw(self):
        has = core.has_password(self.app.cfg)
        self.pw_state.config(text="🔒 Proteção por senha: ligada" if has else "🔓 Proteção por senha: desligada",
                             foreground=C("ok" if has else "muted"))
        self.pw_btn.config(text="Alterar senha" if has else "Definir senha")
        self.pw_rm.config(state="normal" if has else "disabled")

    def set_password(self, skip_auth=False):
        if not skip_auth and core.has_password(self.app.cfg) and not self.app.auth("Alterar a senha", fresh=True):
            return
        p1 = ask_text(self, "Nova senha", "Digite a nova senha (mínimo 4 caracteres):", show="•")
        if p1 is None:
            return
        if len(p1) < 4:
            messagebox.showwarning(core.APP_NAME, "Use pelo menos 4 caracteres.")
            return
        p2 = ask_text(self, "Nova senha", "Digite a senha novamente:", show="•")
        if p2 != p1:
            messagebox.showwarning(core.APP_NAME, "As senhas não são iguais.")
            return
        code = core.set_password(self.app.cfg, p1)
        self.app.save()
        self.app.lock_now()
        self.refresh_pw()
        show_recovery_code(self, code)

    def remove_password(self):
        if not self.app.auth("Remover a senha", fresh=True):
            return
        core.clear_password(self.app.cfg)
        self.app.save()
        self.refresh_pw()

    def save_unlock(self):
        if not self.app.auth("Alterar configurações"):
            self.unlock.set(str(self.app.cfg["security"]["unlock_minutes"]))
            return
        self.app.cfg["security"]["unlock_minutes"] = int(self.unlock.get())
        self.app.save()

    # ---- sistema
    def toggle_system(self, key, label):
        var = self.vars[key]
        new = var.get()
        if not self.app.auth(label):
            var.set(not new)
            return
        err = ""
        if key == "autostart":
            ok, err = core.set_autostart(new)
            ok = ok
        elif key == "watchdog":
            ok, err = core.set_watchdog(new)
        elif key == "block_doh":
            errs = core.set_doh_block(new)
            ok, err = not errs, "\n".join(errs)
        else:
            ok = True
        if not ok:
            var.set(not new)
            messagebox.showerror(core.APP_NAME, f"Não foi possível aplicar a mudança:\n{err}")
            return
        self.app.cfg["system"][key] = new
        self.app.save()

    # ---- interface
    def save_ui(self):
        ui = self.app.cfg["ui"]
        ui["theme"] = self.theme.get().lower()
        ui["font_size"] = int(self.size.get())
        ui["notify"] = self.notify.get()
        self.app.save()
        self.app.apply_theme()

    def open_folder(self):
        os.makedirs(core.CONFIG_DIR, exist_ok=True)
        try:
            os.startfile(core.CONFIG_DIR)
        except AttributeError:
            webbrowser.open(core.CONFIG_DIR)


def show_recovery_code(parent, code: str):
    dlg, frm = make_dialog(parent, "Código de recuperação")
    ttk.Label(frm, text="Senha definida!", style="Title.TLabel").pack(anchor="w")
    tone_label(frm, "Anote este código de recuperação e guarde em lugar seguro. Ele é mostrado "
                    "UMA ÚNICA VEZ e é a única forma de redefinir a senha se você a esquecer.",
               wraplength=420).pack(anchor="w", pady=(4, 10))
    ttk.Label(frm, text=code, style="Title.TLabel", foreground=C("warn")).pack(pady=6)

    def copy():
        dlg.clipboard_clear()
        dlg.clipboard_append(code)

    row = ttk.Frame(frm)
    row.pack(fill="x", pady=(10, 0))
    ttk.Button(row, text="Copiar", command=copy).pack(side="left")
    ttk.Button(row, text="Anotei, fechar", command=dlg.destroy).pack(side="right")
    show_modal(dlg, parent)


# ===================================================================== apoie o projeto
class SupportTab(ttk.Frame):
    """Apoio voluntario e opcional: mostra a chave PIX e um link para o GitHub. Nao cobra nada."""

    def __init__(self, parent, app):
        super().__init__(parent, padding=18)
        self.app = app
        s = core.SUPPORT
        st = ttk.Style(self)
        st.configure("Accent.TButton", background="#f5b400", foreground="#1a1a1a",
                     bordercolor="#c98f00", padding=(14, 8))
        st.map("Accent.TButton", background=[("active", "#ffc933"), ("pressed", "#d99f00")])

        ttk.Label(self, text=s["titulo"], style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text=s["subtitulo"], wraplength=WRAP, foreground=C("muted")).pack(anchor="w", pady=(2, 12))
        ttk.Label(self, text=s["destaque"], style="Bold.TLabel").pack(anchor="w")
        ttk.Label(self, text=s["mensagem"], wraplength=WRAP, justify="left").pack(anchor="w", pady=(6, 0))
        ttk.Label(self, text=s["sem_contribuir"], wraplength=WRAP, justify="left",
                  foreground=C("muted")).pack(anchor="w", pady=(10, 0))

        card = ttk.LabelFrame(self, text=f" {s['pix_rotulo']} ", padding=16)
        card.pack(fill="x", pady=(18, 0))
        ttk.Label(card, text="Chave PIX (e-mail):", style="Bold.TLabel").pack(anchor="w")
        self.pix_var = tk.StringVar(value=core.SUPPORT_PIX_KEY)  # guardado no objeto para nao ser coletado
        ent = ttk.Entry(card, textvariable=self.pix_var, state="readonly", font=("Consolas", 12))
        ent.pack(fill="x", pady=(6, 12), ipady=4)
        row = ttk.Frame(card)
        row.pack(anchor="w")
        ttk.Button(row, text="📋 Copiar chave PIX", style="Accent.TButton", command=self.copy_pix).pack(side="left")
        ttk.Button(row, text="⭐ Apoiar no GitHub", command=self.open_github).pack(side="left", padx=8)
        self.feedback = ttk.Label(card, text="", foreground=C("ok"))
        self.feedback.pack(anchor="w", pady=(10, 0))

        tags = ttk.Frame(self)
        tags.pack(fill="x", pady=(18, 0))
        for text in s["rodape"]:
            ttk.Label(tags, text=text, foreground=C("muted")).pack(side="left", padx=(0, 18))
        ttk.Label(self, text=s["final"], style="Bold.TLabel").pack(anchor="w", pady=(10, 0))

        bot = ttk.Frame(self)
        bot.pack(fill="x", pady=(16, 0))
        ttk.Button(bot, text="Fechar", command=lambda: self.app.nb.select(0)).pack(side="right")

    def copy_pix(self):
        key = core.SUPPORT_PIX_KEY
        try:
            top = self.winfo_toplevel()
            top.clipboard_clear()
            top.clipboard_append(key)
            top.update()
            if top.clipboard_get() != key:
                raise tk.TclError("conteudo diferente")
            self.feedback.config(text=core.SUPPORT["copiado"], foreground=C("ok"))
        except tk.TclError:
            self.feedback.config(text=core.SUPPORT["erro_copia"], foreground=C("err"))
        self.after(5000, lambda: self.feedback.config(text=""))

    def open_github(self):
        url = (core.SUPPORT_GITHUB_URL or "").strip()
        if not url.lower().startswith("https://"):
            return messagebox.showinfo(core.APP_NAME, core.SUPPORT["sem_url"])
        try:
            webbrowser.open(url)
        except Exception:
            messagebox.showwarning(core.APP_NAME, f"Não foi possível abrir o navegador. Acesse:\n{url}")


# ======================================================================== sobre
class AboutTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=16)
        self.app = app
        self.update_info = None

        ttk.Label(self, text=core.APP_NAME, style="Title.TLabel").pack(anchor="w")
        tone_label(self, core.APP_TAGLINE).pack(anchor="w", pady=(0, 12))
        info = ttk.Frame(self)
        info.pack(fill="x")
        rows = [("Versão", core.APP_VERSION), ("Autor", core.AUTHOR), ("Sistema", "Windows 10 / 11"),
                ("Repositório", core.REPO_URL), ("Configurações", core.CONFIG_DIR)]
        for i, (k, v) in enumerate(rows):
            ttk.Label(info, text=f"{k}:", style="Bold.TLabel").grid(row=i, column=0, sticky="nw", pady=2, padx=(0, 10))
            lbl = ttk.Label(info, text=v, wraplength=560)
            lbl.grid(row=i, column=1, sticky="w", pady=2)
            if k == "Repositório":
                lbl.configure(foreground=C("link"), cursor="hand2")
                lbl.bind("<Button-1>", lambda e: webbrowser.open(core.REPO_URL))

        box = ttk.LabelFrame(self, text=" Atualizações ", padding=10)
        box.pack(fill="x", pady=14)
        self.status = ttk.Label(box, text="Clique em \"Verificar atualizações\".", wraplength=640)
        self.status.pack(anchor="w")
        self.notes = tone_label(box, wraplength=640)
        self.notes.pack(anchor="w", pady=(4, 0))
        row = ttk.Frame(box)
        row.pack(fill="x", pady=(8, 0))
        ttk.Button(row, text="🔄 Verificar atualizações",
                   command=lambda: app.check_update(manual=True)).pack(side="left")
        self.dl_btn = ttk.Button(row, text="⬇ Baixar nova versão", state="disabled", command=self.download)
        self.dl_btn.pack(side="left", padx=6)
        self.auto_btn = ttk.Button(row, text="⚡ Atualizar agora", state="disabled", command=self.install)
        self.auto_btn.pack(side="left")
        self.auto = tk.BooleanVar(value=app.cfg["check_updates"])
        ttk.Checkbutton(box, text="Verificar atualizações ao abrir o app", variable=self.auto,
                        command=self.save_auto).pack(anchor="w", pady=(8, 0))
        tone_label(self, wraplength=WRAP, text=(
            "Como funciona: sites são bloqueados pelo arquivo hosts do Windows; aplicativos e termos são "
            "monitorados enquanto o programa estiver aberto. As listas online são baixadas dos endereços "
            "configurados e somadas à lista local.")).pack(anchor="w")

    def save_auto(self):
        self.app.cfg["check_updates"] = self.auto.get()
        self.app.save()

    def download(self):
        if self.update_info:
            webbrowser.open(self.update_info["download"])

    def install(self):
        if self.update_info:
            self.app.install_update(self.update_info, self)

    def set_checking(self):
        self.status.config(text="Verificando…", foreground=C("fg"))
        self.notes.config(text="")

    def set_progress(self, text):
        self.status.config(text=text, foreground=C("fg"))

    def show_result(self, kind, payload, manual):
        if kind == "ok":
            stamp = time.strftime("%d/%m/%Y %H:%M")
            if core.version_tuple(payload["version"]) > core.version_tuple(core.APP_VERSION):
                self.update_info = payload
                self.status.config(
                    text=f"🔔 Nova versão disponível: {payload['version']} (você tem {core.APP_VERSION})",
                    foreground=C("warn"))
                self.notes.config(text=payload["notes"])
                self.dl_btn.config(state="normal")
                self.auto_btn.config(state="normal" if core.can_self_update(payload) else "disabled")
            else:
                self.update_info = None
                self.status.config(text=f"✔ Você está na versão mais recente ({core.APP_VERSION}). "
                                        f"Verificado em {stamp}.", foreground=C("ok"))
                self.notes.config(text="")
                self.dl_btn.config(state="disabled")
                self.auto_btn.config(state="disabled")
        elif manual:
            self.status.config(text=f"Não foi possível verificar agora: {payload}", foreground=C("err"))
            self.notes.config(text="")
        else:
            self.status.config(text="Clique em \"Verificar atualizações\".", foreground=C("fg"))
        self.app.refresh_titles()

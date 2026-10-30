"""
Bloqueador - bloqueio de sites, aplicativos e jogos para Windows 10/11.

Execute como Administrador (necessario para editar o arquivo hosts).
Parametros: --minimized (inicia na bandeja) | --watchdog (guardiao: reabre o app se fechado)
"""
import os
import queue
import sys
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

import core
from ui_common import C, apply_theme, ask_text, retheme
from ui_tabs import (AboutTab, HistoryTab, KIND_LABELS, LimitsTab, ListTab, RemoteTab, ScheduleTab,
                     SettingsTab, SupportTab, wizard_dialog)

# Bandeja do sistema desativada: o app nunca fica escondido na bandeja.
HAVE_TRAY = False


class Tray:
    """Icone na bandeja do sistema (pystray)."""

    def __init__(self, app):
        self.app, self.icon = app, None

    @property
    def available(self) -> bool:
        return HAVE_TRAY

    @property
    def running(self) -> bool:
        return self.icon is not None

    def start(self):
        return  # bandeja desativada

    def notify(self, msg: str, title: str = core.APP_NAME):
        if self.icon is not None:
            try:
                self.icon.notify(msg, title)
            except Exception:
                pass

    def stop(self):
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None


class App(tk.Tk):
    def __init__(self, minimized: bool = False):
        super().__init__()
        self.ready = False
        self.cfg = core.load_config()
        self.history = core.History()
        self.unlocked_until = 0.0
        self.fail_count, self.locked_until = 0, 0.0
        self.sync_status = {}
        self.ui_q, self.sync_q, self.upd_q = queue.Queue(), queue.Queue(), queue.Queue()
        self.syncing, self.sync_again, self.last_sync_try = False, False, 0.0
        self._hosts_key, self._hosts_error_shown = None, False
        self._last_save, self._ticks = time.time(), 0
        self.tray = Tray(self)
        self.tray_available = self.tray.available

        self.title(core.APP_NAME)
        self.geometry("1120x860")
        self.minsize(1020, 720)
        apply_theme(self, self.cfg["ui"]["theme"], self.cfg["ui"]["font_size"])

        top = ttk.Frame(self, padding=(12, 10, 12, 0))
        top.pack(fill="x")
        self.active_var = tk.BooleanVar(value=self.cfg["active"])
        ttk.Checkbutton(top, text="Bloqueio ativo", variable=self.active_var,
                        command=self.toggle_active).pack(side="left")
        self.status = ttk.Label(top, text="")
        self.status.pack(side="right")

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=6, pady=6)
        self.tabs = {
            "sites": ListTab(self.nb, self, "sites", "Sites",
                             "Endereços de sites. Pode colar URLs completas (https://www.exemplo.com/pagina): "
                             "o domínio inteiro será bloqueado.", "youtube.com, tiktok.com"),
            "apps": ListTab(self.nb, self, "apps", "Aplicativos / jogos",
                            "Nome do programa. Com .exe (ex.: steam.exe) o nome é exato; sem .exe (ex.: minecraft) "
                            "bloqueia qualquer processo que contenha o texto. Se colar o caminho completo, só o "
                            "nome do arquivo é usado. Use \"Programas abertos\" para escolher na lista.",
                            "steam.exe, RobloxPlayerBeta.exe"),
            "terms": ListTab(self.nb, self, "terms", "Termos",
                             "Janelas cujo título contenha o termo serão fechadas (útil para abas de navegador). "
                             "Processos com o termo no nome também são encerrados.", "fortnite, cassino"),
        }
        self.limits_tab = LimitsTab(self.nb, self)
        self.schedule_tab = ScheduleTab(self.nb, self)
        self.remote_tab = RemoteTab(self.nb, self)
        self.history_tab = HistoryTab(self.nb, self)
        self.settings_tab = SettingsTab(self.nb, self)
        self.about_tab = AboutTab(self.nb, self)
        self.support_tab = SupportTab(self.nb, self)
        for t in self.tabs.values():
            self.nb.add(t, text=t.title)
        for tab in (self.limits_tab, self.schedule_tab, self.remote_tab, self.history_tab,
                    self.settings_tab, self.about_tab, self.support_tab):
            self.nb.add(tab, text="")
        self.build_menu()
        retheme(self)
        self.ready = True
        self.refresh_titles()

        self.monitor = core.Monitor(lambda: core.effective(self.cfg), self.history)
        self.monitor.start()
        self.sync_hosts()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.tray.start()
        if minimized:
            self.withdraw() if self.tray.running else self.iconify()
        else:
            self.after(700, self.maybe_wizard)
        self.tick()
        if self.cfg["check_updates"]:
            self.check_update(manual=False)

    # ------------------------------------------------------------ utilidades
    def save(self):
        try:
            core.save_config(self.cfg)
        except OSError as e:
            core.log_error(f"salvar config: {e}")

    def apply_theme(self):
        apply_theme(self, self.cfg["ui"]["theme"], self.cfg["ui"]["font_size"])
        retheme(self)
        self.remote_tab.tree.tag_configure("ignored", foreground=C("muted"))
        self.limits_tab.tree.tag_configure("full", foreground=C("err"))

    def refresh_titles(self):
        if not getattr(self, "ready", False):
            return
        names = {"sites": "🌐 Sites", "apps": "🎮 Apps/jogos", "terms": "🔤 Termos"}
        titles = [(t, f"{names[k]} ({len(self.cfg[k])})") for k, t in self.tabs.items()]
        sch = self.cfg["schedule"]
        titles += [
            (self.limits_tab, f"⏱ Limites ({len(self.cfg['limits'])})"),
            (self.schedule_tab, "📅 Agenda" + (" ●" if sch["enabled"] and sch["rules"] else "")),
            (self.remote_tab, f"☁ Online ({self.remote_tab.total()})"),
            (self.history_tab, "📜 Histórico"),
            (self.settings_tab, "⚙ Config."),
            (self.about_tab, "ℹ Sobre" + (" 🔔" if self.about_tab.update_info else "")),
            (self.support_tab, "💛 Apoie"),
        ]
        for tab, text in titles:
            try:
                self.nb.tab(tab, text=text)
            except tk.TclError:
                pass

    def build_menu(self):
        bar = tk.Menu(self)
        arq = tk.Menu(bar, tearoff=False)
        arq.add_command(label="Abrir pasta de configurações", command=self.settings_tab.open_folder)
        arq.add_separator()
        arq.add_command(label="Sair", command=self.request_quit)
        bar.add_cascade(label="Arquivo", menu=arq)
        aj = tk.Menu(bar, tearoff=False)
        aj.add_command(label="Verificar atualizações…", command=self.menu_check_update)
        aj.add_command(label="Repositório no GitHub", command=lambda: webbrowser.open(core.REPO_URL))
        aj.add_separator()
        aj.add_command(label="💛 Apoie o projeto", command=lambda: self.nb.select(self.support_tab))
        aj.add_command(label=f"Sobre o {core.APP_NAME}", command=lambda: self.nb.select(self.about_tab))
        bar.add_cascade(label="Ajuda", menu=aj)
        self.config(menu=bar)

    def menu_check_update(self):
        self.nb.select(self.about_tab)
        self.check_update(manual=True)

    # ---------------------------------------------------------------- senha
    def auth(self, reason: str = "Esta ação", fresh: bool = False) -> bool:
        """Pede a senha quando a protecao esta ligada. True se liberado."""
        if not core.has_password(self.cfg):
            return True
        if not fresh and time.time() < self.unlocked_until:
            return True
        if time.time() < self.locked_until:
            messagebox.showwarning(core.APP_NAME, f"Muitas tentativas erradas. Aguarde "
                                                  f"{int(self.locked_until - time.time()) + 1} s.")
            return False
        pw = ask_text(self, "Senha necessária", f"{reason} exige a senha.", show="•",
                      extra_text="Esqueci a senha", extra_cmd=self.recover_password)
        if pw is None:
            return False
        if core.check_password(self.cfg, pw):
            self.fail_count = 0
            self.unlocked_until = time.time() + self.cfg["security"]["unlock_minutes"] * 60
            return True
        self.fail_count += 1
        if self.fail_count >= 3:
            self.locked_until, self.fail_count = time.time() + 30, 0
        messagebox.showerror(core.APP_NAME, "Senha incorreta.")
        return False

    def lock_now(self):
        self.unlocked_until = 0.0

    def recover_password(self):
        code = ask_text(self, "Recuperar senha", "Digite o código de recuperação que você anotou "
                                                 "ao definir a senha:")
        if code is None:
            return
        if not core.check_recovery(self.cfg, code):
            messagebox.showerror(core.APP_NAME, "Código de recuperação incorreto.")
            return
        self.settings_tab.set_password(skip_auth=True)

    # ------------------------------------------------------------ bloqueio
    def toggle_active(self):
        new = self.active_var.get()
        if not new and not self.auth("Pausar o bloqueio"):
            self.active_var.set(True)
            return
        self.cfg["active"] = new
        self.save()
        self.sync_hosts()
        self.update_status()

    def lists_changed(self, sites_changed: bool):
        self.save()
        if sites_changed:
            self.sync_hosts()
        self.refresh_titles()

    def sync_hosts(self):
        try:
            eff = core.effective(self.cfg)
            core.apply_hosts(eff["sites"], eff["active"])
            self._hosts_key = (tuple(eff["sites"]), eff["active"])
        except PermissionError:
            self._hosts_key = None
            if not self._hosts_error_shown:
                self._hosts_error_shown = True
                messagebox.showerror(core.APP_NAME, "Sem permissão para editar o arquivo hosts. "
                                                    "Execute como Administrador.")
        except Exception as e:
            core.log_error(f"hosts: {e}")
            if not self._hosts_error_shown:
                self._hosts_error_shown = True
                messagebox.showerror(core.APP_NAME, f"Erro ao atualizar o arquivo hosts:\n{e}")

    def update_status(self):
        eff = core.effective(self.cfg)
        if not self.cfg["active"]:
            state = "⏸ pausado"
        elif not eff["scheduled"]:
            state = "⏸ fora do horário da agenda"
        else:
            state = "● ATIVO"
        err = self.monitor.last_error
        extra = f" • ⚠ erro: {err}" if err else ""
        self.status.config(text=f"{state} • bloqueios aplicados: {self.monitor.blocked_count}{extra}")

    # -------------------------------------------------------- listas online
    def start_sync(self, force: bool = False):
        if self.syncing:
            self.sync_again = self.sync_again or force
            return
        todo = [(s["url"], s["secret"]) for s in self.cfg["remote"]["sources"] if s["enabled"]]
        if not todo:
            return
        self.syncing, self.last_sync_try = True, time.time()
        for url, _ in todo:
            self.sync_status[url] = ("run", "")
        self.remote_tab.refresh()

        def work():
            for url, secret in todo:
                try:
                    self.sync_q.put((url, "ok", core.fetch_remote(url, secret)))
                except Exception as e:
                    self.sync_q.put((url, "err", str(e)[:90]))
            self.sync_q.put((None, "done", None))

        threading.Thread(target=work, daemon=True).start()

    def _drain_sync(self):
        changed = False
        while True:
            try:
                url, kind, payload = self.sync_q.get_nowait()
            except queue.Empty:
                break
            if kind == "done":
                self.syncing = False
                if self.sync_again:
                    self.sync_again = False
                    self.start_sync()
                continue
            src = next((s for s in self.cfg["remote"]["sources"] if s["url"] == url), None)
            if src is None:
                continue
            if kind == "ok":
                if src["cache"] != payload:
                    changed = True
                src["cache"], src["last_sync"] = payload, time.strftime("%d/%m/%Y %H:%M")
                self.sync_status[url] = ("ok", "")
            else:
                self.sync_status[url] = ("err", payload)
                core.log_error(f"lista online {url}: {payload}")
            changed = True
        if changed:
            self.save()
            self.sync_hosts()
            self.remote_tab.refresh()

    # ----------------------------------------------------------- atualizacao
    def check_update(self, manual: bool = False):
        if manual:
            self.about_tab.set_checking()

        def work():
            try:
                self.upd_q.put(("ok", core.fetch_update(), manual))
            except Exception as e:
                self.upd_q.put(("err", str(e), manual))

        threading.Thread(target=work, daemon=True).start()

    def install_update(self, info: dict, about):
        if not self.auth("Atualizar o app"):
            return
        if not messagebox.askyesno(core.APP_NAME, f"Baixar e instalar a versão {info['version']}?\n"
                                                  "O app será reiniciado."):
            return
        about.set_progress("Baixando atualização…")

        def work():
            try:
                path = core.download_update(
                    info, progress=lambda f: self.ui_q.put(("progress", f"Baixando… {int(f * 100)}%")))
                self.ui_q.put(("update_ready", path))
            except Exception as e:
                self.ui_q.put(("update_error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------------ laco
    def tick(self):
        try:
            self._tick()
        except Exception as e:  # nunca derrubar o laco da interface
            core.log_error(f"tick: {type(e).__name__}: {e}")
        self.after(1000, self.tick)

    def _tick(self):
        self._ticks += 1
        # comandos vindos da bandeja / threads
        while True:
            try:
                cmd = self.ui_q.get_nowait()
            except queue.Empty:
                break
            if cmd == "show":
                self.deiconify()
                self.lift()
                self.focus_force()
            elif cmd == "toggle":
                self.active_var.set(not self.cfg["active"])
                self.toggle_active()
            elif cmd == "quit":
                self.deiconify()
                self.request_quit()
            elif isinstance(cmd, tuple) and cmd[0] == "progress":
                self.about_tab.set_progress(cmd[1])
            elif isinstance(cmd, tuple) and cmd[0] == "update_error":
                self.about_tab.set_progress(f"Falha na atualização: {cmd[1]}")
            elif isinstance(cmd, tuple) and cmd[0] == "update_ready":
                core.set_stop_flag()  # evita o guardiao reabrir o exe antigo
                core.apply_update(cmd[1])
                self.quit_now(stop_flag=False)
                return
        while True:
            try:
                kind, payload, manual = self.upd_q.get_nowait()
            except queue.Empty:
                break
            self.about_tab.show_result(kind, payload, manual)
        self._drain_sync()

        # historico + notificacoes
        recs = self.history.drain()
        if recs:
            self.history_tab.add_records(recs)
            if self.cfg["ui"]["notify"] and self.tray.running:
                r = recs[-1]
                more = f" (+{len(recs) - 1})" if len(recs) > 1 else ""
                self.tray.notify(f"{KIND_LABELS.get(r['kind'], r['kind'])}: {r['item']}{more}", "Bloqueado")

        # agenda mudou de estado? atualiza hosts
        eff = core.effective(self.cfg)
        if (tuple(eff["sites"]), eff["active"]) != self._hosts_key:
            self.sync_hosts()
        # sincronizacao periodica das listas online
        interval = self.cfg["remote"]["interval"] * 60
        if not self.syncing and time.time() - self.last_sync_try >= interval:
            self.start_sync()
        # uso (limites) salvo de tempos em tempos
        if self.monitor.usage_dirty and time.time() - self._last_save > 30:
            self.monitor.usage_dirty = False
            self._last_save = time.time()
            self.save()
        if self._ticks % 5 == 0:
            self.limits_tab.refresh()
            self.schedule_tab.update_state()
        self.update_status()

    # -------------------------------------------------------- saida / janela
    def on_close(self):
        if self.tray.running and self.cfg["ui"]["close_to_tray"]:
            self.withdraw()
            if not getattr(self, "_tray_tip", False):
                self._tray_tip = True
                self.tray.notify("O EasyBlock continua em execução na bandeja do sistema.")
            return
        self.request_quit()

    def request_quit(self):
        if not self.auth("Sair do app"):
            return
        if self.cfg["active"] and not messagebox.askyesno(
                core.APP_NAME, "Se fechar o app, aplicativos, termos e limites deixam de ser bloqueados "
                               "(os sites continuam bloqueados no arquivo hosts).\n\nFechar mesmo assim?"):
            return
        self.quit_now(stop_flag=True)

    def quit_now(self, stop_flag: bool = False):
        if stop_flag:
            core.set_stop_flag()  # saida intencional: o guardiao nao reabre
        self.save()
        self.tray.stop()
        self.destroy()

    # ------------------------------------------------------------ assistente
    def maybe_wizard(self):
        if self.cfg["first_run_done"]:
            return
        has_items = any(self.cfg[k] for k in core.KEYS)
        if not has_items:
            for cat in wizard_dialog(self):
                for key, preset_names in core.WIZARD[cat].items():
                    for name in preset_names:
                        self.tabs[key].add_items(core.PRESETS[key][name])
        self.cfg["first_run_done"] = True
        self.save()


def main(argv) -> int:
    if os.name != "nt":
        print("Este app funciona apenas no Windows.")
        return 1
    if not core.is_admin():
        core.relaunch_as_admin(argv)
        return 0
    if "--watchdog" in argv:
        core.run_watchdog()
        return 0
    if not core.acquire_instance():
        if "--minimized" not in argv:
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo(core.APP_NAME, "O EasyBlock já está em execução "
                                               "(veja o ícone na bandeja do sistema).")
            root.destroy()
        return 0
    core.clear_stop_flag()
    App(minimized="--minimized" in argv).mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

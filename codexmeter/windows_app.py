"""English Windows control panel. BLE and the daemon run in separate processes."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from .app_server import resolve_codex_binary
from .launch import app_command
from .settings import LOG_FILE


class MeterApp:
    def __init__(self, root: tk.Tk, *, tray_managed: bool = False) -> None:
        self.root = root
        root.title("CodexMeter")
        root.geometry("780x590")
        root.minsize(680, 500)
        self.results: queue.Queue = queue.Queue()
        self.busy = False
        self.codex = tk.StringVar(value="codex")
        self.short_id = tk.StringVar()
        self.alias = tk.StringVar(value="Desk")
        self.status = tk.StringVar(value="Ready — start the bridge, then scan for your display.")
        frame = ttk.Frame(root, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="CodexMeter", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Codex usage and task alerts on your Waveshare display").pack(anchor="w", pady=(0, 16))
        path_row = ttk.Frame(frame)
        path_row.pack(fill="x", pady=4)
        ttk.Label(path_row, text="Codex executable").pack(side="left", padx=(0, 10))
        ttk.Entry(path_row, textvariable=self.codex).pack(side="left", fill="x", expand=True)
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=10)
        for label, callback in [
            ("Start bridge", self.start), ("Stop bridge", self.stop),
            ("Status", lambda: self.command("status")),
            ("Read usage", lambda: self.command("once", "--codex-bin", self.codex.get())),
            ("Scan displays", lambda: self.command("devices", "scan")),
        ]:
            ttk.Button(actions, text=label, command=callback).pack(side="left", padx=(0, 5))
        register = ttk.Frame(frame)
        register.pack(fill="x", pady=4)
        ttk.Label(register, text="Display ID").pack(side="left")
        ttk.Entry(register, textvariable=self.short_id, width=10).pack(side="left", padx=8)
        ttk.Label(register, text="Name").pack(side="left")
        ttk.Entry(register, textvariable=self.alias, width=16).pack(side="left", padx=8)
        ttk.Button(register, text="Register display", command=self.adopt).pack(side="left")
        controls = ttk.Frame(frame)
        controls.pack(fill="x", pady=10)
        for label, args in [("Test alert", ("demo-alert", "CodexMeter is connected.")),
                            ("Screen on", ("screen-on",)), ("Screen off", ("screen-off",))]:
            ttk.Button(controls, text=label, command=lambda a=args: self.command(*a)).pack(side="left", padx=(0, 5))
        ttk.Button(controls, text="Open log", command=self.open_log).pack(side="left")
        ttk.Button(controls, text="Tokens / pricing", command=self.open_pricing).pack(side="left", padx=5)
        from .update_dialog import show_updates
        ttk.Button(controls, text="Updates", command=lambda: show_updates(self.root)).pack(side="left", padx=5)
        self.pricing_status = tk.StringVar()
        ttk.Label(frame, textvariable=self.pricing_status, wraplength=720, foreground="#9b5800").pack(anchor="w")
        self.pricing_poll_count = 0
        ttk.Label(frame, textvariable=self.status, wraplength=720).pack(anchor="w", pady=6)
        self.output = tk.Text(frame, wrap="word", font=("Consolas", 10), height=15, state="disabled")
        self.output.pack(fill="both", expand=True)
        footer = ("Closing this window hides it. Use the tray icon to reopen it or quit CodexMeter."
                  if tray_managed else "Closing this window leaves the bridge running. Stop it with Stop bridge.")
        ttk.Label(frame, text=footer).pack(anchor="w", pady=(10, 0))
        self.poll_after = root.after(100, self.poll)
        root.bind("<Destroy>", self._on_destroy, add="+")

    def _on_destroy(self, event):
        if event.widget is self.root:
            self.root.after_cancel(self.poll_after)

    def launch_job(self, job) -> None:
        if self.busy:
            self.status.set("Please wait for the current operation to finish.")
            return
        self.busy = True
        self.status.set("Working…")
        def worker():
            try:
                self.results.put((True, job()))
            except Exception as exc:
                self.results.put((False, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def command(self, *args: str) -> None:
        def run():
            proc = subprocess.run(
                app_command("cli", *args),
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=120, creationflags=subprocess.CREATE_NO_WINDOW,
                env={**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"},
            )
            if proc.returncode:
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
            return proc.stdout.strip()
        self.launch_job(run)

    def start(self) -> None:
        requested_executable = self.codex.get()
        executable = resolve_codex_binary(requested_executable)
        if not executable:
            self.status.set("Codex was not found. Enter the path to codex.exe.")
            return
        def run():
            from .events import send_event
            try:
                status = asyncio.run(send_event({"type": "ping"}))
                if status.get("ok"):
                    return "Bridge is already running."
            except (OSError, ValueError, TimeoutError):
                pass
            from .launch import launch_background
            launch_background(app_command("daemon", "--codex-bin", requested_executable))
            import time
            for _ in range(300):
                time.sleep(0.1)
                try:
                    if asyncio.run(send_event({"type": "ping"})).get("ok"):
                        return "Bridge started. Read usage to check Codex, or scan for a flashed display."
                except (OSError, ValueError, TimeoutError):
                    pass
            raise RuntimeError(f"Bridge did not become ready. Check {LOG_FILE}.")
        self.launch_job(run)

    def stop(self) -> None:
        from .events import send_event
        self.launch_job(lambda: json.dumps(asyncio.run(send_event({"type": "shutdown"})), indent=2))

    def adopt(self) -> None:
        self.command("devices", "adopt", self.short_id.get().strip(), "--alias", self.alias.get().strip())

    def open_log(self) -> None:
        if LOG_FILE.exists():
            os.startfile(LOG_FILE)
        else:
            self.status.set("No log yet. Start the bridge first.")

    def poll(self) -> None:
        self.pricing_poll_count += 1
        if self.pricing_poll_count % 50 == 1:
            from .pricing import PricingStore
            state = PricingStore().status()
            self.pricing_status.set(state["message"] if state.get("state") != "current" else "")
        try:
            success, text = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.status.set("Done. After registering a display, stop and start the bridge." if success else "Operation failed — details below.")
            self.output.configure(state="normal")
            self.output.delete("1.0", "end")
            self.output.insert("end", text)
            self.output.configure(state="disabled")
        self.poll_after = self.root.after(100, self.poll)

    def open_pricing(self):
        import webbrowser
        from .pricing import PricingStore, PUBLIC_URL
        store = PricingStore()
        window = tk.Toplevel(self.root)
        window.title("CodexMeter — Tokens and pricing history")
        window.geometry("900x650")
        ttk.Label(window, text="API-equivalent token costs (USD), not subscription charges", font=("Segoe UI", 13, "bold")).pack(pady=8)
        ttk.Label(window, text="Standard rates; context length accounted for. Unknown models, older dates and cache writes without retention are unpriced.", wraplength=860).pack()
        state_label = tk.StringVar()
        ttk.Label(window, textvariable=state_label, wraplength=860).pack(pady=6)
        actions = ttk.Frame(window)
        actions.pack(fill="x", padx=10)
        box = tk.Text(window, wrap="word", font=("Consolas", 10))
        box.pack(fill="both", expand=True, padx=10, pady=10)
        def refresh():
            state_label.set(store.status()["message"])
            lines = []
            try:
                report = json.loads((store.root / "usage-report.json").read_text(encoding="utf-8"))
                for key, title in (("today", "Today"), ("week", "Last 7 days")):
                    part = report[key]
                    lines.append(f"{title} — recorded total {part['total_tokens']:,} tokens")
                    for label, tokens, cost in zip(("Input (uncached)", "Cached input", "Output"), part["tokens"], part["cost_micro_usd"]):
                        lines.append(f"  {label:18} {tokens:>15,}   ${cost / 1e6:,.4f}")
                    lines.append(f"  Unpriced tokens: {part['unpriced_tokens']:,}; breakdown unavailable: {part['unknown_tokens']:,}")
                    for model, item in sorted(part["models"].items()):
                        lines.append(f"  {model}: {item['tokens']:,} tokens; priced subtotal ${item['cost_usd']:,.4f}; unpriced {item['unpriced_tokens']:,}  {'; '.join(item['reasons'])}")
                    lines.append("")
            except (OSError, ValueError, KeyError):
                lines.append("No token report yet. Start the bridge or use Read usage.")
            lines.append("Pricing history (effective UTC; new revisions do not change prior dates):")
            for revision in store.revisions():
                lines.append(f"  {revision['effective_from']} — {len(revision['prices'])} models; source {revision['source_sha256'][:12]}")
            box.configure(state="normal")
            box.delete("1.0", "end")
            box.insert("end", "\n".join(lines))
            box.configure(state="disabled")
        def check():
            state_label.set("Checking official pricing source…")
            result = queue.Queue()
            def worker():
                try:
                    result.put(store.check(force=True))
                except Exception as exc:
                    result.put({"message": str(exc)})
            threading.Thread(target=worker, daemon=True).start()
            def poll_check():
                if not window.winfo_exists():
                    return
                try:
                    outcome = result.get_nowait()
                except queue.Empty:
                    window.after(100, poll_check)
                    return
                refresh()
                state_label.set(outcome["message"])
            window.after(100, poll_check)
        def review():
            try:
                if store.status().get("state") != "changed":
                    raise ValueError("Check the source first. There is no validated changed table to accept.")
                candidate = json.loads((store.root / "pending.json").read_text(encoding="utf-8"))
                previous = store.revisions()[-1]["prices"]
                changes = {m: {"saved": previous.get(m), "new": candidate["prices"].get(m)}
                           for m in sorted(previous.keys() | candidate["prices"].keys())
                           if previous.get(m) != candidate["prices"].get(m)}
                dialog = tk.Toplevel(window)
                dialog.title("Review updated official pricing")
                dialog.geometry("780x550")
                ttk.Label(dialog, text="USD per million; order: uncached input, cached input, output.\nReview the official source for changed terms as well as rates.").pack(pady=8)
                details = tk.Text(dialog, wrap="word")
                details.pack(fill="both", expand=True)
                details.insert("end", json.dumps(changes, indent=2) if changes else "The source text changed, but the parsed Standard prices are unchanged. Review the source for changes to terms/context thresholds.")
                details.configure(state="disabled")
                ttk.Button(dialog, text="Open official source", command=lambda: webbrowser.open(PUBLIC_URL)).pack(pady=4)
                def accept():
                    try:
                        store.accept_pending(candidate["source_sha256"])
                        dialog.destroy()
                        refresh()
                    except Exception as exc:
                        messagebox.showerror("Pricing update", str(exc), parent=dialog)
                ttk.Button(dialog, text="Accept reviewed rates from now", command=accept).pack(pady=6)
            except Exception as exc:
                messagebox.showerror("Pricing review", str(exc), parent=window)
        for label, action in (("Refresh report", refresh), ("Check official source", check), ("Review pricing update", review), ("Open official source", lambda: webbrowser.open(PUBLIC_URL))):
            ttk.Button(actions, text=label, command=action).pack(side="left", padx=3)
        refresh()


def show_pricing_notice(root, review):
    """Small modeless dialog; opening a notification never accepts rates."""
    import webbrowser
    from .pricing import PricingStore, PUBLIC_URL
    dialog = tk.Toplevel(root)
    dialog.title("CodexMeter — Pricing source status")
    dialog.resizable(False, False)
    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Pricing source review", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 12))
    ttk.Label(frame, text=PricingStore().review_summary(), wraplength=520, justify="left").pack(anchor="w")
    actions = ttk.Frame(frame)
    actions.pack(anchor="e", pady=(16, 0))
    def open_review():
        dialog.destroy()
        review()
    ttk.Button(actions, text="Rates and history…", command=open_review).pack(side="left", padx=4)
    ttk.Button(actions, text="Official pricing page", command=lambda: webbrowser.open(PUBLIC_URL)).pack(side="left", padx=4)
    ttk.Button(actions, text="Close", command=dialog.destroy).pack(side="left", padx=4)
    dialog.lift()
    dialog.focus_force()
    return dialog


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("This control panel requires Windows.")
    root = tk.Tk()
    ttk.Style().theme_use("vista")
    MeterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

"""Release status and shared notification landing dialog, on the Tk thread."""
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

from .updates import UpdateStore, CURRENT_RELEASE, APP_VERSION


def show_updates(root, store=None):
    store = store if store is not None else UpdateStore()
    dialog = tk.Toplevel(root)
    dialog.title("CodexMeter — Updates")
    dialog.resizable(False, False)
    frame = ttk.Frame(dialog, padding=20)
    frame.pack()
    ttk.Label(frame, text=f"Windows app {APP_VERSION}\nRelease baseline: {CURRENT_RELEASE}").pack(anchor="w")
    status = tk.StringVar(value=store.display_message())
    ttk.Label(frame, textvariable=status, wraplength=500).pack(anchor="w", pady=14)
    automatic = tk.BooleanVar(value=store.automatic_enabled())
    def save_preference():
        try:
            store.set_automatic(automatic.get())
            status.set(store.display_message())
        except OSError:
            automatic.set(store.automatic_enabled())
            messagebox.showerror("Update checks", "Could not save this preference. The previous setting remains active.", parent=dialog)
    ttk.Checkbutton(frame, text="Automatically check GitHub releases", variable=automatic,
                    command=save_preference, name="automatic_updates").pack(anchor="w", pady=(0, 8))
    ttk.Label(frame, text="When off, no background GitHub release requests are made.\nManual checks and opening GitHub still contact GitHub.\nOpenAI pricing-page checks are separate and remain enabled.", wraplength=500).pack(anchor="w", pady=(0, 8))
    ttk.Label(frame, text="Checks daily while running. Notifications appear once per new release.\nNo automatic downloads, installation or firmware flashing.", wraplength=500).pack(anchor="w")
    actions = ttk.Frame(frame)
    actions.pack(pady=(16, 0))
    results = queue.Queue()
    def check():
        button.configure(state="disabled")
        status.set("Checking GitHub releases…")
        def worker():
            try:
                results.put(store.check(force=True)["message"])
            except Exception:
                results.put("Release check could not be saved. Try again later.")
        threading.Thread(target=worker, daemon=True).start()
        def poll():
            if not dialog.winfo_exists():
                return
            try:
                status.set(results.get_nowait())
                button.configure(state="normal")
            except queue.Empty:
                dialog.after(100, poll)
        dialog.after(100, poll)
    button = ttk.Button(actions, text="Check now", command=check)
    button.pack(side="left", padx=4)
    ttk.Button(actions, text="Open GitHub release", command=lambda: webbrowser.open(store.release_url())).pack(side="left", padx=4)
    ttk.Button(actions, text="Close", command=dialog.destroy).pack(side="left", padx=4)
    dialog.lift()
    dialog.focus_force()
    return dialog


def show_notifications(root, pricing, updates):
    # Windows balloon callbacks carry no per-notification ID. Show both statuses
    # so an older pricing balloon can never silently route to an update instead.
    from .pricing import PricingStore
    dialog = tk.Toplevel(root)
    dialog.title("CodexMeter — Notifications")
    frame = ttk.Frame(dialog, padding=20)
    frame.pack()
    ttk.Label(frame, text="Pricing source", font=("Segoe UI", 11, "bold")).pack(anchor="w")
    ttk.Label(frame, text=PricingStore().review_summary(), wraplength=520).pack(anchor="w", pady=8)
    ttk.Button(frame, text="Pricing details…", command=pricing).pack(anchor="w")
    ttk.Separator(frame).pack(fill="x", pady=12)
    ttk.Label(frame, text="App releases", font=("Segoe UI", 11, "bold")).pack(anchor="w")
    ttk.Label(frame, text=UpdateStore().display_message(), wraplength=520).pack(anchor="w", pady=8)
    ttk.Button(frame, text="Update details…", command=updates).pack(anchor="w")
    ttk.Button(frame, text="Close", command=dialog.destroy).pack(anchor="e", pady=(12, 0))
    dialog.lift()
    dialog.focus_force()
    return dialog

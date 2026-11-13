"""Per-display status and capability-aware controls over authenticated local IPC."""
from __future__ import annotations
import asyncio
import queue
import threading


def device_row(device):
    state = "Connected" if device.get("connected") else "Disconnected"
    if device.get("compatibility") == "incompatible":
        state = "Incompatible protocol"
    return (device.get("label") or device["device_id"], device.get("model") or "Legacy / unknown",
            device.get("firmware") or "Unknown", state,
            device.get("last_error") or (f"ACK {device['last_ack_age_sec']}s ago" if device.get("last_ack_age_sec") is not None else "No acknowledgement yet"))


def show_devices(parent):
    import tkinter as tk
    from tkinter import ttk
    from .events import send_event
    window = tk.Toplevel(parent)
    window.title("CodexMeter — Displays")
    window.geometry("940x370")
    ttk.Label(window, text="Select a display to control it. Other displays keep their own settings.").pack(pady=10)
    columns=("name","model","firmware","state","detail")
    tree=ttk.Treeview(window,columns=columns,show="headings",height=7,selectmode="browse")
    for key,title in zip(columns,("Display","Model","Firmware","Connection","Last result")):
        tree.heading(key,text=title); tree.column(key,width=170)
    tree.pack(fill="both",expand=True,padx=10)
    status=tk.StringVar(value="Loading…")
    row=ttk.Frame(window); row.pack(fill="x",padx=10,pady=8)
    brightness=tk.IntVar(value=70); rotation=tk.StringVar(value="0")
    ttk.Spinbox(row,from_=10,to=100,textvariable=brightness,width=5).pack(side="left")
    results=queue.Queue(); devices={}; closed=False; refreshing=False
    buttons={}
    def launch(event,tag):
        def work():
            try: results.put((tag,asyncio.run(send_event(event))))
            except Exception as exc: results.put((tag,{"ok":False,"error":str(exc)}))
        threading.Thread(target=work,daemon=True).start()
    def control(command,value):
        selection=tree.selection()
        if not selection: return
        try: chosen=value()
        except (ValueError,tk.TclError): status.set("Enter a valid value."); return
        launch({"type":"device_control","device_id":selection[0],"command":command,"value":chosen},"control")
    buttons['brightness']=ttk.Button(row,text="Set brightness",command=lambda:control("brightness",brightness.get))
    buttons['brightness'].pack(side="left",padx=5)
    ttk.Combobox(row,textvariable=rotation,values=("0","90","180","270"),state="readonly",width=5).pack(side="left")
    buttons['rotation']=ttk.Button(row,text="Set rotation",command=lambda:control("rotation",lambda:int(rotation.get())))
    buttons['rotation'].pack(side="left",padx=5)
    for key,on in (("on",True),("off",False)):
        buttons[key]=ttk.Button(row,text=f"Screen {key}",command=lambda v=on:control("screen",lambda:v))
        buttons[key].pack(side="left",padx=5)
    def selected(_event=None):
        selection=tree.selection(); device=devices.get(selection[0],{}) if selection else {}
        caps=device.get("capabilities")
        for key,button in buttons.items():
            cap="screen" if key in ("on","off") else key
            allowed=bool(device) and device.get("compatibility")!='incompatible' and ((caps is None and cap=='screen') or (caps is not None and cap in caps))
            button.configure(state="normal" if allowed else "disabled")
    tree.bind('<<TreeviewSelect>>',selected); selected()
    ttk.Label(window,textvariable=status,wraplength=900).pack(padx=10,pady=5)
    def refresh():
        nonlocal refreshing
        if not closed and not refreshing:
            refreshing=True; launch({"type":"ping"},"status")
    def poll():
        nonlocal refreshing
        if closed: return
        try:
            while True:
                tag,result=results.get_nowait()
                if tag=='status':
                    refreshing=False
                    if result.get('ok'):
                        new={d['device_id']:d for d in result.get('ble',{}).get('devices',[])}
                        devices.clear();devices.update(new)
                        for item in tree.get_children():
                            if item not in new: tree.delete(item)
                        for key,device in new.items():
                            if tree.exists(key): tree.item(key,values=device_row(device))
                            else: tree.insert('', 'end',iid=key,values=device_row(device))
                        selected()
                        status.set("No enabled displays. Register one in the control panel." if not new else "Settings apply only to the selected display.")
                    else: status.set(result.get('error','Companion unavailable'))
                else: status.set("Command queued; connection details show delivery status." if result.get('ok') else result.get('error','Command rejected'))
        except queue.Empty: pass
        window.after(150,poll)
    def timer():
        if not closed: refresh();window.after(2000,timer)
    def close():
        nonlocal closed
        closed=True;window.destroy()
    window.protocol('WM_DELETE_WINDOW',close)
    def destroyed(event):
        nonlocal closed
        if event.widget is window: closed=True
    window.bind('<Destroy>',destroyed)
    timer();poll()

"""Small Tk control panel; serial IO stays on one worker thread."""
import json
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
try:
    from .pedalctl import Client, CommandRejected, open_link, set_command
except ImportError:
    from pedalctl import Client, CommandRejected, open_link, set_command

def main():
    root = tk.Tk()
    root.title("RP2350 双踏板调参 · 开发版")
    root.geometry("800x600")
    jobs, events = queue.Queue(), queue.Queue()
    connected = False
    latest = None
    notice = ""

    def worker():
        link = None
        while True:
            kind, value = jobs.get()
            try:
                if kind == "stop":
                    if link: link.close()
                    return
                if kind == "connect":
                    if link: link.close()
                    link = open_link(value)
                elif kind == "command":
                    if not link: raise RuntimeError("请先连接")
                    try:
                        Client(link).request(value)
                    except CommandRejected as exc:
                        current = Client(link).get()
                        events.put(("state", current, False))
                        message = "设备拒绝操作，连接保持：" + str(exc)
                        if value.startswith("CAL ") and value.endswith(" END"):
                            axis = int(value.split()[1])
                            if current.get("calibration_axis") != axis:
                                message = "该轴尚未开始校准：先全松开点击①，再踩到底保持后点击②。连接保持。"
                            else:
                                message = "校准未通过：保持踩到底再点②；两端原始值差需至少128。可重试或取消校准，连接保持。"
                        elif value == "SAVE":
                            message = "保存未成功：结束校准、松开双踏板并等待回零后重试。连接保持。"
                        events.put(("rejected", message, False))
                        continue
                if link:
                    events.put(("state", Client(link).get(), kind != "poll"))
            except Exception as exc:
                if link: link.close()
                link = None
                events.put(("error", str(exc), True))

    threading.Thread(target=worker, daemon=True).start()
    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Type-C 接电脑；确认传感器电压后再接 GP26 / GP27。", font=("Microsoft YaHei UI", 11)).pack(anchor="w")
    top = ttk.Frame(frame); top.pack(fill="x", pady=12)
    ttk.Label(top, text="串口").pack(side="left")
    port = ttk.Entry(top, width=14); port.pack(side="left", padx=8)
    ttk.Button(top, text="连接 / 重连", command=lambda: jobs.put(("connect", port.get().strip()))).pack(side="left")
    status = tk.StringVar(value="未连接；所有参数仅点击“应用”后写入RAM，点击“保存”才写Flash。")
    ttk.Label(frame, textvariable=status, wraplength=760).pack(anchor="w", pady=6)
    rows = []
    for axis, title in enumerate(("油门 · GP26", "刹车 · GP27")):
        box = ttk.LabelFrame(frame, text=title, padding=10); box.pack(fill="x", pady=8)
        telemetry = tk.StringVar(value="原始值 —  /  滤波值 —  /  输出 —")
        ttk.Label(box, textvariable=telemetry).grid(row=0, column=0, columnspan=5, sticky="w")
        controls = []
        for col, (label, lo, hi, initial) in enumerate((("触发 %", 0.1, 50, 3), ("释放 %", 0, 49, 1), ("曲线 γ", 1, 4, 1 if axis==0 else 2), ("平均窗口", 1, 8, 4))):
            ttk.Label(box, text=label).grid(row=1, column=col)
            var = tk.DoubleVar(value=initial)
            tk.Scale(box, from_=lo, to=hi, resolution=1 if col==3 else 0.1, orient="horizontal", variable=var, length=145).grid(row=2,column=col)
            controls.append(var)
        def apply(i=axis, values=controls):
            try:
                command = set_command(i, round(values[0].get()*100), round(values[1].get()*100), round(values[2].get()*100), round(values[3].get()))
                jobs.put(("command", command))
            except ValueError as exc:
                messagebox.showerror("参数错误", str(exc))
        ttk.Button(box, text="应用参数", command=apply).grid(row=2,column=4,padx=8)
        ttk.Button(box, text="① 全松开：开始校准", command=lambda i=axis: jobs.put(("command", f"CAL {i} BEGIN"))).grid(row=3,column=0,columnspan=2,sticky="w")
        ttk.Button(box, text="② 踩到底并保持：完成", command=lambda i=axis: jobs.put(("command", f"CAL {i} END"))).grid(row=3,column=2,columnspan=2,sticky="w")
        ttk.Button(box, text="取消校准", command=lambda i=axis: jobs.put(("command", f"CAL {i} CANCEL"))).grid(row=3,column=4)
        rows.append((telemetry, controls))
    actions = ttk.Frame(frame); actions.pack(fill="x", pady=10)
    for label, command in (("手柄模式", "MODE JOYSTICK"), ("键盘 W/S 模式", "MODE KEYBOARD"), ("保存到 Flash", "SAVE")):
        ttk.Button(actions, text=label, command=lambda c=command: jobs.put(("command", c))).pack(side="left", padx=4)
    def export():
        if latest is None: return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            with open(path, "w", encoding="utf-8") as out:
                json.dump(latest, out, ensure_ascii=False, indent=2)
    ttk.Button(actions, text="导出 JSON", command=export).pack(side="left", padx=4)
    ttk.Label(frame, text="校准后松开双踏板，等待回零，再保存。切换模式后也需松开才能重新输出。", wraplength=760).pack(anchor="w")
    def pump():
        nonlocal connected, latest, notice
        while not events.empty():
            kind, value, refresh = events.get_nowait()
            if kind == "error":
                connected = False
                notice = ""
                status.set("连接已关闭：" + value + "；修正操作或接线后点击重连。")
                continue
            if kind == "rejected":
                notice = value
                status.set(value)
                continue
            connected = True; latest = value
            if refresh:
                notice = ""
            status.set(f"{value['mode']}  |  已使能={value['armed']}  |  校准轴={value['calibration_axis']}  |  保存前需回零" + ("\n" + notice if notice else ""))
            for i, (telemetry, values) in enumerate(rows):
                axis_config = value["axes"][i]
                telemetry.set(f"原始 {value['raw'][i]}  /  滤波 {value['filtered'][i]}  /  输出 {value['output'][i]}  /  已校准 {axis_config['calibrated']}")
                if refresh:
                    for var, key, divisor in zip(values, ("on", "off", "gamma", "window"), (100,100,100,1)):
                        var.set(axis_config[key]/divisor)
        if connected and jobs.empty(): jobs.put(("poll", None))
        root.after(200, pump)
    def close():
        jobs.put(("stop", None)); root.destroy()
    root.protocol("WM_DELETE_WINDOW", close)
    root.update_idletasks()
    root.minsize(max(800, root.winfo_reqwidth()), max(600, root.winfo_reqheight()))
    pump(); root.mainloop()

if __name__ == "__main__":
    main()

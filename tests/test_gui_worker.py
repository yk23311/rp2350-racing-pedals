import json
import unittest
from unittest.mock import patch
import tkinter as tk
from tools import pedal_gui


class SerialLink:
    def __init__(self, responses):
        self.responses = list(responses)
        self.commands = []
        self.closed = False

    def write(self, data):
        self.commands.append(data.decode().strip())
        return len(data)

    def readline(self, size=768):
        return self.responses.pop(0) if self.responses else b""

    def close(self):
        self.closed = True


def state(calibration_axis=0):
    return ("OK " + json.dumps({"protocol": 1, "calibration_axis": calibration_axis}) + "\n").encode()


class GuiWorkerTests(unittest.TestCase):
    def exercise(self, button_text, responses, repeats=2):
        link = SerialLink(responses)
        targets = []
        real_tk = tk.Tk

        class Thread:
            def __init__(self, target, **kwargs):
                targets.append(target)
            def start(self):
                pass

        def hidden_root():
            try:
                root = real_tk()
            except tk.TclError as exc:
                self.skipTest(str(exc))
            root.withdraw()
            return root

        def inspect(root):
            def descendants(parent):
                for widget in parent.winfo_children():
                    yield widget
                    yield from descendants(widget)
            widgets = list(descendants(root))
            entry = next(w for w in widgets if w.winfo_class() == "TEntry")
            entry.insert(0, "COM_TEST")
            next(w for w in widgets if w.winfo_class() == "TButton" and w.cget("text") == "连接 / 重连").invoke()
            button = next(w for w in widgets if w.winfo_class() == "TButton" and button_text in w.cget("text"))
            for _ in range(repeats):
                button.invoke()
            # The real close handler enqueues stop. Run queued IO synchronously.
            root.tk.call(root.protocol("WM_DELETE_WINDOW"))
            targets[0]()

        with patch.object(tk, "Tk", hidden_root), patch.object(real_tk, "mainloop", inspect), patch.object(pedal_gui.threading, "Thread", Thread), patch.object(pedal_gui, "open_link", return_value=link):
            pedal_gui.main()
        return link

    def test_rejected_calibration_can_retry_without_reconnect(self):
        link = self.exercise("踩到底并保持", [state(), b"ERR STATE_OR_VALUE\n", state(), b"OK\n", state(-1)])
        self.assertEqual(link.commands, ["GET", "CAL 0 END", "GET", "CAL 0 END", "GET"])
        self.assertTrue(link.closed)  # only at intentional application shutdown

    def test_rejected_save_can_retry_without_reconnect(self):
        link = self.exercise("保存到 Flash", [state(-1), b"ERR STATE_OR_VALUE\n", state(-1), b"OK\n", state(-1)])
        self.assertEqual(link.commands, ["GET", "SAVE", "GET", "SAVE", "GET"])

    def test_timeout_still_closes_connection(self):
        link = self.exercise("踩到底并保持", [state(), b""], repeats=1)
        self.assertEqual(link.commands, ["GET", "CAL 0 END"])
        self.assertTrue(link.closed)

    def test_host_logs_allow_get_and_save_without_disconnect(self):
        log = b"[HOST] state=3 reports=500\r\n"
        link = self.exercise("保存到 Flash", [log, state(-1), log, b"OK\n", log, state(-1)], repeats=1)
        self.assertEqual(link.commands, ["GET", "SAVE", "GET"])


if __name__ == "__main__":
    unittest.main()

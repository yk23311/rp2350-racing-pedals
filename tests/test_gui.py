import unittest
from unittest.mock import patch
import tkinter as tk
from tools import pedal_gui

class GuiLayoutTests(unittest.TestCase):
    def test_initial_window_fits_content(self):
        real_tk = tk.Tk
        def hidden_root():
            try:
                root = real_tk()
            except tk.TclError as exc:
                self.skipTest(f"Tk display unavailable: {exc}")
            root.withdraw()
            return root
        def inspect(root):
            try:
                root.update_idletasks()
                self.assertGreaterEqual(root.winfo_width(), root.winfo_reqwidth())
                self.assertGreaterEqual(root.winfo_height(), root.winfo_reqheight())
            finally:
                root.destroy()
        with patch.object(tk, "Tk", hidden_root), patch.object(real_tk, "mainloop", inspect), patch.object(pedal_gui.threading.Thread, "start"):
            pedal_gui.main()

if __name__ == "__main__":
    unittest.main()

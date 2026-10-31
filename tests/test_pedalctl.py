import io
import unittest
from tools.pedalctl import Client, ProtocolError, set_command

class Link:
    def __init__(self, response):
        self.response = response
        self.written = b""
    def write(self, data):
        self.written += data
        return len(data)
    def readline(self, size=768):
        return self.response

class ClientTests(unittest.TestCase):
    def test_synchronize_discards_stale_responses(self):
        class QueuedLink(Link):
            def __init__(self):
                super().__init__(None)
                self.lines = [b'garbage\n', b'OK {"raw":[999,999]}\n', b'OK {"sync":"0123456789abcdef0123456789abcdef"}\n']
            def readline(self, size=768):
                return self.lines.pop(0) if self.lines else b''
        link = QueuedLink()
        Client(link).synchronize("0123456789abcdef0123456789abcdef")
        self.assertEqual(link.written, b"PING 0123456789abcdef0123456789abcdef\n")
        self.assertEqual(link.lines, [])
    def test_synchronize_timeout(self):
        with self.assertRaises(TimeoutError):
            Client(Link(b'')).synchronize("0123456789abcdef0123456789abcdef")
    def test_synchronize_handles_inflight_prefix_without_newline(self):
        token = "0123456789abcdef0123456789abcdef"
        link = Link(b'OK {"protocol":1,"old_inflight_fragment":' + f'OK {{"sync":"{token}"}}\n'.encode())
        Client(link).synchronize(token)
    def test_get(self):
        link = Link(b'OK {"protocol":1,"raw":[10,20]}\n')
        self.assertEqual(Client(link).get()["raw"], [10, 20])
        self.assertEqual(link.written, b"GET\n")
    def test_ok(self):
        self.assertIsNone(Client(Link(b"OK\n")).request("SAVE"))
    def test_device_error(self):
        with self.assertRaisesRegex(ProtocolError, "STATE"):
            Client(Link(b"ERR STATE_OR_VALUE\n")).request("SAVE")
    def test_timeout(self):
        with self.assertRaises(TimeoutError):
            Client(Link(b"")).request("GET")
    def test_truncated_and_bad_response(self):
        for response in [b"OK {}", b"OK {bad}\n", b"OK []\n", b"WHAT\n", b"OK \xff\n"]:
            with self.subTest(response=response), self.assertRaises(ProtocolError):
                Client(Link(response)).request("GET")
    def test_reject_injection(self):
        for cmd in ["GET\nSAVE", "GET\rSAVE", "GET\0", "x"*128]:
            link = Link(b"OK\n")
            with self.assertRaises(ValueError):
                Client(link).request(cmd)
            self.assertEqual(link.written, b"")
    def test_protocol_version(self):
        with self.assertRaises(ProtocolError):
            Client(Link(b'OK {"protocol":99}\n')).get()
    def test_set_validation(self):
        self.assertEqual(set_command(1,300,100,200,4), "SET 1 300 100 200 4")
        for args in [(2,300,100,200,4),(0,100,300,200,4),(0,300,100,99,4),(0,300,100,200,9),(0,300.5,100,200,4)]:
            with self.assertRaises(ValueError):
                set_command(*args)

if __name__ == "__main__":
    unittest.main()

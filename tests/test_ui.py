"""
Unit tests for VoxelMem UI Surfaces (TUI Braille Radar & Web HUD Server).
"""

import unittest
import os
import json
import urllib.request
import threading
import time

from voxelmem.tui import BrailleRadarCanvas, VoxelMemTUI, render_sparkline
from voxelmem.web import ThreadedHTTPServer, VoxelMemHTTPHandler


class TestBrailleRadar(unittest.TestCase):

    def test_canvas_initialization(self):
        canvas = BrailleRadarCanvas(cols=20, rows=10)
        self.assertEqual(canvas.pixel_width, 40)
        self.assertEqual(canvas.pixel_height, 40)

    def test_canvas_set_pixel(self):
        canvas = BrailleRadarCanvas(cols=10, rows=10)
        canvas.set_pixel(0, 0, True)
        rendered = canvas.render()
        # Non-empty char at (0,0)
        self.assertNotEqual(rendered[0][0], "⠀")

    def test_sparkline_generation(self):
        vals = [10.0, 20.0, 50.0, 80.0, 100.0]
        spark = render_sparkline(vals, length=5)
        self.assertEqual(len(spark), 5)
        self.assertEqual(spark[-1], "█")


class TestWebServer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.port = 8990
        cls.server = ThreadedHTTPServer(("127.0.0.1", cls.port), VoxelMemHTTPHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_api_status_endpoint(self):
        url = f"http://127.0.0.1:{self.port}/api/status"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertEqual(data["status"], "running")
            self.assertIn("version", data)

    def test_api_snapshot_endpoint(self):
        url = f"http://127.0.0.1:{self.port}/api/snapshot"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertIn("pid", data)
            self.assertIn("regions", data)
            self.assertIn("voxels", data)

    def test_api_simulate_endpoint(self):
        url = f"http://127.0.0.1:{self.port}/api/simulate"
        req = urllib.request.Request(url, data=b"workload=leak", headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertEqual(data["current_workload"], "leak")


if __name__ == "__main__":
    unittest.main()

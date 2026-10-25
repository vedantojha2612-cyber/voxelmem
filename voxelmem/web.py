"""
VoxelMem Web HUD Server: REST API & 3D WebGL Hologram Server.
Pure Python Standard Library (Zero external dependencies).
"""

from __future__ import annotations
import http.server
import json
import os
import socketserver
import sys
import urllib.parse
from typing import Dict, Any, Optional

from .engine import MemoryTelemetryEngine
from .simulator import MemoryWorkloadSimulator
from .models import (
    ProcessMemorySnapshot,
    MemoryRegionType,
    REGION_COLORS,
    PAGE_SIZE,
)
from .fragmentation import hilbert_2d, map_address_to_voxel

WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "web")
if not os.path.exists(WEB_DIR):
    WEB_DIR = os.path.join(os.path.dirname(__file__), "web")


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Multi-threaded HTTP server for high-concurrency Web HUD and REST endpoints."""
    daemon_threads = True
    allow_reuse_address = True


class VoxelMemHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler serving the 3D WebGL Hologram HUD and REST APIs."""

    engine = MemoryTelemetryEngine()
    simulator = MemoryWorkloadSimulator()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def end_headers(self):
        """Inject OWASP security response headers."""
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob:;"
        )
        super().end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/status":
            self._send_json({
                "status": "online",
                "service": "VoxelMem 3D Spatial Virtual Memory Hologram",
                "version": "1.0.0",
                "pid": os.getpid(),
                "platform": sys.platform,
            })
            return

        if path == "/api/snapshot":
            raw_pid = query.get("pid", [None])[0]
            target_pid = int(raw_pid) if raw_pid and raw_pid.isdigit() else os.getpid()
            snapshot = self.engine.take_snapshot(pid=target_pid)
            self._send_json(snapshot.to_dict())
            return

        if path == "/api/simulate":
            workload = query.get("workload", ["fragment"])[0]
            if workload not in ("steady", "leak", "fragment", "burst"):
                workload = "fragment"
            metrics = self.simulator.simulate_tick(workload=workload)

            # Generate dynamic 3D voxel coordinates for simulation chunks
            chunks_data = []
            for i, c in enumerate(self.simulator.chunks[-128:]):
                order = 4
                hx, hy = hilbert_2d(i % 256, order=order)
                z_tier = 4 if c.is_allocated else 0
                if c.tag == "leak_object":
                    col = "#ff0055"
                elif not c.is_allocated:
                    col = "#1e293b"
                else:
                    col = "#00f3ff"

                chunks_data.append({
                    "address_hex": f"0x{c.address:012x}",
                    "size": c.size,
                    "is_allocated": c.is_allocated,
                    "tag": c.tag,
                    "age_ticks": c.age_ticks,
                    "x": hx - 8,
                    "y": hy - 8,
                    "z": z_tier,
                    "color": col,
                })

            response_data = {
                "metrics": metrics,
                "chunks": chunks_data,
                "total_chunks": len(self.simulator.chunks),
            }
            self._send_json(response_data)
            return

        if path == "/api/voxels":
            # Complete 3D spatial voxel map of the process
            snapshot = self.engine.take_snapshot()
            voxels = []
            for p in snapshot.sample_pages:
                voxels.append(p.to_dict())

            self._send_json({
                "pid": snapshot.pid,
                "process_name": snapshot.process_name,
                "vms_mb": round(snapshot.vms_bytes / (1024 * 1024), 2),
                "rss_mb": round(snapshot.rss_bytes / (1024 * 1024), 2),
                "heap_mb": round(snapshot.heap_bytes / (1024 * 1024), 2),
                "stack_kb": round(snapshot.stack_bytes / 1024, 2),
                "fragmentation_score": snapshot.fragmentation_score,
                "leak_probability_score": snapshot.leak_probability_score,
                "voxels": voxels,
            })
            return

        # Serve static HTML/JS from WEB_DIR
        super().do_GET()

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Silence verbose standard logging
        pass


def start_web_server(port: int = 8080, host: str = "0.0.0.0", open_browser: bool = False):
    """Launch the VoxelMem Web HUD HTTP server."""
    with ThreadedHTTPServer((host, port), VoxelMemHTTPHandler) as httpd:
        print(f"\033[92m✔ VoxelMem 3D WebGL Hologram active on http://localhost:{port}\033[0m")
        print(f"\033[90mPress Ctrl+C to terminate web server.\033[0m")
        if open_browser:
            import webbrowser
            webbrowser.open(f"http://localhost:{port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down VoxelMem web server.")


if __name__ == "__main__":
    p = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    start_web_server(port=p)

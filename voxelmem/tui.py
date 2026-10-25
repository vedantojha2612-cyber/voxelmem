"""
VoxelMem Cyberpunk ANSI & Braille Terminal Radar HUD.
Subpixel polar & Hilbert radar plotting, real-time RSS/Fragmentation sparklines, and memory telemetry.
Pure Python standard library (Zero external runtime dependencies).
"""

from __future__ import annotations
import math
import os
import sys
import time
import random
from typing import List, Optional, Tuple, Dict, Any

from .engine import MemoryTelemetryEngine
from .models import (
    ProcessMemorySnapshot,
    MemoryRegionType,
    REGION_COLORS,
    REGION_ANSI_COLORS,
    PAGE_SIZE,
)
from .fragmentation import hilbert_2d, map_address_to_voxel
from .simulator import MemoryWorkloadSimulator

# ANSI Styling & 24-bit Truecolor
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
CYAN = "\033[38;2;0;243;255m"
NEON_GREEN = "\033[38;2;0;255;136m"
AMBER = "\033[38;2;255;170;0m"
CRIMSON = "\033[38;2;255;0;85m"
VIOLET = "\033[38;2;112;0;255m"
AZURE = "\033[38;2;0;119;255m"
MAGENTA = "\033[38;2;255;0;187m"
DARK_GRAY = "\033[38;2;45;55;72m"
MID_GRAY = "\033[38;2;100;116;139m"
LIGHT_GRAY = "\033[38;2;203;213;225m"
WHITE = "\033[38;2;255;255;255m"
BG_DARK = "\033[48;2;10;14;23m"

SPARKLINE_BARS = [" ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]


def render_sparkline(values: List[float], max_val: Optional[float] = None) -> str:
    """Renders a unicode sparkline string from numeric values."""
    if not values:
        return ""
    high = max_val if max_val is not None else max(values)
    if high <= 0:
        high = 1.0
    res = []
    for v in values:
        idx = int((max(0.0, v) / high) * (len(SPARKLINE_BARS) - 1))
        idx = min(len(SPARKLINE_BARS) - 1, max(0, idx))
        res.append(SPARKLINE_BARS[idx])
    return "".join(res)


def format_bytes(b: int) -> str:
    """Format byte sizes for compact terminal display."""
    if b >= 1024 * 1024 * 1024:
        return f"{b / (1024**3):.2f} GB"
    if b >= 1024 * 1024:
        return f"{b / (1024**2):.2f} MB"
    if b >= 1024:
        return f"{b / 1024:.1f} KB"
    return f"{b} B"


class BrailleRadarCanvas:
    """Subpixel terminal canvas utilizing 2x4 Unicode Braille dot patterns (U+2800..U+28FF)."""

    def __init__(self, cols: int = 40, rows: int = 20):
        self.cols = cols
        self.rows = rows
        self.pixel_width = cols * 2
        self.pixel_height = rows * 4
        self.grid = [[0 for _ in range(self.pixel_width)] for _ in range(self.pixel_height)]
        self.color_grid = [[None for _ in range(cols)] for _ in range(rows)]

    def clear(self):
        for r in range(self.pixel_height):
            for c in range(self.pixel_width):
                self.grid[r][c] = 0
        for r in range(self.rows):
            for c in range(self.cols):
                self.color_grid[r][c] = None

    def set_pixel(self, x: int, y: int, color: str = CYAN):
        if 0 <= x < self.pixel_width and 0 <= y < self.pixel_height:
            self.grid[y][x] = 1
            cell_x = x // 2
            cell_y = y // 4
            self.color_grid[cell_y][cell_x] = color

    def draw_line(self, x0: int, y0: int, x1: int, y1: int, color: str = CYAN):
        """Bresenham's line algorithm for radar sweep & memory bus vectors."""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        cx, cy = x0, y0
        while True:
            self.set_pixel(cx, cy, color)
            if cx == x1 and cy == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                cx += sx
            if e2 < dx:
                err += dx
                cy += sy

    def draw_circle(self, cx: int, cy: int, radius: int, color: str = DARK_GRAY):
        """Midpoint circle algorithm for spatial memory rings."""
        x = radius
        y = 0
        err = 0
        while x >= y:
            for px, py in [
                (cx + x, cy + y), (cx + y, cy + x),
                (cx - y, cy + x), (cx - x, cy + y),
                (cx - x, cy - y), (cx - y, cy - x),
                (cx + y, cy - x), (cx + x, cy - y)
            ]:
                self.set_pixel(px, py, color)
            y += 1
            err += 1 + 2 * y
            if 2 * (err - x) + 1 > 0:
                x -= 1
                err += 1 - 2 * x

    def render_rows(self) -> List[str]:
        output_lines = []
        dot_offsets = [
            (0, 0, 0x01), (0, 1, 0x02), (0, 2, 0x04),
            (1, 0, 0x08), (1, 1, 0x10), (1, 2, 0x20),
            (0, 3, 0x40), (1, 3, 0x80),
        ]
        for r in range(self.rows):
            line = ""
            for c in range(self.cols):
                code = 0
                for dx, dy, bit in dot_offsets:
                    px = c * 2 + dx
                    py = r * 4 + dy
                    if 0 <= py < self.pixel_height and 0 <= px < self.pixel_width:
                        if self.grid[py][px]:
                            code |= bit

                char = chr(0x2800 + code) if code > 0 else " "
                col = self.color_grid[r][c] or DARK_GRAY
                line += f"{col}{char}{RESET}"
            output_lines.append(line)
        return output_lines


class VoxelMemTUI:
    """Cyberpunk Interactive Terminal Radar HUD for VoxelMem."""

    def __init__(self, pid: Optional[int] = None, workload: str = "fragment"):
        self.engine = MemoryTelemetryEngine(pid=pid)
        self.simulator = MemoryWorkloadSimulator()
        self.workload = workload
        self.canvas = BrailleRadarCanvas(cols=36, rows=18)
        self.rss_history: List[float] = []
        self.frag_history: List[float] = []
        self.max_history = 20
        self.sweep_angle = 0.0

    def step(self) -> Tuple[ProcessMemorySnapshot, Dict[str, Any]]:
        # Take real process snapshot
        snapshot = self.engine.take_snapshot()
        # Step allocator simulator
        sim_metrics = self.simulator.simulate_tick(workload=self.workload)

        # Update history
        self.rss_history.append(snapshot.rss_bytes / (1024 * 1024))
        if len(self.rss_history) > self.max_history:
            self.rss_history.pop(0)

        frag = snapshot.fragmentation_score
        if frag == 0:
            frag = sim_metrics["fragmentation_index"]
        self.frag_history.append(frag)
        if len(self.frag_history) > self.max_history:
            self.frag_history.pop(0)

        self.sweep_angle = (self.sweep_angle + 0.14) % (2 * math.pi)
        return snapshot, sim_metrics

    def render_frame(self, snapshot: ProcessMemorySnapshot, sim_metrics: Dict[str, Any]) -> str:
        self.canvas.clear()

        # Canvas dimensions
        pw = self.canvas.pixel_width
        ph = self.canvas.pixel_height
        cx = pw // 2
        cy = ph // 2
        radius = min(cx, cy) - 3

        # Draw concentric memory rings
        self.canvas.draw_circle(cx, cy, radius, DARK_GRAY)
        self.canvas.draw_circle(cx, cy, int(radius * 0.66), DARK_GRAY)
        self.canvas.draw_circle(cx, cy, int(radius * 0.33), DARK_GRAY)

        # Draw 16x16 Hilbert / Page Frame clusters
        for i, page in enumerate(snapshot.sample_pages[:120]):
            order = 4
            hx, hy = hilbert_2d(i % 256, order=order)
            # Map 16x16 space into canvas polar/cartesian zone
            px = int(cx + (hx - 8) * (radius / 10.0))
            py = int(cy + (hy - 8) * (radius / 10.0))

            color = CYAN
            if page.is_leak_suspect:
                color = CRIMSON
            elif page.is_fragmented:
                color = AMBER
            elif page.region_type == MemoryRegionType.STACK:
                color = NEON_GREEN
            elif page.region_type == MemoryRegionType.CODE:
                color = VIOLET
            elif page.region_type == MemoryRegionType.MMAP:
                color = AMBER

            self.canvas.set_pixel(px, py, color)

        # Draw dynamic allocator chunk dots from simulator
        for j, chunk in enumerate(self.simulator.chunks[-40:]):
            angle = (j * 0.35) % (2 * math.pi)
            dist = int(radius * (0.3 + (j % 5) * 0.13))
            c_x = int(cx + math.cos(angle) * dist)
            c_y = int(cy + math.sin(angle) * dist)
            c_col = CYAN if chunk.is_allocated else DARK_GRAY
            if chunk.tag == "leak_object":
                c_col = CRIMSON
            self.canvas.set_pixel(c_x, c_y, c_col)

        # Draw 15 FPS subpixel radar sweep line
        sweep_x = int(cx + math.cos(self.sweep_angle) * radius)
        sweep_y = int(cy + math.sin(self.sweep_angle) * radius)
        self.canvas.draw_line(cx, cy, sweep_x, sweep_y, CYAN)

        radar_rows = self.canvas.render_rows()

        # Telemetry metrics
        vms_str = format_bytes(snapshot.vms_bytes)
        rss_str = format_bytes(snapshot.rss_bytes)
        heap_str = format_bytes(snapshot.heap_bytes)
        stack_str = format_bytes(snapshot.stack_bytes)
        code_str = format_bytes(snapshot.code_bytes)

        frag_val = self.frag_history[-1] if self.frag_history else 0.0
        frag_color = NEON_GREEN if frag_val < 0.3 else AMBER if frag_val < 0.7 else CRIMSON
        frag_bar = render_sparkline(self.frag_history, max_val=1.0)
        rss_bar = render_sparkline(self.rss_history)

        leak_count = sim_metrics.get("leak_count", 0)
        leak_color = CRIMSON if leak_count > 0 else NEON_GREEN

        # Construct Cyberpunk Split-Pane HUD
        lines = []
        lines.append(f"{CYAN}{BOLD}╔══════════════════════════════════════════════════════════════════════════════════╗{RESET}")
        lines.append(f"{CYAN}{BOLD}║  VOXELMEM // 3D SPATIAL VIRTUAL MEMORY & HEAP ALLOCATION RADAR HUD             ║{RESET}")
        lines.append(f"{CYAN}{BOLD}╚══════════════════════════════════════════════════════════════════════════════════╝{RESET}")
        lines.append(f"{LIGHT_GRAY}  PID: {WHITE}{BOLD}{snapshot.pid:<6}{RESET}  PROC: {CYAN}{snapshot.process_name:<14}{RESET}  MODE: {AMBER}{self.workload.upper():<10}{RESET}  FREQ: {NEON_GREEN}15 FPS{RESET}")
        lines.append(f"{DARK_GRAY}{'─' * 82}{RESET}")

        # Assemble side-by-side: Left = Braille Radar, Right = Telemetry & Region Matrix
        sidebar_info = [
            f"{WHITE}{BOLD}SYSTEM MEMORY METRICS:{RESET}",
            f"  {LIGHT_GRAY}Virtual Size (VMS): {WHITE}{vms_str:<12}{RESET}",
            f"  {LIGHT_GRAY}Resident Set (RSS): {CYAN}{rss_str:<12}{RESET}",
            f"  {LIGHT_GRAY}Heap Allocation:    {CYAN}{heap_str:<12}{RESET}",
            f"  {LIGHT_GRAY}Execution Stack:    {NEON_GREEN}{stack_str:<12}{RESET}",
            f"  {LIGHT_GRAY}Executable Code:    {VIOLET}{code_str:<12}{RESET}",
            f"  {LIGHT_GRAY}Active 4KB Pages:   {WHITE}{snapshot.active_pages:<12}{RESET}",
            f"{DARK_GRAY}{'─' * 38}{RESET}",
            f"{WHITE}{BOLD}FRAGMENTATION & LEAKS:{RESET}",
            f"  {LIGHT_GRAY}Knuth-Wilson Index: {frag_color}{frag_val * 100:>5.1f}% {frag_bar}{RESET}",
            f"  {LIGHT_GRAY}RSS Trend (MB):     {CYAN}{rss_bar}{RESET}",
            f"  {LIGHT_GRAY}Shannon Entropy:    {WHITE}{sim_metrics.get('entropy', 0.0):.4f} bits{RESET}",
            f"  {LIGHT_GRAY}Active Chunks:      {WHITE}{sim_metrics.get('allocated_chunks', 0)} alloc / {sim_metrics.get('free_chunks', 0)} free{RESET}",
            f"  {LIGHT_GRAY}Leak Suspect Pool:  {leak_color}{leak_count} objects{RESET}",
            f"{DARK_GRAY}{'─' * 38}{RESET}",
            f"{WHITE}{BOLD}RADAR LEGEND:{RESET}",
            f"  {VIOLET}■ Code (.text){RESET}  {AZURE}■ Data (BSS){RESET}  {CYAN}■ Heap{RESET}",
            f"  {NEON_GREEN}■ Stack{RESET}        {AMBER}■ Frag/MMAP{RESET}   {CRIMSON}■ Leak{RESET}",
        ]

        for idx, r_line in enumerate(radar_rows):
            side = sidebar_info[idx] if idx < len(sidebar_info) else ""
            lines.append(f"  {r_line}  │ {side}")

        lines.append(f"{DARK_GRAY}{'─' * 82}{RESET}")
        lines.append(f"{LIGHT_GRAY}  [Ctrl+C] Exit  •  [3D Web HUD: python3 cli.py --web]  •  Pure Python Stdlib{RESET}")

        return "\n".join(lines)

    def run_live(self, frames: int = 150, delay: float = 0.066):
        """Runs the live terminal radar HUD at ~15 FPS."""
        # Hide cursor
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
        try:
            for _ in range(frames):
                snapshot, sim_metrics = self.step()
                output = self.render_frame(snapshot, sim_metrics)
                # Clear screen & home cursor
                sys.stdout.write("\033[H" + output)
                sys.stdout.flush()
                time.sleep(delay)
        finally:
            # Restore cursor
            sys.stdout.write("\033[?25h\n")
            sys.stdout.flush()


def run_tui(pid: Optional[int] = None, workload: str = "fragment", frames: int = 120):
    hud = VoxelMemTUI(pid=pid, workload=workload)
    hud.run_live(frames=frames)


if __name__ == "__main__":
    run_tui()

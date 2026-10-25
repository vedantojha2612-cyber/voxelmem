"""
Unit tests for VoxelMem Telemetry Engine & Linux /proc maps parsing.
"""

import os
import unittest
from voxelmem.engine import MemoryTelemetryEngine
from voxelmem.models import MemoryRegionType


class TestMemoryTelemetryEngine(unittest.TestCase):

    def setUp(self):
        self.engine = MemoryTelemetryEngine()

    def test_parse_maps_line_valid(self):
        line = "5a8a3980e000-5a8a3982f000 rw-p 00000000 00:00 0                          [heap]"
        region = self.engine.parse_maps_line(line)
        self.assertIsNotNone(region)
        self.assertEqual(region.start_addr, 0x5a8a3980e000)
        self.assertEqual(region.end_addr, 0x5a8a3982f000)
        self.assertEqual(region.permissions, "rw-p")
        self.assertEqual(region.region_type, MemoryRegionType.HEAP)
        self.assertEqual(region.pathname, "[heap]")

    def test_parse_maps_line_text_and_stack(self):
        line_text = "5a8a39000000-5a8a39010000 r-xp 00000000 08:01 12345                 /usr/bin/python3"
        reg_text = self.engine.parse_maps_line(line_text)
        self.assertEqual(reg_text.region_type, MemoryRegionType.CODE_TEXT)

        line_stack = "7ffd9c000000-7ffd9c021000 rw-p 00000000 00:00 0                          [stack]"
        reg_stack = self.engine.parse_maps_line(line_stack)
        self.assertEqual(reg_stack.region_type, MemoryRegionType.STACK)

    def test_parse_maps_line_invalid(self):
        self.assertIsNone(self.engine.parse_maps_line(""))
        self.assertIsNone(self.engine.parse_maps_line("corrupt line format without spaces"))

    def test_get_snapshot_for_current_process(self):
        snapshot = self.engine.get_snapshot(pid=os.getpid())
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.pid, os.getpid())
        self.assertGreater(snapshot.total_virtual_bytes, 0)
        self.assertGreater(len(snapshot.regions), 0)
        self.assertGreaterEqual(snapshot.fragmentation_index, 0.0)
        self.assertLessEqual(snapshot.fragmentation_index, 1.0)

    def test_synthetic_fallback_snapshot(self):
        # PID that does not exist to verify synthetic fallback
        snapshot = self.engine.get_snapshot(pid=99999999)
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.pid, 99999999)
        self.assertTrue(len(snapshot.regions) >= 4)
        types = {r.region_type for r in snapshot.regions}
        self.assertIn(MemoryRegionType.CODE_TEXT, types)
        self.assertIn(MemoryRegionType.HEAP, types)
        self.assertIn(MemoryRegionType.STACK, types)


if __name__ == "__main__":
    unittest.main()

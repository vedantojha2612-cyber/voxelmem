"""
Unit tests for VoxelMem Models & Data Structures.
"""

import unittest
from voxelmem.models import (
    MemoryRegion,
    MemoryRegionType,
    PageFrame,
    HeapArena,
    HeapChunk,
    ProcessMemorySnapshot,
    VoxelCoord,
    PAGE_SIZE,
    REGION_COLORS,
)


class TestVoxelMemModels(unittest.TestCase):

    def test_memory_region_properties(self):
        reg = MemoryRegion(
            start_addr=0x1000,
            end_addr=0x5000,
            permissions="r-xp",
            offset=0,
            device="08:01",
            inode=12345,
            pathname="/bin/test",
            region_type=MemoryRegionType.CODE_TEXT,
        )
        self.assertEqual(reg.size, 0x4000)
        self.assertEqual(reg.page_count, 4)
        self.assertTrue(reg.is_readable)
        self.assertFalse(reg.is_writable)
        self.assertTrue(reg.is_executable)
        self.assertFalse(reg.is_shared)

    def test_heap_chunk_dict(self):
        chunk = HeapChunk(addr=0x2000, size=512, is_allocated=True, tag="meta_arena")
        d = chunk.to_dict()
        self.assertEqual(d["addr"], "0x2000")
        self.assertEqual(d["size"], 512)
        self.assertTrue(d["is_allocated"])
        self.assertEqual(d["tag"], "meta_arena")

    def test_heap_arena_metrics(self):
        chunks = [
            HeapChunk(addr=0x1000, size=1024, is_allocated=True),
            HeapChunk(addr=0x1400, size=1024, is_allocated=False),
            HeapChunk(addr=0x1800, size=2048, is_allocated=True),
            HeapChunk(addr=0x2000, size=4096, is_allocated=False),
        ]
        arena = HeapArena(arena_id=0, start_addr=0x1000, size=8192, chunks=chunks)
        self.assertEqual(arena.allocated_bytes, 3072)
        self.assertEqual(arena.free_bytes, 5120)
        self.assertEqual(arena.largest_free_block, 4096)
        self.assertEqual(arena.fragmentation_percentage, 20.0)

    def test_voxel_coord_dict(self):
        v = VoxelCoord(
            x=3,
            y=1,
            z=7,
            region_type=MemoryRegionType.HEAP,
            color=REGION_COLORS[MemoryRegionType.HEAP],
            page_addr=0x1234000,
            access_count=5
        )
        d = v.to_dict()
        self.assertEqual(d["x"], 3)
        self.assertEqual(d["y"], 1)
        self.assertEqual(d["z"], 7)
        self.assertEqual(d["region_type"], "heap")
        self.assertEqual(d["color"], "#00f3ff")
        self.assertEqual(d["page_addr"], "0x1234000")

    def test_process_memory_snapshot_dict(self):
        snap = ProcessMemorySnapshot(
            pid=1337,
            process_name="test_proc",
            timestamp=1700000000.0,
            total_virtual_bytes=10 * 1024 * 1024,
            rss_bytes=4 * 1024 * 1024,
            regions=[],
            arenas=[],
            voxels=[],
            fragmentation_index=0.25,
            entropy=1.85,
            gini_coefficient=0.32
        )
        d = snap.to_dict()
        self.assertEqual(d["pid"], 1337)
        self.assertEqual(d["process_name"], "test_proc")
        self.assertEqual(d["fragmentation_index"], 0.25)
        self.assertEqual(d["entropy"], 1.85)
        self.assertEqual(d["gini_coefficient"], 0.32)


if __name__ == "__main__":
    unittest.main()

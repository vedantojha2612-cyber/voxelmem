"""
Unit tests for VoxelMem Fragmentation & Spatial Geometry.
"""

import unittest
from voxelmem.models import HeapChunk, MemoryRegionType, VoxelCoord
from voxelmem.fragmentation import (
    calculate_fragmentation_index,
    calculate_entropy,
    calculate_gini_coefficient,
    hilbert_2d,
    map_address_to_voxel,
    map_linear_to_3d_grid,
)


class TestFragmentationGeometry(unittest.TestCase):

    def test_fragmentation_index_bounds(self):
        # Empty
        self.assertEqual(calculate_fragmentation_index([]), 0.0)

        # Single large contiguous free chunk -> 0.0 fragmentation
        chunks = [
            HeapChunk(addr=0x1000, size=4096, is_allocated=False),
        ]
        self.assertAlmostEqual(calculate_fragmentation_index(chunks), 0.0)

        # Multiple small scattered free chunks -> higher fragmentation
        chunks = [
            HeapChunk(addr=0x1000, size=100, is_allocated=False),
            HeapChunk(addr=0x2000, size=100, is_allocated=False),
            HeapChunk(addr=0x3000, size=100, is_allocated=False),
            HeapChunk(addr=0x4000, size=100, is_allocated=False),
        ]
        # Total free = 400, max free = 100 -> Frag = 1 - (100/400) = 0.75
        self.assertAlmostEqual(calculate_fragmentation_index(chunks), 0.75)

    def test_entropy_and_gini(self):
        # Uniform sizes -> low gini
        sizes = [100, 100, 100, 100]
        self.assertAlmostEqual(calculate_gini_coefficient(sizes), 0.0)

        # Non-uniform -> positive entropy and gini
        sizes = [10, 50, 200, 1000]
        entropy = calculate_entropy(sizes)
        gini = calculate_gini_coefficient(sizes)
        self.assertGreater(entropy, 0.0)
        self.assertGreater(gini, 0.0)

    def test_hilbert_2d(self):
        # Order 1 (2x2)
        x0, y0 = hilbert_2d(0, 1)
        x1, y1 = hilbert_2d(1, 1)
        x2, y2 = hilbert_2d(2, 1)
        x3, y3 = hilbert_2d(3, 1)

        self.assertEqual((x0, y0), (0, 0))
        self.assertEqual((x1, y1), (0, 1))
        self.assertEqual((x2, y2), (1, 1))
        self.assertEqual((x3, y3), (1, 0))

    def test_map_address_to_voxel(self):
        voxel = map_address_to_voxel(
            addr=0x5a8a39801000,
            base_addr=0x5a8a39800000,
            region_type=MemoryRegionType.HEAP,
            access_frequency=12,
            page_index=1,
            grid_order=4
        )
        self.assertIsInstance(voxel, VoxelCoord)
        self.assertEqual(voxel.region_type, MemoryRegionType.HEAP)
        self.assertGreaterEqual(voxel.x, 0)
        self.assertGreaterEqual(voxel.z, 0)
        self.assertEqual(voxel.access_count, 12)


if __name__ == "__main__":
    unittest.main()

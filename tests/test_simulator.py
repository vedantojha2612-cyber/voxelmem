"""
Unit tests for VoxelMem Workload & Allocator Simulator.
"""

import unittest
from voxelmem.simulator import MemoryWorkloadSimulator


class TestMemoryWorkloadSimulator(unittest.TestCase):

    def setUp(self):
        self.sim = MemoryWorkloadSimulator(initial_size=512 * 1024)

    def test_alloc_and_free(self):
        c1 = self.sim.allocate(1024, tag="test_buffer")
        self.assertTrue(c1.is_allocated)
        self.assertEqual(c1.size, 1024)
        self.assertEqual(c1.tag, "test_buffer")

        freed = self.sim.free(c1)
        self.assertFalse(freed.is_allocated)

    def test_workload_modes_execution(self):
        modes = ["steady", "leak", "fragment", "burst"]
        for mode in modes:
            self.sim.set_workload(mode)
            self.assertEqual(self.sim.current_workload, mode)
            # Step 5 ticks
            for _ in range(5):
                snapshot = self.sim.step()
                self.assertIsNotNone(snapshot)
                self.assertGreater(snapshot.rss_bytes, 0)
                self.assertGreaterEqual(snapshot.fragmentation_index, 0.0)
                self.assertLessEqual(snapshot.fragmentation_index, 1.0)

    def test_leak_workload_growth(self):
        self.sim.set_workload("leak")
        initial_alloc = self.sim.arena.allocated_bytes
        for _ in range(10):
            self.sim.step()
        final_alloc = self.sim.arena.allocated_bytes
        self.assertGreater(final_alloc, initial_alloc)


if __name__ == "__main__":
    unittest.main()

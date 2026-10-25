"""
Tests for VoxelMem Benchmark & Load Testing Suite.
Ensures zero performance regressions across spatial math, concurrency, and leak detection.
"""

import unittest
import os
from voxelmem.benchmark import PerformanceBenchmarker


class TestVoxelMemBenchmark(unittest.TestCase):

    def setUp(self):
        # Create silent benchmarker for testing
        self.benchmarker = PerformanceBenchmarker(verbose=False)

    def test_benchmark_math_engine(self):
        res = self.benchmarker.benchmark_math_engine(iterations=500)
        self.assertIn("hilbert_2d_ops_sec", res)
        self.assertIn("voxel_map_ops_sec", res)
        self.assertIn("frag_index_ops_sec", res)
        self.assertIn("maps_parse_ops_sec", res)
        self.assertGreater(res["hilbert_2d_ops_sec"], 100_000)
        self.assertGreater(res["voxel_map_ops_sec"], 50_000)
        self.assertGreater(res["frag_index_ops_sec"], 20_000)

    def test_benchmark_concurrency(self):
        res = self.benchmarker.benchmark_concurrency(
            concurrency_levels=[5],
            requests_per_level=10
        )
        self.assertIn("5_workers", res)
        w5 = res["5_workers"]
        self.assertEqual(w5["total_requests"], 10)
        self.assertEqual(w5["errors"], 0)
        self.assertGreater(w5["throughput_rps"], 0)
        self.assertGreaterEqual(w5["p95_ms"], 0)

    def test_benchmark_memory_leaks(self):
        res = self.benchmarker.benchmark_memory_leaks(test_runs=15)
        self.assertIn("leak_detected", res)
        self.assertIn("net_leak_bytes", res)
        self.assertIn("profiler_overhead_pct", res)
        self.assertFalse(res["leak_detected"])
        self.assertLessEqual(res["profiler_overhead_pct"], 1.0)

    def test_benchmark_frontend_bundles(self):
        res = self.benchmarker.benchmark_frontend_bundles()
        self.assertIn("assets", res)
        self.assertIn("total_raw_kb", res)
        self.assertIn("total_gzip_kb", res)
        self.assertIn("overall_compression_pct", res)
        self.assertGreater(res["overall_compression_pct"], 50.0)

    def test_benchmark_web_server(self):
        res = self.benchmarker.benchmark_web_server(requests_count=10, concurrency=2)
        self.assertIn("total_requests", res)
        self.assertIn("successful", res)
        self.assertIn("status_codes", res)
        self.assertEqual(res["total_requests"], 10)
        self.assertEqual(res["errors"], 0)
        self.assertEqual(res["status_codes"].get(200, 0), 10)


if __name__ == "__main__":
    unittest.main()

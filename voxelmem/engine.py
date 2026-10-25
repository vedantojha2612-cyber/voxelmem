"""
VoxelMem - Memory Telemetry Engine
High-performance parser for Linux /proc/[pid]/maps, /proc/[pid]/status, 4KB page frame tracking,
and cross-platform synthetic fallback engine. Pure Python standard library.
"""

from __future__ import annotations
import os
import sys
import time
import re
from typing import List, Dict, Optional, Tuple, Any

from .models import (
    MemoryRegion,
    MemoryRegionType,
    PageFrame,
    HeapArena,
    HeapChunk,
    ProcessMemorySnapshot,
    VoxelCoord,
    PAGE_SIZE,
)
from .fragmentation import (
    calculate_fragmentation_index,
    map_address_to_voxel,
)

# Regex pattern for Linux /proc/[pid]/maps
MAPS_PATTERN = re.compile(
    r"^([0-9a-fA-F]+)-([0-9a-fA-F]+)\s+([rwxsp\-]{4})\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+:[0-9a-fA-F]+)\s+(\d+)\s*(.*)$"
)


class MemoryTelemetryEngine:
    """
    Virtual Memory Telemetry Engine.
    Inspects process virtual address spaces, parses maps, and profiles fragmentation.
    """

    def __init__(self, pid: Optional[int] = None):
        self.pid = pid if pid is not None else os.getpid()
        self.is_linux = sys.platform.startswith("linux")
        self._history: List[ProcessMemorySnapshot] = []
        self._max_history = 60

    @staticmethod
    def parse_maps_line(line: str) -> Optional[MemoryRegion]:
        """
        Parses a single line from Linux /proc/[pid]/maps.
        Example:
        5a8a3980e000-5a8a3982f000 rw-p 00000000 00:00 0                          [heap]
        """
        line = line.strip()
        if not line:
            return None

        match = MAPS_PATTERN.match(line)
        if not match:
            # Fallback split
            parts = line.split(maxsplit=5)
            if len(parts) < 5:
                return None
            addr_part, perms, offset_hex, dev, inode_str = parts[:5]
            pathname = parts[5] if len(parts) > 5 else ""
            if "-" not in addr_part:
                return None
            start_str, end_str = addr_part.split("-", 1)
            try:
                start_addr = int(start_str, 16)
                end_addr = int(end_str, 16)
                offset = int(offset_hex, 16)
                inode = int(inode_str)
            except ValueError:
                return None
            return MemoryRegion.create(start_addr, end_addr, perms, offset, dev, inode, pathname)

        start_str, end_str, perms, offset_hex, dev, inode_str, pathname = match.groups()
        try:
            start_addr = int(start_str, 16)
            end_addr = int(end_str, 16)
            offset = int(offset_hex, 16)
            inode = int(inode_str)
        except ValueError:
            return None

        return MemoryRegion.create(start_addr, end_addr, perms, offset, dev, inode, pathname)

    def read_proc_maps(self, pid: Optional[int] = None) -> List[MemoryRegion]:
        """
        Reads and parses /proc/[pid]/maps.
        Falls back to synthetic regions if /proc is unavailable.
        """
        target_pid = pid if pid is not None else self.pid
        maps_path = f"/proc/{target_pid}/maps"

        if self.is_linux and os.path.exists(maps_path):
            try:
                regions: List[MemoryRegion] = []
                with open(maps_path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        region = self.parse_maps_line(line)
                        if region:
                            regions.append(region)
                if regions:
                    return regions
            except (PermissionError, FileNotFoundError, ProcessLookupError):
                pass

        # Cross-platform or non-Linux synthetic fallback
        return self._generate_synthetic_regions(target_pid)

    def read_proc_status(self, pid: Optional[int] = None) -> Dict[str, int]:
        """
        Reads VmSize, VmRSS, VmData, VmStk, VmExe from /proc/[pid]/status or /proc/[pid]/statm.
        """
        target_pid = pid if pid is not None else self.pid
        status_path = f"/proc/{target_pid}/status"
        metrics: Dict[str, int] = {
            "vms_bytes": 0,
            "rss_bytes": 0,
            "data_bytes": 0,
            "stack_bytes": 0,
            "code_bytes": 0,
            "shared_bytes": 0,
        }

        if self.is_linux and os.path.exists(status_path):
            try:
                with open(status_path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        if ":" not in line:
                            continue
                        k, v = line.split(":", 1)
                        k = k.strip()
                        parts = v.strip().split()
                        if not parts or not parts[0].isdigit():
                            continue
                        val_bytes = int(parts[0]) * 1024
                        if k == "VmSize":
                            metrics["vms_bytes"] = val_bytes
                        elif k == "VmRSS":
                            metrics["rss_bytes"] = val_bytes
                        elif k == "VmData":
                            metrics["data_bytes"] = val_bytes
                        elif k == "VmStk":
                            metrics["stack_bytes"] = val_bytes
                        elif k == "VmExe":
                            metrics["code_bytes"] = val_bytes
                        elif k == "RssFile":
                            metrics["shared_bytes"] = val_bytes
                return metrics
            except (PermissionError, FileNotFoundError, ProcessLookupError):
                pass

        # Fallback reading statm
        statm_path = f"/proc/{target_pid}/statm"
        if self.is_linux and os.path.exists(statm_path):
            try:
                with open(statm_path, "r", encoding="utf-8") as f:
                    parts = f.read().split()
                    if len(parts) >= 6:
                        metrics["vms_bytes"] = int(parts[0]) * PAGE_SIZE
                        metrics["rss_bytes"] = int(parts[1]) * PAGE_SIZE
                        metrics["shared_bytes"] = int(parts[2]) * PAGE_SIZE
                        metrics["code_bytes"] = int(parts[3]) * PAGE_SIZE
                        metrics["data_bytes"] = int(parts[5]) * PAGE_SIZE
                return metrics
            except Exception:
                pass

        # Default fallback
        metrics["vms_bytes"] = 32 * 1024 * 1024
        metrics["rss_bytes"] = 8 * 1024 * 1024
        metrics["heap_bytes"] = 4 * 1024 * 1024
        metrics["stack_bytes"] = 128 * 1024
        metrics["code_bytes"] = 2 * 1024 * 1024
        return metrics

    def get_process_name(self, pid: Optional[int] = None) -> str:
        """Gets process executable name."""
        target_pid = pid if pid is not None else self.pid
        comm_path = f"/proc/{target_pid}/comm"
        if self.is_linux and os.path.exists(comm_path):
            try:
                with open(comm_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
        return f"proc_{target_pid}"

    def sample_page_frames(self, regions: List[MemoryRegion], max_samples: int = 144) -> List[PageFrame]:
        """
        Samples page frames across regions and projects each page into a 3D Voxel coordinate.
        """
        samples: List[PageFrame] = []
        if not regions:
            return samples

        # Sort regions: code, data, heap, mmap, stack
        priority_order = {
            MemoryRegionType.HEAP: 0,
            MemoryRegionType.STACK: 1,
            MemoryRegionType.DATA: 2,
            MemoryRegionType.CODE: 3,
            MemoryRegionType.MMAP: 4,
            MemoryRegionType.ANONYMOUS: 5,
            MemoryRegionType.SYSTEM: 6,
        }
        sorted_regions = sorted(regions, key=lambda r: priority_order.get(r.region_type, 9))

        samples_per_region = max(1, max_samples // max(1, len(sorted_regions)))
        page_counter = 0

        for reg in sorted_regions:
            reg_pages = reg.page_count
            if reg_pages <= 0:
                continue

            step = max(1, reg_pages // samples_per_region)
            for p_idx in range(0, reg_pages, step):
                if len(samples) >= max_samples:
                    break

                page_vaddr = reg.start_addr + (p_idx * PAGE_SIZE)
                voxel = map_address_to_voxel(
                    virtual_address=page_vaddr,
                    base_address=reg.start_addr,
                    region_type=reg.region_type,
                    page_size=PAGE_SIZE,
                    grid_order=4  # 16x16 grid base
                )

                # Simulated access dynamics & fragmentation flags
                is_dirty = reg.writable and (p_idx % 3 == 0)
                is_fragmented = (reg.region_type == MemoryRegionType.HEAP) and (p_idx % 4 == 2)
                is_leak_suspect = (reg.region_type == MemoryRegionType.HEAP) and (p_idx % 17 == 0)

                frame = PageFrame(
                    page_index=page_counter,
                    virtual_address=page_vaddr,
                    region_type=reg.region_type,
                    is_allocated=True,
                    is_dirty=is_dirty,
                    is_free=False,
                    is_fragmented=is_fragmented,
                    is_leak_suspect=is_leak_suspect,
                    access_frequency=(p_idx * 7) % 100,
                    voxel_coord=voxel,
                )
                samples.append(frame)
                page_counter += 1

        return samples

    def build_synthetic_heap_arena(self, heap_bytes: int) -> HeapArena:
        """
        Builds a modeled heap arena with realistic allocated vs free chunks for fragmentation analysis.
        """
        model_size = min(256 * 1024, max(64 * 1024, heap_bytes))
        chunks: List[HeapChunk] = []
        curr_addr = 0x550000000000
        allocated_bytes = 0
        free_bytes = 0

        # Pattern of realistic allocations: mix of small, medium, large, and free holes
        chunk_sizes = [
            (64, True, "string"),
            (128, False, "free"),
            (256, True, "object"),
            (512, True, "buffer"),
            (64, False, "free"),
            (1024, True, "arena_node"),
            (2048, False, "free"),
            (4096, True, "cache_slab"),
            (512, False, "free"),
            (8192, True, "mmap_pool"),
            (256, False, "free"),
            (128, True, "hash_entry"),
        ]

        repeat = min(6, max(2, model_size // (32 * 1024)))
        for _ in range(repeat):
            for sz, is_alloc, tag in chunk_sizes:
                chunk = HeapChunk(
                    address=curr_addr,
                    size=sz,
                    is_allocated=is_alloc,
                    tag=tag if is_alloc else "free",
                )
                chunks.append(chunk)
                curr_addr += sz
                if is_alloc:
                    allocated_bytes += sz
                else:
                    free_bytes += sz
                if curr_addr - 0x550000000000 >= model_size:
                    break
            if curr_addr - 0x550000000000 >= model_size:
                break

        total_sz = max(heap_bytes, allocated_bytes + free_bytes)
        arena = HeapArena(
            arena_id=0,
            base_address=0x550000000000,
            total_size=total_sz,
            allocated_bytes=allocated_bytes,
            free_bytes=free_bytes,
            chunks=chunks,
        )
        return arena

    def take_snapshot(self, pid: Optional[int] = None) -> ProcessMemorySnapshot:
        """
        Captures an instant telemetry snapshot of process memory.
        """
        target_pid = pid if pid is not None else self.pid
        proc_name = self.get_process_name(target_pid)
        regions = self.read_proc_maps(target_pid)
        status_metrics = self.read_proc_status(target_pid)

        # Region sums
        heap_bytes = 0
        stack_bytes = 0
        code_bytes = 0
        mmap_bytes = 0
        total_pages = 0

        for r in regions:
            total_pages += r.page_count
            if r.region_type == MemoryRegionType.HEAP:
                heap_bytes += r.size_bytes
            elif r.region_type == MemoryRegionType.STACK:
                stack_bytes += r.size_bytes
            elif r.region_type == MemoryRegionType.CODE:
                code_bytes += r.size_bytes
            elif r.region_type in (MemoryRegionType.MMAP, MemoryRegionType.DATA, MemoryRegionType.ANONYMOUS):
                mmap_bytes += r.size_bytes

        vms_bytes = status_metrics.get("vms_bytes") or sum(r.size_bytes for r in regions)
        rss_bytes = status_metrics.get("rss_bytes") or int(vms_bytes * 0.25)
        shared_bytes = status_metrics.get("shared_bytes") or int(rss_bytes * 0.3)
        if stack_bytes == 0:
            stack_bytes = status_metrics.get("stack_bytes", 132 * 1024)
        if code_bytes == 0:
            code_bytes = status_metrics.get("code_bytes", 1024 * 1024)

        # Heap arena simulation & fragmentation
        heap_arena = self.build_synthetic_heap_arena(heap_bytes if heap_bytes > 0 else 2 * 1024 * 1024)
        frag_score = heap_arena.fragmentation_ratio

        # Voxel Page Frame sampling
        sample_pages = self.sample_page_frames(regions, max_samples=144)

        active_pages = sum(1 for p in sample_pages if p.is_allocated)
        leak_suspects = sum(1 for p in sample_pages if p.is_leak_suspect)
        leak_score = round(leak_suspects / max(1, len(sample_pages)), 4)

        snapshot = ProcessMemorySnapshot(
            pid=target_pid,
            process_name=proc_name,
            timestamp=time.time(),
            vms_bytes=vms_bytes,
            rss_bytes=rss_bytes,
            shared_bytes=shared_bytes,
            heap_bytes=heap_bytes if heap_bytes > 0 else heap_arena.allocated_bytes,
            stack_bytes=stack_bytes,
            code_bytes=code_bytes,
            mmap_bytes=mmap_bytes,
            total_pages=total_pages if total_pages > 0 else (vms_bytes // PAGE_SIZE),
            active_pages=active_pages,
            regions=regions,
            arenas=[heap_arena],
            sample_pages=sample_pages,
            fragmentation_score=frag_score,
            leak_probability_score=leak_score,
        )

        self._history.append(snapshot)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        return snapshot

    def _generate_synthetic_regions(self, pid: int) -> List[MemoryRegion]:
        """
        Creates synthetic virtual address space for demo mode or non-Linux platforms.
        """
        return [
            MemoryRegion.create(0x55a000000000, 0x55a000040000, "r-xp", 0, "08:01", 1001, f"/usr/bin/proc_{pid}"),
            MemoryRegion.create(0x55a000040000, 0x55a000050000, "r--p", 0x40000, "08:01", 1001, f"/usr/bin/proc_{pid}"),
            MemoryRegion.create(0x55a000050000, 0x55a000060000, "rw-p", 0x50000, "08:01", 1001, f"/usr/bin/proc_{pid}"),
            MemoryRegion.create(0x55a001000000, 0x55a001800000, "rw-p", 0, "00:00", 0, "[heap]"),
            MemoryRegion.create(0x7f1000000000, 0x7f1000200000, "r-xp", 0, "08:01", 2001, "/lib/libc.so.6"),
            MemoryRegion.create(0x7f1000200000, 0x7f1000250000, "rw-p", 0x200000, "08:01", 2001, "/lib/libc.so.6"),
            MemoryRegion.create(0x7f1000300000, 0x7f1000500000, "rw-p", 0, "00:00", 0, ""),
            MemoryRegion.create(0x7ffd00000000, 0x7ffd00021000, "rw-p", 0, "00:00", 0, "[stack]"),
            MemoryRegion.create(0x7ffd00030000, 0x7ffd00032000, "r-xp", 0, "00:00", 0, "[vdso]"),
        ]

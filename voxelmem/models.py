"""
VoxelMem - Models & Data Structures
Core primitives for virtual address spaces, 4KB page frames, heap arenas, and 3D voxel coordinates.
Zero third-party runtime dependencies.
"""

from __future__ import annotations
import enum
import math
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple

PAGE_SIZE = 4096  # Standard 4KB Page Frame size


class MemoryRegionType(str, enum.Enum):
    CODE = "code"            # Executable code (.text, rx)
    DATA = "data"            # Initialized/uninitialized data (BSS, rw)
    HEAP = "heap"            # Dynamic heap allocation ([heap])
    STACK = "stack"          # Thread execution stack ([stack])
    MMAP = "mmap"            # Memory mapped files, shared libraries (.so)
    ANONYMOUS = "anonymous"  # Private anonymous mappings
    SYSTEM = "system"        # vdso, vvar, vsyscall
    FREE = "free"            # Unallocated / hole in virtual memory


# High-contrast cyberpunk palette for 3D WebGL HUD and ANSI/Braille TUI
REGION_COLORS: Dict[MemoryRegionType, str] = {
    MemoryRegionType.CODE: "#7000ff",       # Electric Violet
    MemoryRegionType.DATA: "#0077ff",       # Neon Azure
    MemoryRegionType.HEAP: "#00f3ff",       # Bright Cyan
    MemoryRegionType.STACK: "#00ff88",      # Matrix Green
    MemoryRegionType.MMAP: "#ffaa00",       # Amber Flame
    MemoryRegionType.ANONYMOUS: "#ff00bb",  # Synthwave Magenta
    MemoryRegionType.SYSTEM: "#666688",     # Muted Slate
    MemoryRegionType.FREE: "#111827",       # Deep Void
}

REGION_ANSI_COLORS: Dict[MemoryRegionType, str] = {
    MemoryRegionType.CODE: "\033[35m",       # Magenta
    MemoryRegionType.DATA: "\033[34m",       # Blue
    MemoryRegionType.HEAP: "\033[36m",       # Cyan
    MemoryRegionType.STACK: "\033[32m",      # Green
    MemoryRegionType.MMAP: "\033[33m",       # Yellow
    MemoryRegionType.ANONYMOUS: "\033[95m",  # Bright Magenta
    MemoryRegionType.SYSTEM: "\033[90m",     # Gray
    MemoryRegionType.FREE: "\033[2m",        # Dim
}


@dataclass
class VoxelCoord:
    x: int
    y: int
    z: int

    def to_tuple(self) -> Tuple[int, int, int]:
        return (self.x, self.y, self.z)


@dataclass
class MemoryRegion:
    start_addr: int
    end_addr: int
    perms: str
    offset: int
    dev: str
    inode: int
    pathname: str
    region_type: MemoryRegionType
    size_bytes: int
    page_count: int
    readable: bool
    writable: bool
    executable: bool
    is_private: bool

    @classmethod
    def create(cls, start_addr: int, end_addr: int, perms: str, offset: int,
               dev: str, inode: int, pathname: str) -> MemoryRegion:
        size = max(0, end_addr - start_addr)
        pages = math.ceil(size / PAGE_SIZE) if size > 0 else 0
        readable = 'r' in perms
        writable = 'w' in perms
        executable = 'x' in perms
        is_private = 'p' in perms

        clean_path = pathname.strip()
        if clean_path == "[heap]":
            rtype = MemoryRegionType.HEAP
        elif clean_path == "[stack]" or clean_path.startswith("[stack:"):
            rtype = MemoryRegionType.STACK
        elif clean_path in ("[vdso]", "[vvar]", "[vsyscall]"):
            rtype = MemoryRegionType.SYSTEM
        elif executable and not writable:
            rtype = MemoryRegionType.CODE
        elif clean_path and not clean_path.startswith("["):
            rtype = MemoryRegionType.MMAP
        elif writable and not executable:
            rtype = MemoryRegionType.DATA if clean_path else MemoryRegionType.ANONYMOUS
        else:
            rtype = MemoryRegionType.ANONYMOUS

        return cls(
            start_addr=start_addr,
            end_addr=end_addr,
            perms=perms,
            offset=offset,
            dev=dev,
            inode=inode,
            pathname=clean_path,
            region_type=rtype,
            size_bytes=size,
            page_count=pages,
            readable=readable,
            writable=writable,
            executable=executable,
            is_private=is_private,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_addr_hex": f"0x{self.start_addr:012x}",
            "end_addr_hex": f"0x{self.end_addr:012x}",
            "start_addr": self.start_addr,
            "end_addr": self.end_addr,
            "perms": self.perms,
            "offset": self.offset,
            "dev": self.dev,
            "inode": self.inode,
            "pathname": self.pathname,
            "region_type": self.region_type.value,
            "size_bytes": self.size_bytes,
            "size_kb": round(self.size_bytes / 1024, 2),
            "size_mb": round(self.size_bytes / (1024 * 1024), 2),
            "page_count": self.page_count,
            "readable": self.readable,
            "writable": self.writable,
            "executable": self.executable,
            "is_private": self.is_private,
            "color_hex": REGION_COLORS[self.region_type],
        }


@dataclass
class PageFrame:
    page_index: int
    virtual_address: int
    region_type: MemoryRegionType
    is_allocated: bool = True
    is_dirty: bool = False
    is_free: bool = False
    is_fragmented: bool = False
    is_leak_suspect: bool = False
    access_frequency: int = 0
    voxel_coord: VoxelCoord = field(default_factory=lambda: VoxelCoord(0, 0, 0))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_index": self.page_index,
            "virtual_address_hex": f"0x{self.virtual_address:012x}",
            "virtual_address": self.virtual_address,
            "region_type": self.region_type.value,
            "is_allocated": self.is_allocated,
            "is_dirty": self.is_dirty,
            "is_free": self.is_free,
            "is_fragmented": self.is_fragmented,
            "is_leak_suspect": self.is_leak_suspect,
            "access_frequency": self.access_frequency,
            "x": self.voxel_coord.x,
            "y": self.voxel_coord.y,
            "z": self.voxel_coord.z,
            "color_hex": (
                "#ff0055" if self.is_leak_suspect else
                "#ff5500" if self.is_fragmented else
                REGION_COLORS[self.region_type]
            )
        }


@dataclass
class HeapChunk:
    address: int
    size: int
    is_allocated: bool
    tag: str = "general"
    age_ticks: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address_hex": f"0x{self.address:012x}",
            "address": self.address,
            "size": self.size,
            "size_kb": round(self.size / 1024, 2),
            "is_allocated": self.is_allocated,
            "tag": self.tag,
            "age_ticks": self.age_ticks,
        }


@dataclass
class HeapArena:
    arena_id: int
    base_address: int
    total_size: int
    allocated_bytes: int
    free_bytes: int
    chunks: List[HeapChunk] = field(default_factory=list)

    @property
    def largest_free_block(self) -> int:
        free_sizes = [c.size for c in self.chunks if not c.is_allocated]
        return max(free_sizes) if free_sizes else 0

    @property
    def free_chunk_count(self) -> int:
        return sum(1 for c in self.chunks if not c.is_allocated)

    @property
    def allocated_chunk_count(self) -> int:
        return sum(1 for c in self.chunks if c.is_allocated)

    @property
    def fragmentation_ratio(self) -> float:
        """
        External fragmentation index:
        F = 1 - (largest_free_block / total_free_bytes) if total_free_bytes > 0 else 0.0
        Range: 0.0 (completely contiguous free space) to 1.0 (highly fragmented free space).
        """
        if self.free_bytes <= 0:
            return 0.0
        largest = self.largest_free_block
        if largest == 0:
            return 1.0
        ratio = 1.0 - (largest / self.free_bytes)
        return max(0.0, min(1.0, round(ratio, 4)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "arena_id": self.arena_id,
            "base_address_hex": f"0x{self.base_address:012x}",
            "total_size": self.total_size,
            "allocated_bytes": self.allocated_bytes,
            "free_bytes": self.free_bytes,
            "allocated_percent": round((self.allocated_bytes / self.total_size) * 100, 2) if self.total_size > 0 else 0,
            "largest_free_block": self.largest_free_block,
            "free_chunk_count": self.free_chunk_count,
            "allocated_chunk_count": self.allocated_chunk_count,
            "fragmentation_ratio": self.fragmentation_ratio,
            "chunks": [c.to_dict() for c in self.chunks[:100]],  # Cap to avoid runaway size
        }


@dataclass
class ProcessMemorySnapshot:
    pid: int
    process_name: str
    timestamp: float
    vms_bytes: int
    rss_bytes: int
    shared_bytes: int
    heap_bytes: int
    stack_bytes: int
    code_bytes: int
    mmap_bytes: int
    total_pages: int
    active_pages: int
    regions: List[MemoryRegion] = field(default_factory=list)
    arenas: List[HeapArena] = field(default_factory=list)
    sample_pages: List[PageFrame] = field(default_factory=list)
    fragmentation_score: float = 0.0
    leak_probability_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pid": self.pid,
            "process_name": self.process_name,
            "timestamp": self.timestamp,
            "vms_bytes": self.vms_bytes,
            "vms_mb": round(self.vms_bytes / (1024 * 1024), 2),
            "rss_bytes": self.rss_bytes,
            "rss_mb": round(self.rss_bytes / (1024 * 1024), 2),
            "shared_bytes": self.shared_bytes,
            "shared_mb": round(self.shared_bytes / (1024 * 1024), 2),
            "heap_bytes": self.heap_bytes,
            "heap_mb": round(self.heap_bytes / (1024 * 1024), 2),
            "stack_bytes": self.stack_bytes,
            "stack_kb": round(self.stack_bytes / 1024, 2),
            "code_bytes": self.code_bytes,
            "code_mb": round(self.code_bytes / (1024 * 1024), 2),
            "mmap_bytes": self.mmap_bytes,
            "mmap_mb": round(self.mmap_bytes / (1024 * 1024), 2),
            "total_pages": self.total_pages,
            "active_pages": self.active_pages,
            "fragmentation_score": round(self.fragmentation_score, 4),
            "leak_probability_score": round(self.leak_probability_score, 4),
            "regions_count": len(self.regions),
            "regions": [r.to_dict() for r in self.regions],
            "arenas": [a.to_dict() for a in self.arenas],
            "sample_pages": [p.to_dict() for p in self.sample_pages],
        }

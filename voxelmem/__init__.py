"""
VoxelMem - Real-Time 3D Spatial Virtual Memory & Heap Allocation Hologram
Pure Python Standard Library.
"""

from .models import (
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
from .fragmentation import (
    calculate_fragmentation_index,
    calculate_entropy,
    calculate_gini_coefficient,
    map_address_to_voxel,
    hilbert_2d,
)
from .engine import MemoryTelemetryEngine
from .simulator import MemoryWorkloadSimulator

__version__ = "0.1.0"
__all__ = [
    "MemoryRegion",
    "MemoryRegionType",
    "PageFrame",
    "HeapArena",
    "HeapChunk",
    "ProcessMemorySnapshot",
    "VoxelCoord",
    "PAGE_SIZE",
    "REGION_COLORS",
    "calculate_fragmentation_index",
    "calculate_entropy",
    "calculate_gini_coefficient",
    "map_address_to_voxel",
    "hilbert_2d",
    "MemoryTelemetryEngine",
    "MemoryWorkloadSimulator",
]

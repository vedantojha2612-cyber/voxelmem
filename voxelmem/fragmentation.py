"""
VoxelMem - Fragmentation Analysis & Spatial Voxel Coordinates
Mathematical algorithms for memory fragmentation, entropy, and 3D Hilbert/isometric voxel projection.
"""

from __future__ import annotations
import math
from typing import List, Tuple, Dict, Any
from .models import VoxelCoord, HeapChunk, MemoryRegionType


def calculate_fragmentation_index(total_free_bytes: int, largest_free_block: int) -> float:
    """
    Standard Knuth / Wilson heap fragmentation index:
    F = 1.0 - (largest_free_block / total_free_bytes)
    Returns a float between 0.0 (perfectly consolidated) and 1.0 (completely shattered).
    """
    if total_free_bytes <= 0:
        return 0.0
    if largest_free_block <= 0:
        return 1.0
    ratio = 1.0 - (largest_free_block / total_free_bytes)
    return max(0.0, min(1.0, round(ratio, 4)))


def calculate_entropy(chunks: List[HeapChunk]) -> float:
    """
    Calculates Shannon Entropy of chunk sizes to quantify heap randomness.
    H = - sum(p * log2(p))
    """
    if not chunks:
        return 0.0
    total_size = sum(c.size for c in chunks)
    if total_size <= 0:
        return 0.0

    entropy = 0.0
    for c in chunks:
        p = c.size / total_size
        if p > 0:
            entropy -= p * math.log2(p)
    return round(entropy, 4)


def calculate_gini_coefficient(chunks: List[HeapChunk]) -> float:
    """
    Gini coefficient of chunk sizes (0.0 = uniform sizes, 1.0 = maximal inequality).
    """
    if len(chunks) < 2:
        return 0.0
    sizes = sorted(c.size for c in chunks)
    n = len(sizes)
    sum_sizes = sum(sizes)
    if sum_sizes <= 0:
        return 0.0
    
    cumulative = 0
    gini_sum = 0
    for i, s in enumerate(sizes):
        cumulative += s
        gini_sum += (2 * (i + 1) - n - 1) * s
    return round(gini_sum / (n * sum_sizes), 4)


def map_linear_to_3d_grid(index: int, grid_width: int = 16, grid_depth: int = 16) -> VoxelCoord:
    """
    Maps a linear page index into a 3D isometric voxel coordinate (x, y, z).
    x: width column [0 .. grid_width-1]
    y: depth row [0 .. grid_depth-1]
    z: vertical tier [0 .. ]
    """
    layer_capacity = grid_width * grid_depth
    z = index // layer_capacity
    rem = index % layer_capacity
    x = rem % grid_width
    y = rem // grid_width
    return VoxelCoord(x=x, y=y, z=z)


def _compute_hilbert_2d(index: int, order: int = 4) -> Tuple[int, int]:
    """Raw calculation for 2D Hilbert space-filling curve."""
    n = 1 << order
    t = index
    x = y = 0
    s = 1
    while s < n:
        rx = 1 & (t // 2)
        ry = 1 & (t ^ rx)
        # Rotate/flip quadrant
        if ry == 0:
            if rx == 1:
                x = s - 1 - x
                y = s - 1 - y
            x, y = y, x
        x += s * rx
        y += s * ry
        t //= 4
        s *= 2
    return (x, y)


_HILBERT_ORDER4_CACHE: Tuple[Tuple[int, int], ...] = tuple(_compute_hilbert_2d(i, 4) for i in range(256))


def hilbert_2d(index: int, order: int = 4) -> Tuple[int, int]:
    """
    2D Hilbert space-filling curve generator.
    Preserves locality of reference in memory address spaces.
    order=4 yields a 16x16 grid (256 positions).
    Ultra-high performance cached lookup for order=4.
    """
    if order == 4 and 0 <= index < 256:
        return _HILBERT_ORDER4_CACHE[index]
    return _compute_hilbert_2d(index, order)


def map_address_to_voxel(
    virtual_address: int,
    base_address: int,
    region_type: MemoryRegionType,
    page_size: int = 4096,
    grid_order: int = 4
) -> VoxelCoord:
    """
    Maps a virtual address to a 3D Voxel Coordinate.
    x, y: Hilbert curve projection of page offset (spatial locality).
    z: Region tier height (e.g. Stack high, Heap mid, Code base).
    """
    offset = max(0, virtual_address - base_address)
    page_index = offset // page_size
    n_positions = (1 << grid_order) * (1 << grid_order)  # 256
    
    local_index = page_index % n_positions
    tier_offset = page_index // n_positions

    hx, hy = hilbert_2d(local_index, order=grid_order)

    # Base z level per region type to form the 3D Voxel Memory City
    tier_base = {
        MemoryRegionType.SYSTEM: 0,
        MemoryRegionType.CODE: 1,
        MemoryRegionType.DATA: 2,
        MemoryRegionType.HEAP: 4,
        MemoryRegionType.MMAP: 8,
        MemoryRegionType.STACK: 12,
        MemoryRegionType.ANONYMOUS: 6,
        MemoryRegionType.FREE: 0,
    }.get(region_type, 0)

    z = tier_base + (tier_offset % 4)
    return VoxelCoord(x=hx, y=hy, z=z)

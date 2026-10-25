"""
VoxelMem Dynamic Memory Allocator Workload Simulator.
Emulates real-world memory fragmentation, allocation churn, arena free-lists, and leak vectors.
Pure Python Standard Library.
"""

from __future__ import annotations
import random
from typing import List, Dict, Any, Optional

from .models import HeapChunk, HeapArena
from .fragmentation import calculate_fragmentation_index, calculate_entropy


class MemoryWorkloadSimulator:
    """Simulates realistic heap allocation workloads and dynamic memory states."""

    def __init__(self, base_address: int = 0x555500000000):
        self.base_address = base_address
        self.current_offset = 0
        self.chunks: List[HeapChunk] = []
        self._allocated_chunks: List[HeapChunk] = []
        self._leak_pool: List[HeapChunk] = []
        self.tick_counter = 0

    def allocate(self, size: int, tag: str = "active") -> HeapChunk:
        """Simulates an allocation, attempting first-fit in free chunks or bumping heap brk."""
        # Check for reusable free chunk (First-fit allocation)
        for i, c in enumerate(self.chunks):
            if not c.is_allocated and c.size >= size:
                c.is_allocated = True
                c.tag = tag
                c.access_count += 1
                c.age_ticks = 0
                self._allocated_chunks.append(c)
                return c

        # Bump allocator if no suitable free chunk exists
        addr = self.base_address + self.current_offset
        self.current_offset += size
        chunk = HeapChunk(
            address=addr,
            size=size,
            is_allocated=True,
            tag=tag,
            age_ticks=0,
            access_count=1,
        )
        self.chunks.append(chunk)
        self._allocated_chunks.append(chunk)
        return chunk

    def free(self, chunk: HeapChunk) -> bool:
        """Frees an allocated memory chunk, creating a free space hole."""
        if chunk in self._allocated_chunks:
            self._allocated_chunks.remove(chunk)
            chunk.is_allocated = False
            chunk.tag = "free"
            return True
        return False

    def simulate_tick(self, workload: str = "fragment") -> Dict[str, Any]:
        """
        Executes one tick of allocation dynamics based on the specified workload pattern.
        Workloads: 'steady', 'leak', 'fragment', 'burst'
        """
        self.tick_counter += 1

        for c in self.chunks:
            if c.is_allocated:
                c.age_ticks += 1

        if workload == "steady":
            # Allocate 3, free 3 (balanced state)
            for _ in range(3):
                sz = random.choice([64, 128, 256, 512])
                self.allocate(sz, tag="steady_buffer")
            if len(self._allocated_chunks) > 10:
                to_free = random.sample(self._allocated_chunks, min(3, len(self._allocated_chunks)))
                for c in to_free:
                    self.free(c)

        elif workload == "leak":
            # Continuously allocate without freeing some objects
            for _ in range(4):
                sz = random.choice([128, 256, 1024])
                c = self.allocate(sz, tag="leak_object")
                self._leak_pool.append(c)
            # Free only short-lived objects
            transient = [c for c in self._allocated_chunks if c.tag != "leak_object"]
            if transient:
                for c in random.sample(transient, min(2, len(transient))):
                    self.free(c)

        elif workload == "fragment":
            # Swiss-cheese fragmentation: allocate many small blocks, free alternating blocks
            new_chunks = []
            for _ in range(6):
                sz = random.choice([32, 64, 128, 256, 512, 1024])
                c = self.allocate(sz, tag="frag_block")
                new_chunks.append(c)
            # Free random chunks to punch holes in the heap
            if len(self._allocated_chunks) > 8:
                holes = random.sample(self._allocated_chunks, min(4, len(self._allocated_chunks)))
                for c in holes:
                    self.free(c)

        elif workload == "burst":
            # Periodic huge allocations followed by mass frees
            if self.tick_counter % 3 == 0:
                for _ in range(12):
                    self.allocate(random.randint(256, 4096), tag="burst_batch")
            else:
                if len(self._allocated_chunks) > 5:
                    for c in random.sample(self._allocated_chunks, min(6, len(self._allocated_chunks))):
                        self.free(c)

        # Calculate metrics
        allocated_bytes = sum(c.size for c in self.chunks if c.is_allocated)
        free_chunks = [c for c in self.chunks if not c.is_allocated]
        free_bytes = sum(c.size for c in free_chunks)
        largest_free = max((c.size for c in free_chunks), default=0)

        frag_idx = calculate_fragmentation_index(free_bytes, largest_free)
        entropy = calculate_entropy(self.chunks)

        return {
            "tick": self.tick_counter,
            "workload": workload,
            "total_chunks": len(self.chunks),
            "allocated_chunks": len(self._allocated_chunks),
            "free_chunks": len(free_chunks),
            "allocated_bytes": allocated_bytes,
            "free_bytes": free_bytes,
            "largest_free_block": largest_free,
            "fragmentation_index": frag_idx,
            "entropy": entropy,
            "leak_count": len(self._leak_pool),
        }

    def to_arena(self, arena_id: int = 0) -> HeapArena:
        """Converts simulator state into a HeapArena model."""
        allocated_bytes = sum(c.size for c in self.chunks if c.is_allocated)
        free_bytes = sum(c.size for c in self.chunks if not c.is_allocated)
        return HeapArena(
            arena_id=arena_id,
            base_address=self.base_address,
            total_size=allocated_bytes + free_bytes,
            allocated_bytes=allocated_bytes,
            free_bytes=free_bytes,
            chunks=list(self.chunks),
        )

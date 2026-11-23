"""Vertex sharing for flat shaded materials.

With G_SHADING_SMOOTH cleared, the microcode takes the shade of a whole triangle from
the vertex selected by the flag argument of the triangle commands (v[flag]). The shade
of the other two corners is never read, so vertices that differ only in shade can be
merged, as long as every triangle keeps one corner carrying its own shade.

    key   - what must match for two vertices to be the same vertex: position, uv,
            stOffset, alpha, vertex group, material index.
    shade - normal (lit materials), rgb (unlit), or both (F3DEX3 packed normals).

Nothing here imports bpy, so the assignment can be tested without Blender.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Hashable, Optional

# Bounded so a mesh with thousands of distinct normals cannot recurse deep enough to
# overflow the stack; a longer search wins very few vertices.
MAX_AUGMENT_DEPTH = 32


def material_uses_flat_optimization(material, f3d) -> bool:
    # F3DEX and later rotate the indices to put the flag'd vertex first, which is what this
    # relies on. Original F3D writes flag as a separate byte instead, and is left out.
    from ..utility import getRgbNormalSettings  # here, so this module stays bpy free

    f3d_mat = material.f3d_mat
    if f3d_mat.rdp_settings.g_shade_smooth or f3d.F3D_OLD_GBI:
        return False
    has_rgb, has_normal, _ = getRgbNormalSettings(f3d_mat)
    return has_rgb or has_normal


def vertex_key(f3d_vert, group_index, material_index) -> tuple:
    # Alpha stays in the key: fog rides on it, and F3DEX3 keeps shade alpha per vertex in
    # flat mode while some renderers flatten it, so never merging across alpha is safe.
    return (
        tuple(f3d_vert.position),
        tuple(f3d_vert.uv),
        f3d_vert.stOffset,
        f3d_vert.alpha,
        group_index,
        material_index,
    )


def shade_of(f3d_vert) -> tuple:
    rgb = None if f3d_vert.rgb is None else tuple(f3d_vert.rgb)
    normal = None if f3d_vert.normal is None else tuple(f3d_vert.normal)
    return rgb, normal


def write_shade(f3d_vert, shade: tuple) -> None:
    f3d_vert.rgb = _same_type_as(f3d_vert.rgb, shade[0])
    f3d_vert.normal = _same_type_as(f3d_vert.normal, shade[1])


def poison_shade(shade: tuple) -> tuple:
    """A deliberately wrong shade, for vertices no triangle provokes.

    Nothing reads their shade, so this changes nothing - unless a provoking vertex was
    picked wrong, and then the mistake shows up as a magenta or unlit face.
    """
    rgb, normal = shade
    return (
        (1.0, 0.0, 1.0) if rgb is not None else None,
        tuple(-value for value in normal) if normal is not None else None,
    )


def _same_type_as(old, values):
    # Rebuild as the type being replaced (a frozen Vector in the exporter).
    if values is None or old is None:
        return values
    rebuilt = type(old)(values)
    freeze = getattr(rebuilt, "freeze", None)
    return freeze() if freeze is not None else rebuilt


def match_shades_to_keys(tris: list[tuple]) -> dict:
    """Give as many shades as possible a key of their own, with Kuhn's algorithm.

    `tris` is a list of (key0, key1, key2, face_shade). A shade that owns a key costs no
    extra vertex, and a per face choice does not find those: on a cube every corner is a
    candidate for three faces, so any fixed order wastes one and ends at 9 vertices
    instead of 8.
    """
    candidates: dict[Hashable, set] = {}
    for key0, key1, key2, shade in tris:
        keys = {key0, key1, key2}
        candidates[shade] = candidates[shade] & keys if shade in candidates else keys

    # sorted for reproducible exports
    ordered = {shade: sorted(keys, key=repr) for shade, keys in candidates.items()}
    key_to_shade: dict = {}

    def assign(shade, seen: set, depth: int) -> bool:
        if depth > MAX_AUGMENT_DEPTH:
            return False
        for key in ordered[shade]:
            if key in seen:
                continue
            seen.add(key)
            holder = key_to_shade.get(key)
            if holder is None or assign(holder, seen, depth + 1):
                key_to_shade[key] = shade
                return True
        return False

    # Most constrained first: fewer candidate keys means less room to move later.
    for shade in sorted(ordered, key=lambda shade: len(ordered[shade])):
        assign(shade, set(), 0)

    return {shade: key for key, shade in key_to_shade.items()}


@dataclass
class _Slot:
    buffer_vert: object
    shade: tuple
    claimed: bool = False
    inherited: bool = False


class FlatVertexPool:
    """The vertices of the current vertex buffer, indexed by key.

    A slot is claimed once a triangle provokes it; until then nothing has read its shade,
    so it can be overwritten. Inherited slots (a parent limb's vertices in SM64 skinning)
    are already written out and start claimed.
    """

    def __init__(self):
        self.by_key: dict[Hashable, list[_Slot]] = defaultdict(list)

    def reset(self) -> None:
        self.by_key.clear()

    def add(self, buffer_vert, key: Hashable, claimed: bool = False, inherited: bool = False) -> _Slot:
        slot = _Slot(buffer_vert, shade_of(buffer_vert.f3dVert), claimed, inherited)
        self.by_key[key].append(slot)
        return slot

    def reusable(self, key: Hashable) -> Optional[_Slot]:
        """Any slot with this key, which is all a corner that does not provoke needs."""
        slots = self.by_key.get(key)
        return slots[0] if slots else None

    def provokable(self, key: Hashable, shade: tuple) -> Optional[_Slot]:
        """Slot that can provoke this shade: one that already has it, or an unclaimed one."""
        unclaimed = None
        for slot in self.by_key.get(key, ()):
            if slot.shade == shade:
                return slot
            if unclaimed is None and not slot.claimed:
                unclaimed = slot
        return unclaimed

    def claim(self, slot: _Slot, shade: tuple) -> None:
        if slot.shade != shade:
            write_shade(slot.buffer_vert.f3dVert, shade)
            slot.shade = shade
        slot.claimed = True

    def poison_unread_shades(self) -> int:
        """Overwrite the shade of every slot nothing provokes, see poison_shade."""
        count = 0
        for slots in self.by_key.values():
            for slot in slots:
                if slot.claimed or slot.inherited:
                    continue
                slot.shade = poison_shade(slot.shade)
                write_shade(slot.buffer_vert.f3dVert, slot.shade)
                count += 1
        return count

    def new_vertex_count(self, keys: tuple, provoking_position: int, shade: tuple) -> int:
        """How many vertices this choice of provoking corner would add to the buffer.

        Counts each corner on its own, so a degenerate triangle whose corners share a key
        is overestimated. That only flushes the buffer a face early, never too late.
        """
        provoking_key = keys[provoking_position]
        count = 0 if self.provokable(provoking_key, shade) else 1
        for position, key in enumerate(keys):
            if position != provoking_position and key != provoking_key and self.reusable(key) is None:
                count += 1
        return count

"""Tests for the flat shading provoking-vertex assignment.

`fast64_internal/f3d/flat_shading.py` imports nothing from bpy, so it is driven here with
stand-in vertices. `assign_corpus` replays what TriangleConverter.addFace does, which
keeps these numbers and the exporter's numbers describing one algorithm.

Run with `python tests/test_flat_shading.py`; no Blender and no test framework needed.
"""

import itertools
import math
import os
import random
import sys
from dataclasses import dataclass, field
from typing import Optional

# Imported by path: going through fast64_internal would pull in bpy.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fast64_internal", "f3d"))

from flat_shading import (  # noqa: E402
    FlatVertexPool,
    match_shades_to_keys,
    poison_shade,
    shade_of,
    vertex_key,
    write_shade,
)


# Stand-ins for F3DVert and BufferVertex, holding only what the module touches.
@dataclass
class FakeF3DVert:
    position: tuple
    normal: Optional[tuple]
    rgb: Optional[tuple] = None
    uv: tuple = (0.0, 0.0)
    stOffset: Optional[tuple] = None
    alpha: float = 1.0


@dataclass
class FakeBufferVert:
    f3dVert: FakeF3DVert
    groupIndex: Optional[int] = None
    materialIndex: int = 0


@dataclass
class Face:
    corners: tuple
    shade: tuple


@dataclass
class Result:
    vertices: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    triangles: list = field(default_factory=list)


def key_of(corner: FakeBufferVert) -> tuple:
    return vertex_key(corner.f3dVert, corner.groupIndex, corner.materialIndex)


def preferred_keys(faces: list) -> dict:
    return match_shades_to_keys([(*[key_of(corner) for corner in face.corners], face.shade) for face in faces])


def assign_corpus(faces: list) -> Result:
    """Replay TriangleConverter.addFace over a whole material, with no buffer limit."""
    pool = FlatVertexPool()
    preferred = preferred_keys(faces)
    result = Result()

    for face in faces:
        keys = tuple(key_of(corner) for corner in face.corners)
        preferred_key = preferred.get(face.shade)
        if preferred_key is not None and preferred_key in keys:
            flag = keys.index(preferred_key)
        else:
            flag = min(range(3), key=lambda position: pool.new_vertex_count(keys, position, face.shade))

        verts = [None, None, None]
        for position in [flag, *(other for other in range(3) if other != flag)]:
            provoking = position == flag
            slot = pool.provokable(keys[position], face.shade) if provoking else pool.reusable(keys[position])
            if slot is None:
                corner = face.corners[position]
                if provoking:
                    write_shade(corner.f3dVert, face.shade)
                slot = pool.add(corner, keys[position], claimed=provoking)
                result.vertices.append(corner)
            elif provoking:
                pool.claim(slot, face.shade)
            verts[position] = slot.buffer_vert

        result.flags.append(flag)
        result.triangles.append(tuple(verts))
    return result


# Meshes. Deterministic, and triangulated the way the optimum assumes.
def tri() -> tuple:
    return [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)]


def tetra() -> tuple:
    verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
    return verts, [(0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)]


def cube() -> tuple:
    verts = [
        (-1, -1, -1),
        (1, -1, -1),
        (1, 1, -1),
        (-1, 1, -1),
        (-1, -1, 1),
        (1, -1, 1),
        (1, 1, 1),
        (-1, 1, 1),
    ]
    faces = [
        (0, 3, 2),
        (0, 2, 1),
        (4, 5, 6),
        (4, 6, 7),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
    ]
    return verts, faces


def hex_prism() -> tuple:
    """Hexagonal prism without a bottom: 16 triangles, 12 vertices is the optimum."""
    ring = lambda z: [  # noqa: E731
        (round(math.cos(math.radians(60 * i)), 6), round(math.sin(math.radians(60 * i)), 6), z) for i in range(6)
    ]
    verts = ring(1.0) + ring(0.0)
    faces = [(0, i, i + 1) for i in range(1, 5)]  # cap, fanned from t0
    for k in range(6):
        t_next, b_k, b_next = (k + 1) % 6, 6 + k, 6 + (k + 1) % 6
        faces += [(b_k, t_next, k), (b_k, b_next, t_next)]  # both side triangles provoke at b_k
    return verts, faces


def bobomb_top() -> tuple:
    """Hexagonal prism plus a four vertex fuse cone: 20 triangles, optimum 16 vertices."""
    verts, faces = hex_prism()
    base = len(verts)
    verts = verts + [(0.0, 0.0, 2.0), (0.25, 0.0, 1.0), (-0.125, 0.216506, 1.0), (-0.125, -0.216506, 1.0)]
    tip, a, b, c = base, base + 1, base + 2, base + 3
    return verts, faces + [(tip, a, b), (tip, b, c), (tip, c, a), (a, c, b)]


def grid(n: int = 8) -> tuple:
    verts = [(x / n * 2 - 1, y / n * 2 - 1, 0.0) for y in range(n + 1) for x in range(n + 1)]
    faces = []
    for y in range(n):
        for x in range(n):
            i = y * (n + 1) + x
            faces += [(i, i + 1, i + n + 2), (i, i + n + 2, i + n + 1)]
    return verts, faces


def face_normal(verts: list, face: tuple) -> tuple:
    ax, ay, az = verts[face[0]]
    bx, by, bz = verts[face[1]]
    cx, cy, cz = verts[face[2]]
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    normal = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
    length = sum(component**2 for component in normal) ** 0.5 or 1.0
    # Quantized like getLoopNormal, so "same normal" means the same thing here.
    return tuple(round(component / length * 2**16) for component in normal)


def flat_faces(verts: list, faces: list) -> list:
    """Flat shaded mesh: every corner of a face carries that face's normal."""
    return [
        Face(
            corners=tuple(
                FakeBufferVert(FakeF3DVert(position=verts[index], normal=face_normal(verts, face))) for index in face
            ),
            shade=(None, face_normal(verts, face)),
        )
        for face in faces
    ]


def vertices_today(faces: list) -> int:
    """What the exporter emits without the optimization: one vertex per (key, shade)."""
    return len({(key_of(corner), shade_of(corner.f3dVert)) for face in faces for corner in face.corners})


def distinct_keys(faces: list) -> int:
    """No assignment can use fewer vertices than there are distinct keys."""
    return len({key_of(corner) for face in faces for corner in face.corners})


def optimum(faces: list) -> int:
    """Exact minimum by brute force: for a fixed choice of provoking corners the count is
    sum over keys of max(1, distinct shades demanded at that key)."""
    keys = {key_of(corner) for face in faces for corner in face.corners}
    best = None
    for choice in itertools.product(range(3), repeat=len(faces)):
        demanded = {key: set() for key in keys}
        for face, provoking in zip(faces, choice):
            demanded[key_of(face.corners[provoking])].add(face.shade)
        total = sum(max(1, len(shades)) for shades in demanded.values())
        best = total if best is None else min(best, total)
    return best


def check_invariants(faces: list, result: Result) -> None:
    assert len(result.triangles) == len(faces)
    for face, verts, flag in zip(faces, result.triangles, result.flags):
        assert shade_of(verts[flag].f3dVert) == face.shade, "provoking vertex lost the face shade"
        for corner, vert in zip(face.corners, verts):
            assert key_of(vert) == key_of(corner), "corner changed to a different vertex"


def run(builder) -> tuple:
    """Returns (vertices after, lower bound, vertices today).

    The baseline is measured before assigning: claiming a vertex rewrites its shade.
    """
    faces = flat_faces(*builder())
    today, bound = vertices_today(faces), distinct_keys(faces)
    result = assign_corpus(faces)
    check_invariants(faces, result)
    return len(result.vertices), bound, today


def test_single_triangle():
    count, bound, _ = run(tri)
    assert count == bound == 3


def test_tetrahedron():
    count, bound, today = run(tetra)
    assert (today, count, bound) == (12, 4, 4)


def test_cube():
    count, bound, today = run(cube)
    assert (today, count, bound) == (24, 8, 8)


def test_hexagonal_prism():
    count, bound, today = run(hex_prism)
    assert (today, count, bound) == (30, 12, 12)


def test_bobomb_top():
    count, bound, today = run(bobomb_top)
    assert (today, count, bound) == (42, 16, 16)


def test_planar_mesh_is_untouched():
    """One normal over the whole mesh: nothing to win and nothing to lose."""
    count, _, today = run(grid)
    assert count == today


def test_never_worse_than_today():
    for builder in (tri, tetra, cube, hex_prism, bobomb_top, grid):
        count, bound, today = run(builder)
        assert bound <= count <= today


def test_matches_brute_force_optimum():
    """Against the exact optimum on random small meshes; 3^7 assignments is cheap."""
    rng = random.Random(20260919)
    for _ in range(20):
        vert_count = rng.randint(4, 7)
        verts = [(rng.randint(-3, 3), rng.randint(-3, 3), rng.randint(-3, 3)) for _ in range(vert_count)]
        faces = []
        while len(faces) < 7:
            face = tuple(rng.sample(range(vert_count), 3))
            if face_normal(verts, face) != (0, 0, 0):
                faces.append(face)
        built = flat_faces(verts, faces)
        expected = optimum(built)
        result = assign_corpus(built)
        check_invariants(built, result)
        assert len(result.vertices) == expected


def test_alpha_stays_in_the_key():
    """Corners at one position but with different alpha are different vertices even in
    flat mode: alpha is interpolated per vertex and fog rides on it."""
    opaque = FakeBufferVert(FakeF3DVert(position=(0, 0, 0), normal=(0, 1, 0), alpha=1.0))
    faded = FakeBufferVert(FakeF3DVert(position=(0, 0, 0), normal=(1, 0, 0), alpha=0.5))
    assert key_of(opaque) != key_of(faded)


def test_unclaimed_slot_can_be_claimed_once():
    pool = FlatVertexPool()
    vert = FakeBufferVert(FakeF3DVert(position=(1, 2, 3), normal=(0, 1, 0)))
    key = key_of(vert)
    pool.add(vert, key)

    assert pool.reusable(key).buffer_vert is vert
    side = (None, (1, 0, 0))
    pool.claim(pool.provokable(key, side), side)
    assert shade_of(vert.f3dVert) == side
    assert pool.provokable(key, (None, (0, 0, 1))) is None


def test_inherited_slot_is_never_rewritten():
    """SM64 skinning: a parent limb's vertices are already written out, so they may only
    provoke a face whose shade they already carry."""
    pool = FlatVertexPool()
    vert = FakeBufferVert(FakeF3DVert(position=(0, 0, 0), normal=(0, 1, 0)))
    key = key_of(vert)
    pool.add(vert, key, claimed=True, inherited=True)

    assert pool.reusable(key).buffer_vert is vert
    assert pool.provokable(key, (None, (0, 1, 0))).buffer_vert is vert
    assert pool.provokable(key, (None, (1, 0, 0))) is None


def test_matching_prefers_a_shared_corner():
    """Both triangles of a quad must provoke at a corner they share, or the quad costs an
    extra vertex."""
    faces = flat_faces([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [(0, 1, 2), (0, 2, 3)])
    shared = {key_of(faces[0].corners[0]), key_of(faces[0].corners[2])}
    assert preferred_keys(faces)[faces[0].shade] in shared


def test_poison_only_touches_unread_slots():
    """The debug poison must leave provoking and inherited vertices alone."""
    pool = FlatVertexPool()
    up, side = (None, (0, 1, 0)), (None, (1, 0, 0))
    unread = FakeBufferVert(FakeF3DVert(position=(0, 0, 0), normal=up[1]))
    provoking = FakeBufferVert(FakeF3DVert(position=(1, 0, 0), normal=up[1]))
    inherited = FakeBufferVert(FakeF3DVert(position=(2, 0, 0), normal=side[1]))
    pool.add(unread, key_of(unread))
    pool.add(provoking, key_of(provoking), claimed=True)
    pool.add(inherited, key_of(inherited), claimed=True, inherited=True)

    assert pool.poison_unread_shades() == 1
    assert shade_of(unread.f3dVert) == poison_shade(up)
    assert shade_of(provoking.f3dVert) == up
    assert shade_of(inherited.f3dVert) == side


def test_poison_keeps_alpha():
    """Fog rides on shade alpha, so poisoning must not touch it."""
    vert = FakeF3DVert(position=(0, 0, 0), normal=(0, 1, 0), rgb=(0.5, 0.5, 0.5), alpha=0.25)
    write_shade(vert, poison_shade(shade_of(vert)))
    assert vert.alpha == 0.25
    assert vert.rgb == (1.0, 0.0, 1.0)
    assert vert.normal == (0, -1, 0)


def main() -> int:
    failures = []
    tests = [(name, test) for name, test in sorted(globals().items()) if name.startswith("test_") and callable(test)]
    for name, test in tests:
        try:
            test()
        except Exception as exc:
            failures.append(f"FAIL {name}: {type(exc).__name__}: {exc}")

    for failure in failures:
        print(failure)
    print(f"{len(tests) - len(failures)}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

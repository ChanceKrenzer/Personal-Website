"""Converts SolidWorks STL exports into a GLB for <model-viewer>.

Usage:
  python tools/stl2glb.py out.glb [options] part.stl[@dx,dy,dz[@rx,ry,rz]] [part.stl ...]

Each part can be shifted (mm) and rotated (degrees, applied X then Y then Z)
before it's merged, which is how separately exported print sections are put
back together. The result is centred, converted to metres (glTF's unit) and
written with smooth normals that stay sharp across creases.

Options:
  --two-tone=R   paint faces more than R mm from the model's long axis in a
                 second colour. On the high-speed quadcopter that separates the
                 printed body (red) from the arms and nacelles (black).
  --edges        add dark feature lines along every crease and open boundary,
                 the way NX and SolidWorks draw a shaded-with-edges view.

Needs only numpy.
"""
import json
import struct
import sys

import numpy as np

CREASE_DEG = 35

GREY = [0.28, 0.32, 0.37, 1]     # CAD grey
BODY = [0.50, 0.025, 0.02, 1]     # printed red
ARMS = [0.025, 0.025, 0.03, 1]     # printed black
EDGE = [0.03, 0.03, 0.04, 1]


def load_stl(path):
    data = open(path, "rb").read()
    if data[:5].lower() == b"solid" and b"facet" in data[:400]:
        verts = [list(map(float, line.split()[1:4]))
                 for line in data.decode("latin1").splitlines() if line.strip().startswith("vertex")]
        return np.array(verts, dtype=np.float64).reshape(-1, 3, 3)
    count = struct.unpack("<I", data[80:84])[0]
    record = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    return np.frombuffer(data, record, count=count, offset=84)["v"].astype(np.float64)


def rotation(rx, ry, rz):
    rx, ry, rz = np.radians([rx, ry, rz])
    x = np.array([[1, 0, 0], [0, np.cos(rx), -np.sin(rx)], [0, np.sin(rx), np.cos(rx)]])
    y = np.array([[np.cos(ry), 0, np.sin(ry)], [0, 1, 0], [-np.sin(ry), 0, np.cos(ry)]])
    z = np.array([[np.cos(rz), -np.sin(rz), 0], [np.sin(rz), np.cos(rz), 0], [0, 0, 1]])
    return z @ y @ x


def parse_part(arg):
    path, *rest = arg.split("@")
    shift = np.array(list(map(float, rest[0].split(","))) if rest else [0, 0, 0])
    rot = list(map(float, rest[1].split(","))) if len(rest) > 1 else [0, 0, 0]
    return load_stl(path) @ rotation(*rot).T + shift


def face_normals(tris):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    return n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-20)


def weld(tris):
    """Index of each corner's position once coincident corners are merged."""
    _, ids = np.unique(np.round(tris.reshape(-1, 3), 7), axis=0, return_inverse=True)
    return ids.ravel()


def smooth_normals(fn, ids):
    corner_fn = np.repeat(fn, 3, axis=0)
    summed = np.zeros((ids.max() + 1, 3))
    np.add.at(summed, ids, corner_fn)
    avg = summed[ids]
    avg /= np.linalg.norm(avg, axis=1, keepdims=True) + 1e-20
    sharp = np.einsum("ij,ij->i", avg, corner_fn) < np.cos(np.radians(CREASE_DEG))
    return np.where(sharp[:, None], corner_fn, avg)


def feature_edges(tris, fn, ids):
    """Line segments along creases steeper than CREASE_DEG and along open boundaries."""
    corners = ids.reshape(-1, 3)
    pairs = np.concatenate([corners[:, [0, 1]], corners[:, [1, 2]], corners[:, [2, 0]]])
    faces = np.tile(np.arange(len(tris)), 3)
    pairs.sort(axis=1)
    order = np.lexsort((pairs[:, 1], pairs[:, 0]))
    pairs, faces = pairs[order], faces[order]
    _, start, count = np.unique(pairs, axis=0, return_index=True, return_counts=True)
    keep = count != 2                                   # boundaries and non-manifold edges
    two = count == 2
    dots = np.einsum("ij,ij->i", fn[faces[start[two]]], fn[faces[start[two] + 1]])
    keep[two] = dots < np.cos(np.radians(CREASE_DEG))
    positions = np.zeros((ids.max() + 1, 3))
    positions[ids] = tris.reshape(-1, 3)
    return positions[pairs[start[keep]]].reshape(-1, 3)


def write_glb(path, positions, normals, groups, edges):
    """groups: (colour, corner mask) per triangle primitive; edges: (n, 3) segment endpoints or None."""
    both = np.round(np.hstack([positions, normals]), 6)
    unique, index = np.unique(both, axis=0, return_inverse=True)
    index = index.ravel().astype("<u4")
    blobs = [unique[:, :3].astype("<f4"), unique[:, 3:].astype("<f4")] + [index[mask] for _, mask in groups]
    if edges is not None:
        blobs.append(edges.astype("<f4"))
    raw = [b.tobytes() for b in blobs]
    offsets = np.cumsum([0] + [len(r) for r in raw[:-1]]).tolist()
    binary = b"".join(raw)

    accessors = [
        {"bufferView": 0, "componentType": 5126, "count": len(unique), "type": "VEC3",
         "min": blobs[0].min(0).tolist(), "max": blobs[0].max(0).tolist()},
        {"bufferView": 1, "componentType": 5126, "count": len(unique), "type": "VEC3"},
    ] + [{"bufferView": 2 + k, "componentType": 5125, "count": len(blobs[2 + k]), "type": "SCALAR"}
         for k in range(len(groups))]
    materials = [{"pbrMetallicRoughness": {"baseColorFactor": colour, "metallicFactor": 0, "roughnessFactor": 0.6}}
                 for colour, _ in groups]
    primitives = [{"attributes": {"POSITION": 0, "NORMAL": 1}, "indices": 2 + k, "material": k}
                  for k in range(len(groups))]
    if edges is not None:
        accessors.append({"bufferView": len(blobs) - 1, "componentType": 5126, "count": len(edges), "type": "VEC3",
                          "min": blobs[-1].min(0).tolist(), "max": blobs[-1].max(0).tolist()})
        materials.append({"pbrMetallicRoughness": {"baseColorFactor": EDGE}})
        primitives.append({"attributes": {"POSITION": len(accessors) - 1}, "mode": 1, "material": len(materials) - 1})

    gltf = {
        "asset": {"version": "2.0", "generator": "tools/stl2glb.py"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
        "materials": materials, "meshes": [{"primitives": primitives}], "accessors": accessors,
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [{"buffer": 0, "byteOffset": offsets[k], "byteLength": len(raw[k]),
                         "target": 34963 if 2 <= k < 2 + len(groups) else 34962}
                        for k in range(len(raw))],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    binary += b"\0" * (-len(binary) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(binary)))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(binary), 0x004E4942) + binary)
    return len(unique), len(index) // 3


if __name__ == "__main__":
    args = sys.argv[1:]
    out = args.pop(0)
    two_tone = next((float(a.split("=")[1]) for a in args if a.startswith("--two-tone=")), None)
    tris = np.concatenate([parse_part(p) for p in args if not p.startswith("--")])
    lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
    tris = tris - (lo + hi) / 2                          # centre on the bounding box

    fn, ids = face_normals(tris), weld(tris)
    normals = smooth_normals(fn, ids)
    edges = feature_edges(tris, fn, ids) / 1000.0 if "--edges" in args else None
    if two_tone is None:
        groups = [(GREY, np.ones(len(ids), bool))]
    else:
        axis = int(np.argmax(hi - lo))                   # the airframe's long axis
        radius = np.linalg.norm(np.delete(tris.mean(axis=1), axis, axis=1), axis=1)
        outer = np.repeat(radius > two_tone, 3)
        groups = [(BODY, ~outer), (ARMS, outer)]
    verts, faces = write_glb(out, tris.reshape(-1, 3) / 1000.0, normals, groups, edges)
    lines = 0 if edges is None else len(edges) // 2
    print(f"{out}: {faces} triangles, {lines} edge lines, {verts} vertices, {np.round(hi - lo, 1)} mm")

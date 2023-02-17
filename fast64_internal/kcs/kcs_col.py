# ------------------------------------------------------------------------
#    Header
# ------------------------------------------------------------------------
from __future__ import annotations

import bpy

import os, struct, math
from pathlib import Path
from mathutils import Vector, Euler, Matrix
from collections import namedtuple
from dataclasses import dataclass, field
from typing import BinaryIO, TextIO

from .kcs_data import *
from .kcs_utils import *
from ..utility import (
    propertyGroupGetEnums,
    transform_mtx_blender_to_n64,
    duplicateHierarchy,
    cleanupDuplicatedObjects,
    parentObject,
    PluginError,
)

# ------------------------------------------------------------------------
#    Classes
# ------------------------------------------------------------------------

# for selecting proper misc type of imp bin
class MiscBinary(BinProcess):
    _vert_sig = (0x270F, 0x270F, 0x270F)

    def __new__(self, file: BinaryIO):
        self.file = file
        sig_obj = self.upt(self, 4, ">3H", 6)
        if sig_obj == self._vert_sig:
            feature = "obj"
        else:
            sig_obj = self.upt(self, 16, ">3H", 6)
            if sig_obj == self._vert_sig:
                feature = "level"
            else:
                feature = "particle"
        subclass_map = {subclass.feature: subclass for subclass in self.__subclasses__()}
        subclass = subclass_map[feature]
        instance = super(MiscBinary, subclass).__new__(subclass)
        return instance


class LevelBinary(MiscBinary):
    feature = "level"

    def __init__(self, file: BinaryIO):
        self.main_header = self.upt(0, ">3L", 12)
        self.col_header = self.upt(self.main_header[0], ">17L", 68)
        self.node_header = self.upt(self.main_header[1], ">4L", 16)
        self.num_nodes = self.node_header[0]
        self.path_nodes = {}
        for i in range(self.num_nodes):
            self.decode_node(i)
        self.entities = []
        x = 0
        start = self.main_header[2]
        entity = namedtuple("entity", "node bank id action res_flag spawn_flag eep pos rot scale")
        vec3f = namedtuple("vec3", "x y z")
        if start:
            while True:
                sig = self.upt(start + x * 0x2C, ">L", 4)
                if sig[0] == 0x99999999:
                    break
                ent = self.upt(start + x * 0x2C, ">6BH9f", 0x2C)
                pos, rot, scale = [vec3f._make(ent[3 * i + 7 : 3 * i + 10]) for i in range(3)]
                self.entities.append(entity._make([*ent[:7], pos, rot, scale]))
                x += 1
        self.decode_col()

    def decode_node(self, num: int):
        node = BpyNode(num)
        kirb = namedtuple(
            "kirb_node",
            "node EnterEnum w l a DestNode unused shad1 shad2 shad3 unused2 WarpFlag opt1 opt2 opt3 opt4 unused3",
        )
        cam = namedtuple(
            "cam_node",
            """Profile pad LockX LockY LockZ pad PanHiLo PanLo PanYaw pad pad FocusX FocusY FocusZ
        NearClip FarClip CamR1 CamR2 CamYaw1 CamYaw2 CamRadius1 CamRadius2 FOV1 FOV2 CamPhi1 CamPhi2
        CamXLock1 CamXLock2 CamYLock1 CamYLock2 CamZLock1 CamZLock2 CamYawLock1 CamYawLock2 CamPitchLock1 CamPitchLock2""",
            rename=True,
        )
        path_node = self.node_header[1] + (num * 16)
        node.path_node = self.upt(path_node, ">3L2H", 16)
        node.kirb_node = kirb._make(self.upt(node.path_node[0], ">2H4B4B4H2fL", 0x20))
        node.cam_node = cam._make(self.upt(node.path_node[0] + 0x20, ">10BH25f", 0x70))
        node.path_footer = self.upt(node.path_node[1], ">2HfLf2L", 0x18)
        node.num_connections = node.path_node[3]
        node.node_connections = self.upt(
            node.path_node[2], ">%dB" % (0x4 * node.num_connections), 0x4 * node.num_connections
        )
        node.is_loop = node.path_node[4]
        self.path_nodes[num] = node
        node.path_matrix = [self.upt(node.path_footer[3] + 12 * i, ">3f", 12) for i in range(node.path_footer[1])]

    def decode_col(self):
        tri_num = self.col_header[1]
        vert_num = self.col_header[3]
        water_num = self.col_header[14]
        self.triangles = [self.upt(a * 20 + self.col_header[0], ">10H", 20) for a in range(1, tri_num)]
        self.vertices = [self.upt(a * 6 + self.col_header[2], ">3h", 6) for a in range(1, vert_num)]
        de_groups = self.col_header[11]
        de_indices = self.col_header[12]
        x = 0
        self.de_tris = {}
        pops = []
        while x + de_groups + 2 < de_indices:
            grp = self.upt(x + de_groups, ">3H", 6)
            if grp[0] != 0:
                indices = [self.upt(2 * grp[1] + de_indices + 2 * i, ">H", 2)[0] - 1 for i in range(grp[0])]
                self.de_tris[grp[2]] = [self.triangles[a] for a in indices]
                pops.extend(indices)
            x += 6
        if self.de_tris:
            pops.sort(reverse=True)
            [self.triangles.pop(a) for a in pops]


# unused currently, will raise error
class ObjectBinary(MiscBinary):
    feature = "obj"


# unused currently, will raise error
class ParticleBinary(MiscBinary):
    feature = "particle"


# dummy class to be filled in later when c/asm importing works
class MiscText:
    pass


# for i/o of node data
class BpyNode:
    def __init__(self, num: int):
        self.index = num

    def cam_imp(self, cam: bpy.types.Camera, vol: bpy.types.Object, scale: float):
        Null = lambda x, y: x * (x != y)
        kcs_cam = cam.data.KCS_cam
        camera_node = self.cam_node
        kcs_cam.axis_locks = [camera_node.LockX != 0, camera_node.LockY != 0, camera_node.LockZ != 0]
        kcs_cam.profile_view = camera_node.Profile
        kcs_cam.pan_ahead, kcs_cam.pan_vertical, kcs_cam.pan_below = (
            camera_node.PanYaw,
            camera_node.PanHiLo,
            camera_node.PanLo,
        )
        kcs_cam.follow_yaw = (camera_node.CamYaw1, camera_node.CamYaw2)
        kcs_cam.follow_radius = (camera_node.CamRadius1, camera_node.CamRadius2)
        kcs_cam.follow_pitch = (camera_node.CamPhi1, camera_node.CamPhi2)
        kcs_cam.clip_planes = (camera_node.NearClip, camera_node.FarClip)
        kcs_cam.focus_location = (camera_node.FocusX, camera_node.FocusY, camera_node.FocusZ)
        kcs_cam.cam_bounds_pitch = (camera_node.CamYawLock1, camera_node.CamYawLock2)
        kcs_cam.cam_bounds_yaw = (camera_node.CamPitchLock1, camera_node.CamPitchLock2)
        kcs_cam.cam_bounds_x = (camera_node.CamXLock1, camera_node.CamXLock2)
        kcs_cam.cam_bounds_y = (camera_node.CamYLock1, camera_node.CamYLock2)
        kcs_cam.cam_bounds_z = (camera_node.CamZLock1, camera_node.CamZLock2)
        x, y, z = (
            (Null(camera_node.CamXLock1, 9999) + Null(camera_node.CamXLock2, -9999)) / (2 * scale),
            (Null(camera_node.CamYLock1, 9999) + Null(camera_node.CamYLock2, -9999)) / (2 * scale),
            (Null(camera_node.CamZLock1, 9999) + Null(camera_node.CamZLock2, -9999)) / (2 * scale),
        )
        cam.location = Vector((x, y, z)) - cam.parent.location
        vol.scale = (x, z, y)

    def path_imp(self, path: bpy.types.Object, scale: float):
        kcs_node = path.data.KCS_node
        kcs_node.node_num = self.index + 1
        if self.num_connections == 1:
            kcs_node.next_node = self.node_connections[2] + 1
            kcs_node.prev_node = self.node_connections[2] + 1
            kcs_node.lock_backward = self.node_connections[0] != 0
            kcs_node.lock_forward = self.node_connections[3] == 0
        elif self.num_connections == 2:
            kcs_node.next_node = self.node_connections[2] + 1
            kcs_node.prev_node = self.node_connections[6] + 1
            kcs_node.lock_backward = self.node_connections[0] != 0
            kcs_node.lock_forward = self.node_connections[4] == 0
        num_pts = self.path_footer[1]
        path.data.splines.remove(path.data.splines[0])
        sp = path.data.splines.new("POLY")
        sp.points.add(num_pts - 1)
        first = self.path_matrix[0]
        path.location = [
            f / scale for f in (first[0], -first[2], first[1])
        ]  # rotation is not applied to location so I have to manually swap coords
        for i, s in enumerate(sp.points):
            coord = self.path_matrix[i]
            s.co = [*[(f - a) / scale for f, a in zip(coord, first)], 0]
        # warps
        shade = self.kirb_node[6:10]  # not implemented yet
        warp = self.kirb_node[2:6]
        # flag values to enums
        Locations = {
            0: "walk start",
            1: "walk end",
            2: "appear start",
            3: "appear end",
        }
        Actions = {
            0: "walk",
            1: "stand",
            2: "jump up",
            3: "jump forward",
            # 4 is unk
            5: "climb wall up",
            6: "climb wall down",
            7: "climb rope up",
            8: "climb rope down",
            9: "walking (unk)",
            10: "jumping (unk)",
            11: "fall from air",
        }
        # kcs_node.entrance_location = Locations.get(self.kirb_node.EnterEnum >> 0xFF)
        # kcs_node.entrance_action = Actions.get(self.kirb_node.EnterEnum & 0xFF)
        # kcs_node.stage_dest = warp[0:3]
        kcs_node.warp_node = self.kirb_node.DestNode
        kcs_node.enable_warp = self.kirb_node.WarpFlag & 1


# interim between bpy props and misc blocks, used for importing and exporting
class BpyCollision:
    # given a class full of formatted data, writes
    # data to blender. also gets data from blender
    # for class
    def __init__(self, rt: bpy.types.Object, collection: bpy.types.Collection):
        self.rt = rt  # this is an empty with kcs object type collision
        self.collection = collection

    # creates a KCS_Level class which is used to export C data
    def init_kcs_col_from_bpy(self, scale: float):
        kcs_level = KCS_Level()
        # create duplicate objects to work on
        tempObj, kcs_level.allObjs = duplicateHierarchy(self.rt, None, True, 0, include_curves=1, include_cameras=1)
        # make root location 0 so that area is centered on root
        root_transform = (transform_mtx_blender_to_n64() @ tempObj.matrix_local) * scale

        # get all child meshes
        def loop_children(obj, kcs_level, transform):
            for child in obj.children:
                if self.is_kcs_col(child):
                    # depending on the type of object, allocate to a different list
                    # curves aka nodes should only be the single node
                    # other objects in hierarchy are ignored
                    if child.type == "CURVE":
                        self.create_node(child, transform @ child.matrix_local, scale, kcs_level)
                        # do not loop over children for paths
                        continue
                    if child.type == "MESH":
                        self.create_col_mesh(child, transform @ child.matrix_local, kcs_level)
                    if child.children:
                        loop_children(child, kcs_level, transform @ child.matrix_local)

        loop_children(tempObj, kcs_level, root_transform)

        # now add the root if it is a mesh
        if tempObj.type == "MESH":
            kcs_level.mesh_data.append(self.create_col_mesh(tempObj, root_transform))
        return kcs_level

    def create_entity(self, obj: bpy.types.Object, transform: Matrix, scale: float, kcs_level: KCS_Level, node_num: int):
        ent_matrix = transform @ obj.matrix_local
        ent_data = obj.KCS_ent
        kcs_entity = StructContainer(
            (
                node_num,
                ent_data.bank_num,
                ent_data.index_num,
                ent_data.action,
                ent_data.flags,
                ent_data.respawn,
                ent_data.eeprom_data,
                tuple(ent_matrix.translation),
                tuple(ent_matrix.to_euler("XYZ")),
                tuple(ent_matrix.to_scale())
            )
        )
        kcs_level.entities.append(kcs_entity)
        return kcs_entity
        
    def create_node(self, obj: bpy.types.Object, transform: Matrix, scale: float, kcs_level: KCS_Level):
        kcs_node = KCS_Node(obj, transform, scale)
        kcs_level.node_data.append(kcs_node)
        # grab entities
        for child in obj.children:
            if child.type == "EMPTY" and child.KCS_obj.KCS_obj_type == "Entity":
                self.create_entity(child, transform @ child.matrix_local, scale, kcs_level, obj.data.KCS_node.node_num)
        return kcs_node

    def create_col_mesh(self, obj: bpy.types.Object, transform: Matrix, kcs_level: KCS_Level):
        # generate mesh data and store in parent
        kcs_mesh = KCS_Mesh(obj)
        vertices, triangles = kcs_mesh.calc_mesh_data(transform, len(kcs_level.vertices), kcs_level.normals)
        kcs_level.vertices.extend(vertices)
        kcs_level.triangles.extend(triangles)
        kcs_level.mesh_data.append(kcs_mesh)
        return kcs_mesh

    def is_kcs_col(self, obj: bpy.types.Object):
        if obj.type == "CURVE":
            return True
        if obj.type == "MESH":
            return obj.KCS_mesh.mesh_type == "Collision"
        if obj.type == "EMPTY":
            return obj.KCS_obj.KCS_obj_type == "Collision" or obj.KCS_obj.KCS_obj_type == "Entity"

    def cleanup_collision(self, kcs_level: KCS_Level):
        cleanupDuplicatedObjects(kcs_level.allObjs)
        self.rt.select_set(True)
        bpy.context.view_layer.objects.active = self.rt

    def write_bpy_col(self, cls: Union[MiscBinary, MiscText], scene: bpy.types.Scene, scale: float):
        # start by formatting tri/vert data
        collection = self.rt.users_collection[0]
        main = self.create_pydata(cls, cls.triangles, scale)
        dynamic = {}
        for geo, dyn in cls.de_tris.items():
            dynamic[geo] = self.create_pydata(cls, dyn, scale)
            # make objs but no parenting
            dyn_mesh = make_mesh_data("kcd_dyn_mesh", dynamic[geo][0:3])
            dyn_obj = make_mesh_obj("kcs dyn obj", dyn_mesh, collection)
            self.write_mats(dyn_obj, dynamic[geo][3])
            parentObject(self.rt, dyn_obj, 0)
            dyn_obj.rotation_euler = rotate_quat_n64_to_blender(dyn_obj.rotation_quaternion).to_euler("XYZ")
            dyn_obj.KCS_mesh.mesh_type = "Collision"
            dyn_obj.KCS_mesh.col_mesh_type = "Breakable"
        # make objs and link
        main_mesh = make_mesh_data("kcs level mesh", main[0:3])
        main_obj = make_mesh_obj("kcs level obj col", main_mesh, collection)
        parentObject(self.rt, main_obj, 0)  # get col rt from rt
        apply_rotation_n64_to_bpy(main_obj)
        main_obj.KCS_mesh.mesh_type = "Collision"
        self.write_mats(main_obj, main[3])
        # format node data
        for num, node in cls.path_nodes.items():
            add_node(self.rt, collection)  # use my own operator so default settings are made
            path = self.rt.children[-1]
            # paths cannot have rotations applied
            path.rotation_euler = rotate_quat_n64_to_blender(path.rotation_quaternion).to_euler("XYZ")
            cam = path.children[0]
            vol = cam.children[0]
            node.path_imp(path, scale)
            node.cam_imp(cam, vol, scale)
            node.bpy_path = path
        # update view layer so that paths have accurate positions
        bpy.context.view_layer.update()
        # write entities
        for e in cls.entities:
            o = make_empty("KCS entity", "ARROWS", collection)
            o.KCS_obj.KCS_obj_type = "Entity"
            ent = o.KCS_ent
            path = cls.path_nodes[e.node].bpy_path
            parentObject(path, o, 1)  # parent to node, but remove transform
            rot = (e.rot[0], e.rot[1], e.rot[2])  # only rotate root since tree will inherit transform
            o.rotation_euler = rot
            loc = Vector(e.pos) / scale
            # I add because I already have the parent inverse transform applied to the location
            # because these are empties I cannot apply the transform because it has no data to apply to
            o.location += Vector([loc[0], loc[1], loc[2]])
            o.scale = e.scale

            ent.bank_num = e.bank
            ent.index_num = e.id
            ent.action = e.action
            ent.flags = e.spawn_flag
            ent.respawn = e.res_flag
            ent.eeprom_data = e.eep

    def scale_verts(self, verts: tuple, scale: float):
        scaled = []
        for v in verts:
            scaled.append([a / scale for a in v])
        return scaled

    # make (verts,[],tris,mat_dat) properly formated given tri list
    def create_pydata(self, cls: Union[MiscBinary, MiscText], tris: list[tuple], scale: float):
        verts = []
        triangles = []
        ind = set()
        mat_dat = []
        for i, t in enumerate(tris):
            tri = []
            for j, a in enumerate(t[0:3]):
                if a - 1 not in ind:
                    ind.add(a - 1)
                    tri.append(len(verts))
                    verts.append(cls.vertices[a - 1])
                else:
                    tri.append(verts.index(cls.vertices[a - 1]))
            mat_dat.append(t)
            triangles.append(tri)
        return (self.scale_verts(verts, scale), (), triangles, mat_dat)

    def write_mats(self, obj: bpy.types.Object, dat: tuple):
        polys = obj.data.polygons
        mats = set()
        mat_dict = dict()
        for p, t in zip(polys, dat):
            if t[9] == 8:
                warp = t[5]
            else:
                warp = 0
            mat = (t[4], t[9], t[8], warp)
            if mat not in mats:
                mats.add(mat)
                bpy.data.materials.new("kcs mat")
                mat_dict[mat] = (len(bpy.data.materials), len(mat_dict))
                material = bpy.data.materials[-1]
                obj.data.materials.append(material)
                material.KCS_col.norm_type = t[4]
                material.KCS_col.col_type = t[9]
                material.KCS_col.col_param = t[8]
                material.KCS_col.warp_num = warp
            p.material_index = mat_dict[mat][1]


# The entire export, says level but could be a full misc block or just a collision block
class KCS_Level(BinWrite):
    def __init__(self):
        self.ptrManager = PointerManager()
        self.symbol_init()
        # child classes
        self.mesh_data = []
        self.node_data = []
        self.entities = []
        # raw data
        self.collision_header = None
        self.vertices = [(0x270F, 0x270F, 0x270F)]
        self.triangles = []
        self.normals = [(-1.0, -2.0, -3.0, -4.0)]
        self.tri_cells = []
        self.norm_cells = []
        self.norm_root = -1
        self.dyn_geo_groups = []
        self.dyn_geo_indices = []
        self.water_boxes = []
        self.water_normals = []
        # node data
        self.node_header = None
        self.node_traversals = []
        self.node_distances = []

    def process_meshes_and_nodes(self):
        self.create_node_relations()
        self.create_binary_space_partition()
        self.create_collision_header()

        if self.node_data:
            self.node_header = StructContainer(
                (
                    len(self.node_data),
                    self.pointer_truty(self.node_data[0].path_header),
                    self.pointer_truty(self.node_traversals),
                    self.pointer_truty(self.node_distances),
                )
            )
        self.level_header = StructContainer(
            (
                self.pointer_truty(self.collision_header, cast="struct CollisionHeader *"),
                self.pointer_truty(self.node_header, cast="struct NodeHeader *"),
                self.pointer_truty(self.entities, cast="struct Entity *"),
            )
        )

    def create_collision_header(self):
        if not self.vertices or not self.triangles or not self.normals:
            return
        self.collision_header = StructContainer(
            (
                self.pointer_truty(self.triangles),
                len(self.triangles),
                self.pointer_truty(self.vertices),
                len(self.vertices),
                self.pointer_truty(self.normals),
                len(self.normals),
                self.pointer_truty(self.tri_cells),
                len(self.tri_cells),
                self.pointer_truty(self.norm_cells),
                len(self.norm_cells),
                self.norm_root,
                self.pointer_truty(self.dyn_geo_groups),
                self.pointer_truty(self.dyn_geo_indices),
                self.pointer_truty(self.water_boxes),
                len(self.water_boxes),
                self.pointer_truty(self.water_normals),
                len(self.water_normals),
            )
        )

    # a BSP is used for collision triangles
    # BSP uses normal planes to rough in hits, then iterates over
    # a list of triangles with that normal to do mesh detection
    def create_binary_space_partition(self):
        # each cell will have a left and right child.
        # a left child means the children are in front this plane
        # a right child means they're behind the plane
        # intersections become both left and right children
        # each cell consists of a list of triangles, called a tri cell
        # the optimal root(?) is a triangle with the min right children

        # method is simple, starting at the root, find tris in the left/right pool
        # add those tris to the cell attributes pools
        # and make the tris of that norm into a cell
        # then for each pool, pick a norm of one tri in that pool
        # this becomes the left/right child of the last normal
        # repeat the steps, but with the tris in the cell removed from the pool
        def create_norm_pool(self, tri_pool, parent_cell=None):
            # deal with NULL case
            if not tri_pool:
                return 0
            # just pick a random normal
            norm = tri_pool[-1].normal
            kcs_cell = KCS_Cell(norm, parent=parent_cell)
            tri_pool = kcs_cell.create_tri_cell(tri_pool)
            for tri in tri_pool:
                in_front = tri.direction_towards_normal(self.vertices, norm)
                if in_front or in_front is None:
                    kcs_cell.left_children.append(tri)
                if not in_front:
                    kcs_cell.right_children.append(tri)
            if kcs_cell.left_children:
                child_cell = create_norm_pool(self, kcs_cell.left_children, kcs_cell)
                kcs_cell.left = child_cell
            if kcs_cell.right_children:
                child_cell = create_norm_pool(self, kcs_cell.right_children, kcs_cell)
                kcs_cell.right = child_cell
            return kcs_cell

        kcs_cell_root = create_norm_pool(self, self.triangles)

        # create list of cells
        def find_child(seq, cell):
            if cell.left:
                find_child(seq, cell.left)
            if cell.right:
                find_child(seq, cell.right)
            seq.append(cell)

        # create tri cells as list, add data to norm cells
        # insert pads so 0 index can be interpreted as NULL
        self.norm_cells.append(KCS_Cell(0, 1, 2, 3))
        find_child(self.norm_cells, kcs_cell_root)
        self.tri_cells.append(0x8192)
        self.triangles.insert(0, KCS_Triangle(destructable_index=5, particle_index=6))
        tri_indices = 1
        for cell in self.norm_cells[1:]:
            # mark the end of each tri cell with msb
            tri_cell = [self.triangles.index(tri) for tri in cell.triangle_cell]
            tri_cell[-1] = tri_cell[-1] | 0x8000
            self.tri_cells.extend(tri_cell)
            if cell.left:
                cell.left = self.norm_cells.index(cell.left)
            if cell.right:
                cell.right = self.norm_cells.index(cell.right)
            cell.tri_index = tri_indices
            tri_indices += len(cell.triangle_cell)
            cell.normal = self.normals.index(cell.normal)
        self.norm_root = self.norm_cells.index(kcs_cell_root)

    def create_node_relations(self):
        # sort nodes by node number
        self.node_data = sorted(self.node_data, key=lambda x: x.node_num)
        # node relations show the distance it takes to get from each node to another node
        # relation index can therefore be found by using the binomial coefficient of (n - 1, k)
        def walk_node(self, kcs_node: KCS_Node, target: int, distance: float):
            if (
                (kcs_node.node.lock_forward and kcs_node.node.next_node == target)
                or (kcs_node.node.lock_backward and kcs_node.node.prev_node == target)
                or (kcs_node.node.lock_backward and kcs_node.node.lock_forward)
            ):
                return (0, 9999.0)
            if kcs_node.node.prev_node == target:
                return (0x80, distance)
            if kcs_node.node.next_node == target:
                return (0, distance + kcs_node.node_length)
            if kcs_node.node.next_node != target and not kcs_node.node.lock_forward:
                return walk_node(self, self.node_data[kcs_node.node.next_node], target, distance + kcs_node.node_length)
            if kcs_node.node.prev_node != target and not kcs_node.node.lock_backward:
                return walk_node(self, self.node_data[kcs_node.node.prev_node], target, distance + kcs_node.node_length)

        def app_unique_list(seq, value):
            if value in seq:
                return seq.index(value)
            seq.append(value)
            return len(seq) - 1

        self.node_distances.append(9999.0)
        for node in self.node_data:
            for j, other in enumerate(self.node_data):
                if other is node:
                    self.node_traversals.append(0)
                # travel across nodes starting at "node" until "other" is found
                # if it is not connected, then use 0 as NULL connection
                direction, distance = walk_node(self, node, j, 0)
                self.node_traversals.append(direction + app_unique_list(self.node_distances, distance))

    # this should try to export in the same order as a default level.c file
    # though I will not explicitly add padding like the OG
    def to_c(self):
        # export data
        col_data = KCS_Cdata()
        col_data.write(level_block_includes)
        # level header
        if self.level_header:
            self.write_dict_struct(
                self.level_header,
                LevelHeader,
                col_data,
                "LevelHeader",
                "LvlHeader",
                static=True
            )
        # collision data
        self.write_arr(
            col_data,
            "s16",
            f"Vertices",
            self.vertices,
            self.format_arr,
            length=len(self.vertices),
            ampersand="",
            index="[0]",
            static=True
        )
        # triangles, each class has its own export func
        self.write_class_arr(
            col_data, self.triangles, "CollisionTriangle", "Triangles", length=len(self.triangles), ampersand="", static=True
        )
        self.write_arr(
            col_data,
            "struct Normal",
            "Normals",
            self.normals,
            self.format_arr,
            length=len(self.normals),
            outer_only=1,
            ampersand="",
            static=True
        )
        self.write_arr(
            col_data, "u16", "Tri_Cells", self.tri_cells, self.format_arr, length=len(self.tri_cells), ampersand="", static=True
        )
        self.write_class_arr(
            col_data, self.norm_cells, "NormalGroup", "Norm_Cells", length=len(self.norm_cells), ampersand="", static=True
        )
        # norml cells
        # dyn geo groups
        # dyn geo indices
        # water data
        # water normals
        if self.collision_header:
            self.write_dict_struct(
                self.collision_header,
                CollisionHeader,
                col_data,
                "CollisionHeader",
                "Col_Header",
                static=True
            )
        # node data, this is done to preserve ordering as the original files are done
        node_c_data = (
            path_data := KCS_Cdata(),
            kirb_data := KCS_Cdata(),
            connector_data := KCS_Cdata(),
            traversal_data := KCS_Cdata(),  # this isn't exported per node
            header_data := KCS_Cdata(),
        )
        for node in self.node_data:
            [aggr.append(dat) for aggr, dat in zip(node_c_data, node.to_c())]
        # add in traversal data
        self.write_arr(
            traversal_data,
            "u8",
            f"NodeTraversals",
            self.node_traversals,
            self.format_arr,
            length=len(self.node_traversals),
            static=True
        )
        self.write_arr(
            traversal_data,
            "f32",
            f"NodeDistances",
            self.node_distances,
            self.format_arr,
            length=len(self.node_distances),
            static=True
        )
        [col_data.append(dat) for dat in node_c_data]
        # node header
        if self.node_header:
            self.write_dict_struct(
                self.node_header,
                NodeHeader,
                col_data,
                "NodeHeader",
                "NodeHdr",
                static=True
            )

        # entities
        self.write_dict_struct_array(
            self.entities,
            EntityStruct,
            col_data,
            "Entity",
            f"Entities",
            ampersand="",
            static = True
        )
        # replace plcaeholder pointers in file with real symbols
        self.resolve_ptrs_c(col_data)
        return col_data


# One mesh from bpy point of view
class KCS_Mesh(BinWrite):
    def __init__(self, obj: bpy.types.Object):
        self.symbol_init()
        self.mesh = obj

    def calc_vertices(self, transform: Matrix, coords: Vector):
        # le tuple comprehension
        return (*(int(vert) for vert in transform @ coords),)

    def calc_mesh_data(self, transform: Matrix, vertex_offset: int, normals: list[float]):
        obj = self.mesh
        obj.data.calc_loop_triangles()
        triangles = []
        vertices = []
        for face in obj.data.loop_triangles:
            material = obj.material_slots[face.material_index].material

            v1 = (x1, y1, z1) = self.calc_vertices(transform, obj.data.vertices[face.vertices[0]].co)
            v2 = (x2, y2, z2) = self.calc_vertices(transform, obj.data.vertices[face.vertices[1]].co)
            v3 = (x3, y3, z3) = self.calc_vertices(transform, obj.data.vertices[face.vertices[2]].co)

            nx = (y2 - y1) * (z3 - z2) - (z2 - z1) * (y3 - y2) * 1.0
            ny = (z2 - z1) * (x3 - x2) - (x2 - x1) * (z3 - z2) * 1.0
            nz = (x2 - x1) * (y3 - y2) - (y2 - y1) * (x3 - x2) * 1.0
            # normalize
            magnitude = math.sqrt(nx * nx + ny * ny + nz * nz)
            if magnitude <= 0:
                print("Ignore denormalized triangle.")
                continue
            nx = nx / magnitude
            ny = ny / magnitude
            nz = nz / magnitude
            offset = -(x1 * nx + y1 * ny + z1 * nz)
            vert_index = len(vertices) + vertex_offset
            vertices.extend((v1, v2, v3))
            normal = (nx, ny, nz, offset)
            if normal not in normals:
                normals.append(normal)
            triangles.append(
                KCS_Triangle(
                    (vert_index, vert_index + 1, vert_index + 2),
                    *material.KCS_col.params,
                    normals.index(normal),
                    normal,
                )
            )
        return vertices, triangles


# One triangle
@dataclass
class KCS_Triangle(BinWrite):
    vertices: tuple[int] = (0, 1, 2)  # indices into vert array
    norm_type: int = 4
    col_type: int = 9
    col_param: int = 8
    stop_flag: int = 7
    normal_index: int = 3
    normal: tuple[float] = (1, 2, 3, 4)
    destructable_index: int = 0
    particle_index: int = 0

    def dot_product(self, vector_1, vector_2):
        return sum(a * b for a, b in zip(vector_1, vector_2))

    def direction_towards_normal(self, verts: list[int], normal: tuple[float]):
        vert_coords = [verts[v] for v in self.vertices]
        # solve the plane equation for the verts in tri
        in_front = [None, None, None]
        for i, vertex in enumerate(vert_coords):
            plane_eq = self.dot_product(vertex, normal[:-1]) + normal[-1]
            # if less than 1 unit away, count as in front
            if plane_eq > 0.5:
                in_front[i] = True
                continue
            if plane_eq < -0.5:
                in_front[i] = False
        if all(in_front):
            return True
        if in_front == [False, False, False]:
            return False
        return None  # intersection

    def to_c(self, file: KCS_Cdata):
        args = (
            self.normal_index,
            self.norm_type,
            self.destructable_index,
            self.particle_index,
            self.stop_flag,
            self.col_param,
            self.col_type,
        )
        args = f"{{{', '.join(hex(v) for v in self.vertices)}}}, {', '.join(str(a) for a in args)}"
        file.write(f"\t{{{args}}},\n")


# a cell for sorting BSP
@dataclass
class KCS_Cell:
    normal: tuple
    left: KCS_Cell = 0
    right: KCS_Cell = 0
    tri_index: int = 0
    parent: KCS_Cell = None
    left_children: list[tuple] = field(default_factory=list)
    right_children: list[tuple] = field(default_factory=list)
    triangle_cell: list[KCS_Triangle] = field(default_factory=list)

    def create_tri_cell(self, triangles: list[KCS_Triangle]):
        leftovers = []
        for tri in triangles:
            if tri.normal == self.normal:
                self.triangle_cell.append(tri)
            else:
                leftovers.append(tri)
        return leftovers

    def to_c(self, file: KCS_Cdata):
        args = (self.normal, self.left, self.right, self.tri_index)
        file.write(f"\t{{{', '.join([str(a) for a in args])}}},\n")


# One node from bpy point of view
class KCS_Node(BinWrite):
    def __init__(self, path_obj: bpy.types.Object, transform: Matrix, scale: float):
        self.symbol_init()
        self.node = path_obj.data.KCS_node
        self.node_num = self.node.node_num
        for child in path_obj.children:
            if child.type == "CAMERA":
                self.init_camera(child)
                break
        else:
            PluginError(f"no camera object detected in node {path_obj}")
        self.init_path(path_obj, transform, scale)

    def init_camera(self, camera_obj: bpy.types.Object):
        for child in camera_obj.children:
            if child.type == "EMPTY":
                camera_volume = child
        cam_node = camera_obj.data.KCS_cam
        # init props here
        self.camera_node = StructContainer(
            (
                cam_node.profile_view,
                0xA,
                *cam_node.axis_locks,
                0,
                not cam_node.pan_vertical,
                not cam_node.pan_below,
                not cam_node.pan_ahead,
                0,
                64,
                *cam_node.focus_location,
                *cam_node.clip_planes,
                (100.0, 100.0),  # radius scale in %
                cam_node.follow_yaw,
                cam_node.follow_radius,
                (30.0, 30.0),  # FOV
                cam_node.follow_pitch,
                cam_node.cam_bounds_x,
                cam_node.cam_bounds_y,
                cam_node.cam_bounds_z,
                cam_node.cam_bounds_yaw,
                cam_node.cam_bounds_pitch,
            )
        )
        # if there is a volume, use that for bounds
        # though for now, it is not incorporated

    def init_path(self, path_obj: bpy.types.Object, transform: Matrix, scale: float):
        path_dat = self.node
        self.kirby_node = StructContainer(
            (
                path_dat.node_num,
                path_dat.entrance_int,
                (*path_dat.stage_dest.stage, path_dat.warp_node),
                0,  # pad
                (0, 0, 0),  # node shading
                0,  # pad
                0x20 + path_dat.enable_warp,  # idk what 0x20 reps
                0,  # following are unused? or maybe hyper specific
                0,
                0.0,
                0.0,
                0.0,
            )
        )
        self.node_connector = (
            (
                2 * int(path_dat.lock_backward),
                0,
                path_dat.prev_node,
                2 * int(not path_dat.lock_forward),
            ),
            (
                2 * int(not path_dat.lock_forward),
                0,
                path_dat.next_node,
                0,
            ),
        )
        # if there are no splines in this obj, then raise error
        spline = path_obj.data.splines[0]
        # I need to set W to 1 so translation is applied during transform, but normal curves
        # use W for twist or something, so I need to override that, forcing this to be ugly
        self.path_matrix = []
        for point in spline.points:
            point = point.co
            point[3] = 1
            self.path_matrix.append(tuple((transform @ point).xyz))
        # path relative coords are basis invariant, no transform needed
        spline_length = spline.calc_length()
        first_point = spline.points[0].co
        self.path_bounds = (*((point.co - first_point).length / spline_length for point in spline.points),)
        self.node_length = spline_length * scale
        self.path_footer = StructContainer(
            (
                0,  # has path curl, not implemented
                len(self.path_matrix),
                0,  # force, not implemented
                self.pointer_truty(self.path_matrix),
                self.node_length / 10,
                self.pointer_truty(self.path_bounds),
                0,  # pointer to path curl, not implemented
            )
        )
        self.path_header = StructContainer(
            (
                self.pointer_truty(self.kirby_node),
                self.pointer_truty(self.path_footer),
                self.pointer_truty(self.node_connector),
                2,  # num connections, rework later
                0,  # self connected, rework later
            )
        )

    # write node data, in same order as original file, so multiple data objects
    # are used to preserve the ordering
    def to_c(self):
        # path data
        path_data = KCS_Cdata()
        self.write_arr(
            path_data,
            "f32",
            f"PathMatrix_{self.node_num}",
            self.path_matrix,
            self.format_arr,
            length=len(self.path_matrix),
            ampersand="",
            index="[0]",
            static=True
        )
        self.write_arr(
            path_data,
            "f32",
            f"PathBounds_{self.node_num}",
            self.path_bounds,
            self.format_arr,
            length=len(self.path_bounds),
            ampersand="",
            static=True
        )
        self.write_dict_struct(
            self.path_footer,
            Path_Footer,
            path_data,
            "PathNodeFooter",
            f"PathFooter_{self.node_num}",
            static=True
        )
        # kirb data
        kirb_data = KCS_Cdata()
        self.write_dict_struct(
            self.kirby_node,
            Kirby_Settings_Node,
            kirb_data,
            "KirbyNode",
            f"KirbyNode_{self.node_num}",
            static=True
        )
        self.write_dict_struct(
            self.camera_node,
            Camera_Node,
            kirb_data,
            "CameraNode",
            f"CamNode_{self.node_num}",
            static=True
        )
        # connectors
        connector_data = KCS_Cdata()
        self.write_arr(
            connector_data,
            "struct Node_Connectors",
            f"NodeConnector_{self.node_num}",
            self.node_connector,
            self.format_arr,
            length=len(self.node_connector),
            outer_only=1,
            ampersand="",
            static=True
        )
        # path headers
        header_data = KCS_Cdata()
        self.write_dict_struct(
            self.path_header,
            PathHeader,
            header_data,
            "PathNodeHeader",
            f"PathHeader_{self.node_num}",
            static=True
        )
        return (path_data, kirb_data, connector_data, KCS_Cdata(), header_data)


# ------------------------------------------------------------------------
#    Exorter Functions
# ------------------------------------------------------------------------


def export_col_c(name: str, obj: bpy.types.Object, context: bpy.types.Context):
    scale = context.scene.KCS_scene.scale
    # create writer class using blender data, class should
    # have all context needed for export from obj hierarchy
    bpy_col = BpyCollision(obj, None)
    kcs_level = bpy_col.init_kcs_col_from_bpy(scale)
    bpy_col.cleanup_collision(kcs_level)  # processing of bpy data is done
    # process and export cData from writer class
    kcs_level.process_meshes_and_nodes()
    cData = kcs_level.to_c()
    with open(f"{name}.c", "w") as file:
        file.write(cData.source)
    with open(f"{name}.h", "w") as file:
        file.write(cData.header)


# ------------------------------------------------------------------------
#    Importer
# ------------------------------------------------------------------------


def import_col_bin(bin_file: BinaryIO, context: bpy.types.Context, name: str):
    LS = bin_file
    LS = open(LS, "rb")
    collection = context.scene.collection
    rt = make_empty(name, "PLAIN_AXES", collection)
    rt.KCS_obj.KCS_obj_type = "Collision"
    LS_Block = MiscBinary(LS.read())
    write = BpyCollision(rt, collection)
    write.write_bpy_col(LS_Block, context.scene, context.scene.KCS_scene.scale)


def add_node(Rt: bpy.types.Object, collection: bpy.types.Collection):
    # Make Node
    PathData = bpy.data.curves.new("KCS Path Node", "CURVE")
    PathData.splines.new("POLY")
    PathData.splines[0].points.add(4)
    for i, s in enumerate(PathData.splines[0].points):
        s.co = (i - 2, 0, 0, 0)
    Node = bpy.data.objects.new("KCS Node", PathData)
    collection.objects.link(Node)
    parentObject(Rt, Node, 0)
    # make camera
    CamDat = bpy.data.cameras.new("KCS Node Cam")
    CamObj = bpy.data.objects.new("KCS Node Cam", CamDat)
    collection.objects.link(CamObj)
    parentObject(Node, CamObj, 0)
    # Make Camera Volume
    Vol = make_empty("KCS Cam Volume", "CUBE", collection)
    Vol.KCS_obj.KCS_obj_type = "Camera Volume"
    parentObject(CamObj, Vol, 0)
    Rt.select_set(True)

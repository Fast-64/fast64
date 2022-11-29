# ------------------------------------------------------------------------
#    Header
# ------------------------------------------------------------------------

import bpy

import os, struct, math

from pathlib import Path
from mathutils import Vector, Euler, Matrix
from collections import namedtuple
from dataclasses import dataclass

from .kcs_utils import *

# ------------------------------------------------------------------------
#    Classes
# ------------------------------------------------------------------------

# for selecting proper misc type of imp bin
class misc_bin(BinProcess):
    _vert_sig = (0x270F, 0x270F, 0x270F)

    def __new__(self, file):
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
        instance = super(misc_bin, subclass).__new__(subclass)
        return instance


# for i/o of node data
class node_cls:
    def __init__(self, num):
        self.index = num

    def cam_imp(self, cam, vol, scale):
        Null = lambda x, y: x * (x != y)
        kcs_cam = cam.data.KCS_cam
        cn = self.cam_node
        kcs_cam.AxisLocks = [cn.LockX != 0, cn.LockY != 0, cn.LockZ != 0]
        kcs_cam.ProfileView = cn.Profile
        kcs_cam.PanH, kcs_cam.PanUPDown, kcs_cam.PanDown = (cn.PanYaw, cn.PanHiLo, cn.PanLo)
        kcs_cam.Yaw = (cn.CamYaw1, cn.CamYaw2)
        kcs_cam.Radius = (cn.CamRadius1, cn.CamRadius2)
        kcs_cam.Pitch = (cn.CamPhi1, cn.CamPhi2)
        kcs_cam.Clips = (cn.NearClip, cn.FarClip)
        kcs_cam.Foc = (cn.FocusX, cn.FocusY, cn.FocusZ)
        kcs_cam.CamPitchBound = (cn.CamYawLock1, cn.CamYawLock2)
        kcs_cam.CamYawhBound = (cn.CamPitchLock1, cn.CamPitchLock2)
        x, y, z = (
            (Null(cn.CamXLock1, -9999) + Null(cn.CamXLock2, 9999)) / (2 * scale),
            (Null(cn.CamYLock1, -9999) + Null(cn.CamYLock2, 9999)) / (2 * scale),
            (Null(cn.CamZLock1, -9999) + Null(cn.CamZLock2, 9999)) / (2 * scale),
        )
        cam.location = Vector((x, y, z)) - cam.parent.location
        x, y, z = (
            (Null(cn.CamXLock2, 9999) - Null(cn.CamXLock1, -9999)) / (2 * scale),
            (Null(cn.CamYLock2, 9999) - Null(cn.CamYLock1, -9999)) / (2 * scale),
            (Null(cn.CamZLock2, 9999) - Null(cn.CamZLock1, -9999)) / (2 * scale),
        )
        vol.scale = (x, z, y)

    def path_imp(self, path, scale):
        kcs_node = path.data.KCS_node
        kcs_node.NodeNum = self.index + 1
        if self.num_connections == 1:
            kcs_node.NextNode = self.node_connections[2] + 1
            kcs_node.PrevNode = self.node_connections[2] + 1
            kcs_node.LockBackward = self.node_connections[0] != 0
            kcs_node.LockForward = self.node_connections[3] == 0
        elif self.num_connections == 2:
            kcs_node.NextNode = self.node_connections[2] + 1
            kcs_node.PrevNode = self.node_connections[6] + 1
            kcs_node.LockBackward = self.node_connections[0] != 0
            kcs_node.LockForward = self.node_connections[4] == 0
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
        kcs_node.EntranceLocation = Locations.get(self.kirb_node.EnterEnum >> 0xFF)
        kcs_node.EntranceAction = Actions.get(self.kirb_node.EnterEnum & 0xFF)
        kcs_node.Warp = warp[0:3]
        kcs_node.WarpDir = self.kirb_node.DestNode
        kcs_node.EnWarp = self.kirb_node.WarpFlag & 1

    def cam_out(self, cam, vol):
        pass

    def path_out(self, path):
        pass


# for i/o of level bin data
class level_bin(misc_bin):
    feature = "level"

    def __init__(self, file):
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

    def decode_node(self, num):
        node = node_cls(num)
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


# for object bins. unused for now
class object_bin(misc_bin):
    feature = "obj"


# wont be used, will raise error
class particle_bin(misc_bin):
    feature = "particle"


class bpy_collision:
    # given a class full of formatted data, writes
    # data to blender. also gets data from blender
    # for class
    def __init__(self, rt, collection):
        self.rt = rt  # this is an empty with kcs object type collision
        self.collection = collection

    def write_bpy_col(self, cls, scene, scale):
        # start by formatting tri/vert data
        collection = self.rt.users_collection[0]
        main = self.create_pydata(cls, cls.triangles, scale)
        dynamic = {}
        for geo, dyn in cls.de_tris.items():
            dynamic[geo] = self.create_pydata(cls, dyn, scale)
            # make objs but no parenting
            dyn_mesh = MakeMeshData("kcd_dyn_mesh", dynamic[geo][0:3])
            dyn_obj = MakeMeshObj("kcs dyn obj", dyn_mesh, collection)
            self.write_mats(dyn_obj, dynamic[geo][3])
            Parent(self.rt, dyn_obj, 0)
            RotateObj_n64_to_bpy(-90, dyn_obj)
            dyn_obj.KCS_mesh.MeshType = "Collision"
            dyn_obj.KCS_mesh.ColMeshType = "Breakable"
        # make objs and link
        main_mesh = MakeMeshData("kcs level mesh", main[0:3])
        main_obj = MakeMeshObj("kcs level obj col", main_mesh, collection)
        Parent(self.rt, main_obj, 0)  # get col rt from rt
        ApplyRotation_n64_to_bpy(main_obj)
        main_obj.KCS_mesh.MeshType = "Collision"
        self.write_mats(main_obj, main[3])
        # format node data
        for num, node in cls.path_nodes.items():
            AddNode(self.rt, collection)  # use my own operator so default settings are made
            path = self.rt.children[-1]
            # paths cannot have rotations applied
            RotateObj_n64_to_bpy(-90, path)
            cam = path.children[0]
            vol = cam.children[0]
            node.path_imp(path, scale)
            node.cam_imp(cam, vol, scale)
            node.bpy_path = path
        # update view layer so that paths have accurate positions
        bpy.context.view_layer.update()
        # write entities
        for e in cls.entities:
            o = MakeEmpty("KCS entity", "ARROWS", collection)
            o.KCS_obj.KCS_obj_type = "Entity"
            ent = o.KCS_ent
            path = cls.path_nodes[e.node].bpy_path
            Parent(path, o, 1)  # parent to node, but remove transform
            rot = (e.rot[0], e.rot[1], e.rot[2])  # only rotate root since tree will inherit transform
            o.rotation_euler = rot
            loc = Vector(e.pos) / scale
            # I add because I already have the parent inverse transform applied to the location
            # because these are empties I cannot apply the transform because it has no data to apply to
            o.location += Vector([loc[0], loc[1], loc[2]])
            o.scale = e.scale

            ent.BankNum = e.bank
            ent.IndexNum = e.id
            ent.Action = e.action
            ent.Respawn = e.res_flag
            ent.Eep = e.eep
            ent.Flags = e.spawn_flag

    def scale_verts(self, verts, scale):
        scaled = []
        for v in verts:
            scaled.append([a / scale for a in v])
        return scaled

    # make (verts,[],tris,mat_dat) properly formated given tri list
    def create_pydata(self, cls, tris, scale):
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

    def write_mats(self, obj, dat):
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
                material.KCS_col.NormType = t[4]
                material.KCS_col.ColType = t[9]
                material.KCS_col.ColParam = t[8]
                material.KCS_col.WarpNum = warp
            p.material_index = mat_dict[mat][1]


# ------------------------------------------------------------------------
#    Exorter Functions
# ------------------------------------------------------------------------


# ------------------------------------------------------------------------
#    Importer
# ------------------------------------------------------------------------


def ImportColBin(bin_file, context, name):
    LS = bin_file
    LS = open(LS, "rb")
    collection = context.scene.collection
    rt = MakeEmpty(name, "PLAIN_AXES", collection)
    rt.KCS_obj.KCS_obj_type = "Collision"
    LS_Block = misc_bin(LS.read())
    write = bpy_collision(rt, collection)
    write.write_bpy_col(LS_Block, context.scene, context.scene.KCS_scene.Scale)


def AddNode(Rt, collection):
    # Make Node
    PathData = bpy.data.curves.new("KCS Path Node", "CURVE")
    PathData.splines.new("POLY")
    PathData.splines[0].points.add(4)
    for i, s in enumerate(PathData.splines[0].points):
        s.co = (i - 2, 0, 0, 0)
    Node = bpy.data.objects.new("KCS Node", PathData)
    collection.objects.link(Node)
    Parent(Rt, Node, 0)
    # make camera
    CamDat = bpy.data.cameras.new("KCS Node Cam")
    CamObj = bpy.data.objects.new("KCS Node Cam", CamDat)
    collection.objects.link(CamObj)
    Parent(Node, CamObj, 0)
    # Make Camera Volume
    Vol = MakeEmpty("KCS Cam Volume", "CUBE", collection)
    Vol.KCS_obj.KCS_obj_type = "Camera Volume"
    Parent(CamObj, Vol, 0)
    Rt.select_set(True)

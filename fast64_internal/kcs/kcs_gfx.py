# ------------------------------------------------------------------------
#    Header
# ------------------------------------------------------------------------

import bpy

import os, struct, math

from functools import lru_cache
from pathlib import Path
from mathutils import Vector, Euler, Matrix
from collections import namedtuple
from dataclasses import dataclass
from copy import deepcopy
from re import findall

from . import F3DEX2_gbi as f3dex2
from .kcs_utils import *
#fast64 imports

from ..utility import (colorToLuminance,
                    propertyGroupGetEnums,
                    combineObjects,
                    cleanupCombineObj,
                    CData,
                    writeCData,
                    writeCDataSourceOnly,
                    writeCDataHeaderOnly)
from ..f3d.f3d_writer import *
from ..f3d.f3d_gbi import *


# ------------------------------------------------------------------------
#    Classes
# ------------------------------------------------------------------------

#geo data

#these aren't actually all ints
@dataclass
class layout(BinProcess):
    flag: int
    depth: int
    ptr: int
    translation: int
    rotation: int
    scale: int
    index: int = 0

#fake storage class that mirrors methods of layout
@dataclass
class faux_LY():
    ptr: int
    index: int = 0

class Vertices():
    _Vec3 = namedtuple("Vec3", "x y z")
    _UV = namedtuple("UV", "s t")
    _color = namedtuple("rgba", "r g b a")
    def __init__(self, scale):
        self.UVs = []
        self.VCs = []
        self.Pos = []
        self.scale = scale
    def _make(self, v):
        self.Pos.append(self.ScaleVerts(self._Vec3._make(v[0:3])))
        self.UVs.append(self._UV._make(v[4:6]))
        self.VCs.append(self._color._make(v[6:10])) #holds norms and vcs when importing
    def ScaleVerts(self, pos):
        v = [a / self.scale for a in pos]
        return v

#use for extraction,
TextureScrollStruct = {
    0x00: [">H",'field_0x0', 2],
    0x02: [">B",'fmt1', 1],
    0x03: [">B",'siz1', 1],
    0x04: [">L",'textures', 4],
    0x08: [">H",'stretch', 2],
    0x0A: [">H",'sharedOffset', 2],
    0x0C: [">H",'t0_w', 2],
    0x0E: [">H",'t0_h', 2],
    0x10: [">L",'halve', 4],
    0x14: [">f",'t0_xShift', 4],
    0x18: [">f",'t0_yShift', 4],
    0x1C: [">f",'xScale', 4],
    0x20: [">f",'yScale', 4],
    0x24: [">f",'field_0x24', 4],
    0x28: [">f",'field_0x28', 4],
    0x2C: [">L",'palettes', 4],
    0x30: [">H",'flags', 2],
    0x32: [">B",'fmt2', 1],
    0x33: [">B",'siz2', 1],
    0x34: [">H",'w2', 2],
    0x36: [">H",'h2', 2],
    0x38: [">H",'t1_w', 2],
    0x3A: [">H",'t1_h', 2],
    0x3C: [">f",'t1_xShift', 4],
    0x40: [">f",'t1_yShift', 4],
    0x44: [">f",'field_0x44', 4],
    0x48: [">f",'field_0x48', 4],
    0x4C: [">L",'field_0x4c', 4],
    0x50: [">4B",'prim_col', 4, 'arr'],
    0x54: [">B",'primLODFrac', 1],
    0x55: [">B",'field_0x55', 1],
    0x56: [">B",'field_0x56', 1],
    0x57: [">B",'field_0x57', 1],
    0x58: [">4B",'env_col', 4, 'arr'],
    0x5C: [">4B",'blend_col', 4, 'arr'],
    0x60: [">4B",'light1_col', 4, 'arr'],
    0x64: [">4B",'light2_col', 4, 'arr'],
    0x68: [">L",'field_0x68', 4],
    0x6C: [">L",'field_0x6c', 4],
    0x70: [">L",'field_0x70', 4],
    0x74: [">L",'field_0x74', 4]
}

#this is the class that holds the actual individual scroll struct and textures
class tx_scroll():
    _scroll = namedtuple("texture_scroll", ' '.join([x[1] for x in TextureScrollStruct.values()]))
    def __init__(self, *args):
        self.scroll = self._scroll._make(*args)

#each texture scroll will start from an array of ptrs, and each ptr will reference
#tex scroll data
class Tex_Scroll(BinProcess):
    def extract_dict(self, start, dict):
        a = []
        for k, v in dict.items():
            try:
                if v[3]:
                    a.append( self.upt(start + k, v[0], v[2]) )
            except:
                a.append( self.upt(start + k, v[0], v[2])[0] )
        return a
    def __init__(self, scroll_ptrs, file, ptr):
        self.scroll_ptrs = scroll_ptrs
        self.scrolls = {}
        self.file = file
        self.ptr = ptr
        for p in scroll_ptrs:
            if p != 0x99999999 and p:
                #get struct
                scr = tx_scroll(self.extract_dict(self.seg2phys(p), TextureScrollStruct))
                self.scrolls[p] = scr
                #search for palletes
                if scr.scroll.palettes:
                    start = self.seg2phys(scr.scroll.palettes)
                    self.pal_start = scr.scroll.textures
                    scr.palettes = self.get_BI_pairs(start, stop = (0x9999, 0x9999))
                #search for textures
                if scr.scroll.textures:
                    start = self.seg2phys(scr.scroll.textures)
                    self.tx_start = scr.scroll.textures
                    scr.textures = self.get_BI_pairs(start, stop = (0x9999, 0x9999))
    def Write(self, file):
        #sort structs in case they aren't in order
        self.scrolls = self.SortDict(self.scrolls)
        for p, s in self.scrolls.items():
            #textures
            if hasattr(s, "textures"):
                self.write_arr(file, f"tx_scroll_textures_{self.tx_start:X}", s.textures, BI = 1)
            #palletes
            if hasattr(s, "palettes"):
                self.write_arr(file, f"tx_scroll_palettes_{self.pal_start:X}", s.palettes, BI = 1)
            #struct
            WriteDictStruct(s.scroll, TextureScrollW, file, "", f"tx_scroll scroll_{p:X}")
    def WriteHeader(self, file):
        #write header, separate func because these are at the end of the file
        self.write_arr(file, f"tx_scroll_hdr_{self.ptr:X}", self.scroll_ptrs, ptr_format = "&scroll_")

#takes binary input and makes geo block data
class geo_bin(BinProcess):
    _Vec3 = namedtuple("Vec3", "x y z")
    _texture = namedtuple("texture", "fmt siz bank_index")
    def __init__(self, file, scale):
        self.file = file
        self.main_header = self.upt(0,">8L",32)
        self.scale = scale
        self.get_tex_scrolls()
        self.DLs = dict()#this is also in layouts, but I want it raw here to print in RAM order, and in layouts to analyze in the processed order
        self.render_mode = self.main_header[2]
        self._render_mode_map[self.render_mode](self)
        #get vtx and img refs null terminated arrays
        self.get_refs()
        self.get_anims()
    def get_tex_scrolls(self):
        if self.main_header[1]:
            start = self.main_header[1]
            #get header of POINTERS
            self.tex_header = self.get_referece_list(start, stop = 0x99999999)
            self.tex_scrolls = {}
            for p in self.tex_header:
                if p and p != 0x99999999:
                    self.tex_scrolls[p] = Tex_Scroll(self.get_referece_list(p, stop = 0x99999999), self.file, p)
            #sort scrolls
            self.tex_scrolls = self.SortDict(self.tex_scrolls)
    #anims are bank indices
    def get_anims(self):
        num = self.main_header[5]
        start = self.seg2phys(self.main_header[6])
        self.anims = self.get_BI_pairs(start, num = num)
    #both types of refs are null terminated lists
    def get_refs(self):
        self.img_refs = self.get_referece_list(self.main_header[3])
        self.vtx_refs = self.get_referece_list(self.main_header[4])
    #no layout, just a single DL
    def decode_layout_13(self):
        L = faux_LY(self.seg2phys(self.main_header[0]))
        L.dl_ptrs = [L.ptr]
        self.layouts = [L]
        self.decode_f3d_bin(L)
        Vert_End = L.ptr[0]
        self.decode_vertices(32, Vert_End)
    #no layouts, just an entry point
    def decode_layout_14(self):
        L = faux_LY(self.seg2phys(self.main_header[0]))
        self.decode_entry(L)
        self.layouts = [L]
        self.decode_f3d_bin(L)
        Vert_End = L.ptr[0]
        self.decode_vertices(32,Vert_End)
    #layouts point to DL
    def decode_layout_17(self):
        self.layouts = [self.decode_layout(self.main_header[0]+0x2C*i, index = i) for i in range(self.main_header[-1])]
        starts = []
        for l in self.layouts:
            if l.ptr:
                l.dl_ptrs = [l.ptr]
                starts.extend( self.decode_f3d_bin(l) )
        if starts:
            Vert_End = min(starts)
            self.decode_vertices(32, Vert_End)
    #layouts point to entry point
    def decode_layout_18(self):
        self.layouts = [self.decode_layout(self.main_header[0]+0x2C*i, index = i) for i in range(self.main_header[-1])]
        starts = []
        for l in self.layouts:
            if l.ptr:
                self.decode_entry(l)
                starts.extend( self.decode_f3d_bin(l) )
        if starts:
            Vert_End = min(starts)
            self.decode_vertices(32, Vert_End)
    #layout points to pair of DLs
    def decode_layout_1B(self):
        self.layouts = [self.decode_layout(self.main_header[0]+0x2C*i, index = i) for i in range(self.main_header[-1])]
        starts = []
        for l in self.layouts:
            if l.ptr:
                self.decode_DL_pair(l)
                starts.extend( self.decode_f3d_bin(l) )
        if starts:
            Vert_End = min(starts)
            self.decode_vertices(32, Vert_End)
    #layout points to entry point with pair of DL
    def decode_layout_1C(self):
        self.layouts = [self.decode_layout(self.main_header[0]+0x2C*i, index = i) for i in range(self.main_header[-1])]
        starts = []
        for l in self.layouts:
            if l.ptr:
                self.decode_entry_dbl(l)
                starts.extend( self.decode_f3d_bin(l) )
        if starts:
            Vert_End = min(starts)
            self.decode_vertices(32, Vert_End)
    def decode_layout(self, start, index = None):
        start = self.seg2phys(start)
        LY = self.upt(start,">2HL9f",0x2C)
        v = self._Vec3._make
        return layout(*LY[0:3],v(LY[3:6]),v(LY[6:9]),v(LY[9:12]), index = index)
    #has to be after func declarations
    _render_mode_map = {
        0x13: decode_layout_13,
        0x14: decode_layout_14,
        0x17: decode_layout_17,
        0x18: decode_layout_18,
        0x1B: decode_layout_1B,
        0x1C: decode_layout_1C
    }
    def decode_DL_pair(self, ly: layout):
        ly.dl_ptrs = [] #just a literal list of ptrs
        ptrs = self.upt(self.seg2phys(ly.ptr), ">2L", 8)
        for ptr in ptrs:
            if ptr:
                ly.dl_ptrs.append(ptr)
        ly.DL_Pair = ptrs
    def decode_entry_dbl(self, ly: layout):
        x = 0
        start = self.seg2phys(ly.ptr)
        ly.entry_dbls = []
        ly.dl_ptrs = [] #just a literal list of ptrs
        while(True):
            mark, *ptrs = self.upt(start+x, ">3L", 12)
            ly.entry_dbls.append( (mark, ptrs) )
            if mark == 4:
                return
            else:
                for ptr in ptrs:
                    if ptr:
                        ly.dl_ptrs.append(ptr)
            x += 12
            #shouldn't execute
            if x > 120:
                print("your while loop is broken in geo_bin.decode_entry")
                break
    def decode_entry(self, ly: layout):
        x = 0
        start = self.seg2phys(ly.ptr)
        ly.entry_pts = [] #the actual entry pt raw data
        ly.dl_ptrs = [] #just a literal list of ptrs
        while(True):
            mark, ptr = self.upt(start+x, ">2L", 8)
            ly.entry_pts.append( (mark, ptr) )
            if mark == 4:
                return
            if ptr == 0:
                continue
            else:
                ly.dl_ptrs.append(ptr)
            x += 8
            #shouldn't execute
            if x > 80:
                print("your while loop is broken in geo_bin.decode_entry")
                break
    #gonna use a module for this
    def decode_f3d_bin(self, layout):
        DLs = {}
        self.vertices = []
        starts = []
        layout.entry = layout.dl_ptrs[:] #create shallow copy, use this for analyzing DL, while DL ptrs will be a dict including jumped to DLs
        for dl in layout.dl_ptrs:
            start = self.seg2phys(dl)
            starts.append(start)
            f3d = self.decode_dl_bin(start, layout)
            self.DLs[dl] = f3d
            DLs[dl] = f3d
        layout.DLs = DLs
        return starts
    def DL_ptr(self,num):
        if num >> 24 == 0xE:
            return None
        else:
            return num
    def decode_dl_bin(self, start, layout):
        DL = []
        x = 0
        while(True):
            cmd = self.Getf3dCmd(self.file[start + x : start + x + 8])
            x += 8
            if not cmd:
                continue
            name, args = self.split_args(cmd)
            if name == 'gsSPEndDisplayList':
                break
            elif name == 'gsSPDisplayList':
                ptr = self.DL_ptr(int(args[0]))
                if ptr:
                    layout.dl_ptrs.append(ptr)
                DL.append((name, args))
                continue
            #this LoD info will probably just stay destroyed for now
            elif name == 'gsSPBranchLessZ':
                ptr = self.DL_ptr(int(args[0]))
                if ptr:
                    layout.dl_ptrs.append(ptr)
                DL.append((name,  args))
                continue
            elif name == 'gsSPBranchList':
                ptr = self.DL_ptr(int(args[0]))
                if ptr:
                    layout.dl_ptrs.append(ptr)
                DL.append((name, args))
                break
            DL.append((name, args))
        DL.append((name, args))
        return DL
    @lru_cache(maxsize = 32) #will save lots of time with repeats of tri calls
    def Getf3dCmd(self, bin):
        return f3dex2.Ex2String(bin)
    def split_args(self, cmd):
        filt = "\(.*\)"
        a = re.search(filt, cmd)
        return cmd[:a.span()[0]], cmd[a.span()[0]+1 : a.span()[1]-1].split(',')
    def decode_vertices(self, start, end):
        self.vertices = Vertices(self.scale)
        for i in range(start,end,16):
            v = self.upt(i,">6h4B",16)
            self.vertices._make(v)


#interim between bpy props and geo blocks
class bpy_geo():
    def __init__(self, rt, scale):
        self.rt = rt
        self.scale = scale
    #write gfx from geo bin cls to blender
    def write_gfx(self, name, cls, tex_path, collection):
        #for now, do basic import, each layout is an object
        stack = [self.rt]
        self.LastMat = None
        #create dict of models so I can reuse model dat as needed (usually for blocks)
        Models = dict()
        for i, layout in enumerate(cls.layouts):
            if(layout.depth&0xFF) == 0x12:
                break
            #mesh object
            if layout.ptr:
                prev = Models.get(layout.ptr)
                #model was already imported, reuse data block with new obj
                if prev:
                    mesh, self.LastMat = prev
                else:
                    ModelDat = F3d(lastmat = self.LastMat)
                    (layout.vertices, layout.Triangles) = ModelDat.GetDataFromDL(cls, layout)
                    self.LastMat = ModelDat.LastMat
                    mesh = bpy.data.meshes.new(f"{name} {layout.depth&0xFF} {i}")
                    mesh.from_pydata(layout.vertices,[],layout.Triangles)
                    #add model to dict
                    Models[layout.ptr] = (mesh, self.LastMat)
                obj = bpy.data.objects.new(f"{name} {layout.depth&0xFF} {i}",mesh)
                collection.objects.link(obj)
                #set KCS props of obj
                obj.KCS_mesh.MeshType = "Graphics"
                #apply dat
                ModelDat.ApplyDat(obj, mesh, tex_path)
                #cleanup
                mesh.validate()
                mesh.update(calc_edges = True)
                if bpy.context.scene.KCS_scene.CleanUp:
                    #shade smooth
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.object.shade_smooth()
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.remove_doubles()
                    bpy.ops.object.mode_set(mode='OBJECT')
            #empty transform
            else:
                obj = MakeEmpty(f"{name} {layout.depth} {i}",'PLAIN_AXES', collection)
                #set KCS props of obj
                obj.KCS_mesh.MeshType = "Graphics"
            #now that obj is created, parent and add transforms to it
            if (layout.depth & 0xFF) < len(stack)-1:
                stack = stack[:(layout.depth&0xFF)+1]
            Parent(stack[-1], obj, 0)
            if (layout.depth & 0xFF) + 1 > len(stack) - 1:
                stack.append(obj)
            loc = layout.translation
            obj.location += Vector(loc) / self.scale
            obj.scale = Vector([1 / a for a in layout.scale])
            ApplyRotation_n64_to_bpy(obj)
    @staticmethod
    def Vec3Trans(vec3):
        return (vec3.x, -vec3.z, vec3.y)
    #create the geo out cls and populate it with layouts based on child objects
    def init_geo(self):
        cls = geo_write()
        depth = 0
        cls.layouts = []
        obj = self.rt
        #get all child layouts first
        def loop_children(obj, cls, depth):
            for child in obj.children:
                if self.is_kcs_gfx(child):
                    #clean up the mesh data, apply transforms and then give the copy to layout.ptr
                    cls.layouts.append( self.create_layout(child, depth, cls.f3d) )
                    if child.children:
                        loop_children(child, cls, depth + 1)
        loop_children(obj, cls, 1)
        #add the root as a layout, though if there are no children, set the render mode to 14
        if not cls.layouts:
            cls.render_mode = 0x14 #list of DLs (entry point)
            cls.layouts.append( faux_LY(F3d_Mesh(obj, obj.data, self.scale, cls.f3d)) )
        else:
            cls.render_mode = 0x17 #list of layouts
            cls.layouts.insert(0, self.create_layout(obj, 0, cls.f3d) )
        return cls
    #create a layout for an obj given its depth and the obj props
    def create_layout(self, obj, depth, f3d):
        #transform layout values to match N64 specs
        #only location needs to be transformed here, because rotation in the mesh data
        #will change the scale and rot
        loc = self.Vec3Trans(obj.location)
        rot = obj.rotation_euler
        scale = obj.scale
        ly = layout(0, depth, F3d_Mesh(obj, obj.data, self.scale, f3d), loc, rot, scale)
        ly.name = obj.name #for debug
        return ly
    #given an obj, eval if it is a kcs gfx export
    def is_kcs_gfx(self, obj):
        if obj.type == "MESH":
            return obj.KCS_mesh.MeshType == "Graphics"
        if obj.type == "EMPTY":
            return obj.KCS_obj.KCS_obj_type == "Graphics"


#this will hold tile properties
class Tile():
    def __init__(self):
        self.Fmt = 'RGBA'
        self.Siz = '16'
        self.Slow = 32
        self.Tlow = 32
        self.Shigh = 32
        self.Thigh = 32
        self.SMask = 5
        self.TMask = 5
        self.SShift = 0
        self.TShift = 0
        self.Sflags = None
        self.Tflags = None
    def Bounds(self):
        return (self.Slow << 2, self.Tlow << 2, self.Shigh << 2, self.Thigh << 2)
    def LoadTile(self, tmem = 0, num = 0, pal_num = 0):
        return (self.Fmt, self.Siz, "n rows", tmem, "G_TX_LOADTILE", 0, \
        self.Tflags, self.TMask, self.TShift, \
        self.Sflags, self.SMask, self.SShift)
    def RenderTile(self, tmem = 0, num = 0, pal_num = 0):
        return (self.Fmt, self.Siz, "n rows", tmem, num, pal_num, \
        self.Tflags, self.TMask, self.TShift, \
        self.Sflags, self.SMask, self.SShift)

#this will hold texture properties, dataclass props
#are created in order for me to make comparisons in a set
@dataclass(init = True, eq = True, unsafe_hash = True)
class Texture():
    Timg: tuple
    Fmt: str
    Siz: int
    Width: int = 0
    Height: int = 0
    Pal: tuple = None
    def SetImg(self):
        return (self.Fmt, self.Siz, 1, self.Timg)
    def LoadImg(self):
        return ("G_TX_LOADTILE", 0, 0, "math", "dxt")
    def size(self):
        return self.Width, self.Height

#This is a data storage class and mat to f3dmat converting class
#used when importing for kirby
class Mat():
    def __init__(self):
        self.TwoCycle = False
        self.GeoSet = []
        self.GeoClear = []
        self.tiles = [Tile() for a in range(8)]
        self.tex0 = None
        self.tex1 = None
        self.tx_scr = None
    #calc the hash for an f3d mat and see if its equal to this mats hash
    def MatHashF3d(self, f3d):
        #texture,1 cycle combiner, render mode, geo modes, some other blender settings, tile size (very important in kirby64)
        rdp = f3d.rdp_settings
        if f3d.tex0.tex:
            T = f3d.tex0.tex_reference
        else:
            T = ''
        F3Dprops = (T, f3d.combiner1.A, f3d.combiner1.B, f3d.combiner1.C, f3d.combiner1.D,
        f3d.combiner1.A_alpha, f3d.combiner1.B_alpha, f3d.combiner1.C_alpha, f3d.combiner1.D_alpha,
        f3d.rdp_settings.rendermode_preset_cycle_1, f3d.rdp_settings.rendermode_preset_cycle_2,
        f3d.rdp_settings.g_lighting, f3d.rdp_settings.g_shade, f3d.rdp_settings.g_shade_smooth, f3d.rdp_settings.g_zbuffer,
        f3d.rdp_settings.g_mdsft_alpha_compare, f3d.rdp_settings.g_mdsft_zsrcsel, f3d.rdp_settings.g_mdsft_alpha_dither,
        f3d.tex0.S.high, f3d.tex0.T.high, f3d.tex0.S.low, f3d.tex0.T.low )
        if hasattr(self,'Combiner'):
            MyT = ''
            if hasattr(self.tex0,'Timg'):
                MyT = str(self.tex0.Timg)
            else:
                pass
            def EvalGeo(self, mode):
                for a in self.GeoSet:
                    if mode in a.lower():
                        return True
                for a in self.GeoClear:
                    if mode in a.lower():
                        return False
                else:
                    return True
            
            chkT = lambda x, y, d: x.__dict__.get(y, d)
            rendermode = getattr(self,"RenderMode", ['G_RM_AA_ZB_OPA_SURF','G_RM_AA_ZB_OPA_SURF2'])
            MyProps = (MyT, *self.Combiner[0:8], *rendermode,
            EvalGeo(self,'g_lighting'), EvalGeo(self, 'g_shade'),
            EvalGeo(self,'g_shade_smooth'), EvalGeo(self,'g_zbuffer'),
            chkT(self, 'g_mdsft_alpha_compare', 'G_AC_NONE'),
            chkT(self, 'g_mdsft_zsrcsel', 'G_ZS_PIXEL'),
            chkT(self, 'g_mdsft_alpha_dither', 'G_AD_NOISE'),
            self.tiles[0].Shigh,  self.tiles[0].Thigh,  self.tiles[0].Slow,  self.tiles[0].Tlow  )
            dupe = hash(MyProps) == hash(F3Dprops)
            return dupe
        return False
    def MatHash(self, mat):
        return False
    def ConvertColor(self, color):
        return [int(a) / 255 for a in color]
    def LoadTexture(self, ForceNewTex, path, tex):
        png = path / f"bank_{tex.Timg[0]}" / f"{tex.Timg[1]}"
        png =  *png.glob('*.png'),
        if png:
            i = bpy.data.images.get(str(png[0]))
            if not i or ForceNewTex:
                return bpy.data.images.load(filepath=str(png[0]))
            else:
                return i
    def ApplyPBSDFMat(self, mat):
        nt = mat.node_tree
        nodes = nt.nodes
        links = nt.links
        pbsdf = nodes.get('Principled BSDF')
        tex = nodes.new("ShaderNodeTexImage")
        links.new(pbsdf.inputs[0],tex.outputs[0])
        links.new(pbsdf.inputs[19],tex.outputs[1])
        i = self.LoadTexture(0, path)
        if i:
            tex.image = i
    def ApplyMatSettings(self, mat, tex_path):
#        if bpy.context.scene.LevelImp.AsObj:
#            return self.ApplyPBSDFMat(mat, textures, path, layer)
        
        f3d = mat.f3d_mat #This is kure's custom property class for materials
        
        #set color registers if they exist
        if hasattr(self, 'fog_position'):
            f3d.set_fog = True
            f3d.use_global_fog = False
            f3d.fog_position[0] = eval(self.fog_pos[0])
            f3d.fog_position[1] = eval(self.fog_pos[1])
        if hasattr(self, 'fog_color'):
            f3d.set_fog = True
            f3d.use_global_fog = False
            f3d.fog_color = self.ConvertColor(self.fog_color)
        if hasattr(self, 'light_col'):
            #this is a dict but I'll only use the first color for now
            f3d.set_lights = True
            if self.light_col.get(1):
                f3d.default_light_color = self.ConvertColor(eval(self.light_col[1]).to_bytes(4, 'big'))
        if hasattr(self, 'env_color'):
            f3d.set_env = True
            f3d.env_color = self.ConvertColor(self.env_color[-4:])
        if hasattr(self, 'prim_color'):
            prim = self.prim_color
            f3d.set_prim = True
            f3d.prim_lod_min = int(prim[0])
            f3d.prim_lod_frac = int(prim[1])
            f3d.prim_color = self.ConvertColor(prim[-4:])
        #I set these but they aren't properly stored because they're reset by fast64 or something
        #its better to have defaults than random 2 cycles
        self.SetGeoMode(f3d.rdp_settings, mat)
        
        if self.TwoCycle:
            f3d.rdp_settings.g_mdsft_cycletype = 'G_CYC_2CYCLE'
        else:
            f3d.rdp_settings.g_mdsft_cycletype = 'G_CYC_1CYCLE'
        
        #make combiner custom
        f3d.presetName = "Custom"
        self.SetCombiner(f3d)
        #add tex scroll objects
        if self.tx_scr:
            scr = self.tx_scr
            mat_scr = mat.KCS_tx_scroll
            if hasattr(scr, "textures"):
                [mat_scr.AddTex(t) for t in scr.textures]
            if hasattr(scr, "palettes"):
                [mat_scr.AddPal(t) for t in scr.palettes]
        #deal with custom render modes
        if hasattr(self, "RenderMode"):
            self.SetRenderMode(f3d)
        #g texture handle
        if hasattr(self, "set_tex"):
            #not exactly the same but gets the point across maybe?
            f3d.tex0.tex_set = self.set_tex
            f3d.tex1.tex_set = self.set_tex
            #tex scale gets set to 0 when textures are disabled which is automatically done
            #often to save processing power between mats or something, or just adhoc bhv
            if f3d.rdp_settings.g_tex_gen or any([a < 1 and a > 0 for a in self.tex_scale]):
                f3d.scale_autoprop = False
                f3d.tex_scale = self.tex_scale
                print(self.tex_scale)
            if not self.set_tex:
                #Update node values
                override = bpy.context.copy()
                override["material"] = mat
                bpy.ops.material.update_f3d_nodes(override)
                del override
                return
        #texture 0 then texture 1
        if self.tex0:
            i = self.LoadTexture(0, tex_path, self.tex0)
            tex0 = f3d.tex0
            tex0.tex_reference = str(self.tex0.Timg) #setting prop for hash purposes
            tex0.tex_set = True
            tex0.tex = i
            tex0.tex_format = self.EvalFmt(self.tiles[0])
            tex0.autoprop = False
            Sflags = self.EvalFlags(self.tiles[0].Sflags)
            for f in Sflags:
                setattr(tex0.S,f,True)
            Tflags = self.EvalFlags(self.tiles[0].Tflags)
            for f in Sflags:
                setattr(tex0.T,f,True)
            tex0.S.low = self.tiles[0].Slow
            tex0.T.low = self.tiles[0].Tlow
            tex0.S.high = self.tiles[0].Shigh
            tex0.T.high = self.tiles[0].Thigh
            
            tex0.S.mask = self.tiles[0].SMask
            tex0.T.mask = self.tiles[0].TMask
        if self.tex1:
            i = self.LoadTexture(0, tex_path, self.tex1)
            tex1 = f3d.tex1
            tex1.tex_reference = str(self.tex1.Timg) #setting prop for hash purposes
            tex1.tex_set = True
            tex1.tex = i
            tex1.tex_format = self.EvalFmt(self.tiles[1])
            Sflags = self.EvalFlags(self.tiles[1].Sflags)
            for f in Sflags:
                setattr(tex1.S,f,True)
            Tflags = self.EvalFlags(self.tiles[1].Tflags)
            for f in Sflags:
                setattr(tex1.T,f,True)
            tex1.S.low = self.tiles[1].Slow
            tex1.T.low = self.tiles[1].Tlow
            tex1.S.high = self.tiles[1].Shigh
            tex1.T.high = self.tiles[1].Thigh
            
            tex1.S.mask = self.tiles[0].SMask
            tex1.T.mask = self.tiles[0].TMask
        #Update node values
        override = bpy.context.copy()
        override["material"] = mat
        bpy.ops.material.update_f3d_nodes(override)
        del override
    def EvalFlags(self, flags):
        if not flags:
            return []
        GBIflags = {
            "G_TX_NOMIRROR": None,
            "G_TX_WRAP": None,
            "G_TX_MIRROR": ("mirror"),
            "G_TX_CLAMP": ("clamp"),
            "0": None,
            "1": ("mirror"),
            "2": ("clamp"),
            "3": ("clamp","mirror")
        }
        x = []
        fsplit = flags.split("|")
        for f in fsplit:
            z = GBIflags.get(f.strip(), 0)
            if z:
                x.append(z)
        return x
    #only work with macros I can recognize for now
    def SetRenderMode(self, f3d):
        rdp = f3d.rdp_settings
        rdp.set_rendermode = True
        #if the enum isn't there, then just print an error for now
        try:
            rdp.rendermode_preset_cycle_1 = self.RenderMode[0]
            rdp.rendermode_preset_cycle_2 = self.RenderMode[1]
            #print(f"set render modes with render mode {self.RenderMode}")
        except:
            print(f"could not set render modes with render mode {self.RenderMode}")
    def SetGeoMode(self, rdp, mat):
        #texture gen has a different name than gbi
        for a in self.GeoSet:
            setattr(rdp, a.replace('G_TEXTURE_GEN','G_TEX_GEN').lower().strip(), True)
        for a in self.GeoClear:
            setattr(rdp, a.replace('G_TEXTURE_GEN','G_TEX_GEN').lower().strip(), False)
    #Very lazy for now
    def SetCombiner(self,f3d):
        if not hasattr(self,'Combiner'):
            f3d.combiner1.A = 'TEXEL0'
            f3d.combiner1.A_alpha = '0'
            f3d.combiner1.C = 'SHADE'
            f3d.combiner1.C_alpha = '0'
            f3d.combiner1.D = '0'
            f3d.combiner1.D_alpha = '1'
        else:
            f3d.combiner1.A = self.Combiner[0]
            f3d.combiner1.B = self.Combiner[1]
            f3d.combiner1.C = self.Combiner[2]
            f3d.combiner1.D = self.Combiner[3]
            f3d.combiner1.A_alpha = self.Combiner[4]
            f3d.combiner1.B_alpha = self.Combiner[5]
            f3d.combiner1.C_alpha = self.Combiner[6]
            f3d.combiner1.D_alpha = self.Combiner[7]
            f3d.combiner2.A = self.Combiner[8]
            f3d.combiner2.B = self.Combiner[9]
            f3d.combiner2.C = self.Combiner[10]
            f3d.combiner2.D = self.Combiner[11]
            f3d.combiner2.A_alpha = self.Combiner[12]
            f3d.combiner2.B_alpha = self.Combiner[13]
            f3d.combiner2.C_alpha = self.Combiner[14]
            f3d.combiner2.D_alpha = self.Combiner[15]
    def EvalFmt(self, tex):
        GBIfmts = {
            "G_IM_FMT_RGBA":"RGBA",
            "RGBA":"RGBA",
            "G_IM_FMT_CI":"CI",
            "CI":"CI",
            "G_IM_FMT_IA":"IA",
            "IA":"IA",
            "G_IM_FMT_I":"I",
            "I":"I",
            "0":"RGBA",
            "2":"CI",
            "3":"IA",
            "4":"I"
        }
        GBIsiz = {
            "G_IM_SIZ_4b":"4",
            "G_IM_SIZ_8b":"8",
            "G_IM_SIZ_16b":"16",
            "G_IM_SIZ_32b":"32",
            "0":"4",
            "1":"8",
            "2":"16",
            "3":"32"
        }
        return GBIfmts.get(tex.Fmt,"RGBA") + GBIsiz.get(str(tex.Siz),"16")

# handles DL import processing, specifically built to process each cmd into the mat class
# should be inherited into a larger F3d class which wraps DL processing
# does not deal with flow control or gathering the data containers (VB, Geo cls etc.)
class DL:
    # the min needed for this class to work for importing
    def __init__(self, lastmat=None):
        self.VB = {}
        self.Gfx = {}
        self.diff = {}
        self.amb = {}
        self.Lights = {}
        if not lastmat:
            self.LastMat = Mat()
            self.LastMat.name = 0
        else:
            self.LastMat = lastmat
    # DL cmds that control the flow of a DL cannot be handled within a independent	#class method without larger context of the total DL
    # def gsSPEndDisplayList():
    # return
    # def gsSPBranchList():
    # break
    # def gsSPDisplayList():
    # continue
    # Vertices are one big list for kirby64, all buffers are combined in pre process
    def gsSPVertex(self, args, Geo):
        # fill virtual buffer
        args = [int(a) for a in args]
        addr = Geo.seg2phys(args[0]) -32
        start = int(addr // 16)
        for i in range(args[2], args[2] + args[1], 1):
            self.VertBuff[i] = len(self.Verts) + i - args[2]
        # verts are pre processed
        self.Verts.extend(Geo.vertices.Pos[start : start + args[1]])
        self.UVs.extend(Geo.vertices.UVs[start : start + args[1]])
        self.VCs.extend(Geo.vertices.VCs[start : start + args[1]])
    # Triangles
    def gsSP2Triangles(self, args, Geo):
        self.MakeNewMat()
        args = [int(a) for a in args]
        Tri1 = self.ParseTri(args[:3])
        Tri2 = self.ParseTri(args[4:7])
        self.Tris.append(Tri1)
        self.Tris.append(Tri2)
    def gsSP1Triangle(self, args, Geo):
        self.MakeNewMat()
        args = [int(a) for a in args]
        Tri = self.ParseTri(args[:3])
        self.Tris.append(Tri)
    # materials
    # Mats will be placed sequentially. The first item of the list is the triangle number
    # The second is the material class
    def gsDPSetRenderMode(self, args, Geo):
        self.NewMat = 1
        self.LastMat.RenderMode = [a.strip() for a in args]
    def gsDPSetFogColor(self, args, Geo):
        self.NewMat = 1
        self.LastMat.fog_color = args
    def gsSPFogPosition(self, args, Geo):
        self.NewMat = 1
        self.LastMat.fog_pos = args
    def gsSPLightColor(self, args, Geo):
        self.NewMat = 1
        if not hasattr(self.LastMat, "light_col"):
            self.LastMat.light_col = {}
        num = re.search("_\d", args[0]).group()[1]
        self.LastMat.light_col[num] = args[-1]
    def gsDPSetPrimColor(self, args, Geo):
        self.NewMat = 1
        self.LastMat.prim_color = args
    def gsDPSetEnvColor(self, args, Geo):
        self.NewMat = 1
        self.LastMat.env_color = args
    # multiple geo modes can happen in a row that contradict each other
    # this is mostly due to culling wanting diff geo modes than drawing
    # but sometimes using the same vertices
    def gsSPClearGeometryMode(self, args, Geo):
        self.NewMat = 1
        args = [a.strip() for a in args[0].split("|")]
        for a in args:
            if a in self.LastMat.GeoSet:
                self.LastMat.GeoSet.remove(a)
        self.LastMat.GeoClear.extend(args)
    def gsSPSetGeometryMode(self, args, Geo):
        self.NewMat = 1
        args = [a.strip() for a in args[0].split("|")]
        for a in args:
            if a in self.LastMat.GeoClear:
                self.LastMat.GeoClear.remove(a)
        self.LastMat.GeoSet.extend(args)
    def gsSPGeometryMode(self, args, Geo):
        self.NewMat = 1
        argsC = [a.strip() for a in args[0].split("|")]
        argsS = [a.strip() for a in args[1].split("|")]
        for a in argsC:
            if a in self.LastMat.GeoSet:
                self.LastMat.GeoSet.remove(a)
        for a in argsS:
            if a in self.LastMat.GeoClear:
                self.LastMat.GeoClear.remove(a)
        self.LastMat.GeoClear.extend(argsC)
        self.LastMat.GeoSet.extend(argsS)
    def gsDPSetCycleType(self, args, Geo):
        if "G_CYC_1CYCLE" in args[0]:
            self.LastMat.TwoCycle = False
        if "G_CYC_2CYCLE" in args[0]:
            self.LastMat.TwoCycle = True
    def gsDPSetCombineMode(self, args, Geo):
        self.NewMat = 1
        self.LastMat.Combiner = args
    def gsDPSetCombineLERP(self, args, Geo):
        self.NewMat = 1
        self.LastMat.Combiner = [a.strip() for a in args]
    # root tile, scale and set tex
    def gsSPTexture(self, args, Geo):
        self.NewMat = 1
        self.LastMat.set_tex = int(args[-1].strip()) == 2
        self.LastMat.tex_scale = [
            ((0x10000 * (int(a) < 0)) + int(a)) / 0xFFFF for a in args[0:2]
        ]  # signed half to unsigned half
        self.LastMat.tile_root = int(args[-2])  # I don't think I'll actually use this
    # last tex is a palette
    def gsDPLoadTLUT(self, args, Geo):
        try:
            tex = self.LastMat.loadtex
            self.LastMat.pal = tex
        except:
            print(
                "**--Load block before set t img, DL is partial and missing context"
                "likely static file meant to be used as a piece of a realtime system.\n"
                "No interpretation on file possible**--"
            )
            return None
    # tells us what tile the last loaded mat goes into
    def gsDPLoadBlock(self, args, Geo):
        try:
            tex = self.LastMat.loadtex
            # these values can be used to calc texture size
            tex.dxt = eval(args[4])
            tex.texels = eval(args[3])
            tile = self.EvalTile(args[0])
            tex.tile = tile
            if tile == 7:
                self.LastMat.tex0 = tex
            elif tile == 6:
                self.LastMat.tex1 = tex
        except:
            print(
                "**--Load block before set t img, DL is partial and missing context"
                "likely static file meant to be used as a piece of a realtime system.\n"
                "No interpretation on file possible**--"
            )
            return None
    def gsDPSetTextureImage(self, args, Geo):
        self.NewMat = 1
        Timg = (eval(args[3].strip()) >> 16, eval(args[3].strip()) & 0xFFFF)
        Fmt = args[1].strip()
        Siz = args[2].strip()
        loadtex = Texture(Timg, Fmt, Siz)
        self.LastMat.loadtex = loadtex
    # catch tile size
    def gsDPSetTileSize(self, args, Geo):
        self.NewMat = 1
        tile = self.LastMat.tiles[self.EvalTile(args[0])]
        tile.Slow = self.EvalImFrac(args[1].strip())
        tile.Tlow = self.EvalImFrac(args[2].strip())
        tile.Shigh = self.EvalImFrac(args[3].strip())
        tile.Thigh = self.EvalImFrac(args[4].strip())
    def gsDPSetTile(self, args, Geo):
        self.NewMat = 1
        tile = self.LastMat.tiles[self.EvalTile(args[4])]
        tile.Fmt = args[0].strip()
        tile.Siz = args[1].strip()
        tile.Tflags = args[6].strip()
        tile.TMask = int(args[7].strip())
        tile.TShift = int(args[8].strip())
        tile.Sflags = args[9].strip()
        tile.SMask = int(args[10].strip())
        tile.SShift = int(args[11].strip())
    def MakeNewMat(self):
        if self.NewMat:
            self.NewMat = 0
            self.Mats.append([len(self.Tris) - 1, self.LastMat])
            self.LastMat = deepcopy(self.LastMat)  # for safety
            self.LastMat.name = self.num + 1
            if self.LastMat.tx_scr:
                # I'm clearing here because I did some illegal stuff a bit before, temporary (maybe)
                self.LastMat.tx_scr = None
            self.num += 1
    def ParseTri(self, Tri):
        return [self.VertBuff[a] for a in Tri]
    def EvalImFrac(self, arg):
        if type(arg) == int:
            return arg
        arg2 = arg.replace("G_TEXTURE_IMAGE_FRAC", "2")
        return eval(arg2)
    def EvalTile(self, arg):
        # only 0 and 7 have enums, other stuff just uses int (afaik)
        Tiles = {
            "G_TX_LOADTILE": 7,
            "G_TX_RENDERTILE": 0,
        }
        t = Tiles.get(arg)
        if t == None:
            t = int(arg)
        return t

#used to parse imports with specific kirby information, works on entire layouts
class F3d(DL):
    def __init__(self, lastmat = None):
        super().__init__()
        self.num = self.LastMat.name  # for debug
    #use tex scroll struct info to get the equivalent dynamic DL, and set the t_scroll flag to true in mat so when getting mats, I can return an array of mats
    def ScrollDynDL(self, Geo, layout, scr_num):
        Tex_Scroll = Geo.tex_scrolls[Geo.tex_header[layout.index]]
        scr = Tex_Scroll.scrolls[Tex_Scroll.scroll_ptrs[scr_num]]
        self.LastMat.tx_scr = scr
        flgs = scr.scroll.flags
        #do textures and palettes by taking only the first texture, the rest will have to go into the scroll object
        if flgs & 3:
            Timg = scr.textures[0]
            Fmt = scr.scroll.fmt1
            Siz = scr.scroll.siz1
            loadtex = Texture(Timg, Fmt, Siz)
            loadtex.scr_tex = scr.textures[:-1]
            self.LastMat.loadtex = loadtex
            #if both textures are present, dyn DL loads tex1 (tile 6)
            #this results in both just being the same as far as my
            #export is concerned, but I will replicate DL bhv
            if flgs & 3 == 3:
                self.LastMat.tex1 = loadtex
                self.LastMat.tex1.scr_tex = scr.textures[:-1]
        #if there is both a tex and a palette, then the load TLUT
        #is inside of the dyn DL, otherwise it isn't
        if flgs & 4:
            Timg = scr.palettes[0]
            Fmt = "G_IM_FMT_RGBA"
            Siz = "G_IM_SIZ_16b"
            pal_tex = Texture(Timg, Fmt, Siz)
            pal_tex.scr_pal = scr.palettes[:-1]
            if scr.scroll.flags & 3:
                self.LastMat.pal = pal_tex
            else:
                self.LastMat.loadtex = pal_tex
        #set some color registers
        if flgs & 0x400:
            self.LastMat.env = scr.scroll.env_col
        if flgs & 0x800:
            self.LastMat.blend = scr.scroll.blend_col
        if flgs & 0x1000:
            self.LastMat.light_col[1] = scr.scroll.light1_col
        if flgs & 0x2000:
            self.LastMat.light_col[2] = scr.scroll.light2_col
        #prim is sort of special and set with various flags
        if flgs & 0x18:
            self.LastMat.prim = (0, scr.scroll.primLODFrac, scr.scroll.prim_col)
        #texture scale
        if flgs & 0x80:
            self.LastMat.tex_scale = (scr.scroll.xScale, scr.scroll.yScale)
    #recursively parse the display list in order to return a bunch of model data
    def GetDataFromDL(self, Geo, layout):
        self.VertBuff = [0]*32 #If you're doing some fucky shit with a larger vert buffer it sucks to suck I guess
        self.Tris = []
        self.UVs = []
        self.VCs = []
        self.Verts = []
        self.Mats = []
        self.NewMat = 0
        if hasattr(layout, "DLs"):
            for k in layout.entry:
                DL = layout.DLs[k]
                self.ParseDL(DL, Geo, layout)
        return (self.Verts, self.Tris)
    def ParseDL(self, DL, Geo, layout):
        #This will be the equivalent of a giant switch case
        x = -1
        while(x < len(DL)):
            # manaual iteration so I can skip certain children efficiently if needed
            x += 1
            (cmd, args) = DL[x]  # each member is a tuple of (cmd, arguments)
            LsW = cmd.startswith
            # Deal with control flow first, this requires total DL context
            if LsW("gsSPEndDisplayList"):
                return
            # recursively call ParseDL
            if LsW("gsSPBranchList"):
                if self.DL_ptr(args[0]):
                    self.ParseDL(layout.DLs[self.DL_ptr(args[0])], Geo, layout)
                else:
                    scr_num = (eval(args[0]) & 0xFFFF) // 8
                    self.ScrollDynDL(Geo, layout, scr_num)
                break
            if LsW("gsSPDisplayList"):
                if self.DL_ptr(args[0]):
                    self.ParseDL(layout.DLs[self.DL_ptr(args[0])], Geo, layout)
                else:
                    scr_num = (eval(args[0]) & 0xFFFF) // 8
                    self.ScrollDynDL(Geo, layout, scr_num)
                continue
            # tri and mat DL cmds will be called via parent class
            func = getattr(self, cmd, None)
            if func:
                func(args, Geo)
    def EvalCombiner(self,arg):
        #two args
        GBI_CC_Macros = {
            'G_CC_PRIMITIVE': ['0', '0', '0', 'PRIMITIVE', '0', '0', '0', 'PRIMITIVE'],
            'G_CC_SHADE': ['0', '0', '0', 'SHADE', '0', '0', '0', 'SHADE'],
            'G_CC_MODULATEI': ['TEXEL0', '0', 'SHADE', '0', '0', '0', '0', 'SHADE'],
            'G_CC_MODULATEIDECALA': ['TEXEL0', '0', 'SHADE', '0', '0', '0', '0', 'TEXEL0'],
            'G_CC_MODULATEIFADE': ['TEXEL0', '0', 'SHADE', '0', '0', '0', '0', 'ENVIRONMENT'],
            'G_CC_MODULATERGB': ['TEXEL0', '0', 'SHADE', '0', '0', '0', '0', 'SHADE'],
            'G_CC_MODULATERGBDECALA': ['TEXEL0', '0', 'SHADE', '0', '0', '0', '0', 'TEXEL0'],
            'G_CC_MODULATERGBFADE': ['TEXEL0', '0', 'SHADE', '0', '0', '0', '0', 'ENVIRONMENT'],
            'G_CC_MODULATEIA': ['TEXEL0', '0', 'SHADE', '0', 'TEXEL0', '0', 'SHADE', '0'],
            'G_CC_MODULATEIFADEA': ['TEXEL0', '0', 'SHADE', '0', 'TEXEL0', '0', 'ENVIRONMENT', '0'],
            'G_CC_MODULATEFADE': ['TEXEL0', '0', 'SHADE', '0', 'ENVIRONMENT', '0', 'TEXEL0', '0'],
            'G_CC_MODULATERGBA': ['TEXEL0', '0', 'SHADE', '0', 'TEXEL0', '0', 'SHADE', '0'],
            'G_CC_MODULATERGBFADEA': ['TEXEL0', '0', 'SHADE', '0', 'ENVIRONMENT', '0', 'TEXEL0', '0'],
            'G_CC_MODULATEI_PRIM': ['TEXEL0', '0', 'PRIMITIVE', '0', '0', '0', '0', 'PRIMITIVE'],
            'G_CC_MODULATEIA_PRIM': ['TEXEL0', '0', 'PRIMITIVE', '0', 'TEXEL0', '0', 'PRIMITIVE', '0'],
            'G_CC_MODULATEIDECALA_PRIM': ['TEXEL0', '0', 'PRIMITIVE', '0', '0', '0', '0', 'TEXEL0'],
            'G_CC_MODULATERGB_PRIM': ['TEXEL0', '0', 'PRIMITIVE', '0', 'TEXEL0', '0', 'PRIMITIVE', '0'],
            'G_CC_MODULATERGBA_PRIM': ['TEXEL0', '0', 'PRIMITIVE', '0', 'TEXEL0', '0', 'PRIMITIVE', '0'],
            'G_CC_MODULATERGBDECALA_PRIM': ['TEXEL0', '0', 'PRIMITIVE', '0', '0', '0', '0', 'TEXEL0'],
            'G_CC_FADE': ['SHADE', '0', 'ENVIRONMENT', '0', 'SHADE', '0', 'ENVIRONMENT', '0'],
            'G_CC_FADEA': ['TEXEL0', '0', 'ENVIRONMENT', '0', 'TEXEL0', '0', 'ENVIRONMENT', '0'],
            'G_CC_DECALRGB': ['0', '0', '0', 'TEXEL0', '0', '0', '0', 'SHADE'],
            'G_CC_DECALRGBA': ['0', '0', '0', 'TEXEL0', '0', '0', '0', 'TEXEL0'],
            'G_CC_DECALFADE': ['0', '0', '0', 'TEXEL0', '0', '0', '0', 'ENVIRONMENT'],
            'G_CC_DECALFADEA': ['0', '0', '0', 'TEXEL0', 'TEXEL0', '0', 'ENVIRONMENT', '0'],
            'G_CC_BLENDI': ['ENVIRONMENT', 'SHADE', 'TEXEL0', 'SHADE', '0', '0', '0', 'SHADE'],
            'G_CC_BLENDIA': ['ENVIRONMENT', 'SHADE', 'TEXEL0', 'SHADE', 'TEXEL0', '0', 'SHADE', '0'],
            'G_CC_BLENDIDECALA': ['ENVIRONMENT', 'SHADE', 'TEXEL0', 'SHADE', '0', '0', '0', 'TEXEL0'],
            'G_CC_BLENDRGBA': ['TEXEL0', 'SHADE', 'TEXEL0_ALPHA', 'SHADE', '0', '0', '0', 'SHADE'],
            'G_CC_BLENDRGBDECALA': ['TEXEL0', 'SHADE', 'TEXEL0_ALPHA', 'SHADE', '0', '0', '0', 'TEXEL0'],
            'G_CC_BLENDRGBFADEA': ['TEXEL0', 'SHADE', 'TEXEL0_ALPHA', 'SHADE', '0', '0', '0', 'ENVIRONMENT'],
            'G_CC_ADDRGB': ['TEXEL0', '0', 'TEXEL0', 'SHADE', '0', '0', '0', 'SHADE'],
            'G_CC_ADDRGBDECALA': ['TEXEL0', '0', 'TEXEL0', 'SHADE', '0', '0', '0', 'TEXEL0'],
            'G_CC_ADDRGBFADE': ['TEXEL0', '0', 'TEXEL0', 'SHADE', '0', '0', '0', 'ENVIRONMENT'],
            'G_CC_REFLECTRGB': ['ENVIRONMENT', '0', 'TEXEL0', 'SHADE', '0', '0', '0', 'SHADE'],
            'G_CC_REFLECTRGBDECALA': ['ENVIRONMENT', '0', 'TEXEL0', 'SHADE', '0', '0', '0', 'TEXEL0'],
            'G_CC_HILITERGB': ['PRIMITIVE', 'SHADE', 'TEXEL0', 'SHADE', '0', '0', '0', 'SHADE'],
            'G_CC_HILITERGBA': ['PRIMITIVE', 'SHADE', 'TEXEL0', 'SHADE', 'PRIMITIVE', 'SHADE', 'TEXEL0', 'SHADE'],
            'G_CC_HILITERGBDECALA': ['PRIMITIVE', 'SHADE', 'TEXEL0', 'SHADE', '0', '0', '0', 'TEXEL0'],
            'G_CC_SHADEDECALA': ['0', '0', '0', 'SHADE', '0', '0', '0', 'TEXEL0'],
            'G_CC_SHADEFADEA': ['0', '0', '0', 'SHADE', '0', '0', '0', 'ENVIRONMENT'],
            'G_CC_BLENDPE': ['PRIMITIVE', 'ENVIRONMENT', 'TEXEL0', 'ENVIRONMENT', 'TEXEL0', '0', 'SHADE', '0'],
            'G_CC_BLENDPEDECALA': ['PRIMITIVE', 'ENVIRONMENT', 'TEXEL0', 'ENVIRONMENT', '0', '0', '0', 'TEXEL0'],
            '_G_CC_BLENDPE': ['ENVIRONMENT', 'PRIMITIVE', 'TEXEL0', 'PRIMITIVE', 'TEXEL0', '0', 'SHADE', '0'],
            '_G_CC_BLENDPEDECALA': ['ENVIRONMENT', 'PRIMITIVE', 'TEXEL0', 'PRIMITIVE', '0', '0', '0', 'TEXEL0'],
            '_G_CC_TWOCOLORTEX': ['PRIMITIVE', 'SHADE', 'TEXEL0', 'SHADE', '0', '0', '0', 'SHADE'],
            '_G_CC_SPARSEST': ['PRIMITIVE', 'TEXEL0', 'LOD_FRACTION', 'TEXEL0', 'PRIMITIVE', 'TEXEL0', 'LOD_FRACTION', 'TEXEL0'],
            'G_CC_TEMPLERP': ['TEXEL1', 'TEXEL0', 'PRIM_LOD_FRAC', 'TEXEL0', 'TEXEL1', 'TEXEL0', 'PRIM_LOD_FRAC', 'TEXEL0'],
            'G_CC_TRILERP': ['TEXEL1', 'TEXEL0', 'LOD_FRACTION', 'TEXEL0', 'TEXEL1', 'TEXEL0', 'LOD_FRACTION', 'TEXEL0'],
            'G_CC_INTERFERENCE': ['TEXEL0', '0', 'TEXEL1', '0', 'TEXEL0', '0', 'TEXEL1', '0'],
            'G_CC_1CYUV2RGB': ['TEXEL0', 'K4', 'K5', 'TEXEL0', '0', '0', '0', 'SHADE'],
            'G_CC_YUV2RGB': ['TEXEL1', 'K4', 'K5', 'TEXEL1', '0', '0', '0', '0'],
            'G_CC_PASS2': ['0', '0', '0', 'COMBINED', '0', '0', '0', 'COMBINED'],
            'G_CC_MODULATEI2': ['COMBINED', '0', 'SHADE', '0', '0', '0', '0', 'SHADE'],
            'G_CC_MODULATEIA2': ['COMBINED', '0', 'SHADE', '0', 'COMBINED', '0', 'SHADE', '0'],
            'G_CC_MODULATERGB2': ['COMBINED', '0', 'SHADE', '0', '0', '0', '0', 'SHADE'],
            'G_CC_MODULATERGBA2': ['COMBINED', '0', 'SHADE', '0', 'COMBINED', '0', 'SHADE', '0'],
            'G_CC_MODULATEI_PRIM2': ['COMBINED', '0', 'PRIMITIVE', '0', '0', '0', '0', 'PRIMITIVE'],
            'G_CC_MODULATEIA_PRIM2': ['COMBINED', '0', 'PRIMITIVE', '0', 'COMBINED', '0', 'PRIMITIVE', '0'],
            'G_CC_MODULATERGB_PRIM2': ['COMBINED', '0', 'PRIMITIVE', '0', '0', '0', '0', 'PRIMITIVE'],
            'G_CC_MODULATERGBA_PRIM2': ['COMBINED', '0', 'PRIMITIVE', '0', 'COMBINED', '0', 'PRIMITIVE', '0'],
            'G_CC_DECALRGB2': ['0', '0', '0', 'COMBINED', '0', '0', '0', 'SHADE'],
            'G_CC_BLENDI2': ['ENVIRONMENT', 'SHADE', 'COMBINED', 'SHADE', '0', '0', '0', 'SHADE'],
            'G_CC_BLENDIA2': ['ENVIRONMENT', 'SHADE', 'COMBINED', 'SHADE', 'COMBINED', '0', 'SHADE', '0'],
            'G_CC_CHROMA_KEY2': ['TEXEL0', 'CENTER', 'SCALE', '0', '0', '0', '0', '0'],
            'G_CC_HILITERGB2': ['ENVIRONMENT', 'COMBINED', 'TEXEL0', 'COMBINED', '0', '0', '0', 'SHADE'],
            'G_CC_HILITERGBA2': ['ENVIRONMENT', 'COMBINED', 'TEXEL0', 'COMBINED', 'ENVIRONMENT', 'COMBINED', 'TEXEL0', 'COMBINED'],
            'G_CC_HILITERGBDECALA2': ['ENVIRONMENT', 'COMBINED', 'TEXEL0', 'COMBINED', '0', '0', '0', 'TEXEL0'],
            'G_CC_HILITERGBPASSA2': ['ENVIRONMENT', 'COMBINED', 'TEXEL0', 'COMBINED', '0', '0', '0', 'COMBINED'],
        }
        return GBI_CC_Macros.get(arg[0].strip(), ['TEXEL0', '0', 'SHADE', '0', 'TEXEL0', '0', 'SHADE', '0']) + \
            GBI_CC_Macros.get(arg[1].strip(), ['TEXEL0', '0', 'SHADE', '0', 'TEXEL0', '0', 'SHADE', '0'])
    def DL_ptr(self, num):
        num = int(num)
        if num >> 24 == 0xE:
            return None
        else:
            return num
    def MakeNewMat(self):
        if self.NewMat:
            self.NewMat = 0
            self.Mats.append([len(self.Tris)-1,self.LastMat])
            self.LastMat = deepcopy(self.LastMat) #for safety
            self.LastMat.name = self.num + 1
            self.num += 1
    def ParseTri(self,Tri):
        return [self.VertBuff[a] for a in Tri]
    def StripArgs(self,cmd):
        a = cmd.find("(")
        return cmd[a+1:-2].split(',')
    def ApplyDat(self, obj, mesh, tex_path):
        tris = mesh.polygons
        bpy.context.view_layer.objects.active = obj
        ind = -1
        new = -1
        UVmap = obj.data.uv_layers.new(name = 'UVMap')
        #I can get the available enums for color attrs with this func
        vcol_enums = propertyGroupGetEnums(bpy.types.FloatColorAttribute, 'data_type')
        #enums were changed in a blender version, this should future proof it a little
        if "FLOAT_COLOR" in vcol_enums:
            e = "FLOAT_COLOR"
        else:
            e = "COLOR"
        Vcol = obj.data.color_attributes.get('Col')
        if not Vcol:
            Vcol = obj.data.color_attributes.new(name = 'Col', type = e, domain = "CORNER")
        Valph = obj.data.color_attributes.get('Alpha')
        if not Valph:
            Valph = obj.data.color_attributes.new(name = 'Alpha', type = e, domain = "CORNER")
        self.Mats.append([len(tris), 0])
        for i, t in enumerate(tris):
            if i > self.Mats[ind + 1][0]:
                new = self.Create_new_f3d_mat(self.Mats[ind+1][1], mesh)
                ind += 1
                if not new:
                    new = len(mesh.materials)-1
                    mat = mesh.materials[new]
                    mat.name = "KCS F3D Mat {} {}".format(obj.name, new)
                    self.Mats[new][1].ApplyMatSettings(mat, tex_path)
                else:
                    #I tried to re use mat slots but it is much slower, and not as accurate
                    #idk if I was just doing it wrong or the search is that much slower, but this is easier
                    mesh.materials.append(new)
                    new = len(mesh.materials)-1  
            #if somehow ther is no material assigned to the triangle or something is lost
            if new != -1:
                t.material_index = new
                #Get texture size or assume 32, 32 otherwise
                i = mesh.materials[new].f3d_mat.tex0.tex
                if not i:
                    WH = (32,32)
                else:
                    WH = i.size
                #Set UV data and Vertex Color Data
                for v,l in zip(t.vertices, t.loop_indices):
                    uv = self.UVs[v]
                    vcol = self.VCs[v]
                    #scale verts. I just copy/pasted this from kirby tbh Idk
                    UVmap.data[l].uv = [a*(1/(32*b)) if b>0 else a*.001*32 for a,b in zip(uv,WH)]
                    #idk why this is necessary. N64 thing or something?
                    UVmap.data[l].uv[1] = UVmap.data[l].uv[1]*-1 + 1
                    Vcol.data[l].color = [a/255 for a in vcol]
    def Create_new_f3d_mat(self, mat, mesh):
        #check if this mat was used already in another mesh (or this mat if DL is garbage or something)
        #even looping n^2 is probably faster than duping 3 mats with blender speed
        for j, F3Dmat in enumerate(bpy.data.materials):
            if F3Dmat.is_f3d:
                dupe = mat.MatHashF3d(F3Dmat.f3d_mat)
                if dupe:
                    return F3Dmat
        if mesh.materials:
            mat = mesh.materials[-1]
            new = mat.id_data.copy() #make a copy of the data block
            #add a mat slot and add mat to it
            mesh.materials.append(new)
        else:
            bpy.ops.object.create_f3d_mat() #the newest mat should be in slot[-1] for the mesh materials
        return None


#a data class that will hold various primitive geo classes and then write them out to files
#population of the classes will be done by bpy_geo or geo_bin
class geo_write(FModel):
    def __init__(self, name = "Kirby"):
        super().__init__("F3DEX2/LX2", False, name, DLFormat.Static, GfxMatWriteMethod.WriteAll)
    def save_binary(self, file):
        print(file)
    def to_c(self, file):
        pass
    def to_c_inline(self, file):
        for ly in self.layouts:
            fMesh = ly.ptr
            if fMesh.mesh:
                GfxDat, VtxDat = fMesh.to_c_inline()
                print(GfxDat.source)
                print(file)
    def construct_fMaterial(self, name, DLformat):
        return fMat_KCS(name, DLformat)
    #given a layout, create the export data such as verts, f3d cls, and mat classes
    def create_mesh_dat(self):
        for ly in self.layouts:
            #should be mesh data
            if mesh := ly.ptr.mesh:
                #Create mats and mat DLs
                fMesh = ly.ptr
                fMesh.mat_tris = {m:mesh_desc(list(),\
                *saveOrGetF3DMaterial(m, self, fMesh.obj, None, None), None) for m in mesh.materials}
                #put tris in dict of mat
                mesh.calc_loop_triangles()
                for tri in mesh.loop_triangles:
                    mat = mesh.materials[tri.material_index]
                    fMesh.mat_tris[mat].tri_list.append(tri)
                #use tris to create tri groups
                for j, (mat, desc) in enumerate(fMesh.mat_tris.items()):
                    if desc.tri_list:
                        fMesh.save_tri_list(desc.tri_list, desc.fMaterial, desc.texDimensions, mat, self.f3d, index = j)
    #now that all the verts are made, and the mats have the info they need, make the DLs
    def create_DLs(self):
        lastMat = None
        for ly in self.layouts:
            #independent mats are already created, now using f3d class bleed them together
            fMesh = ly.ptr
            lastMat = fMesh.bleed(lastMat)
            # fMesh.print_DLs()
            #now clean up the obj
            fMesh.clean()


#overrdides fMaterial
class fMat_KCS(FMaterial):
    def __init__(self, name, DLformat):
        super().__init__(name, DLformat)
        self.name = name
        self.textures = [GfxList(f"tex_{i}_" + name, GfxListTag.Material, DLFormat.Static) for i in range(8)]
        self.textureLoads = {}  # dict of {tex_offset : DPSetTextureImage}

#small containers for mesh data
@dataclass
class bleed_gfx:
    bled_mats: list
    bled_tex: list


@dataclass
class mesh_desc:
    tri_list: list
    fMaterial: fMat_KCS
    texDimensions: tuple
    bleed: bleed_gfx


#Holds all the info needed for one mesh to export
#bleeds mesh materials together
class F3d_Mesh(FMesh):
    def __init__(self, obj, mesh, scale, f3d):
        if mesh:
            self.obj, self.mesh = obj, mesh
        else:
            self.mesh = None
            self.obj = obj
        self.scale = scale
        super().__init__(obj.name, DLFormat.Static)
        self.f3d = f3d
    def clean(self):
        pass
    def bleed(self, LastMat):
        if not self.mesh: return
        for mat, desc in self.mat_tris.items():
            #bleed mat and tex
            if desc.fMaterial:
                bleed_mat = self.bleed_mat(desc.fMaterial, LastMat)
                bleed_tex = self.bleed_textures(desc.fMaterial, LastMat)
            else:
                bleed_mat = []
                bleed_tex = []
            #set bled props to _mesh_desc, update LastMat
            LastMat = desc.fMaterial
            desc.bleed = bleed_gfx(bleed_mat, bleed_tex)
        return LastMat
    def bleed_textures(self, mat, LastMat):
        if LastMat:
            #bleed cmds if tiles are the same
            #or pipe syncs as of now
            bled_tex = []
            for j, (LastTex, TexCmds) in enumerate(zip(LastMat.textures, mat.textures)):
                print(f"tex {j} start bleed")
                #deep copy breaks on Image objects so I will only copy the levels needed
                commands_bled = copy.copy(TexCmds)
                commands_bled.commands = copy.copy(TexCmds.commands) #copy the commands also
                LastList = LastTex.commands
                #eliminate set tex images
                set_tex = (c for c in TexCmds.commands if type(c) == DPSetTextureImage)
                removed_tex = [c for c in set_tex if c in LastList] #needs to be a list to check "in" multiple times
                rm_load = None #flag to elim loads once
                for j, cmd in enumerate(TexCmds.commands):
                    #remove set tex explicitly
                    if cmd in removed_tex:
                        commands_bled.commands.remove(cmd)
                        rm_load = True
                        continue
                    if rm_load and type(cmd) in (DPLoadTLUTCmd, DPLoadTile, DPLoadBlock):
                        commands_bled.commands.remove(cmd)
                        rm_load = None
                        continue
                #now eval as normal conditionals
                iter_cmds = copy.copy(commands_bled.commands) #need extra list to iterate with
                for j, cmd in enumerate(iter_cmds):
                    print(cmd, cmd.to_c(), cmd in LastList)
                    if cmd.bleed(LastList, commands_bled.commands, j):
                        if cmd in LastList:
                            commands_bled.commands.remove(cmd)
                bled_tex.append(commands_bled)
        else:
            bled_tex = mat.textures
        return bled_tex
    def bleed_mat(self, mat, LastMat):
        if LastMat:
            GfxList = mat.material
            #deep copy breaks on Image objects so I will only copy the levels needed
            commands_bled = copy.copy(GfxList)
            commands_bled.commands = copy.copy(GfxList.commands) #copy the commands also
            LastList = LastMat.material.commands
            cnt = 0
            for j, cmd in enumerate(GfxList.commands):
                if cmd.bleed(LastList, commands_bled.commands, j - cnt):
                    if cmd in LastList:
                        commands_bled.commands.pop(j - cnt) #list gets smaller as I pop, so modify index by num popped
                        cnt += 1
            #remove SPEndDisplayList
            while(SPEndDisplayList() in commands_bled.commands):
                commands_bled.commands.remove(SPEndDisplayList())
        else:
            commands_bled = mat.material
        #remove SPEndDisplayList
        while(SPEndDisplayList() in commands_bled.commands):
            commands_bled.commands.remove(SPEndDisplayList())
        return commands_bled
    def save_tri_list(self, tri_list, fMaterial, texDims, mat, f3d, index = 0):
        #make some objects used in the existing code base
        #so I can export triangle. Has some extra functionality
        #used for skinning etc. that I don't take advantage of
        finalTransform = Matrix.Diagonal(Vector((self.scale, self.scale, self.scale))).to_4x4() #just use the blender scale, other obj transforms can be
        #applied to the layout
        triGroup = FTriGroup(self.obj.name, index, fMaterial)
        triConverterInfo = TriangleConverterInfo(
            self.obj,
            None,
            f3d,
            finalTransform,
            getInfoDict(self.obj)
        )
        triConverter = TriangleConverter(
            triConverterInfo,
            texDims,
            mat,
            None,
            triGroup.triList,
            triGroup.vertexList,
            None,
            None,
        )
        saveTriangleStrip( triConverter, tri_list, self.mesh, None)
        self.mat_tris[mat].tri_list = triGroup
    #return Cdata object
    def to_c_inline(self):
        if not self.mesh: return None, None
        GfxData = CData()
        VtxData = CData()
        GfxData.source = f"Gfx {self.name}_mesh[] = {{\n"
        for mat, desc in self.mat_tris.items():
            #add in vertex data
            triGroup = desc.tri_list
            if not triGroup:
                continue
            VtxData.append( triGroup.vertexList.to_c() )
            #add mat, add tex data, then add tri data
            if desc.bleed.bled_mats:
                GfxData.append( desc.bleed.bled_mats.to_c_inline(self.f3d) )
            for tex in desc.bleed.bled_tex:
                if tex:
                    GfxData.append( tex.to_c_inline(self.f3d) )
            GfxData.append( triGroup.triList.to_c_inline(self.f3d) )
        GfxData.source += f"\t{SPEndDisplayList().to_c()}\n}};\n" #end DL
        #there may be tri groups floating around that aren't a part of the mesh_desc object
        #these are from large textures, these will be also inlined, but not right now
        return GfxData, VtxData
    #debug print
    def print_DLs(self):
        if not self.mesh: return
        for mat, desc in self.mat_tris.items():
            triGroup = desc.tri_list
            print("\n\noriginal cmd list\n")
            [print(c) for c in desc.fMaterial.material.commands]
            try:
                print("\n\nbled cmd list\n")
                [print(c) for c in desc.bleed.bled_mats]
                for i, (tex, bleed_tex) in enumerate(zip(desc.fMaterial.textures, desc.bleed.bled_tex)):
                    print(f"\noriginal tex list {i}\n")
                    [print(c) for c in tex.commands]
                    print(f"\nbleed tex list {i}\n")
                    [print(c) for c in bleed_tex]
            except:
                print(f"no bleed on material {self.name}")

# ------------------------------------------------------------------------
#    Exorter Functions
# ------------------------------------------------------------------------

@time_func
def ExportGeoBin(name, obj, context):
    scale = context.scene.KCS_scene.Scale
    blend_geo = bpy_geo(obj, scale)
    out_geo = blend_geo.init_geo() #create writer class
    out_geo.create_mesh_dat()
    out_geo.create_DLs()
    with open(name, 'wb') as file:
        out_geo.save_binary(file)
        out_geo.to_c_inline(file)

# ------------------------------------------------------------------------
#    Importer
# ------------------------------------------------------------------------

@time_func
def ImportGeoBin(bin_file, context, name, path):
    Geo = bin_file
    Geo = open(Geo,'rb')
    collection = context.scene.collection
    rt = MakeEmpty(name,'PLAIN_AXES',collection)
    rt.KCS_obj.KCS_obj_type = 'Graphics'
    Geo_Block = geo_bin(Geo.read(), context.scene.KCS_scene.Scale)
    write = bpy_geo(rt, context.scene.KCS_scene.Scale)
    write.write_gfx("geo", Geo_Block, path, collection)
# ------------------------------------------------------------------------
#    Header
# ------------------------------------------------------------------------
from __future__ import annotations

import bpy

import os, struct, math, re
from mathutils import Vector, Euler, Matrix
from time import time
from pathlib import Path
from typing import TextIO, BinaryIO, Sequence

from ..utility import (
    rotate_quat_blender_to_n64,
    rotate_quat_n64_to_blender,
    apply_objects_modifiers_and_transformations,
    CData,
    PluginError,
)

# ------------------------------------------------------------------------
#    Decorators
# ------------------------------------------------------------------------

# time a function, use as a decorator
def time_func(func: callable):
    # This function shows the execution time of
    # the function object passed
    def wrap_func(*args, **kwargs):
        t1 = time()
        result = func(*args, **kwargs)
        t2 = time()
        print(f"Function {func.__name__!r} executed in {(t2-t1):.4f}s")
        return result

    return wrap_func


# ------------------------------------------------------------------------
#    Classes
# ------------------------------------------------------------------------


# maintain parity with file objects, and CData objects
class KCS_Cdata(CData):
    def __init__(self):
        super().__init__()

    def tell(self):
        return 0

    def extend(self, iterable: Sequence):
        for val in iterable:
            self.source += val.source
            self.header += val.header

    def write(self, content: str):
        self.source += content


# there can only be one of these per fModel object
# this object will manage pointers throughout data
class PointerManager:
    ptr_targets = dict()
    memoize = None

    def __init__(self):
        PointerManager.memoize = self

    def resolve_obj_id(self, obj: object, multi: object):
        if multi:
            return hash((obj, multi))
        else:
            return id(obj)

    # add a pointer target obj to self.ptr_targets, and then return a placeholder object which is filled in after first pass writing
    def add_target(self, obj: object, multi: object = None, cast: str = ""):
        # you can have multiple targets to the same object, so check before making a new Pointer obj
        # though you can also write something multiple times, and only want a pointer to one of those locations
        # so an optional argument is added to bind the specific call to the multi use owner (usually a gfxList)

        # cast is bound by the caller, because it is specific to the struct/arr not where it is going
        ptr = self.ptr_targets.get(self.resolve_obj_id(obj, multi), None)
        if not ptr or multi:
            ptr = Pointer(obj, cast=cast)
            self.ptr_targets[self.resolve_obj_id(obj, multi)] = ptr
        return ptr

    def ptr_obj(self, obj: object, file: KCS_Cdata, label: str, multi: object = None):
        try:
            ptr = self.ptr_targets.get(self.resolve_obj_id(obj, multi), None)
        except Exception as e:
            print(f"failed to find ptr with Expection: {Exception(str(e))}")
            return obj
        if ptr:
            if file:
                ptr.location = file.tell()
            ptr.symbol = label
        return obj


# Placeholder pointer values
class Pointer:
    def __init__(self, obj: object, cast: str = ""):
        self.obj = obj
        self.value = 0
        self.location = 0
        self.symbol = "NULL_ptr"
        self.cast = cast

    @property
    def export_sym(self):
        if self.cast:
            cast = f"({self.cast}) "
        else:
            cast = ""
        return f"{cast}{self.symbol}"

    def __str__(self):
        return f"Pointer_Type.{id(self)}"


# generic container for structs
class StructContainer:
    def __init__(self, data):
        self.dat = data


# just a base class that holds some binary processing
class BinProcess:
    def upt(self, offset: int, typeString: str, length: int):
        return struct.unpack(typeString, self.file[offset : offset + length])

    @staticmethod
    def seg2phys(num: int):
        if num >> 24 == 4:
            return num & 0xFFFFFF
        else:
            return num

    def get_BI_pairs(self, start: int, num: int = 9999, stop: tuple = (0, 0)):
        pairs = []
        for i in range(num):
            BI = self.upt(start + 4 * i, ">HH", 4)
            pairs.append(BI)
            if stop == BI:
                break
        return pairs

    def get_referece_list(self, start: int, stop: int = 0):
        x = 0
        start = self.seg2phys(start)
        ref = []
        r = self.upt(start, ">L", 4)[0]
        while r != stop:
            x += 4
            ref.append(r)
            r = self.upt(start + x, ">L", 4)[0]
        ref.append(r)
        return ref

    def sort_dict(self, dictionary: dict):
        return {k: dictionary[k] for k in sorted(dictionary.keys())}


# this class writes bin data out from within the class
# taken from level splitting tools, staged to be rewritten for blender specifically
class BinWrite:
    def symbol_init(self):
        if not hasattr(self, "ptrManager"):
            self.ptrManager = PointerManager()
        else:
            self.ptrManager = PointerManager.memoize
        # pass through methods
        self.add_target = self.ptrManager.add_target
        self.ptr_obj = self.ptrManager.ptr_obj

    # now that things are written, find the replacement data for all the pointers
    def resolve_ptrs_c(self, file: KCS_Cdata):
        for obj, ptr in self.ptrManager.ptr_targets.items():
            file.source = file.source.replace(str(ptr), ptr.export_sym)

    # given a symbol with a data type, make an extern and add it
    def add_header(self, file: KCS_Cdata, datType: str, label: str):
        file.header += f"extern {datType} {label};\n"

    # format arr data
    def format_arr(self, vals: Union[Sequence, Str], name: str, file: KCS_Cdata):
        # infer type from first item of each array
        if type(vals[0]) == float:
            return f"""{", ".join( [f"{self.ptr_obj(a, file, f'&{name}[{j}]'):f}" for j, a in enumerate(vals)] )}"""
        # happens during recursion
        elif type(vals[0]) == str:
            return ",\n\t".join(vals)
        # ptr or other objects
        elif type(vals[0]) != int:
            return f"""{", ".join( [str(self.ptr_obj(a, file, f"&{name}[{j}]")) for j, a in enumerate(vals)] )}"""
        else:
            return f"""{", ".join( [hex(self.ptr_obj(a, file, f"&{name}[{j}]")) for j, a in enumerate(vals)] )}"""

    # format arr ptr data into string
    def format_arr_ptr(self, arr: Sequence, name: str, file: KCS_Cdata, BI: bool = None, ptr_format: str = "0x"):
        vals = []
        for j, a in enumerate(arr):
            # set symbol if obj is a ptr target
            self.ptr_obj(arr, file, f"&{name}[{j}]")
            if a == 0x99999999 or a == (0x9999, 0x9999):
                vals.append(f"ARR_TERMINATOR")
            elif BI:
                vals.append("BANK_INDEX(0x{:X}, 0x{:X})".format(a.bank, a.index))
            elif a:
                # ptrs have to be in bank 4 (really applied to entry pts)
                if a & 0x04000000 == 0x04000000:
                    vals.append(f"{ptr_format}{a:X}")
                else:
                    vals.append(f"0x{a:X}")
            else:
                vals.append("NULL")
        return f"{', '.join( vals )}"

    # given an array, create a recursive set of lines until no more
    # iteration is possible
    def format_iter(self, arr: Sequence, func: callable, name: str, file: KCS_Cdata, depth=(), **kwargs):
        if hasattr(arr[0], "__iter__"):
            arr = [self.format_iter(a, func, name, file, depth=(*depth, len(a)), **kwargs) for a in arr]
            depth = arr[0][1]
            arr = [f"{{{a[0]}}}" for a in arr]
        return func(arr, name, file, **kwargs), depth

    # write generic array, use recursion to unroll all loops
    def write_arr(
        self,
        file: KCS_Cdata,
        arr_format: str,
        name: str,
        arr: Sequence,
        func: callable,
        length=None,
        outer_only=False,
        **kwargs,
    ):
        # use array formatter func
        arr_insides, depth = self.format_iter(arr, func, name, file, **kwargs)
        # set symbol if obj is a ptr target
        self.ptr_obj(arr, file, f"&{name}")
        # create array size initializer, handles everything but outermost dimension
        arr_size_init = "".join([f"[{length}]" for length in depth]) * (not outer_only)
        self.add_header(file, arr_format, f"{name}{arr_size_init}[{self.write_truthy(length)}]")
        file.write(f"{arr_format} {name}{arr_size_init}[{self.write_truthy(length)}] = {{\n\t")
        file.write(arr_insides)
        file.write("\n};\n\n")

    # write if val exists else return nothing
    def write_truthy(self, val):
        if val:
            return val
        return ""

    # create pointer only if val exists
    def pointer_truty(self, val, **kwargs):
        if val:
            return self.add_target(val, **kwargs)
        return 0

    # sort a dict by keys, useful for making sure DLs are in mem order
    # instead of being in referenced order
    def SortDict(self, dictionary):
        return {k: dictionary[k] for k in sorted(dictionary.keys())}

    # write an array of a class with its own to_c method
    def write_class_arr(
        self,
        file: "filestream write",
        class_arr: object,
        prototype: str,
        name: str,
        length=None,
    ):
        # set symbol if obj is a ptr target
        self.ptr_obj(class_arr, file, f"&{name}")
        self.add_header(file, f"struct {prototype}", f"{name}[{self.write_truthy(length)}]")
        file.write(f"struct {prototype} {name}[{self.write_truthy(length)}] = {{\n")
        [cls.to_c(file) for cls in class_arr]
        file.write("};\n\n")

    # write a struct from a python dictionary
    def write_dict_struct(
        self,
        struct_dat: object,
        struct_format: dict,
        file: "filestream write",
        prototype: str,
        name: str,
        align="",
    ):
        # set symbol if obj is a ptr target
        self.ptr_obj(struct_dat, file, f"&{name}")
        self.add_header(file, f"struct {prototype}", name)
        file.write(f"{self.write_truthy(align)}struct {prototype} {name} = {{\n")
        for x, y, z in zip(struct_format.values(), struct_dat.dat, struct_format.keys()):
            # x is (data type, string name, is arr/ptr etc.)
            # y is the actual variable value
            # z is the struct hex offset
            try:
                arr = "arr" in x[2] and hasattr(y, "__iter__")
            except:
                arr = 0
            try:
                ptrs = "ptr" in x[2]
            except:
                ptrs = 0
            if ptrs:
                value = y if y else "NULL"
                if value == "NULL":
                    file.write(f"\t/* 0x{z:X} {x[1]}*/\t{value},\n")
                else:
                    if arr and is_arr(value):
                        value = ", ".join(y)
                        file.write(f"\t/* 0x{z:X} {x[1]}*/\t{{{value}}},\n")
                    else:
                        file.write(f"\t/* 0x{z:X} {x[1]}*/\t{y},\n")
                continue
            if "f32" in x[0] and arr:
                value = ", ".join([f"{a}" for a in y])
                file.write(f"\t/* 0x{z:X} {x[1]}*/\t{{{value}}},\n")
                continue
            if "f32" in x[0]:
                file.write(f"\t/* 0x{z:X} {x[1]}*/\t{y},\n")
            elif arr:
                value = ", ".join([hex(a) for a in y])
                file.write(f"\t/* 0x{z:X} {x[1]}*/\t{{{value}}},\n")
            else:
                file.write(f"\t/* 0x{z:X} {x[1]}*/\t0x{y:X},\n")
        file.write("};\n\n")


# singleton for breakable block, I don't think this actually works across sessions
# I'll probably get rid of this later, not a fan of this structure
class BreakableBlockDat:
    _instance = None
    _Gfx_mat = None
    _Col_mat = None
    _Col_Mesh = None
    _Gfx_Mesh = None
    _Verts = [
        (-40.0, -40.0, -40.0),
        (-40.0, -40.0, 40.0),
        (-40.0, 40.0, -40.0),
        (-40.0, 40.0, 40.0),
        (40.0, -40.0, -40.0),
        (40.0, -40.0, 40.0),
        (40.0, 40.0, -40.0),
        (40.0, 40.0, 40.0),
    ]
    _GfxTris = [
        (1, 2, 0),
        (3, 6, 2),
        (7, 4, 6),
        (5, 0, 4),
        (6, 0, 2),
        (3, 5, 7),
        (1, 3, 2),
        (3, 7, 6),
        (7, 5, 4),
        (5, 1, 0),
        (6, 4, 0),
        (3, 1, 5),
    ]
    _ColTris = [(3, 6, 2), (5, 0, 4), (6, 0, 2), (3, 5, 7), (3, 7, 6), (5, 1, 0), (6, 4, 0), (3, 1, 5)]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = cls
        return cls._instance

    def Instance_Col(self):
        if self._Col_Mesh:
            return self._Col_Mesh
        else:
            self._Col_Mesh = bpy.data.meshes.new("KCS Block Col")
            self._Col_Mesh.from_pydata(self._Verts, [], self._ColTris)
            return self._Col_Mesh

    def Instance_Gfx(self):
        if self._Gfx_Mesh:
            return self._Gfx_Mesh
        else:
            self._Gfx_Mesh = bpy.data.meshes.new("KCS Block Gfx")
            self._Gfx_Mesh.from_pydata(self._Verts, [], self._GfxTris)
            return self._Gfx_Mesh

    def Instance_Mat_Gfx(self, obj: bpy.types.Object):
        if self._Gfx_mat:
            return self._Gfx_mat
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.create_f3d_mat()
        self._Gfx_mat = self._Gfx_Mesh.materials[-1]
        self._Gfx_mat.f3d_mat.combiner1.D = "TEXEL0"
        self._Gfx_mat.f3d_mat.combiner1.D_alpha = "1"
        return self._Gfx_mat

    def Instance_Mat_Col(self, obj: bpy.types.Object):
        if self._Col_mat:
            return self._Col_mat
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.create_f3d_mat()
        self._Col_mat = self._Col_Mesh.materials[-1]
        self._Col_mat.KCS_col.ColType = 9
        return self._Col_mat


# ------------------------------------------------------------------------
#    Importer
# ------------------------------------------------------------------------


def parse_stage_table(world: int, level: int, area: int, path: Path):
    f = open(path, "r")
    lines = f.readlines()
    StageArea = pre_process_c(lines, "StageArea", ["{", "}"])  # data type StageArea, delimiter {}

    # There should a ptr to stages, and then a list of stages in the same file
    levels = None
    for k, v in StageArea.items():
        if "*" in k:
            levels = v
            StageArea.pop(k)
            break
    else:
        raise PluginError("Could not find level stage table")
    for a, w in enumerate(levels):
        levels = w.split(",")
        if a != world - 1:
            continue
        cnt = 0  # use a counter becuase I don't trust that each line is actually a ptr
        for l in levels:
            start = l.find("&")  # these are ptrs
            end = l.find("]")  # if it returns -1 array slicing still work
            ptr = l[start : end + 1]
            if ptr:
                cnt += 1
                if cnt == level:
                    break
        else:
            raise PluginError("could not find level selected")
        break
    # ptr is now going to tell me what var I need
    index = int(ptr[ptr.find("[") + 1 : ptr.find("]")]) + area - 1
    ptr = ptr[1 : ptr.find("[")]

    # I don't check for STAGE_TERMINATOR, so insert that now
    cnt = 0  # when I insert, I increase length by 1
    for i, s in enumerate(StageArea[ptr].copy()):
        if "STAGE_TERMINATOR" in s:
            StageArea[ptr].insert(i + cnt, "{{0}, {0), 0, 0, 0, {0}, 0, 0, {0}, {0}, 0}")
            cnt += 1
    try:
        area = StageArea[ptr][int(index)]
    except:
        raise PluginError("Could not find area within levels")

    # process the area
    macros = {"LIST_INDEX": BANK_INDEX, "BANK_INDEX": BANK_INDEX}
    stage_dict = {
        "geo": tuple,
        "geo2": tuple,
        "skybox": int,
        "color": int,
        "music": int,
        "level_block": tuple,
        "cutscene": int,
        "level_type": str,
        "dust_block": tuple,
        "dust_image": tuple,
        "name": None,
    }
    area = process_struct(stage_dict, macros, area[area.find("{") + 1 : area.rfind("}")])
    return area


# ------------------------------------------------------------------------
#    Macro Unrollers + common regex
# ------------------------------------------------------------------------


def CURLYBRACE_REGX():
    return "\{[0-9,a-fx ]+\}"


def PAREN_REGX():
    return "\([0-9,a-fx ]+\)"


def BANK_INDEX(args: any):
    return f"{{ {args} }}"


# ------------------------------------------------------------------------
#    Helper Functions
# ------------------------------------------------------------------------


def is_arr(val):
    if type(val) == str:
        return False
    if hasattr(val, "__iter__"):
        return True
    return False


def apply_rotation_n64_to_bpy(obj: bpy.types.Object):
    rot = obj.rotation_euler
    rot[0] += math.radians(90)
    obj.rotation_euler = rotate_quat_n64_to_blender(rot.to_quaternion()).to_euler("XYZ")
    apply_objects_modifiers_and_transformations([obj])
    return obj


def apply_rotation_bpy_to_n64(obj: bpy.types.Object):
    rot = obj.rotation_euler
    rot[0] -= math.radians(90)
    obj.rotation_euler = rotate_quat_blender_to_n64(rot.to_quaternion()).to_euler("XYZ")
    apply_objects_modifiers_and_transformations([obj])
    return obj


def make_empty(name: str, displayEnum: str, collection: bpy.types.Collection):
    Obj = bpy.data.objects.new(name, None)
    Obj.empty_display_type = displayEnum
    collection.objects.link(Obj)
    return Obj


def make_mesh_obj(name: str, data: bpy.types.Mesh, collection: bpy.types.Collection):
    Obj = bpy.data.objects.new(name, data)
    collection.objects.link(Obj)
    return Obj


def make_mesh_data(name: str, data: tuple("vertices", "edges", "triangles")):
    dat = bpy.data.meshes.new(name)
    dat.from_pydata(*data)
    dat.validate()
    return dat


# a struct may have various data types inside of it, so this is here to split it when provided a struct dict
# also has support for macros, so it will unroll them given a list of macro defs, otherwise will return as is

# this will only do one value, which is a string representation of the struct, use list comp for an array of structs

# struct dict will contain names of the args, and values of this dict will tell me the delims via regex, recursion using dicts
def process_struct(struct_dict: dict[str, type], macros: dict[str, callable], value: str):
    # first unroll macros as they have internal commas
    for k, v in macros.items():
        if k in value:
            value = process_macro(value, k, v)
    res = {}
    for k, v in struct_dict.items():
        # if None take the rest of the string as the end
        if not v:
            res[k] = value
            break
        # get the appropriate regex using the type
        if v == dict:
            # not supported for now, but a sub struct will be found by getting the string between equal number of curly braces
            continue
        if v == tuple:
            regX = f"{CURLYBRACE_REGX()}\s*,"
        if v == int or v == float or v == str:
            regX = ","
        # search through the line until I hit the delim
        m = re.search(regX, value, flags=re.IGNORECASE)
        if m:
            a = value[: m.span()[1]].strip()
            if v == tuple:
                res[k] = tuple(a[a.find("{") + 1 : a.rfind("}")].split(","))
            if v == str:
                res[k] = a[: a.find(",")]
            if v == int or v == float:
                res[k] = eval(a[: a.find(",")])
            value = value[m.span()[1] :].strip()
        else:
            raise PluginError(f"struct parsing failed {value}, attempt {res}")
    return res


# processes a macro and returns its value, not recursive
# line is a line in the file, macro is str of macro, process is a function equiv of macro
def process_macro(line: str, macro: str, process: callable):
    regX = f"{macro}{PAREN_REGX()}"
    args = PAREN_REGX()
    while True:
        m = re.search(regX, line, flags=re.IGNORECASE)
        if not m:
            break
        line = line.replace(m.group(), process(re.search(args, m.group(), flags=re.IGNORECASE).group()[1:-1]))
    return line


# if there are macros, look for scene defs on macros, currently none, so skip them all
def eval_macro(line: str):
    scene = bpy.context.scene
    #    if scene.LevelImp.Version in line:
    #        return False
    #    if scene.LevelImp.Target in line:
    #        return False
    return False


# Given a file of lines, returns a dict of all vars of type 'typeName', and the values are arrays
# chars are the container for types value, () for macros, {} for structs, None for int arrays

# splits data into array using chars, does not recursively do it, only the top level is split
def pre_process_c(lines: list[str], typeName: str, delims: list[str]):
    # Get a dictionary made up with keys=level script names
    # and values as an array of all the cmds inside.
    Vars = {}
    InlineReg = "/\*((?!\*/).)*\*/"  # remove comments
    dat_name = 0
    skip = 0
    for l in lines:
        comment = l.rfind("//")
        # double slash terminates line basically
        if comment:
            l = l[:comment]
        # check for macro
        if "#ifdef" in l:
            skip = eval_macro(l)
        if "#elif" in l:
            skip = eval_macro(l)
        if "#else" in l:
            skip = 0
            continue
        # Now Check for var starts
        regX = "\[[0-9a-fx]*\]"
        match = re.search(regX, l, flags=re.IGNORECASE)
        if typeName in l and re.search(regX, l.lower()) and not skip:
            b = match.span()[0]
            a = l.find(typeName)
            var = l[a + len(typeName) : b].strip()
            Vars[var] = ""
            dat_name = var
            continue
        if dat_name and not skip:
            # remove inline comments from line
            while True:
                m = re.search(InlineReg, l)
                if not m:
                    break
                m = m.span()
                l = l[: m[0]] + l[m[1] :]
            # Check for end of Level Script array
            if "};" in l:
                dat_name = 0
            # Add line to dict
            else:
                Vars[dat_name] += l
    return process_macro_dict_into_lines(Vars, delims)


# given a dict of lines, turns it into a dict with arrays for value of isolated data members
def process_macro_dict_into_lines(varStrings: dict[str, str], delims: list[str]):
    for k, v in varStrings.items():
        v = v.replace("\n", "")
        arr = []
        x = 0
        stack = 0
        buf = ""
        app = 0
        while x < len(v):
            char = v[x]
            if char == delims[0]:
                stack += 1
                app = 1
            if char == delims[1]:
                stack -= 1
            if app == 1 and stack == 0:
                app = 0
                buf += v[x : x + 2]  # get the last parenthesis and comma
                arr.append(buf.strip())
                x += 2
                buf = ""
                continue
            buf += char
            x += 1
        # for when the control flow characters are nothing
        if buf:
            arr.append(buf)
        varStrings[k] = arr
    return varStrings

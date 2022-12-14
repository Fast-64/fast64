# ------------------------------------------------------------------------
#    Header
# ------------------------------------------------------------------------

import bpy

import os, struct, math, re
from mathutils import Vector, Euler, Matrix

from time import time
from pathlib import Path
from ..utility import rotate_quat_blender_to_n64, apply_objects_modifiers_and_transformations, CData

# ------------------------------------------------------------------------
#    Decorators
# ------------------------------------------------------------------------

# time a function
def time_func(func):
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


# maintain duality with file objects, and CData objects
class kcs_Cdata(CData):
    def __init__(self):
        super().__init__()

    def tell(self):
        return 0

    def write(self, content):
        self.source += content


# there can only be one of these per fModel object
# this object will manage pointers throughout data
class PointerManager:
    ptr_targets = dict()
    memoize = None

    def __init__(self):
        PointerManager.memoize = self

    def resolve_obj_id(self, obj, multi):
        if multi:
            return hash((obj, multi))
        else:
            return id(obj)

    # add a pointer target obj to self.ptr_targets, and then return a placeholder object which is filled in after first pass writing
    def add_target(self, obj, multi=None):
        # you can have multiple targets to the same object, so check before making a new Pointer obj
        # though you can also write something multiple times, and only want a pointer to one of those locations
        # so an optional argument is added to bind the specific call to the multi use owner (usually a gfxList)
        ptr = self.ptr_targets.get(self.resolve_obj_id(obj, multi), None)
        if not ptr or multi:
            ptr = Pointer(obj)
            self.ptr_targets[self.resolve_obj_id(obj, multi)] = ptr
        return ptr

    def ptr_obj(self, obj, file, label, multi=None):
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


# generic container for structs
class StructContainer:
    def __init__(self, data):
        self.dat = data


# Placeholder pointer values
class Pointer:
    def __init__(self, obj):
        self.obj = obj
        self.value = 0
        self.location = 0
        self.symbol = "NULL_ptr"

    def __str__(self):
        return f"Pointer_Type.{id(self)}"


# just a base class that holds some binary processing
class BinProcess:
    def upt(self, offset, type, len):
        return struct.unpack(type, self.file[offset : offset + len])

    @staticmethod
    def seg2phys(num):
        if num >> 24 == 4:
            return num & 0xFFFFFF
        else:
            return num

    def get_BI_pairs(self, start, num=9999, stop=(0, 0)):
        pairs = []
        for i in range(num):
            BI = self.upt(start + 4 * i, ">HH", 4)
            pairs.append(BI)
            if stop == BI:
                break
        return pairs

    def get_referece_list(self, start, stop=0):
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

    def write_arr(self, file, name, arr, BI=None, ptr_format="0x"):
        file.write(f"void *{name}[] = {{\n\t")
        vals = []
        for a in arr:
            if a == 0x99999999 or a == (0x9999, 0x9999):
                vals.append(f"ARR_TERMINATOR")
            elif BI:
                vals.append("BANK_INDEX(0x{:X}, 0x{:X})".format(*a))
            elif a:
                # ptrs have to be in bank 4 (really applied to entry pts)
                if a & 0x04000000 == 0x04000000:
                    vals.append(f"{ptr_format}{a:X}")
                else:
                    vals.append(f"0x{a:X}")
            else:
                vals.append("NULL")
        file.write(", ".join(vals))
        file.write("\n};\n\n")

    def SortDict(self, dictionary):
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
    def resolve_ptrs_c(self, file: kcs_Cdata):
        for obj, ptr in self.ptrManager.ptr_targets.items():
            print(f"object {ptr.obj} resolves to: {ptr.symbol}")
            file.source = file.source.replace(str(ptr), ptr.symbol)

    # format arr data
    def format_arr(self, vals, name, file):
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
    def format_arr_ptr(self, arr, name, file, BI=None, ptr_format="0x"):
        vals = []
        for j, a in enumerate(arr):
            # set symbol if obj is a ptr target
            self.ptr_obj(arr, file, f"{name} + j")
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
    def format_iter(self, arr, func, name, file, **kwargs):
        if hasattr(arr[0], "__iter__"):
            arr = [f"{{{self.format_iter(a, func, name, file, **kwargs)}}}" for a in arr]
        return func(arr, name, file, **kwargs)

    # write generic array, use recursion to unroll all loops
    def write_arr(self, file: kcs_Cdata, name, arr, func, **kwargs):
        # set symbol if obj is a ptr target
        self.ptr_obj(arr, file, name)
        file.write(f"{name}[{len(arr)}] = {{\n\t")
        # use array formatter func
        file.write(self.format_iter(arr, func, name, file, **kwargs))
        file.write("\n};\n\n")

    # sort a dict by keys, useful for making sure DLs are in mem order
    # instead of being in referenced order
    def SortDict(self, dictionary):
        return {k: dictionary[k] for k in sorted(dictionary.keys())}

    # write a struct from a python dictionary
    def WriteDictStruct(self, structDat: object, Prototype_dict: dict, file: kcs_Cdata, protype: str, name: str):
        # set symbol if obj is a ptr target
        self.ptr_obj(structDat, file, f"&{name}")
        file.write(f"struct {protype} {name} = {{\n")
        for x, y, z in zip(Prototype_dict.values(), structDat.dat, Prototype_dict.keys()):
            # x is (data type, string name, is arr/ptr etc.)
            # y is the actual variable value
            # z is the struct hex offset
            try:
                arr = "arr" in x[2] and hasattr(y, "__iter__")
            except:
                arr = 0
            if "f32" in x[0] and arr:
                value = ", ".join([f"{a:f}" for a in y])
                file.write(f"\t/* 0x{z:X} {x[1]}*/\t{{{value}}},\n")
                continue
            if "f32" in x[0]:
                file.write(f"\t/* 0x{z:X} {x[1]}*/\t{y:f},\n")
            if "ptr" in x[2]:
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

    def Instance_Mat_Gfx(self, obj):
        if self._Gfx_mat:
            return self._Gfx_mat
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.create_f3d_mat()
        self._Gfx_mat = self._Gfx_Mesh.materials[-1]
        self._Gfx_mat.f3d_mat.combiner1.D = "TEXEL0"
        self._Gfx_mat.f3d_mat.combiner1.D_alpha = "1"
        return self._Gfx_mat

    def Instance_Mat_Col(self, obj):
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


def ParseStageTable(world, level, area, path):
    f = open(path, "r")
    lines = f.readlines()
    StageArea = PreProcessC(lines, "StageArea", ["{", "}"])  # data type StageArea, delimiter {}

    # There should a ptr to stages, and then a list of stages in the same file
    levels = None
    for k, v in StageArea.items():
        if "*" in k:
            levels = v
            StageArea.pop(k)
            break
    else:
        raise Exception("Could not find level stage table")
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
            raise Exception("could not find level selected")
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
        raise Exception("Could not find area within levels")

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
    area = ProcessStruct(stage_dict, macros, area[area.find("{") + 1 : area.rfind("}")])
    return area


# ------------------------------------------------------------------------
#    Macro Unrollers + common regex
# ------------------------------------------------------------------------


def CurlyBraceRegX():
    return "\{[0-9,a-fx ]+\}"


def ParenRegX():
    return "\([0-9,a-fx ]+\)"


def BANK_INDEX(args):
    return f"{{ {args} }}"


# ------------------------------------------------------------------------
#    Helper Functions
# ------------------------------------------------------------------------


def RotateObj_n64_to_bpy(deg, obj, world=0):
    deg = Euler((math.radians(-deg), 0, 0))
    deg = deg.to_quaternion().to_matrix().to_4x4()
    if world:
        obj.matrix_world = obj.matrix_world @ deg
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(rotation=True)
    else:
        obj.matrix_basis = obj.matrix_basis @ deg


def ApplyRotation_n64_to_bpy(obj):
    RotateObj(-90, obj)
    apply_objects_modifiers_and_transformations([obj])


def MakeEmpty(name, type, collection):
    Obj = bpy.data.objects.new(name, None)
    Obj.empty_display_type = type
    collection.objects.link(Obj)
    return Obj


def MakeMeshObj(name, data, collection):
    Obj = bpy.data.objects.new(name, data)
    collection.objects.link(Obj)
    return Obj


def MakeMeshData(name, data):
    dat = bpy.data.meshes.new(name)
    dat.from_pydata(*data)
    dat.validate()
    return dat


# if keep, then it doesn't inherit parent trasnform
def Parent(parent, child, keep=0):
    if not keep:
        child.parent = parent
        child.matrix_local = child.matrix_parent_inverse
    else:
        # idk this is fucked
        child.parent = parent
        child.matrix_world = parent.matrix_world.inverted() * 0.5


# this will take a blender property, its enumprop name, and then return a list of the allowed enums
def GetEnums(prop, enum):
    enumProp = prop.bl_rna.properties.get(enum)
    if enumProp:
        return [item.identifier for item in enumProp.enum_items]


# a struct may have various data types inside of it, so this is here to split it when provided a struct dict
# also has support for macros, so it will unroll them given a list of macro defs, otherwise will return as is

# this will only do one value, use list comp for an array of structs

# struct dict will contain names of the args, and values tell me the delims via regex, recursion using dicts
def ProcessStruct(struct_dict, macros, value):
    # first unroll macros as they have internal commas
    for k, v in macros.items():
        if k in value:
            value = ProcessMacro(value, k, v)
    res = {}
    for k, v in struct_dict.items():
        # if None take the rest of the string as the end
        if not v:
            res[k] = value
            break
        # get the appropriate regex using the type
        if v == dict:
            # not supported for now, but a sub strcut will be found by getting the string between equal number of curly braces
            continue
        if v == tuple:
            regX = f"{CurlyBraceRegX()}\s*,"
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
            raise Exception(f"struct parsing failed {value}, attempt {res}")
    return res


# processes a macro and returns its value, not recursive
# line is line, macro is str of macro, process is a function equiv of macro
def ProcessMacro(line, macro, process):
    regX = f"{macro}{ParenRegX()}"
    args = ParenRegX()
    while True:
        m = re.search(regX, line, flags=re.IGNORECASE)
        if not m:
            break
        line = line.replace(m.group(), process(re.search(args, m.group(), flags=re.IGNORECASE).group()[1:-1]))
    return line


# if there are macros, look for scene defs on macros, currently none, so skip them all
def EvalMacro(line):
    scene = bpy.context.scene
    #    if scene.LevelImp.Version in line:
    #        return False
    #    if scene.LevelImp.Target in line:
    #        return False
    return False


# Given a file of lines, returns a dict of all vars of type 'data_type', and the values are arrays
# chars are the container for types value, () for macros, {} for structs, None for int arrays

# splits data into array using chars, does not recursively do it, only the top level is split
def PreProcessC(lines, data_type, chars):
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
            skip = EvalMacro(l)
        if "#elif" in l:
            skip = EvalMacro(l)
        if "#else" in l:
            skip = 0
            continue
        # Now Check for var starts
        regX = "\[[0-9a-fx]*\]"
        match = re.search(regX, l, flags=re.IGNORECASE)
        if data_type in l and re.search(regX, l.lower()) and not skip:
            b = match.span()[0]
            a = l.find(data_type)
            var = l[a + len(data_type) : b].strip()
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
    return ProcessLine(Vars, chars)


# given a dict of lines, turns it into a dict with arrays for value of isolated data members
def ProcessLine(Vars, chars):
    for k, v in Vars.items():
        v = v.replace("\n", "")
        arr = []
        x = 0
        stack = 0
        buf = ""
        app = 0
        while x < len(v):
            char = v[x]
            if char == chars[0]:
                stack += 1
                app = 1
            if char == chars[1]:
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
        Vars[k] = arr
    return Vars

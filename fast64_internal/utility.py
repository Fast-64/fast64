from pathlib import Path
import bpy, random, string, os, math, traceback, re, os, mathutils, ast, operator
from math import pi, ceil, degrees, radians, copysign
from mathutils import *
from .utility_anim import *
from typing import Callable, Iterable, Any, Optional, Tuple, TypeVar, Union
from bpy.types import UILayout, Scene, World

CollectionProperty = Any  # collection prop as defined by using bpy.props.CollectionProperty


class PluginError(Exception):
    pass


class VertexWeightError(PluginError):
    pass


# default indentation to use when writing to decomp files
indent = " " * 4

geoNodeRotateOrder = "ZXY"
sm64BoneUp = Vector([1, 0, 0])

transform_mtx_blender_to_n64 = lambda: Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))

yUpToZUp = mathutils.Quaternion((1, 0, 0), math.radians(90.0)).to_matrix().to_4x4()

axis_enums = [
    ("X", "X", "X"),
    ("Y", "Y", "Y"),
    ("-X", "-X", "-X"),
    ("-Y", "-Y", "-Y"),
]

enumExportHeaderType = [
    # ('None', 'None', 'Headers are not written'),
    ("Actor", "Actor Data", "Headers are written to a group in actors/"),
    ("Level", "Level Data", "Headers are written to a specific level in levels/"),
]

# bpy.context.mode returns the keys here, while the values are required by bpy.ops.object.mode_set
CONTEXT_MODE_TO_MODE_SET = {
    "PAINT_VERTEX": "VERTEX_PAINT",
    "PAINT_WEIGHT": "WEIGHT_PAINT",
    "PAINT_TEXTURE": "TEXTURE_PAINT",
    "PARTICLE": "PARTICLE_EDIT",
    "EDIT_GREASE_PENCIL": "EDIT_GPENCIL",
}


def get_mode_set_from_context_mode(context_mode: str):
    if context_mode in CONTEXT_MODE_TO_MODE_SET:
        return CONTEXT_MODE_TO_MODE_SET[context_mode]
    elif context_mode.startswith("EDIT"):
        return "EDIT"
    else:
        return context_mode


def isPowerOf2(n):
    return (n & (n - 1) == 0) and n != 0


def log2iRoundDown(n):
    assert n > 0
    return int(math.floor(math.log2(n)))


def log2iRoundUp(n):
    assert n > 0
    return int(math.ceil(math.log2(n)))


def roundDownToPowerOf2(n):
    return 1 << log2iRoundDown(n)


def roundUpToPowerOf2(n):
    return 1 << log2iRoundUp(n)


def getDeclaration(data, name):
    matchResult = re.search("extern\s*[A-Za-z0-9\_]*\s*" + re.escape(name) + "\s*(\[[^;\]]*\])?;\s*", data, re.DOTALL)
    return matchResult


def hexOrDecInt(value: Union[int, str]) -> int:
    if isinstance(value, int):
        return value
    elif "<<" in value:
        i = value.index("<<")
        return hexOrDecInt(value[:i]) << hexOrDecInt(value[i + 2 :])
    elif ">>" in value:
        i = value.index(">>")
        return hexOrDecInt(value[:i]) >> hexOrDecInt(value[i + 2 :])
    elif "x" in value or "X" in value:
        return int(value, 16)
    else:
        return int(value)


def getOrMakeVertexGroup(obj, groupName):
    for group in obj.vertex_groups:
        if group.name == groupName:
            return group
    return obj.vertex_groups.new(name=groupName)


def unhideAllAndGetHiddenState(scene):
    hiddenObjs = []
    for obj in scene.objects:
        if obj.hide_get():
            hiddenObjs.append(obj)

    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.hide_view_clear()

    hiddenLayerCols = []

    layerColStack = [bpy.context.view_layer.layer_collection]
    while layerColStack:
        layerCol = layerColStack.pop(0)
        layerColStack.extend(layerCol.children)

        if layerCol.hide_viewport:
            hiddenLayerCols.append(layerCol)
            layerCol.hide_viewport = False

    hiddenState = (hiddenObjs, hiddenLayerCols)

    return hiddenState


def restoreHiddenState(hiddenState):
    # as returned by unhideAllAndGetHiddenState
    (hiddenObjs, hiddenLayerCols) = hiddenState

    for obj in hiddenObjs:
        obj.hide_set(True)

    for layerCol in hiddenLayerCols:
        layerCol.hide_viewport = True


def readFile(filepath):
    datafile = open(filepath, "r", newline="\n", encoding="utf-8")
    data = datafile.read()
    datafile.close()
    return data


def writeFile(filepath, data):
    datafile = open(filepath, "w", newline="\n", encoding="utf-8")
    datafile.write(data)
    datafile.close()


def checkObjectReference(obj, title):
    if obj.name not in bpy.context.view_layer.objects:
        raise PluginError(
            title + " not in current view layer.\n The object is either in a different view layer or is deleted."
        )


def selectSingleObject(obj: bpy.types.Object):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def parentObject(parent, child):
    bpy.ops.object.select_all(action="DESELECT")

    child.select_set(True)
    parent.select_set(True)
    bpy.context.view_layer.objects.active = parent
    bpy.ops.object.parent_set(type="OBJECT", keep_transform=True)


def getFMeshName(vertexGroup, namePrefix, drawLayer, isSkinned):
    fMeshName = toAlnum(namePrefix + ("_" if namePrefix != "" else "") + vertexGroup)
    if isSkinned:
        fMeshName += "_skinned"
    fMeshName += "_mesh"
    if drawLayer is not None:
        fMeshName += "_layer_" + str(drawLayer)
    return fMeshName


def checkUniqueBoneNames(fModel, name, vertexGroup):
    if name in fModel.meshes:
        raise PluginError(
            vertexGroup
            + " has already been processed. Make "
            + "sure this bone name is unique, even across all switch option "
            + "armatures, and that any integer keys are not strings."
        )


def getGroupIndexFromname(obj, name):
    for group in obj.vertex_groups:
        if group.name == name:
            return group.index
    return None


def getGroupNameFromIndex(obj, index):
    for group in obj.vertex_groups:
        if group.index == index:
            return group.name
    return None


def copyPropertyCollection(oldProp, newProp):
    newProp.clear()
    for item in oldProp:
        newItem = newProp.add()
        if isinstance(item, bpy.types.PropertyGroup):
            copyPropertyGroup(item, newItem)
        elif type(item).__name__ == "bpy_prop_collection_idprop":
            copyPropertyCollection(item, newItem)
        else:
            newItem = item


def copyPropertyGroup(oldProp, newProp):
    for sub_value_attr in oldProp.bl_rna.properties.keys():
        if sub_value_attr == "rna_type":
            continue
        sub_value = getattr(oldProp, sub_value_attr)
        if isinstance(sub_value, bpy.types.PropertyGroup):
            copyPropertyGroup(sub_value, getattr(newProp, sub_value_attr))
        elif type(sub_value).__name__ == "bpy_prop_collection_idprop":
            newCollection = getattr(newProp, sub_value_attr)
            copyPropertyCollection(sub_value, newCollection)
        else:
            setattr(newProp, sub_value_attr, sub_value)


def get_attr_or_property(prop: dict | object, attr: str, newProp: dict | object):
    """Safely get an attribute or old dict property"""
    val = getattr(prop, attr, prop.get(attr))

    # might be a dead enum that needs to be mapped back
    if type(val) is int:
        try:
            newPropDef: bpy.types.Property = newProp.bl_rna.properties[attr]
            if "Enum" in newPropDef.bl_rna.name:  # Should be "Enum Definition"
                # change type hint to proper type
                newPropDef: bpy.types.EnumProperty = newPropDef
                return newPropDef.enum_items[val].identifier
            elif "Bool" in newPropDef.bl_rna.name:  # Should be "Boolean Definition"
                return bool(val)
        except Exception as e:
            pass
    return val


def iter_prop(prop):
    """Return iterable keys or attributes"""
    if isinstance(prop, bpy.types.PropertyGroup):
        return prop.bl_rna.properties.keys()
    elif type(prop).__name__ == "bpy_prop_collection_idprop":
        return prop
    elif type(prop).__name__ == "IDPropertyGroup":
        return prop.keys()

    return prop


def recursiveCopyOldPropertyGroup(oldProp, newProp):
    """Recursively go through an old property group, copying to the new one"""
    for sub_value_attr in iter_prop(oldProp):
        if sub_value_attr == "rna_type":
            continue
        sub_value = get_attr_or_property(oldProp, sub_value_attr, newProp)
        new_value = get_attr_or_property(newProp, sub_value_attr, newProp)

        if isinstance(new_value, bpy.types.PropertyGroup) or type(new_value).__name__ in (
            "bpy_prop_collection_idprop",
            "IDPropertyGroup",
        ):
            newCollection = getattr(newProp, sub_value_attr)
            recursiveCopyOldPropertyGroup(sub_value, newCollection)
        else:
            try:
                setattr(newProp, sub_value_attr, sub_value)
            except Exception as e:
                print(e)


def propertyCollectionEquals(oldProp, newProp):
    if len(oldProp) != len(newProp):
        print("Unequal size: " + str(oldProp) + " " + str(len(oldProp)) + ", " + str(newProp) + str(len(newProp)))
        return False

    equivalent = True
    for i in range(len(oldProp)):
        item = oldProp[i]
        newItem = newProp[i]
        if isinstance(item, bpy.types.PropertyGroup):
            equivalent &= propertyGroupEquals(item, newItem)
        elif type(item).__name__ == "bpy_prop_collection_idprop":
            equivalent &= propertyCollectionEquals(item, newItem)
        else:
            try:
                iterator = iter(item)
            except TypeError:
                isEquivalent = newItem == item
            else:
                isEquivalent = tuple([i for i in newItem]) == tuple([i for i in item])
            if not isEquivalent:
                pass  # print("Not equivalent: " + str(item) + " " + str(newItem))
            equivalent &= isEquivalent

    return equivalent


def propertyGroupEquals(oldProp, newProp):
    equivalent = True
    for sub_value_attr in oldProp.bl_rna.properties.keys():
        if sub_value_attr == "rna_type":
            continue
        sub_value = getattr(oldProp, sub_value_attr)
        if isinstance(sub_value, bpy.types.PropertyGroup):
            equivalent &= propertyGroupEquals(sub_value, getattr(newProp, sub_value_attr))
        elif type(sub_value).__name__ == "bpy_prop_collection_idprop":
            newCollection = getattr(newProp, sub_value_attr)
            equivalent &= propertyCollectionEquals(sub_value, newCollection)
        else:
            newValue = getattr(newProp, sub_value_attr)
            try:
                iterator = iter(newValue)
            except TypeError:
                isEquivalent = newValue == sub_value
            else:
                isEquivalent = tuple([i for i in newValue]) == tuple([i for i in sub_value])

            if not isEquivalent:
                pass  # print("Not equivalent: " + str(sub_value) + " " + str(newValue) + " " + str(sub_value_attr))
            equivalent &= isEquivalent

    return equivalent


def writeCData(data, headerPath, sourcePath):
    sourceFile = open(sourcePath, "w", newline="\n", encoding="utf-8")
    sourceFile.write(data.source)
    sourceFile.close()

    headerFile = open(headerPath, "w", newline="\n", encoding="utf-8")
    headerFile.write(data.header)
    headerFile.close()


def writeCDataSourceOnly(data, sourcePath):
    sourceFile = open(sourcePath, "w", newline="\n", encoding="utf-8")
    sourceFile.write(data.source)
    sourceFile.close()


def writeCDataHeaderOnly(data, headerPath):
    headerFile = open(headerPath, "w", newline="\n", encoding="utf-8")
    headerFile.write(data.header)
    headerFile.close()


class CData:
    def __init__(self):
        self.source = ""
        self.header = ""

    def append(self, other):
        self.source += other.source
        self.header += other.header


class CScrollData(CData):
    """This class contains a list of function names, so that the top level scroll function can call all of them."""

    def __init__(self):
        self.functionCalls: list[str] = []
        """These function names are all called in one top level scroll function."""

        self.topLevelScrollFunc: str = ""
        """This function is the final one that calls all the others."""

        CData.__init__(self)

    def append(self, other):
        if isinstance(other, CScrollData):
            self.functionCalls.extend(other.functionCalls)
        CData.append(self, other)

    def hasScrolling(self):
        return len(self.functionCalls) > 0


def getObjectFromData(data):
    for obj in bpy.data.objects:
        if obj.data == data:
            return obj
    return None


def getTabbedText(text, tabCount):
    return text.replace("\n", "\n" + "\t" * tabCount)


def extendedRAMLabel(layout):
    return
    infoBox = layout.box()
    infoBox.label(text="Be sure to add: ")
    infoBox.label(text='"#define USE_EXT_RAM"')
    infoBox.label(text="to include/segments.h.")
    infoBox.label(text="Extended RAM prevents crashes.")


def getPathAndLevel(is_custom_export, custom_export_path, custom_level_name, level_enum):
    if is_custom_export:
        export_path = bpy.path.abspath(custom_export_path)
        level_name = custom_level_name
    else:
        export_path = bpy.path.abspath(bpy.context.scene.fast64.sm64.decomp_path)
        if level_enum == "Custom":
            level_name = custom_level_name
        else:
            level_name = level_enum
    return export_path, level_name


def findStartBones(armatureObj):
    noParentBones = sorted(
        [
            bone.name
            for bone in armatureObj.data.bones
            if bone.parent is None and (bone.geo_cmd != "SwitchOption" and bone.geo_cmd != "Ignore")
        ]
    )

    if len(noParentBones) == 0:
        raise PluginError(
            "No non switch option start bone could be found "
            + "in "
            + armatureObj.name
            + ". Is this the root armature?"
        )
    else:
        return noParentBones

    if len(noParentBones) == 1:
        return noParentBones[0]
    elif len(noParentBones) == 0:
        raise PluginError(
            "No non switch option start bone could be found "
            + "in "
            + armatureObj.name
            + ". Is this the root armature?"
        )
    else:
        raise PluginError(
            "Too many parentless bones found. Make sure your bone hierarchy starts from a single bone, "
            + 'and that any bones not related to a hierarchy have their geolayout command set to "Ignore".'
        )


def getDataFromFile(filepath):
    if not os.path.exists(filepath):
        raise PluginError('Path "' + filepath + '" does not exist.')
    dataFile = open(filepath, "r", newline="\n")
    data = dataFile.read()
    dataFile.close()
    return data


def saveDataToFile(filepath, data):
    dataFile = open(filepath, "w", newline="\n")
    dataFile.write(data)
    dataFile.close()


def applyBasicTweaks(baseDir):
    if bpy.context.scene.fast64.sm64.force_extended_ram:
        enableExtendedRAM(baseDir)


def enableExtendedRAM(baseDir):
    segmentPath = os.path.join(baseDir, "include/segments.h")

    segmentFile = open(segmentPath, "r", newline="\n")
    segmentData = segmentFile.read()
    segmentFile.close()

    matchResult = re.search("#define\s*USE\_EXT\_RAM", segmentData)

    if not matchResult:
        matchResult = re.search("#ifndef\s*USE\_EXT\_RAM", segmentData)
        if matchResult is None:
            raise PluginError(
                "When trying to enable extended RAM, " + "could not find '#ifndef USE_EXT_RAM' in include/segments.h."
            )
        segmentData = (
            segmentData[: matchResult.start(0)] + "#define USE_EXT_RAM\n" + segmentData[matchResult.start(0) :]
        )

        segmentFile = open(segmentPath, "w", newline="\n")
        segmentFile.write(segmentData)
        segmentFile.close()


def writeMaterialHeaders(exportDir, matCInclude, matHInclude):
    writeIfNotFound(os.path.join(exportDir, "src/game/materials.c"), "\n" + matCInclude, "")
    writeIfNotFound(os.path.join(exportDir, "src/game/materials.h"), "\n" + matHInclude, "#endif")


def writeMaterialFiles(
    exportDir, assetDir, headerInclude, matHInclude, headerDynamic, dynamic_data, geoString, customExport
):
    if not customExport:
        writeMaterialBase(exportDir)
    levelMatCPath = os.path.join(assetDir, "material.inc.c")
    levelMatHPath = os.path.join(assetDir, "material.inc.h")

    levelMatCFile = open(levelMatCPath, "w", newline="\n")
    levelMatCFile.write(dynamic_data)
    levelMatCFile.close()

    headerDynamic = headerInclude + "\n\n" + headerDynamic
    levelMatHFile = open(levelMatHPath, "w", newline="\n")
    levelMatHFile.write(headerDynamic)
    levelMatHFile.close()

    return matHInclude + "\n\n" + geoString


def writeMaterialBase(baseDir):
    matHPath = os.path.join(baseDir, "src/game/materials.h")
    if not os.path.exists(matHPath):
        matHFile = open(matHPath, "w", newline="\n")

        # Write material.inc.h
        matHFile.write("#ifndef MATERIALS_H\n" + "#define MATERIALS_H\n\n" + "#endif")

        matHFile.close()

    matCPath = os.path.join(baseDir, "src/game/materials.c")
    if not os.path.exists(matCPath):
        matCFile = open(matCPath, "w", newline="\n")
        matCFile.write(
            '#include "types.h"\n'
            + '#include "rendering_graph_node.h"\n'
            + '#include "object_fields.h"\n'
            + '#include "materials.h"'
        )

        # Write global texture load function here
        # Write material.inc.c
        # Write update_materials

        matCFile.close()


def getRGBA16Tuple(color):
    return (
        ((int(round(color[0] * 0x1F)) & 0x1F) << 11)
        | ((int(round(color[1] * 0x1F)) & 0x1F) << 6)
        | ((int(round(color[2] * 0x1F)) & 0x1F) << 1)
        | (1 if color[3] > 0.5 else 0)
    )


RGB_TO_LUM_COEF = mathutils.Vector([0.2126729, 0.7151522, 0.0721750])


def colorToLuminance(color: mathutils.Color | list[float] | Vector):
    # https://github.com/blender/blender/blob/594f47ecd2d5367ca936cf6fc6ec8168c2b360d0/intern/cycles/render/shader.cpp#L387
    # These coefficients are used by Blender, so we use them as well for parity between Fast64 exports and Blender color conversions
    return RGB_TO_LUM_COEF.dot(color[:3])


def getIA16Tuple(color):
    intensity = colorToLuminance(color[0:3])
    alpha = color[3]
    return (int(round(intensity * 0xFF)) << 8) | int(alpha * 0xFF)


def convertRadiansToS16(value):
    value = math.degrees(value)
    # ??? Why is this negative?
    # TODO: Figure out why this has to be this way
    value = 360 - (value % 360)
    return hex(round(value / 360 * 0xFFFF))


def cast_integer(value: int, bits: int, signed: bool):
    wrap = 1 << bits
    value %= wrap
    return value - wrap if signed and value & (1 << (bits - 1)) else value


to_s16 = lambda x: cast_integer(round(x), 16, True)
radians_to_s16 = lambda d: to_s16(d * 0x10000 / (2 * math.pi))


def int_from_s16(value: int) -> int:
    value &= 0xFFFF
    if value >= 0x8000:
        value -= 0x10000
    return value


def int_from_s16_str(value: str) -> int:
    return int_from_s16(int(value, 0))


def float_from_u16_str(value: str) -> float:
    return float(int(value, 0)) / (2**16)


def decompFolderMessage(layout):
    layout.box().label(text="This will export to your decomp folder.")


def customExportWarning(layout):
    layout.box().label(text="This will not write any headers/dependencies.")


def raisePluginError(operator, exception):
    print(traceback.format_exc())
    if bpy.context.scene.fullTraceback:
        operator.report({"ERROR"}, traceback.format_exc())
    else:
        operator.report({"ERROR"}, str(exception))


def highlightWeightErrors(obj, elements, elementType):
    return  # Doesn't work currently
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.mesh.select_mode(type=elementType)
    bpy.ops.object.mode_set(mode="OBJECT")
    print(elements)
    for element in elements:
        element.select = True


def checkIdentityRotation(obj, rotation, allowYaw):
    rotationDiff = rotation.to_euler()
    if abs(rotationDiff.x) > 0.001 or (not allowYaw and abs(rotationDiff.y) > 0.001) or abs(rotationDiff.z) > 0.001:
        raise PluginError(
            'Box "'
            + obj.name
            + '" cannot have a non-zero world rotation '
            + ("(except yaw)" if allowYaw else "")
            + ", currently at ("
            + str(rotationDiff[0])
            + ", "
            + str(rotationDiff[1])
            + ", "
            + str(rotationDiff[2])
            + ")"
        )


def setOrigin(target, obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply()
    bpy.context.scene.cursor.location = target.location
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    bpy.ops.object.select_all(action="DESELECT")


def checkIfPathExists(filePath):
    if not os.path.exists(filePath):
        raise PluginError(filePath + " does not exist.")


def makeWriteInfoBox(layout):
    writeBox = layout.box()
    writeBox.label(text="Along with header edits, this will write to:")
    return writeBox


def writeBoxExportType(writeBox, headerType, name, levelName, levelOption):
    if headerType == "Actor":
        writeBox.label(text="actors/" + toAlnum(name))
    elif headerType == "Level":
        if levelOption != "Custom":
            levelName = levelOption
        writeBox.label(text="levels/" + toAlnum(levelName) + "/" + toAlnum(name))


def getExportDir(customExport, dirPath, headerType, levelName, texDir, dirName):
    # Get correct directory from decomp base, and overwrite texDir
    if not customExport:
        if headerType == "Actor":
            dirPath = os.path.join(dirPath, "actors")
            texDir = "actors/" + dirName
        elif headerType == "Level":
            dirPath = os.path.join(dirPath, "levels/" + levelName)
            texDir = "levels/" + levelName
    elif not texDir:
        texDir = (Path(dirPath).name / Path(dirName)).as_posix()

    return dirPath, texDir


def overwriteData(headerRegex, name, value, filePath, writeNewBeforeString, isFunction):
    if os.path.exists(filePath):
        dataFile = open(filePath, "r")
        data = dataFile.read()
        dataFile.close()

        matchResult = re.search(
            headerRegex
            + re.escape(name)
            + ("\s*\((((?!\)).)*)\)\s*\{(((?!\}).)*)\}" if isFunction else "\[\]\s*=\s*\{(((?!;).)*);"),
            data,
            re.DOTALL,
        )
        if matchResult:
            data = data[: matchResult.start(0)] + value + data[matchResult.end(0) :]
        else:
            if writeNewBeforeString is not None:
                cmdPos = data.find(writeNewBeforeString)
                if cmdPos == -1:
                    raise PluginError("Could not find '" + writeNewBeforeString + "'.")
                data = data[:cmdPos] + value + "\n" + data[cmdPos:]
            else:
                data += "\n" + value
        dataFile = open(filePath, "w", newline="\n")
        dataFile.write(data)
        dataFile.close()
    else:
        raise PluginError(filePath + " does not exist.")


def writeIfNotFound(filePath, stringValue, footer):
    if os.path.exists(filePath):
        fileData = open(filePath, "r")
        fileData.seek(0)
        stringData = fileData.read()
        fileData.close()
        if stringValue not in stringData:
            if len(footer) > 0:
                footerIndex = stringData.rfind(footer)
                if footerIndex == -1:
                    raise PluginError("Footer " + footer + " does not exist.")
                stringData = stringData[:footerIndex] + stringValue + "\n" + stringData[footerIndex:]
            else:
                stringData += stringValue
            fileData = open(filePath, "w", newline="\n")
            fileData.write(stringData)
        fileData.close()
    else:
        raise PluginError(filePath + " does not exist.")


def deleteIfFound(filePath, stringValue):
    if os.path.exists(filePath):
        fileData = open(filePath, "r")
        fileData.seek(0)
        stringData = fileData.read()
        fileData.close()
        if stringValue in stringData:
            stringData = stringData.replace(stringValue, "")
            fileData = open(filePath, "w", newline="\n")
            fileData.write(stringData)
        fileData.close()


def yield_children(obj: bpy.types.Object):
    yield obj
    if obj.children:
        for o in obj.children:
            yield from yield_children(o)


def store_original_mtx():
    active_obj = bpy.context.view_layer.objects.active
    for obj in yield_children(active_obj):
        # negative scales produce a rotation, we need to remove that since
        # scales will be applied to the transform for each object
        loc, rot, _scale = obj.matrix_local.decompose()
        obj["original_mtx"] = Matrix.LocRotScale(loc, rot, None)


def rotate_bounds(bounds, mtx: mathutils.Matrix):
    return [(mtx @ mathutils.Vector(b)).to_tuple() for b in bounds]


def obj_scale_is_unified(obj):
    """Combine scale values into a set to ensure all values are the same"""
    return len(set(obj.scale)) == 1


def translation_rotation_from_mtx(mtx: mathutils.Matrix):
    """Strip scale from matrix"""
    t, r, _ = mtx.decompose()
    return Matrix.Translation(t) @ r.to_matrix().to_4x4()


def scale_mtx_from_vector(scale: mathutils.Vector):
    return mathutils.Matrix.Diagonal(scale[0:3]).to_4x4()


def copy_object_and_apply(obj: bpy.types.Object, apply_scale=False, apply_modifiers=False):
    if apply_scale or apply_modifiers:
        # it's a unique mesh, use object name
        obj["instanced_mesh_name"] = obj.name

        obj.original_name = obj.name

    obj_copy = obj.copy()
    obj_copy.data = obj_copy.data.copy()

    if apply_modifiers:
        # In order to correctly apply modifiers, we have to go through blender and add the object to the collection, then apply modifiers
        prev_active = bpy.context.view_layer.objects.active
        bpy.context.collection.objects.link(obj_copy)
        obj_copy.select_set(True)
        bpy.context.view_layer.objects.active = obj_copy
        for modifier in obj_copy.modifiers:
            attemptModifierApply(modifier)

        bpy.context.view_layer.objects.active = prev_active

    obj_copy.parent = None
    # reset transformations
    obj_copy.location = mathutils.Vector([0.0, 0.0, 0.0])
    obj_copy.scale = mathutils.Vector([1.0, 1.0, 1.0])
    obj_copy.rotation_quaternion = mathutils.Quaternion([1, 0, 0, 0])

    mtx = transform_mtx_blender_to_n64()
    if apply_scale:
        mtx = mtx @ scale_mtx_from_vector(obj.scale)

    obj_copy.data.transform(mtx)
    # Flag used for finding these temp objects
    obj_copy["temp_export"] = True

    # Override for F3D culling bounds (used in addCullCommand)
    bounds_mtx = transform_mtx_blender_to_n64()
    if apply_scale:
        bounds_mtx = bounds_mtx @ scale_mtx_from_vector(obj.scale)  # apply scale if needed
    obj_copy["culling_bounds"] = rotate_bounds(obj_copy.bound_box, bounds_mtx)


def store_original_meshes(add_warning: Callable[[str], None]):
    """
    - Creates new objects at 0, 0, 0 with shared mesh
    - Original mesh name is saved to each object
    """
    instanced_meshes = set()
    active_obj = bpy.context.view_layer.objects.active
    for obj in yield_children(active_obj):
        if obj.type != "EMPTY":
            has_modifiers = len(obj.modifiers) != 0
            has_uneven_scale = not obj_scale_is_unified(obj)
            shares_mesh = obj.data.users > 1
            can_instance = not has_modifiers and not has_uneven_scale
            should_instance = can_instance and (shares_mesh or obj.scaleFromGeolayout)

            if should_instance:
                # add `_shared_mesh` to instanced name because `obj.data.name` can be the same as object names
                obj["instanced_mesh_name"] = f"{obj.data.name}_shared_mesh"
                obj.original_name = obj.name

                if obj.data.name not in instanced_meshes:
                    instanced_meshes.add(obj.data.name)
                    copy_object_and_apply(obj)
            else:
                if shares_mesh and has_modifiers:
                    add_warning(
                        f'Object "{obj.name}" cannot be instanced due to having modifiers so an extra displaylist will be created. Remove modifiers to allow instancing.'
                    )
                if shares_mesh and has_uneven_scale:
                    add_warning(
                        f'Object "{obj.name}" cannot be instanced due to uneven object scaling and an extra displaylist will be created. Set all scale values to the same value to allow instancing.'
                    )

                copy_object_and_apply(obj, apply_scale=True, apply_modifiers=has_modifiers)
    bpy.context.view_layer.objects.active = active_obj


def get_obj_temp_mesh(obj):
    for o in bpy.data.objects:
        if o.get("temp_export") and o.get("instanced_mesh_name") == obj.get("instanced_mesh_name"):
            return o


def apply_objects_modifiers_and_transformations(allObjs: Iterable[bpy.types.Object]):
    # first apply modifiers so that any objects that affect each other are taken into consideration
    for selectedObj in allObjs:
        bpy.ops.object.select_all(action="DESELECT")
        selectedObj.select_set(True)
        bpy.context.view_layer.objects.active = selectedObj

        for modifier in selectedObj.modifiers:
            attemptModifierApply(modifier)

    # apply transformations now that world space changes are applied
    for selectedObj in allObjs:
        bpy.ops.object.select_all(action="DESELECT")
        selectedObj.select_set(True)
        bpy.context.view_layer.objects.active = selectedObj

        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True, properties=False)


def duplicateHierarchy(obj, ignoreAttr, includeEmpties, areaIndex):
    # Duplicate objects to apply scale / modifiers / linked data
    bpy.ops.object.select_all(action="DESELECT")
    selectMeshChildrenOnly(obj, None, includeEmpties, areaIndex)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.duplicate()
    try:
        tempObj = bpy.context.view_layer.objects.active
        allObjs = bpy.context.selected_objects

        bpy.ops.object.make_single_user(obdata=True)

        apply_objects_modifiers_and_transformations(allObjs)

        for selectedObj in allObjs:
            if ignoreAttr is not None and getattr(selectedObj, ignoreAttr):
                for child in selectedObj.children:
                    bpy.ops.object.select_all(action="DESELECT")
                    child.select_set(True)
                    bpy.context.view_layer.objects.active = child
                    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
                    selectedObj.parent.select_set(True)
                    bpy.context.view_layer.objects.active = selectedObj.parent
                    bpy.ops.object.parent_set(keep_transform=True)
                selectedObj.parent = None
        return tempObj, allObjs
    except Exception as e:
        cleanupDuplicatedObjects(allObjs)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        raise Exception(str(e))


enumSM64PreInlineGeoLayoutObjects = {"Geo ASM", "Geo Branch", "Geo Displaylist", "Custom Geo Command"}


def checkIsSM64PreInlineGeoLayout(sm64_obj_type):
    return sm64_obj_type in enumSM64PreInlineGeoLayoutObjects


enumSM64InlineGeoLayoutObjects = {
    "Geo ASM",
    "Geo Branch",
    "Geo Translate/Rotate",
    "Geo Translate Node",
    "Geo Rotation Node",
    "Geo Billboard",
    "Geo Scale",
    "Geo Displaylist",
    "Custom Geo Command",
}


def checkIsSM64InlineGeoLayout(sm64_obj_type):
    return sm64_obj_type in enumSM64InlineGeoLayoutObjects


enumSM64EmptyWithGeolayout = {"None", "Level Root", "Area Root", "Switch"}


def checkSM64EmptyUsesGeoLayout(sm64_obj_type):
    return sm64_obj_type in enumSM64EmptyWithGeolayout or checkIsSM64InlineGeoLayout(sm64_obj_type)


def selectMeshChildrenOnly(obj, ignoreAttr, includeEmpties, areaIndex):
    checkArea = areaIndex is not None and obj.type == "EMPTY"
    if checkArea and obj.sm64_obj_type == "Area Root" and obj.areaIndex != areaIndex:
        return
    ignoreObj = ignoreAttr is not None and getattr(obj, ignoreAttr)
    isMesh = obj.type == "MESH"
    isEmpty = obj.type == "EMPTY" and includeEmpties and checkSM64EmptyUsesGeoLayout(obj.sm64_obj_type)
    if (isMesh or isEmpty) and not ignoreObj:
        obj.select_set(True)
        obj.original_name = obj.name
    for child in obj.children:
        if checkArea and obj.sm64_obj_type == "Level Root":
            if not (child.type == "EMPTY" and child.sm64_obj_type == "Area Root"):
                continue
        selectMeshChildrenOnly(child, ignoreAttr, includeEmpties, areaIndex)


def cleanupDuplicatedObjects(selected_objects):
    meshData = []
    for selectedObj in selected_objects:
        if selectedObj.type == "MESH":
            meshData.append(selectedObj.data)
    for selectedObj in selected_objects:
        bpy.data.objects.remove(selectedObj)
    for mesh in meshData:
        bpy.data.meshes.remove(mesh)


def cleanupTempMeshes():
    """Delete meshes that have been duplicated for instancing"""
    remove_data = []
    for obj in bpy.data.objects:
        if obj.get("temp_export"):
            remove_data.append(obj.data)
            bpy.data.objects.remove(obj)
        else:
            if obj.get("instanced_mesh_name"):
                del obj["instanced_mesh_name"]
            if obj.get("original_mtx"):
                del obj["original_mtx"]

    for data in remove_data:
        data_type = type(data)
        if data_type == bpy.types.Mesh:
            bpy.data.meshes.remove(data)
        elif data_type == bpy.types.Curve:
            bpy.data.curves.remove(data)


def combineObjects(obj, includeChildren, ignoreAttr, areaIndex):
    obj.original_name = obj.name

    # Duplicate objects to apply scale / modifiers / linked data
    bpy.ops.object.select_all(action="DESELECT")
    if includeChildren:
        selectMeshChildrenOnly(obj, ignoreAttr, False, areaIndex)
    else:
        obj.select_set(True)
    if len(bpy.context.selected_objects) == 0:
        return None, []
    bpy.ops.object.duplicate()
    joinedObj = None
    try:
        # duplicate obj and apply modifiers / make single user
        allObjs = bpy.context.selected_objects
        bpy.ops.object.make_single_user(obdata=True)

        apply_objects_modifiers_and_transformations(allObjs)

        bpy.ops.object.select_all(action="DESELECT")

        # Joining causes orphan data, so we remove it manually.
        meshList = []
        for selectedObj in allObjs:
            selectedObj.select_set(True)
            meshList.append(selectedObj.data)

        joinedObj = bpy.context.selected_objects[0]
        bpy.context.view_layer.objects.active = joinedObj
        joinedObj.select_set(True)
        meshList.remove(joinedObj.data)
        bpy.ops.object.join()
        setOrigin(obj, joinedObj)

        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = joinedObj
        joinedObj.select_set(True)

        # Need to clear parent transform in order to correctly apply transform.
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True, properties=False)
        bpy.context.view_layer.objects.active = joinedObj
        joinedObj.select_set(True)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True, properties=False)

    except Exception as e:
        cleanupDuplicatedObjects(allObjs)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        raise Exception(str(e))

    return joinedObj, meshList


def cleanupCombineObj(tempObj, meshList):
    for mesh in meshList:
        bpy.data.meshes.remove(mesh)
    cleanupDuplicatedObjects([tempObj])
    # obj.select_set(True)
    # bpy.context.view_layer.objects.active = obj


def writeInsertableFile(filepath, dataType, address_ptrs, startPtr, data):
    address = 0
    openfile = open(filepath, "wb")

    # 0-4 - Data Type
    openfile.write(dataType.to_bytes(4, "big"))
    address += 4

    # 4-8 - Data Size
    openfile.seek(address)
    openfile.write(len(data).to_bytes(4, "big"))
    address += 4

    # 8-12 Start Address
    openfile.seek(address)
    openfile.write(startPtr.to_bytes(4, "big"))
    address += 4

    # 12-16 - Number of pointer addresses
    openfile.seek(address)
    openfile.write(len(address_ptrs).to_bytes(4, "big"))
    address += 4

    # 16-? - Pointer address list
    for i in range(len(address_ptrs)):
        openfile.seek(address)
        openfile.write(address_ptrs[i].to_bytes(4, "big"))
        address += 4

    openfile.seek(address)
    openfile.write(data)
    openfile.close()


def colorTo16bitRGBA(color):
    r = int(round(color[0] * 31))
    g = int(round(color[1] * 31))
    b = int(round(color[2] * 31))
    a = 1 if color[3] > 0.5 else 0

    return (r << 11) | (g << 6) | (b << 1) | a


# On 2.83/2.91 the rotate operator rotates in the opposite direction (???)
def getDirectionGivenAppVersion():
    if bpy.app.version[1] == 83 or bpy.app.version[1] == 91:
        return -1
    else:
        return 1


def applyRotation(objList, angle, axis):
    bpy.context.scene.tool_settings.use_transform_data_origin = False
    bpy.context.scene.tool_settings.use_transform_pivot_point_align = False
    bpy.context.scene.tool_settings.use_transform_skip_children = False

    bpy.ops.object.select_all(action="DESELECT")
    for obj in objList:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objList[0]

    direction = getDirectionGivenAppVersion()

    bpy.ops.transform.rotate(value=direction * angle, orient_axis=axis, orient_type="GLOBAL")
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True, properties=False)


def doRotation(angle, axis):
    direction = getDirectionGivenAppVersion()
    bpy.ops.transform.rotate(value=direction * angle, orient_axis=axis, orient_type="GLOBAL")


def getAddressFromRAMAddress(RAMAddress):
    addr = RAMAddress - 0x80000000
    if addr < 0:
        raise PluginError("Invalid RAM address.")
    return addr


def getObjectQuaternion(obj):
    if obj.rotation_mode == "QUATERNION":
        rotation = mathutils.Quaternion(obj.rotation_quaternion)
    elif obj.rotation_mode == "AXIS_ANGLE":
        rotation = mathutils.Quaternion(obj.rotation_axis_angle)
    else:
        rotation = mathutils.Euler(obj.rotation_euler, obj.rotation_mode).to_quaternion()
    return rotation


def tempName(name):
    letters = string.digits
    return name + "_temp" + "".join(random.choice(letters) for i in range(10))


def label_split(layout, name, text):
    split = layout.split(factor=0.5)
    split.label(text=name)
    split.label(text=text)


def enum_label_split(layout, name, data, prop, enumItems):
    split = layout.split(factor=0.5)
    split.label(text=name)
    split.enum_item_name(data, prop, enumItems)


def prop_split(layout, data, field, name, **prop_kwargs):
    split = layout.split(factor=0.5)
    split.label(text=name)
    split.prop(data, field, text="", **prop_kwargs)


def multilineLabel(layout: UILayout, text: str, icon: str = "NONE"):
    layout = layout.column()
    for i, line in enumerate(text.split("\n")):
        r = layout.row()
        r.label(text=line, icon=icon if i == 0 else "NONE")
        r.scale_y = 0.75


def draw_and_check_tab(
    layout: UILayout, data, proprety: str, text: Optional[str] = None, icon: Optional[str] = None
) -> bool:
    row = layout.row(align=True)
    tab = getattr(data, proprety)
    tria_icon = "TRIA_DOWN" if tab else "TRIA_RIGHT"
    if icon is not None:
        row.prop(data, proprety, icon=tria_icon, text="")
    row.prop(data, proprety, icon=tria_icon if icon is None else icon, text=text)
    if tab:
        layout.separator()
    return tab


def run_and_draw_errors(layout: UILayout, func, *args):
    try:
        func(*args)
        return True
    except Exception as e:
        multilineLabel(layout.box(), str(e), "ERROR")
        return False


def path_checks(path: str, empty="Empty path.", doesnt_exist="Path {}does not exist.", include_path=True):
    path_in_error = f'"{path}" ' if include_path else ""
    if path == "":
        raise PluginError(empty)
    elif not os.path.exists(path):
        raise FileNotFoundError(doesnt_exist.format(path_in_error))


def path_ui_warnings(layout: bpy.types.UILayout, path: str, empty="Empty path.", doesnt_exist="Path does not exist."):
    return run_and_draw_errors(layout, path_checks, path, empty, doesnt_exist, False)


def directory_path_checks(
    path: str,
    empty="Empty path.",
    doesnt_exist="Directory {}does not exist.",
    not_a_directory="Path {}is not a folder.",
    include_path=True,
):
    path_checks(path, empty, doesnt_exist, include_path)
    if not os.path.isdir(path):
        raise NotADirectoryError(not_a_directory.format(f'"{path}" ' if include_path else ""))


def directory_ui_warnings(
    layout: bpy.types.UILayout,
    path: str,
    empty="Empty path.",
    doesnt_exist="Directory does not exist.",
    not_a_directory="Path is not a folder.",
):
    return run_and_draw_errors(layout, directory_path_checks, path, empty, doesnt_exist, not_a_directory, False)


def filepath_checks(
    path: str,
    empty="Empty path.",
    doesnt_exist="File {}does not exist.",
    not_a_file="Path {}is not a file.",
    include_path=True,
):
    path_checks(path, empty, doesnt_exist, include_path)
    if not os.path.isfile(path):
        raise IsADirectoryError(not_a_file.format(f'"{path}" ' if include_path else ""))


def filepath_ui_warnings(
    layout: bpy.types.UILayout,
    path: str,
    empty="Empty path.",
    doesnt_exist="File does not exist.",
    not_a_file="Path is not a file.",
):
    return run_and_draw_errors(layout, filepath_checks, path, empty, doesnt_exist, not_a_file, False)


def toAlnum(name, exceptions=[]):
    if name is None or name == "":
        return None
    for i in range(len(name)):
        if not name[i].isalnum() and not name[i] in exceptions:
            name = name[:i] + "_" + name[i + 1 :]
    if name[0].isdigit():
        name = "_" + name
    return name


def get64bitAlignedAddr(address):
    endNibble = hex(address)[-1]
    if endNibble != "0" and endNibble != "8":
        address = ceil(address / 8) * 8
    return address


def getNameFromPath(path, removeExtension=False):
    if path[:2] == "//":
        path = path[2:]
    name = os.path.basename(path)
    if removeExtension:
        name = os.path.splitext(name)[0]
    return toAlnum(name, ["-", "."])


def gammaCorrect(linearColor):
    return list(mathutils.Color(linearColor[:3]).from_scene_linear_to_srgb())


def s_rgb_alpha_1_tuple(linearColor):
    s_rgb = gammaCorrect(linearColor)
    s_rgb.append(1.0)
    return tuple(s for s in s_rgb)


def gammaCorrectValue(linearValue):
    # doesn't need to use `colorToLuminance` since all values are the same
    return mathutils.Color((linearValue, linearValue, linearValue)).from_scene_linear_to_srgb().v


def gammaInverse(sRGBColor):
    return list(mathutils.Color(sRGBColor[:3]).from_srgb_to_scene_linear())


def gammaInverseValue(sRGBValue):
    # doesn't need to use `colorToLuminance` since all values are the same
    return mathutils.Color((sRGBValue, sRGBValue, sRGBValue)).from_srgb_to_scene_linear().v


def exportColor(lightColor):
    return [scaleToU8(value) for value in gammaCorrect(lightColor)]


def get_clean_color(srgb: list, include_alpha=False, round_color=True) -> list:
    return [round(channel, 4) if round_color else channel for channel in list(srgb[: 4 if include_alpha else 3])]


def printBlenderMessage(msgSet, message, blenderOp):
    if blenderOp is not None:
        blenderOp.report(msgSet, message)
    else:
        print(message)


def bytesToInt(value):
    return int.from_bytes(value, "big")


def bytesToHex(value, byteSize=4):
    return format(bytesToInt(value), "#0" + str(byteSize * 2 + 2) + "x")


def bytesToHexClean(value, byteSize=4):
    return format(bytesToInt(value), "0" + str(byteSize * 2) + "x")


def intToHex(value, byteSize=4):
    return format(value, "#0" + str(byteSize * 2 + 2) + "x")


def intToBytes(value, byteSize):
    return bytes.fromhex(intToHex(value, byteSize)[2:])


# byte input
# returns an integer, usually used for file seeking positions
def decodeSegmentedAddr(address, segmentData):
    # print(bytesAsHex(address))
    if address[0] not in segmentData:
        raise PluginError("Segment " + str(address[0]) + " not found in segment list.")
    segmentStart = segmentData[address[0]][0]
    return segmentStart + bytesToInt(address[1:4])


# int input
# returns bytes, usually used for writing new segmented addresses
def encodeSegmentedAddr(address, segmentData):
    segment = getSegment(address, segmentData)
    segmentStart = segmentData[segment][0]

    segmentedAddr = address - segmentStart
    return intToBytes(segment, 1) + intToBytes(segmentedAddr, 3)


def getSegment(address, segmentData):
    for segment, interval in segmentData.items():
        if address in range(*interval):
            return segment

    raise PluginError("Address " + hex(address) + " is not found in any of the provided segments.")


# Position
def readVectorFromShorts(command, offset):
    return [readFloatFromShort(command, valueOffset) for valueOffset in range(offset, offset + 6, 2)]


def readFloatFromShort(command, offset):
    return (
        int.from_bytes(command[offset : offset + 2], "big", signed=True)
        / bpy.context.scene.fast64.sm64.blender_to_sm64_scale
    )


def writeVectorToShorts(command, offset, values):
    for i in range(3):
        valueOffset = offset + i * 2
        writeFloatToShort(command, valueOffset, values[i])


def writeFloatToShort(command, offset, value):
    command[offset : offset + 2] = int(round(value * bpy.context.scene.fast64.sm64.blender_to_sm64_scale)).to_bytes(
        2, "big", signed=True
    )


def convertFloatToShort(value):
    return int(round((value * bpy.context.scene.fast64.sm64.blender_to_sm64_scale)))


def convertEulerFloatToShort(value):
    return int(round(degrees(value)))


# Rotation


# Rotation is stored as a short.
# Zero rotation starts at Z+ on an XZ plane and goes counterclockwise.
# 2**16 - 1 is the last value before looping around again.
def readEulerVectorFromShorts(command, offset):
    return [readEulerFloatFromShort(command, valueOffset) for valueOffset in range(offset, offset + 6, 2)]


def readEulerFloatFromShort(command, offset):
    return radians(int.from_bytes(command[offset : offset + 2], "big", signed=True))


def writeEulerVectorToShorts(command, offset, values):
    for i in range(3):
        valueOffset = offset + i * 2
        writeEulerFloatToShort(command, valueOffset, values[i])


def writeEulerFloatToShort(command, offset, value):
    command[offset : offset + 2] = int(round(degrees(value))).to_bytes(2, "big", signed=True)


def getObjDirectionVec(obj, toExport: bool):
    rotation = getObjectQuaternion(obj)
    if toExport:
        spaceRot = mathutils.Euler((-pi / 2, 0, 0)).to_quaternion()
        rotation = spaceRot @ rotation
    normal = (rotation @ mathutils.Vector((0, 0, 1))).normalized()
    return normal


# convert 32 bit (8888) to 16 bit (5551) color
def convert32to16bitRGBA(oldPixel):
    if oldPixel[3] > 127:
        alpha = 1
    else:
        alpha = 0
    newPixel = (oldPixel[0] >> 3) << 11 | (oldPixel[1] >> 3) << 6 | (oldPixel[2] >> 3) << 1 | alpha
    return newPixel.to_bytes(2, "big")


# convert normalized RGB values to bytes (0-255)
def convertRGB(normalizedRGB):
    return bytearray([int(normalizedRGB[0] * 255), int(normalizedRGB[1] * 255), int(normalizedRGB[2] * 255)])


# convert normalized RGB values to bytes (0-255)
def convertRGBA(normalizedRGBA):
    return bytearray(
        [
            int(normalizedRGBA[0] * 255),
            int(normalizedRGBA[1] * 255),
            int(normalizedRGBA[2] * 255),
            int(normalizedRGBA[3] * 255),
        ]
    )


def vector3ComponentMultiply(a, b):
    return mathutils.Vector((a.x * b.x, a.y * b.y, a.z * b.z))


# Position values are signed shorts.
def convertPosition(position):
    positionShorts = [int(floatValue) for floatValue in position]
    F3DPosition = bytearray(0)
    for shortData in [shortValue.to_bytes(2, "big", signed=True) for shortValue in positionShorts]:
        F3DPosition.extend(shortData)
    return F3DPosition


# UVs in F3D are a fixed point short: s10.5 (hence the 2**5)
# fixed point is NOT exponent+mantissa, it is integer+fraction
def convertUV(normalizedUVs, textureWidth, textureHeight):
    # print(str(normalizedUVs[0]) + " - " + str(normalizedUVs[1]))
    F3DUVs = convertFloatToFixed16Bytes(normalizedUVs[0] * textureWidth) + convertFloatToFixed16Bytes(
        normalizedUVs[1] * textureHeight
    )
    return F3DUVs


def convertFloatToFixed16Bytes(value):
    value *= 2**5
    value = min(max(value, -(2**15)), 2**15 - 1)

    return int(round(value)).to_bytes(2, "big", signed=True)


def convertFloatToFixed16(value):
    return int(round(value * (2**5)))

    # We want support for large textures with 32 bit UVs
    # value *= 2**5
    # value = min(max(value, -2**15), 2**15 - 1)
    # return int.from_bytes(
    # 	int(round(value)).to_bytes(2, 'big', signed = True), 'big')


def scaleToU8(val):
    return min(int(round(val * 0xFF)), 255)


def normToSigned8Vector(normal):
    return [int.from_bytes(int(value * 127).to_bytes(1, "big", signed=True), "big") for value in normal]


def unpackNormalS8(packedNormal: int) -> Tuple[int, int, int]:
    assert isinstance(packedNormal, int) and packedNormal >= 0 and packedNormal <= 0xFFFF
    xo, yo = packedNormal >> 8, packedNormal & 0xFF
    # This is following the instructions in F3DEX3
    x, y = xo & 0x7F, yo & 0x7F
    z = x + y
    zNeg = bool(z & 0x80)
    x2, y2 = x ^ 0x7F, y ^ 0x7F  # this is actually producing 7F - x, 7F - y
    z = z ^ 0x7F  # 7F - x - y; using xor saves an instruction and a register on the RSP
    if zNeg:
        x, y = x2, y2
    x, y = -x if xo & 0x80 else x, -y if yo & 0x80 else y
    z = z - 0x100 if z & 0x80 else z
    assert abs(x) + abs(y) + abs(z) == 127
    return x, y, z


def unpackNormal(packedNormal: int) -> Vector:
    # Convert constant-L1 norm to standard L2 norm
    return Vector(unpackNormalS8(packedNormal)).normalized()


def packNormal(normal: Vector) -> int:
    # Convert standard normal to constant-L1 normal
    assert len(normal) == 3
    l1norm = abs(normal[0]) + abs(normal[1]) + abs(normal[2])
    xo, yo, zo = tuple([int(round(a * 127.0 / l1norm)) for a in normal])
    if abs(xo) + abs(yo) > 127:
        yo = int(math.copysign(127 - abs(xo), yo))
    zo = int(math.copysign(127 - abs(xo) - abs(yo), zo))
    assert abs(xo) + abs(yo) + abs(zo) == 127
    # Pack normals
    xsign, ysign = xo & 0x80, yo & 0x80
    x, y = abs(xo), abs(yo)
    if zo < 0:
        x, y = 0x7F - x, 0x7F - y
    x, y = x | xsign, y | ysign
    packedNormal = x << 8 | y
    # The only error is in the float to int rounding above. The packing and unpacking
    # will precisely restore the original int values.
    assert (xo, yo, zo) == unpackNormalS8(packedNormal)
    return packedNormal


def getRgbNormalSettings(f3d_mat: "F3DMaterialProperty") -> Tuple[bool, bool, bool]:
    rdp_settings = f3d_mat.rdp_settings
    has_packed_normals = bpy.context.scene.f3d_type == "F3DEX3" and rdp_settings.g_packed_normals
    has_rgb = not rdp_settings.g_lighting or has_packed_normals
    has_normal = rdp_settings.g_lighting
    return has_rgb, has_normal, has_packed_normals


def byteMask(data, offset, amount):
    return bitMask(data, offset * 8, amount * 8)


def bitMask(data, offset, amount):
    return (~(-1 << amount) << offset & data) >> offset


def read16bitRGBA(data):
    r = bitMask(data, 11, 5) / ((2**5) - 1)
    g = bitMask(data, 6, 5) / ((2**5) - 1)
    b = bitMask(data, 1, 5) / ((2**5) - 1)
    a = bitMask(data, 0, 1) / ((2**1) - 1)

    return [r, g, b, a]


def join_c_args(args: "list[str]"):
    return ", ".join(args)


def translate_blender_to_n64(translate: mathutils.Vector):
    return transform_mtx_blender_to_n64() @ translate


def rotate_quat_blender_to_n64(rotation: mathutils.Quaternion):
    new_rot = transform_mtx_blender_to_n64() @ rotation.to_matrix().to_4x4() @ transform_mtx_blender_to_n64().inverted()
    return new_rot.to_quaternion()


def all_values_equal_x(vals: Iterable, test):
    return len(set(vals) - set([test])) == 0


def get_blender_to_game_scale(context):
    match context.scene.gameEditorMode:
        case "SM64":
            return context.scene.fast64.sm64.blender_to_sm64_scale
        case "OOT":
            return context.scene.ootBlenderScale
        case "F3D":
            # TODO: (V5) create F3D game editor mode, utilize that scale
            return context.scene.blenderF3DScale
        case _:
            pass
    return context.scene.blenderF3DScale


def get_material_from_context(context: bpy.types.Context):
    """Safely check if the context has a valid material and return it"""
    try:
        if type(getattr(context, "material", None)) == bpy.types.Material:
            return context.material
        return context.material_slot.material
    except:
        return None


def lightDataToObj(lightData):
    for obj in bpy.context.scene.objects:
        if obj.data == lightData:
            return obj
    raise PluginError("A material is referencing a light that is no longer in the scene (i.e. has been deleted).")


def ootGetSceneOrRoomHeader(parent, idx, isRoom):
    # This should be in oot_utility.py, but it is needed in f3d_material.py
    # which creates a circular import. The real problem is that the F3D render
    # settings stuff should be in a place which can import both SM64 and OoT
    # code without circular dependencies.
    if idx < 0:
        raise PluginError("Alternate scene/room header index too low: " + str(idx))
    target = "Room" if isRoom else "Scene"
    altHeaders = getattr(parent, "ootAlternate" + target + "Headers")
    if idx == 0:
        return getattr(parent, "oot" + target + "Header")
    elif 1 <= idx <= 3:
        if idx == 1:
            ret = altHeaders.childNightHeader
        elif idx == 2:
            ret = altHeaders.adultDayHeader
        else:
            ret = altHeaders.adultNightHeader
        return None if ret.usePreviousHeader else ret
    else:
        if idx - 4 >= len(altHeaders.cutsceneHeaders):
            return None
        return altHeaders.cutsceneHeaders[idx - 4]


def ootGetBaseOrCustomLight(prop, idx, toExport: bool, errIfMissing: bool):
    # This should be in oot_utility.py, but it is needed in render_settings.py
    # which creates a circular import. The real problem is that the F3D render
    # settings stuff should be in a place which can import both SM64 and OoT
    # code without circular dependencies.
    assert idx in {0, 1}
    col = getattr(prop, "diffuse" + str(idx))
    dir = (mathutils.Vector((1.0, -1.0, 1.0)) * (1.0 if idx == 0 else -1.0)).normalized()
    if getattr(prop, "useCustomDiffuse" + str(idx)):
        light = getattr(prop, "diffuse" + str(idx) + "Custom")
        if light is None:
            if errIfMissing:
                raise PluginError("Error: Diffuse " + str(idx) + " light object not set in a scene lighting property.")
        else:
            col = tuple(c for c in light.color) + (1.0,)
            lightObj = lightDataToObj(light)
            dir = getObjDirectionVec(lightObj, toExport)
    col = mathutils.Vector(tuple(c for c in col))
    if toExport:
        col, dir = exportColor(col), normToSigned8Vector(dir)
    return col, dir


def getTextureSuffixFromFormat(texFmt):
    # if texFmt == "RGBA16":
    #     return "rgb5a1"
    return texFmt.lower()


def removeComments(text: str):
    # https://stackoverflow.com/a/241506

    def replacer(match: re.Match[str]):
        s = match.group(0)
        if s.startswith("/"):
            return " "  # note: a space and not an empty string
        else:
            return s

    pattern = re.compile(r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"', re.DOTALL | re.MULTILINE)

    return re.sub(pattern, replacer, text)


binOps = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.LShift: operator.lshift,
    ast.RShift: operator.rshift,
    ast.RShift: operator.rshift,
    ast.BitOr: operator.or_,
    ast.BitAnd: operator.and_,
    ast.BitXor: operator.xor,
}


def prop_group_to_json(prop_group, blacklist: list[str] = None, whitelist: list[str] = None):
    blacklist = ["rna_type", "name"] + (blacklist or [])

    def prop_to_json(prop):
        if isinstance(prop, list) or type(prop).__name__ == "bpy_prop_collection_idprop":
            prop = list(prop)
            for index, value in enumerate(prop):
                prop[index] = prop_to_json(value)
            return prop
        elif isinstance(prop, Color):
            return get_clean_color(prop)
        elif hasattr(prop, "to_list"):  # for IDPropertyArray classes
            return prop.to_list()
        elif hasattr(prop, "to_dict"):
            return prop.to_dict()
        else:
            return prop

    data = {}
    for prop in iter_prop(prop_group):
        if prop in blacklist or (whitelist and prop not in whitelist):
            continue
        value = prop_to_json(getattr(prop_group, prop))
        if value is not None:
            data[prop] = value
    return data


def json_to_prop_group(prop_group, data: dict, blacklist: list[str] = None, whitelist: list[str] = None):
    blacklist = ["rna_type", "name"] + (blacklist or [])
    for prop in iter_prop(prop_group):
        if prop in blacklist or (whitelist and prop not in whitelist):
            continue
        default = getattr(prop_group, prop)
        if hasattr(default, "from_dict"):
            default.from_dict(data.get(prop, None))
        else:
            setattr(prop_group, prop, data.get(prop, default))


T = TypeVar("T")
SetOrVal = T | list[T]


def get_first_set_prop(old_loc, old_props: SetOrVal[str]):
    """Pops all old props and returns the first one that is set"""

    def as_set(val: SetOrVal[T]) -> set[T]:
        if isinstance(val, Iterable) and not isinstance(val, str):
            return set(val)
        else:
            return {val}

    result = None
    for old_prop in as_set(old_props):
        old_value = old_loc.pop(old_prop, None)
        if old_value is not None:
            result = old_value
    return result


def upgrade_old_prop(
    new_loc,
    new_prop: str,
    old_loc,
    old_props: SetOrVal[str],
    old_enum: list[str] = None,
    fix_forced_base_16=False,
):
    try:
        new_prop_def = new_loc.bl_rna.properties[new_prop]
        new_prop_value = getattr(new_loc, new_prop)
        assert not old_enum or new_prop_def.type == "ENUM"
        assert not (old_enum and fix_forced_base_16)

        old_value = get_first_set_prop(old_loc, old_props)
        if old_value is None:
            return False

        if new_prop_def.type == "ENUM":
            if isinstance(old_value, str):
                new_enum_options = {enum_item.identifier for enum_item in new_prop_def.enum_items}
                if old_value not in new_enum_options:
                    return False
            elif not isinstance(old_value, int):
                raise ValueError(f"({old_value}) not an int, but {new_prop} is an enum")
            elif old_enum:
                if old_value >= len(old_enum):
                    raise ValueError(f"({old_value}) not in {old_enum}")
                old_value = old_enum[old_value]
            else:
                if old_value >= len(new_prop_def.enum_items):
                    raise ValueError(f"({old_value}) not in {new_prop}´s enum items")
                old_value = new_prop_def.enum_items[old_value].identifier
        elif isinstance(new_prop_value, bpy.types.PropertyGroup):
            recursiveCopyOldPropertyGroup(old_value, new_prop_value)
            print(f"Upgraded {new_prop} from old location {old_loc} with props {old_props} via recursive group copy")
            return True
        elif isinstance(new_prop_value, bpy.types.Collection):
            copyPropertyCollection(old_value, new_prop_value)
            print(f"Upgraded {new_prop} from old location {old_loc} with props {old_props} via collection copy")
            return True
        elif fix_forced_base_16:
            try:
                if not isinstance(old_value, str):
                    raise ValueError(f"({old_value}) not a string")
                old_value = int(old_value, 16)
                if new_prop_def.type == "STRING":
                    old_value = intToHex(old_value)
            except ValueError as exc:
                raise ValueError(f"({old_value}) not a valid base 16 integer") from exc

        if new_prop_def.type == "STRING":
            old_value = str(old_value)
        if getattr(new_loc, new_prop, None) == old_value:
            return False
        setattr(new_loc, new_prop, old_value)
        print(f'{new_prop} set to "{getattr(new_loc, new_prop)}"')
        return True
    except Exception as exc:
        print(f"Failed to upgrade {new_prop} from old location {old_loc} with props {old_props}")
        traceback.print_exc()
        return False


WORLD_WARNING_COUNT = 0


def create_or_get_world(scene: Scene) -> World:
    """
    Given a scene, this function will return:
    - The world selected in the scene if the scene has a selected world.
    - The first world in bpy.data.worlds if the current file has a world. (Which it almost always does because of the f3d nodes library)
    - Create a world named "Fast64" and return it if no world exits.
    This function does not assign any world to the scene.
    """
    global WORLD_WARNING_COUNT
    if scene.world:
        WORLD_WARNING_COUNT = 0
        return scene.world
    elif bpy.data.worlds:
        world: World = bpy.data.worlds.values()[0]
        if WORLD_WARNING_COUNT < 10:
            print(f'No world selected in scene, selected the first one found in this file "{world.name}".')
            WORLD_WARNING_COUNT += 1
        return world
    else:  # Almost never reached because the node library has its own world
        WORLD_WARNING_COUNT = 0
        print(f'No world in this file, creating world named "Fast64".')
        return bpy.data.worlds.new("Fast64")


def set_if_different(owner: object, prop: str, value):
    if getattr(owner, prop) != value:
        setattr(owner, prop, value)


def set_prop_if_in_data(owner: object, prop_name: str, data: dict, data_name: str):
    if data_name in data:
        set_if_different(owner, prop_name, data[data_name])

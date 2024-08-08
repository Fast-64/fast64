import bpy
import math
import os
import re

from ast import parse, Expression, Num, UnaryOp, USub, Invert, BinOp
from mathutils import Vector
from bpy.types import Object
from bpy.utils import register_class, unregister_class
from bpy.types import Object
from typing import Callable, Optional, TYPE_CHECKING, List
from .oot_constants import ootSceneIDToName
from dataclasses import dataclass

from ..utility import (
    PluginError,
    prop_split,
    getDataFromFile,
    saveDataToFile,
    attemptModifierApply,
    setOrigin,
    applyRotation,
    cleanupDuplicatedObjects,
    ootGetSceneOrRoomHeader,
    hexOrDecInt,
    binOps,
)

if TYPE_CHECKING:
    from .scene.properties import OOTBootupSceneOptions


def isPathObject(obj: bpy.types.Object) -> bool:
    return obj.type == "CURVE" and obj.ootSplineProperty.splineType == "Path"


ootSceneDungeons = [
    "bdan",
    "bdan_boss",
    "Bmori1",
    "ddan",
    "ddan_boss",
    "FIRE_bs",
    "ganon",
    "ganontika",
    "ganontikasonogo",
    "ganon_boss",
    "ganon_demo",
    "ganon_final",
    "ganon_sonogo",
    "ganon_tou",
    "gerudoway",
    "HAKAdan",
    "HAKAdanCH",
    "HAKAdan_bs",
    "HIDAN",
    "ice_doukutu",
    "jyasinboss",
    "jyasinzou",
    "men",
    "MIZUsin",
    "MIZUsin_bs",
    "moribossroom",
    "ydan",
    "ydan_boss",
]

ootSceneIndoors = [
    "bowling",
    "daiyousei_izumi",
    "hairal_niwa",
    "hairal_niwa2",
    "hairal_niwa_n",
    "hakasitarelay",
    "hut",
    "hylia_labo",
    "impa",
    "kakariko",
    "kenjyanoma",
    "kokiri_home",
    "kokiri_home3",
    "kokiri_home4",
    "kokiri_home5",
    "labo",
    "link_home",
    "mahouya",
    "malon_stable",
    "miharigoya",
    "nakaniwa",
    "syatekijyou",
    "takaraya",
    "tent",
    "tokinoma",
    "yousei_izumi_tate",
    "yousei_izumi_yoko",
]

ootSceneMisc = [
    "enrui",
    "entra_n",
    "hakaana",
    "hakaana2",
    "hakaana_ouke",
    "hiral_demo",
    "kakariko3",
    "kakusiana",
    "kinsuta",
    "market_alley",
    "market_alley_n",
    "market_day",
    "market_night",
    "market_ruins",
    "shrine",
    "shrine_n",
    "shrine_r",
    "turibori",
]

ootSceneOverworld = [
    "entra",
    "souko",
    "spot00",
    "spot01",
    "spot02",
    "spot03",
    "spot04",
    "spot05",
    "spot06",
    "spot07",
    "spot08",
    "spot09",
    "spot10",
    "spot11",
    "spot12",
    "spot13",
    "spot15",
    "spot16",
    "spot17",
    "spot18",
    "spot20",
]

ootSceneShops = [
    "alley_shop",
    "drag",
    "face_shop",
    "golon",
    "kokiri_shop",
    "night_shop",
    "shop1",
    "zoora",
]

ootSceneTest_levels = [
    "besitu",
    "depth_test",
    "sasatest",
    "sutaru",
    "syotes",
    "syotes2",
    "test01",
    "testroom",
]

ootSceneDirs = {
    "assets/scenes/dungeons/": ootSceneDungeons,
    "assets/scenes/indoors/": ootSceneIndoors,
    "assets/scenes/misc/": ootSceneMisc,
    "assets/scenes/overworld/": ootSceneOverworld,
    "assets/scenes/shops/": ootSceneShops,
    "assets/scenes/test_levels/": ootSceneTest_levels,
}


def sceneNameFromID(sceneID):
    if sceneID in ootSceneIDToName:
        return ootSceneIDToName[sceneID]
    else:
        raise PluginError("Cannot find scene ID " + str(sceneID))


def getOOTScale(actorScale: float) -> float:
    return bpy.context.scene.ootBlenderScale * actorScale


@dataclass
class OOTEnum:
    """
    Represents a enum parsed from C code
    """

    name: str
    vals: List[str]

    @staticmethod
    def fromMatch(m: re.Match):
        return OOTEnum(m.group("name"), OOTEnum.parseVals(m.group("vals")))

    @staticmethod
    def parseVals(valsCode: str) -> List[str]:
        return [entry.strip() for entry in ootStripComments(valsCode).split(",")]

    def indexOrNone(self, valueorNone: str):
        return self.vals.index(valueorNone) if valueorNone in self.vals else None


def ootGetEnums(code: str) -> List["OOTEnum"]:
    return [
        OOTEnum.fromMatch(m)
        for m in re.finditer(
            r"(?<!extern)\s*"
            + r"typedef\s*enum\s*(?P<name>[A-Za-z0-9\_]+)"  # doesn't start with extern (is defined here)
            + r"\s*\{"  # typedef enum gDekukButlerLimb
            + r"(?P<vals>[^\}]*)"  # opening curly brace
            + r"\s*\}"  # values
            + r"\s*\1"  # closing curly brace
            + r"\s*;",  # name again  # end statement
            code,
        )
    ]


def replaceMatchContent(data: str, newContent: str, match: re.Match, index: int) -> str:
    return data[: match.start(index)] + newContent + data[match.end(index) :]


def addIncludeFiles(objectName, objectPath, assetName):
    addIncludeFilesExtension(objectName, objectPath, assetName, "h")
    addIncludeFilesExtension(objectName, objectPath, assetName, "c")


def addIncludeFilesExtension(objectName, objectPath, assetName, extension):
    include = '#include "' + assetName + "." + extension + '"\n'
    if not os.path.exists(objectPath):
        raise PluginError(objectPath + " does not exist.")
    path = os.path.join(objectPath, objectName + "." + extension)
    data = getDataFromFile(path)

    if include not in data:
        data += "\n" + include

    # Save this regardless of modification so it will be recompiled.
    saveDataToFile(path, data)


def getSceneDirFromLevelName(name):
    for sceneDir, dirLevels in ootSceneDirs.items():
        if name in dirLevels:
            return sceneDir + name
    return None


def ootStripComments(code: str) -> str:
    code = re.sub(r"\/\*[^*]*\*+(?:[^/*][^*]*\*+)*\/", "", code)  # replace /* ... */ comments
    # TODO: replace end of line (// ...) comments
    return code


@dataclass
class ExportInfo:
    """Contains all parameters used for a scene export. Any new parameters for scene export should be added here."""

    isCustomExportPath: bool
    """Whether or not we are exporting to a known decomp repo"""

    exportPath: str
    """Either the decomp repo root, or a specified custom folder (if ``isCustomExportPath`` is true)"""

    customSubPath: Optional[str]
    """If ``isCustomExportPath``, then this is the relative path used for writing filepaths in files like spec.
    For decomp repos, the relative path is automatically determined and thus this will be ``None``."""

    name: str
    """ The name of the scene, similar to the folder names of scenes in decomp.
    If ``option`` is not "Custom", then this is usually overriden by the name derived from ``option`` before being passed in."""

    option: str
    """ The scene enum value that we are exporting to (can be Custom)"""

    saveTexturesAsPNG: bool
    """ Whether to write textures as C data or as .png files."""

    isSingleFile: bool
    """ Whether to export scene files as a single file or as multiple."""

    useMacros: bool
    """ Whether to use macros or numeric/binary representations of certain values."""

    hackerootBootOption: "OOTBootupSceneOptions"
    """ Options for setting the bootup scene in HackerOoT."""


@dataclass
class RemoveInfo:
    """Contains all parameters used for a scene removal."""

    exportPath: str
    """The path to the decomp repo root"""

    customSubPath: Optional[str]
    """The relative path to the scene directory, if a custom scene is being removed"""

    name: str
    """The name of the level to remove"""


class OOTObjectCategorizer:
    def __init__(self):
        self.sceneObj = None
        self.roomObjs = []
        self.actors = []
        self.transitionActors = []
        self.meshes = []
        self.entrances = []
        self.waterBoxes = []

    def sortObjects(self, allObjs):
        for obj in allObjs:
            if obj.type == "EMPTY":
                if obj.ootEmptyType == "Actor":
                    self.actors.append(obj)
                elif obj.ootEmptyType == "Transition Actor":
                    self.transitionActors.append(obj)
                elif obj.ootEmptyType == "Entrance":
                    self.entrances.append(obj)
                elif obj.ootEmptyType == "Water Box":
                    self.waterBoxes.append(obj)
                elif obj.ootEmptyType == "Room":
                    self.roomObjs.append(obj)
                elif obj.ootEmptyType == "Scene":
                    self.sceneObj = obj
            elif obj.type == "MESH":
                self.meshes.append(obj)


# This also sets all origins relative to the scene object.
def ootDuplicateHierarchy(obj, ignoreAttr, includeEmpties, objectCategorizer) -> tuple[Object, list[Object]]:
    # Duplicate objects to apply scale / modifiers / linked data
    bpy.ops.object.select_all(action="DESELECT")
    ootSelectMeshChildrenOnly(obj, includeEmpties)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.duplicate()
    try:
        tempObj = bpy.context.view_layer.objects.active
        allObjs = bpy.context.selected_objects
        bpy.ops.object.make_single_user(obdata=True)

        objectCategorizer.sortObjects(allObjs)
        meshObjs = objectCategorizer.meshes
        bpy.ops.object.select_all(action="DESELECT")
        for selectedObj in meshObjs:
            selectedObj.select_set(True)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True, properties=False)

        for selectedObj in meshObjs:
            bpy.ops.object.select_all(action="DESELECT")
            selectedObj.select_set(True)
            bpy.context.view_layer.objects.active = selectedObj
            for modifier in selectedObj.modifiers:
                attemptModifierApply(modifier)
        for selectedObj in meshObjs:
            setOrigin(obj, selectedObj)
        if ignoreAttr is not None:
            for selectedObj in meshObjs:
                if getattr(selectedObj, ignoreAttr):
                    for child in selectedObj.children:
                        bpy.ops.object.select_all(action="DESELECT")
                        child.select_set(True)
                        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
                        selectedObj.parent.select_set(True)
                        bpy.ops.object.parent_set(keep_transform=True)
                    selectedObj.parent = None

        # Assume objects with these types of constraints are parented, and are
        # intended to be parented in-game, i.e. rendered as an extra DL alongside
        # a skeletal mesh, e.g. for a character to be wearing or holding it.
        # In this case we purely want the transformation of the object relative
        # to whatever it's parented to. Getting rid of the constraint and then
        # doing transform_apply() sets up this transformation.
        hasConstraint = False
        for constraint in tempObj.constraints:
            if (
                constraint.type
                in {
                    "COPY_LOCATION",
                    "COPY_ROTATION",
                    "COPY_SCALE",
                    "COPY_TRANSFORMS",
                    "TRANSFORM",
                    "CHILD_OF",
                    "CLAMP_TO",
                    "DAMPED_TRACK",
                    "LOCKED_TRACK",
                    "TRACK_TO",
                }
                and not constraint.mute
            ):
                hasConstraint = True
                tempObj.constraints.remove(constraint)
        if not hasConstraint:
            # For normal objects, the game's coordinate system is 90 degrees
            # away from Blender's.
            applyRotation([tempObj], math.radians(90), "X")
        else:
            # This is a relative transform we care about so the 90 degrees
            # doesn't matter (since they're both right-handed).
            print("Applying transform")
            bpy.ops.object.select_all(action="DESELECT")
            tempObj.select_set(True)
            bpy.context.view_layer.objects.active = tempObj
            bpy.ops.object.transform_apply()

        return tempObj, allObjs
    except Exception as e:
        cleanupDuplicatedObjects(allObjs)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        raise Exception(str(e))


def ootSelectMeshChildrenOnly(obj, includeEmpties):
    isMesh = obj.type == "MESH"
    isEmpty = (obj.type == "EMPTY" or obj.type == "CAMERA" or obj.type == "CURVE") and includeEmpties
    if isMesh or isEmpty:
        obj.select_set(True)
        obj.original_name = obj.name
    for child in obj.children:
        ootSelectMeshChildrenOnly(child, includeEmpties)


def ootCleanupScene(originalSceneObj, allObjs):
    cleanupDuplicatedObjects(allObjs)
    originalSceneObj.select_set(True)
    bpy.context.view_layer.objects.active = originalSceneObj


def getSceneObj(obj):
    while not (obj is None or (obj is not None and obj.type == "EMPTY" and obj.ootEmptyType == "Scene")):
        obj = obj.parent
    if obj is None:
        return None
    else:
        return obj


def getRoomObj(obj):
    while not (obj is None or (obj is not None and obj.type == "EMPTY" and obj.ootEmptyType == "Room")):
        obj = obj.parent
    if obj is None:
        return None
    else:
        return obj


def checkEmptyName(name):
    if name == "":
        raise PluginError("No name entered for the exporter.")


def ootGetObjectPath(isCustomExport: bool, exportPath: str, folderName: str) -> str:
    if isCustomExport:
        filepath = exportPath
    else:
        filepath = os.path.join(
            ootGetPath(exportPath, isCustomExport, "assets/objects/", folderName, False, False), folderName + ".c"
        )
    return filepath


def ootGetObjectHeaderPath(isCustomExport: bool, exportPath: str, folderName: str) -> str:
    if isCustomExport:
        filepath = exportPath
    else:
        filepath = os.path.join(
            ootGetPath(exportPath, isCustomExport, "assets/objects/", folderName, False, False), folderName + ".h"
        )
    return filepath


def ootGetPath(exportPath, isCustomExport, subPath, folderName, makeIfNotExists, useFolderForCustom):
    if isCustomExport:
        path = bpy.path.abspath(os.path.join(exportPath, (folderName if useFolderForCustom else "")))
    else:
        if bpy.context.scene.ootDecompPath == "":
            raise PluginError("Decomp base path is empty.")
        path = bpy.path.abspath(os.path.join(os.path.join(bpy.context.scene.ootDecompPath, subPath), folderName))

    if not os.path.exists(path):
        if isCustomExport or makeIfNotExists:
            os.makedirs(path)
        else:
            raise PluginError(path + " does not exist.")

    return path


def getSortedChildren(armatureObj, bone):
    return sorted(
        [child.name for child in bone.children if child.ootBone.boneType != "Ignore"],
        key=lambda childName: childName.lower(),
    )


def getStartBone(armatureObj):
    startBoneNames = [
        bone.name for bone in armatureObj.data.bones if bone.parent is None and bone.ootBone.boneType != "Ignore"
    ]
    if len(startBoneNames) == 0:
        raise PluginError(armatureObj.name + ' does not have any root bones that are not of the "Ignore" type.')
    startBoneName = startBoneNames[0]
    return startBoneName
    # return 'root'


def getNextBone(boneStack: list[str], armatureObj: bpy.types.Object):
    if len(boneStack) == 0:
        raise PluginError("More bones in animation than on armature.")
    bone = armatureObj.data.bones[boneStack[0]]
    boneStack = boneStack[1:]
    boneStack = getSortedChildren(armatureObj, bone) + boneStack
    return bone, boneStack


def checkForStartBone(armatureObj):
    pass
    # if "root" not in armatureObj.data.bones:
    # 	raise PluginError("Skeleton must have a bone named 'root' where the skeleton starts from.")


class BoxEmpty:
    def __init__(self, position, scale, emptyScale):
        # The scale ordering is due to the fact that scaling happens AFTER rotation.
        # Thus the translation uses Y-up, while the scale uses Z-up.
        self.low = (position[0] - scale[0] * emptyScale, position[2] - scale[1] * emptyScale)
        self.high = (position[0] + scale[0] * emptyScale, position[2] + scale[1] * emptyScale)
        self.height = position[1] + scale[2] * emptyScale

        self.low = [int(round(value)) for value in self.low]
        self.high = [int(round(value)) for value in self.high]
        self.height = int(round(self.height))


def checkUniformScale(scale, obj):
    if abs(scale[0] - scale[1]) > 0.01 or abs(scale[1] - scale[2]) > 0.01 or abs(scale[0] - scale[2]) > 0.01:
        raise PluginError("Cull group " + obj.name + " must have a uniform scale.")


class CullGroup:
    def __init__(self, position, scale, emptyScale):
        self.position = [int(round(field)) for field in position]
        self.cullDepth = abs(int(round(scale[0] * emptyScale)))


def setCustomProperty(data: any, prop: str, value: str, enumList: list[tuple[str, str, str]] | None):
    if enumList is not None:
        if value in [enumItem[0] for enumItem in enumList]:
            setattr(data, prop, value)
            return
        else:
            try:
                numberValue = hexOrDecInt(value)
                hexValue = f'0x{format(numberValue, "02X")}'
                if hexValue in [enumItem[0] for enumItem in enumList]:
                    setattr(data, prop, hexValue)
                    return
            except ValueError:
                pass

    setattr(data, prop, "Custom")
    setattr(data, prop + str("Custom"), value)


def getCustomProperty(data, prop):
    value = getattr(data, prop)
    return value if value != "Custom" else getattr(data, prop + str("Custom"))


def convertIntTo2sComplement(value, length, signed):
    return int.from_bytes(int(round(value)).to_bytes(length, "big", signed=signed), "big")


def drawEnumWithCustom(panel, data, attribute, name, customName):
    prop_split(panel, data, attribute, name)
    if getattr(data, attribute) == "Custom":
        prop_split(panel, data, attribute + "Custom", customName)


def getEnumName(enumItems, value):
    for enumTuple in enumItems:
        if enumTuple[0] == value:
            return enumTuple[1]
    raise PluginError("Could not find enum value " + str(value))


def getEnumIndex(enumItems, value):
    for i, enumTuple in enumerate(enumItems):
        if enumTuple[0] == value or enumTuple[1] == value:
            return i
    return None


def ootConvertTranslation(translation):
    return [int(round(value)) for value in translation]


def ootConvertRotation(rotation):
    # see BINANG_TO_DEGF
    return [int(round((math.degrees(value) % 360) / 360 * (2**16))) % (2**16) for value in rotation.to_euler()]


# parse rotaion in Vec3s format
def ootParseRotation(values: list[int]):
    return [
        math.radians(
            (int.from_bytes(value.to_bytes(2, "big", signed=value < 0x8000), "big", signed=False) / 2**16) * 360
        )
        for value in values
    ]


def getCutsceneName(obj):
    name = obj.name
    if name.startswith("Cutscene."):
        name = name[9:]
    name = name.replace(".", "_")
    return name


def getCollectionFromIndex(obj, prop, subIndex, isRoom):
    header = ootGetSceneOrRoomHeader(obj, subIndex, isRoom)
    return getattr(header, prop)


# Operators cannot store mutable references (?), so to reuse PropertyCollection modification code we do this.
# Save a string identifier in the operator, then choose the member variable based on that.
# subIndex is for a collection within a collection element
def getCollection(objName, collectionType, subIndex):
    obj = bpy.data.objects[objName]
    if collectionType == "Actor":
        collection = obj.ootActorProperty.headerSettings.cutsceneHeaders
    elif collectionType == "Transition Actor":
        collection = obj.ootTransitionActorProperty.actor.headerSettings.cutsceneHeaders
    elif collectionType == "Entrance":
        collection = obj.ootEntranceProperty.actor.headerSettings.cutsceneHeaders
    elif collectionType == "Room":
        collection = obj.ootAlternateRoomHeaders.cutsceneHeaders
    elif collectionType == "Scene":
        collection = obj.ootAlternateSceneHeaders.cutsceneHeaders
    elif collectionType == "Light":
        collection = getCollectionFromIndex(obj, "lightList", subIndex, False)
    elif collectionType == "Exit":
        collection = getCollectionFromIndex(obj, "exitList", subIndex, False)
    elif collectionType == "Object":
        collection = getCollectionFromIndex(obj, "objectList", subIndex, True)
    elif collectionType == "Curve":
        collection = obj.ootSplineProperty.headerSettings.cutsceneHeaders
    elif collectionType.startswith("CSHdr."):
        # CSHdr.HeaderNumber[.ListType]
        # Specifying ListType means uses subIndex
        toks = collectionType.split(".")
        assert len(toks) in [2, 3]
        hdrnum = int(toks[1])
        collection = getCollectionFromIndex(obj, "csLists", hdrnum, False)
        if len(toks) == 3:
            collection = getattr(collection[subIndex], toks[2])
    elif collectionType.startswith("Cutscene."):
        # Cutscene.ListType
        toks = collectionType.split(".")
        assert len(toks) == 2
        collection = obj.ootCutsceneProperty.csLists
        collection = getattr(collection[subIndex], toks[1])
    elif collectionType == "Cutscene":
        collection = obj.ootCutsceneProperty.csLists
    elif collectionType == "extraCutscenes":
        collection = obj.ootSceneHeader.extraCutscenes
    elif collectionType == "BgImage":
        collection = obj.ootRoomHeader.bgImageList
    else:
        raise PluginError("Invalid collection type: " + collectionType)

    return collection


def drawAddButton(layout, index, collectionType, subIndex, objName):
    if subIndex is None:
        subIndex = 0
    addOp = layout.operator(OOTCollectionAdd.bl_idname)
    addOp.option = index
    addOp.collectionType = collectionType
    addOp.subIndex = subIndex
    addOp.objName = objName


def drawCollectionOps(layout, index, collectionType, subIndex, objName, allowAdd=True, compact=False):
    if subIndex is None:
        subIndex = 0

    if not compact:
        buttons = layout.row(align=True)
    else:
        buttons = layout

    if allowAdd:
        addOp = buttons.operator(OOTCollectionAdd.bl_idname, text="Add" if not compact else "", icon="ADD")
        addOp.option = index + 1
        addOp.collectionType = collectionType
        addOp.subIndex = subIndex
        addOp.objName = objName

    removeOp = buttons.operator(OOTCollectionRemove.bl_idname, text="Delete" if not compact else "", icon="REMOVE")
    removeOp.option = index
    removeOp.collectionType = collectionType
    removeOp.subIndex = subIndex
    removeOp.objName = objName

    moveUp = buttons.operator(OOTCollectionMove.bl_idname, text="Up" if not compact else "", icon="TRIA_UP")
    moveUp.option = index
    moveUp.offset = -1
    moveUp.collectionType = collectionType
    moveUp.subIndex = subIndex
    moveUp.objName = objName

    moveDown = buttons.operator(OOTCollectionMove.bl_idname, text="Down" if not compact else "", icon="TRIA_DOWN")
    moveDown.option = index
    moveDown.offset = 1
    moveDown.collectionType = collectionType
    moveDown.subIndex = subIndex
    moveDown.objName = objName


class OOTCollectionAdd(bpy.types.Operator):
    bl_idname = "object.oot_collection_add"
    bl_label = "Add Item"
    bl_options = {"REGISTER", "UNDO"}

    option: bpy.props.IntProperty()
    collectionType: bpy.props.StringProperty(default="Actor")
    subIndex: bpy.props.IntProperty(default=0)
    objName: bpy.props.StringProperty()

    def execute(self, context):
        collection = getCollection(self.objName, self.collectionType, self.subIndex)

        collection.add()
        collection.move(len(collection) - 1, self.option)
        return {"FINISHED"}


class OOTCollectionRemove(bpy.types.Operator):
    bl_idname = "object.oot_collection_remove"
    bl_label = "Remove Item"
    bl_options = {"REGISTER", "UNDO"}

    option: bpy.props.IntProperty()
    collectionType: bpy.props.StringProperty(default="Actor")
    subIndex: bpy.props.IntProperty(default=0)
    objName: bpy.props.StringProperty()

    def execute(self, context):
        collection = getCollection(self.objName, self.collectionType, self.subIndex)
        collection.remove(self.option)
        return {"FINISHED"}


class OOTCollectionMove(bpy.types.Operator):
    bl_idname = "object.oot_collection_move"
    bl_label = "Move Item"
    bl_options = {"REGISTER", "UNDO"}

    option: bpy.props.IntProperty()
    offset: bpy.props.IntProperty()
    subIndex: bpy.props.IntProperty(default=0)
    objName: bpy.props.StringProperty()

    collectionType: bpy.props.StringProperty(default="Actor")

    def execute(self, context):
        collection = getCollection(self.objName, self.collectionType, self.subIndex)
        collection.move(self.option, self.option + self.offset)
        return {"FINISHED"}


def getHeaderSettings(actorObj: bpy.types.Object):
    itemType = actorObj.ootEmptyType
    if actorObj.type == "EMPTY":
        if itemType == "Actor":
            headerSettings = actorObj.ootActorProperty.headerSettings
        elif itemType == "Entrance":
            headerSettings = actorObj.ootEntranceProperty.actor.headerSettings
        elif itemType == "Transition Actor":
            headerSettings = actorObj.ootTransitionActorProperty.actor.headerSettings
        else:
            headerSettings = None
    elif isPathObject(actorObj):
        headerSettings = actorObj.ootSplineProperty.headerSettings
    else:
        headerSettings = None

    return headerSettings


oot_utility_classes = (
    OOTCollectionAdd,
    OOTCollectionRemove,
    OOTCollectionMove,
)


def oot_utility_register():
    for cls in oot_utility_classes:
        register_class(cls)


def oot_utility_unregister():
    for cls in reversed(oot_utility_classes):
        unregister_class(cls)


def getActiveHeaderIndex() -> int:
    # All scenes/rooms should have synchronized tabs from property callbacks
    headerObjs = [obj for obj in bpy.data.objects if obj.ootEmptyType == "Scene" or obj.ootEmptyType == "Room"]
    if len(headerObjs) == 0:
        return 0

    headerObj = headerObjs[0]
    if headerObj.ootEmptyType == "Scene":
        header = headerObj.ootSceneHeader
        altHeader = headerObj.ootAlternateSceneHeaders
    else:
        header = headerObj.ootRoomHeader
        altHeader = headerObj.ootAlternateRoomHeaders

    if header.menuTab != "Alternate":
        headerIndex = 0
    else:
        if altHeader.headerMenuTab == "Child Night":
            headerIndex = 1
        elif altHeader.headerMenuTab == "Adult Day":
            headerIndex = 2
        elif altHeader.headerMenuTab == "Adult Night":
            headerIndex = 3
        else:
            headerIndex = altHeader.currentCutsceneIndex

    return (
        headerIndex,
        altHeader.childNightHeader.usePreviousHeader,
        altHeader.adultDayHeader.usePreviousHeader,
        altHeader.adultNightHeader.usePreviousHeader,
    )


def setAllActorsVisibility(self, context: bpy.types.Context):
    activeHeaderInfo = getActiveHeaderIndex()

    actorObjs = [
        obj
        for obj in bpy.data.objects
        if obj.ootEmptyType in ["Actor", "Transition Actor", "Entrance"] or isPathObject(obj)
    ]

    for actorObj in actorObjs:
        setActorVisibility(actorObj, activeHeaderInfo)


def setActorVisibility(actorObj: bpy.types.Object, activeHeaderInfo: tuple[int, bool, bool, bool]):
    headerIndex, childNightHeader, adultDayHeader, adultNightHeader = activeHeaderInfo
    usePreviousHeader = [False, childNightHeader, adultDayHeader, adultNightHeader]
    if headerIndex < 4:
        while usePreviousHeader[headerIndex]:
            headerIndex -= 1

    headerSettings = getHeaderSettings(actorObj)
    if headerSettings is None:
        return
    if headerSettings.sceneSetupPreset == "All Scene Setups":
        actorObj.hide_set(False)
    elif headerSettings.sceneSetupPreset == "All Non-Cutscene Scene Setups":
        actorObj.hide_set(headerIndex >= 4)
    elif headerSettings.sceneSetupPreset == "Custom":
        actorObj.hide_set(not headerSettings.checkHeader(headerIndex))
    else:
        print("Error: unhandled header case")


def onMenuTabChange(self, context: bpy.types.Context):
    def callback(thisHeader, otherObj: bpy.types.Object):
        if otherObj.ootEmptyType == "Scene":
            header = otherObj.ootSceneHeader
        else:
            header = otherObj.ootRoomHeader

        if thisHeader.menuTab != "Alternate" and header.menuTab == "Alternate":
            header.menuTab = "General"
        if thisHeader.menuTab == "Alternate" and header.menuTab != "Alternate":
            header.menuTab = "Alternate"

    onHeaderPropertyChange(self, context, callback)


def onHeaderMenuTabChange(self, context: bpy.types.Context):
    def callback(thisHeader, otherObj: bpy.types.Object):
        if otherObj.ootEmptyType == "Scene":
            header = otherObj.ootAlternateSceneHeaders
        else:
            header = otherObj.ootAlternateRoomHeaders

        header.headerMenuTab = thisHeader.headerMenuTab
        header.currentCutsceneIndex = thisHeader.currentCutsceneIndex

    onHeaderPropertyChange(self, context, callback)


def onHeaderPropertyChange(self, context: bpy.types.Context, callback: Callable[[any, bpy.types.Object], None]):
    if not bpy.context.scene.fast64.oot.headerTabAffectsVisibility or bpy.context.scene.ootActiveHeaderLock:
        return
    bpy.context.scene.ootActiveHeaderLock = True

    thisHeader = self
    thisObj = context.object
    otherObjs = [
        obj
        for obj in bpy.data.objects
        if (obj.ootEmptyType == "Scene" or obj.ootEmptyType == "Room") and obj != thisObj
    ]

    for otherObj in otherObjs:
        callback(thisHeader, otherObj)

    setAllActorsVisibility(self, context)

    bpy.context.scene.ootActiveHeaderLock = False


def getEvalParams(input: str):
    """Evaluates a string to an hexadecimal number"""

    # degrees to binary angle conversion
    if "DEG_TO_BINANG(" in input:
        input = input.strip().removeprefix("DEG_TO_BINANG(").removesuffix(")").strip()
        return f"0x{round(float(input) * (0x8000 / 180)):X}"

    if input is None or "None" in input:
        return "0x0"

    # remove spaces
    input = input.strip()

    try:
        node = parse(input, mode="eval")
    except Exception as e:
        raise ValueError(f"Could not parse {input} as an AST.") from e

    def _eval(node):
        if isinstance(node, Expression):
            return _eval(node.body)
        elif isinstance(node, Num):
            return node.n
        elif isinstance(node, UnaryOp):
            if isinstance(node.op, USub):
                return -_eval(node.operand)
            elif isinstance(node.op, Invert):
                return ~_eval(node.operand)
            else:
                raise ValueError(f"Unsupported unary operator {node.op}")
        elif isinstance(node, BinOp):
            return binOps[type(node.op)](_eval(node.left), _eval(node.right))
        else:
            raise ValueError(f"Unsupported AST node {node}")

    return f"0x{_eval(node.body):X}"


def getNewPath(type: str, isClosedShape: bool):
    """
    Returns a new Curve Object with the selected spline shape

    Parameters:
    - ``type``: the path's type (square, line, etc)
    - ``isClosedShape``: choose if the spline should have an extra point to make a closed shape
    """

    # create a new curve
    newCurve = bpy.data.curves.new("New Path", "CURVE")
    newCurve.dimensions = "3D"

    # add a new spline to the curve
    newSpline = newCurve.splines.new("NURBS")  # comes with 1 point

    # generate shape based on 'type' parameter
    scaleDivBy2 = bpy.context.scene.ootBlenderScale / 2
    match type:
        case "Line":
            newSpline.points.add(1)
            for i, point in enumerate(newSpline.points):
                point.co.x = i * bpy.context.scene.ootBlenderScale
                point.co.w = 1
        case "Triangle":
            newSpline.points.add(2)
            for i, point in enumerate(newSpline.points):
                point.co.x = i * scaleDivBy2
                if i == 1:
                    point.co.y = (len(newSpline.points) * scaleDivBy2) / 2
                point.co.w = 1
        case "Square" | "Trapezium":
            newSpline.points.add(3)
            for i, point in enumerate(newSpline.points):
                point.co.x = i * scaleDivBy2
                if i in [1, 2]:
                    if type == "Square":
                        point.co.y = (len(newSpline.points) - 1) * scaleDivBy2
                        if i == 1:
                            point.co.x = newSpline.points[0].co.x
                        else:
                            point.co.x = point.co.y
                    else:
                        point.co.y = 1 * scaleDivBy2
                point.co.w = 1
        case _:
            raise PluginError("ERROR: Invalid Path Type!")

    if isClosedShape and type != "Line":
        newSpline.points.add(1)
        newSpline.points[-1].co = newSpline.points[0].co

    # make the curve's display accurate to the point's shape
    newSpline.use_cyclic_u = True
    newSpline.use_endpoint_u = False
    newSpline.resolution_u = 64
    newSpline.order_u = 2

    # create a new object and add the curve as data
    newPath = bpy.data.objects.new("New Path", newCurve)
    newPath.show_name = True
    newPath.location = Vector(bpy.context.scene.cursor.location)
    bpy.context.view_layer.active_layer_collection.collection.objects.link(newPath)

    return newPath


def getObjectList(
    objList: list[Object],
    objType: str,
    emptyType: Optional[str] = None,
    splineType: Optional[str] = None,
    parentObj: Object = None,
):
    """
    Returns a list containing objects matching ``objType``. Sorts by object name.

    Parameters:
    - ``objList``: the list of objects to iterate through, usually ``obj.children_recursive``
    - ``objType``: the object's type (``EMPTY``, ``CURVE``, etc.)
    - ``emptyType``: optional, filters the object by the given empty type
    - ``splineType``: optional, filters the object by the given spline type
    - ``parentObj``: optional, checks if the found object is parented to ``parentObj``
    """

    ret: list[Object] = []
    for obj in objList:
        if obj.type == objType:
            cond = True

            if emptyType is not None:
                cond = obj.ootEmptyType == emptyType
            elif splineType is not None:
                cond = obj.ootSplineProperty.splineType == splineType

            if parentObj is not None:
                if emptyType == "Actor" and obj.ootEmptyType == "Room":
                    for o in obj.children_recursive:
                        if o.type == objType and o.ootEmptyType == emptyType and o not in ret:
                            ret.append(o)
                    continue
                else:
                    cond = cond and obj.parent is not None and obj.parent.name == parentObj.name

            if cond and obj not in ret:
                ret.append(obj)
    ret.sort(key=lambda o: o.name)
    return ret

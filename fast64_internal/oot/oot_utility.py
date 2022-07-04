from ..utility import *
import bpy, math, mathutils, os, re, ast
from bpy.utils import register_class, unregister_class
from .oot_constants import actorRoot, ootEnumActorID

# default indentation to use when writing to decomp files
indent = " " * 4

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


class ExportInfo:
    def __init__(self, isCustomExport, exportPath, customSubPath, name):
        self.isCustomExportPath = isCustomExport
        self.exportPath = exportPath
        self.customSubPath = customSubPath
        self.name = name


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
            if obj.data is None:
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
            elif isinstance(obj.data, bpy.types.Mesh):
                self.meshes.append(obj)


# This also sets all origins relative to the scene object.
def ootDuplicateHierarchy(obj, ignoreAttr, includeEmpties, objectCategorizer):
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
    isMesh = isinstance(obj.data, bpy.types.Mesh)
    isEmpty = (
        obj.data is None or isinstance(obj.data, bpy.types.Camera) or isinstance(obj.data, bpy.types.Curve)
    ) and includeEmpties
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
    while not (obj is None or (obj is not None and obj.data is None and obj.ootEmptyType == "Scene")):
        obj = obj.parent
    if obj is None:
        return None
    else:
        return obj


def getRoomObj(obj):
    while not (obj is None or (obj is not None and obj.data is None and obj.ootEmptyType == "Room")):
        obj = obj.parent
    if obj is None:
        return None
    else:
        return obj


def checkEmptyName(name):
    if name == "":
        raise PluginError("No name entered for the exporter.")


def ootGetObjectPath(isCustomExport, exportPath, folderName):
    if isCustomExport:
        filepath = exportPath
    else:
        filepath = os.path.join(
            ootGetPath(exportPath, isCustomExport, "assets/objects/", folderName, False, False), folderName + ".c"
        )
    return filepath


def ootGetPath(exportPath, isCustomExport, subPath, folderName, makeIfNotExists, useFolderForCustom):
    if isCustomExport:
        path = bpy.path.abspath(os.path.join(exportPath, (folderName if useFolderForCustom else "")))
    else:
        if bpy.context.scene.ootDecompPath == "":
            raise PluginError("Decomp base path is empty.")
        path = bpy.path.abspath(os.path.join(bpy.context.scene.ootDecompPath, subPath + folderName))

    if not os.path.exists(path):
        if isCustomExport or makeIfNotExists:
            os.makedirs(path)
        else:
            raise PluginError(path + " does not exist.")

    return path


def getSortedChildren(armatureObj, bone):
    return sorted(
        [child.name for child in bone.children if child.ootBoneType != "Ignore"],
        key=lambda childName: childName.lower(),
    )


def getStartBone(armatureObj):
    startBoneNames = [
        bone.name for bone in armatureObj.data.bones if bone.parent is None and bone.ootBoneType != "Ignore"
    ]
    if len(startBoneNames) == 0:
        raise PluginError(armatureObj.name + ' does not have any root bones that are not of the "Ignore" type.')
    startBoneName = startBoneNames[0]
    return startBoneName
    # return 'root'


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


def getCustomProperty(data, prop):
    value = getattr(data, prop)
    return value if value != "Custom" else getattr(data, prop + str("Custom"))


def getActorExportValue(actor, field, user):
    """Returns an actor's prop value"""
    if field == "actorParam":
        return getActorParameter(actor, actor.actorKey, "Params", user)
    elif field == "transActorParam":
        return getActorParameter(actor, actor.transActorKey, "Params", user)
    elif field in {"XRot", "YRot", "ZRot"}:
        actorType = getActorType(actor, actor.actorKey)
        actorIndex = getIndexFromKey(actor.actorKey, ootEnumActorID)
        for elem in actorRoot[actorIndex]:
            target = elem.get("Target")
            tiedActorTypes = elem.get("TiedParams")
            # check if the element is tied to a specific type
            if ((tiedActorTypes is None or actorType is None) or hasActorTiedParams(tiedActorTypes, actorType)) and (
                target == field
            ):
                return getActorParameter(actor, actor.actorKey, field, user)
    return None


def getCustomActorExportValue(actor, field):
    """Returns the value of a custom actor's prop"""
    field = getCustomPropName(field)
    return getattr(actor, field, None)


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


def ootConvertTranslation(translation):
    return [int(round(value)) for value in translation]


def ootConvertRotation(rotation):
    # see BINANG_TO_DEGF
    return [int(round((math.degrees(value) % 360) / 360 * (2**16))) % (2**16) for value in rotation.to_euler()]


def getCutsceneName(obj):
    name = obj.name
    if name.startswith("Cutscene."):
        name = name[9:]
    name = name.replace(".", "_")
    return name


def getCollectionFromIndex(obj, prop, subIndex, isRoom):
    if not isRoom:
        header0 = obj.ootSceneHeader
        header1 = obj.ootAlternateSceneHeaders.childNightHeader
        header2 = obj.ootAlternateSceneHeaders.adultDayHeader
        header3 = obj.ootAlternateSceneHeaders.adultNightHeader
        cutsceneHeaders = obj.ootAlternateSceneHeaders.cutsceneHeaders
    else:
        header0 = obj.ootRoomHeader
        header1 = obj.ootAlternateRoomHeaders.childNightHeader
        header2 = obj.ootAlternateRoomHeaders.adultDayHeader
        header3 = obj.ootAlternateRoomHeaders.adultNightHeader
        cutsceneHeaders = obj.ootAlternateRoomHeaders.cutsceneHeaders

    if subIndex < 0:
        raise PluginError("Alternate scene header index too low: " + str(subIndex))
    elif subIndex == 0:
        collection = getattr(header0, prop)
    elif subIndex == 1:
        collection = getattr(header1, prop)
    elif subIndex == 2:
        collection = getattr(header2, prop)
    elif subIndex == 3:
        collection = getattr(header3, prop)
    else:
        collection = getattr(cutsceneHeaders[subIndex - 4], prop)
    return collection


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


def drawCollectionOps(layout, index, collectionType, subIndex, objName, allowAdd=True):
    if subIndex is None:
        subIndex = 0

    buttons = layout.row(align=True)

    if allowAdd:
        addOp = buttons.operator(OOTCollectionAdd.bl_idname, text="Add", icon="ADD")
        addOp.option = index + 1
        addOp.collectionType = collectionType
        addOp.subIndex = subIndex
        addOp.objName = objName

    removeOp = buttons.operator(OOTCollectionRemove.bl_idname, text="Delete", icon="REMOVE")
    removeOp.option = index
    removeOp.collectionType = collectionType
    removeOp.subIndex = subIndex
    removeOp.objName = objName

    moveUp = buttons.operator(OOTCollectionMove.bl_idname, text="Up", icon="TRIA_UP")
    moveUp.option = index
    moveUp.offset = -1
    moveUp.collectionType = collectionType
    moveUp.subIndex = subIndex
    moveUp.objName = objName

    moveDown = buttons.operator(OOTCollectionMove.bl_idname, text="Down", icon="TRIA_DOWN")
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


def getAndFormatActorProperty(object, field, shift, mask):
    """Returns an actor's property with the correct formatting"""
    # get the raw value of the prop
    attr = getattr(object, field, None)
    if field.find(".collectibleDrop") != -1:
        attr = getItemAttrFromKey("Collectibles", attr, "Value")

    # format and return the parameter part
    if attr is not None:
        # check if the value is a boolean or a string
        # then determine the right format to use
        # and return the string
        if isinstance(attr, str):
            if shift > 0:
                return f"(({attr} << {shift}) & {mask})"
            else:
                return f"({attr} & {mask})"
        elif isinstance(attr, bool):
            if attr:
                return f"(1 << {shift})"
            else:
                # return an empty string as it's not useful to return 'False' value
                return ""
        else:
            # by default, raise an error
            raise NotImplementedError
    else:
        # by default, return None
        return None


def getActorParameter(actor, actorKey, paramTarget, user):
    """Returns the current actor's parameters"""
    params = []
    actorIndex = getIndexFromKey(actorKey, ootEnumActorID)
    paramPart = ""
    for elem in actorRoot[actorIndex]:
        actorType = getActorType(actor, actorKey)
        index = int(elem.get("Index", "1"), base=10)
        tiedActorTypes = elem.get("TiedParams")

        # check if the element is tied to a specific type
        if (tiedActorTypes is None or actorType is None) or hasActorTiedParams(tiedActorTypes, actorType):
            # if the param part it's not none and not empty add it to the list
            paramPart = getActorParameterPart(elem, actor, paramTarget, index, user)
            if paramPart is not None and paramPart != "" and evalActorParams(paramPart) != 0:
                params.append(paramPart)

    # when the param part list is completed,
    # make a string with each element separated by a ``|``
    propsParams = " | ".join(params)

    # format and return the value
    if paramTarget == "Params":
        # get and format the actor type if neccessary
        actorType = getActorType(actor, actorKey)
        if actorType is not None:
            actorType = f"0x{actorType}"

        # if the list containing every param parts has items
        hasParams = len(params) > 0

        # if there's an actor type
        hasType = actorType is not None and actorType != "" and evalActorParams(actorType) != 0

        # format and return the final string
        if not hasParams and hasType:
            return actorType
        elif hasParams and not hasType:
            return f"({propsParams})"
        elif hasParams and hasType:
            return f"({actorType} | ({propsParams}))"
        elif not hasParams and not hasType:
            return "0x0"
        else:
            raise NotImplementedError
    elif len(params) > 0:
        # else if the target is a rotation and the list
        # is not empty, return the string
        return propsParams
    else:
        # else return 0
        return "0x0"


def setActorParameterPart(object, field, param, mask):
    """Sets the attributes to have the correct display on the UI"""
    shift = getShiftFromMask(mask)
    attr = getattr(object, field, None)
    paramPart = f"0x{(param & mask) >> shift:02X}"

    # look for actor type
    if field.find(".type") != -1:
        setattr(object, field, f"{param & mask:04X}")
    elif field.find(".collectibleDrop") != -1:
        # look for collectible drop
        setKeyFromItemValue("Collectibles", object, field, paramPart)
    elif field == "itemChest":
        # look for chest content
        setKeyFromItemValue("Chest Content", object, field, paramPart)
    elif field == "naviMsgID":
        # look for navi message id
        setKeyFromItemValue("Elf_Msg Message ID", object, field, paramPart)
    else:
        # by default
        if isinstance(attr, str):
            setattr(object, field, paramPart)
        elif isinstance(attr, bool):
            setattr(object, field, bool(int(paramPart, base=16)))
        else:
            raise NotImplementedError
    # return True if the prop exists
    # return False if not and this will run again
    # with an incremented index (see ``setActorParameter()``)
    return True if attr is not None else False


def getActorLastElemIndex(actorKey, elemTag, flagType):
    """Looking for the last index of an actor's property (from XML data)"""
    indices = []

    # get the index of the current actor
    actorIndex = getIndexFromKey(actorKey, ootEnumActorID)

    # iterate through each sub-elements of the current actor's XML data
    for elem in actorRoot[actorIndex]:
        # if the element tag matches
        # if we don't want to look for flags or
        # if we want to look for flags and the current element is the right one
        if (elem.tag == elemTag) and (flagType is None or elem.get("Type") == flagType):
            # convert the index to an integer and add it to the list of indices
            indices.append(int(elem.get("Index"), base=10))

    # determine the highest index and return it
    return max(indices) if indices else None


def hasActorTiedParams(tiedActorTypes, actorType):
    """Looking for parameters that depend on other parameters"""
    if tiedActorTypes is not None and actorType is not None:
        return actorType in tiedActorTypes.split(",")
    return False


def getActorParameterPart(elem, actor, paramTarget, index, user):
    """Returns the current actor's parameter part"""
    paramPart = ""
    strMask = elem.get("Mask")
    target = elem.get("Target")

    # default target to Params
    if target is None:
        target = "Params"

    # if: not <Type>, there's a bit mask and it's the right target
    if elem.tag != "Type" and strMask is not None and (target == paramTarget):
        mask = int(strMask, base=16)
        shift = getShiftFromMask(mask)

        # for each type of element tag
        # get the formatted prop value
        if elem.tag == "Flag":
            # we need to look for type of flags
            elemType = elem.get("Type")
            if elemType == "Chest":
                paramPart = getAndFormatActorProperty(
                    actor, getActorKey(actor, user) + f".chestFlag{index}", shift, strMask
                )
            elif elemType == "Collectible":
                paramPart = getAndFormatActorProperty(
                    actor, getActorKey(actor, user) + f".collectibleFlag{index}", shift, strMask
                )
            elif elemType == "Switch":
                paramPart = getAndFormatActorProperty(
                    actor, getActorKey(actor, user) + f".switchFlag{index}", shift, strMask
                )
        elif elem.tag == "Property":
            paramPart = getAndFormatActorProperty(actor, (getActorKey(actor, user) + f".props{index}"), shift, strMask)
        elif elem.tag == "ChestContent":
            itemChest = getItemAttrFromKey("Chest Content", actor.itemChest, "Value")
            if shift > 0:
                paramPart = f"(({itemChest} << {shift}) & 0x{mask:X})"
            else:
                paramPart = f"({itemChest} & 0x{mask:X})"
        elif elem.tag == "Message":
            naviMsg = getItemAttrFromKey("Elf_Msg Message ID", actor.naviMsgID, "Value")
            if shift > 0:
                paramPart = f"(({naviMsg} << {shift}) & 0x{mask:X})"
            else:
                paramPart = f"({naviMsg} & 0x{mask:X})"
        elif elem.tag == "Collectible":
            paramPart = getAndFormatActorProperty(
                actor, getActorKey(actor, user) + f".collectibleDrop{index}", shift, strMask
            )
        elif elem.tag == "Bool":
            paramPart = getAndFormatActorProperty(actor, (getActorKey(actor, user) + f".bool{index}"), shift, strMask)
        elif elem.tag == "Enum":
            paramPart = getAndFormatActorProperty(actor, (getActorKey(actor, user) + f".enum{index}"), shift, strMask)

    # if the return value is none execute again this function
    # but increment the index value
    if paramPart is None:
        paramPart = getActorParameterPart(elem, actor, paramTarget, (index + 1), user)

    return paramPart


def setActorParameter(elem, params, actor, actorKey, paramTarget, index):
    """Sets the current actor's parameters"""
    strMask = elem.get("Mask")
    target = elem.get("Target")
    paramPart = ""

    # default target to Params
    if target is None:
        target = "Params"

    # if no mask is given in the data default to 0xFFFF
    if strMask is not None:
        mask = int(strMask, base=16)
    else:
        mask = 0xFFFF

    # for each elem tag type
    # set and return the values
    # so we can see if we need to execute this again
    # with an incremented index value
    if target == paramTarget:
        if elem.tag == "Type":
            paramPart = setActorParameterPart(actor, actorKey + f".type{index}", params, mask)
        if elem.tag == "Flag":
            elemType = elem.get("Type")
            if elemType == "Chest":
                paramPart = setActorParameterPart(actor, actorKey + f".chestFlag{index}", params, mask)
            elif elemType == "Collectible":
                paramPart = setActorParameterPart(actor, actorKey + f".collectibleFlag{index}", params, mask)
            elif (elemType == "Switch") and (target == paramTarget):
                paramPart = setActorParameterPart(actor, actorKey + f".switchFlag{index}", params, mask)
        elif ((elem.tag == "Property") and (elem.get("Name") != "None")) and (target == paramTarget):
            paramPart = setActorParameterPart(actor, actorKey + f".props{index}", params, mask)
        elif elem.tag == "ChestContent":
            paramPart = setActorParameterPart(actor, "itemChest", params, mask)
        elif elem.tag == "Message":
            paramPart = setActorParameterPart(actor, "naviMsgID", params, mask)
        elif elem.tag == "Collectible":
            paramPart = setActorParameterPart(actor, actorKey + f".collectibleDrop{index}", params, mask)
        elif (elem.tag == "Bool") and (target == paramTarget):
            paramPart = setActorParameterPart(actor, actorKey + f".bool{index}", params, mask)
        elif (elem.tag == "Enum") and (target == paramTarget):
            paramPart = setActorParameterPart(actor, actorKey + f".enum{index}", params, mask)

    if paramPart is False:
        setActorParameter(elem, params, actor, actorKey, paramTarget, (index + 1))


def upgradeActorInit(obj):
    """
    Upgrades parameters stored in the blend
    to the new system
    """

    print("Upgrading actor props of object", obj.name, obj.ootEmptyType)

    def _processRotation(rotName, legacyActor, actor):
        """Process the rotation values if needed"""

        # get the value
        rotValue = getattr(legacyActor, getLegacyPropName(rotName))

        # if it's not 0
        if rotValue != "0" or rotValue != "0x0":
            # convert the value to an integer
            try:
                rotParam = evalActorParams(rotValue)
            except SyntaxError:
                # if the value is not an hexadecimal number convert the actor to a custom one
                convertLegacyActorToCustom(obj, legacyActor, actor, objType, getLegacyPropName(rotName))

                # stop the execution there
                return

            # if the value was successfully converted:
            # start the actual upgrade process
            upgradeActorProcess(rotName, obj, legacyActor.actorID, actor, rotParam, getLegacyPropName(rotName), rotName)

            # and set the value to the new actor
            setattr(actor, getLegacyPropName(rotName), getActorParameter(actor, actor.actorKey, rotName, objType))

    # actors are empty objects
    if obj.data is None:
        objType = obj.ootEmptyType
        actor = obj.fast64.oot.actor

        if objType == "Actor":
            # get the legacy actor data
            legacyActor = obj.ootActorProperty

            # convert the value to an integer
            try:
                legacyParams = evalActorParams(legacyActor.actorParam)
            except SyntaxError:
                # if the value is not an hexadecimal number convert the actor to a custom one
                # legacyParams is none to check if we should start the upgrade process
                legacyParams = None
                convertLegacyActorToCustom(obj, legacyActor, actor, objType, None)

                if legacyActor.rotOverride:
                    if legacyActor.rotOverrideX != "0" or legacyActor.rotOverrideX != "0x0":
                        convertLegacyActorToCustom(obj, legacyActor, actor, objType, "rotOverrideX")

                    if legacyActor.rotOverrideY != "0" or legacyActor.rotOverrideY != "0x0":
                        convertLegacyActorToCustom(obj, legacyActor, actor, objType, "rotOverrideY")

                    if legacyActor.rotOverrideZ != "0" or legacyActor.rotOverrideZ != "0x0":
                        convertLegacyActorToCustom(obj, legacyActor, actor, objType, "rotOverrideZ")

            if legacyParams is not None:
                # start the upgrade process
                upgradeActorProcess(
                    objType, obj, obj.ootActorProperty.actorID, actor, legacyParams, "actorParam", "Params"
                )

                # update the parameters since every props are set
                actor.actorParam = getActorParameter(actor, actor.actorKey, "Params", objType)

                # do the same thing for rotations values if needed
                if legacyActor.rotOverride:
                    # for each rotation, look if the legacy parameter is anything but zero
                    # and start the upgrade process like we did before
                    _processRotation("XRot", legacyActor, actor)
                    _processRotation("YRot", legacyActor, actor)
                    _processRotation("ZRot", legacyActor, actor)

        elif objType == "Transition Actor":
            # get the legacy data
            legacyActor = obj.ootTransitionActorProperty.actor

            # convert the value to an integer
            try:
                legacyParams = evalActorParams(legacyActor.actorParam)
            except SyntaxError:
                # if the value is not an hexadecimal number convert the actor to a custom one
                legacyParams = None
                convertLegacyActorToCustom(obj, legacyActor, actor, objType, None)
                return

            if legacyParams is not None:
                # start the upgrade process
                upgradeActorProcess(objType, obj, legacyActor.actorID, actor, legacyParams, "actorParam", "Params")

                # update the parameters since every props are set
                actor.transActorParam = getActorParameter(actor, actor.transActorKey, "Params", objType)
        elif objType == "Entrance":
            # get the legacy data
            legacyActor = obj.ootEntranceProperty.actor

            # convert the value to an integer
            try:
                legacyParams = evalActorParams(legacyActor.actorParam)
            except SyntaxError:
                # if the value is not an hexadecimal number convert the actor to a custom one
                legacyParams = None
                convertLegacyActorToCustom(obj, legacyActor, actor, objType, None)
                return

            if legacyParams is not None:
                # start the upgrade process
                upgradeActorProcess(objType, obj, legacyActor.actorID, actor, legacyParams, "actorParam", "Params")

                # update the parameters since every props are set
                actor.actorParam = getActorParameter(actor, actor.actorKey, "Params", objType)


def upgradeActorProcess(user, obj, actorID, actor, params, paramField, paramTarget):
    # for non-custom
    if not obj.ootEntranceProperty.customActor and actorID != "Custom":
        # read XML data
        for actorNode in actorRoot:
            if actorNode.tag == "Actor":
                actorKey = actorNode.get("Key")

                # since it's still the debug names
                # we can recreate the actor ID from the key
                if ("ACTOR_" + actorKey.upper()) == actorID:
                    # if it's a match set the actor key
                    if not "Transition" in user:
                        actor.actorKey = actorKey
                    else:
                        actor.transActorKey = actorKey

                    # if the current actor has sub-elements
                    if len(actorNode) > 0:
                        # for each sub-element set props' values
                        for elem in actorNode:
                            index = int(elem.get("Index", "1"), base=10)
                            tiedActorTypes = elem.get("TiedActorTypes")
                            actorType = getActorType(actor, actorKey)

                            # check if the element is tied to a specific type
                            if (tiedActorTypes is None or actorType is None) or hasActorTiedParams(
                                tiedActorTypes, actorType
                            ) is True:
                                setActorParameter(elem, params, actor, actorKey, paramTarget, index)
                    # get out of the loop
                    break
    else:
        # for custom actors
        if user != "Transition Actor":
            # if this is an entrance or normal actor

            # set the key to custom
            actor.actorKey = "Custom"

            # get the legacy actor data
            legacyActor = obj.ootActorProperty
            if user == "Entrance":
                legacyActor = obj.ootEntranceProperty.actor

            # copy the ID and the parameters to the new actor properties
            actor.actorIDCustom = getattr(legacyActor, "actorIDCustom")
            setattr(actor, getCustomPropName(paramField), getattr(legacyActor, paramField))

            # same for the rotations value if necessary
            if "Rot" in paramField and legacyActor.rotOverride:
                rotX = evalActorParams(legacyActor.rotOverrideX)
                rotY = evalActorParams(legacyActor.rotOverrideY)
                rotZ = evalActorParams(legacyActor.rotOverrideZ)

                # use the rotation override if needed
                if not (rotX == 0) or not (rotY == 0) or not (rotZ == 0):
                    actor.rotOverride = True
                    setattr(actor, getCustomPropName(getLegacyPropName(paramField)), getattr(legacyActor, paramField))
        else:
            # for transition actors

            # set the key to custom
            actor.transActorKey = "Custom"

            # retrieve the ID and the parameters
            actor.transActorIDCustom = getattr(obj.ootTransitionActorProperty.actor, "actorIDCustom")
            actor.transActorParamCustom = actor.transActorParam = getattr(
                obj.ootTransitionActorProperty.actor, paramField
            )


def convertLegacyActorToCustom(obj, legacyActor, actor, user, rotField):
    """Converts the legacy data to a custom actor"""

    # To inconvenient data loss from the system upgrade
    # we're converting the actor to a custom actor
    # that can accept any value
    print(f"Converting actor: {obj.name} to custom...")

    # for entrance or regular actors
    if not "Transition" in user:

        # set ``customActor`` to true for entrance actors
        # set the actor key to custom
        if "Entrance" in user:
            actor.customActor = True
        else:
            actor.actorKey = "Custom"

        # move the ID and the parameters
        actor.actorIDCustom = legacyActor.actorIDCustom
        actor.actorParamCustom = legacyActor.actorParam

        # if there's rotation parameters
        # and the rotation name is set
        # set the value to the new actor's corresponding rotation
        if legacyActor.rotOverride and rotField is not None:
            actor.rotOverride = True
            setattr(actor, getCustomPropName(rotField), getattr(legacyActor, rotField))
    else:
        # if it's a transition actor

        # set the actor key
        actor.transActorKey = "Custom"

        # then move the ID and the parameters
        actor.transActorIDCustom = legacyActor.actorIDCustom
        actor.transActorParamCustom = legacyActor.actorParam


def getCustomPropName(propName):
    """Returns the name of the custom version of a prop"""

    # get the name among those defines in this dictionnary
    customPropNameByPropName = {
        "actorParam": "actorParamCustom",
        "transActorParam": "transActorParamCustom",
        "rotOverrideX": "rotOverrideXCustom",
        "rotOverrideY": "rotOverrideYCustom",
        "rotOverrideZ": "rotOverrideZCustom",
    }
    return customPropNameByPropName[propName] if propName in customPropNameByPropName else propName


def getLegacyPropName(propName):
    """Returns the old name of a prop"""

    # get the name among those defines in this dictionnary
    legacyPropNameByPropName = {
        "Params": "actorParam",
        "XRot": "rotOverrideX",
        "YRot": "rotOverrideY",
        "ZRot": "rotOverrideZ",
    }
    return legacyPropNameByPropName[propName] if propName in legacyPropNameByPropName else propName


def getIDFromKey(key, root, list):
    """Returns the actor ID from its key"""

    # return the argument ``key`` for custom actors
    if not (key == "Custom"):
        return root[getIndexFromKey(key, list)].get("ID")
    else:
        return key


def getItemAttrFromKey(enum, key, elemToGet):
    """Returns a list sub-element attribute"""
    for listNode in actorRoot:
        # look for the correct <List>
        if listNode.tag == "List" and listNode.get("Name") == enum:
            for elem in listNode:
                # if this is the correct element
                if elem.get("Key") == key:
                    # return the wanted attribute
                    return elem.get(elemToGet)


def setKeyFromItemValue(enum, object, field, value):
    """Sets the key based on the value"""
    for listNode in actorRoot:
        # look for the correct <List>
        if listNode.tag == "List" and listNode.get("Name") == enum:
            for elem in listNode:
                # if the current element's value matches the argument value
                # set the key and return to break out of the loop
                # since the job is done
                if elem.get("Value") == value:
                    setattr(object, field, elem.get("Key"))
                    return


def isLatestVersion():
    """Returns ``True`` or ``False`` if the object is on the latest version or not"""
    return bpy.context.object.fast64.oot.version == bpy.context.object.fast64.oot.cur_version


def isActorCustom(actor):
    """Checks either the actor is an entrance in custom mode or a transition/normal actor with the actor key ``Custom``"""

    # if it's a regular or transition actor
    isTransition = bpy.context.view_layer.objects.active.ootEmptyType == "Transition Actor"
    isCustom = (actor.transActorKey == "Custom") if isTransition else (actor.actorKey == "Custom")

    # if the actor is an entrance
    isEntrance = bpy.context.view_layer.objects.active.ootEmptyType == "Entrance"
    isEntranceCustom = bpy.context.view_layer.objects.active.ootEntranceProperty.customActor

    return isCustom if isEntrance is False else isEntranceCustom


def getActorType(actor, actorKey):
    """Returns the value of ``actor.type``"""

    actorIndex = getIndexFromKey(actorKey, ootEnumActorID)
    for elem in actorRoot[actorIndex]:
        # if the current element is <Type>
        if elem.tag == "Type":
            # return the value of the prop ``.typeX``
            return getattr(actor, actorKey + ".type" + elem.get("Index", "1"), None)
    # default to None
    return None


def getIndexFromKey(key, list):
    """Returns the index of an XML element from its key"""

    # we can use it to directly get the right actor
    # instead of ``for node in root for elem in node``
    # we can use ``for elem in root[index]``
    # to access the correct data from the XML file
    for index, elem in enumerate(list):
        if key == elem[0]:
            return index - 1


def getShiftFromMask(mask):
    """Returns the shift value from the mask"""

    # get the shift by subtracting the length of the mask
    # converted in binary on 16 bits (since the mask can be on 16 bits) with
    # that length but with the rightmost zeros stripped
    return int(f"{len(f'{mask:016b}') - len(f'{mask:016b}'.rstrip('0'))}", base=10)


def evalActorParams(params):
    """Compute the parameters"""

    # remove spaces
    s = params.strip()

    # check if we need to add '0x'
    if not "&" in s:
        match = re.finditer(r"[xXa-fA-F0-9]+", s)
        for elem in match:
            elem = elem.group(0)
            if not "0x" in elem and not "|" in s:
                s = "0x" + elem

    node = ast.parse(s, mode="eval")

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        elif isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.USub):
                return -_eval(node.operand)
            elif isinstance(node.op, ast.Invert):
                return ~_eval(node.operand)
            else:
                raise Exception("Unsupported type {}".format(node.op))
        elif isinstance(node, ast.BinOp):
            return binOps[type(node.op)](_eval(node.left), _eval(node.right))
        else:
            raise Exception("Unsupported type {}".format(node))

    return _eval(node.body)


def getActorKey(actor, user):
    """Returns the actor key value"""

    # check if it's a transition or an entrance/normal actor
    if "Transition" in user or "trans" in user:
        return actor.transActorKey
    else:
        return actor.actorKey

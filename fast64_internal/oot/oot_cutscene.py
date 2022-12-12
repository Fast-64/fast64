import os, bpy
from bpy.utils import register_class, unregister_class
from ..panels import OOT_Panel
from ..utility import PluginError, CData, prop_split, writeCData, raisePluginError
from .oot_utility import OOTCollectionAdd, drawCollectionOps, getCollection, getCutsceneName, getCustomProperty

from .oot_constants import (
    ootEnumCSTextboxType,
    ootEnumCSListType,
    ootEnumCSTransitionType,
    ootEnumCSTextboxTypeIcons,
    ootEnumCSListTypeIcons,
    ootEnumCSListTypeListC,
    ootEnumCSTextboxTypeEntryC,
    ootEnumCSListTypeEntryC,
)

from .oot_level_classes import (
    OOTCSList,
    OOTCSTextbox,
    OOTCSLighting,
    OOTCSTime,
    OOTCSBGM,
    OOTCSMisc,
    OOTCS0x09,
    OOTCSUnk,
    OOTCutscene,
)

################################################################################
# Properties
################################################################################

# Perhaps this should have been called something like OOTCSParentPropertyType,
# but now it needs to keep the same name to not break existing scenes which use
# the cutscene system.
class OOTCSProperty:
    propName = None
    attrName = None
    subprops = ["startFrame", "endFrame"]
    expandTab: bpy.props.BoolProperty(default=True)
    startFrame: bpy.props.IntProperty(name="", default=0, min=0)
    endFrame: bpy.props.IntProperty(name="", default=1, min=0)

    def getName(self):
        return self.propName

    def filterProp(self, name, listProp):
        return True

    def filterName(self, name, listProp):
        return name

    def draw(self, layout, listProp, listIndex, cmdIndex, objName, collectionType):
        layout.prop(
            self,
            "expandTab",
            text=self.getName() + " " + str(cmdIndex),
            icon="TRIA_DOWN" if self.expandTab else "TRIA_RIGHT",
        )
        if not self.expandTab:
            return
        box = layout.box().column()
        drawCollectionOps(box, cmdIndex, collectionType + "." + self.attrName, listIndex, objName)
        for p in self.subprops:
            if self.filterProp(p, listProp):
                prop_split(box, self, p, self.filterName(p, listProp))


class OOTCSTextboxProperty(OOTCSProperty, bpy.types.PropertyGroup):
    propName = "Textbox"
    attrName = "textbox"
    subprops = [
        "messageId",
        "ocarinaSongAction",
        "startFrame",
        "endFrame",
        "type",
        "topOptionBranch",
        "bottomOptionBranch",
        "ocarinaMessageId",
    ]
    textboxType: bpy.props.EnumProperty(items=ootEnumCSTextboxType)
    messageId: bpy.props.StringProperty(name="", default="0x0000")
    ocarinaSongAction: bpy.props.StringProperty(name="", default="0x0000")
    type: bpy.props.StringProperty(name="", default="0x0000")
    topOptionBranch: bpy.props.StringProperty(name="", default="0x0000")
    bottomOptionBranch: bpy.props.StringProperty(name="", default="0x0000")
    ocarinaMessageId: bpy.props.StringProperty(name="", default="0x0000")

    def getName(self):
        return self.textboxType

    def filterProp(self, name, listProp):
        if self.textboxType == "Text":
            return name not in ["ocarinaSongAction", "ocarinaMessageId"]
        elif self.textboxType == "None":
            return name in ["startFrame", "endFrame"]
        elif self.textboxType == "LearnSong":
            return name in ["ocarinaSongAction", "startFrame", "endFrame", "ocarinaMessageId"]
        else:
            raise PluginError("Invalid property name for OOTCSTextboxProperty")


class OOTCSTextboxAdd(bpy.types.Operator):
    bl_idname = "object.oot_cstextbox_add"
    bl_label = "Add CS Textbox"
    bl_options = {"REGISTER", "UNDO"}

    collectionType: bpy.props.StringProperty()
    textboxType: bpy.props.EnumProperty(items=ootEnumCSTextboxType)
    listIndex: bpy.props.IntProperty()
    objName: bpy.props.StringProperty()

    def execute(self, context):
        collection = getCollection(self.objName, self.collectionType, self.listIndex)
        newTextboxElement = collection.add()
        newTextboxElement.textboxType = self.textboxType
        return {"FINISHED"}


class OOTCSLightingProperty(OOTCSProperty, bpy.types.PropertyGroup):
    propName = "Lighting"
    attrName = "lighting"
    subprops = ["index", "startFrame"]
    index: bpy.props.IntProperty(name="", default=1, min=1)


class OOTCSTimeProperty(OOTCSProperty, bpy.types.PropertyGroup):
    propName = "Time"
    attrName = "time"
    subprops = ["startFrame", "hour", "minute"]
    hour: bpy.props.IntProperty(name="", default=23, min=0, max=23)
    minute: bpy.props.IntProperty(name="", default=59, min=0, max=59)


class OOTCSBGMProperty(OOTCSProperty, bpy.types.PropertyGroup):
    propName = "BGM"
    attrName = "bgm"
    subprops = ["value", "startFrame", "endFrame"]
    value: bpy.props.StringProperty(name="", default="0x0000")

    def filterProp(self, name, listProp):
        return name != "endFrame" or listProp.listType == "FadeBGM"

    def filterName(self, name, listProp):
        if name == "value":
            return "Fade Type" if listProp.listType == "FadeBGM" else "Sequence"
        return name


class OOTCSMiscProperty(OOTCSProperty, bpy.types.PropertyGroup):
    propName = "Misc"
    attrName = "misc"
    subprops = ["operation", "startFrame", "endFrame"]
    operation: bpy.props.IntProperty(name="", default=1, min=1, max=35)


class OOTCS0x09Property(OOTCSProperty, bpy.types.PropertyGroup):
    propName = "0x09"
    attrName = "nine"
    subprops = ["startFrame", "unk2", "unk3", "unk4"]
    unk2: bpy.props.StringProperty(name="", default="0x00")
    unk3: bpy.props.StringProperty(name="", default="0x00")
    unk4: bpy.props.StringProperty(name="", default="0x00")


class OOTCSUnkProperty(OOTCSProperty, bpy.types.PropertyGroup):
    propName = "Unk"
    attrName = "unk"
    subprops = ["unk1", "unk2", "unk3", "unk4", "unk5", "unk6", "unk7", "unk8", "unk9", "unk10", "unk11", "unk12"]
    unk1: bpy.props.StringProperty(name="", default="0x00000000")
    unk2: bpy.props.StringProperty(name="", default="0x00000000")
    unk3: bpy.props.StringProperty(name="", default="0x00000000")
    unk4: bpy.props.StringProperty(name="", default="0x00000000")
    unk5: bpy.props.StringProperty(name="", default="0x00000000")
    unk6: bpy.props.StringProperty(name="", default="0x00000000")
    unk7: bpy.props.StringProperty(name="", default="0x00000000")
    unk8: bpy.props.StringProperty(name="", default="0x00000000")
    unk9: bpy.props.StringProperty(name="", default="0x00000000")
    unk10: bpy.props.StringProperty(name="", default="0x00000000")
    unk11: bpy.props.StringProperty(name="", default="0x00000000")
    unk12: bpy.props.StringProperty(name="", default="0x00000000")


class OOTCSListProperty(bpy.types.PropertyGroup):
    expandTab: bpy.props.BoolProperty(default=True)

    listType: bpy.props.EnumProperty(items=ootEnumCSListType)
    textbox: bpy.props.CollectionProperty(type=OOTCSTextboxProperty)
    lighting: bpy.props.CollectionProperty(type=OOTCSLightingProperty)
    time: bpy.props.CollectionProperty(type=OOTCSTimeProperty)
    bgm: bpy.props.CollectionProperty(type=OOTCSBGMProperty)
    misc: bpy.props.CollectionProperty(type=OOTCSMiscProperty)
    nine: bpy.props.CollectionProperty(type=OOTCS0x09Property)
    unk: bpy.props.CollectionProperty(type=OOTCSUnkProperty)

    unkType: bpy.props.StringProperty(name="", default="0x0001")
    fxType: bpy.props.EnumProperty(items=ootEnumCSTransitionType)
    fxStartFrame: bpy.props.IntProperty(name="", default=0, min=0)
    fxEndFrame: bpy.props.IntProperty(name="", default=1, min=0)


def drawCSListProperty(layout, listProp, listIndex, objName, collectionType):
    layout.prop(
        listProp,
        "expandTab",
        text=listProp.listType + " List" if listProp.listType != "FX" else "Scene Trans FX",
        icon="TRIA_DOWN" if listProp.expandTab else "TRIA_RIGHT",
    )
    if not listProp.expandTab:
        return
    box = layout.box().column()
    drawCollectionOps(box, listIndex, collectionType, None, objName, False)

    if listProp.listType == "Textbox":
        attrName = "textbox"
    elif listProp.listType == "FX":
        prop_split(box, listProp, "fxType", "Transition")
        prop_split(box, listProp, "fxStartFrame", "Start Frame")
        prop_split(box, listProp, "fxEndFrame", "End Frame")
        return
    elif listProp.listType == "Lighting":
        attrName = "lighting"
    elif listProp.listType == "Time":
        attrName = "time"
    elif listProp.listType in ["PlayBGM", "StopBGM", "FadeBGM"]:
        attrName = "bgm"
    elif listProp.listType == "Misc":
        attrName = "misc"
    elif listProp.listType == "0x09":
        attrName = "nine"
    elif listProp.listType == "Unk":
        prop_split(box, listProp, "unkType", "Unk List Type")
        attrName = "unk"
    else:
        raise PluginError("Internal error: invalid listType " + listProp.listType)

    dat = getattr(listProp, attrName)
    for i, p in enumerate(dat):
        p.draw(box, listProp, listIndex, i, objName, collectionType)
    if len(dat) == 0:
        box.label(text="No items in " + listProp.listType + " List.")
    if listProp.listType == "Textbox":
        row = box.row(align=True)
        for l in range(3):
            addOp = row.operator(
                OOTCSTextboxAdd.bl_idname, text="Add " + ootEnumCSTextboxType[l][1], icon=ootEnumCSTextboxTypeIcons[l]
            )
            addOp.collectionType = collectionType + ".textbox"
            addOp.textboxType = ootEnumCSTextboxType[l][0]
            addOp.listIndex = listIndex
            addOp.objName = objName
    else:
        addOp = box.operator(OOTCollectionAdd.bl_idname, text="Add item to " + listProp.listType + " List")
        addOp.option = len(dat)
        addOp.collectionType = collectionType + "." + attrName
        addOp.subIndex = listIndex
        addOp.objName = objName


class OOTCSListAdd(bpy.types.Operator):
    bl_idname = "object.oot_cslist_add"
    bl_label = "Add CS List"
    bl_options = {"REGISTER", "UNDO"}

    collectionType: bpy.props.StringProperty()
    listType: bpy.props.EnumProperty(items=ootEnumCSListType)
    objName: bpy.props.StringProperty()

    def execute(self, context):
        collection = getCollection(self.objName, self.collectionType, None)
        newList = collection.add()
        newList.listType = self.listType
        return {"FINISHED"}


def drawCSAddButtons(layout, objName, collectionType):
    def addButton(row):
        nonlocal l
        op = row.operator(OOTCSListAdd.bl_idname, text=ootEnumCSListType[l][1], icon=ootEnumCSListTypeIcons[l])
        op.collectionType = collectionType
        op.listType = ootEnumCSListType[l][0]
        op.objName = objName
        l += 1

    box = layout.column(align=True)
    l = 0
    row = box.row(align=True)
    row.label(text="Add:")
    addButton(row)
    for _ in range(3):
        row = box.row(align=True)
        for _ in range(3):
            addButton(row)
    box.label(text="Install zcamedit for camera/actor motion.")


class OOTCutsceneProperty(bpy.types.PropertyGroup):
    csEndFrame: bpy.props.IntProperty(name="End Frame", min=0, default=100)
    csWriteTerminator: bpy.props.BoolProperty(name="Write Terminator (Code Execution)")
    csTermIdx: bpy.props.IntProperty(name="Index", min=0)
    csTermStart: bpy.props.IntProperty(name="Start Frm", min=0, default=99)
    csTermEnd: bpy.props.IntProperty(name="End Frm", min=0, default=100)
    csLists: bpy.props.CollectionProperty(type=OOTCSListProperty, name="Cutscene Lists")


def drawCutsceneProperty(box, obj):
    prop = obj.ootCutsceneProperty
    box.prop(prop, "csEndFrame")
    box.prop(prop, "csWriteTerminator")
    if prop.csWriteTerminator:
        r = box.row()
        r.prop(prop, "csTermIdx")
        r.prop(prop, "csTermStart")
        r.prop(prop, "csTermEnd")
    for i, p in enumerate(prop.csLists):
        drawCSListProperty(box, p, i, obj.name, "Cutscene")
    drawCSAddButtons(box, obj.name, "Cutscene")


################################################################################
# Properties to level classes
################################################################################


def readCutsceneData(csParentOut, csParentIn):
    for listIn in csParentIn.csLists:
        listOut = OOTCSList()
        listOut.listType = listIn.listType
        listOut.unkType, listOut.fxType, listOut.fxStartFrame, listOut.fxEndFrame = (
            listIn.unkType,
            listIn.fxType,
            listIn.fxStartFrame,
            listIn.fxEndFrame,
        )
        listData = []
        if listOut.listType == "Textbox":
            for entryIn in listIn.textbox:
                entryOut = OOTCSTextbox()
                entryOut.textboxType = entryIn.textboxType
                entryOut.messageId = entryIn.messageId
                entryOut.ocarinaSongAction = entryIn.ocarinaSongAction
                entryOut.startFrame = entryIn.startFrame
                entryOut.endFrame = entryIn.endFrame
                entryOut.type = entryIn.type
                entryOut.topOptionBranch = entryIn.topOptionBranch
                entryOut.bottomOptionBranch = entryIn.bottomOptionBranch
                entryOut.ocarinaMessageId = entryIn.ocarinaMessageId
                listOut.entries.append(entryOut)
        elif listOut.listType == "Lighting":
            for entryIn in listIn.lighting:
                entryOut = OOTCSLighting()
                entryOut.index = entryIn.index
                entryOut.startFrame = entryIn.startFrame
                listOut.entries.append(entryOut)
        elif listOut.listType == "Time":
            for entryIn in listIn.time:
                entryOut = OOTCSTime()
                entryOut.startFrame = entryIn.startFrame
                entryOut.hour = entryIn.hour
                entryOut.minute = entryIn.minute
                listOut.entries.append(entryOut)
        elif listOut.listType in {"PlayBGM", "StopBGM", "FadeBGM"}:
            for entryIn in listIn.bgm:
                entryOut = OOTCSBGM()
                entryOut.value = entryIn.value
                entryOut.startFrame = entryIn.startFrame
                entryOut.endFrame = entryIn.endFrame
                listOut.entries.append(entryOut)
        elif listOut.listType == "Misc":
            for entryIn in listIn.misc:
                entryOut = OOTCSMisc()
                entryOut.operation = entryIn.operation
                entryOut.startFrame = entryIn.startFrame
                entryOut.endFrame = entryIn.endFrame
                listOut.entries.append(entryOut)
        elif listOut.listType == "0x09":
            for entryIn in listIn.nine:
                entryOut = OOTCS0x09()
                entryOut.startFrame = entryIn.startFrame
                entryOut.unk2 = entryIn.unk2
                entryOut.unk3 = entryIn.unk3
                entryOut.unk4 = entryIn.unk4
                listOut.entries.append(entryOut)
        elif listOut.listType == "Unk":
            for entryIn in listIn.unk:
                entryOut = OOTCSUnk()
                entryOut.unk1 = entryIn.unk1
                entryOut.unk2 = entryIn.unk2
                entryOut.unk3 = entryIn.unk3
                entryOut.unk4 = entryIn.unk4
                entryOut.unk5 = entryIn.unk5
                entryOut.unk6 = entryIn.unk6
                entryOut.unk7 = entryIn.unk7
                entryOut.unk8 = entryIn.unk8
                entryOut.unk9 = entryIn.unk9
                entryOut.unk10 = entryIn.unk10
                entryOut.unk11 = entryIn.unk11
                entryOut.unk12 = entryIn.unk12
                listOut.entries.append(entryOut)
        csParentOut.csLists.append(listOut)


def convertCutsceneObject(obj):
    cs = OOTCutscene()
    cs.name = getCutsceneName(obj)
    csprop = obj.ootCutsceneProperty
    cs.csEndFrame = getCustomProperty(csprop, "csEndFrame")
    cs.csWriteTerminator = getCustomProperty(csprop, "csWriteTerminator")
    cs.csTermIdx = getCustomProperty(csprop, "csTermIdx")
    cs.csTermStart = getCustomProperty(csprop, "csTermStart")
    cs.csTermEnd = getCustomProperty(csprop, "csTermEnd")
    readCutsceneData(cs, csprop)
    return cs


################################################################################
# Level classes to C
################################################################################


def ootCutsceneIncludes(headerfilename):
    ret = CData()
    ret.source = (
        '#include "ultra64.h"\n'
        + '#include "z64.h"\n'
        + '#include "macros.h"\n'
        + '#include "command_macros_base.h"\n'
        + '#include "z64cutscene_commands.h"\n\n'
        + '#include "'
        + headerfilename
        + '"\n\n'
    )
    return ret


def ootCutsceneDataToC(csParent, csName):
    # csParent can be OOTCutscene or OOTScene
    data = CData()
    data.header = "extern CutsceneData " + csName + "[];\n"
    data.source = "CutsceneData " + csName + "[] = {\n"
    nentries = len(csParent.csLists) + (1 if csParent.csWriteTerminator else 0)
    data.source += "\tCS_BEGIN_CUTSCENE(" + str(nentries) + ", " + str(csParent.csEndFrame) + "),\n"
    if csParent.csWriteTerminator:
        data.source += (
            "\tCS_TERMINATOR("
            + str(csParent.csTermIdx)
            + ", "
            + str(csParent.csTermStart)
            + ", "
            + str(csParent.csTermEnd)
            + "),\n"
        )
    for list in csParent.csLists:
        data.source += "\t" + ootEnumCSListTypeListC[list.listType] + "("
        if list.listType == "Unk":
            data.source += list.unkType + ", "
        if list.listType == "FX":
            data.source += list.fxType + ", " + str(list.fxStartFrame) + ", " + str(list.fxEndFrame)
        else:
            data.source += str(len(list.entries))
        data.source += "),\n"
        for e in list.entries:
            data.source += "\t\t"
            if list.listType == "Textbox":
                data.source += ootEnumCSTextboxTypeEntryC[e.textboxType]
            else:
                data.source += ootEnumCSListTypeEntryC[list.listType]
            data.source += "("
            if list.listType == "Textbox":
                if e.textboxType == "Text":
                    data.source += (
                        e.messageId
                        + ", "
                        + str(e.startFrame)
                        + ", "
                        + str(e.endFrame)
                        + ", "
                        + e.type
                        + ", "
                        + e.topOptionBranch
                        + ", "
                        + e.bottomOptionBranch
                    )
                elif e.textboxType == "None":
                    data.source += str(e.startFrame) + ", " + str(e.endFrame)
                elif e.textboxType == "LearnSong":
                    data.source += (
                        e.ocarinaSongAction
                        + ", "
                        + str(e.startFrame)
                        + ", "
                        + str(e.endFrame)
                        + ", "
                        + e.ocarinaMessageId
                    )
            elif list.listType == "Lighting":
                data.source += (
                    str(e.index) + ", " + str(e.startFrame) + ", " + str(e.startFrame + 1) + ", 0, 0, 0, 0, 0, 0, 0, 0"
                )
            elif list.listType == "Time":
                data.source += (
                    "1, "
                    + str(e.startFrame)
                    + ", "
                    + str(e.startFrame + 1)
                    + ", "
                    + str(e.hour)
                    + ", "
                    + str(e.minute)
                    + ", 0"
                )
            elif list.listType in ["PlayBGM", "StopBGM", "FadeBGM"]:
                data.source += e.value
                if list.listType != "FadeBGM":
                    data.source += " + 1"  # Game subtracts 1 to get actual seq
                data.source += ", " + str(e.startFrame) + ", " + str(e.endFrame) + ", 0, 0, 0, 0, 0, 0, 0, 0"
            elif list.listType == "Misc":
                data.source += (
                    str(e.operation)
                    + ", "
                    + str(e.startFrame)
                    + ", "
                    + str(e.endFrame)
                    + ", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0"
                )
            elif list.listType == "0x09":
                data.source += (
                    "0, "
                    + str(e.startFrame)
                    + ", "
                    + str(e.startFrame + 1)
                    + ", "
                    + e.unk2
                    + ", "
                    + e.unk3
                    + ", "
                    + e.unk4
                    + ", 0, 0"
                )
            elif list.listType == "Unk":
                data.source += (
                    e.unk1
                    + ", "
                    + e.unk2
                    + ", "
                    + e.unk3
                    + ", "
                    + e.unk4
                    + ", "
                    + e.unk5
                    + ", "
                    + e.unk6
                    + ", "
                    + e.unk7
                    + ", "
                    + e.unk8
                    + ", "
                    + e.unk9
                    + ", "
                    + e.unk10
                    + ", "
                    + e.unk11
                    + ", "
                    + e.unk12
                )
            else:
                raise PluginError("Internal error: invalid cutscene list type " + list.listType)
            data.source += "),\n"
    data.source += "\tCS_END(),\n"
    data.source += "};\n\n"
    return data


################################################################################
# Operators and panel
################################################################################


def checkGetFilePaths(context):
    cpath = bpy.path.abspath(context.scene.ootCutsceneExportPath)
    if not cpath.endswith(".c"):
        raise PluginError("Output file must end with .c")
    hpath = cpath[:-1] + "h"
    headerfilename = os.path.basename(hpath)
    return cpath, hpath, headerfilename


class OOT_ExportCutscene(bpy.types.Operator):
    bl_idname = "object.oot_export_cutscene"
    bl_label = "Export Cutscene"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        try:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            activeObj = context.view_layer.objects.active
            if activeObj is None or activeObj.data is not None or activeObj.ootEmptyType != "Cutscene":
                raise PluginError("You must select a cutscene object")
            if activeObj.parent is not None:
                raise PluginError("Cutscene object must not be parented to anything")
            cpath, hpath, headerfilename = checkGetFilePaths(context)
            csdata = ootCutsceneIncludes(headerfilename)
            converted = convertCutsceneObject(activeObj)
            csdata.append(ootCutsceneDataToC(converted, converted.name))
            writeCData(csdata, hpath, cpath)
            self.report({"INFO"}, "Successfully exported cutscene")
            return {"FINISHED"}
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}


class OOT_ExportAllCutscenes(bpy.types.Operator):
    bl_idname = "object.oot_export_all_cutscenes"
    bl_label = "Export All Cutscenes"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        try:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            cpath, hpath, headerfilename = checkGetFilePaths(context)
            csdata = ootCutsceneIncludes(headerfilename)
            count = 0
            for obj in context.view_layer.objects:
                if obj.data is not None or obj.ootEmptyType != "Cutscene":
                    continue
                if obj.parent is not None:
                    raise PluginError("Cutscene object must not be parented to anything")
                converted = convertCutsceneObject(obj)
                csdata.append(ootCutsceneDataToC(converted, converted.name))
                count += 1
            if count == 0:
                raise PluginError("Could not find any cutscenes to export")
            writeCData(csdata, hpath, cpath)
            self.report({"INFO"}, "Successfully exported " + str(count) + " cutscenes")
            return {"FINISHED"}
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}


class OOT_ExportCutscenePanel(OOT_Panel):
    bl_idname = "OOT_PT_export_cutscene"
    bl_label = "OOT Cutscene Exporter"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OOT"

    def draw(self, context):
        col = self.layout.column()
        col.operator(OOT_ExportCutscene.bl_idname)
        col.operator(OOT_ExportAllCutscenes.bl_idname)
        prop_split(col, context.scene, "ootCutsceneExportPath", "File")


oot_cutscene_classes = (
    OOT_ExportCutscene,
    OOT_ExportAllCutscenes,
)

oot_cutscene_panel_classes = (OOT_ExportCutscenePanel,)


def oot_cutscene_panel_register():
    for cls in oot_cutscene_panel_classes:
        register_class(cls)


def oot_cutscene_panel_unregister():
    for cls in oot_cutscene_panel_classes:
        unregister_class(cls)


def oot_cutscene_register():
    for cls in oot_cutscene_classes:
        register_class(cls)

    bpy.types.Scene.ootCutsceneExportPath = bpy.props.StringProperty(name="File", subtype="FILE_PATH")


def oot_cutscene_unregister():
    for cls in reversed(oot_cutscene_classes):
        unregister_class(cls)

    del bpy.types.Scene.ootCutsceneExportPath

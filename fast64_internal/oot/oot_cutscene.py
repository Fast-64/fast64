from ..utility import PluginError, CData, prop_split
from .oot_utility import OOTCollectionAdd, drawCollectionOps, getCutsceneName, getCustomProperty
from .cutscene.operators import OOTCSTextboxAdd, OOTCSListAdd

from .oot_constants import (
    ootEnumCSTextboxType,
    ootEnumCSListType,
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

def ootCutsceneDataToC(csParent, csName):
    # csParent can be OOTCutscene or OOTScene
    data = CData()
    data.header = "extern s32 " + csName + "[];\n"
    data.source = "s32 " + csName + "[] = {\n"
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

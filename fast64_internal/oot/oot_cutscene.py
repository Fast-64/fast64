from ..utility import PluginError, CData
from .oot_utility import getCutsceneName, getCustomProperty

from .oot_constants import (
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

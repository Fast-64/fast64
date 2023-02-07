from ...oot_utility import getCutsceneName, getCustomProperty

from .classes import (
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

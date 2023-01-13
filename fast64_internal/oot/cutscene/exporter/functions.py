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

        listOut.fxType, listOut.fxStartFrame, listOut.fxEndFrame = (
            getCustomProperty(listIn, "fxType"),
            listIn.fxStartFrame,
            listIn.fxEndFrame,
        )

        listData = []
        if listOut.listType == "Textbox":
            for entryIn in listIn.textbox:
                entryOut = OOTCSTextbox()
                entryOut.textboxType = entryIn.textboxType
                entryOut.textID = entryIn.textID
                entryOut.ocarinaAction = getCustomProperty(entryIn, "ocarinaAction")
                entryOut.startFrame = entryIn.startFrame
                entryOut.endFrame = entryIn.endFrame
                entryOut.textboxType = getCustomProperty(entryIn, "csTextType")
                entryOut.topOptionTextID = entryIn.topOptionTextID
                entryOut.bottomOptionTextID = entryIn.bottomOptionTextID
                entryOut.ocarinaMessageId = entryIn.ocarinaMessageId
                listOut.entries.append(entryOut)
        elif listOut.listType == "Lighting":
            for entryIn in listIn.lighting:
                entryOut = OOTCSLighting()
                entryOut.lightSettingsIndex = entryIn.lightSettingsIndex
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
                csSeqPropSuffix = "ID" if listOut.listType != "FadeBGM" else "Player"
                entryOut.csSeqID = getCustomProperty(entryIn, f"csSeq{csSeqPropSuffix}")
                entryOut.startFrame = entryIn.startFrame
                entryOut.endFrame = entryIn.endFrame
                listOut.entries.append(entryOut)
        elif listOut.listType == "Misc":
            for entryIn in listIn.misc:
                entryOut = OOTCSMisc()
                entryOut.csMiscType = getCustomProperty(entryIn, "csMiscType")
                entryOut.startFrame = entryIn.startFrame
                entryOut.endFrame = entryIn.endFrame
                listOut.entries.append(entryOut)
        elif listOut.listType == "Rumble":
            for entryIn in listIn.nine:
                entryOut = OOTCS0x09()
                entryOut.startFrame = entryIn.startFrame
                entryOut.rumbleSourceStrength = entryIn.rumbleSourceStrength
                entryOut.rumbleDuration = entryIn.rumbleDuration
                entryOut.rumbleDecreaseRate = entryIn.rumbleDecreaseRate
                listOut.entries.append(entryOut)
        csParentOut.csLists.append(listOut)


def convertCutsceneObject(obj):
    cs = OOTCutscene()

    cs.name = getCutsceneName(obj)
    csprop = obj.ootCutsceneProperty
    cs.csEndFrame = getCustomProperty(csprop, "csEndFrame")
    cs.csWriteTerminator = getCustomProperty(csprop, "csWriteTerminator")
    cs.csTermIdx = getCustomProperty(csprop, "csDestination")
    cs.csTermStart = getCustomProperty(csprop, "csTermStart")
    cs.csTermEnd = getCustomProperty(csprop, "csTermEnd")
    readCutsceneData(cs, csprop)

    return cs

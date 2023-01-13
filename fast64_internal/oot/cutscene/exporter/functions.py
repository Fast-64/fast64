from ...oot_utility import getCutsceneName, getCustomProperty

from .classes import (
    OOTCSList,
    OOTCSText,
    OOTCSLightSettings,
    OOTCSTime,
    OOTCSSeq,
    OOTCSMisc,
    OOTCSRumble,
    OOTCutscene,
)


def readCutsceneData(csParentOut, csParentIn):
    for listIn in csParentIn.csLists:
        listOut = OOTCSList()
        listOut.listType = listIn.listType

        listOut.transitionType, listOut.transitionStartFrame, listOut.transitionEndFrame = (
            getCustomProperty(listIn, "transitionType"),
            listIn.transitionStartFrame,
            listIn.transitionEndFrame,
        )

        listData = []
        if listOut.listType == "TextList":
            for entryIn in listIn.textList:
                entryOut = OOTCSText()
                entryOut.textboxType = entryIn.textboxType
                entryOut.textID = entryIn.textID
                entryOut.ocarinaAction = getCustomProperty(entryIn, "ocarinaAction")
                entryOut.startFrame = entryIn.startFrame
                entryOut.endFrame = entryIn.endFrame
                entryOut.textType = getCustomProperty(entryIn, "csTextType")
                entryOut.topOptionTextID = entryIn.topOptionTextID
                entryOut.bottomOptionTextID = entryIn.bottomOptionTextID
                entryOut.ocarinaMessageId = entryIn.ocarinaMessageId
                listOut.entries.append(entryOut)
        elif listOut.listType == "LightSettingsList":
            for entryIn in listIn.lightSettingsList:
                entryOut = OOTCSLightSettings()
                entryOut.lightSettingsIndex = entryIn.lightSettingsIndex
                entryOut.startFrame = entryIn.startFrame
                listOut.entries.append(entryOut)
        elif listOut.listType == "TimeList":
            for entryIn in listIn.timeList:
                entryOut = OOTCSTime()
                entryOut.startFrame = entryIn.startFrame
                entryOut.hour = entryIn.hour
                entryOut.minute = entryIn.minute
                listOut.entries.append(entryOut)
        elif listOut.listType in {"StartSeqList", "StopSeqList", "FadeOutSeqList"}:
            for entryIn in listIn.seqList:
                entryOut = OOTCSSeq()
                entryOut.csSeqID = getCustomProperty(entryIn, "csSeqID")
                entryOut.csSeqPlayer = getCustomProperty(entryIn, "csSeqPlayer")
                print(entryOut.csSeqPlayer)
                entryOut.startFrame = entryIn.startFrame
                entryOut.endFrame = entryIn.endFrame
                listOut.entries.append(entryOut)
        elif listOut.listType == "MiscList":
            for entryIn in listIn.miscList:
                entryOut = OOTCSMisc()
                entryOut.csMiscType = getCustomProperty(entryIn, "csMiscType")
                entryOut.startFrame = entryIn.startFrame
                entryOut.endFrame = entryIn.endFrame
                listOut.entries.append(entryOut)
        elif listOut.listType == "RumbleList":
            for entryIn in listIn.rumbleList:
                entryOut = OOTCSRumble()
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

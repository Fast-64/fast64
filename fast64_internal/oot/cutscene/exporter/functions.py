from ...oot_utility import getCustomProperty
from ...oot_constants import ootData

from .classes import (
    OOTCSList,
    OOTCSText,
    OOTCSLightSettings,
    OOTCSTime,
    OOTCSSeq,
    OOTCSMisc,
    OOTCSRumble,
)


def readCutsceneData(csParentOut, csParentIn):
    for listIn in csParentIn.csLists:
        listOut = OOTCSList()
        listOut.listType = listIn.listType

        value = getCustomProperty(listIn, "transitionType")
        listOut.transitionType, listOut.transitionStartFrame, listOut.transitionEndFrame = (
            ootData.enumData.enumByKey["csTransitionType"].itemByKey[value] if value != "Custom" else value,
            listIn.transitionStartFrame,
            listIn.transitionEndFrame,
        )

        listData = []
        if listOut.listType == "TextList":
            for entryIn in listIn.textList:
                entryOut = OOTCSText()
                entryOut.textboxType = entryIn.textboxType
                entryOut.textID = entryIn.textID

                value = getCustomProperty(entryIn, "ocarinaAction")
                entryOut.ocarinaAction = (
                    ootData.enumData.enumByKey["ocarinaSongActionId"].itemByKey[value] if value != "Custom" else value
                )

                entryOut.startFrame = entryIn.startFrame
                entryOut.endFrame = entryIn.endFrame

                value = getCustomProperty(entryIn, "csTextType")
                entryOut.textType = (
                    ootData.enumData.enumByKey["csTextType"].itemByKey[value] if value != "Custom" else value
                )

                if entryOut.textType == "choice":
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

                value = getCustomProperty(entryIn, "csSeqPlayer")
                entryOut.csSeqPlayer = (
                    ootData.enumData.enumByKey["csFadeOutSeqPlayer"].itemByKey[value] if value != "Custom" else value
                )

                entryOut.startFrame = entryIn.startFrame
                entryOut.endFrame = entryIn.endFrame
                listOut.entries.append(entryOut)
        elif listOut.listType == "MiscList":
            for entryIn in listIn.miscList:
                entryOut = OOTCSMisc()
                value = getCustomProperty(entryIn, "csMiscType")
                entryOut.csMiscType = (
                    ootData.enumData.enumByKey["csMiscType"].itemByKey[value] if value != "Custom" else value
                )
                entryOut.startFrame = entryIn.startFrame
                entryOut.endFrame = entryIn.endFrame
                listOut.entries.append(entryOut)
        elif listOut.listType == "RumbleList":
            for entryIn in listIn.rumbleList:
                entryOut = OOTCSRumble()
                entryOut.startFrame = entryIn.startFrame
                entryOut.rumbleSourceStrength = entryIn.rumbleSourceStrength

                # the duration's unit are vertical retraces, this happens 3 times per frame
                # so we're multiplying the value by 3 to get a frame unit on the UI
                # to keep consistency between start frame and duration
                entryOut.rumbleDuration = entryIn.rumbleDuration * 3

                entryOut.rumbleDecreaseRate = entryIn.rumbleDecreaseRate
                listOut.entries.append(entryOut)
        csParentOut.csLists.append(listOut)

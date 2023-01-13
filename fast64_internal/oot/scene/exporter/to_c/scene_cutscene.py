from .....utility import CData, PluginError, indent
from ....oot_level_classes import OOTScene
from ....cutscene.constants import ootEnumCSTextboxTypeEntryC, ootEnumCSListTypeListC, ootEnumCSListTypeEntryC
from ....cutscene.exporter import OOTCutscene


def ootCutsceneDataToC(csParent: OOTCutscene | OOTScene, csName: str):
    csData = CData()
    arrayName = f"CutsceneData {csName}[]"
    nentries = len(csParent.csLists) + (1 if csParent.csUseDestination else 0)

    # .h
    csData.header = f"extern {arrayName};\n"

    # .c
    csData.source = (
        arrayName
        + " = {\n"
        + (indent + f"CS_BEGIN_CUTSCENE({nentries}, {csParent.csEndFrame}),\n")
        + (
            (indent * 2) + f"CS_DESTINATION({csParent.csDestination}, {csParent.csDestinationStartFrame}, 0),\n"
            if csParent.csUseDestination
            else ""
        )
    )

    for list in csParent.csLists:
        # CS "XXXX List" Command
        csData.source += (
            (indent * 2)
            + ootEnumCSListTypeListC[list.listType]
            + "("
            + (
                f"{list.transitionType}, {list.transitionStartFrame}, {list.transitionEndFrame}"
                if list.listType == "Transition"
                else str(len(list.entries))
            )
            + "),\n"
        )

        for e in list.entries:
            csData.source += (
                indent * 3
                + (
                    ootEnumCSTextboxTypeEntryC[e.textboxType]
                    # @TODO make a separate variable for ``ootEnumCSListTypeEntryC``
                    if list.listType == "TextList"
                    else ootEnumCSListTypeEntryC[list.listType.replace("List", "")]
                )
                + "("
            )

            if list.listType == "TextList":
                if e.textboxType == "Text":
                    csData.source += f"{e.textID}, {e.startFrame}, {e.endFrame}, {e.textType}, {e.topOptionTextID}, {e.bottomOptionTextID}"

                elif e.textboxType == "None":
                    csData.source += f"{e.startFrame}, {e.endFrame}"

                elif e.textboxType == "OcarinaAction":
                    csData.source += f"{e.ocarinaAction}, {e.startFrame}, {e.endFrame}, {e.ocarinaMessageId}"

            elif list.listType == "LightSettingsList":
                # the endFrame variable is not used in the implementation of the commend
                # so the value doesn't matter
                csData.source += f"{e.lightSettingsIndex}, {e.startFrame}" + (", 0" * 9)

            elif list.listType == "TimeList":
                # same as above
                csData.source += f"0, {e.startFrame}, 0, {e.hour}, {e.minute}"

            elif list.listType == "RumbleList":
                # same as above
                csData.source += (
                    f"0, {e.startFrame}, 0, {e.rumbleSourceStrength}, {e.rumbleDuration}, {e.rumbleDecreaseRate}, 0, 0"
                )

            elif list.listType in ["StartSeqList", "StopSeqList", "FadeOutSeqList"]:
                endFrame = e.endFrame if list.listType == "FadeOutSeqList" else "0"
                firstArg = e.csSeqPlayer if list.listType == "FadeOutSeqList" else e.csSeqID
                csData.source += f"{firstArg}, {e.startFrame}, {endFrame}" + (", 0" * 8)

            elif list.listType == "MiscList":
                csData.source += f"{e.csMiscType}, {e.startFrame}, {e.endFrame}" + (", 0" * 11)

            else:
                raise PluginError("Internal error: invalid cutscene list type " + list.listType)

            csData.source += "),\n"

    csData.source += indent + "CS_END(),\n};\n\n"
    return csData


def getSceneCutscenes(outScene: OOTScene):
    cutscenes: list[CData] = []
    altHeaders = [outScene, outScene.childNightHeader, outScene.adultDayHeader, outScene.adultNightHeader]
    altHeaders.extend(outScene.cutsceneHeaders)

    for i, curHeader in enumerate(altHeaders):
        # curHeader is either None or an OOTScene. This can either be the main scene itself,
        # or one of the alternate / cutscene headers.
        if curHeader is not None and curHeader.writeCutscene:
            if curHeader.csWriteType == "Embedded":
                cutscenes.append(ootCutsceneDataToC(curHeader, curHeader.cutsceneDataName(i)))
            elif curHeader.csWriteType == "Object":
                cutscenes.append(ootCutsceneDataToC(curHeader.csWriteObject, curHeader.csWriteObject.name))

    for extraCs in outScene.extraCutscenes:
        cutscenes.append(ootCutsceneDataToC(extraCs, extraCs.name))

    return cutscenes

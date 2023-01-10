from .....utility import CData, PluginError, indent
from ....oot_level_classes import OOTScene
from ....cutscene.constants import ootEnumCSTextboxTypeEntryC, ootEnumCSListTypeListC, ootEnumCSListTypeEntryC
from ....cutscene.exporter import OOTCutscene


def ootCutsceneDataToC(csParent: OOTCutscene | OOTScene, csName: str):
    csData = CData()
    arrayName = f"CutsceneData {csName}[]"
    nentries = len(csParent.csLists) + (1 if csParent.csWriteTerminator else 0)

    # .h
    csData.header = f"extern {arrayName};\n"

    # .c
    csData.source = (
        arrayName + " = {\n"
        + (indent + f"CS_BEGIN_CUTSCENE({nentries}, {csParent.csEndFrame}),\n")
        + (
            (indent * 2) + f"CS_DESTINATION({csParent.csTermIdx}, {csParent.csTermStart}, {csParent.csTermEnd}),\n"
            if csParent.csWriteTerminator else ""
        )
    )

    for list in csParent.csLists:
        # CS "XXXX List" Command
        csData.source += (
            (indent * 2) + ootEnumCSListTypeListC[list.listType] + "("
            + (
                f"{list.fxType}, {list.fxStartFrame}, {list.fxEndFrame}"
                if list.listType == "FX" else str(len(list.entries))
            )
            + "),\n"
        )

        for e in list.entries:
            csData.source += (
                indent * 3
                + (
                    ootEnumCSTextboxTypeEntryC[e.textboxType]
                    if list.listType == "Textbox" else ootEnumCSListTypeEntryC[list.listType]
                )
                + "("
            )

            if list.listType == "Textbox":
                if e.textboxType == "Text":
                    csData.source += (
                        f"{e.messageId}, {e.startFrame}, {e.endFrame}, {e.type}, {e.topOptionBranch}, {e.bottomOptionBranch}"
                    )

                elif e.textboxType == "None":
                    csData.source += f"{e.startFrame}, {e.endFrame}"

                elif e.textboxType == "LearnSong":
                    csData.source += f"{e.ocarinaSongAction}, {e.startFrame}, {e.endFrame}, {e.ocarinaMessageId}"

            elif list.listType == "Lighting":
                # the endFrame variable is not used in the implementation of the commend
                # so the value doesn't matter
                csData.source += f"{e.index}, {e.startFrame}" + (", 0" * 9)

            elif list.listType == "Time":
                # same as above
                csData.source += f"0, {e.startFrame}, 0, {e.hour}, {e.minute}"

            elif list.listType == "0x09": # rumble command
                # same as above
                csData.source += f"0, {e.startFrame}, 0, {e.unk2}, {e.unk3}, {e.unk4}, 0, 0"

            elif list.listType in ["PlayBGM", "StopBGM", "FadeBGM"]:
                endFrame = e.endFrame if list.listType == "FadeBGM" else "0"
                csData.source += f"{e.value}, {e.startFrame}, {endFrame}" + (", 0" * 8)

            elif list.listType == "Misc":
                csData.source += f"{e.operation}, {e.startFrame}, {e.endFrame}" + (", 0" * 11)

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

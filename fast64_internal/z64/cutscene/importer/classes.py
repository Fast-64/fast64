import bpy
import re

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING
from bpy.types import Object, Armature
from ....utility import PluginError
from ...utility import is_oot_features
from ..motion.utility import setupCutscene, getBlenderPosition, getInteger

if TYPE_CHECKING:
    from ..properties import OOTCSListProperty, OOTCutsceneProperty

from ..constants import (
    ootCSLegacyToNewCmdNames,
    ootCSListCommands,
    ootCutsceneCommandsC,
    ootCSListEntryCommands,
    ootCSSingleCommands,
    ootCSListAndSingleCommands,
)

from ..classes import (
    CutsceneObjectFactory,
)

# TODO: move these classes to a common place outside the exporter
from ...exporter.utility import Utility
from ...exporter.cutscene import Cutscene, CutsceneData
from ...exporter.cutscene.actor_cue import CutsceneCmdActorCueList, CutsceneCmdActorCue
from ...exporter.cutscene.text import (
    CutsceneCmdTextList,
    CutsceneCmdText,
    CutsceneCmdTextNone,
    CutsceneCmdTextOcarinaAction,
)

from ...exporter.cutscene.seq import (
    CutsceneCmdStartStopSeqList,
    CutsceneCmdFadeSeqList,
    CutsceneCmdStartStopSeq,
    CutsceneCmdFadeSeq,
    CutsceneCmdModifySeq,
    CutsceneCmdModifySeqList,
    CutsceneCmdStartAmbience,
    CutsceneCmdStartAmbienceList,
    CutsceneCmdFadeOutAmbience,
    CutsceneCmdFadeOutAmbienceList,
)

from ...exporter.cutscene.misc import (
    CutsceneCmdLightSetting,
    CutsceneCmdTime,
    CutsceneCmdMisc,
    CutsceneCmdRumbleController,
    CutsceneCmdDestination,
    CutsceneCmdMiscList,
    CutsceneCmdRumbleControllerList,
    CutsceneCmdTransition,
    CutsceneCmdTransitionList,
    CutsceneCmdLightSettingList,
    CutsceneCmdTimeList,
    CutsceneCmdMotionBlur,
    CutsceneCmdMotionBlurList,
    CutsceneCmdChooseCreditsScenes,
    CutsceneCmdChooseCreditsScenesList,
    CutsceneCmdTransitionGeneral,
    CutsceneCmdTransitionGeneralList,
    CutsceneCmdGiveTatl,
)

from ...exporter.cutscene.camera import (
    CutsceneCmdCamPoint,
    CutsceneCmdCamEyeSpline,
    CutsceneCmdCamATSpline,
    CutsceneCmdCamEyeSplineRelToPlayer,
    CutsceneCmdCamATSplineRelToPlayer,
    CutsceneCmdCamEye,
    CutsceneCmdCamAT,
    CutsceneCmdNewCamPoint,
    CutsceneCmdCamMisc,
    CutsceneSplinePoint,
    CutsceneCmdCamSpline,
    CutsceneCmdCamSplineList,
)

cmdToClass = {
    "CS_CAM_POINT": CutsceneCmdCamPoint,
    "CS_MISC": CutsceneCmdMisc,
    "CS_LIGHT_SETTING": CutsceneCmdLightSetting,
    "CS_TIME": CutsceneCmdTime,
    "CS_FADE_OUT_SEQ": CutsceneCmdFadeSeq,
    "CS_RUMBLE_CONTROLLER": CutsceneCmdRumbleController,
    "CS_TEXT": CutsceneCmdText,
    "CS_TEXT_NONE": CutsceneCmdTextNone,
    "CS_TEXT_OCARINA_ACTION": CutsceneCmdTextOcarinaAction,
    "CS_START_SEQ": CutsceneCmdStartStopSeq,
    "CS_STOP_SEQ": CutsceneCmdStartStopSeq,
    "CS_ACTOR_CUE": CutsceneCmdActorCue,
    "CS_PLAYER_CUE": CutsceneCmdActorCue,
    "CS_CAM_EYE_SPLINE": CutsceneCmdCamEyeSpline,
    "CS_CAM_AT_SPLINE": CutsceneCmdCamATSpline,
    "CS_CAM_EYE_SPLINE_REL_TO_PLAYER": CutsceneCmdCamEyeSplineRelToPlayer,
    "CS_CAM_AT_SPLINE_REL_TO_PLAYER": CutsceneCmdCamATSplineRelToPlayer,
    "CS_CAM_EYE": CutsceneCmdCamEye,
    "CS_CAM_AT": CutsceneCmdCamAT,
    "CS_MISC_LIST": CutsceneCmdMiscList,
    "CS_TRANSITION": CutsceneCmdTransition,
    "CS_TEXT_LIST": CutsceneCmdTextList,
    "CS_LIGHT_SETTING_LIST": CutsceneCmdLightSettingList,
    "CS_TIME_LIST": CutsceneCmdTimeList,
    "CS_FADE_OUT_SEQ_LIST": CutsceneCmdFadeSeqList,
    "CS_RUMBLE_CONTROLLER_LIST": CutsceneCmdRumbleControllerList,
    "CS_START_SEQ_LIST": CutsceneCmdStartStopSeqList,
    "CS_STOP_SEQ_LIST": CutsceneCmdStartStopSeqList,
    "CS_ACTOR_CUE_LIST": CutsceneCmdActorCueList,
    "CS_PLAYER_CUE_LIST": CutsceneCmdActorCueList,
    "CS_DESTINATION": CutsceneCmdDestination,
    # from new system
    "CS_CAM_SPLINE_LIST": CutsceneCmdCamSplineList,
    "CS_CAM_SPLINE": CutsceneCmdCamSpline,
    "CS_CAM_POINT_NEW": CutsceneCmdNewCamPoint,
    "CS_CAM_MISC": CutsceneCmdCamMisc,
    "CS_TRANSITION_LIST": CutsceneCmdTransitionList,
    "CS_TEXT_DEFAULT": CutsceneCmdText,
    "CS_TEXT_TYPE_1": CutsceneCmdText,
    "CS_TEXT_TYPE_3": CutsceneCmdText,
    "CS_TEXT_BOSSES_REMAINS": CutsceneCmdText,
    "CS_TEXT_ALL_NORMAL_MASKS": CutsceneCmdText,
    "CS_MOTION_BLUR_LIST": CutsceneCmdMotionBlurList,
    "CS_MOTION_BLUR": CutsceneCmdMotionBlur,
    "CS_MODIFY_SEQ_LIST": CutsceneCmdModifySeqList,
    "CS_MODIFY_SEQ": CutsceneCmdModifySeq,
    "CS_CHOOSE_CREDITS_SCENES_LIST": CutsceneCmdChooseCreditsScenesList,
    "CS_CHOOSE_CREDITS_SCENES": CutsceneCmdChooseCreditsScenes,
    "CS_TRANSITION_GENERAL_LIST": CutsceneCmdTransitionGeneralList,
    "CS_TRANSITION_GENERAL": CutsceneCmdTransitionGeneral,
    "CS_GIVE_TATL": CutsceneCmdGiveTatl,
}


@dataclass
class ParsedCutscene:
    """Local class used to order the parsed cutscene properly"""

    csName: str
    csData: list[str]  # contains every command lists or standalone ones like ``CS_TRANSITION()``


@dataclass
class PropertyData:
    listType: str
    subPropsData: dict[str, str]
    useEndFrame: bool


@dataclass
class CutsceneImport(CutsceneObjectFactory):
    """This class contains functions to create the new cutscene Blender data"""

    filePath: Optional[str]  # used when importing from the panel
    fileData: Optional[str]  # used when importing the cutscenes when importing a scene
    csName: Optional[str]  # used when import a specific cutscene
    new_cs_system: bool

    def getCmdParams(self, data: str, cmdName: str, paramNumber: int):
        """Returns the list of every parameter of the given command"""

        # kinda hacky but better than duplicating the classes
        if self.new_cs_system:
            if cmdName in {"CS_START_SEQ", "CS_FADE_OUT_SEQ", "CS_LIGHT_SETTING"}:
                paramNumber = 3
            elif cmdName in {"CS_MISC", "CS_STOP_SEQ", "CS_TEXT_ALL_NORMAL_MASKS"}:
                paramNumber = 4
            elif cmdName in {"CS_TEXT_DEFAULT", "CS_TEXT_TYPE_1", "CS_TEXT_TYPE_3", "CS_TEXT_BOSSES_REMAINS"}:
                paramNumber = 5
            elif cmdName in {"CS_RUMBLE_CONTROLLER"}:
                paramNumber = 6

        parenthesis = "(" if not cmdName.endswith("(") else ""
        data = data.strip().removeprefix(f"{cmdName}{parenthesis}").replace(" ", "").removesuffix(")")
        if "CS_FLOAT" in data:
            data = re.sub(r"CS_FLOAT\([a-fA-F0-9x]*,([0-9e+-.f]*)\)", r"\1", data, re.DOTALL)
            data = re.sub(r"CS_FLOAT\([a-fA-F0-9x]*,([0-9e+-.f]*)", r"\1", data, re.DOTALL)
        params = data.split(",")
        validTimeCmd = cmdName == "CS_TIME" and len(params) == 6 and paramNumber == 5
        if len(params) != paramNumber and not validTimeCmd:
            raise PluginError(
                f"ERROR: The number of expected parameters for `{cmdName}` "
                + "and the number of found ones is not the same!"
            )
        return params

    def getNewCutscene(self, csData: str, name: str, use_macros: bool, motion_only: bool):
        params = self.getCmdParams(csData, "CS_HEADER", Cutscene.paramNumber)
        new_cs = Cutscene.new(name, None, use_macros, motion_only)
        new_cs.totalEntries = getInteger(params[0])
        new_cs.frameCount = getInteger(params[1])
        return new_cs

    def correct_command_lists(self, command: str):
        """If using the new cs system, moves standalone commands to the proper lists"""
        if self.new_cs_system:
            if command in ootCSSingleCommands:
                ootCSSingleCommands.remove(command)
            if command in ootCSListAndSingleCommands:
                ootCSListAndSingleCommands.remove(command)
            if command not in ootCSListEntryCommands:
                ootCSListEntryCommands.append(command)

    def getParsedCutscenes(self):
        """Returns the parsed commands read from every cutscene we can find"""

        fileData = ""

        if self.fileData is not None:
            fileData = self.fileData
        elif self.filePath is not None:
            with open(self.filePath, "r") as inputFile:
                fileData = inputFile.read()
        else:
            raise PluginError("ERROR: File data can't be found!")

        self.correct_command_lists("CS_TRANSITION")
        self.correct_command_lists("CS_DESTINATION")

        # replace old names
        oldNames = list(ootCSLegacyToNewCmdNames.keys())
        fileData = fileData.replace("CS_CMD_CONTINUE", "CS_CAM_CONTINUE")
        fileData = fileData.replace("CS_CMD_STOP", "CS_CAM_STOP")
        for oldName in oldNames:
            fileData = fileData.replace(f"{oldName}(", f"{ootCSLegacyToNewCmdNames[oldName]}(")

        # handle conflicts between the cs system of OoT and MM
        if self.new_cs_system:
            fileData = fileData.replace("CS_CAM_POINT", "CS_CAM_POINT_NEW")
            fileData = fileData.replace("CS_RUMBLE", "CS_RUMBLE_CONTROLLER")

        # make a list of existing cutscene names, to skip importing them if found
        existingCutsceneNames = [
            csObj.name.removeprefix("Cutscene.")
            for csObj in bpy.data.objects
            if csObj.type == "EMPTY" and csObj.ootEmptyType == "Cutscene"
        ]

        fileLines: list[str] = []
        for line in fileData.split("\n"):
            fileLines.append(line.strip())

        # parse cutscenes
        csData = []
        cutsceneList: list[list[str]] = []
        foundCutscene = False
        for line in fileLines:
            if not line.startswith("//") and not line.startswith("/*"):
                if "CutsceneData " in line:
                    # split with "[" just in case the array has a set size
                    csName = line.split(" ")[1].split("[")[0]
                    if csName in existingCutsceneNames:
                        print(f"WARNING: Cutscene '{csName}' already exists in this blend's data.")
                    foundCutscene = True
                    print(f"INFO: Found cutscene '{csName}' in the file data.")

                if foundCutscene:
                    sLine = line.strip()
                    csCmd = sLine.split("(")[0]
                    if "CutsceneData " not in line and "};" not in line and csCmd not in ootCutsceneCommandsC:
                        if len(csData) > 0:
                            csData[-1] += line

                    if len(csData) == 0 or sLine.startswith("CS_") and not sLine.startswith("CS_FLOAT"):
                        if self.csName is None or self.csName == csName:
                            csData.append(line)

                    if "};" in line:
                        foundCutscene = False
                        if len(csData) > 0:
                            cutsceneList.append(csData)
                        csData = []

        if len(cutsceneList) == 0:
            print("INFO: Found no cutscenes in this file!")
            return None

        # parse the commands from every cutscene we found
        parsedCutscenes: list[ParsedCutscene] = []
        for cutscene in cutsceneList:
            cmdListFound = False
            curCmdPrefix = None
            parsedCS = []
            parsedData = ""
            csName = None

            for line in cutscene:
                curCmd = line.strip().split("(")[0]
                index = cutscene.index(line) + 1
                nextCmd = cutscene[index].strip().split("(")[0] if index < len(cutscene) else None
                line = line.strip()
                if "CutsceneData" in line:
                    csName = line.split(" ")[1][:-2]

                # NOTE: ``CS_UNK_DATA()`` are commands that are completely useless, so we're ignoring those
                if csName is not None and not "CS_UNK_DATA" in curCmd:
                    if curCmd in ootCutsceneCommandsC:
                        line = line.removesuffix(",") + "\n"

                        if curCmd in ootCSSingleCommands and curCmd != "CS_END_OF_SCRIPT":
                            parsedData += line

                        if not cmdListFound and curCmd in ootCSListCommands:
                            cmdListFound = True
                            parsedData = ""

                            # camera and lighting have "non-standard" list names
                            if curCmd.startswith("CS_CAM"):
                                curCmdPrefix = "CS_CAM"
                            elif curCmd.startswith("CS_LIGHT") or curCmd.startswith("L_CS_LIGHT"):
                                curCmdPrefix = "CS_LIGHT"
                            else:
                                curCmdPrefix = curCmd[:-5]

                        if curCmdPrefix is not None:
                            if curCmdPrefix in curCmd:
                                parsedData += line
                            elif not cmdListFound and curCmd in ootCSListEntryCommands:
                                print(f"{csName}, command:\n{line}")
                                raise PluginError(f"ERROR: Found a list entry outside a list inside ``{csName}``!")

                        if cmdListFound and nextCmd == "CS_END_OF_SCRIPT" or nextCmd in ootCSListAndSingleCommands:
                            cmdListFound = False
                            parsedCS.append(parsedData)
                            parsedData = ""
                    elif not "CutsceneData" in curCmd and not "};" in curCmd:
                        print(f"WARNING: Unknown command found: ``{curCmd}``")
                        cmdListFound = False

            if csName is not None and len(parsedCS) > 0:
                parsedCutscenes.append(ParsedCutscene(csName, parsedCS))
            else:
                raise PluginError("ERROR: Something wrong happened during the parsing of the cutscene.")

        return parsedCutscenes

    def getCutsceneList(self, use_macros: bool, motion_only: bool):
        """Returns the list of cutscenes with the data processed"""

        parsedCutscenes = self.getParsedCutscenes()

        if parsedCutscenes is None:
            # if it's none then there's no cutscene in the file
            return None

        if len(parsedCutscenes) == 0:
            raise PluginError("ERROR: No cutscene was found.")

        cutsceneList: list[Cutscene] = []

        # for each cutscene from the list returned by getParsedCutscenes(),
        # create classes containing the cutscene's informations
        # that will be used later when creating Blender objects to complete the import
        for parsedCS in parsedCutscenes:
            cutscene = None

            for data in parsedCS.csData:
                cmdData = data.removesuffix("\n").split("\n")
                cmdListData = cmdData.pop(0)
                cmdListName = cmdListData.strip().split("(")[0]

                if cmdListName == "CS_HEADER":
                    # create a new cutscene data
                    cutscene = self.getNewCutscene(data, parsedCS.csName, use_macros, motion_only)
                elif cutscene is not None and data.startswith(f"{cmdListName}("):
                    # if we have a cutscene, create and add the commands data in it
                    isPlayer = cmdListData.startswith("CS_PLAYER_CUE_LIST(")
                    isStartSeq = cmdListData.startswith("CS_START_SEQ_LIST(")
                    isStopSeq = cmdListData.startswith("CS_STOP_SEQ_LIST(")

                    cs_list_raw_cmd = cmdToClass.get(cmdListName)
                    if cs_list_raw_cmd is not None:
                        cmdList = getattr(cutscene.data, "playerCueList" if isPlayer else cs_list_raw_cmd.listName)

                        paramNumber = cs_list_raw_cmd.paramNumber - 1 if isPlayer else cs_list_raw_cmd.paramNumber
                        params = self.getCmdParams(cmdListData, cmdListName, paramNumber)

                        if isStartSeq or isStopSeq:
                            new_cs_list_data = cs_list_raw_cmd.from_params(
                                params, type="start" if isStartSeq else "stop"
                            )
                        elif cmdListData.startswith("CS_ACTOR_CUE_LIST(") or isPlayer:
                            new_cs_list_data = cs_list_raw_cmd.from_params(params, isPlayer=isPlayer)
                        else:
                            new_cs_list_data = cs_list_raw_cmd.from_params(params)

                        # treating camera commands separately if using the new cs commands
                        # as it became more complex to parse since it's basically a list in a list in a list
                        if self.new_cs_system and "CAM" in cmdListName:
                            foundEndCmd = False
                            cur_point = 0
                            at_list: list[CutsceneCmdNewCamPoint] = []
                            eye_list: list[CutsceneCmdNewCamPoint] = []
                            misc_list: list[CutsceneCmdCamMisc] = []
                            cur_spline_entry: Optional[CutsceneCmdCamSpline] = None
                            for d in cmdData:
                                cmdEntryName = d.strip().split("(")[0]

                                if foundEndCmd:
                                    raise ValueError("ERROR: More camera commands after last one!")

                                if "CS_CAM_END" in d:
                                    foundEndCmd = True
                                    continue

                                entryCmd = cmdToClass[cmdEntryName]
                                params = self.getCmdParams(d, cmdEntryName, entryCmd.paramNumber)
                                listEntry = entryCmd.from_params(params)

                                if cmdEntryName == "CS_CAM_SPLINE":
                                    cur_spline_entry = listEntry
                                elif cur_spline_entry is not None:
                                    cs_data_entry_base = cmdToClass[cmdEntryName]
                                    sub_params = self.getCmdParams(d, cmdEntryName, cs_data_entry_base.paramNumber)

                                    if cur_point < cur_spline_entry.num_entries:
                                        at_list.append(cs_data_entry_base.from_params(sub_params))
                                        cur_point += 1
                                    elif cur_point < cur_spline_entry.num_entries * 2:
                                        eye_list.append(cs_data_entry_base.from_params(sub_params))
                                        cur_point += 1
                                    elif cur_point < cur_spline_entry.num_entries * 3:
                                        misc_list.append(cs_data_entry_base.from_params(sub_params))
                                        cur_point += 1

                                    if cur_point == cur_spline_entry.num_entries * 3:
                                        assert len(at_list) == len(eye_list) == len(misc_list)

                                        for i, (at, eye, misc) in enumerate(zip(at_list, eye_list, misc_list)):
                                            if i < len(at_list) - 1:
                                                # ignore the last points, see the exporter to know why
                                                cur_spline_entry.entries.append(CutsceneSplinePoint(at, eye, misc))

                                        new_cs_list_data.entries.append(cur_spline_entry)
                                        cur_point = 0
                                        at_list.clear()
                                        eye_list.clear()
                                        misc_list.clear()
                                        cur_spline_entry = None
                                else:
                                    raise ValueError("ERROR: Invalid number of entries.")
                        elif cmdListName != "CS_TRANSITION" and cmdListName != "CS_DESTINATION":
                            # this condition still works for both versions since the list name actually ends with "_LIST",
                            # same thing in the next if/else block when it adds the data to the `Cutscene` class

                            foundEndCmd = False
                            for d in cmdData:
                                cmdEntryName = d.strip().split("(")[0]
                                isLegacy = d.startswith("L_")
                                if isLegacy:
                                    cmdEntryName = cmdEntryName.removeprefix("L_")
                                    d = d.removeprefix("L_")

                                if "CAM" in cmdListName:
                                    flag = d.removeprefix("CS_CAM_POINT(").split(",")[0]
                                    if foundEndCmd:
                                        raise PluginError("ERROR: More camera commands after last one!")
                                    foundEndCmd = "CS_CAM_STOP" in flag or "-1" in flag

                                entryCmd = cmdToClass[cmdEntryName]
                                params = self.getCmdParams(d, cmdEntryName, entryCmd.paramNumber)

                                if "CS_LIGHT_SETTING(" in d:
                                    listEntry = entryCmd.from_params(params, isLegacy)
                                elif isPlayer:
                                    listEntry = entryCmd.from_params(params, True)
                                elif isStartSeq or isStopSeq:
                                    listEntry = entryCmd.from_params(
                                        params, "start" if isStartSeq else "stop", isLegacy
                                    )
                                else:
                                    listEntry = entryCmd.from_params(params)
                                new_cs_list_data.entries.append(listEntry)
                        if cmdListName == "CS_DESTINATION":
                            cutscene.data.destination = new_cs_list_data
                        else:
                            cmdList.append(new_cs_list_data)
                    else:
                        print(f"WARNING: `{cmdListName}` is not implemented yet!")

            # after processing the commands we can add the cutscene to the cutscene list
            if cutscene is not None:
                cutsceneList.append(cutscene)
        return cutsceneList

    def setActorCueData(self, csObj: Object, actorCueList: list[CutsceneCmdActorCueList], cueName: str, csNbr: int):
        """Creates the objects from the Actor Cue List data"""

        cueObjList = []
        cueEndFrames = []
        for i, entry in enumerate(actorCueList, 1):
            if len(entry.entries) == 0:
                raise PluginError("ERROR: Actor Cue List does not have any Actor Cue!")

            lastFrame = lastPos = None
            actorCueListObj = self.getNewActorCueListObject(
                f"CS_{csNbr:02}.{cueName} Cue List {i:02}", entry.commandType, csObj
            )

            for j, actorCue in enumerate(entry.entries, 1):
                if lastFrame is not None and lastFrame != actorCue.startFrame:
                    raise PluginError("ERROR: Actor Cues are not temporally continuous!")

                if lastPos is not None and lastPos != actorCue.startPos:
                    raise PluginError("ERROR: Actor Cues are not spatially continuous!")

                cueObjList.append(
                    self.getNewActorCueObject(
                        f"CS_{csNbr:02}.{cueName} Cue {i}.{j:02}",
                        actorCue.startFrame,
                        actorCue.actionID,
                        actorCue.startPos,
                        actorCue.rot,
                        actorCueListObj,
                    )
                )
                lastFrame = actorCue.endFrame
                lastPos = actorCue.endPos
                cueEndFrames.append(lastFrame)

            # we need a dummy actor cue to get the end position of the last real one
            if lastFrame is not None:
                cueObjList.append(
                    self.getNewActorCueObject(
                        f"CS_{csNbr:02}.{cueName} Cue {i}.999 (D)",
                        lastFrame,
                        "DUMMY",
                        lastPos,
                        actorCue.rot,
                        actorCueListObj,
                    )
                )
                cueEndFrames.append(lastFrame + 1)

        # updating the end frames
        if len(cueEndFrames) != len(cueObjList):
            raise PluginError("ERROR: Lists lengths do not match!")

        for obj, endFrame in zip(cueObjList, cueEndFrames):
            # reading this value will trigger the "get" function
            getEndFrame = obj.ootCSMotionProperty.actorCueProp.cueEndFrame

            if endFrame != getEndFrame and obj.ootEmptyType != "CS Dummy Cue":
                print(f"WARNING: `{obj.name}`'s end frame do not match the one from the script!")

    def validateCameraData(self, cutscene: Cutscene):
        """Safety checks to make sure the camera data is correct"""

        camLists: list[tuple[str, list, list]] = [
            ("Eye and AT Spline", cutscene.data.camEyeSplineList, cutscene.data.camATSplineList),
            (
                "Eye and AT Spline Rel to Player",
                cutscene.data.camEyeSplineRelPlayerList,
                cutscene.data.camATSplineRelPlayerList,
            ),
            ("Eye and AT", cutscene.data.camEyeList, cutscene.data.camATList),
        ]

        for camType, eyeList, atList in camLists:
            for eyeListEntry, atListEntry in zip(eyeList, atList):
                eyeTotal = len(eyeListEntry.entries)
                atTotal = len(atListEntry.entries)

                # Eye -> bone's head, AT -> bone's tail, that's why both lists requires the same length
                if eyeTotal != atTotal:
                    raise PluginError(f"ERROR: Found {eyeTotal} Eye lists but {atTotal} AT lists in {camType}!")

                if eyeTotal < 4:
                    raise PluginError(f"ERROR: Only {eyeTotal} cam point in this command!")

                if eyeTotal > 4:
                    # NOTE: There is a bug in the game where when incrementing to the next set of key points,
                    # the key point which checked for whether it's the last point or not is the last point
                    # of the next set, not the last point of the old set. This means we need to remove
                    # the extra point at the end that will only tell the game that this camera shot stops.
                    del eyeListEntry.entries[-1]
                    del atListEntry.entries[-1]

    def setBoneData(
        self, cameraShotObj: Object, boneData: list[tuple[CutsceneCmdCamPoint, CutsceneCmdCamPoint]], csNbr: int
    ):
        """Creates the bones from the Camera Point data"""

        scale = bpy.context.scene.ootBlenderScale
        for i, (eyePoint, atPoint) in enumerate(boneData, 1):
            # we need the edit mode to be able to change the bone's location
            bpy.ops.object.mode_set(mode="EDIT")
            armatureData: Armature = cameraShotObj.data
            boneName = f"CS_{csNbr:02}.Camera Point {i:02}"
            newEditBone = armatureData.edit_bones.new(boneName)
            newEditBone.head = getBlenderPosition(eyePoint.pos, scale)
            newEditBone.tail = getBlenderPosition(atPoint.pos, scale)
            bpy.ops.object.mode_set(mode="OBJECT")
            newBone = armatureData.bones[boneName]

            if eyePoint.frame != 0:
                print("WARNING: Frames must be 0!")

            # using the "AT" (look-at) data since this is what determines where the camera is looking
            # the "Eye" only sets the location of the camera
            newBone.ootCamShotPointProp.shotPointFrame = atPoint.frame
            newBone.ootCamShotPointProp.shotPointViewAngle = atPoint.viewAngle
            newBone.ootCamShotPointProp.shotPointRoll = atPoint.camRoll

    def setCameraShotData(
        self, csObj: Object, eyePoints: list, atPoints: list, camMode: str, startIndex: int, csNbr: int
    ):
        """Creates the armatures from the Camera Shot data"""

        endIndex = 0

        # this is required to be able to change the object mode
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        for i, (camEyeSpline, camATSpline) in enumerate(zip(eyePoints, atPoints), startIndex):
            cameraShotObj = self.getNewArmatureObject(f"CS_{csNbr:02}.Camera Shot {i:02}", True, csObj)

            if camEyeSpline.endFrame < camEyeSpline.startFrame + 2 or camATSpline.endFrame < camATSpline.startFrame + 2:
                print("WARNING: Non-standard end frame")

            cameraShotObj.data.ootCamShotProp.shotStartFrame = camEyeSpline.startFrame
            cameraShotObj.data.ootCamShotProp.shotCamMode = camMode
            boneData = [(eyePoint, atPoint) for eyePoint, atPoint in zip(camEyeSpline.entries, camATSpline.entries)]
            self.setBoneData(cameraShotObj, boneData, csNbr)
            endIndex = i

        return endIndex + 1

    def create_camera_shots(self, cs_obj: Object, spline_list: list[CutsceneCmdCamSplineList], cs_nbr: int):
        scale = bpy.context.scene.ootBlenderScale
        i = 0

        # this is required to be able to change the object mode
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        for splines in spline_list:
            start_index = i

            for i, spline in enumerate(splines.entries, start_index):
                new_shot = self.getNewArmatureObject(f"CS_{cs_nbr:02}.Camera Shot {i:02}", True, cs_obj)
                shot_props = new_shot.data.ootCamShotProp
                armature_data: Armature = new_shot.data

                shot_props.shot_duration = spline.duration
                # TODO: move this to the bones?
                first_entry = spline.entries[0]
                self.setPropOrCustom(
                    shot_props,
                    "shot_interp_type",
                    Utility.enum_id_to_key(first_entry.at.interp_type, "cs_spline_interp_type"),
                )
                self.setPropOrCustom(
                    shot_props,
                    "shot_spline_rel_to",
                    Utility.enum_id_to_key(first_entry.at.relative_to, "cs_spline_rel"),
                )

                for j, point in enumerate(spline.entries):
                    bpy.ops.object.mode_set(mode="EDIT")
                    boneName = f"CS_{cs_nbr:02}.Camera Point {j:02}"
                    new_edit_bone = armature_data.edit_bones.new(boneName)
                    new_edit_bone.head = getBlenderPosition(point.eye.pos, scale)
                    new_edit_bone.tail = getBlenderPosition(point.at.pos, scale)
                    bpy.ops.object.mode_set(mode="OBJECT")
                    new_bone = armature_data.bones[boneName]

                    # using the "AT" (look-at) data since this is what determines where the camera is looking
                    # the "Eye" only sets the location of the camera
                    new_bone.ootCamShotPointProp.shot_point_duration = point.at.duration
                    new_bone.ootCamShotPointProp.shotPointViewAngle = point.misc.viewAngle
                    new_bone.ootCamShotPointProp.shotPointRoll = point.misc.camRoll

    def setPropOrCustom(self, prop, propName: str, value):
        try:
            setattr(prop, propName, value)
        except TypeError:
            setattr(prop, propName, "Custom")
            setattr(prop, f"{propName}_custom" if "_" in propName else f"{propName}Custom", value)

    def setSubPropertyData(self, subPropsData: dict[str, str], newSubElem, entry):
        customNames = [
            "csMiscType",
            "csTextType",
            "ocarinaAction",
            "transition_type",
            "csSeqID",
            "csSeqPlayer",
            "transition",
        ]

        for key, value in subPropsData.items():
            if value is not None:
                if key in customNames:
                    valueToSet = getattr(entry, value)
                    self.setPropOrCustom(newSubElem, key, valueToSet)
                else:
                    setattr(newSubElem, key, getattr(entry, value))

    def setPropertyData(self, csProp: "OOTCutsceneProperty", cutscene: Cutscene, propDataList: list[PropertyData]):
        for data in propDataList:
            listName = f"{data.listType[0].lower() + data.listType[1:]}List"
            dataList = getattr(cutscene.data, (listName if data.listType != "FadeOutSeq" else "fadeSeqList"))
            for list in dataList:
                newElem: "OOTCSListProperty" = csProp.csLists.add()

                if data.listType == "Seq":
                    type = "StartSeqList" if list.type == "start" else "StopSeqList"
                else:
                    type = f"{data.listType}List" if data.listType != "Transition" else data.listType
                newElem.listType = type

                if data.listType == "Transition":
                    newElem.transitionStartFrame = list.startFrame
                    newElem.transitionEndFrame = list.endFrame
                    self.setSubPropertyData(data.subPropsData, newElem, list)
                else:
                    list.entries.sort(key=lambda elem: elem.startFrame)
                    for entry in list.entries:
                        newSubElem = getattr(newElem, "seqList" if "fadeOut" in listName else listName).add()
                        newSubElem.startFrame = entry.startFrame

                        if data.useEndFrame:
                            newSubElem.endFrame = entry.endFrame

                        if data.listType == "Text":
                            self.setPropOrCustom(newSubElem, "textboxType", entry.id)
                            match entry.id:
                                case "Text":
                                    newSubElem.textID = f"0x{entry.textId:04X}"
                                    self.setPropOrCustom(newSubElem, "csTextType", entry.type)
                                case "None":
                                    pass
                                case "OcarinaAction":
                                    newSubElem.ocarinaMessageId = f"0x{entry.messageId:04X}"
                                    self.setPropOrCustom(newSubElem, "ocarinaAction", entry.ocarinaActionId)
                                case _:
                                    raise PluginError("ERROR: Unknown text type!")
                        self.setSubPropertyData(data.subPropsData, newSubElem, entry)

    def setCutsceneData(self, csNumber, use_macros: bool, motion_only: bool):
        """Creates the cutscene empty objects from the file data"""

        cutsceneList = self.getCutsceneList(use_macros, motion_only)

        if cutsceneList is None:
            # if it's none then there's no cutscene in the file
            return csNumber

        if len(cutsceneList) == 0:
            raise PluginError("ERROR: No cutscene was found.")

        for i, cutscene in enumerate(cutsceneList, csNumber):
            print(f'Found Cutscene "{cutscene.name}"! Importing...')
            if is_oot_features():
                self.validateCameraData(cutscene)
            csName = f"Cutscene.{cutscene.name}"
            csObj = self.getNewCutsceneObject(csName, cutscene.frameCount, None)
            csProp = csObj.ootCutsceneProperty
            csNumber = i

            self.setActorCueData(csObj, cutscene.data.actorCueList, "Actor", i)
            self.setActorCueData(csObj, cutscene.data.playerCueList, "Player", i)

            if is_oot_features():
                if len(cutscene.data.camEyeSplineList) > 0:
                    lastIndex = self.setCameraShotData(
                        csObj, cutscene.data.camEyeSplineList, cutscene.data.camATSplineList, "splineEyeOrAT", 1, i
                    )

                if len(cutscene.data.camEyeSplineRelPlayerList) > 0:
                    lastIndex = self.setCameraShotData(
                        csObj,
                        cutscene.data.camEyeSplineRelPlayerList,
                        cutscene.data.camATSplineRelPlayerList,
                        "splineEyeOrATRelPlayer",
                        lastIndex,
                        i,
                    )

                if len(cutscene.data.camEyeList) > 0:
                    lastIndex = self.setCameraShotData(
                        csObj, cutscene.data.camEyeList, cutscene.data.camATList, "eyeOrAT", lastIndex, i
                    )
            else:
                if len(cutscene.data.camSplineList) > 0:
                    self.create_camera_shots(csObj, cutscene.data.camSplineList, i)

            if cutscene.data.destination is not None:
                csProp.csUseDestination = True
                csProp.csDestinationStartFrame = cutscene.data.destination.startFrame
                self.setPropOrCustom(csProp, "csDestination", cutscene.data.destination.id)

            if not is_oot_features() and cutscene.data.give_tatl is not None:
                csProp.csUseDestination = True
                csProp.csDestinationStartFrame = cutscene.data.destination.startFrame
                self.setPropOrCustom(csProp, "cs_give_tatl", cutscene.data.give_tatl.giveTatl)

            propDataList = [
                PropertyData("Text", {"textboxType": "id"}, True),
                PropertyData("Misc", {"csMiscType": "type"}, True),
                PropertyData("Transition", {"transition_type": "type"}, True),
                PropertyData("LightSettings", {"lightSettingsIndex": "lightSetting"}, False),
                PropertyData("Time", {"hour": "hour", "minute": "minute"}, False),
                PropertyData("Seq", {"csSeqID": "seqId"}, False),
                PropertyData("FadeOutSeq", {"csSeqPlayer": "seqPlayer"}, True),
                PropertyData(
                    "Rumble",
                    {
                        "rumbleSourceStrength": "sourceStrength",
                        "rumbleDuration": "duration",
                        "rumbleDecreaseRate": "decreaseRate",
                    },
                    False,
                ),
            ]
            self.setPropertyData(csProp, cutscene, propDataList)

            # Init camera + preview objects and setup the scene
            setupCutscene(csObj)
            bpy.ops.object.select_all(action="DESELECT")
            print("Success!")

        # ``csNumber`` makes sure there's no duplicates
        return csNumber + 1

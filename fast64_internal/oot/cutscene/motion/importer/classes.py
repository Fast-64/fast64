import bpy

from dataclasses import dataclass
from struct import unpack
from typing import TYPE_CHECKING
from bpy.types import Object, Armature
from .....utility import PluginError
from ....oot_constants import ootData
from ..utility import setupCutscene, getBlenderPosition, getRotation

if TYPE_CHECKING:
    from ...properties import OOTCSListProperty

from ..constants import (
    ootCSMotionLegacyToNewCmdNames,
    ootCSMotionListCommands,
    ootCSMotionCSCommands,
    ootCSMotionListEntryCommands,
    ootCSMotionSingleCommands,
    ootCSMotionListAndSingleCommands,
)

from ..io_classes import (
    OOTCSMotionActorCueList,
    OOTCSMotionActorCue,
    OOTCSMotionCamEyeSpline,
    OOTCSMotionCamATSpline,
    OOTCSMotionCamEyeSplineRelToPlayer,
    OOTCSMotionCamATSplineRelToPlayer,
    OOTCSMotionCamEye,
    OOTCSMotionCamAT,
    OOTCSMotionCamPoint,
    OOTCSMotionCutscene,
    OOTCSMotionObjectFactory,
    OOTCSMotionMisc,
    OOTCSMotionMiscList,
    OOTCSMotionTransition,
    OOTCSMotionText,
    OOTCSMotionTextNone,
    OOTCSMotionTextOcarinaAction,
    OOTCSMotionTextList,
    OOTCSMotionLightSetting,
    OOTCSMotionLightSettingList,
    OOTCSMotionTime,
    OOTCSMotionTimeList,
    OOTCSMotionStartStopSeq,
    OOTCSMotionStartStopSeqList,
    OOTCSMotionFadeSeq,
    OOTCSMotionFadeSeqList,
    OOTCSMotionRumbleController,
    OOTCSMotionRumbleControllerList,
)


@dataclass
class ParsedCutscene:
    """Local class used to order the parsed cutscene properly"""

    csName: str
    csData: list[str]  # contains every command lists or standalone ones like ``CS_TRANSITION()``


class OOTCSMotionImportCommands:
    """This class contains functions to create the cutscene dataclasses"""

    def getCmdParams(self, data: str, cmdName: str, paramNumber: int):
        """Returns the list of every parameter of the given command"""

        parenthesis = "(" if not cmdName.endswith("(") else ""
        params = data.strip().removeprefix(f"{cmdName}{parenthesis}").replace(" ", "").removesuffix(")").split(",")
        validTimeCmd = cmdName == "CS_TIME" and len(params) == 6 and paramNumber == 5
        if len(params) != paramNumber and not validTimeCmd:
            raise PluginError(
                f"ERROR: The number of expected parameters for `{cmdName}` "
                + "and the number of found ones is not the same!"
            )
        return params

    def getInteger(self, number: str):
        """Returns an int number (handles properly negative hex numbers)"""

        if number.startswith("0x"):
            number = number.removeprefix("0x")

            # ``"0" * (8 - len(number)`` adds the missing zeroes (if necessary) to have a 8 digit hex number
            return unpack("!i", bytes.fromhex("0" * (8 - len(number)) + number))[0]
        else:
            return int(number)

    def getNewCutscene(self, csData: str, name: str):
        params = self.getCmdParams(csData, "CS_BEGIN_CUTSCENE", OOTCSMotionCutscene.paramNumber)
        return OOTCSMotionCutscene(name, self.getInteger(params[0]), self.getInteger(params[1]))

    def getNewActorCueList(self, cmdData: str, isPlayer: bool):
        paramNumber = OOTCSMotionActorCueList.paramNumber
        paramNumber = paramNumber - 1 if isPlayer else paramNumber
        params = self.getCmdParams(cmdData, f"CS_{'PLAYER' if isPlayer else 'ACTOR'}_CUE_LIST", paramNumber)

        if isPlayer:
            actorCueList = OOTCSMotionActorCueList("Player", params[0])
        else:
            commandType = params[0]
            if commandType.startswith("0x"):
                # make it a 4 digit hex
                commandType = commandType.removeprefix("0x")
                commandType = "0x" + "0" * (4 - len(commandType)) + commandType
            actorCueList = OOTCSMotionActorCueList(commandType, self.getInteger(params[1].strip()))

        return actorCueList

    def getNewCamEyeSpline(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_CAM_EYE_SPLINE", OOTCSMotionCamEyeSpline.paramNumber)
        return OOTCSMotionCamEyeSpline(self.getInteger(params[0]), self.getInteger(params[1]))

    def getNewCamATSpline(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_CAM_AT_SPLINE", OOTCSMotionCamATSpline.paramNumber)
        return OOTCSMotionCamATSpline(self.getInteger(params[0]), self.getInteger(params[1]))

    def getNewCamEyeSplineRelToPlayer(self, cmdData: str):
        params = self.getCmdParams(
            cmdData, "CS_CAM_EYE_SPLINE_REL_TO_PLAYER", OOTCSMotionCamEyeSplineRelToPlayer.paramNumber
        )
        return OOTCSMotionCamEyeSplineRelToPlayer(self.getInteger(params[0]), self.getInteger(params[1]))

    def getNewCamATSplineRelToPlayer(self, cmdData: str):
        params = self.getCmdParams(
            cmdData, "CS_CAM_AT_SPLINE_REL_TO_PLAYER", OOTCSMotionCamATSplineRelToPlayer.paramNumber
        )
        return OOTCSMotionCamATSplineRelToPlayer(self.getInteger(params[0]), self.getInteger(params[1]))

    def getNewCamEye(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_CAM_EYE", OOTCSMotionCamEye.paramNumber)
        return OOTCSMotionCamEye(self.getInteger(params[0]), self.getInteger(params[1]))

    def getNewCamAT(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_CAM_AT", OOTCSMotionCamAT.paramNumber)
        return OOTCSMotionCamAT(self.getInteger(params[0]), self.getInteger(params[1]))

    def getNewActorCue(self, cmdData: str, isPlayer: bool):
        params = self.getCmdParams(
            cmdData, f"CS_{'PLAYER' if isPlayer else 'ACTOR'}_CUE", OOTCSMotionActorCue.paramNumber
        )

        return OOTCSMotionActorCue(
            self.getInteger(params[1]),
            self.getInteger(params[2]),
            self.getInteger(params[0]),
            [getRotation(params[3]), getRotation(params[4]), getRotation(params[5])],
            [self.getInteger(params[6]), self.getInteger(params[7]), self.getInteger(params[8])],
            [self.getInteger(params[9]), self.getInteger(params[10]), self.getInteger(params[11])],
        )

    def getNewCamPoint(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_CAM_POINT", OOTCSMotionCamPoint.paramNumber)

        return OOTCSMotionCamPoint(
            params[0],
            self.getInteger(params[1]),
            self.getInteger(params[2]),
            float(params[3][:-1]),
            [self.getInteger(params[4]), self.getInteger(params[5]), self.getInteger(params[6])],
        )

    def getNewMisc(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_MISC", OOTCSMotionMisc.paramNumber)
        miscEnum = ootData.enumData.enumByKey["csMiscType"]
        item = miscEnum.itemById.get(params[0])
        if item is None:
            item = miscEnum.itemByIndex.get(self.getInteger(params[0]))
        miscType = item.key if item is not None else params[0]
        return OOTCSMotionMisc(self.getInteger(params[1]), self.getInteger(params[2]), miscType)

    def getNewMiscList(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_MISC_LIST", OOTCSMotionMiscList.paramNumber)
        return OOTCSMotionMiscList(params[0])

    def getNewTransition(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_TRANSITION", OOTCSMotionTransition.paramNumber)
        transitionEnum = ootData.enumData.enumByKey["csTransitionType"]
        item = transitionEnum.itemById.get(params[0])
        if item is None:
            item = transitionEnum.itemByIndex.get(self.getInteger(params[0]))
        transType = item.key if item is not None else params[0]
        return OOTCSMotionTransition(self.getInteger(params[1]), self.getInteger(params[2]), transType)

    def getNewText(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_TEXT(", OOTCSMotionText.paramNumber)
        textEnum = ootData.enumData.enumByKey["csTextType"]
        item = textEnum.itemById.get(params[3])
        if item is None:
            item = textEnum.itemByIndex.get(self.getInteger(params[3]))
        textType = item.key if item is not None else params[3]
        return OOTCSMotionText(
            self.getInteger(params[1]),
            self.getInteger(params[2]),
            self.getInteger(params[0]),
            textType,
            self.getInteger(params[4]),
            self.getInteger(params[5]),
        )

    def getNewTextNone(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_TEXT_NONE", OOTCSMotionTextNone.paramNumber)
        return OOTCSMotionTextNone(self.getInteger(params[0]), self.getInteger(params[1]))

    def getNewTextOcarinaAction(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_TEXT_OCARINA_ACTION", OOTCSMotionTextOcarinaAction.paramNumber)
        actionEnum = ootData.enumData.enumByKey["ocarinaSongActionId"]
        item = actionEnum.itemById.get(params[0])
        if item is None:
            item = actionEnum.itemByIndex.get(self.getInteger(params[0]))
        actionId = item.key if item is not None else params[0]
        return OOTCSMotionTextOcarinaAction(
            self.getInteger(params[1]), self.getInteger(params[2]), actionId, self.getInteger(params[3])
        )

    def getNewTextEntry(self, cmdData: str):
        if cmdData.startswith("CS_TEXT("):
            return self.getNewText(cmdData)
        elif cmdData.startswith("CS_TEXT_NONE("):
            return self.getNewTextNone(cmdData)
        elif cmdData.startswith("CS_TEXT_OCARINA_ACTION("):
            return self.getNewTextOcarinaAction(cmdData)
        return None

    def getNewTextList(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_TEXT_LIST", OOTCSMotionTextList.paramNumber)
        return OOTCSMotionTextList(self.getInteger(params[0]))

    def getNewLightSetting(self, cmdData: str):
        isLegacy = cmdData.startswith("L_")
        if isLegacy:
            cmdData = cmdData.removeprefix("L_")
        params = self.getCmdParams(cmdData, "CS_LIGHT_SETTING", OOTCSMotionLightSetting.paramNumber)
        setting = self.getInteger(params[0])

        if isLegacy:
            setting -= 1
        return OOTCSMotionLightSetting(self.getInteger(params[1]), self.getInteger(params[2]), setting)

    def getNewLightSettingList(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_LIGHT_SETTING_LIST", OOTCSMotionLightSettingList.paramNumber)
        return OOTCSMotionLightSettingList(self.getInteger(params[0]))

    def getNewTime(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_TIME", OOTCSMotionTime.paramNumber)
        return OOTCSMotionTime(
            self.getInteger(params[1]),
            self.getInteger(params[2]),
            self.getInteger(params[3]),
            self.getInteger(params[4]),
        )

    def getNewTimeList(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_TIME_LIST", OOTCSMotionTimeList.paramNumber)
        return OOTCSMotionTimeList(self.getInteger(params[0]))

    def getNewStartStopSeq(self, cmdData: str, type: str):
        isLegacy = cmdData.startswith("L_")
        if isLegacy:
            cmdData = cmdData.removeprefix("L_")
        cmdName = f"CS_{'START' if type == 'start' else 'STOP'}_SEQ"
        params = self.getCmdParams(cmdData, cmdName, OOTCSMotionStartStopSeq.paramNumber)
        try:
            seqEnum = ootData.enumData.enumByKey["seqId"]
            item = seqEnum.itemById.get(params[0])
            if item is None:
                setting = self.getInteger(params[0])
                if isLegacy:
                    setting -= 1
                item = seqEnum.itemByIndex.get(setting)
            seqId = item.key if item is not None else params[0]
        except:
            seqId = params[0]
        return OOTCSMotionStartStopSeq(
            self.getInteger(params[1]),
            self.getInteger(params[2]),
            seqId,
        )

    def getNewStartStopSeqList(self, cmdData: str, type: str):
        cmdName = f"CS_{'START' if type == 'start' else 'STOP'}_SEQ_LIST"
        params = self.getCmdParams(cmdData, cmdName, OOTCSMotionStartStopSeqList.paramNumber)
        return OOTCSMotionStartStopSeqList(self.getInteger(params[0]), type)

    def getNewFadeSeq(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_FADE_OUT_SEQ", OOTCSMotionFadeSeq.paramNumber)
        fadePlayerEnum = ootData.enumData.enumByKey["csFadeOutSeqPlayer"]
        item = fadePlayerEnum.itemById.get(params[0])
        if item is None:
            item = fadePlayerEnum.itemByIndex.get(self.getInteger(params[0]))
        fadePlayerType = item.key if item is not None else params[0]
        return OOTCSMotionFadeSeq(self.getInteger(params[1]), self.getInteger(params[2]), fadePlayerType)

    def getNewFadeSeqList(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_FADE_OUT_SEQ_LIST", OOTCSMotionFadeSeqList.paramNumber)
        return OOTCSMotionFadeSeqList(self.getInteger(params[0]))

    def getNewRumbleController(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_RUMBLE_CONTROLLER", OOTCSMotionRumbleController.paramNumber)
        return OOTCSMotionRumbleController(
            self.getInteger(params[1]),
            self.getInteger(params[2]),
            self.getInteger(params[3]),
            self.getInteger(params[4]),
            self.getInteger(params[5]),
        )

    def getNewRumbleControllerList(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_RUMBLE_CONTROLLER_LIST", OOTCSMotionRumbleControllerList.paramNumber)
        return OOTCSMotionRumbleControllerList(self.getInteger(params[0]))


@dataclass
class OOTCSMotionImport(OOTCSMotionImportCommands, OOTCSMotionObjectFactory):
    """This class contains functions to create the new cutscene Blender data"""

    filePath: str  # used when importing from the panel
    fileData: str  # used when importing the cutscenes when importing a scene

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

        # replace old names
        oldNames = list(ootCSMotionLegacyToNewCmdNames.keys())
        fileData = fileData.replace("CS_CMD_CONTINUE", "CS_CAM_CONTINUE")
        fileData = fileData.replace("CS_CMD_STOP", "CS_CAM_STOP")
        for oldName in oldNames:
            fileData = fileData.replace(f"{oldName}(", f"{ootCSMotionLegacyToNewCmdNames[oldName]}(")

        # parse cutscenes
        fileLines = fileData.split("\n")
        csData = []
        cutsceneList: list[list[str]] = []
        foundCutscene = False
        for line in fileLines:
            if not line.startswith("//") and not line.startswith("/*"):
                if "CutsceneData " in line:
                    foundCutscene = True

                if foundCutscene:
                    sLine = line.strip()
                    if not sLine.endswith("),") and sLine.endswith(","):
                        line += fileLines[fileLines.index(line) + 1].strip()

                    if len(csData) == 0 or "CS_" in line:
                        csData.append(line)

                    if "};" in line:
                        foundCutscene = False
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
                    if curCmd in ootCSMotionCSCommands:
                        line = line.removesuffix(",") + "\n"

                        if curCmd in ootCSMotionSingleCommands and curCmd != "CS_END":
                            parsedData += line

                        if not cmdListFound and curCmd in ootCSMotionListCommands:
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
                            elif not cmdListFound and curCmd in ootCSMotionListEntryCommands:
                                print(f"{csName}, command:\n{line}")
                                raise PluginError(f"ERROR: Found a list entry outside a list inside ``{csName}``!")

                        if cmdListFound and nextCmd == "CS_END" or nextCmd in ootCSMotionListAndSingleCommands:
                            cmdListFound = False
                            parsedCS.append(parsedData)
                            parsedData = ""
                    elif not "CutsceneData" in curCmd and not "};" in curCmd:
                        print(f"WARNING: Unknown command found: ``{curCmd}``")
                        cmdListFound = False
            parsedCutscenes.append(ParsedCutscene(csName, parsedCS))

        return parsedCutscenes

    def getCutsceneList(self):
        """Returns the list of cutscenes with the data processed"""

        parsedCutscenes = self.getParsedCutscenes()

        if parsedCutscenes is None:
            # if it's none then there's no cutscene in the file
            return None

        cutsceneList: list[OOTCSMotionCutscene] = []
        cmdDataList = [
            ("ACTOR_CUE_LIST", self.getNewActorCueList, self.getNewActorCue, "actorCue"),
            ("PLAYER_CUE_LIST", self.getNewActorCueList, self.getNewActorCue, "playerCue"),
            ("CAM_EYE_SPLINE", self.getNewCamEyeSpline, self.getNewCamPoint, "camEyeSpline"),
            ("CAM_AT_SPLINE", self.getNewCamATSpline, self.getNewCamPoint, "camATSpline"),
            (
                "CAM_EYE_SPLINE_REL_TO_PLAYER",
                self.getNewCamEyeSplineRelToPlayer,
                self.getNewCamPoint,
                "camEyeSplineRelPlayer",
            ),
            (
                "CAM_AT_SPLINE_REL_TO_PLAYER",
                self.getNewCamATSplineRelToPlayer,
                self.getNewCamPoint,
                "camATSplineRelPlayer",
            ),
            ("CAM_EYE", self.getNewCamEye, self.getNewCamPoint, "camEye"),
            ("CAM_AT", self.getNewCamAT, self.getNewCamPoint, "camAT"),
            ("MISC_LIST", self.getNewMiscList, self.getNewMisc, "misc"),
            ("TRANSITION", self.getNewTransition, None, "transition"),
            ("TEXT_LIST", self.getNewTextList, self.getNewTextEntry, "text"),
            ("LIGHT_SETTING_LIST", self.getNewLightSettingList, self.getNewLightSetting, "lightSetting"),
            ("TIME_LIST", self.getNewTimeList, self.getNewTime, "time"),
            ("SEQ_LIST", self.getNewStartStopSeqList, self.getNewStartStopSeq, "seq"),
            ("FADE_OUT_SEQ_LIST", self.getNewFadeSeqList, self.getNewFadeSeq, "fadeSeq"),
            ("RUMBLE_CONTROLLER_LIST", self.getNewRumbleControllerList, self.getNewRumbleController, "rumble"),
        ]

        # for each cutscene from the list returned by getParsedCutscenes(),
        # create classes containing the cutscene's informations
        # that will be used later when creating Blender objects to complete the import
        for parsedCS in parsedCutscenes:
            cutscene = None
            for data in parsedCS.csData:
                # print(data)
                # create a new cutscene data
                if "CS_BEGIN_CUTSCENE(" in data:
                    cutscene = self.getNewCutscene(data, parsedCS.csName)

                # if we have a cutscene, create and add the commands data in it
                if cutscene is not None:
                    cmdData = data.removesuffix("\n").split("\n")
                    cmdListData = cmdData.pop(0)
                    for cmd, getListFunc, getFunc, listName in cmdDataList:
                        isPlayer = cmd == "PLAYER_CUE_LIST"
                        isStartSeq = cmd == "SEQ_LIST" and cmdListData.startswith("CS_START_SEQ_LIST")
                        isStopSeq = cmd == "SEQ_LIST" and cmdListData.startswith("CS_STOP_SEQ_LIST")

                        if isStartSeq or isStopSeq or f"CS_{cmd}(" in data:
                            cmdList = getattr(cutscene, f"{listName}List")

                            if getListFunc is not None:
                                if not isPlayer and not cmd == "ACTOR_CUE_LIST":
                                    if isStartSeq:
                                        commandData = getListFunc(cmdListData, "start")
                                    elif isStopSeq:
                                        commandData = getListFunc(cmdListData, "stop")
                                    else:
                                        commandData = getListFunc(cmdListData)
                                else:
                                    commandData = getListFunc(cmdListData, isPlayer)
                            else:
                                raise PluginError("ERROR: List getter callback is None!")

                            if getFunc is not None:
                                foundEndCmd = False
                                for d in cmdData:
                                    if not isPlayer and not cmd == "ACTOR_CUE_LIST":
                                        if isStartSeq:
                                            listEntry = getFunc(d, "start")
                                        elif isStopSeq:
                                            listEntry = getFunc(d, "stop")
                                        else:
                                            listEntry = getFunc(d)
                                        if "CAM" in cmd:
                                            flag = d.removeprefix("CS_CAM_POINT(").split(",")[0]
                                            if foundEndCmd:
                                                raise PluginError("ERROR: More camera commands after last one!")
                                            foundEndCmd = "CS_CAM_STOP" in flag or "-1" in flag
                                    else:
                                        listEntry = getFunc(d, isPlayer)

                                    if listEntry is not None:
                                        commandData.entries.append(listEntry)

                            cmdList.append(commandData)

            # after processing the commands we can add the cutscene to the cutscene list
            if cutscene is not None:
                cutsceneList.append(cutscene)
        return cutsceneList

    def setActorCueData(self, csObj: Object, actorCueList: list[OOTCSMotionActorCueList], cueName: str, csNbr: int):
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

    def validateCameraData(self, cutscene: OOTCSMotionCutscene):
        """Safety checks to make sure the camera data is correct"""

        camLists: list[tuple[str, list, list]] = [
            ("Eye and AT Spline", cutscene.camEyeSplineList, cutscene.camATSplineList),
            ("Eye and AT Spline Rel to Player", cutscene.camEyeSplineRelPlayerList, cutscene.camATSplineRelPlayerList),
            ("Eye and AT", cutscene.camEyeList, cutscene.camATList),
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
                    # the extra point at the end  that will only tell the game that this camera shot stops.
                    del eyeListEntry.entries[-1]
                    del atListEntry.entries[-1]

    def setBoneData(
        self, cameraShotObj: Object, boneData: list[tuple[OOTCSMotionCamPoint, OOTCSMotionCamPoint]], csNbr: int
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

    def setListData(self, prop, typeName: str, startFrame: int, endFrame: int, type: str):
        prop.startFrame = startFrame
        prop.endFrame = endFrame
        if typeName is not None and type is not None:
            try:
                setattr(prop, typeName, type)
            except TypeError:
                setattr(prop, typeName, "Custom")
                setattr(prop, f"{typeName}Custom", type)

    def setCutsceneData(self, csNumber):
        """Creates the cutscene empty objects from the file data"""

        cutsceneList = self.getCutsceneList()

        if cutsceneList is None:
            # if it's none then there's no cutscene in the file
            return csNumber

        for i, cutscene in enumerate(cutsceneList, csNumber):
            print(f'Found Cutscene "{cutscene.name}"!')
            self.validateCameraData(cutscene)
            csName = f"Cutscene.{cutscene.name}"
            csObj = self.getNewCutsceneObject(csName, cutscene.frameCount, None)
            csProp = csObj.ootCutsceneProperty
            csNumber = i

            print("Importing Actor Cues...")
            self.setActorCueData(csObj, cutscene.actorCueList, "Actor", i)
            self.setActorCueData(csObj, cutscene.playerCueList, "Player", i)
            print("Done!")

            print("Importing Camera Shots...")
            if len(cutscene.camEyeSplineList) > 0:
                lastIndex = self.setCameraShotData(
                    csObj, cutscene.camEyeSplineList, cutscene.camATSplineList, "splineEyeOrAT", 1, i
                )

            if len(cutscene.camEyeSplineRelPlayerList) > 0:
                lastIndex = self.setCameraShotData(
                    csObj,
                    cutscene.camEyeSplineRelPlayerList,
                    cutscene.camATSplineRelPlayerList,
                    "splineEyeOrATRelPlayer",
                    lastIndex,
                    i,
                )

            if len(cutscene.camEyeList) > 0:
                lastIndex = self.setCameraShotData(
                    csObj, cutscene.camEyeList, cutscene.camATList, "eyeOrAT", lastIndex, i
                )

            for miscList in cutscene.miscList:
                miscElem: "OOTCSListProperty" = csProp.csLists.add()
                miscElem.listType = "MiscList"
                for miscCmd in miscList.entries:
                    miscProp = miscElem.miscList.add()
                    self.setListData(miscProp, "csMiscType", miscCmd.startFrame, miscCmd.endFrame, miscCmd.type)

            for transition in cutscene.transitionList:
                transitionElem: "OOTCSListProperty" = csProp.csLists.add()
                transitionElem.listType = "Transition"
                transitionElem.transitionStartFrame = transition.startFrame
                transitionElem.transitionEndFrame = transition.endFrame
                try:
                    transitionElem.transitionType = transition.type
                except TypeError:
                    transitionElem.transitionType = "Custom"
                    transitionElem.transitionTypeCustom = transition.type

            for textList in cutscene.textList:
                textElem: "OOTCSListProperty" = csProp.csLists.add()
                textElem.listType = "TextList"
                textList.entries.sort(key=lambda elem: elem.startFrame)
                for textCmd in textList.entries:
                    textProp = textElem.textList.add()
                    textProp.textboxType = textCmd.id
                    match textCmd.id:
                        case "Text":
                            textProp.textID = f"0x{textCmd.textId:04X}"
                            typeName = "csTextType"
                            type = textCmd.type
                        case "None":
                            typeName = type = None
                        case "OcarinaAction":
                            textProp.ocarinaMessageId = f"0x{textCmd.messageId:04X}"
                            typeName = "ocarinaAction"
                            type = textCmd.ocarinaActionId
                        case _:
                            raise PluginError("ERROR: Unknown text type!")
                    self.setListData(textProp, typeName, textCmd.startFrame, textCmd.endFrame, type)

            for lightList in cutscene.lightSettingList:
                lightElem: "OOTCSListProperty" = csProp.csLists.add()
                lightElem.listType = "LightSettingsList"
                for lightCmd in lightList.entries:
                    lightProp = lightElem.lightSettingsList.add()
                    lightProp.lightSettingsIndex = lightCmd.lightSetting
                    lightProp.startFrame = lightCmd.startFrame

            for timeList in cutscene.timeList:
                timeElem: "OOTCSListProperty" = csProp.csLists.add()
                timeElem.listType = "TimeList"
                for timeCmd in timeList.entries:
                    timeProp = timeElem.timeList.add()
                    timeProp.hour = timeCmd.hour
                    timeProp.minute = timeCmd.minute
                    timeProp.startFrame = timeCmd.startFrame

            for seqList in cutscene.seqList:
                seqElem: "OOTCSListProperty" = csProp.csLists.add()
                seqElem.listType = "StartSeqList" if seqList.type == "start" else "StopSeqList"
                for seqCmd in seqList.entries:
                    seqProp = seqElem.seqList.add()
                    try:
                        seqProp.csSeqID = seqCmd.seqId
                    except TypeError:
                        seqProp.csSeqID = "Custom"
                        transitionElem.csSeqIDCustom = seqCmd.seqId
                    seqProp.startFrame = seqCmd.startFrame

            for fadeList in cutscene.fadeSeqList:
                fadeElem: "OOTCSListProperty" = csProp.csLists.add()
                fadeElem.listType = "FadeOutSeqList"
                for fadeCmd in fadeList.entries:
                    fadeProp = fadeElem.seqList.add()
                    try:
                        fadeProp.csSeqPlayer = fadeCmd.seqPlayer
                    except TypeError:
                        fadeProp.csSeqPlayer = "Custom"
                        transitionElem.csSeqPlayerCustom = fadeCmd.seqPlayer
                    fadeProp.startFrame = fadeCmd.startFrame
                    fadeProp.endFrame = fadeCmd.endFrame

            for rumbleList in cutscene.rumbleList:
                rumbleElem: "OOTCSListProperty" = csProp.csLists.add()
                rumbleElem.listType = "RumbleList"
                for rumbleCmd in rumbleList.entries:
                    rumbleProp = rumbleElem.rumbleList.add()
                    rumbleProp.startFrame = rumbleCmd.startFrame
                    rumbleProp.rumbleSourceStrength = rumbleCmd.sourceStrength
                    rumbleProp.rumbleDuration = rumbleCmd.duration
                    rumbleProp.rumbleDecreaseRate = rumbleCmd.decreaseRate

            # Init camera + preview objects and setup the scene
            setupCutscene(csObj)
            print("Done!")
            bpy.ops.object.select_all(action="DESELECT")

        # ``csNumber`` makes sure there's no duplicates
        return csNumber + 1

import bpy

from dataclasses import dataclass
from struct import unpack
from bpy.types import Object, Armature
from mathutils import Vector
from .....utility import PluginError, indent, yUpToZUp
from ....oot_utility import ootParseRotation
from ..utility import initCutscene
from ..constants import ootCSMotionLegacyToNewCmdNames, ootCSMotionListCommands

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
)


@dataclass
class ParsedCutscene:
    csName: str
    csData: list[str]


class OOTCSMotionImportCommands:
    def getCmdParams(self, data: str, cmdName: str, paramNumber: int):
        params = data.strip().removeprefix(f"{cmdName}(").removesuffix(",").replace(" ", "").split(",")
        if len(params) != paramNumber:
            raise PluginError(
                f"ERROR: The number of expected parameters for `{cmdName}` "
                + "and the number of found ones is not the same!"
            )
        return params

    def getRotation(self, data: str):
        if "DEG_TO_BINANG" in data or not "0x" in data:
            angle = float(data.split("(")[1].removesuffix(")") if "DEG_TO_BINANG" in data else data)
            binang = int(angle * (0x8000 / 180.0))
            return f"0x{0xFFFF if binang > 0xFFFF else binang:04X}"
        else:
            return data

    def getInteger(self, number: str):
        if number.startswith("0x"):
            number = number.removeprefix("0x")
            return unpack("!i", bytes.fromhex("0" * (8 - len(number)) + number))[0]
        else:
            return int(number)

    def getNewCutscene(self, csData: str, name: str):
        params = self.getCmdParams(csData, "CS_BEGIN_CUTSCENE", OOTCSMotionCutscene.paramNumber)
        return OOTCSMotionCutscene(name, self.getInteger(params[0]), self.getInteger(params[1]))

    def getNewActorCueList(self, cmdData: str, isPlayer: bool):
        paramNumber = OOTCSMotionActorCueList.paramNumber
        paramNumber = paramNumber - 1 if isPlayer else paramNumber
        params = self.getCmdParams(
            cmdData, f"CS_{'PLAYER' if isPlayer else 'ACTOR'}_CUE_LIST", paramNumber
        )

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
            params[0],
            [self.getRotation(params[3]), self.getRotation(params[4]), self.getRotation(params[5])],
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


@dataclass
class OOTCSMotionImport(OOTCSMotionImportCommands, OOTCSMotionObjectFactory):
    filePath: str

    def getBlenderPosition(self, pos: list[int], scale: int):
        # OoT: +X right, +Y up, -Z forward
        # Blender: +X right, +Z up, +Y forward
        return [float(pos[0]) / scale, -float(pos[2]) / scale, float(pos[1]) / scale]

    def getBlenderRotation(self, rotation: list[str]):
        rot = [int(self.getRotation(r), base=16) for r in rotation]
        return yUpToZUp @ Vector(ootParseRotation(rot))

    def getParsedCutscenes(self):
        """Returns a list of cutscenes in the file with commands parsed"""

        # open and read the file
        fileLines = None

        with open(self.filePath, "r") as inputFile:
            fileLines = inputFile.readlines()

        if fileLines is None:
            raise RuntimeError("Can't read file data!")

        # replace old names and tabs
        oldNames = list(ootCSMotionLegacyToNewCmdNames.keys())
        for i in range(len(fileLines)):
            fileLines[i] = fileLines[i].replace("\t", indent)
            for oldName in oldNames:
                fileLines[i] = fileLines[i].replace(oldName, ootCSMotionLegacyToNewCmdNames[oldName])

        parsedCutscenes: list[ParsedCutscene] = []
        parsedCommands = []
        cmdListLines = ""
        csName = None

        # separate commands lists as a list of lines
        for i, line in enumerate(fileLines):
            # avoid comments
            if not line.startswith("//") and not line.startswith("/*"):
                # get the cutscene's name and reset the commands and the cmd list entries
                if "CutsceneData" in line:
                    csName = line.split(" ")[1][:-2]
                    cmdListLines = ""
                    parsedCommands = []
                elif csName is not None:
                    # when the cutscene name is found
                    if "CS_BEGIN_CUTSCENE" in line:
                        # save the CS_BEGIN_CUTSCENE line
                        parsedCommands = [line]
                    elif "CS_END" in line:
                        # save the CS_END line
                        parsedCommands.append(line)
                        parsedCutscenes.append(ParsedCutscene(csName, parsedCommands))
                        csName = None
                    elif "CS_TRANSITION" in line or "CS_DESTINATION" in line:
                        parsedCommands.append(line)
                    else:
                        # checking for commands on two lines
                        line = line.strip()
                        if not line.endswith("),\n") and line.endswith(",\n"):
                            line = line[:-1]

                        # add list entries
                        cmdListLines += line

                        # if the current line is a new cmd list declaration, reset the content
                        for cmd in ootCSMotionListCommands:
                            if cmd in line:
                                cmdListLines = line
                                break

                        # once we reach the end of the list, save it to the parsedCommands list
                        # we're reading next line to see if it's a new list declaration
                        index = i + 1
                        if index < len(fileLines):
                            if not "CS_UNK_DATA" in cmdListLines:
                                cmdList = ["CS_END", "CS_TRANSITION", "CS_DESTINATION"]
                                cmdList.extend(ootCSMotionListCommands)
                                for cmd in cmdList:
                                    if cmd in fileLines[index]:
                                        parsedCommands.append(cmdListLines)
                                        cmdListLines = ""
                                        break

        return parsedCutscenes

    def getCutsceneList(self):
        """Returns the list of cutscenes with the data processed"""

        parsedCutscenes = self.getParsedCutscenes()
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
        ]

        # for each cutscene from the list returned by getParsedCutscenes(),
        # create classes containing the cutscene's informations
        # that will be used later when creating Blender objects to complete the import
        for parsedCS in parsedCutscenes:
            cutscene = None
            for data in parsedCS.csData:
                data = data.replace("),", ",\n")
                # create a new cutscene data
                if "CS_BEGIN_CUTSCENE(" in data:
                    cutscene = self.getNewCutscene(data, parsedCS.csName)

                # if we have a cutscene, create and add the commands data in it
                if cutscene is not None:
                    cmdData = data.removesuffix("\n").split("\n")
                    for cmd, getListFunc, getFunc, listName in cmdDataList:
                        isPlayer = cmd == "PLAYER_CUE_LIST"

                        if f"CS_{cmd}(" in data:
                            cmdList = getattr(cutscene, f"{listName}List")

                            if not isPlayer and not cmd == "ACTOR_CUE_LIST":
                                commandData = getListFunc(cmdData.pop(0))
                            else:
                                commandData = getListFunc(cmdData.pop(0), isPlayer)

                            foundEndCmd = False
                            for d in cmdData:
                                if not isPlayer and not cmd == "ACTOR_CUE_LIST":
                                    listEntry = getFunc(d)
                                    if "CAM" in cmd:
                                        flag = d.removeprefix("CS_CAM_POINT(").split(",")[0]
                                        if foundEndCmd:
                                            raise PluginError("ERROR: More camera commands after last one!")
                                        foundEndCmd = "CS_CAM_STOP" in flag or "-1" in flag or "CS_CMD_STOP" in flag
                                else:
                                    listEntry = getFunc(d, isPlayer)
                                commandData.entries.append(listEntry)

                            cmdList.append(commandData)

            # after processing the commands we can add the cutscene to the cutscene list
            if cutscene is not None:
                cutsceneList.append(cutscene)
        return cutsceneList

    def setActorCueData(self, csObj: Object, actorCueList: list[OOTCSMotionActorCueList], cueName: str, csNbr: int):
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

                objPos = [actorCue.startPos, actorCue.endPos]
                for k in range(2):
                    actorCueObj = self.getNewActorCueObject(
                        f"CS_{csNbr:02}.{cueName} Cue {i}.{j:02} - Point {k + 1:02}",
                        actorCue.startFrame,
                        actorCue.endFrame,
                        actorCue.actionID,
                        objPos[k],
                        actorCue.rot,
                        actorCueListObj,
                    )
                lastFrame = actorCue.endFrame
                lastPos = actorCue.endPos

    def validateCameraData(self, cutscene: OOTCSMotionCutscene):
        camLists: list[tuple[str, list, list]] = [
            ("Eye and AT Spline", cutscene.camEyeSplineList, cutscene.camATSplineList),
            ("Eye and AT Spline Rel to Player", cutscene.camEyeSplineRelPlayerList, cutscene.camATSplineRelPlayerList),
            ("Eye and AT", cutscene.camEyeList, cutscene.camATList),
        ]

        for camType, eyeList, atList in camLists:
            for eyeListEntry, atListEntry in zip(eyeList, atList):
                if len(eyeListEntry.entries) != len(atListEntry.entries):
                    raise PluginError(f"ERROR: Found {len(eyeList)} Eye lists but {len(atList)} AT lists in {camType}!")

                if len(eyeListEntry.entries) < 4:
                    raise PluginError(f"ERROR: Only {len(eyeList)} cam point in this command!")

                if len(eyeListEntry.entries) > 4:
                    # NOTE: there is a bug in the game where when incrementing to the next set of key points,
                    # the key point which checked for whether it's the last point or not is the last point
                    # of the next set, not the last point of the old set. This means we need to remove
                    # the extra point at the end  that will only tell the game that this camera shot stops
                    del eyeListEntry.entries[-1]
                    del atListEntry.entries[-1]

    def setBoneData(
        self, cameraShotObj: Object, boneData: list[tuple[OOTCSMotionCamPoint, OOTCSMotionCamPoint]], csNbr: int
    ):
        scale = bpy.context.scene.ootBlenderScale
        for i, (eyePoint, atPoint) in enumerate(boneData, 1):
            bpy.ops.object.mode_set(mode="EDIT")
            armatureData: Armature = cameraShotObj.data
            boneName = f"CS_{csNbr:02}.Camera Point {i:02}"
            newEditBone = armatureData.edit_bones.new(boneName)
            newEditBone.head = self.getBlenderPosition(eyePoint.pos, scale)
            newEditBone.tail = self.getBlenderPosition(atPoint.pos, scale)
            bpy.ops.object.mode_set(mode="OBJECT")
            newBone = armatureData.bones[boneName]

            if eyePoint.frame != 0:
                print("WARNING: Frames must be 0!")

            newBone.ootCamShotPointProp.shotPointFrame = atPoint.frame
            newBone.ootCamShotPointProp.shotPointViewAngle = atPoint.viewAngle
            newBone.ootCamShotPointProp.shotPointRoll = atPoint.camRoll

    def setCameraShotData(
        self, csObj: Object, eyePoints: list, atPoints: list, camMode: str, startIndex: int, csNbr: int
    ):
        endIndex = 0

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

    def setCutsceneData(self, csNumber):
        cutsceneList = self.getCutsceneList()

        for i, cutscene in enumerate(cutsceneList, csNumber):
            print(f'Found Cutscene "{cutscene.name}"!')
            self.validateCameraData(cutscene)
            csName = f"Cutscene.{cutscene.name}"
            csObj = self.getNewCutsceneObject(csName, cutscene.frameCount, None)
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

            # Init camera + preview objects and setup the scene
            initCutscene(csObj)
            print("Done!")
            bpy.ops.object.select_all(action="DESELECT")

        return csNumber + 1

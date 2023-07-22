import bpy

from dataclasses import dataclass
from struct import unpack
from bpy.types import Object, Armature
from .....utility import PluginError
from ..utility import setupCutscene, getBlenderPosition, getRotation

from ..constants import (
    ootCSMotionLegacyToNewCmdNames,
    ootCSMotionListCommands,
    ootCSMotionCSCommands,
    ootCSMotionListEntryCommands,
    ootCSMotionSingleCommands,
    ootCSMotionListAndSingleCommands,
    ootCSMotionTransTypeHexToEnum,
    ootCSMotionMiscTypeHexToEnum,
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

        params = data.strip().removeprefix(f"{cmdName}(").replace(" ", "").removesuffix(")").split(",")
        if len(params) != paramNumber:
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
            params[0],
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
        if params[0].startswith("CS_MISC_"):
            miscType = params[0] 
        else: 
            miscType = ootCSMotionMiscTypeHexToEnum[f"0x{self.getInteger(params[0]):02X}"]
        return OOTCSMotionMisc(self.getInteger(params[1]), self.getInteger(params[2]), miscType)

    def getNewMiscList(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_MISC_LIST", OOTCSMotionMiscList.paramNumber)
        return OOTCSMotionMiscList(params[0])

    def getNewTransition(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_TRANSITION", OOTCSMotionTransition.paramNumber)
        if params[0].startswith("CS_TRANS_"):
            transType = params[0] 
        else: 
            transType = ootCSMotionTransTypeHexToEnum[f"0x{self.getInteger(params[0]):02X}"]
        return OOTCSMotionTransition(self.getInteger(params[1]), self.getInteger(params[2]), transType)


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
                            elif curCmd.startswith("CS_LIGHT"):
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
        ]

        # for each cutscene from the list returned by getParsedCutscenes(),
        # create classes containing the cutscene's informations
        # that will be used later when creating Blender objects to complete the import
        for parsedCS in parsedCutscenes:
            cutscene = None
            for data in parsedCS.csData:
                # create a new cutscene data
                if "CS_BEGIN_CUTSCENE(" in data:
                    cutscene = self.getNewCutscene(data, parsedCS.csName)

                # if we have a cutscene, create and add the commands data in it
                if cutscene is not None:
                    cmdData = data.removesuffix("\n").split("\n")
                    cmdListData = cmdData.pop(0)
                    for cmd, getListFunc, getFunc, listName in cmdDataList:
                        isPlayer = cmd == "PLAYER_CUE_LIST"

                        if f"CS_{cmd}(" in data:
                            cmdList = getattr(cutscene, f"{listName}List")

                            if getListFunc is not None:
                                if not isPlayer and not cmd == "ACTOR_CUE_LIST":
                                    commandData = getListFunc(cmdListData)
                                else:
                                    commandData = getListFunc(cmdListData, isPlayer)

                            if getFunc is not None:
                                foundEndCmd = False
                                for d in cmdData:
                                    if not isPlayer and not cmd == "ACTOR_CUE_LIST":
                                        listEntry = getFunc(d)
                                        if "CAM" in cmd:
                                            flag = d.removeprefix("CS_CAM_POINT(").split(",")[0]
                                            if foundEndCmd:
                                                raise PluginError("ERROR: More camera commands after last one!")
                                            foundEndCmd = "CS_CAM_STOP" in flag or "-1" in flag
                                    else:
                                        listEntry = getFunc(d, isPlayer)
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

            if len(cutscene.miscList) > 0:
                for miscList in cutscene.miscList:
                    for miscCmd in miscList.entries:
                        miscProp = csObj.ootCutsceneProperty.preview.miscList.add()
                        miscProp.startFrame = miscCmd.startFrame
                        miscProp.endFrame = miscCmd.endFrame
                        miscProp.type = miscCmd.type

            if len(cutscene.transitionList) > 0:
                for transition in cutscene.transitionList:
                    transitionProp = csObj.ootCutsceneProperty.preview.transitionList.add()
                    transitionProp.startFrame = transition.startFrame
                    transitionProp.endFrame = transition.endFrame
                    transitionProp.type = transition.type

            # Init camera + preview objects and setup the scene
            setupCutscene(csObj)
            print("Done!")
            bpy.ops.object.select_all(action="DESELECT")

        # ``csNumber`` makes sure there's no duplicates
        return csNumber + 1

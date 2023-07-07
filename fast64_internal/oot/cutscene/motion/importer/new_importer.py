# temp file while creating the new importer
import bpy

from dataclasses import dataclass
from struct import pack, unpack
from bpy.types import Object, Armature
from mathutils import Vector
from .....utility import PluginError, indent, yUpToZUp
from ....oot_utility import getEnumIndex, ootParseRotation
from ..constants import ootCSMotionLegacyToNewCmdNames, ootEnumCSActorCueListCommandType, ootCSMotionListCommands

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
)


@dataclass
class ParsedCutscene:
    csName: str
    csData: list[str]


class OOTCSMotionObjectFactory:
    def getNewObject(self, name: str, data, selectObject: bool) -> Object:
        newObj = bpy.data.objects.new(name=name, object_data=data)
        bpy.context.scene.collection.objects.link(newObj)

        if selectObject:
            newObj.select_set(True)
            bpy.context.view_layer.objects.active = newObj

        return newObj

    def getNewEmptyObject(self, name: str, selectObject: bool):
        return self.getNewObject(name, None, selectObject)

    def getNewArmatureObject(self, name: str, selectObject: bool):
        newArmatureData = bpy.data.armatures.new(name)
        newArmatureData.display_type = "STICK"
        newArmatureData.show_names = True
        return self.getNewObject(name, newArmatureData, selectObject)

    def getNewCutsceneObject(self, name: str, frameCount: int):
        newCSObj = self.getNewEmptyObject(name, True)
        newCSObj.ootEmptyType = "Cutscene"
        newCSObj.ootCutsceneProperty.csEndFrame = frameCount
        return newCSObj

    def getNewActorCueListObject(self, name: str, commandType: str):
        newActorCueListObj = self.getNewEmptyObject(name, False)
        newActorCueListObj.ootEmptyType = f"CS {'Player' if 'Player' in name else 'Actor'} Cue List"
        index = getEnumIndex(ootEnumCSActorCueListCommandType, commandType)

        if index is not None:
            cmdType = ootEnumCSActorCueListCommandType[index][0]
            newActorCueListObj.ootCSMotionProperty.actorCueListProp.commandType = cmdType
        else:
            newActorCueListObj.ootCSMotionProperty.actorCueListProp.commandType = "Custom"
            newActorCueListObj.ootCSMotionProperty.actorCueListProp.commandTypeCustom = commandType

        return newActorCueListObj

    def getNewActorCueObject(
        self, name: str, startFrame: int, endFrame: int, actionID: str, location: list[int], rot: list[str]
    ):
        newActorCueObj = self.getNewEmptyObject(name, False)
        newActorCueObj.location = self.getBlenderPosition(location, bpy.context.scene.ootBlenderScale)
        newActorCueObj.empty_display_type = "ARROWS"
        newActorCueObj.rotation_mode = "XZY"
        newActorCueObj.rotation_euler = self.getBlenderRotation(rot)
        newActorCueObj.ootEmptyType = f"CS {'Actor' if 'Actor' in name else 'Player'} Cue"
        newActorCueObj.ootCSMotionProperty.actorCueProp.cueStartFrame = startFrame
        newActorCueObj.ootCSMotionProperty.actorCueProp.cueEndFrame = endFrame
        newActorCueObj.ootCSMotionProperty.actorCueProp.cueActionID = actionID
        return newActorCueObj


class OOTCSMotionImportCommands:
    def getCmdParams(self, data: str, cmdName: str):
        return data.strip().removeprefix(f"{cmdName}(").removesuffix("),").replace(" ", "").split(",")

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

    def getFloat(self, number: str):
        """From https://stackoverflow.com/questions/14431170/get-the-bits-of-a-float-in-python"""
        s = pack(">l", self.getInteger(number))
        return unpack(">f", s)[0]

    def getNewCutscene(self, csData: str, name: str):
        params = self.getCmdParams(csData, "CS_BEGIN_CUTSCENE")
        return OOTCSMotionCutscene(name, self.getInteger(params[0]), self.getInteger(params[1]))

    def getNewActorCueList(self, cmdData: str, isPlayer: bool):
        params = self.getCmdParams(cmdData, f"CS_{'PLAYER' if isPlayer else 'ACTOR'}_CUE_LIST")

        if isPlayer:
            actorCueList = OOTCSMotionActorCueList("Player", params[0])
        else:
            actorCueList = OOTCSMotionActorCueList(params[0], self.getInteger(params[1].strip()))

        return actorCueList

    def getNewCamEyeSpline(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_CAM_EYE_SPLINE")
        return OOTCSMotionCamEyeSpline(self.getInteger(params[0]), self.getInteger(params[1]))

    def getNewCamATSpline(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_CAM_AT_SPLINE")
        return OOTCSMotionCamATSpline(self.getInteger(params[0]), self.getInteger(params[1]))

    def getNewCamEyeSplineRelToPlayer(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_CAM_EYE_SPLINE_REL_TO_PLAYER")
        return OOTCSMotionCamEyeSplineRelToPlayer(self.getInteger(params[0]), self.getInteger(params[1]))

    def getNewCamATSplineRelToPlayer(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_CAM_AT_SPLINE_REL_TO_PLAYER")
        return OOTCSMotionCamATSplineRelToPlayer(self.getInteger(params[0]), self.getInteger(params[1]))

    def getNewCamEye(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_CAM_EYE")
        return OOTCSMotionCamEye(self.getInteger(params[0]), self.getInteger(params[1]))

    def getNewCamAT(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_CAM_AT")
        return OOTCSMotionCamAT(self.getInteger(params[0]), self.getInteger(params[1]))

    def getNewActorCue(self, cmdData: str, isPlayer: bool):
        params = self.getCmdParams(cmdData, f"CS_{'PLAYER' if isPlayer else 'ACTOR'}_CUE")

        return OOTCSMotionActorCue(
            self.getInteger(params[1]),
            self.getInteger(params[2]),
            params[0],
            [self.getRotation(params[3]), self.getRotation(params[4]), self.getRotation(params[5])],
            [self.getInteger(params[6]), self.getInteger(params[7]), self.getInteger(params[8])],
            [self.getInteger(params[9]), self.getInteger(params[10]), self.getInteger(params[11])],
        )

    def getNewCamPoint(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_CAM_POINT")

        return OOTCSMotionCamPoint(
            params[0],
            self.getInteger(params[1]),
            self.getInteger(params[2]),
            float(params[3][:-1]),
            [self.getInteger(params[4]), self.getInteger(params[5]), self.getInteger(params[6])],
        )


class OOTCSMotionImport(OOTCSMotionImportCommands, OOTCSMotionObjectFactory):
    def getBlenderPosition(self, pos: list[int], scale: int):
        # OoT: +X right, +Y up, -Z forward
        # Blender: +X right, +Z up, +Y forward
        return [float(pos[0]) / scale, -float(pos[2]) / scale, float(pos[1]) / scale]

    def getBlenderRotation(self, rotation: list[str]):
        rot = [int(self.getRotation(r), base=16) for r in rotation]
        return yUpToZUp @ Vector(ootParseRotation(rot))

    def getParsedCutscenes(self, filePath: str):
        """Returns a list of cutscenes in the file with commands parsed"""

        # open and read the file
        fileLines = None

        with open(filePath, "r") as inputFile:
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
                        # adds list entries
                        if cmdListLines.endswith("),"):
                            if not cmdListLines.endswith("\n"):
                                cmdListLines = f"{cmdListLines}\n"
                            cmdListLines += line
                        else:
                            cmdListLines += f" {line.strip()}"

                        # if the current line is a new cmd list declaration, reset the content
                        for cmd in ootCSMotionListCommands:
                            if cmd in line:
                                cmdListLines = line
                                break

                        # once we reach the end of the list, save it to the parsedCommands list
                        # we're reading next line to see if it's a new list declaration
                        index = i + 1
                        if index < len(fileLines):
                            nextLine = fileLines[index]

                            # checking for commands on two lines
                            if not line.endswith("),\n") and line.endswith(",\n"):
                                cmdListLines = cmdListLines[:-1]

                            if not "CS_UNK_DATA" in cmdListLines:
                                nextLineIsStandaloneCmd = (
                                    "CS_END" in nextLine or "CS_TRANSITION" in nextLine or "CS_DESTINATION" in nextLine
                                )
                                cmdList = ["CS_END", "CS_TRANSITION", "CS_DESTINATION"]
                                cmdList.extend(ootCSMotionListCommands)
                                for cmd in cmdList:
                                    if cmd in nextLine:
                                        parsedCommands.append(cmdListLines)
                                        cmdListLines = ""
                                        break

        return parsedCutscenes

    def getCutsceneList(self, filePath: str):
        """Returns the list of cutscenes with the data processed"""

        parsedCutscenes = self.getParsedCutscenes(filePath)
        cutsceneList: list[OOTCSMotionCutscene] = []

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
                    isPlayer = "CS_PLAYER_CUE_LIST(" in data
                    cmdData = data.removesuffix("\n").split("\n")

                    if "CS_ACTOR_CUE_LIST(" in data or isPlayer:
                        actorCueList = self.getNewActorCueList(cmdData.pop(0), isPlayer)

                        for data in cmdData:
                            actorCueList.entries.append(self.getNewActorCue(data, isPlayer))

                        if isPlayer:
                            cutscene.playerCueList.append(actorCueList)
                        else:
                            cutscene.actorCueList.append(actorCueList)

                    # note: camera commands are basically the same but there's all separate on purpose
                    # in order to make editing easier if the user change something in decomp that need to be ported there
                    if "CS_CAM_EYE_SPLINE(" in data:
                        camEyeSpline = self.getNewCamEyeSpline(cmdData.pop(0))

                        for data in cmdData:
                            camEyeSpline.entries.append(self.getNewCamPoint(data))

                        cutscene.camEyeSplineList.append(camEyeSpline)

                    if "CS_CAM_AT_SPLINE(" in data:
                        camATSpline = self.getNewCamATSpline(cmdData.pop(0))

                        for data in cmdData:
                            camATSpline.entries.append(self.getNewCamPoint(data))

                        cutscene.camATSplineList.append(camATSpline)

                    if "CS_CAM_EYE_SPLINE_REL_TO_PLAYER(" in data:
                        camEyeSplineRelToPlayer = self.getNewCamEyeSplineRelToPlayer(cmdData.pop(0))

                        for data in cmdData:
                            camEyeSplineRelToPlayer.entries.append(self.getNewCamPoint(data))

                        cutscene.camEyeSplineRelPlayerList.append(camEyeSplineRelToPlayer)

                    if "CS_CAM_AT_SPLINE_REL_TO_PLAYER(" in data:
                        camATSplineRelToPlayer = self.getNewCamATSplineRelToPlayer(cmdData.pop(0))

                        for data in cmdData:
                            camATSplineRelToPlayer.entries.append(self.getNewCamPoint(data))

                        cutscene.camATSplineRelPlayerList.append(camATSplineRelToPlayer)

                    if "CS_CAM_EYE(" in data:
                        camEye = self.getNewCamEye(cmdData.pop(0))

                        for data in cmdData:
                            camEye.entries.append(self.getNewCamPoint(data))

                        cutscene.camEyeList.append(camEye)

                    if "CS_CAM_AT(" in data:
                        camAT = self.getNewCamAT(cmdData.pop(0))

                        for data in cmdData:
                            camAT.entries.append(self.getNewCamPoint(data))

                        cutscene.camATList.append(camAT)

            # after processing the commands we can add the cutscene to the cutscene list
            if cutscene is not None:
                cutsceneList.append(cutscene)

        return cutsceneList

    def importActorCues(self, csObj: Object, actorCueList: list[OOTCSMotionActorCueList], cueName: str, csNbr: int):
        for i, entry in enumerate(actorCueList, 1):
            if len(entry.entries) == 0:
                raise PluginError("ERROR: Actor Cue List does not have any Actor Cue!")

            lastFrame = lastPos = None
            actorCueListObj = self.getNewActorCueListObject(
                f"CS_{csNbr:02}.{cueName} Cue List {i:02}", entry.commandType
            )
            actorCueListObj.parent = csObj

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
                    )
                    actorCueObj.parent = actorCueListObj
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

    def getBoneData(self, eyeCamPoints: list[OOTCSMotionCamPoint], atCamPoints: list[OOTCSMotionCamPoint]):
        # Eye -> Head, AT -> Tail
        return [(eyePoint, atPoint) for eyePoint, atPoint in zip(eyeCamPoints, atCamPoints)]

    def importBoneData(
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

    def importCameraShots(
        self, csObj: Object, eyePoints: list, atPoints: list, camMode: str, startIndex: int, csNbr: int
    ):
        endIndex = 0

        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        for i, (camEyeSpline, camATSpline) in enumerate(zip(eyePoints, atPoints), startIndex):
            cameraShotObj = self.getNewArmatureObject(f"CS_{csNbr:02}.Camera Shot {i:02}", True)
            cameraShotObj.parent = csObj

            if camEyeSpline.endFrame < camEyeSpline.startFrame + 2 or camATSpline.endFrame < camATSpline.startFrame + 2:
                print("WARNING: Non-standard end frame")

            cameraShotObj.data.ootCamShotProp.shotStartFrame = camEyeSpline.startFrame
            cameraShotObj.data.ootCamShotProp.shotCamMode = camMode
            boneData = self.getBoneData(camEyeSpline.entries, camATSpline.entries)
            self.importBoneData(cameraShotObj, boneData, csNbr)
            endIndex = i

        return endIndex + 1


def setCutsceneMotionData(filePath: str, csNumber):
    csImport = OOTCSMotionImport()
    cutsceneList = csImport.getCutsceneList(filePath)

    for i, cutscene in enumerate(cutsceneList, csNumber):
        print(f'Found Cutscene "{cutscene.name}"!')
        csImport.validateCameraData(cutscene)
        csName = f"Cutscene.{cutscene.name}"
        csObj = csImport.getNewCutsceneObject(csName, cutscene.frameCount)
        csNumber = i

        print("Importing Actor Cues...")
        csImport.importActorCues(csObj, cutscene.actorCueList, "Actor", i)
        csImport.importActorCues(csObj, cutscene.playerCueList, "Player", i)
        print("Done!")

        print("Importing Camera Shots...")
        if len(cutscene.camEyeSplineList) > 0:
            lastIndex = csImport.importCameraShots(
                csObj, cutscene.camEyeSplineList, cutscene.camATSplineList, "splineEyeOrAT", 1, i
            )

        if len(cutscene.camEyeSplineRelPlayerList) > 0:
            lastIndex = csImport.importCameraShots(
                csObj,
                cutscene.camEyeSplineRelPlayerList,
                cutscene.camATSplineRelPlayerList,
                "splineEyeOrATRelPlayer",
                lastIndex,
                i,
            )

        if len(cutscene.camEyeList) > 0:
            lastIndex = csImport.importCameraShots(
                csObj, cutscene.camEyeList, cutscene.camATList, "eyeOrAT", lastIndex, i
            )
        print("Done!")
        bpy.ops.object.select_all(action="DESELECT")

    return csNumber + 1

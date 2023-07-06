# temp file while creating the new importer
import bpy, math

from dataclasses import dataclass
from struct import pack, unpack
from bpy.types import Object, Bone, Armature
from .....utility import indent
from ....oot_utility import getEnumIndex
from ..constants import ootCSMotionLegacyToNewCmdNames, ootEnumCSActorCueListCommandType

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


class OOTCSMotionImportCommands:
    def getCmdParams(self, data: str, cmdName: str):
        return data.strip().removeprefix(f"{cmdName}(").removesuffix("),").replace(" ", "").split(",")

    def getRotation(self, data: str):
        return data.split("(")[1].removesuffix(")") if "DEG_TO_BINANG" in data else data

    def getInteger(self, number: str):
        return int(number, base=16 if number.startswith("0x") else 10)

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


class OOTCSMotionImport(OOTCSMotionImportCommands):
    def getBlenderPosition(self, pos: list[int], scale: int):
        # OoT: +X right, +Y up, -Z forward
        # Blender: +X right, +Z up, +Y forward
        return [float(pos[0]) / scale, -float(pos[2]) / scale, float(pos[1]) / scale]

    def getBlenderRotation(self, rotation: list[str]):
        rot = [self.getFloat(r) for r in rotation]

        def conv(r):
            assert r >= -0x8000 and r <= 0x7FFF
            return 2.0 * math.pi * float(r) / 0x10000

        return [conv(rot[0]), conv(rot[2]), conv(rot[1])]

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

        csListCmds = [
            "CS_ACTOR_CUE_LIST",
            "CS_PLAYER_CUE_LIST",
            "CS_CAM_EYE_SPLINE",
            "CS_CAM_AT_SPLINE",
            "CS_CAM_EYE_SPLINE_REL_TO_PLAYER",
            "CS_CAM_AT_SPLINE_REL_TO_PLAYER",
            "CS_CAM_EYE",
            "CS_CAM_AT",
            "CS_MISC_LIST",
            "CS_LIGHT_SETTING_LIST",
            "CS_RUMBLE_CONTROLLER_LIST",
            "CS_TEXT_LIST",
            "CS_START_SEQ_LIST",
            "CS_STOP_SEQ_LIST",
            "CS_FADE_OUT_SEQ_LIST",
            "CS_TIME_LIST",
            "CS_UNK_DATA_LIST",
        ]

        csCommands = [
            "CS_ACTOR_CUE",
            "CS_CAM_POINT",
            "CS_MISC",
            "CS_LIGHT_SETTING",
            "CS_RUMBLE_CONTROLLER",
            "CS_TEXT",
            "CS_TEXT_NONE",
            "CS_TEXT_OCARINA_ACTION",
            "CS_TRANSITION",
            "CS_START_SEQ",
            "CS_STOP_SEQ",
            "CS_FADE_OUT_SEQ",
            "CS_TIME",
            "CS_DESTINATION",
            "CS_UNK_DATA",
        ]

        csCommands.extend(csListCmds)
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
                        for cmd in csListCmds:
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
                                for cmd in csListCmds:
                                    if cmd in nextLine or "CS_END" in nextLine:
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
                if "CS_BEGIN_CUTSCENE" in data:
                    cutscene = self.getNewCutscene(data, parsedCS.csName)

                # if we have a cutscene, create and add the commands data in it
                if cutscene is not None:
                    isPlayer = "CS_PLAYER_CUE_LIST" in data
                    cmdData = data.removesuffix("\n").split("\n")

                    if "CS_ACTOR_CUE_LIST" in data or isPlayer:
                        actorCueList = self.getNewActorCueList(cmdData.pop(0), isPlayer)

                        for data in cmdData:
                            actorCueList.entries.append(self.getNewActorCue(data, isPlayer))

                        if isPlayer:
                            cutscene.playerCueList.append(actorCueList)
                        else:
                            cutscene.actorCueList.append(actorCueList)

                    # note: camera commands are basically the same but there's all separate on purpose
                    # in order to make editing easier if the user change something in decomp that need to be ported there
                    if "CS_CAM_EYE_SPLINE" in data:
                        camEyeSpline = self.getNewCamEyeSpline(cmdData.pop(0))

                        for data in cmdData:
                            camEyeSpline.entries.append(self.getNewCamPoint(data))

                        cutscene.camEyeSplineList.append(camEyeSpline)

                    if "CS_CAM_AT_SPLINE" in data:
                        camATSpline = self.getNewCamATSpline(cmdData.pop(0))

                        for data in cmdData:
                            camATSpline.entries.append(self.getNewCamPoint(data))

                        cutscene.camATSplineList.append(camATSpline)

                    if "CS_CAM_EYE_SPLINE_REL_TO_PLAYER" in data:
                        camEyeSplineRelToPlayer = self.getNewCamEyeSplineRelToPlayer(cmdData.pop(0))

                        for data in cmdData:
                            camEyeSplineRelToPlayer.entries.append(self.getNewCamPoint(data))

                        cutscene.camEyeSplineRelPlayerList.append(camEyeSplineRelToPlayer)

                    if "CS_CAM_AT_SPLINE_REL_TO_PLAYER" in data:
                        camATSplineRelToPlayer = self.getNewCamATSplineRelToPlayer(cmdData.pop(0))

                        for data in cmdData:
                            camATSplineRelToPlayer.entries.append(self.getNewCamPoint(data))

                        cutscene.camATSplineRelPlayerList.append(camATSplineRelToPlayer)

                    if "CS_CAM_EYE" in data:
                        camEye = self.getNewCamEye(cmdData.pop(0))

                        for data in cmdData:
                            camEye.entries.append(self.getNewCamPoint(data))

                        cutscene.camEyeList.append(camEye)

                    if "CS_CAM_AT" in data:
                        camAT = self.getNewCamAT(cmdData.pop(0))

                        for data in cmdData:
                            camAT.entries.append(self.getNewCamPoint(data))

                        cutscene.camATList.append(camAT)

            # after processing the commands we can add the cutscene to the cutscene list
            if cutscene is not None:
                cutsceneList.append(cutscene)

        return cutsceneList

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
        newActorCueObj.rotation_euler = self.getBlenderRotation(rot)
        newActorCueObj.ootEmptyType = "CS Actor Cue"
        newActorCueObj.ootCSMotionProperty.actorCueProp.cueStartFrame = startFrame
        newActorCueObj.ootCSMotionProperty.actorCueProp.cueEndFrame = endFrame
        newActorCueObj.ootCSMotionProperty.actorCueProp.cueActionID = actionID
        return newActorCueObj

    def importActorCues(self, csObj: Object, actorCueList: list[OOTCSMotionActorCueList], cueName: str):
        for i, entry in enumerate(actorCueList, 1):
            actorCueListObj = self.getNewActorCueListObject(f"{cueName} Cue List {i:02}", entry.commandType)
            actorCueListObj.parent = csObj

            for j, actorCue in enumerate(entry.entries, 1):
                objPos = [actorCue.startPos, actorCue.endPos]
                for k in range(2):
                    actorCueObj = self.getNewActorCueObject(
                        f"{cueName} Cue {i}.{j:02} - Point {k + 1:02}",
                        actorCue.startFrame,
                        actorCue.endFrame,
                        actorCue.actionID,
                        objPos[k],
                        actorCue.rot,
                    )

                    actorCueObj.parent = actorCueListObj


def setCutsceneMotionData(filePath: str):
    csImport = OOTCSMotionImport()
    cutsceneList = csImport.getCutsceneList(filePath)

    for cutscene in cutsceneList:
        print(f'Found Cutscene "{cutscene.name}"!')
        csObj = csImport.getNewCutsceneObject(f"Cutscene.{cutscene.name}", cutscene.frameCount)

        print("Importing Actor Cues...")
        csImport.importActorCues(csObj, cutscene.actorCueList, "Actor")
        print("Done!")

        print("Importing Player Cues...")
        csImport.importActorCues(csObj, cutscene.playerCueList, "Player")
        print("Done!")

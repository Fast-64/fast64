# temp file while creating the new importer

from dataclasses import dataclass
from ..constants import ootCSMotionLegacyToNewCmdNames
from .....utility import indent

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
        return data.split("(")[1].removesuffix(")")

    def getNewCutscene(self, csData: str, name: str):
        params = self.getCmdParams(csData, "CS_BEGIN_CUTSCENE")

        return OOTCSMotionCutscene(
            name, int(params[0]), int(params[1]), list(), list(), list(), list(), list(), list(), list(), list()
        )

    def getNewActorCueList(self, cmdData: str, isPlayer: bool):
        params = self.getCmdParams(cmdData, f"CS_{'PLAYER' if isPlayer else 'ACTOR'}_CUE_LIST")

        if isPlayer:
            actorCueList = OOTCSMotionActorCueList("Player", params[0], list())
        else:
            actorCueList = OOTCSMotionActorCueList(params[0], int(params[1].strip()), list())

        return actorCueList

    def getNewCamEyeSpline(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_CAM_EYE_SPLINE")
        return OOTCSMotionCamEyeSpline(int(params[0]), int(params[1]), list())

    def getNewCamATSpline(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_CAM_AT_SPLINE")
        return OOTCSMotionCamATSpline(int(params[0]), int(params[1]), list())

    def getNewCamEyeSplineRelToPlayer(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_CAM_EYE_SPLINE_REL_TO_PLAYER")
        return OOTCSMotionCamEyeSplineRelToPlayer(int(params[0]), int(params[1]), list())

    def getNewCamATSplineRelToPlayer(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_CAM_AT_SPLINE_REL_TO_PLAYER")
        return OOTCSMotionCamATSplineRelToPlayer(int(params[0]), int(params[1]), list())

    def getNewCamEye(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_CAM_EYE")
        return OOTCSMotionCamEye(int(params[0]), int(params[1]), list())

    def getNewCamAT(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_CAM_AT")
        return OOTCSMotionCamAT(int(params[0]), int(params[1]), list())

    def getNewActorCue(self, cmdData: str, isPlayer: bool):
        params = self.getCmdParams(cmdData, f"CS_{'PLAYER' if isPlayer else 'ACTOR'}_CUE")

        return OOTCSMotionActorCue(
            int(params[1]),
            int(params[2]),
            params[0],
            [self.getRotation(params[3]), self.getRotation(params[4]), self.getRotation(params[5])],
            [int(params[6]), int(params[7]), int(params[8])],
            [int(params[9]), int(params[10]), int(params[11])],
        )

    def getNewCamPoint(self, cmdData: str):
        params = self.getCmdParams(cmdData, "CS_CAM_POINT")

        return OOTCSMotionCamPoint(
            params[0],
            int(params[1]),
            int(params[2]),
            float(params[3][:-1]),
            [int(params[4]), int(params[5]), int(params[6])],
        )


class OOTCSMotionImport(OOTCSMotionImportCommands):
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
        ]

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

                # when the cutscene name is found
                if csName is not None:
                    if "CS_BEGIN_CUTSCENE" in line:
                        # save the CS_BEGIN_CUTSCENE line
                        parsedCommands = [line]
                    elif "CS_END" in line:
                        # save the CS_END line
                        parsedCommands.append(line)
                        parsedCutscenes.append(ParsedCutscene(csName, parsedCommands))
                    else:
                        # adds list entries
                        cmdListLines += line

                        # if the current line is a new cmd list declaration, reset the content
                        for cmd in csListCmds:
                            if cmd in line:
                                cmdListLines = line
                                break

                        # once we reach the end of the list, save it to the parsedCommands list
                        # we're reading next line to see if it's a new list declaration
                        index = i + 1
                        if index < len(fileLines):
                            for cmd in csListCmds:
                                if cmd in fileLines[index] or "CS_END" in fileLines[index]:
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


def setCutsceneMotionData(filePath: str):
    csImport = OOTCSMotionImport()
    cutsceneList = csImport.getCutsceneList(filePath)

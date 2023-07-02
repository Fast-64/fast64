import os
import shutil
import math
import traceback
import bpy

from struct import pack, unpack
from bpy.types import Object
from .....utility import indent
from ..constants import CAM_TYPE_LISTS, ACTION_LISTS, ATMODE_TO_CMD
from ..utility import (
    OOTCutsceneMotionIOBase,
    getShotObjects,
    getFakeCSEndFrame,
    getShotPropBonesChecked,
    getFakeCamCmdsLength,
    getActorCueListObjects,
    getActorCuePointObjects,
)


def floatBitsAsInt(f):
    s = pack(">f", f)
    return unpack(">l", s)[0]


class OOTCutsceneMotionExport(OOTCutsceneMotionIOBase):
    def __init__(self, context, use_floats, use_cscmd):
        super().__init__(context)
        self.use_floats = use_floats
        self.use_cscmd = use_cscmd
        self.csObj = None
        self.cs_objects = [obj for obj in bpy.data.objects if obj.type == "EMPTY" and obj.name.startswith("Cutscene.")]

    def getCutsceneArrayName(self, csName: str):
        return f"CutsceneData {csName}[]" + " = {\n"

    def getCutsceneBeginCmdRaw(self, entriesTotal: int, endFrame: int):
        return indent + f"CS_BEGIN_CUTSCENE({entriesTotal}, {endFrame}),\n"

    def getCutsceneBeginCmd(self, csObj: Object):
        return self.getCutsceneBeginCmdRaw(
            len(getShotObjects(self.context.scene, csObj)) * 2
            + len(getActorCueListObjects(self.context.scene, csObj, None)),
            getFakeCSEndFrame(self.context, csObj),
        )

    def getCutsceneEndCmd(self):
        return indent + "CS_END(),\n"

    def getCamListCmd(self, startFrame: int, endFrame: int, useAT: bool, mode: str):
        return indent + f"{ATMODE_TO_CMD[useAT][mode]}_LIST({startFrame}, {endFrame}),\n"

    def getPositionString(self, pos):
        x = int(round(pos[0] * self.scale))
        y = int(round(pos[2] * self.scale))
        z = int(round(-pos[1] * self.scale))

        if any(v < -0x8000 or v >= 0x8000 for v in (x, y, z)):
            raise RuntimeError(f"Position(s) too large, out of range: {x}, {y}, {z}")

        return f"{x}, {y}, {z}"

    def getRotationString(self, rot):
        def conv(r):
            r /= 2.0 * math.pi
            r -= math.floor(r)
            r = round(r * 0x10000)

            if r >= 0x8000:
                r += 0xFFFF0000

            assert r >= 0 and r <= 0xFFFFFFFF and (r <= 0x7FFF or r >= 0xFFFF8000)

            return hex(r)

        rotations = [conv(rot[0]), conv(rot[2]), conv(rot[1])]
        return ", ".join(f"DEG_TO_BINANG({(int(r, base=16) * (180 / 0x8000)):.3f})" for r in rotations)

    def getCamCmd(self, continueFlag: bool, camRoll: int, camFrame: int, camViewAngle, camPos, useAT: bool, mode: str):
        if self.use_cscmd:
            contFlag = "CS_CMD_CONTINUE" if continueFlag else "CS_CMD_STOP"
        else:
            contFlag = "0" if continueFlag else "-1"

        return (
            indent * 2 + f"{ATMODE_TO_CMD[useAT][mode]}({contFlag}"
        ) + f"{camRoll}, {camFrame}, {camViewAngle}f, {self.getPositionString(camPos)}, 0),\n"

    def getActorCueListCmd(self, actor_id: int, entriesTotal: int):
        return (
            indent + "CS_PLAYER_ACTION_LIST("
            if actor_id < 0
            else f"CS_NPC_ACTION_LIST({actor_id}, " + f"{entriesTotal}),\n"
        )

    def getActorCueCmd(self, actor_id: int, action_id: str, start_frame: int, end_frame: int, rot, start_pos, end_pos):
        return (
            indent * 2
            + ("CS_PLAYER_ACTION" if actor_id < 0 else "CS_NPC_ACTION")
            + f"({action_id}, {start_frame}, {end_frame}, {self.getRotationString(rot)}"
            + f"{self.getPositionString(start_pos)}, {self.getPositionString(end_pos)}, 0, 0, 0),\n"
        )

    def onCutsceneStart(self, csName: str):
        super().onCutsceneStart(csName)
        self.wrote_cam_lists = False
        self.wrote_action_lists = False

        for csObj in self.cs_objects:
            if csObj.name == f"Cutscene.{csName}":
                self.csObj = csObj
                self.cs_objects.remove(csObj)
                print("Replacing camera commands in cutscene " + csName)
                break
        else:
            self.csObj = None
            print("Scene does not contain cutscene " + csName + " in file, skipping")

        self.outfile.write(self.getCutsceneArrayName(csName))
        self.cs_text = ""

    def onCutsceneEnd(self):
        super().onCutsceneEnd()

        if self.csObj is not None:
            if not self.wrote_cam_lists:
                print("Cutscene did not contain any existing camera commands, adding at end")
                self.processCamMotionLists(self.csObj)

            if not self.wrote_action_lists:
                print("Cutscene did not contain any existing action lists, adding at end")
                self.processActorCueLists(self.csObj)

        self.csObj = None
        self.cs_text += self.getCutsceneEndCmd()
        self.outfile.write(self.getCutsceneBeginCmdRaw(self.entrycount_write, self.cs_end_frame))
        self.outfile.write(self.cs_text)

    def onLineOutsideCS(self, line: str):
        super().onLineOutsideCS(line)
        self.outfile.write(line)

    def onNonListCmd(self, line: str, cmdDef):
        super().onNonListCmd(line, cmdDef)

        if cmdDef["name"] == "CS_BEGIN_CUTSCENE":
            self.cs_end_frame = cmdDef["endFrame"]
            self.entrycount_write = 0
        else:
            self.cs_text += line
            self.entrycount_write += 1

    def onListCmd(self, line: str, cmdDef):
        super().onListCmd(line, cmdDef)

        if not self.in_cam_list and not self.in_action_list:
            self.cs_text += line

    def onListStart(self, line: str, cmdDef):
        super().onListStart(line, cmdDef)

        if cmdDef["name"] in CAM_TYPE_LISTS:
            if self.csObj is not None and not self.wrote_cam_lists:
                self.processCamMotionLists(self.csObj)
                self.wrote_cam_lists = True
        elif cmdDef["name"] in ACTION_LISTS:
            if self.csObj is not None and not self.wrote_action_lists:
                self.processActorCueLists(self.csObj)
                self.wrote_action_lists = True
        else:
            self.cs_text += line
            self.entrycount_write += 1

    def processCamMotionLists(self, csObj: Object):
        camShotObjects = getShotObjects(self.context.scene, csObj)

        if len(camShotObjects) == 0:
            raise RuntimeError(f"No camera command lists in cutscene `{csObj.name}`")

        def processLists(useAT: bool):
            for obj in camShotObjects:
                propBones = getShotPropBonesChecked(obj)
                startFrame = obj.data.ootCamShotProp.start_frame
                endFrame = startFrame + getFakeCamCmdsLength(obj, useAT)
                mode = obj.data.ootCamShotProp.cam_mode
                self.cs_text += self.getCamListCmd(startFrame, endFrame, useAT, mode)
                self.entrycount_write += 1

                for i, propBone in enumerate(propBones):
                    camRoll = propBone.camroll if useAT else 0
                    camFrame = propBone.frames if useAT else 0
                    camViewAngle = propBone.fov
                    camPos = propBone.tail if useAT else propBone.head
                    self.cs_text += self.getCamCmd(True, camRoll, camFrame, camViewAngle, camPos, useAT, mode)

                # Extra dummy point
                self.cs_text += self.getCamCmd(False, 0, 0, 0.0, [0.0, 0.0, 0.0], useAT, mode)

        processLists(False)
        processLists(True)

    def processActorCueLists(self, csObj: Object):
        cueObjects = getActorCueListObjects(self.context.scene, csObj, None)

        if len(cueObjects) == 0:
            print("No player or NPC action lists in cutscene")
            return

        for cueObj in cueObjects:
            actor_id = cueObj.ootCSMotionProperty.actorCueListProp.actor_id
            cuePoints = getActorCuePointObjects(self.context.scene, cueObj)

            if len(cuePoints) < 2:
                raise RuntimeError(f"Action {cueObj.name} does not have at least 2 key points!")

            self.cs_text += self.getActorCueListCmd(actor_id, len(cuePoints) - 1)
            self.entrycount_write += 1

            for i in range(len(cuePoints) - 1):
                self.cs_text += self.getActorCueCmd(
                    actor_id,
                    cuePoints[i].ootCSMotionProperty.actorCueProp.action_id,
                    cuePoints[i].ootCSMotionProperty.actorCueProp.start_frame,
                    cuePoints[i + 1].ootCSMotionProperty.actorCueProp.start_frame,
                    cuePoints[i].rotation_euler,
                    cuePoints[i].location,
                    cuePoints[i + 1].location,
                )

    def exportToC(self, filename: str):
        if os.path.isfile(filename):
            tmpfile = f"{filename}.tmp"

            try:
                shutil.copyfile(filename, tmpfile)
            except OSError as err:
                print("Could not make backup file")
                return False
        else:
            tmpfile = None

        ret = None

        try:
            with open(filename, "w") as self.outfile:
                if tmpfile is not None:
                    self.processInputFile(tmpfile)

                for csObj in self.cs_objects:
                    print(
                        csObj.name
                        + " not found in C file, appending to end. This may require manual editing afterwards."
                    )
                    self.outfile.write("\n// clang-format off\n")
                    self.outfile.write(self.getCutsceneArrayName(csObj.name[9:]))
                    self.outfile.write(self.getCutsceneBeginCmd(csObj))
                    self.cs_text = ""
                    self.entrycount_write = 0
                    self.processActorCueLists(csObj)
                    self.processCamMotionLists(csObj)
                    self.outfile.write(self.cs_text)
                    self.outfile.write(self.getCutsceneEndCmd())
                    self.outfile.write("};\n// clang-format on\n")
        except Exception as e:
            print("".join(traceback.TracebackException.from_exception(e).format()))

            if tmpfile is not None:
                print("Aborting, restoring original file")
                shutil.copyfile(tmpfile, filename)

            ret = str(e)

        if tmpfile is not None:
            os.remove(tmpfile)

        return ret

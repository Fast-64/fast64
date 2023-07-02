import math
import traceback
import bpy

from ..utility import OOTCutsceneMotionIOBase, createNewObject, createActorCueList, createActorCuePoint, initCutscene
from ..constants import CAM_TYPE_TO_TYPE, CAM_TYPE_TO_MODE


class OOTCutsceneMotionImport(OOTCutsceneMotionIOBase):
    def __init__(self, context):
        super().__init__(context)

    def importPosition(self, pos):
        # OoT: +X right, +Y up, -Z forward
        # Blender: +X right, +Z up, +Y forward
        return [float(pos[0]) / self.scale, -float(pos[2]) / self.scale, float(pos[1]) / self.scale]

    def importRotation(self, rot):
        def conv(r):
            assert r >= -0x8000 and r <= 0x7FFF
            return 2.0 * math.pi * float(r) / 0x10000

        return [conv(rot[0]), conv(rot[2]), conv(rot[1])]

    def convertCutsceneToBlender(self, csName: str, camEyePoints: list, camATPoints: list, actorCueList: list):
        # Create empty cutscene object
        csObj = createNewObject(self.context, f"Cutscene.{csName}", None, False)

        # Camera import
        for i, eyePoint in enumerate(camEyePoints):
            # Get corresponding atlist
            al = None

            for atPoint in camATPoints:
                if atPoint["startFrame"] == eyePoint["startFrame"]:
                    al = atPoint
                    break

            if al is None or len(eyePoint["data"]) != len(al["data"]) or eyePoint["mode"] != al["mode"]:
                print("Internal error!")
                return False

            if eyePoint["endFrame"] < eyePoint["startFrame"] + 2 or al["endFrame"] < al["startFrame"] + 2:
                print("Cam cmd has nonstandard end frames!")

            name = f"Shot{i + 1:02}"
            shotArmature = bpy.data.armatures.new(name)
            shotArmature.display_type = "STICK"
            shotArmature.show_names = True
            shotArmature.ootCamShotProp.shotStartFrame = eyePoint["startFrame"]
            shotArmature.ootCamShotProp.shotCamMode = eyePoint["mode"]
            shotObj = createNewObject(self.context, name, shotArmature, True)
            shotObj.parent = csObj

            for i in range(len(eyePoint["data"])):
                camEyeData = eyePoint["data"][i]
                camATData = al["data"][i]
                bpy.ops.object.mode_set(mode="EDIT")
                newBone = shotArmature.edit_bones.new(f"K{i + 1:02}")
                boneName = newBone.name
                newBone.head = self.importPosition([camEyeData["xPos"], camEyeData["yPos"], camEyeData["zPos"]])
                newBone.tail = self.importPosition([camATData["xPos"], camATData["yPos"], camATData["zPos"]])
                bpy.ops.object.mode_set(mode="OBJECT")
                newBone = shotArmature.bones[boneName]

                if camEyeData["frame"] != 0:
                    print("Frames must be 0 in cam pos command!")

                newBone.ootCamShotPointProp.shotPointFrame = camATData["frame"]
                newBone.ootCamShotPointProp.shotPointViewAngle = camATData["viewAngle"]
                newBone.ootCamShotPointProp.shotPointRoll = camATData["roll"]

        # Action import
        for cueDef in actorCueList:
            cueObj = createActorCueList(self.context, cueDef["actor_id"], csObj)
            lastFrame = lastPosX = lastPosY = lastPosZ = None

            for cueData in cueDef["data"]:
                if lastFrame is not None:
                    if lastFrame != cueData["startFrame"]:
                        raise RuntimeError("Action list path is not temporally continuous!")

                    if lastPosX != cueData["startX"] or lastPosY != cueData["startY"] or lastPosZ != cueData["startZ"]:
                        raise RuntimeError("Action list path is not spatially continuous!")

                cuePoint = createActorCuePoint(
                    self.context,
                    cueObj,
                    False,
                    self.importPosition([cueData["startX"], cueData["startY"], cueData["startZ"]]),
                    cueData["startFrame"],
                    cueData["action"],
                )
                cuePoint.rotation_euler = self.importRotation([cueData["rotX"], cueData["rotY"], cueData["rotZ"]])
                lastFrame = cueData["endFrame"]
                lastPosX = cueData["endX"]
                lastPosY = cueData["endY"]
                lastPosZ = cueData["endZ"]

            if lastFrame is None:
                raise RuntimeError("Action list path did not have any points!")

            cuePoint = createActorCuePoint(
                self.context, cueObj, False, self.importPosition([lastPosX, lastPosY, lastPosZ]), lastFrame, "0x0000"
            )

        # Init at end to get timing info and set up action previewers
        initCutscene(self.context, csObj)

        return True

    def onCutsceneStart(self, csName: str):
        super().onCutsceneStart(csName)
        self.csname = csName
        self.poslists = []
        self.atlists = []
        self.actionlists = []

    def onCutsceneEnd(self):
        super().onCutsceneEnd()

        if len(self.poslists) != len(self.atlists):
            raise RuntimeError(f"Found {len(self.poslists)} pos lists but {len(self.atlists)} AT lists!")

        if not self.convertCutsceneToBlender(self.csname, self.poslists, self.atlists, self.actionlists):
            raise RuntimeError("convertCutsceneToBlender failed")

    def onListStart(self, line: str, cmdDef):
        super().onListStart(line, cmdDef)
        self.listdata = []

        if cmdDef["name"] == "CS_PLAYER_ACTION_LIST":
            self.listtype = "action"
            self.actor_id = -1
        elif cmdDef["name"] == "CS_NPC_ACTION_LIST":
            self.listtype = "action"
            self.actor_id = cmdDef["cmdType"]
        else:
            self.listtype = CAM_TYPE_TO_TYPE.get(cmdDef["name"], None)

            if self.listtype is None:
                return

            self.listmode = CAM_TYPE_TO_MODE[cmdDef["name"]]
            self.list_startFrame = cmdDef["startFrame"]
            self.list_endFrame = cmdDef["endFrame"]

            if self.listtype == "at":
                # Make sure there's already a cam pos list with this start frame
                for camDef in self.poslists:
                    if camDef["startFrame"] == self.list_startFrame:
                        if camDef["mode"] != self.listmode:
                            raise RuntimeError(
                                f"Got pos list mode {camDef['mode']} starting at {camDef['startFrame']}, "
                                + f"but at list starting at the same frame with mode {self.listmode}!"
                            )
                        self.corresponding_poslist = camDef["data"]
                        break
                else:
                    raise RuntimeError(
                        "Started at list for start frame "
                        + str(self.list_startFrame)
                        + ", but there's no pos list with this start frame!"
                    )

    def onListEnd(self):
        super().onListEnd()

        if self.listtype == "action":
            if len(self.listdata) < 1:
                raise RuntimeError("No action list entries!")

            self.actionlists.append({"actor_id": self.actor_id, "data": self.listdata})
        elif self.listtype in ["pos", "at"]:
            if len(self.listdata) < 4:
                raise RuntimeError(f"Only {len(self.listdata)} key points in camera command!")

            if len(self.listdata) > 4:
                # Extra dummy point at end if there's 5 or more points--remove
                # at import and re-add at export
                del self.listdata[-1]

            if self.listtype == "at" and len(self.listdata) != len(self.corresponding_poslist):
                raise RuntimeError(
                    f"At list contains {len(self.listdata)} commands, "
                    + f"but corresponding pos list contains {len(self.corresponding_poslist)} commands!"
                )
            (self.poslists if self.listtype == "pos" else self.atlists).append(
                {
                    "startFrame": self.list_startFrame,
                    "endFrame": self.list_endFrame,
                    "mode": self.listmode,
                    "data": self.listdata,
                }
            )

    def onListCmd(self, line: str, cmdDef):
        super().onListCmd(line, cmdDef)

        if self.listtype is not None:
            self.listdata.append(cmdDef)

    def importFromC(self, filename: str):
        if self.context.view_layer.objects.active is not None:
            bpy.ops.object.mode_set(mode="OBJECT")

        try:
            self.processInputFile(filename)
        except Exception as e:
            print("".join(traceback.TracebackException.from_exception(e).format()))
            return str(e)

        self.context.scene.frame_set(self.context.scene.frame_start)

        return None

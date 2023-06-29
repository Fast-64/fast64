import math, traceback, bpy
from ..utility import CFileIO, CreateObject, CreateActorAction, CreateActionPoint, initCS


class CFileImport(CFileIO):
    def __init__(self, context):
        super().__init__(context)

    def ImportPos(self, pos):
        # OoT: +X right, +Y up, -Z forward
        # Blender: +X right, +Z up, +Y forward
        return [float(pos[0]) / self.scale, -float(pos[2]) / self.scale, float(pos[1]) / self.scale]

    def ImportRot(self, rot):
        def conv(r):
            assert r >= -0x8000 and r <= 0x7FFF
            return 2.0 * math.pi * float(r) / 0x10000

        return [conv(rot[0]), conv(rot[2]), conv(rot[1])]

    def CSToBlender(self, csname, poslists, atlists, actionlists):
        # Create empty cutscene object
        cs_object = CreateObject(self.context, "Cutscene." + csname, None, False)
        # Camera import
        for shotnum, pl in enumerate(poslists):
            # Get corresponding atlist
            al = None
            for a in atlists:
                if a["startFrame"] == pl["startFrame"]:
                    al = a
                    break
            if al is None or len(pl["data"]) != len(al["data"]) or pl["mode"] != al["mode"]:
                print("Internal error!")
                return False
            if pl["endFrame"] < pl["startFrame"] + 2 or al["endFrame"] < al["startFrame"] + 2:
                print("Cam cmd has nonstandard end frames!")
            name = "Shot{:02}".format(shotnum + 1)
            arm = self.context.blend_data.armatures.new(name)
            arm.display_type = "STICK"
            arm.show_names = True
            arm.start_frame = pl["startFrame"]
            arm.cam_mode = pl["mode"]
            armo = CreateObject(self.context, name, arm, True)
            armo.parent = cs_object
            for i in range(len(pl["data"])):
                pos = pl["data"][i]
                at = al["data"][i]
                bpy.ops.object.mode_set(mode="EDIT")
                bone = arm.edit_bones.new("K{:02}".format(i + 1))
                bname = bone.name
                bone.head = self.ImportPos([pos["xPos"], pos["yPos"], pos["zPos"]])
                bone.tail = self.ImportPos([at["xPos"], at["yPos"], at["zPos"]])
                bpy.ops.object.mode_set(mode="OBJECT")
                bone = arm.bones[bname]
                if pos["frame"] != 0:
                    print("Frames must be 0 in cam pos command!")
                bone.frames = at["frame"]
                bone.fov = at["viewAngle"]
                bone.camroll = at["roll"]
        # Action import
        for l in actionlists:
            al_object = CreateActorAction(self.context, l["actor_id"], cs_object)
            lastf, lastx, lasty, lastz = None, None, None, None
            for p in l["data"]:
                if lastf is not None:
                    if lastf != p["startFrame"]:
                        raise RuntimeError("Action list path is not temporally continuous!")
                    if lastx != p["startX"] or lasty != p["startY"] or lastz != p["startZ"]:
                        raise RuntimeError("Action list path is not spatially continuous!")
                point = CreateActionPoint(
                    self.context,
                    al_object,
                    False,
                    self.ImportPos([p["startX"], p["startY"], p["startZ"]]),
                    p["startFrame"],
                    p["action"],
                )
                point.rotation_euler = self.ImportRot([p["rotX"], p["rotY"], p["rotZ"]])
                lastf = p["endFrame"]
                lastx, lasty, lastz = p["endX"], p["endY"], p["endZ"]
            if lastf is None:
                raise RuntimeError("Action list path did not have any points!")
            point = CreateActionPoint(
                self.context, al_object, False, self.ImportPos([lastx, lasty, lastz]), lastf, "0x0000"
            )
        # Init at end to get timing info and set up action previewers
        initCS(self.context, cs_object)
        return True

    def OnCutsceneStart(self, csname):
        super().OnCutsceneStart(csname)
        self.csname = csname
        self.poslists = []
        self.atlists = []
        self.actionlists = []

    def OnCutsceneEnd(self):
        super().OnCutsceneEnd()
        if len(self.poslists) != len(self.atlists):
            raise RuntimeError(
                "Found " + str(len(self.poslists)) + " pos lists but " + str(len(self.atlists)) + " at lists!"
            )
        if not self.CSToBlender(self.csname, self.poslists, self.atlists, self.actionlists):
            raise RuntimeError("CSToBlender failed")

    def OnListStart(self, l, cmd):
        super().OnListStart(l, cmd)
        self.listdata = []
        if cmd["name"] == "CS_PLAYER_ACTION_LIST":
            self.listtype = "action"
            self.actor_id = -1
        elif cmd["name"] == "CS_NPC_ACTION_LIST":
            self.listtype = "action"
            self.actor_id = cmd["cmdType"]
        else:
            self.listtype = self.CAM_TYPE_TO_TYPE.get(cmd["name"], None)
            if self.listtype is None:
                return
            self.listmode = self.CAM_TYPE_TO_MODE[cmd["name"]]
            self.list_startFrame = cmd["startFrame"]
            self.list_endFrame = cmd["endFrame"]
            if self.listtype == "at":
                # Make sure there's already a cam pos list with this start frame
                for ls in self.poslists:
                    if ls["startFrame"] == self.list_startFrame:
                        if ls["mode"] != self.listmode:
                            raise RuntimeError(
                                "Got pos list mode "
                                + ls["mode"]
                                + " starting at "
                                + ls["startFrame"]
                                + ", but at list starting at the same frame with mode "
                                + self.listmode
                                + "!"
                            )
                        self.corresponding_poslist = ls["data"]
                        break
                else:
                    raise RuntimeError(
                        "Started at list for start frame "
                        + str(self.list_startFrame)
                        + ", but there's no pos list with this start frame!"
                    )

    def OnListEnd(self):
        super().OnListEnd()
        if self.listtype == "action":
            if len(self.listdata) < 1:
                raise RuntimeError("No action list entries!")
            self.actionlists.append({"actor_id": self.actor_id, "data": self.listdata})
        elif self.listtype in ["pos", "at"]:
            if len(self.listdata) < 4:
                raise RuntimeError("Only {} key points in camera command!".format(len(self.listdata)))
            if len(self.listdata) > 4:
                # Extra dummy point at end if there's 5 or more points--remove
                # at import and re-add at export
                del self.listdata[-1]
            if self.listtype == "at" and len(self.listdata) != len(self.corresponding_poslist):
                raise RuntimeError(
                    "At list contains "
                    + str(len(self.listdata))
                    + " commands, but corresponding pos list contains "
                    + str(len(self.corresponding_poslist))
                    + " commands!"
                )
            (self.poslists if self.listtype == "pos" else self.atlists).append(
                {
                    "startFrame": self.list_startFrame,
                    "endFrame": self.list_endFrame,
                    "mode": self.listmode,
                    "data": self.listdata,
                }
            )

    def OnListCmd(self, l, cmd):
        super().OnListCmd(l, cmd)
        if self.listtype is None:
            return
        self.listdata.append(cmd)

    def ImportCFile(self, filename):
        if self.context.view_layer.objects.active is not None:
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            self.TraverseInputFile(filename)
        except Exception as e:
            print("".join(traceback.TracebackException.from_exception(e).format()))
            return str(e)
        self.context.scene.frame_set(self.context.scene.frame_start)
        return None

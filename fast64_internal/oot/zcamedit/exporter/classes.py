import os, shutil, math, traceback
from ..constants import CFileIO
from ..Common import floatBitsAsInt
from ..CamData import GetCamCommands, GetCSFakeEnd, GetCamBonesChecked, GetFakeCamCmdLength
from ..ActionData import GetActionLists, GetActionListPoints


class CFileExport(CFileIO):
    def __init__(self, context, use_floats, use_tabs, use_cscmd):
        super().__init__(context)
        self.use_floats, self.use_tabs, self.use_cscmd = use_floats, use_tabs, use_cscmd
        self.tabstr = "\t" if self.use_tabs else "    "
        self.cs_object = None
        self.GetAllCutsceneObjects()

    def CreateCutsceneStartCmd(self, csname):
        return ("CutsceneData " if self.use_cscmd else "s32 ") + csname + "[] = {\n"

    def CreateCutsceneBeginCmdRaw(self, nentries, end_frame):
        return self.tabstr + "CS_BEGIN_CUTSCENE(" + str(nentries) + ", " + str(end_frame) + "),\n"

    def CreateCutsceneBeginCmd(self, cs_object):
        return self.CreateCutsceneBeginCmdRaw(
            len(GetCamCommands(self.context.scene, cs_object)) * 2
            + len(GetActionLists(self.context.scene, cs_object, None)),
            GetCSFakeEnd(self.context, cs_object),
        )

    def CreateCutsceneEndCmd(self):
        return self.tabstr + "CS_END(),\n"

    def CreateCamListCmd(self, start, end, at, mode):
        return self.tabstr + self.ATMODE_TO_CMD[at][mode] + "_LIST(" + str(start) + ", " + str(end) + "),\n"

    def WritePos(self, pos):
        x, y, z = int(round(pos[0] * self.scale)), int(round(pos[2] * self.scale)), int(round(-pos[1] * self.scale))
        if any(v < -0x8000 or v >= 0x8000 for v in (x, y, z)):
            raise RuntimeError("Position(s) too large, out of range: {}, {}, {}".format(x, y, z))
        return str(x) + ", " + str(y) + ", " + str(z)

    def WriteRotU32(self, rot):
        def conv(r):
            r /= 2.0 * math.pi
            r -= math.floor(r)
            r = round(r * 0x10000)
            if r >= 0x8000:
                r += 0xFFFF0000
            assert r >= 0 and r <= 0xFFFFFFFF and (r <= 0x7FFF or r >= 0xFFFF8000)
            return hex(r)

        return conv(rot[0]) + ", " + conv(rot[2]) + ", " + conv(rot[1])

    def CreateCamCmd(self, c_continue, c_roll, c_frames, c_fov, pos, at, mode):
        if self.use_cscmd:
            c_continue = "CS_CMD_CONTINUE" if c_continue else "CS_CMD_STOP"
        else:
            c_continue = "0" if c_continue else "-1"
        cmd = self.tabstr * 2 + self.ATMODE_TO_CMD[at][mode] + "(" + c_continue + ", "
        cmd += str(c_roll) + ", "
        cmd += str(c_frames) + ", "
        cmd += (str(c_fov) + "f" if self.use_floats else hex(floatBitsAsInt(c_fov))) + ", "
        cmd += self.WritePos(pos) + ", 0),\n"
        return cmd

    def CreateActionListCmd(self, actor_id, points):
        return (
            self.tabstr
            + ("CS_PLAYER_ACTION_LIST(" if actor_id < 0 else ("CS_NPC_ACTION_LIST(" + str(actor_id) + ", "))
            + str(points)
            + "),\n"
        )

    def CreateActionCmd(self, actor_id, action_id, start_frame, end_frame, rot, start_pos, end_pos):
        cmd = self.tabstr * 2 + ("CS_PLAYER_ACTION" if actor_id < 0 else "CS_NPC_ACTION")
        cmd += "(" + action_id + ", "
        cmd += str(start_frame) + ", " + str(end_frame) + ", "
        cmd += self.WriteRotU32(rot) + ", "
        cmd += self.WritePos(start_pos) + ", "
        cmd += self.WritePos(end_pos) + ", "
        cmd += "0, 0, 0),\n"  # "Normals" which are probably garbage data
        return cmd

    def GetAllCutsceneObjects(self):
        self.cs_objects = []
        for o in self.context.blend_data.objects:
            if o.type != "EMPTY":
                continue
            if not o.name.startswith("Cutscene."):
                continue
            self.cs_objects.append(o)

    def OnCutsceneStart(self, csname):
        super().OnCutsceneStart(csname)
        self.wrote_cam_lists = False
        self.wrote_action_lists = False
        for o in self.cs_objects:
            if o.name == "Cutscene." + csname:
                self.cs_object = o
                self.cs_objects.remove(o)
                print("Replacing camera commands in cutscene " + csname)
                break
        else:
            self.cs_object = None
            print("Scene does not contain cutscene " + csname + " in file, skipping")
        self.outfile.write(self.CreateCutsceneStartCmd(csname))
        self.cs_text = ""

    def OnCutsceneEnd(self):
        super().OnCutsceneEnd()
        if self.cs_object is not None:
            if not self.wrote_cam_lists:
                print("Cutscene did not contain any existing camera commands, adding at end")
                self.WriteCamMotion(self.cs_object)
            if not self.wrote_action_lists:
                print("Cutscene did not contain any existing action lists, adding at end")
                self.WriteActionLists(self.cs_object)
        self.cs_object = None
        self.cs_text += self.CreateCutsceneEndCmd()
        self.outfile.write(self.CreateCutsceneBeginCmdRaw(self.entrycount_write, self.cs_end_frame))
        self.outfile.write(self.cs_text)

    def OnLineOutsideCS(self, l):
        super().OnLineOutsideCS(l)
        self.outfile.write(l)

    def OnNonListCmd(self, l, cmd):
        super().OnNonListCmd(l, cmd)
        if cmd["name"] == "CS_BEGIN_CUTSCENE":
            self.cs_end_frame = cmd["endFrame"]
            self.entrycount_write = 0
        else:
            self.cs_text += l
            self.entrycount_write += 1

    def OnListCmd(self, l, cmd):
        super().OnListCmd(l, cmd)
        if not self.in_cam_list and not self.in_action_list:
            self.cs_text += l

    def OnListStart(self, l, cmd):
        super().OnListStart(l, cmd)
        if cmd["name"] in self.CAM_TYPE_LISTS:
            if self.cs_object is not None and not self.wrote_cam_lists:
                self.WriteCamMotion(self.cs_object)
                self.wrote_cam_lists = True
        elif cmd["name"] in self.ACTION_LISTS:
            if self.cs_object is not None and not self.wrote_action_lists:
                self.WriteActionLists(self.cs_object)
                self.wrote_action_lists = True
        else:
            self.cs_text += l
            self.entrycount_write += 1

    def WriteCamMotion(self, cs_object):
        cmdlists = GetCamCommands(self.context.scene, cs_object)
        if len(cmdlists) == 0:
            raise RuntimeError("No camera command lists in cutscene " + cs_object.name)

        def WriteLists(at):
            for l in cmdlists:
                bones = GetCamBonesChecked(l)
                sf = l.data.start_frame
                mode = l.data.cam_mode
                self.cs_text += self.CreateCamListCmd(sf, sf + GetFakeCamCmdLength(l, at), at, mode)
                self.entrycount_write += 1
                for i, b in enumerate(bones):
                    c_roll = b.camroll if at else 0
                    c_frames = b.frames if at else 0
                    c_fov = b.fov
                    c_pos = b.tail if at else b.head
                    self.cs_text += self.CreateCamCmd(True, c_roll, c_frames, c_fov, c_pos, at, mode)
                # Extra dummy point
                self.cs_text += self.CreateCamCmd(False, 0, 0, 0.0, [0.0, 0.0, 0.0], at, mode)

        WriteLists(False)
        WriteLists(True)

    def WriteActionLists(self, cs_object):
        actionlists = GetActionLists(self.context.scene, cs_object, None)
        if len(actionlists) == 0:
            print("No player or NPC action lists in cutscene")
            return
        for al_object in actionlists:
            actor_id = al_object.zc_alist.actor_id
            points = GetActionListPoints(self.context.scene, al_object)
            if len(points) < 2:
                raise RuntimeError("Action " + al_object.name + " does not have at least 2 key points!")
            self.cs_text += self.CreateActionListCmd(actor_id, len(points) - 1)
            self.entrycount_write += 1
            for p in range(len(points) - 1):
                self.cs_text += self.CreateActionCmd(
                    actor_id,
                    points[p].zc_apoint.action_id,
                    points[p].zc_apoint.start_frame,
                    points[p + 1].zc_apoint.start_frame,
                    points[p].rotation_euler,
                    points[p].location,
                    points[p + 1].location,
                )

    def ExportCFile(self, filename):
        if os.path.isfile(filename):
            tmpfile = filename + ".tmp"
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
                    self.TraverseInputFile(tmpfile)
                for o in self.cs_objects:
                    print(
                        o.name + " not found in C file, appending to end. This may require manual editing afterwards."
                    )
                    self.outfile.write("\n// clang-format off\n")
                    self.outfile.write(self.CreateCutsceneStartCmd(o.name[9:]))
                    self.outfile.write(self.CreateCutsceneBeginCmd(o))
                    self.cs_text = ""
                    self.entrycount_write = 0
                    self.WriteActionLists(o)
                    self.WriteCamMotion(o)
                    self.outfile.write(self.cs_text)
                    self.outfile.write(self.CreateCutsceneEndCmd())
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

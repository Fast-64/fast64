import os, shutil, math, traceback, bpy
from .Common import intBitsAsFloat, floatBitsAsInt, CreateObject
from .CamData import GetCamCommands, GetCSFakeEnd, GetCamBonesChecked, GetFakeCamCmdLength
from .ActionData import CreateActorAction, CreateActionPoint, GetActionLists, GetActionListPoints
from .InitCS import InitCS


class CFileIO:
    def __init__(self, context):
        self.context, self.scale = context, context.scene.ootBlenderScale

    # Default width is 16

    CAM_LIST_PARAMS = [
        {"name": "continueFlag", "type": "continueFlag"},
        {"name": "roll", "type": "int", "width": 8},
        {"name": "frame", "type": "int"},
        {"name": "viewAngle", "type": "int_or_float", "min": 0.0, "max": 179.99},
        {"name": "xPos", "type": "int"},
        {"name": "yPos", "type": "int"},
        {"name": "zPos", "type": "int"},
        {"name": "unused", "type": "int"},
    ]

    ACTOR_ACTION_PARAMS = [
        {"name": "action", "type": "string"},
        {"name": "startFrame", "type": "int"},
        {"name": "endFrame", "type": "int"},
        {"name": "rotX", "type": "hex"},
        {"name": "rotY", "type": "hex"},
        {"name": "rotZ", "type": "hex"},
        {"name": "startX", "type": "int", "width": 32},
        {"name": "startY", "type": "int", "width": 32},
        {"name": "startZ", "type": "int", "width": 32},
        {"name": "endX", "type": "int", "width": 32},
        {"name": "endY", "type": "int", "width": 32},
        {"name": "endZ", "type": "int", "width": 32},
        {"name": "normX", "type": "int_or_float", "width": 32},
        {"name": "normY", "type": "int_or_float", "width": 32},
        {"name": "normZ", "type": "int_or_float", "width": 32},
    ]

    BGM_PARAMS = [
        {"name": "id", "type": "string"},
        {"name": "startFrame", "type": "int"},
        {"name": "endFrame", "type": "int"},
        {"name": "unused0", "type": "int"},
        {"name": "unused1", "type": "int", "width": 32},
        {"name": "unused2", "type": "int", "width": 32},
        {"name": "unused3", "type": "int", "width": 32},
        {"name": "unused4", "type": "int", "width": 32},
        {"name": "unused5", "type": "int", "width": 32},
        {"name": "unused6", "type": "int", "width": 32},
        {"name": "unused7", "type": "int", "width": 32},
    ]

    CAM_TYPE_LISTS = [
        "CS_CAM_POS_LIST",
        "CS_CAM_FOCUS_POINT_LIST",
        "CS_CAM_POS_PLAYER_LIST",
        "CS_CAM_FOCUS_POINT_PLAYER_LIST",
        "CS_CMD_07_LIST",
        "CS_CMD_08_LIST",
    ]

    CAM_TYPE_TO_TYPE = {
        "CS_CAM_POS_LIST": "pos",
        "CS_CAM_FOCUS_POINT_LIST": "at",
        "CS_CAM_POS_PLAYER_LIST": "pos",
        "CS_CAM_FOCUS_POINT_PLAYER_LIST": "at",
        "CS_CMD_07_LIST": "pos",
        "CS_CMD_08_LIST": "at",
    }

    CAM_TYPE_TO_MODE = {
        "CS_CAM_POS_LIST": "normal",
        "CS_CAM_FOCUS_POINT_LIST": "normal",
        "CS_CAM_POS_PLAYER_LIST": "rel_link",
        "CS_CAM_FOCUS_POINT_PLAYER_LIST": "rel_link",
        "CS_CMD_07_LIST": "0708",
        "CS_CMD_08_LIST": "0708",
    }

    ATMODE_TO_CMD = {
        False: {"normal": "CS_CAM_POS", "rel_link": "CS_CAM_POS_PLAYER", "0708": "CS_CMD_07"},
        True: {"normal": "CS_CAM_FOCUS_POINT", "rel_link": "CS_CAM_FOCUS_POINT_PLAYER", "0708": "CS_CMD_08"},
    }

    ACTION_LISTS = ["CS_PLAYER_ACTION_LIST", "CS_NPC_ACTION_LIST"]

    LISTS_DEF = [
        {
            "name": "CS_CAM_POS_LIST",
            "params": [{"name": "startFrame", "type": "int"}, {"name": "endFrame", "type": "int"}],
            "commands": [{"name": "CS_CAM_POS", "params": CAM_LIST_PARAMS}],
        },
        {
            "name": "CS_CAM_FOCUS_POINT_LIST",
            "params": [{"name": "startFrame", "type": "int"}, {"name": "endFrame", "type": "int"}],
            "commands": [{"name": "CS_CAM_FOCUS_POINT", "params": CAM_LIST_PARAMS}],
        },
        {
            "name": "CS_MISC_LIST",
            "params": [{"name": "entries", "type": "int", "min": 1}],
            "commands": [
                {
                    "name": "CS_MISC",
                    "params": [
                        {"name": "unk", "type": "hex"},
                        {"name": "startFrame", "type": "int"},
                        {"name": "endFrame", "type": "int"},
                        {"name": "unused0", "type": "hex"},
                        {"name": "unused1", "type": "hex", "width": 32},
                        {"name": "unused2", "type": "hex", "width": 32},
                        {"name": "unused3", "type": "int", "width": 32},
                        {"name": "unused4", "type": "int", "width": 32},
                        {"name": "unused5", "type": "int", "width": 32},
                        {"name": "unused6", "type": "int", "width": 32},
                        {"name": "unused7", "type": "int", "width": 32},
                        {"name": "unused8", "type": "int", "width": 32},
                        {"name": "unused9", "type": "int", "width": 32},
                        {"name": "unused10", "type": "int", "width": 32},
                    ],
                }
            ],
        },
        {
            "name": "CS_LIGHTING_LIST",
            "params": [{"name": "entries", "type": "int", "min": 1}],
            "commands": [
                {
                    "name": "CS_LIGHTING",
                    "params": [
                        {"name": "setting", "type": "int"},
                        {"name": "startFrame", "type": "int"},
                        {"name": "endFrame", "type": "int"},
                        {"name": "unused0", "type": "int"},
                        {"name": "unused1", "type": "int", "width": 32},
                        {"name": "unused2", "type": "int", "width": 32},
                        {"name": "unused3", "type": "int", "width": 32},
                        {"name": "unused4", "type": "int", "width": 32},
                        {"name": "unused5", "type": "int", "width": 32},
                        {"name": "unused6", "type": "int", "width": 32},
                        {"name": "unused7", "type": "int", "width": 32},
                    ],
                }
            ],
        },
        {
            "name": "CS_CAM_POS_PLAYER_LIST",
            "params": [{"name": "startFrame", "type": "int"}, {"name": "endFrame", "type": "int"}],
            "commands": [{"name": "CS_CAM_POS_PLAYER", "params": CAM_LIST_PARAMS}],
        },
        {
            "name": "CS_CAM_FOCUS_POINT_PLAYER_LIST",
            "params": [{"name": "startFrame", "type": "int"}, {"name": "endFrame", "type": "int"}],
            "commands": [{"name": "CS_CAM_FOCUS_POINT_PLAYER", "params": CAM_LIST_PARAMS}],
        },
        {
            "name": "CS_CMD_07_LIST",
            "params": [
                {"name": "unk", "type": "hex"},
                {"name": "startFrame", "type": "int"},
                {"name": "endFrame", "type": "int"},
                {"name": "unused", "type": "hex"},
            ],
            "commands": [{"name": "CS_CMD_07", "params": CAM_LIST_PARAMS}],
        },
        {
            "name": "CS_CMD_08_LIST",
            "params": [
                {"name": "unk", "type": "hex"},
                {"name": "startFrame", "type": "int"},
                {"name": "endFrame", "type": "int"},
                {"name": "unused", "type": "hex"},
            ],
            "commands": [{"name": "CS_CMD_08", "params": CAM_LIST_PARAMS}],
        },
        {
            "name": "CS_CMD_09_LIST",
            "params": [{"name": "entries", "type": "int", "min": 1}],
            "commands": [
                {
                    "name": "CS_CMD_09",
                    "params": [
                        {"name": "unk", "type": "int"},
                        {"name": "startFrame", "type": "int"},
                        {"name": "endFrame", "type": "int"},
                        {"name": "unk2", "type": "int", "width": 8},
                        {"name": "unk3", "type": "int", "width": 8},
                        {"name": "unk4", "type": "int", "width": 8},
                        {"name": "unused0", "type": "int", "width": 8},
                        {"name": "unused1", "type": "int"},
                    ],
                }
            ],
        },
        {
            "name": "CS_UNK_DATA_LIST",
            "params": [{"name": "cmdType", "type": "int"}, {"name": "entries", "type": "int", "min": 1}],
            "commands": [
                {
                    "name": "CS_UNK_DATA",
                    "params": [
                        {"name": "unk1", "type": "int", "width": 32},
                        {"name": "unk2", "type": "int", "width": 32},
                        {"name": "unk3", "type": "int", "width": 32},
                        {"name": "unk4", "type": "int", "width": 32},
                        {"name": "unk5", "type": "int", "width": 32},
                        {"name": "unk6", "type": "int", "width": 32},
                        {"name": "unk7", "type": "int", "width": 32},
                        {"name": "unk8", "type": "int", "width": 32},
                        {"name": "unk9", "type": "int", "width": 32},
                        {"name": "unk10", "type": "int", "width": 32},
                        {"name": "unk11", "type": "int", "width": 32},
                        {"name": "unk12", "type": "int", "width": 32},
                    ],
                }
            ],
        },
        {
            "name": "CS_NPC_ACTION_LIST",
            "params": [{"name": "cmdType", "type": "int"}, {"name": "entries", "type": "int", "min": 1}],
            "commands": [{"name": "CS_NPC_ACTION", "params": ACTOR_ACTION_PARAMS}],
        },
        {
            "name": "CS_PLAYER_ACTION_LIST",
            "params": [{"name": "entries", "type": "int", "min": 1}],
            "commands": [{"name": "CS_PLAYER_ACTION", "params": ACTOR_ACTION_PARAMS}],
        },
        {
            "name": "CS_TEXT_LIST",
            "params": [{"name": "entries", "type": "int", "min": 1}],
            "commands": [
                {
                    "name": "CS_TEXT_DISPLAY_TEXTBOX",
                    "params": [
                        {"name": "messageId", "type": "int"},
                        {"name": "startFrame", "type": "int"},
                        {"name": "endFrame", "type": "int"},
                        {"name": "type", "type": "int"},
                        {"name": "topOptionBranch", "type": "int"},
                        {"name": "bottomOptionBranch", "type": "int"},
                    ],
                },
                {
                    "name": "CS_TEXT_NONE",
                    "params": [{"name": "startFrame", "type": "int"}, {"name": "endFrame", "type": "int"}],
                },
                {
                    "name": "CS_TEXT_LEARN_SONG",
                    "params": [
                        {"name": "ocarinaSongAction", "type": "int"},
                        {"name": "startFrame", "type": "int"},
                        {"name": "endFrame", "type": "int"},
                        {"name": "messageId", "type": "int"},
                    ],
                },
            ],
        },
        {
            "name": "CS_PLAY_BGM_LIST",
            "params": [{"name": "entries", "type": "int", "min": 1}],
            "commands": [{"name": "CS_PLAY_BGM", "params": BGM_PARAMS}],
        },
        {
            "name": "CS_STOP_BGM_LIST",
            "params": [{"name": "entries", "type": "int", "min": 1}],
            "commands": [{"name": "CS_STOP_BGM", "params": BGM_PARAMS}],
        },
        {
            "name": "CS_FADE_BGM_LIST",
            "params": [{"name": "entries", "type": "int", "min": 1}],
            "commands": [{"name": "CS_FADE_BGM", "params": BGM_PARAMS}],
        },
        {
            "name": "CS_TIME_LIST",
            "params": [{"name": "entries", "type": "int", "min": 1}],
            "commands": [
                {
                    "name": "CS_TIME",
                    "params": [
                        {"name": "unk", "type": "int"},
                        {"name": "startFrame", "type": "int"},
                        {"name": "endFrame", "type": "int"},
                        {"name": "hour", "type": "int", "width": 8},
                        {"name": "min", "type": "int", "width": 8},
                        {"name": "unused", "type": "int", "width": 32},
                    ],
                }
            ],
        },
    ]

    NONLISTS_DEF = [
        {
            "name": "CS_BEGIN_CUTSCENE",
            "params": [
                {"name": "totalEntries", "type": "int", "min": 0},
                {"name": "endFrame", "type": "int", "min": 1},
            ],
        },
        {
            "name": "CS_SCENE_TRANS_FX",
            "params": [
                {"name": "transitionType", "type": "int"},
                {"name": "startFrame", "type": "int"},
                {"name": "endFrame", "type": "int"},
            ],
        },
        {
            "name": "CS_TERMINATOR",
            "params": [
                {"name": "dest", "type": "hex"},
                {"name": "startFrame", "type": "int"},
                {"name": "endFrame", "type": "int"},
            ],
        },
        {"name": "CS_END", "params": []},
    ]

    def ParseParams(self, cmddef, l):
        assert l.startswith(cmddef["name"] + "(")
        assert l.endswith("),")
        toks = [t.strip() for t in l[len(cmddef["name"]) + 1 : -2].split(",") if t.strip()]
        if len(toks) != len(cmddef["params"]):
            raise RuntimeError(
                "Command "
                + cmddef["name"]
                + " requires "
                + str(len(cmddef["params"]))
                + " params but only "
                + str(len(toks))
                + " found in file"
            )
        ret = {"name": cmddef["name"]}
        for t, p in zip(toks, cmddef["params"]):
            if p["type"] in ("int", "hex"):
                try:
                    value = int(t, 0)
                except ValueError:
                    raise RuntimeError("Invalid numeric value for " + p["name"] + " in " + l)
                width = p.get("width", 16)
                if width == 16 and value >= 0xFFFF8000 and value <= 0xFFFFFFFF:
                    value -= 0x100000000
                elif width == 8 and value >= 0xFFFFFF80 and value <= 0xFFFFFFFF:
                    value -= 0x100000000
                elif value >= (1 << width) or value < -(1 << (width - 1)):
                    raise RuntimeError("Value out of range for " + p["name"] + " in " + l)
                elif value >= (1 << (width - 1)):
                    value -= 1 << width
            elif p["type"] == "continueFlag":
                if t in ["0", "CS_CMD_CONTINUE"]:
                    value = True
                elif t in ["-1", "CS_CMD_STOP"]:
                    value = False
                else:
                    raise RuntimeError("Invalid continueFlag value for " + p["name"] + " in " + l)
            elif p["type"] == "int_or_float":
                if t.startswith("0x"):
                    value = intBitsAsFloat(int(t, 16))
                elif t.endswith("f"):
                    value = float(t[:-1])
                    if not math.isfinite(value):
                        raise RuntimeError("Invalid float value for " + p["name"] + " in " + l)
                else:
                    raise RuntimeError("Invalid int_or_float value for " + p["name"] + " in " + l)
            elif p["type"] == "string":
                value = t
            else:
                raise RuntimeError("Invalid command parameter type: " + p["type"])
            if ("min" in p and value < p["min"]) or ("max" in p and value >= p["max"]):
                raise RuntimeError("Value out of range for " + p["name"] + " in " + l)
            ret[p["name"]] = value
        return ret

    def ParseCommand(self, l, curlist):
        sl = l.strip()
        if not sl.endswith("),"):
            raise RuntimeError("Syntax error: " + sl)
        if curlist is not None:
            ldef = next((c for c in self.LISTS_DEF if c["name"] == curlist), None)
            if ldef is None:
                raise RuntimeError("Invalid current list: " + curlist)
            for lcmd in ldef["commands"]:
                if sl.startswith(lcmd["name"] + "("):
                    if not l.startswith("\t\t") and not l.startswith("        "):
                        print("Warning, invalid indentation in " + curlist + ": " + sl)
                    return self.ParseParams(lcmd, sl), "same"
        if not (l.startswith("\t") and len(l) > 1 and l[1] != "\t") and not (
            l.startswith("    ") and len(l) > 4 and l[4] != " "
        ):
            print("Warning, invalid indentation: " + sl)
        ldef = next((c for c in self.LISTS_DEF if sl.startswith(c["name"] + "(")), None)
        if ldef is not None:
            return self.ParseParams(ldef, sl), ldef["name"]
        ldef = next((c for c in self.NONLISTS_DEF if sl.startswith(c["name"] + "(")), None)
        if ldef is not None:
            return self.ParseParams(ldef, sl), None
        raise RuntimeError("Invalid command: " + l)

    def IsGetCutsceneStart(self, l):
        toks = [t for t in l.strip().split(" ") if t]
        if len(toks) != 4:
            return None
        if toks[0] not in ["s32", "CutsceneData"]:
            return None
        if not toks[1].endswith("[]"):
            return None
        if toks[2] != "=" or toks[3] != "{":
            return None
        return toks[1][:-2]

    def OnLineOutsideCS(self, l):
        pass

    def OnCutsceneStart(self, csname):
        self.first_cs_cmd = True
        self.curlist = None
        self.in_cam_list = False
        self.in_action_list = False
        self.entrycount = 0

    def OnNonListCmd(self, l, cmd):
        if cmd["name"] != "CS_BEGIN_CUTSCENE":
            self.entrycount += 1

    def OnListStart(self, l, cmd):
        self.entrycount += 1
        if cmd["name"] in self.CAM_TYPE_LISTS:
            self.in_cam_list = True
            self.cam_list_last = False
        elif cmd["name"] in self.ACTION_LISTS:
            self.in_action_list = True
        if "entries" in cmd:
            self.list_nentries = cmd["entries"]
            self.list_entrycount = 0
        else:
            self.list_nentries = None

    def OnListCmd(self, l, cmd):
        if self.list_nentries is not None:
            self.list_entrycount += 1
        if self.in_cam_list:
            if self.cam_list_last:
                raise RuntimeError("More camera commands after last cmd! " + l)
            self.cam_list_last = not cmd["continueFlag"]

    def OnListEnd(self):
        if self.list_nentries is not None and self.list_nentries != self.list_entrycount:
            raise RuntimeError(
                "List "
                + self.curlist
                + " was supposed to have "
                + str(self.list_nentries)
                + " entries but actually had "
                + str(self.list_entrycount)
                + "!"
            )
        if self.in_cam_list and not self.cam_list_last:
            raise RuntimeError("Camera list terminated without stop marker!")
        self.in_cam_list = False
        self.in_action_list = False

    def OnCutsceneEnd(self):
        if self.nentries != self.entrycount:
            raise RuntimeError(
                "Cutscene header claimed "
                + str(self.nentries)
                + " entries but only "
                + str(self.entrycount)
                + " found!"
            )

    def TraverseInputFile(self, filename):
        state = "OutsideCS"
        with open(filename, "r") as infile:
            # Merge lines which were broken as long lines
            lines = []
            parenopen = 0
            for l in infile:
                if parenopen < 0 or parenopen > 5:
                    raise RuntimeError("Parentheses parsing failed near line: " + l)
                elif parenopen > 0:
                    lines[-1] += " " + l
                else:
                    lines.append(l)
                parenopen += l.count("(")
                parenopen -= l.count(")")
            if parenopen != 0:
                raise RuntimeError("Unbalanced parentheses by end of file")
            for l in lines:
                if state == "OutsideCS":
                    csname = self.IsGetCutsceneStart(l)
                    if csname is not None:
                        print("Found cutscene " + csname)
                        self.OnCutsceneStart(csname)
                        state = "InsideCS"
                    else:
                        self.OnLineOutsideCS(l)
                    continue
                cmd, newlist = self.ParseCommand(l, self.curlist)
                if self.first_cs_cmd or cmd["name"] == "CS_BEGIN_CUTSCENE":
                    if not self.first_cs_cmd or not cmd["name"] == "CS_BEGIN_CUTSCENE":
                        raise RuntimeError("First command in cutscene must be only CS_BEGIN_CUTSCENE! " + l)
                    self.nentries = cmd["totalEntries"]
                    self.first_cs_cmd = False
                if newlist == "same":
                    self.OnListCmd(l, cmd)
                else:
                    if self.curlist is not None:
                        self.OnListEnd()
                    self.curlist = newlist
                    if cmd["name"] == "CS_END":
                        self.OnCutsceneEnd()
                        state = "OutsideCS"
                    elif newlist is None:
                        self.OnNonListCmd(l, cmd)
                    else:
                        self.OnListStart(l, cmd)
        if state != "OutsideCS":
            raise RuntimeError("Unexpected EOF!")


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
        InitCS(self.context, cs_object)
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


def ImportCFile(context, filename):
    im = CFileImport(context)
    return im.ImportCFile(filename)


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


def ExportCFile(context, filename, use_floats, use_tabs, use_cscmd):
    ex = CFileExport(context, use_floats, use_tabs, use_cscmd)
    return ex.ExportCFile(filename)

import math
from struct import pack, unpack
from .CamData import GetCSFakeEnd
from .ActionData import IsActionList, CreateOrInitPreview


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


def MetersToBlend(context, v):
    return v * 56.0 / context.scene.ootBlenderScale


def intBitsAsFloat(i):
    """From https://stackoverflow.com/questions/14431170/get-the-bits-of-a-float-in-python"""
    s = pack(">l", i)
    return unpack(">f", s)[0]


def CreateObject(context, name, data, select):
    obj = context.blend_data.objects.new(name=name, object_data=data)
    context.view_layer.active_layer_collection.collection.objects.link(obj)
    if select:
        obj.select_set(True)
        context.view_layer.objects.active = obj
    return obj


def CheckGetCSObj(op, context):
    """Check if we are editing a cutscene."""
    cs_object = context.view_layer.objects.active
    if cs_object is None or cs_object.type != "EMPTY":
        if op:
            op.report({"WARNING"}, "Must have an empty object active (selected)")
        return None
    if not cs_object.name.startswith("Cutscene."):
        if op:
            op.report({"WARNING"}, 'Cutscene empty object must be named "Cutscene.<YourCutsceneName>"')
        return None
    return cs_object


def initCS(context, cs_object):
    # Add or move camera
    camo = None
    nocam = True
    for o in context.blend_data.objects:
        if o.type != "CAMERA":
            continue
        nocam = False
        if o.parent is not None and o.parent != cs_object:
            continue
        camo = o
        break
    if nocam:
        cam = context.blend_data.cameras.new("Camera")
        camo = CreateObject(context, "Camera", cam, False)
        print("Created new camera")
    if camo is not None:
        camo.parent = cs_object
        camo.data.display_size = MetersToBlend(context, 0.25)
        camo.data.passepartout_alpha = 0.95
        camo.data.clip_start = MetersToBlend(context, 1e-3)
        camo.data.clip_end = MetersToBlend(context, 200.0)
    # Preview actions
    for o in context.blend_data.objects:
        if IsActionList(o):
            CreateOrInitPreview(context, o.parent, o.zc_alist.actor_id, False)
    # Other setup
    context.scene.frame_start = 0
    context.scene.frame_end = max(GetCSFakeEnd(context, cs_object), context.scene.frame_end)
    context.scene.render.fps = 20
    context.scene.render.resolution_x = 320
    context.scene.render.resolution_y = 240

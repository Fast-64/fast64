import math
from struct import pack, unpack
from .constants import LISTS_DEF, NONLISTS_DEF, CAM_TYPE_LISTS, ACTION_LISTS


class CFileIO:
    def __init__(self, context):
        self.context, self.scale = context, context.scene.ootBlenderScale

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
            ldef = next((c for c in LISTS_DEF if c["name"] == curlist), None)
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
        ldef = next((c for c in LISTS_DEF if sl.startswith(c["name"] + "(")), None)
        if ldef is not None:
            return self.ParseParams(ldef, sl), ldef["name"]
        ldef = next((c for c in NONLISTS_DEF if sl.startswith(c["name"] + "(")), None)
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
        if cmd["name"] in CAM_TYPE_LISTS:
            self.in_cam_list = True
            self.cam_list_last = False
        elif cmd["name"] in ACTION_LISTS:
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


class PropsBone:
    def __init__(self, armo, b):
        eb = BoneToEditBone(armo, b) if armo.mode == "EDIT" else None
        self.name = b.name
        self.head = eb.head if eb is not None else b.head
        self.tail = eb.tail if eb is not None else b.tail
        self.frames = eb["frames"] if eb is not None and "frames" in eb else b.frames
        self.fov = eb["fov"] if eb is not None and "fov" in eb else b.fov
        self.camroll = eb["camroll"] if eb is not None and "camroll" in eb else b.camroll


def BoneToEditBone(armo, b):
    for eb in armo.data.edit_bones:
        if eb.name == b.name:
            return eb
    else:
        print("Could not find corresponding bone")
        return b


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


# action data
def IsActionList(obj):
    if obj is None or obj.type != "EMPTY":
        return False
    if not any(obj.name.startswith(s) for s in ["Path.", "ActionList."]):
        return False
    if obj.parent is None or obj.parent.type != "EMPTY" or not obj.parent.name.startswith("Cutscene."):
        return False
    return True


def IsPreview(obj):
    if obj is None or obj.type != "EMPTY":
        return False
    if not obj.name.startswith("Preview."):
        return False
    if obj.parent is None or obj.parent.type != "EMPTY" or not obj.parent.name.startswith("Cutscene."):
        return False
    return True


def GetActorName(actor_id):
    return "Link" if actor_id < 0 else "Actor" + str(actor_id)


def CreateOrInitPreview(context, cs_object, actor_id, select=False):
    for o in context.blend_data.objects:
        if IsPreview(o) and o.parent == cs_object and o.zc_alist.actor_id == actor_id:
            preview = o
            break
    else:
        preview = CreateObject(context, "Preview." + GetActorName(actor_id) + ".001", None, select)
        preview.parent = cs_object

    actorHeight = 1.5
    if actor_id < 0:
        actorHeight = 1.7 if context.scene.zc_previewlinkage == "link_adult" else 1.3

    preview.empty_display_type = "SINGLE_ARROW"
    preview.empty_display_size = MetersToBlend(context, actorHeight)
    preview.zc_alist.actor_id = actor_id


# camdata
def GetCamBones(armo):
    bones = []
    for b in armo.data.bones:
        if b.parent is not None:
            print("Camera armature bones are not allowed to have parent bones")
            return None
        bones.append(PropsBone(armo, b))
    bones.sort(key=lambda b: b.name)
    return bones


def GetCamBonesChecked(cmd):
    bones = GetCamBones(cmd)
    if bones is None:
        raise RuntimeError("Error in bone properties")
    if len(bones) < 4:
        raise RuntimeError("Only {} bones in {}".format(len(bones), cmd.name))
    return bones


def GetCamCommands(scene, cso):
    ret = []
    for o in scene.objects:
        if o.type != "ARMATURE":
            continue
        if o.parent is None:
            continue
        if o.parent != cso:
            continue
        ret.append(o)
    ret.sort(key=lambda o: o.name)
    return ret


def GetFakeCamCmdLength(armo, at):
    bones = GetCamBonesChecked(armo)
    base = max(2, sum(b.frames for b in bones))
    # Seems to be the algorithm which was used in the canon tool: the at list
    # counts the extra point (same frames as the last real point), and the pos
    # list doesn't count the extra point but adds 1. Of course, neither of these
    # values is actually the number of frames the camera motion lasts for.
    return base + (bones[-1].frames if at else 1)


def GetCSFakeEnd(context, cs_object):
    cmdlists = GetCamCommands(context.scene, cs_object)
    cs_endf = -1
    for c in cmdlists:
        end_frame = c.data.start_frame + GetFakeCamCmdLength(c, False) + 1
        cs_endf = max(cs_endf, end_frame)
    return cs_endf


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


# action data leftovers
def IsActionPoint(obj):
    if obj is None or obj.type != "EMPTY":
        return False
    if not any(obj.name.startswith(s) for s in ["Point.", "Action."]):
        return False
    if not IsActionList(obj.parent):
        return False
    return True


def GetActionListPoints(scene, al_object):
    ret = []
    for o in scene.objects:
        if IsActionPoint(o) and o.parent == al_object:
            ret.append(o)
    ret.sort(key=lambda o: o.zc_apoint.start_frame)
    return ret


def GetActionLists(scene, cs_object, actorid):
    ret = []
    for o in scene.objects:
        if IsActionList(o) and o.parent == cs_object and (actorid is None or o.zc_alist.actor_id == actorid):
            ret.append(o)

    points = GetActionListPoints(scene, o)
    ret.sort(key=lambda o: 1000000 if len(points) < 2 else points[0].zc_apoint.start_frame)
    return ret


def CreateActionPoint(context, al_object, select, pos, start_frame, action_id):
    point = CreateObject(context, "Point.001", None, select)
    point.parent = al_object
    point.empty_display_type = "ARROWS"
    point.location = pos
    point.rotation_mode = "XZY"
    point.zc_apoint.start_frame = start_frame
    point.zc_apoint.action_id = action_id
    return point


def CreateActorAction(context, actor_id, cs_object):
    al_object = CreateObject(context, "ActionList." + GetActorName(actor_id) + ".001", None, True)
    al_object.parent = cs_object
    al_object.zc_alist.actor_id = actor_id
    return al_object

import math
import bpy

from struct import pack, unpack
from bpy.types import Scene, Object, Bone, Context, EditBone, Operator
from ....utility import indent
from .constants import LISTS_DEF, NONLISTS_DEF, CAM_TYPE_LISTS, ACTION_LISTS


class OOTCutsceneMotionIOBase:
    def __init__(self, context):
        self.context = context
        self.scale = context.scene.ootBlenderScale

    def intBitsAsFloat(self, value: int):
        """From https://stackoverflow.com/questions/14431170/get-the-bits-of-a-float-in-python"""
        s = pack(">l", value)
        return unpack(">f", s)[0]

    def parseParams(self, cmdDef: dict, line: str):
        assert line.startswith(cmdDef["name"] + "(")
        assert line.endswith("),")

        cmdArgs = [cmdArg.strip() for cmdArg in line[len(cmdDef["name"]) + 1 : -2].split(",") if cmdArg.strip()]

        if len(cmdArgs) != len(cmdDef["params"]):
            raise RuntimeError(
                f"Command: `{cmdDef['name']}` requires {len(cmdDef['params'])} parameters "
                + f"but only {len(cmdArgs)} found in file"
            )

        ret = {"name": cmdDef["name"]}

        for cmdArg, paramList in zip(cmdArgs, cmdDef["params"]):
            if paramList["type"] in ("int", "hex"):
                try:
                    value = int(cmdArg, base=0)
                except ValueError:
                    raise RuntimeError("Invalid numeric value for " + paramList["name"] + " in " + line)

                width = paramList.get("width", 16)

                if width == 16 and value >= 0xFFFF8000 and value <= 0xFFFFFFFF:
                    value -= 0x100000000
                elif width == 8 and value >= 0xFFFFFF80 and value <= 0xFFFFFFFF:
                    value -= 0x100000000
                elif value >= (1 << width) or value < -(1 << (width - 1)):
                    raise RuntimeError("Value out of range for " + paramList["name"] + " in " + line)
                elif value >= (1 << (width - 1)):
                    value -= 1 << width
            elif paramList["type"] == "continueFlag":
                if cmdArg in ["0", "CS_CMD_CONTINUE"]:
                    value = True
                elif cmdArg in ["-1", "CS_CMD_STOP"]:
                    value = False
                else:
                    raise RuntimeError("Invalid continueFlag value for " + paramList["name"] + " in " + line)
            elif paramList["type"] == "int_or_float":
                if cmdArg.startswith("0x"):
                    value = self.intBitsAsFloat(int(cmdArg, base=16))
                elif cmdArg.endswith("f"):
                    value = float(cmdArg[:-1])

                    if not math.isfinite(value):
                        raise RuntimeError("Invalid float value for " + paramList["name"] + " in " + line)
                else:
                    raise RuntimeError("Invalid int_or_float value for " + paramList["name"] + " in " + line)
            elif paramList["type"] == "string":
                value = cmdArg
            else:
                raise RuntimeError("Invalid command parameter type: " + paramList["type"])

            if ("min" in paramList and value < paramList["min"]) or ("max" in paramList and value >= paramList["max"]):
                raise RuntimeError("Value out of range for " + paramList["name"] + " in " + line)

            ret[paramList["name"]] = value

        return ret

    def parseCommand(self, line: str, curListName: str):
        line = line.strip()

        if not line.endswith("),"):
            raise RuntimeError(f"Syntax error: `{line}`")

        if curListName is not None:
            curCmdDef = next((cmdDef for cmdDef in LISTS_DEF if cmdDef["name"] == curListName), None)

            if curCmdDef is None:
                raise RuntimeError("Invalid current list: " + curListName)

            for listEntryCmdDef in curCmdDef["commands"]:
                if line.startswith(listEntryCmdDef["name"] + "("):
                    if not line.startswith("\t\t") and not line.startswith(indent * 2):
                        print(f"Warning, invalid indentation in {curListName}: `{line}`")

                    return self.parseParams(listEntryCmdDef, line), "same"

        if not (line.startswith("\t") and len(line) > 1 and line[1] != "\t") and not (
            line.startswith(indent) and len(line) > 4 and line[4] != " "
        ):
            # this warning seems glitched for some reasons with the changes
            print(f"Warning, invalid indentation: `{line}`")

        curCmdDef = next((cmdDef for cmdDef in LISTS_DEF if line.startswith(cmdDef["name"] + "(")), None)

        if curCmdDef is not None:
            return self.parseParams(curCmdDef, line), curCmdDef["name"]

        curCmdDef = next((cmdDef for cmdDef in NONLISTS_DEF if line.startswith(cmdDef["name"] + "(")), None)

        if curCmdDef is not None:
            return self.parseParams(curCmdDef, line), None

        raise RuntimeError(f"Invalid command: {line}")

    def getCutsceneArrayName(self, line: str):
        # list of the different words of the array name, looking for "CutsceneData csName[] = {"
        arrayNameElems = line.strip().split(" ")

        if (
            len(arrayNameElems) != 4
            or arrayNameElems[0] != "CutsceneData"
            or not arrayNameElems[1].endswith("[]")
            or arrayNameElems[2] != "="
            or arrayNameElems[3] != "{"
        ):
            return None

        return arrayNameElems[1][:-2]

    def onLineOutsideCS(self, line: str):
        pass

    def onCutsceneStart(self, csName: str):
        self.first_cs_cmd = True
        self.curlist = None
        self.in_cam_list = False
        self.in_action_list = False
        self.entrycount = 0

    def onNonListCmd(self, line: str, cmdDef):
        if cmdDef["name"] != "CS_BEGIN_CUTSCENE":
            self.entrycount += 1

    def onListStart(self, line: str, cmd):
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

    def onListCmd(self, line: str, cmdDef):
        if self.list_nentries is not None:
            self.list_entrycount += 1

        if self.in_cam_list:
            if self.cam_list_last:
                raise RuntimeError(f"More camera commands after last cmd! `{line}`")

            self.cam_list_last = not cmdDef["continueFlag"]

    def onListEnd(self):
        if self.list_nentries is not None and self.list_nentries != self.list_entrycount:
            raise RuntimeError(
                f"List `{self.curlist}` was supposed to have {self.list_nentries} entries "
                + f"but actually had {self.list_entrycount}!"
            )

        if self.in_cam_list and not self.cam_list_last:
            raise RuntimeError("Camera list terminated without stop marker!")

        self.in_cam_list = False
        self.in_action_list = False

    def onCutsceneEnd(self):
        if self.nentries != self.entrycount:
            raise RuntimeError(f"Cutscene header claimed {self.nentries} entries but only {self.entrycount} found!")

    def processInputFile(self, filename: str):
        state = "OutsideCS"

        with open(filename, "r") as infile:
            # Merge lines which were broken as long lines
            lines = []
            parenOpen = 0

            for line in infile:
                if parenOpen < 0 or parenOpen > 5:
                    raise RuntimeError(f"Parentheses parsing failed near line: {line}")
                elif parenOpen > 0:
                    lines[-1] += " " + line
                else:
                    lines.append(line)

                parenOpen += line.count("(") - line.count(")")

            if parenOpen != 0:
                raise RuntimeError("Unbalanced parentheses by end of file")

            for line in lines:
                if state == "OutsideCS":
                    csName = self.getCutsceneArrayName(line)

                    if csName is not None:
                        print(f"Found cutscene {csName}")
                        self.onCutsceneStart(csName)
                        state = "InsideCS"
                    else:
                        self.onLineOutsideCS(line)

                    continue

                curCmdDef, newCmdDef = self.parseCommand(line, self.curlist)

                if self.first_cs_cmd or curCmdDef["name"] == "CS_BEGIN_CUTSCENE":
                    if not self.first_cs_cmd or not curCmdDef["name"] == "CS_BEGIN_CUTSCENE":
                        raise RuntimeError("First command in cutscene must be only CS_BEGIN_CUTSCENE! " + line)

                    self.nentries = curCmdDef["totalEntries"]
                    self.first_cs_cmd = False

                if newCmdDef == "same":
                    self.onListCmd(line, curCmdDef)
                else:
                    if self.curlist is not None:
                        self.onListEnd()

                    self.curlist = newCmdDef

                    if curCmdDef["name"] == "CS_END":
                        self.onCutsceneEnd()
                        state = "OutsideCS"
                    elif newCmdDef is None:
                        self.onNonListCmd(line, curCmdDef)
                    else:
                        self.onListStart(line, curCmdDef)

        if state != "OutsideCS":
            raise RuntimeError("Unexpected EOF!")


def getEditBoneFromBone(shotObj: Object, bone: Bone) -> EditBone | Bone:
    for editBone in shotObj.data.edit_bones:
        if editBone.name == bone.name:
            return editBone
    else:
        print("Could not find corresponding bone")
        return bone


def metersToBlend(context: Context, value: float):
    return value * 56.0 / context.scene.ootBlenderScale


def createNewObject(context: Context, name: str, data, selectObject: bool) -> Object:
    newObj = bpy.data.objects.new(name=name, object_data=data)
    context.view_layer.active_layer_collection.collection.objects.link(newObj)

    if selectObject:
        newObj.select_set(True)
        context.view_layer.objects.active = newObj

    return newObj


def getCSObj(operator: Operator, context: Context):
    """Check if we are editing a cutscene."""
    csObj = context.view_layer.objects.active

    if csObj is None or csObj.type != "EMPTY":
        if operator is not None:
            operator.report({"WARNING"}, "Must have an empty object active (selected)")
        return None

    if not csObj.name.startswith("Cutscene."):
        if operator is not None:
            operator.report({"WARNING"}, 'Cutscene empty object must be named "Cutscene.<YourCutsceneName>"')
        return None

    return csObj


# action data
def isActorCueList(obj: Object):
    if obj is None or obj.type != "EMPTY":
        return False

    if not any(obj.name.startswith(s) for s in ["Path.", "ActionList."]):
        return False

    if obj.parent is None or obj.parent.type != "EMPTY" or not obj.parent.name.startswith("Cutscene."):
        return False

    return True


def isPreview(obj: Object):
    if obj is None or obj.type != "EMPTY":
        return False

    if not obj.name.startswith("Preview."):
        return False

    if obj.parent is None or obj.parent.type != "EMPTY" or not obj.parent.name.startswith("Cutscene."):
        return False

    return True


def getActorName(actor_id: int):
    return "Link" if actor_id < 0 else f"Actor{actor_id}"


def createOrInitPreview(context: Context, csObj: Object, actor_id: int, selectObject=False):
    for obj in bpy.data.objects:
        if isPreview(obj) and obj.parent == csObj and obj.zc_alist.actor_id == actor_id:
            previewObj = obj
            break
    else:
        previewObj = createNewObject(context, f"Preview.{getActorName(actor_id)}.001", None, selectObject)
        previewObj.parent = csObj

    actorHeight = 1.5

    if actor_id < 0:
        actorHeight = 1.7 if context.scene.zc_previewlinkage == "link_adult" else 1.3

    previewObj.empty_display_type = "SINGLE_ARROW"
    previewObj.empty_display_size = metersToBlend(context, actorHeight)
    previewObj.zc_alist.actor_id = actor_id


class PropsBone:
    def __init__(self, shotObj: Object, bone: Bone):
        editBone = getEditBoneFromBone(shotObj, bone) if shotObj.mode == "EDIT" else None
        self.name = bone.name
        self.head = editBone.head if editBone is not None else bone.head
        self.tail = editBone.tail if editBone is not None else bone.tail
        self.frames = editBone["frames"] if editBone is not None and "frames" in editBone else bone.frames
        self.fov = editBone["fov"] if editBone is not None and "fov" in editBone else bone.fov
        self.camroll = editBone["camroll"] if editBone is not None and "camroll" in editBone else bone.camroll


# camdata
def getShotPropBones(shotObj: Object):
    bones: list[PropsBone] = []

    for bone in shotObj.data.bones:
        if bone.parent is not None:
            print("Camera armature bones are not allowed to have parent bones")
            return None

        bones.append(PropsBone(shotObj, bone))

    bones.sort(key=lambda b: b.name)
    return bones


def getShotPropBonesChecked(shotObj: Object):
    propBones = getShotPropBones(shotObj)

    if propBones is None:
        raise RuntimeError("Error in bone properties")

    if len(propBones) < 4:
        raise RuntimeError(f"Only {len(propBones)} bones in `{shotObj.name}`")

    return propBones


def getShotObjects(scene: Scene, csObj: Object):
    shotObjects: list[Object] = [
        obj for obj in scene.objects if obj.type == "ARMATURE" and obj.parent is not None and obj.parent == csObj
    ]
    shotObjects.sort(key=lambda obj: obj.name)

    return shotObjects


def getFakeCamCmdsLength(shotObj: Object, useAT: bool):
    propBones = getShotPropBonesChecked(shotObj)
    base = max(2, sum(b.frames for b in propBones))
    # Seems to be the algorithm which was used in the canon tool: the at list
    # counts the extra point (same frames as the last real point), and the pos
    # list doesn't count the extra point but adds 1. Of course, neither of these
    # values is actually the number of frames the camera motion lasts for.
    return base + (propBones[-1].frames if useAT else 1)


def getFakeCSEndFrame(context: Context, csObj: Object):
    shotObjects = getShotObjects(context.scene, csObj)
    csEndFrame = -1

    for shotObj in shotObjects:
        endFrame = shotObj.data.start_frame + getFakeCamCmdsLength(shotObj, False) + 1
        csEndFrame = max(csEndFrame, endFrame)

    return csEndFrame


def initCutscene(context: Context, csObj: Object):
    # Add or move camera
    camObj = None
    hasNoCam = True

    for obj in bpy.data.objects:
        if obj.type == "CAMERA":
            hasNoCam = False

            if obj.parent is not None and obj.parent == csObj:
                camObj = obj
        break

    if hasNoCam:
        cam = bpy.data.cameras.new("Camera")
        camObj = createNewObject(context, "Camera", cam, False)
        print("Created new camera")

    if camObj is not None:
        camObj.parent = csObj
        camObj.data.display_size = metersToBlend(context, 0.25)
        camObj.data.passepartout_alpha = 0.95
        camObj.data.clip_start = metersToBlend(context, 1e-3)
        camObj.data.clip_end = metersToBlend(context, 200.0)

    # Preview actions
    for obj in bpy.data.objects:
        if isActorCueList(obj):
            createOrInitPreview(context, obj.parent, obj.zc_alist.actor_id, False)

    # Other setup
    context.scene.frame_start = 0
    context.scene.frame_end = max(getFakeCSEndFrame(context, csObj), context.scene.frame_end)
    context.scene.render.fps = 20
    context.scene.render.resolution_x = 320
    context.scene.render.resolution_y = 240


# action data leftovers
def isActorCuePoint(cuePointObj: Object):
    if (
        cuePointObj is None
        or cuePointObj.type != "EMPTY"
        or not cuePointObj.name in ["Point.", "Action."]
        or not isActorCueList(cuePointObj.parent)
    ):
        return False

    return True


def getActorCuePointObjects(scene: Scene, cueObj: Object):
    cuePoints: list[Object] = [obj for obj in scene.objects if isActorCuePoint(obj) and obj.parent == cueObj]
    cuePoints.sort(key=lambda o: o.zc_apoint.start_frame)
    return cuePoints


def getActorCueListObjects(scene: Scene, csObj: Object, actorid: int):
    cueObjects: list[Object] = []

    for obj in scene.objects:
        if isActorCueList(obj) and obj.parent == csObj and (actorid is None or obj.zc_alist.actor_id == actorid):
            cueObjects.append(obj)

    points = getActorCuePointObjects(scene, obj)

    cueObjects.sort(key=lambda o: 1000000 if len(points) < 2 else points[0].zc_apoint.start_frame)
    return cueObjects


def createActorCuePoint(context: Context, actorCueObj: Object, selectObj: bool, pos, startFrame: int, action_id: str):
    newCuePoint = createNewObject(context, "Point.001", None, selectObj)
    newCuePoint.parent = actorCueObj
    newCuePoint.empty_display_type = "ARROWS"
    newCuePoint.location = pos
    newCuePoint.rotation_mode = "XZY"
    newCuePoint.zc_apoint.start_frame = startFrame
    newCuePoint.zc_apoint.action_id = action_id

    return newCuePoint


def createActorCueList(context: Context, actor_id: int, csObj: Object):
    actorCueObj = createNewObject(context, f"ActionList.{getActorName(actor_id)}.001", None, True)
    actorCueObj.parent = csObj
    actorCueObj.zc_alist.actor_id = actor_id

    return actorCueObj

from dataclasses import dataclass, field
from typing import Optional
from mathutils import Matrix
from bpy.types import Object
from ....utility import CData, indent
from ...utility import getObjectList, get_game_props, is_game_oot, getEvalParams
from ...constants import oot_data
from ...room.properties import Z64_RoomHeaderProperty
from ..utility import Utility
from ..actor import Actor


@dataclass
class RoomInfos:
    """This class stores various room header informations"""

    ### General ###

    index: int
    roomShape: str

    ### Behavior ###

    roomBehavior: str
    playerIdleType: str
    showInvisActors: bool

    # OoT
    disableWarpSongs: bool

    # MM
    enable_pos_lights: bool
    enable_storm: bool

    ### Skybox And Time ###

    disableSky: bool
    disableSunMoon: bool
    hour: int
    minute: int
    timeSpeed: float
    echo: str

    ### Wind ###

    setWind: bool
    direction: tuple[int, int, int]
    strength: int

    @staticmethod
    def new(props: Optional[Z64_RoomHeaderProperty]):
        disableWarpSongs = False
        enable_pos_lights = False
        enable_storm = False

        if is_game_oot():
            disableWarpSongs = props.disableWarpSongs
        else:
            enable_pos_lights = props.enable_pos_lights
            enable_storm = props.enable_storm

        return RoomInfos(
            props.roomIndex,
            props.roomShape,
            Utility.getPropValue(props, "roomBehaviour"),
            Utility.getPropValue(props, "linkIdleMode"),
            props.showInvisibleActors,
            disableWarpSongs,
            enable_pos_lights,
            enable_storm,
            props.disableSkybox,
            props.disableSunMoon,
            0xFF if props.leaveTimeUnchanged else props.timeHours,
            0xFF if props.leaveTimeUnchanged else props.timeMinutes,
            max(-128, min(127, round(props.timeSpeed * 0xA))),
            props.echo,
            props.setWind,
            [d for d in props.windVector] if props.setWind else None,
            props.windStrength if props.setWind else None,
        )

    def getCmds(self):
        """Returns the echo settings, room behavior, skybox disables and time settings room commands"""
        showInvisActors = "true" if self.showInvisActors else "false"
        disableSkybox = "true" if self.disableSky else "false"
        disableSunMoon = "true" if self.disableSunMoon else "false"

        if is_game_oot():
            disableWarpSongs = "true" if self.disableWarpSongs else "false"
            roomBehaviorArgs = f"{self.roomBehavior}, {self.playerIdleType}, {showInvisActors}, {disableWarpSongs}"
        else:
            enable_pos_lights = "true" if self.enable_pos_lights else "false"
            enable_storm = "true" if self.enable_storm else "false"
            roomBehaviorArgs = (
                f"{self.roomBehavior}, {self.playerIdleType}, {showInvisActors}, 0, {enable_pos_lights}, {enable_storm}"
            )

        cmdList = [
            f"SCENE_CMD_ECHO_SETTINGS({self.echo})",
            f"SCENE_CMD_ROOM_BEHAVIOR({roomBehaviorArgs})",
            f"SCENE_CMD_SKYBOX_DISABLES({disableSkybox}, {disableSunMoon})",
            f"SCENE_CMD_TIME_SETTINGS({self.hour}, {self.minute}, {self.timeSpeed})",
        ]

        if self.setWind:
            cmdList.append(f"SCENE_CMD_WIND_SETTINGS({', '.join(f'{dir}' for dir in self.direction)}, {self.strength})")

        return indent + f",\n{indent}".join(cmdList) + ",\n"


@dataclass
class RoomObjects:
    """This class defines an OoT object array"""

    name: str
    objectList: list[str]

    @staticmethod
    def new(name: str, props: Optional[Z64_RoomHeaderProperty]):
        objectList: list[str] = []
        for objProp in props.objectList:
            if objProp.objectKey == "Custom":
                objectList.append(objProp.objectIDCustom)
            else:
                objectList.append(oot_data.objectData.objects_by_key[objProp.objectKey].id)
        return RoomObjects(name, objectList)

    def getDefineName(self):
        """Returns the name of the define for the total of entries in the object list"""

        return f"LENGTH_{self.name.upper()}"

    def getCmd(self):
        """Returns the object list room command"""

        return indent + f"SCENE_CMD_OBJECT_LIST({self.getDefineName()}, {self.name}),\n"

    def getC(self):
        """Returns the array with the objects the room uses"""

        objectList = CData()

        listName = f"s16 {self.name}"

        # .h
        objectList.header = f"extern {listName}[];\n"

        # .c
        objectList.source = (
            (f"{listName}[{self.getDefineName()}]" + " = {\n")
            + ",\n".join(indent + objectID for objectID in self.objectList)
            + ",\n};\n\n"
        )

        return objectList


@dataclass
class RoomActors:
    """This class defines an OoT actor array"""

    name: str
    actorList: list[Actor]

    @staticmethod
    def new(
        name: str,
        sceneObj: Optional[Object],
        roomObj: Optional[Object],
        transform: Matrix,
        headerIndex: int,
        room_index: int,
    ):
        actorList: list[Actor] = []
        actorObjList = getObjectList(sceneObj.children, "EMPTY", "Actor", parentObj=roomObj, room_index=room_index)
        for obj in actorObjList:
            actorProp = get_game_props(obj, "actor")
            if not Utility.isCurrentHeaderValid(actorProp.headerSettings, headerIndex):
                continue

            # The Actor list is filled with ``("None", f"{i} (Deleted from the XML)", "None")`` for
            # the total number of actors defined in the XML. If the user deletes one, this will prevent
            # any data loss as Blender saves the index of the element in the Actor list used for the EnumProperty
            # and not the identifier as defined by the first element of the tuple. Therefore, we need to check if
            # the current Actor has the ID `None` to avoid export issues.
            if actorProp.actorID != "None":
                pos, rot, _, _ = Utility.getConvertedTransform(transform, sceneObj, obj, True)
                actor = Actor()

                if actorProp.actorID == "Custom":
                    actor.id = actorProp.actorIDCustom
                else:
                    actor.id = actorProp.actorID

                if is_game_oot():
                    if actorProp.rotOverride:
                        actor.rot = ", ".join([actorProp.rotOverrideX, actorProp.rotOverrideY, actorProp.rotOverrideZ])
                    else:
                        actor.rot = ", ".join(f"DEG_TO_BINANG({(r * (180 / 0x8000)):.3f})" for r in rot)
                else:
                    if actorProp.rotOverride:
                        actor_flags = [0x4000, 0x8000, 0x2000]
                        actor_flag_masks = []
                        spawn_flags = [
                            f"0x{int(getEvalParams(actorProp.rotOverrideX), base=0):02X}",
                            f"0x{int(getEvalParams(actorProp.rotOverrideY), base=0):02X}",
                            f"0x{int(getEvalParams(actorProp.rotOverrideZ), base=0):02X}",
                        ]

                        for i, rot_flag in enumerate(spawn_flags):
                            if int(rot_flag, base=0) > 0:
                                actor_flag_masks.append(actor_flags[i])

                        if len(actor_flag_masks) > 0:
                            mask = 0
                            for val in actor_flag_masks:
                                mask |= val
                            actor.id = f"{actor.id} | 0x{mask:04X}"
                    else:
                        spawn_flags = ["0x00"] * 3

                    spawn_rot = [f"SPAWN_ROT_FLAGS(DEG_TO_BINANG({(r * (180 / 0x8000)):.3f})" for r in rot]
                    actor.rot = ", ".join(f"{rot}, {flag})" for rot, flag in zip(spawn_rot, spawn_flags))

                actor.name = (
                    oot_data.actorData.actorsByID[actorProp.actorID].name.replace(
                        f" - {actorProp.actorID.removeprefix('ACTOR_')}", ""
                    )
                    if actorProp.actorID != "Custom"
                    else "Custom Actor"
                )

                actor.pos = pos
                actor.params = actorProp.actorParam
                actorList.append(actor)
        return RoomActors(name, actorList)

    def getDefineName(self):
        """Returns the name of the define for the total of entries in the actor list"""

        return f"LENGTH_{self.name.upper()}"

    def getCmd(self):
        """Returns the actor list room command"""

        return indent + f"SCENE_CMD_ACTOR_LIST({self.getDefineName()}, {self.name}),\n"

    def getC(self):
        """Returns the array with the actors the room uses"""

        actorList = CData()
        listName = f"ActorEntry {self.name}"

        # .h
        actorList.header = f"extern {listName}[];\n"

        # .c
        actorList.source = (
            (f"{listName}[{self.getDefineName()}]" + " = {\n")
            + "\n".join(actor.getActorEntry() for actor in self.actorList)
            + "};\n\n"
        )

        return actorList


@dataclass
class RoomHeader:
    """This class defines a room header"""

    name: str
    infos: Optional[RoomInfos]
    objects: Optional[RoomObjects]
    actors: Optional[RoomActors]

    @staticmethod
    def new(
        name: str,
        props: Optional[Z64_RoomHeaderProperty],
        sceneObj: Optional[Object],
        roomObj: Optional[Object],
        transform: Matrix,
        headerIndex: int,
    ):
        return RoomHeader(
            name,
            RoomInfos.new(props),
            RoomObjects.new(f"{name}_objectList", props),
            RoomActors.new(f"{name}_actorList", sceneObj, roomObj, transform, headerIndex, props.roomIndex),
        )

    def getHeaderDefines(self):
        """Returns a string containing defines for actor and object lists lengths"""

        headerDefines = ""

        if len(self.objects.objectList) > 0:
            defineName = self.objects.getDefineName()
            headerDefines += f"#define {defineName} {len(self.objects.objectList)}\n"

        if len(self.actors.actorList) > 0:
            defineName = self.actors.getDefineName()
            headerDefines += f"#define {defineName} {len(self.actors.actorList)}\n"

        return headerDefines


@dataclass
class RoomAlternateHeader:
    """This class stores alternate header data"""

    name: str

    childNight: Optional[RoomHeader] = field(init=False, default=None)
    adultDay: Optional[RoomHeader] = field(init=False, default=None)
    adultNight: Optional[RoomHeader] = field(init=False, default=None)
    cutscenes: list[RoomHeader] = field(init=False, default_factory=list)

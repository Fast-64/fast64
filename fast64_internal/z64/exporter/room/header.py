import bpy

from dataclasses import dataclass, field
from typing import Optional
from mathutils import Matrix
from bpy.types import Object
from ....utility import PluginError, CData, indent
from ....game_data import game_data
from ...utility import getObjectList, is_oot_features, getEvalParams
from ...constants import halfday_bits_all_dawns, halfday_bits_all_nights, enum_to_halfday_bits
from ...room.properties import Z64_RoomHeaderProperty
from ...actor.properties import Z64_ActorProperty
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

        if game_data.z64.is_oot():
            disableWarpSongs = props.disableWarpSongs

        if not is_oot_features():
            enable_pos_lights = props.enable_pos_lights
            enable_storm = props.enable_storm

        return RoomInfos(
            props.roomIndex,
            props.roomShape,
            Utility.getPropValue(props, "roomBehaviour", "roomBehaviourCustom"),
            Utility.getPropValue(props, "linkIdleMode", "linkIdleModeCustom"),
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
        disableWarpSongs = "true" if self.disableWarpSongs else "false"

        if is_oot_features():
            roomBehaviorArgs = f"{self.roomBehavior}, {self.playerIdleType}, {showInvisActors}, {disableWarpSongs}"
        else:
            enable_pos_lights = "true" if self.enable_pos_lights else "false"
            enable_storm = "true" if self.enable_storm else "false"
            roomBehaviorArgs = f"{self.roomBehavior}, {self.playerIdleType}, {showInvisActors}, {disableWarpSongs}, {enable_pos_lights}, {enable_storm}"

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
                objectList.append(game_data.z64.objects.objects_by_key[objProp.objectKey].id)
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
    def get_rotation_values(actorProp: Z64_ActorProperty, blender_rot_values: list[int]):
        # Figure out which rotation to export, Blender's or the override
        custom = "_custom" if actorProp.actor_id == "Custom" else ""
        rot_values = [getattr(actorProp, f"rot_{rot}{custom}") for rot in ["x", "y", "z"]]
        export_rot_values = [f"DEG_TO_BINANG({(rot * (180 / 0x8000)):.3f})" for rot in blender_rot_values]

        if actorProp.actor_id == "Custom":
            export_rot_values = rot_values if actorProp.rot_override else export_rot_values
        else:
            for i, rot in enumerate(["X", "Y", "Z"]):
                if actorProp.is_rotation_used(f"{rot}Rot"):
                    export_rot_values[i] = rot_values[i]

        assert len(export_rot_values) == 3
        return export_rot_values

    @staticmethod
    def new(
        name: str,
        sceneObj: Optional[Object],
        roomObj: Optional[Object],
        transform: Matrix,
        headerIndex: int,
        room_index: int,
    ):
        game_data.z64.update(bpy.context, None)
        actorList: list[Actor] = []
        actorObjList = getObjectList(sceneObj.children, "EMPTY", "Actor", parentObj=roomObj, room_index=room_index)
        for obj in actorObjList:
            actorProp: Z64_ActorProperty = obj.ootActorProperty
            if not Utility.isCurrentHeaderValid(actorProp.headerSettings, headerIndex):
                continue

            actor_id: str = actorProp.actor_id

            # The Actor list is filled with ``("None", f"{i} (Deleted from the XML)", "None")`` for
            # the total number of actors defined in the XML. If the user deletes one, this will prevent
            # any data loss as Blender saves the index of the element in the Actor list used for the EnumProperty
            # and not the identifier as defined by the first element of the tuple. Therefore, we need to check if
            # the current Actor has the ID `None` to avoid export issues.
            if actorProp.actor_id != "None":
                pos, rot, _, _ = Utility.getConvertedTransform(transform, sceneObj, obj, True)
                actor = Actor()

                if actorProp.actor_id == "Custom":
                    actor.id = actorProp.actor_id_custom
                else:
                    actor.id = actorProp.actor_id

                rotation = RoomActors.get_rotation_values(actorProp, rot)

                if is_oot_features():
                    actor.rot = ", ".join(rotation)
                else:
                    halfday_bits = 0

                    if actorProp.halfday_all:
                        halfday_bits |= halfday_bits_all_dawns | halfday_bits_all_nights
                    else:
                        if actorProp.halfday_all_dawns:
                            halfday_bits |= halfday_bits_all_dawns

                        if actorProp.halfday_all_nights:
                            halfday_bits |= halfday_bits_all_nights

                    # if the value is 0 it means it's not all nor all dawns nor all nights
                    if halfday_bits == 0:
                        for item in actorProp.halfday_bits:
                            custom_value = 0

                            try:
                                if item.value == "Custom":
                                    custom_value = int(getEvalParams(item.value_custom), base=0)
                            except:
                                raise PluginError(
                                    f"ERROR: custom spawn schedule values don't support non-evaluable characters! ({repr(obj.name)})"
                                )

                            halfday_bits |= enum_to_halfday_bits.get(item.value, custom_value)

                    # rot.x stores a part of the halfday bits value
                    # rot.y stores a cutscene index
                    # rot.z stores the other part of the halfday bits
                    cs_index = actorProp.actor_cs_index & 0x7F
                    spawn_flags = [
                        f"0x{(halfday_bits >> 7) & 0x07:02X}",
                        "CS_ID_GLOBAL_END" if cs_index == 0x7F else cs_index,
                        f"0x{halfday_bits & 0x7F:02X}",
                    ]
                    spawn_rot = [f"SPAWN_ROT_FLAGS({r}" for r in rotation]
                    actor.rot = ", ".join(f"{rot}, {flag})" for rot, flag in zip(spawn_rot, spawn_flags))

                actor.name = (
                    game_data.z64.actors.actorsByID[actor_id].name.replace(f" - {actor_id.removeprefix('ACTOR_')}", "")
                    if actor_id != "Custom"
                    else "Custom Actor"
                )

                actor.pos = pos

                # force custom params for MM (temp solution until the xml is documented properly)
                if game_data.z64.is_oot() and actorProp.actor_id != "Custom":
                    actor.params = actorProp.params
                else:
                    actor.params = actorProp.params_custom

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

from dataclasses import dataclass
from mathutils import Matrix
from bpy.types import Object
from ....utility import PluginError, CData, exportColor, ootGetBaseOrCustomLight, indent
from ...utility import is_oot_features, getObjectList, getEvalParams, get_game_prop_name, is_game_oot
from ...scene.properties import (
    Z64_SceneHeaderProperty,
    Z64_LightProperty,
    Z64_MapDataChestProperty,
    Z64_MapDataRoomProperty,
)
from ..utility import Utility


@dataclass
class EnvLightSettings:
    """This class defines the information of one environment light setting"""

    envLightMode: str
    ambientColor: tuple[int, int, int]
    light1Color: tuple[int, int, int]
    light1Dir: tuple[int, int, int]
    light2Color: tuple[int, int, int]
    light2Dir: tuple[int, int, int]
    fogColor: tuple[int, int, int]
    fogNear: int
    zFar: int
    blendRate: int

    def getBlendFogNear(self):
        """Returns the packed blend rate and fog near values"""

        return f"(({self.blendRate} << 10) | {self.fogNear})"

    def getColorValues(self, vector: tuple[int, int, int]):
        """Returns and formats color values"""

        return ", ".join(f"{v:5}" for v in vector)

    def getDirectionValues(self, vector: tuple[int, int, int]):
        """Returns and formats direction values"""

        return ", ".join(f"{v - 0x100 if v > 0x7F else v:5}" for v in vector)

    def getEntryC(self, index: int):
        """Returns an environment light entry"""

        isLightingCustom = self.envLightMode == "Custom"

        vectors = [
            (self.ambientColor, "Ambient Color", self.getColorValues),
            (self.light1Dir, "Diffuse0 Direction", self.getDirectionValues),
            (self.light1Color, "Diffuse0 Color", self.getColorValues),
            (self.light2Dir, "Diffuse1 Direction", self.getDirectionValues),
            (self.light2Color, "Diffuse1 Color", self.getColorValues),
            (self.fogColor, "Fog Color", self.getColorValues),
        ]

        fogData = [
            (self.getBlendFogNear(), "Blend Rate & Fog Near"),
            (f"{self.zFar}", "Fog Far"),
        ]

        lightDescs = ["Dawn", "Day", "Dusk", "Night"]

        if not isLightingCustom and self.envLightMode == "LIGHT_MODE_TIME":
            # TODO: Improve the lighting system.
            # Currently Fast64 assumes there's only 4 possible settings for "Time of Day" lighting.
            # This is not accurate and more complicated,
            # for now we are doing ``index % 4`` to avoid having an OoB read in the list
            # but this will need to be changed the day the lighting system is updated.
            lightDesc = f"// {lightDescs[index % 4]} Lighting\n"
        else:
            isIndoor = not isLightingCustom and self.envLightMode == "LIGHT_MODE_SETTINGS"
            lightDesc = f"// {'Indoor' if isIndoor else 'Custom'} No. {index + 1} Lighting\n"

        lightData = (
            (indent + lightDesc)
            + (indent + "{\n")
            + "".join(
                indent * 2 + f"{'{ ' + vecToC(vector) + ' },':26} // {desc}\n" for (vector, desc, vecToC) in vectors
            )
            + "".join(indent * 2 + f"{fogValue + ',':26} // {fogDesc}\n" for fogValue, fogDesc in fogData)
            + (indent + "},\n")
        )

        return lightData


@dataclass
class SceneLighting:
    """This class hosts lighting data"""

    name: str
    envLightMode: str
    settings: list[EnvLightSettings]

    @staticmethod
    def new(name: str, props: Z64_SceneHeaderProperty):
        envLightMode = Utility.getPropValue(props, "skyboxLighting")
        lightList: list[Z64_LightProperty] = []
        settings: list[EnvLightSettings] = []

        if envLightMode == "LIGHT_MODE_TIME":
            todLights = props.timeOfDayLights
            lightList = [todLights.dawn, todLights.day, todLights.dusk, todLights.night]
        else:
            lightList = props.lightList

        for lightProp in lightList:
            light1 = ootGetBaseOrCustomLight(lightProp, 0, True, True)
            light2 = ootGetBaseOrCustomLight(lightProp, 1, True, True)
            settings.append(
                EnvLightSettings(
                    envLightMode,
                    exportColor(lightProp.ambient),
                    light1[0],
                    light1[1],
                    light2[0],
                    light2[1],
                    exportColor(lightProp.fogColor),
                    lightProp.fogNear,
                    lightProp.z_far,
                    lightProp.transitionSpeed,
                )
            )
        return SceneLighting(name, envLightMode, settings)

    def getCmd(self):
        """Returns the env light settings scene command"""

        return (
            indent + "SCENE_CMD_ENV_LIGHT_SETTINGS("
        ) + f"{len(self.settings)}, {self.name if len(self.settings) > 0 else 'NULL'}),\n"

    def getC(self):
        """Returns a ``CData`` containing the C data of env. light settings"""

        lightSettingsC = CData()
        lightName = f"EnvLightSettings {self.name}[{len(self.settings)}]"

        # .h
        lightSettingsC.header = f"extern {lightName};\n"

        # .c
        lightSettingsC.source = (
            (lightName + " = {\n") + "".join(light.getEntryC(i) for i, light in enumerate(self.settings)) + "};\n\n"
        )

        return lightSettingsC


@dataclass
class SceneInfos:
    """This class stores various scene header informations"""

    ### General ###

    keepObjectID: str
    naviHintType: str
    drawConfig: str
    appendNullEntrance: bool
    useDummyRoomList: bool

    ### Skybox And Sound ###

    # Skybox
    skyboxID: str
    skyboxConfig: str
    skybox_texture_id: str  # MM

    # Sound
    sequenceID: str
    ambienceID: str
    specID: str

    ### Camera And World Map (OoT) ###

    # World Map
    worldMapLocation: str

    # Camera
    sceneCamType: str

    ### REGION VISITED (MM) ###

    set_region_visited: bool

    @staticmethod
    def new(props: Z64_SceneHeaderProperty, sceneObj: Object):
        if is_oot_features():
            skybox_texture_id = ""
        else:
            skybox_texture_id = Utility.getPropValue(props, "skybox_texture_id")

        return SceneInfos(
            Utility.getPropValue(props, get_game_prop_name("global_obj"), "globalObjectCustom"),
            Utility.getPropValue(props, "naviCup") if is_game_oot() else "NAVI_QUEST_HINTS_NONE",
            Utility.getPropValue(props.sceneTableEntry, get_game_prop_name("draw_config"), "drawConfigCustom"),
            props.appendNullEntrance,
            sceneObj.fast64.oot.scene.write_dummy_room_list,
            Utility.getPropValue(props, get_game_prop_name("skybox_id"), "skyboxIDCustom"),
            Utility.getPropValue(props, get_game_prop_name("skybox_config"), "skyboxCloudinessCustom"),
            skybox_texture_id,
            Utility.getPropValue(props, get_game_prop_name("seq_id"), "musicSeqCustom"),
            Utility.getPropValue(props, get_game_prop_name("ambience_id"), "nightSeqCustom"),
            Utility.getPropValue(props, "audioSessionPreset"),
            Utility.getPropValue(props, "mapLocation") if is_oot_features() else "",
            Utility.getPropValue(props, "cameraMode") if is_oot_features() else "",
            props.set_region_visited if not is_oot_features() else False,
        )

    def getCmds(self, lights: SceneLighting):
        """Returns the sound settings, misc settings, special files and skybox settings scene commands"""
        commands = [
            f"SCENE_CMD_SOUND_SETTINGS({self.specID}, {self.ambienceID}, {self.sequenceID})",
            f"SCENE_CMD_SPECIAL_FILES({self.naviHintType}, {self.keepObjectID})",
        ]

        if is_oot_features():
            commands.extend(
                [
                    f"SCENE_CMD_MISC_SETTINGS({self.sceneCamType}, {self.worldMapLocation})",
                    f"SCENE_CMD_SKYBOX_SETTINGS({self.skyboxID}, {self.skyboxConfig}, {lights.envLightMode})",
                ]
            )
        else:
            commands.append(
                f"SCENE_CMD_SKYBOX_SETTINGS({self.skybox_texture_id}, {self.skyboxID}, {self.skyboxConfig}, {lights.envLightMode})"
            )

            if self.set_region_visited:
                commands.append("SCENE_CMD_SET_REGION_VISITED()")

        return indent + f",\n{indent}".join(commands) + ",\n"


@dataclass
class SceneExits(Utility):
    """This class hosts exit data"""

    name: str
    exitList: list[tuple[int, str]]

    @staticmethod
    def new(name: str, props: Z64_SceneHeaderProperty):
        # TODO: proper implementation of exits

        exitList: list[tuple[int, str]] = []
        for i, exitProp in enumerate(props.exitList):
            if exitProp.exitIndex != "Custom":
                raise PluginError("ERROR: Exits are unfinished, please use 'Custom'.")
            exitList.append((i, exitProp.exitIndexCustom))
        return SceneExits(name, exitList)

    def getCmd(self):
        """Returns the exit list scene command"""

        return indent + f"SCENE_CMD_EXIT_LIST({self.name}),\n"

    def getC(self):
        """Returns a ``CData`` containing the C data of the exit array"""

        exitListC = CData()
        listName = f"u16 {self.name}[{len(self.exitList)}]"

        # .h
        exitListC.header = f"extern {listName};\n"

        # .c
        exitListC.source = (
            (listName + " = {\n")
            # @TODO: use the enum name instead of the raw index
            + "\n".join(indent + f"{value}," for (_, value) in self.exitList)
            + "\n};\n\n"
        )

        return exitListC


class MapDataChest:
    def __init__(self, chest_prop: Z64_MapDataChestProperty, scene_obj: Object, transform: Matrix):
        if chest_prop.chest_obj is None:
            raise PluginError("ERROR: The chest empty object is unset.")

        pos, _, _, _ = Utility.getConvertedTransform(transform, scene_obj, chest_prop.chest_obj, True)

        self.room_idx = self.get_room_index(chest_prop, scene_obj)
        self.chest_flag = int(getEvalParams(chest_prop.chest_obj.ootActorProperty.actorParam), base=0) & 0x1F
        self.pos = pos

    def get_room_index(self, chest_prop: Z64_MapDataChestProperty, scene_obj: Object) -> int:
        room_obj_list = getObjectList(scene_obj.children_recursive, "EMPTY", "Room")

        for room_obj in room_obj_list:
            if chest_prop.chest_obj in room_obj.children_recursive:
                return room_obj.ootRoomHeader.roomIndex

        raise PluginError(f"ERROR: Can't find the room associated with '{chest_prop.chest_obj.name}'")

    def to_c(self):
        return "{ " + f"{self.room_idx}, {self.chest_flag}, {self.pos[0]}, {self.pos[1]}, {self.pos[2]}" + " }"


class MapDataRoom:
    def __init__(self, room_prop: Z64_MapDataRoomProperty):
        self.map_id: str = room_prop.map_id
        self.center_x: int = room_prop.center_x
        self.floor_y: int = room_prop.floor_y
        self.center_z: int = room_prop.center_z
        self.flags: str = room_prop.flags

    def to_c(self):
        return "{ " + f"{self.map_id}, {self.center_x}, {self.floor_y}, {self.center_z}, {self.flags}" + " }"


@dataclass
class SceneMapData:
    """This class hosts exit data"""

    name: str
    map_scale: int
    room_list: list[MapDataRoom]
    chest_list: list[MapDataChest]

    @staticmethod
    def new(name: str, props: Z64_SceneHeaderProperty, scene_obj: Object, transform: Matrix):
        return SceneMapData(
            name,
            props.minimap_scale,
            [MapDataRoom(room_prop) for room_prop in props.minimap_room_list],
            [MapDataChest(chest_prop, scene_obj, transform) for chest_prop in props.minimap_chest_list],
        )

    def get_cmds(self):
        """Returns the sound settings, misc settings, special files and skybox settings scene commands"""
        commands = []

        if len(self.room_list) > 0:
            commands.append(f"SCENE_CMD_MAP_DATA(&{self.name})")

        if len(self.chest_list) > 0:
            commands.append(f"SCENE_CMD_MAP_DATA_CHESTS({len(self.chest_list)}, {self.name}Chest)")

        if len(commands) > 0:
            return indent + f",\n{indent}".join(commands) + ",\n"

        return ""

    def to_c(self):
        map_data_c = CData()
        scene_list_name = f"MapDataScene {self.name}"
        room_list_name = f"MapDataRoom {self.name}Room[{len(self.room_list)}]"
        chest_list_name = f"MapDataChest {self.name}Chest[{len(self.chest_list)}]"
        map_data_header = []
        map_data_source = ""

        if len(self.room_list) > 0:
            map_data_header.extend([f"extern {scene_list_name};\n", f"extern {room_list_name};\n"])
            map_data_source += (
                # MapDataRoom
                (room_list_name + " = {\n")
                + "\n".join(indent + f"{room.to_c()}," for room in self.room_list)
                + "\n};\n\n"
                # MapDataScene
                + (scene_list_name + " = {\n")
                + (indent + f"{self.name}Room, {self.map_scale}")
                + "\n};\n\n"
            )

        if len(self.chest_list) > 0:
            map_data_header.append(f"extern {chest_list_name};\n")
            map_data_source += (
                # MapDataChest
                (chest_list_name + " = {\n")
                + "\n".join(indent + f"{chest.to_c()}," for chest in self.chest_list)
                + "\n};\n\n"
            )

        # .h
        if len(map_data_header) > 0:
            map_data_c.header = "".join(map_data_header)

        # .c
        if len(map_data_source) > 0:
            map_data_c.source = map_data_source

        return map_data_c

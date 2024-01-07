from dataclasses import dataclass, field
from typing import Optional
from bpy.types import Object
from ....utility import PluginError, CData, exportColor, ootGetBaseOrCustomLight, indent
from ...scene.properties import OOTSceneHeaderProperty, OOTLightProperty
from ..base import Base


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
class SceneLighting(Base):
    """This class hosts lighting data"""

    props: OOTSceneHeaderProperty
    name: str

    envLightMode: Optional[str] = None
    settings: list[EnvLightSettings] = field(default_factory=list)

    def __post_init__(self):
        self.envLightMode = self.getPropValue(self.props, "skyboxLighting")
        lightList: list[OOTLightProperty] = []

        if self.envLightMode == "LIGHT_MODE_TIME":
            todLights = self.props.timeOfDayLights
            lightList = [todLights.dawn, todLights.day, todLights.dusk, todLights.night]
        else:
            lightList = self.props.lightList

        for lightProp in lightList:
            light1 = ootGetBaseOrCustomLight(lightProp, 0, True, True)
            light2 = ootGetBaseOrCustomLight(lightProp, 1, True, True)
            self.settings.append(
                EnvLightSettings(
                    self.envLightMode,
                    exportColor(lightProp.ambient),
                    light1[0],
                    light1[1],
                    light2[0],
                    light2[1],
                    exportColor(lightProp.fogColor),
                    lightProp.fogNear,
                    lightProp.fogFar,
                    lightProp.transitionSpeed,
                )
            )

    def getCmd(self):
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
class SceneInfos(Base):
    """This class stores various scene header informations"""

    props: OOTSceneHeaderProperty
    sceneObj: Object

    ### General ###

    keepObjectID: Optional[str] = None
    naviHintType: Optional[str] = None
    drawConfig: Optional[str] = None
    appendNullEntrance: Optional[bool] = None
    useDummyRoomList: Optional[bool] = None

    ### Skybox And Sound ###

    # Skybox
    skyboxID: Optional[str] = None
    skyboxConfig: Optional[str] = None

    # Sound
    sequenceID: Optional[str] = None
    ambienceID: Optional[str] = None
    specID: Optional[str] = None

    ### Camera And World Map ###

    # World Map
    worldMapLocation: Optional[str] = None

    # Camera
    sceneCamType: Optional[str] = None

    def __post_init__(self):
        self.keepObjectID = self.getPropValue(self.props, "globalObject")
        self.naviHintType = self.getPropValue(self.props, "naviCup")
        self.drawConfig = self.getPropValue(self.props.sceneTableEntry, "drawConfig")
        self.appendNullEntrance = self.props.appendNullEntrance
        self.useDummyRoomList = self.sceneObj.fast64.oot.scene.write_dummy_room_list
        self.skyboxID = self.getPropValue(self.props, "skyboxID")
        self.skyboxConfig = self.getPropValue(self.props, "skyboxCloudiness")
        self.sequenceID = self.getPropValue(self.props, "musicSeq")
        self.ambienceID = self.getPropValue(self.props, "nightSeq")
        self.specID = self.getPropValue(self.props, "audioSessionPreset")
        self.worldMapLocation = self.getPropValue(self.props, "mapLocation")
        self.sceneCamType = self.getPropValue(self.props, "cameraMode")

    def getCmds(self, lights: SceneLighting):
        return (
            indent
            + f",\n{indent}".join(
                [
                    f"SCENE_CMD_SOUND_SETTINGS({self.specID}, {self.ambienceID}, {self.sequenceID})",
                    f"SCENE_CMD_MISC_SETTINGS({self.sceneCamType}, {self.worldMapLocation})",
                    f"SCENE_CMD_SPECIAL_FILES({self.naviHintType}, {self.keepObjectID})",
                    f"SCENE_CMD_SKYBOX_SETTINGS({self.skyboxID}, {self.skyboxConfig}, {lights.envLightMode})",
                ]
            )
            + ",\n"
        )


@dataclass
class SceneExits(Base):
    """This class hosts exit data"""

    props: OOTSceneHeaderProperty
    name: str
    exitList: list[tuple[int, str]] = field(default_factory=list)

    def __post_init__(self):
        for i, exitProp in enumerate(self.props.exitList):
            if exitProp.exitIndex != "Custom":
                raise PluginError("ERROR: Exits are unfinished, please use 'Custom'.")
            self.exitList.append((i, exitProp.exitIndexCustom))

    def getCmd(self):
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

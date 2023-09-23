from dataclasses import dataclass, field
from math import radians
from mathutils import Quaternion, Matrix
from bpy.types import Object
from ...utility import indent
from ..oot_utility import ootConvertTranslation, ootConvertRotation
from ..actor.properties import OOTActorProperty


@dataclass
class Common:
    sceneObj: Object
    roomObj: Object
    transform: Matrix
    roomIndex: int
    sceneName: str
    altHeaderList: list[str] = field(default_factory=lambda: ["childNight", "adultDay", "adultNight"])

    def isCurrentHeaderValid(self, actorProp: OOTActorProperty, headerIndex: int):
        preset = actorProp.headerSettings.sceneSetupPreset

        if preset == "All Scene Setups" or (preset == "All Non-Cutscene Scene Setups" and headerIndex < 4):
            return True

        if preset == "Custom":
            if actorProp.headerSettings.childDayHeader and headerIndex == 0:
                return True
            if actorProp.headerSettings.childNightHeader and headerIndex == 1:
                return True
            if actorProp.headerSettings.adultDayHeader and headerIndex == 2:
                return True
            if actorProp.headerSettings.adultNightHeader and headerIndex == 3:
                return True

        return False

    def getPropValue(self, data, propName: str):
        """Returns ``data.propName`` or ``data.propNameCustom``"""

        value = getattr(data, propName)
        return value if value != "Custom" else getattr(data, f"{propName}Custom")

    def getConvertedTransformWithOrientation(self, transformMatrix, sceneObj, obj, orientation):
        relativeTransform = transformMatrix @ sceneObj.matrix_world.inverted() @ obj.matrix_world
        blenderTranslation, blenderRotation, scale = relativeTransform.decompose()
        rotation = blenderRotation @ orientation
        convertedTranslation = ootConvertTranslation(blenderTranslation)
        convertedRotation = ootConvertRotation(rotation)

        return convertedTranslation, convertedRotation, scale, rotation

    def getConvertedTransform(self, transformMatrix, sceneObj, obj, handleOrientation):
        # Hacky solution to handle Z-up to Y-up conversion
        # We cannot apply rotation to empty, as that modifies scale
        if handleOrientation:
            orientation = Quaternion((1, 0, 0), radians(90.0))
        else:
            orientation = Matrix.Identity(4)
        return self.getConvertedTransformWithOrientation(transformMatrix, sceneObj, obj, orientation)

    def getAltHeaderListCmd(self, altName):
        return indent + f"SCENE_CMD_ALTERNATE_HEADER_LIST({altName}),\n"

    def getEndCmd(self):
        return indent + "SCENE_CMD_END(),\n"


@dataclass
class Actor:
    name: str = None
    id: str = None
    pos: list[int] = field(default_factory=list)
    rot: str = None
    params: str = None

    def getActorEntry(self):
        """Returns a single actor entry"""
        posData = "{ " + ", ".join(f"{round(p)}" for p in self.pos) + " }"
        rotData = "{ " + self.rot + " }"

        actorInfos = [self.id, posData, rotData, self.params]
        infoDescs = ["Actor ID", "Position", "Rotation", "Parameters"]

        return (
            indent
            + (f"// {self.name}\n" + indent if self.name != "" else "")
            + "{\n"
            + ",\n".join((indent * 2) + f"/* {desc:10} */ {info}" for desc, info in zip(infoDescs, actorInfos))
            + ("\n" + indent + "},\n")
        )


@dataclass
class TransitionActor(Actor):
    dontTransition: bool = None
    roomFrom: int = None
    roomTo: int = None
    cameraFront: str = None
    cameraBack: str = None

    def getTransitionActorEntry(self):
        """Returns a single transition actor entry"""
        sides = [(self.roomFrom, self.cameraFront), (self.roomTo, self.cameraBack)]
        roomData = "{ " + ", ".join(f"{room}, {cam}" for room, cam in sides) + " }"
        posData = "{ " + ", ".join(f"{round(pos)}" for pos in self.pos) + " }"

        actorInfos = [roomData, self.id, posData, self.rot, self.params]
        infoDescs = ["Room & Cam Index (Front, Back)", "Actor ID", "Position", "Rotation Y", "Parameters"]

        return (
            (indent + f"// {self.name}\n" + indent if self.name != "" else "")
            + "{\n"
            + ",\n".join((indent * 2) + f"/* {desc:30} */ {info}" for desc, info in zip(infoDescs, actorInfos))
            + ("\n" + indent + "},\n")
        )


@dataclass
class EntranceActor(Actor):
    roomIndex: int = None
    spawnIndex: int = None

    def getSpawnEntry(self):
        """Returns a single spawn entry"""
        return indent + "{ " + f"{self.spawnIndex}, {self.roomIndex}" + " },\n"

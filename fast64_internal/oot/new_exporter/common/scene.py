from dataclasses import dataclass, field
from bpy.types import Object
from typing import TYPE_CHECKING
from ....utility import PluginError, exportColor, ootGetBaseOrCustomLight
from ...scene.properties import OOTSceneHeaderProperty, OOTLightProperty
from ...oot_constants import ootData
from ...oot_model_classes import OOTModel
from ..commands import SceneCommands
from ..scene_header import EnvLightSettings, Path, OOTSceneHeader, OOTSceneAlternateHeader
from ..actors import TransitionActor, EntranceActor
from .classes import altHeaderList
from .collision import CollisionCommon

if TYPE_CHECKING:
    from ..room import OOTRoom


@dataclass
class SceneCommon(CollisionCommon, SceneCommands):
    """This class hosts various data and functions related to a scene file"""

    name: str = None
    model: OOTModel = None
    headerIndex: int = None
    mainHeader: OOTSceneHeader = None
    altHeader: OOTSceneAlternateHeader = None
    roomList: list["OOTRoom"] = field(default_factory=list)

    def validateRoomIndices(self):
        """Checks if there are multiple rooms with the same room index"""

        for i, room in enumerate(self.roomList):
            if i != room.roomIndex:
                return False
        return True

    def validateScene(self):
        """Performs safety checks related to the scene data"""

        if not len(self.roomList) > 0:
            raise PluginError("ERROR: This scene does not have any rooms!")

        if not self.validateRoomIndices():
            raise PluginError("ERROR: Room indices do not have a consecutive list of indices.")

    def hasAlternateHeaders(self):
        """Checks if this scene is using alternate headers"""

        return self.altHeader is not None

    def getSceneHeaderFromIndex(self, headerIndex: int) -> OOTSceneHeader | None:
        """Returns the scene header based on the header index"""

        if headerIndex == 0:
            return self.mainHeader

        for i, header in enumerate(altHeaderList, 1):
            if headerIndex == i:
                return getattr(self.altHeader, header)

        for i, csHeader in enumerate(self.altHeader.cutscenes, 4):
            if headerIndex == i:
                return csHeader

        return None

    def getExitListFromProps(self, headerProp: OOTSceneHeaderProperty):
        """Returns the exit list from the current scene header"""

        exitList: list[tuple[int, str]] = []
        for i, exitProp in enumerate(headerProp.exitList):
            if exitProp.exitIndex != "Custom":
                raise PluginError("ERROR: Exits are unfinished, please use 'Custom'.")

            exitList.append((i, exitProp.exitIndexCustom))

        return exitList

    def getTransActorListFromProps(self):
        """Returns the transition actor list based on empty objects with the type 'Transition Actor'"""

        actorList: list[TransitionActor] = []
        actorObjList: list[Object] = [
            obj
            for obj in self.sceneObj.children_recursive
            if obj.type == "EMPTY" and obj.ootEmptyType == "Transition Actor"
        ]
        for obj in actorObjList:
            roomObj = self.getRoomObjectFromChild(obj)
            if roomObj is None:
                raise PluginError("ERROR: Room Object not found!")
            self.roomIndex = roomObj.ootRoomHeader.roomIndex

            transActorProp = obj.ootTransitionActorProperty

            if (
                self.isCurrentHeaderValid(transActorProp.actor.headerSettings, self.headerIndex)
                and transActorProp.actor.actorID != "None"
            ):
                pos, rot, _, _ = self.getConvertedTransform(self.transform, self.sceneObj, obj, True)
                transActor = TransitionActor()

                if transActorProp.dontTransition:
                    front = (255, self.getPropValue(transActorProp, "cameraTransitionBack"))
                    back = (self.roomIndex, self.getPropValue(transActorProp, "cameraTransitionFront"))
                else:
                    front = (self.roomIndex, self.getPropValue(transActorProp, "cameraTransitionFront"))
                    back = (transActorProp.roomIndex, self.getPropValue(transActorProp, "cameraTransitionBack"))

                if transActorProp.actor.actorID == "Custom":
                    transActor.id = transActorProp.actor.actorIDCustom
                else:
                    transActor.id = transActorProp.actor.actorID

                transActor.name = (
                    ootData.actorData.actorsByID[transActorProp.actor.actorID].name.replace(
                        f" - {transActorProp.actor.actorID.removeprefix('ACTOR_')}", ""
                    )
                    if transActorProp.actor.actorID != "Custom"
                    else "Custom Actor"
                )

                transActor.pos = pos
                transActor.rot = f"DEG_TO_BINANG({(rot[1] * (180 / 0x8000)):.3f})"  # TODO: Correct axis?
                transActor.params = transActorProp.actor.actorParam
                transActor.roomFrom, transActor.cameraFront = front
                transActor.roomTo, transActor.cameraBack = back
                actorList.append(transActor)
        return actorList

    def getEntranceActorListFromProps(self):
        """Returns the entrance actor list based on empty objects with the type 'Entrance'"""

        actorList: list[EntranceActor] = []
        actorObjList: list[Object] = [
            obj for obj in self.sceneObj.children_recursive if obj.type == "EMPTY" and obj.ootEmptyType == "Entrance"
        ]
        for obj in actorObjList:
            roomObj = self.getRoomObjectFromChild(obj)
            if roomObj is None:
                raise PluginError("ERROR: Room Object not found!")

            entranceProp = obj.ootEntranceProperty
            if (
                self.isCurrentHeaderValid(entranceProp.actor.headerSettings, self.headerIndex)
                and entranceProp.actor.actorID != "None"
            ):
                pos, rot, _, _ = self.getConvertedTransform(self.transform, self.sceneObj, obj, True)
                entranceActor = EntranceActor()

                entranceActor.name = (
                    ootData.actorData.actorsByID[entranceProp.actor.actorID].name.replace(
                        f" - {entranceProp.actor.actorID.removeprefix('ACTOR_')}", ""
                    )
                    if entranceProp.actor.actorID != "Custom"
                    else "Custom Actor"
                )

                entranceActor.id = "ACTOR_PLAYER" if not entranceProp.customActor else entranceProp.actor.actorIDCustom
                entranceActor.pos = pos
                entranceActor.rot = ", ".join(f"DEG_TO_BINANG({(r * (180 / 0x8000)):.3f})" for r in rot)
                entranceActor.params = entranceProp.actor.actorParam
                entranceActor.roomIndex = roomObj.ootRoomHeader.roomIndex
                entranceActor.spawnIndex = entranceProp.spawnIndex
                actorList.append(entranceActor)
        return actorList

    def getPathListFromProps(self, listNameBase: str):
        """Returns the pathway list from spline objects with the type 'Path'"""

        pathList: list[Path] = []
        pathObjList: list[Object] = [
            obj
            for obj in self.sceneObj.children_recursive
            if obj.type == "CURVE" and obj.ootSplineProperty.splineType == "Path"
        ]

        for i, obj in enumerate(pathObjList):
            isHeaderValid = self.isCurrentHeaderValid(obj.ootSplineProperty.headerSettings, self.headerIndex)
            if isHeaderValid and self.validateCurveData(obj):
                pathList.append(
                    Path(
                        f"{listNameBase}{i:02}", [self.transform @ point.co.xyz for point in obj.data.splines[0].points]
                    )
                )

        return pathList

    def getEnvLightSettingsListFromProps(self, headerProp: OOTSceneHeaderProperty, lightMode: str):
        """Returns the environment light settings list from the current scene header"""

        lightList: list[OOTLightProperty] = []
        lightSettings: list[EnvLightSettings] = []

        if lightMode == "LIGHT_MODE_TIME":
            todLights = headerProp.timeOfDayLights
            lightList = [todLights.dawn, todLights.day, todLights.dusk, todLights.night]
        else:
            lightList = headerProp.lightList

        for lightProp in lightList:
            light1 = ootGetBaseOrCustomLight(lightProp, 0, True, True)
            light2 = ootGetBaseOrCustomLight(lightProp, 1, True, True)
            lightSettings.append(
                EnvLightSettings(
                    lightMode,
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

        return lightSettings

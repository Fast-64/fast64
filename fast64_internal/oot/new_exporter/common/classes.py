from dataclasses import dataclass
from math import radians
from mathutils import Quaternion, Matrix
from bpy.types import Object
from ....utility import PluginError, indent
from ...oot_utility import ootConvertTranslation, ootConvertRotation
from ...actor.properties import OOTActorHeaderProperty


altHeaderList = ["childNight", "adultDay", "adultNight"]


@dataclass
class Common:
    """This class hosts common data used across different sub-systems of this exporter"""

    sceneObj: Object
    transform: Matrix
    roomIndex: int = None

    def getRoomObjectFromChild(self, childObj: Object) -> Object | None:
        """Returns the room empty object from one of its child"""

        # Note: temporary solution until PRs #243 & #255 are merged
        for obj in self.sceneObj.children_recursive:
            if obj.type == "EMPTY" and obj.ootEmptyType == "Room":
                for o in obj.children_recursive:
                    if o == childObj:
                        return obj
        return None

    def validateCurveData(self, curveObj: Object):
        """Performs safety checks related to curve objects"""

        curveData = curveObj.data
        if curveObj.type != "CURVE" or curveData.splines[0].type != "NURBS":
            # Curve was likely not intended to be exported
            return False

        if len(curveData.splines) != 1:
            # Curve was intended to be exported but has multiple disconnected segments
            raise PluginError(f"Exported curves should have only one single segment, found {len(curveData.splines)}")

        return True

    def roundPosition(self, position) -> tuple[int, int, int]:
        """Returns the rounded position values"""

        return (round(position[0]), round(position[1]), round(position[2]))

    def isCurrentHeaderValid(self, headerSettings: OOTActorHeaderProperty, headerIndex: int):
        """Checks if the an alternate header can be used"""

        preset = headerSettings.sceneSetupPreset

        if preset == "All Scene Setups" or (preset == "All Non-Cutscene Scene Setups" and headerIndex < 4):
            return True

        if preset == "Custom":
            for i, header in enumerate(["childDay"] + altHeaderList):
                if getattr(headerSettings, f"{header}Header") and i == headerIndex:
                    return True

            for csHeader in headerSettings.cutsceneHeaders:
                if csHeader.headerIndex == headerIndex:
                    return True

        return False

    def getPropValue(self, data, propName: str):
        """Returns a property's value based on if the value is 'Custom'"""

        value = getattr(data, propName)
        return value if value != "Custom" else getattr(data, f"{propName}Custom")

    def getConvertedTransformWithOrientation(
        self, transform: Matrix, sceneObj: Object, obj: Object, orientation: Quaternion | Matrix
    ):
        relativeTransform = transform @ sceneObj.matrix_world.inverted() @ obj.matrix_world
        blenderTranslation, blenderRotation, scale = relativeTransform.decompose()
        rotation = blenderRotation @ orientation
        convertedTranslation = ootConvertTranslation(blenderTranslation)
        convertedRotation = ootConvertRotation(rotation)

        return convertedTranslation, convertedRotation, scale, rotation

    def getConvertedTransform(self, transform: Matrix, sceneObj: Object, obj: Object, handleOrientation: bool):
        # Hacky solution to handle Z-up to Y-up conversion
        # We cannot apply rotation to empty, as that modifies scale
        if handleOrientation:
            orientation = Quaternion((1, 0, 0), radians(90.0))
        else:
            orientation = Matrix.Identity(4)
        return self.getConvertedTransformWithOrientation(transform, sceneObj, obj, orientation)

    def getAltHeaderListCmd(self, altName: str):
        """Returns the scene alternate header list command"""

        return indent + f"SCENE_CMD_ALTERNATE_HEADER_LIST({altName}),\n"

    def getEndCmd(self):
        """Returns the scene end command"""

        return indent + "SCENE_CMD_END(),\n"

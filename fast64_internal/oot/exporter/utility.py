from math import radians
from mathutils import Quaternion, Matrix
from bpy.types import Object
from ...utility import PluginError, indent
from ..oot_utility import ootConvertTranslation, ootConvertRotation
from ..actor.properties import OOTActorHeaderProperty


altHeaderList = ["childNight", "adultDay", "adultNight"]


class Utility:
    """This class hosts different functions used across different sub-systems of this exporter"""

    @staticmethod
    def validateCurveData(curveObj: Object):
        """Performs safety checks related to curve objects"""

        curveData = curveObj.data
        if curveObj.type != "CURVE" or curveData.splines[0].type != "NURBS":
            # Curve was likely not intended to be exported
            return False

        if len(curveData.splines) != 1:
            # Curve was intended to be exported but has multiple disconnected segments
            raise PluginError(f"Exported curves should have only one single segment, found {len(curveData.splines)}")

        return True

    @staticmethod
    def roundPosition(position) -> tuple[int, int, int]:
        """Returns the rounded position values"""

        return (round(position[0]), round(position[1]), round(position[2]))

    @staticmethod
    def isCurrentHeaderValid(headerSettings: OOTActorHeaderProperty, headerIndex: int):
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

    @staticmethod
    def getPropValue(data, propName: str):
        """Returns a property's value based on if the value is 'Custom'"""

        value = getattr(data, propName)
        return value if value != "Custom" else getattr(data, f"{propName}Custom")

    @staticmethod
    def getConvertedTransformWithOrientation(
        transform: Matrix, dataHolder: Object, obj: Object, orientation: Quaternion | Matrix
    ):
        relativeTransform = transform @ dataHolder.matrix_world.inverted() @ obj.matrix_world
        blenderTranslation, blenderRotation, scale = relativeTransform.decompose()
        rotation = blenderRotation @ orientation
        convertedTranslation = ootConvertTranslation(blenderTranslation)
        convertedRotation = ootConvertRotation(rotation)

        return convertedTranslation, convertedRotation, scale, rotation

    @staticmethod
    def getConvertedTransform(transform: Matrix, dataHolder: Object, obj: Object, handleOrientation: bool):
        # Hacky solution to handle Z-up to Y-up conversion
        # We cannot apply rotation to empty, as that modifies scale
        if handleOrientation:
            orientation = Quaternion((1, 0, 0), radians(90.0))
        else:
            orientation = Matrix.Identity(4)
        return Utility.getConvertedTransformWithOrientation(transform, dataHolder, obj, orientation)

    @staticmethod
    def getAltHeaderListCmd(altName: str):
        """Returns the scene alternate header list command"""

        return indent + f"SCENE_CMD_ALTERNATE_HEADER_LIST({altName}),\n"

    @staticmethod
    def getEndCmd():
        """Returns the scene end command"""

        return indent + "SCENE_CMD_END(),\n"


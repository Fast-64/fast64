import re
import bpy
import mathutils

from ...utility import PluginError, hexOrDecInt, removeComments, yUpToZUp
from ..actor.properties import OOTActorProperty, OOTActorHeaderProperty
from ..oot_utility import ootParseRotation
from .constants import headerNames, actorsWithRotAsParam


def checkBit(value: int, index: int) -> bool:
    return (1 & (value >> index)) == 1


def getBits(value: int, index: int, size: int) -> int:
    return ((1 << size) - 1) & (value >> index)


def unsetAllHeadersExceptSpecified(headerSettings: OOTActorHeaderProperty, headerIndex: int):
    headerSettings.sceneSetupPreset = "Custom"
    for i in range(len(headerNames)):
        setattr(headerSettings, headerNames[i], i == headerIndex)

    if headerIndex >= 4:
        headerSettings.cutsceneHeaders.add().headerIndex = headerIndex


def createEmptyWithTransform(positionValues: list[float], rotationValues: list[float]) -> bpy.types.Object:
    position = (
        yUpToZUp
        @ mathutils.Matrix.Scale(1 / bpy.context.scene.ootBlenderScale, 4)
        @ mathutils.Vector([hexOrDecInt(value) for value in positionValues])
    )
    rotation = yUpToZUp @ mathutils.Vector(ootParseRotation(rotationValues))

    obj = bpy.data.objects.new("Empty", None)
    bpy.context.scene.collection.objects.link(obj)
    obj.empty_display_type = "CUBE"
    obj.location = position
    obj.rotation_euler = rotation
    return obj


def getDisplayNameFromActorID(actorID: str):
    return " ".join([word.lower().capitalize() for word in actorID.split("_") if word != "ACTOR"])


def handleActorWithRotAsParam(actorProp: OOTActorProperty, actorID: str, rotation: list[int]):
    if actorID in actorsWithRotAsParam:
        actorProp.rotOverride = True
        actorProp.rotOverrideX = hex(rotation[0])
        actorProp.rotOverrideY = hex(rotation[1])
        actorProp.rotOverrideZ = hex(rotation[2])


def getDataMatch(
    sceneData: str, name: str, dataType: str | list[str], errorMessageID: str, isArray: bool = True
) -> str:
    arrayText = rf"\[[\s0-9A-Za-z_]*\]\s*" if isArray else ""

    if isinstance(dataType, list):
        dataTypeRegex = "(?:"
        for i in dataType:
            dataTypeRegex += f"(?:{re.escape(i)})|"
        dataTypeRegex = dataTypeRegex[:-1] + ")"
    else:
        dataTypeRegex = re.escape(dataType)
    regex = rf"{dataTypeRegex}\s*{re.escape(name)}\s*{arrayText}=\s*\{{(.*?)\}}\s*;"
    match = re.search(regex, sceneData, flags=re.DOTALL)

    if not match:
        raise PluginError(f"Could not find {errorMessageID} {name}.")

    # return the match with comments removed
    return removeComments(match.group(1))


def stripName(name: str):
    if "&" in name:
        name = name[name.index("&") + 1 :].strip()
    if name[0] == "(" and name[-1] == ")":
        name = name[1:-1].strip()
    return name


def createCurveFromPoints(points: list[tuple[float, float, float]], name: str):
    curve = bpy.data.curves.new(name=name, type="CURVE")
    curveObj = bpy.data.objects.new(name, curve)
    bpy.context.scene.collection.objects.link(curveObj)

    spline = curve.splines.new("NURBS")
    objLocation = None
    curveObj.show_name = True

    # new spline has 1 point by default
    spline.points.add(len(points) - 1)
    for i in range(len(points)):
        position = yUpToZUp @ mathutils.Vector([value / bpy.context.scene.ootBlenderScale for value in points[i]])

        # Set the origin to the first point so that we can display name next to it.
        if objLocation is None:
            objLocation = position
            curveObj.location = position
        spline.points[i].co = (position - objLocation)[:] + (1,)

    spline.resolution_u = 64
    spline.order_u = 2
    curve.dimensions = "3D"

    return curveObj

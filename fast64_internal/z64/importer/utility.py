import re
import bpy
import mathutils

from ...utility import PluginError, hexOrDecInt, removeComments, yUpToZUp
from ..actor.properties import Z64_ActorProperty, Z64_ActorHeaderProperty
from ..utility import ootParseRotation, is_game_oot, get_cs_index_start
from .constants import headerNames, actorsWithRotAsParam


def checkBit(value: int, index: int) -> bool:
    return (1 & (value >> index)) == 1


def getBits(value: int, index: int, size: int) -> int:
    return ((1 << size) - 1) & (value >> index)


def unsetAllHeadersExceptSpecified(headerSettings: Z64_ActorHeaderProperty, headerIndex: int):
    if is_game_oot():
        headerSettings.sceneSetupPreset = "Custom"

        for i in range(len(headerNames)):
            setattr(headerSettings, headerNames[i], i == headerIndex)
    else:
        headerSettings.include_in_all_setups = False
        headerSettings.childDayHeader = headerIndex == 0

    if headerIndex >= get_cs_index_start():
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


def handleActorWithRotAsParam(actorProp: Z64_ActorProperty, actorID: str, rotation: list[int]):
    if is_game_oot():
        if actorID in actorsWithRotAsParam:
            actorProp.rotOverride = True
    else:
        actorProp.rotOverride = rotation[0] != 0 or rotation[1] != 0 or rotation[2] != 0

    if actorProp.rotOverride:
        actorProp.rotOverrideX = f"0x{rotation[0]:04X}"
        actorProp.rotOverrideY = f"0x{rotation[1]:04X}"
        actorProp.rotOverrideZ = f"0x{rotation[2]:04X}"


def getDataMatch(
    sceneData: str,
    name: str,
    dataType: str | list[str],
    errorMessageID: str,
    isArray: bool = True,
    is_type_known: bool = True,
):
    arrayText = rf"\[[\s0-9A-Za-z_]*\]\s*" if isArray else ""
    dataTypeRegex = dataType

    if isinstance(dataType, list):
        dataTypeRegex = "(?:"
        for i in dataType:
            dataTypeRegex += f"(?:{re.escape(i)})|"
        dataTypeRegex = dataTypeRegex[:-1] + ")"
    elif is_type_known:
        dataTypeRegex = re.escape(dataType)
    regex = rf"{dataTypeRegex}\s*{re.escape(name)}\s*{arrayText}=\s*\{{(.*?)\}}\s*;"
    match = re.search(regex, sceneData, flags=re.DOTALL)

    if match is None:
        raise PluginError(f"Could not find {errorMessageID} {name}.")

    if is_type_known:
        # return the match with comments removed
        return removeComments(match.group(1))
    else:
        f = match.groups()
        # return the struct name and the match
        return removeComments(match.group(1)), removeComments(match.group(2))


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

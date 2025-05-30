import re
import bpy
import mathutils

from pathlib import Path

from ...utility import PluginError, hexOrDecInt, removeComments, yUpToZUp
from ..actor.properties import OOTActorProperty, OOTActorHeaderProperty
from ..oot_utility import ootParseRotation, get_include_data
from .constants import headerNames, actorsWithRotAsParam
from .classes import SharedSceneData


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
        if actorProp.actor_id != "Custom":
            actorProp.rot_x = hex(rotation[0])
            actorProp.rot_y = hex(rotation[1])
            actorProp.rot_z = hex(rotation[2])
        else:
            actorProp.rot_override = True
            actorProp.rot_x_custom = hex(rotation[0])
            actorProp.rot_y_custom = hex(rotation[1])
            actorProp.rot_z_custom = hex(rotation[2])


def getDataMatch(
    sceneData: str, name: str, dataType: str | list[str], errorMessageID: str, isArray: bool = True, strip: bool = False
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
    data_match = removeComments(match.group(1))

    if "#include" in data_match:
        data_match = removeComments(get_include_data(data_match))

    if strip:
        data_match = data_match.replace("\n", "").replace(" ", "")

    return data_match


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


def parse_commands_data(data: str):
    lines = data.replace(" ", "").split("\n")
    cmd_map: dict[str, list[str]] = {}

    if lines[-1] == "":
        lines.pop()

    for line in lines:
        match = re.search(r"SCENE\_CMD\_[a-zA-Z0-9\_]*", line, re.DOTALL)

        if match is not None:
            cmd = match.group(0)
            cmd_map[cmd] = line.removeprefix(f"{cmd}(").removesuffix("),").split(",")
        else:
            raise PluginError(f"ERROR: no command found! ({repr(line)})")

    return cmd_map


def get_array_count(shared_data: SharedSceneData, symbol: str):
    header_path = Path(shared_data.scenePath).resolve() / f"{shared_data.scene_name}.h"

    if not header_path.exists():
        raise PluginError("ERROR: can't find scene header!")

    symbol = symbol.removeprefix("ARRAY_COUNT(").removesuffix(")")
    match = re.search(rf"#define\s*LENGTH_{symbol}\s*([0-9]*)", header_path.read_text(), re.DOTALL)

    if match is None:
        raise PluginError(f"ERROR: can't find array count for {repr(symbol)}")

    return hexOrDecInt(match.group(1))

import bpy
from ..utility import PluginError, toAlnum


class OOTPath:
    def __init__(self, ownerName, objName: str):
        self.ownerName = toAlnum(ownerName)
        self.objName = objName
        self.points = []

    def pathName(self, headerIndex, index):
        return self.ownerName + "_pathwayList" + str(headerIndex) + "_" + str(index)


def ootConvertPath(name, obj, transformMatrix):
    path = OOTPath(name, obj.name)

    spline = obj.data.splines[0]
    for point in spline.points:
        position = transformMatrix @ point.co
        path.points.append(position)

    return path


def onSplineTypeSet(self, context):
    self.splines.active.order_u = 1


def assertCurveValid(obj):
    curve = obj.data
    if not isinstance(curve, bpy.types.Curve) or curve.splines[0].type != "NURBS":
        # Curve was likely not intended to be exported
        return False
    if len(curve.splines) != 1:
        # Curve was intended to be exported but has multiple disconnected segments
        raise PluginError("Exported curves should have only one single segment, found " + str(len(curve.splines)))
    return True

import bpy
from bpy.utils import register_class, unregister_class
from ..utility import PluginError, toAlnum, prop_split, register_recursive


class OOTPath:
    def __init__(self, ownerName, splineIndex):
        self.ownerName = toAlnum(ownerName)
        self.splineIndex = splineIndex
        self.points = []

    def pathName(self):
        return self.ownerName + "_pathwayList_" + str(self.splineIndex)


def ootConvertPath(name, index, obj, transformMatrix):
    path = OOTPath(name, index)

    spline = obj.data.splines[0]
    for point in spline.points:
        position = transformMatrix @ point.co
        path.points.append(position)
        # path.speeds.append(int(round(point.radius)))

    return path


def onSplineTypeSet(self, context):
    self.splines.active.order_u = 1


class OOTSplinePanel(bpy.types.Panel):
    bl_label = "Spline Inspector"
    bl_idname = "OBJECT_PT_OOT_Spline_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "OOT" and (
            context.object is not None and type(context.object.data) == bpy.types.Curve
        )

    def draw(self, context):
        box = self.layout.box()
        box.box().label(text="OOT Spline Inspector")
        curve = context.object.data
        if curve.splines[0].type != "NURBS":
            box.label(text="Only NURBS curves are compatible.")
        else:
            prop_split(box, context.object.ootSplineProperty, "index", "Index")

        # drawParentSceneRoom(box, context.object)


class OOTSplineProperty(bpy.types.PropertyGroup):
    index: bpy.props.IntProperty(default=0, min=0)


def assertCurveValid(obj):
    curve = obj.data
    if not isinstance(curve, bpy.types.Curve) or curve.splines[0].type != "NURBS":
        # Curve was likely not intended to be exported
        return False
    if len(curve.splines) != 1:
        # Curve was intended to be exported but has multiple disconnected segments
        raise PluginError("Exported curves should have only one single segment, found " + str(len(curve.splines)))
    return True


oot_spline_classes = (OOTSplineProperty,)


oot_spline_panel_classes = (OOTSplinePanel,)


def oot_spline_panel_register():
    for cls in oot_spline_panel_classes:
        register_recursive(cls)


def oot_spline_panel_unregister():
    for cls in oot_spline_panel_classes:
        unregister_class(cls)


def oot_spline_register():
    for cls in oot_spline_classes:
        register_recursive(cls)

    bpy.types.Object.ootSplineProperty = bpy.props.PointerProperty(type=OOTSplineProperty)


def oot_spline_unregister():

    for cls in reversed(oot_spline_classes):
        unregister_class(cls)

    del bpy.types.Object.ootSplineProperty

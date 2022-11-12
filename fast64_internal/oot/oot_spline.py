import bpy
from bpy.utils import register_class, unregister_class
from ..utility import PluginError, toAlnum, prop_split
from .oot_utility import getSceneObj, drawEnumWithCustom
from .oot_actor import drawActorHeaderProperty, OOTActorHeaderProperty
from .oot_collision_classes import ootEnumCameraCrawlspaceSType


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
        box = self.layout.box().column()
        box.box().label(text="OOT Spline Inspector")
        curve = context.object.data
        if curve.splines[0].type != "NURBS":
            box.label(text="Only NURBS curves are compatible.")
        else:
            sceneObj = getSceneObj(context.object)
            altSceneProp = sceneObj.ootAlternateSceneHeaders if sceneObj is not None else None
            splineProp = context.object.ootSplineProperty

            prop_split(box, splineProp, "splineType", "Type")
            if splineProp.splineType == "Path":
                drawActorHeaderProperty(box, splineProp.headerSettings, "Curve", altSceneProp, context.object.name)
            elif splineProp.splineType == "Crawlspace":
                box.label(text="This counts as a camera for index purposes.", icon="INFO")
                prop_split(box, splineProp, "index", "Index")
                drawEnumWithCustom(box, splineProp, "camSType", "Camera S Type", "")

        # drawParentSceneRoom(box, context.object)


ootSplineEnum = [("Path", "Path", "Path"), ("Crawlspace", "Crawlspace", "Crawlspace")]


class OOTSplineProperty(bpy.types.PropertyGroup):
    splineType: bpy.props.EnumProperty(items=ootSplineEnum, default="Path")
    index: bpy.props.IntProperty(min=0)  # only used for crawlspace, not path
    headerSettings: bpy.props.PointerProperty(type=OOTActorHeaderProperty)
    camSType: bpy.props.EnumProperty(items=ootEnumCameraCrawlspaceSType, default="CAM_SET_CRAWLSPACE")
    camSTypeCustom: bpy.props.StringProperty(default="CAM_SET_CRAWLSPACE")


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
        register_class(cls)


def oot_spline_panel_unregister():
    for cls in oot_spline_panel_classes:
        unregister_class(cls)


def oot_spline_register():
    for cls in oot_spline_classes:
        register_class(cls)

    bpy.types.Object.ootSplineProperty = bpy.props.PointerProperty(type=OOTSplineProperty)


def oot_spline_unregister():

    for cls in reversed(oot_spline_classes):
        unregister_class(cls)

    del bpy.types.Object.ootSplineProperty

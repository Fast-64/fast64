from bpy.types import Panel, PropertyGroup, Curve, Object
from bpy.props import EnumProperty, PointerProperty, StringProperty, IntProperty
from bpy.utils import register_class, unregister_class
from ....utility import prop_split
from ...oot_utility import getSceneObj, drawEnumWithCustom
from ...oot_actor import drawActorHeaderProperty
from ...oot_collision_classes import ootEnumCameraCrawlspaceSType
from ...actor.properties import OOTActorHeaderProperty


##############
# Properties #
##############
ootSplineEnum = [("Path", "Path", "Path"), ("Crawlspace", "Crawlspace", "Crawlspace")]


class OOTSplineProperty(PropertyGroup):
    splineType: EnumProperty(items=ootSplineEnum, default="Path")
    index: IntProperty(min=0)  # only used for crawlspace, not path
    headerSettings: PointerProperty(type=OOTActorHeaderProperty)
    camSType: EnumProperty(items=ootEnumCameraCrawlspaceSType, default="CAM_SET_CRAWLSPACE")
    camSTypeCustom: StringProperty(default="CAM_SET_CRAWLSPACE")


#############
#   Panel   #
#############
class OOTSplinePanel(Panel):
    bl_label = "Spline Inspector"
    bl_idname = "OBJECT_PT_OOT_Spline_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "OOT" and (
            context.object is not None and type(context.object.data) == Curve
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


oot_spline_classes = (OOTSplineProperty,)


oot_spline_panel_classes = (OOTSplinePanel,)


def spline_props_panel_register():
    for cls in oot_spline_panel_classes:
        register_class(cls)


def spline_props_panel_unregister():
    for cls in oot_spline_panel_classes:
        unregister_class(cls)


def spline_props_classes_register():
    for cls in oot_spline_classes:
        register_class(cls)

    Object.ootSplineProperty = PointerProperty(type=OOTSplineProperty)


def spline_props_classes_unregister():

    for cls in reversed(oot_spline_classes):
        unregister_class(cls)

    del Object.ootSplineProperty

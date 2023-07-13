from bpy.types import PropertyGroup, Object, UILayout
from bpy.props import EnumProperty, PointerProperty, StringProperty, IntProperty
from bpy.utils import register_class, unregister_class
from ...utility import prop_split
from ..oot_utility import drawEnumWithCustom
from ..collision.constants import ootEnumCameraCrawlspaceSType
from ..actor.properties import OOTActorHeaderProperty
from ..scene.properties import OOTAlternateSceneHeaderProperty


ootSplineEnum = [("Path", "Path", "Path"), ("Crawlspace", "Crawlspace", "Crawlspace")]


class OOTSplineProperty(PropertyGroup):
    splineType: EnumProperty(items=ootSplineEnum, default="Path")
    index: IntProperty(min=0)  # only used for crawlspace, not path
    headerSettings: PointerProperty(type=OOTActorHeaderProperty)
    camSType: EnumProperty(items=ootEnumCameraCrawlspaceSType, default="CAM_SET_CRAWLSPACE")
    camSTypeCustom: StringProperty(default="CAM_SET_CRAWLSPACE")

    def draw_props(self, layout: UILayout, altSceneProp: OOTAlternateSceneHeaderProperty, objName: str):
        prop_split(layout, self, "splineType", "Type")
        if self.splineType == "Path":
            headerProp: OOTActorHeaderProperty = self.headerSettings
            headerProp.draw_props(layout, "Curve", altSceneProp, objName)
        elif self.splineType == "Crawlspace":
            layout.label(text="This counts as a camera for index purposes.", icon="INFO")
            prop_split(layout, self, "index", "Index")
            drawEnumWithCustom(layout, self, "camSType", "Camera S Type", "")


oot_spline_classes = (OOTSplineProperty,)


def spline_props_register():
    for cls in oot_spline_classes:
        register_class(cls)

    Object.ootSplineProperty = PointerProperty(type=OOTSplineProperty)


def spline_props_unregister():

    for cls in reversed(oot_spline_classes):
        unregister_class(cls)

    del Object.ootSplineProperty

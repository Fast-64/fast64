from bpy.types import PropertyGroup, Object, UILayout
from bpy.props import EnumProperty, PointerProperty, StringProperty, IntProperty
from bpy.utils import register_class, unregister_class
from ...utility import prop_split
from ...game_data import game_data
from ..utility import drawEnumWithCustom, is_oot_features
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

    # MM exclusive
    opt_path_index: IntProperty(name="Additional Path Index", min=-1, default=-1)
    custom_value: IntProperty(name="Custom Value", min=-1, default=-1)

    def draw_props(self, layout: UILayout, altSceneProp: OOTAlternateSceneHeaderProperty, objName: str):
        camIndexName = "Path Index" if self.splineType == "Path" else "Camera Index"
        prop_split(layout, self, "splineType", "Type")
        prop_split(layout, self, "index", camIndexName)

        if not is_oot_features():
            prop_split(layout, self, "opt_path_index", "Additional Path Index")
            prop_split(layout, self, "custom_value", "Custom Value")

        if self.splineType == "Path":
            headerProp: OOTActorHeaderProperty = self.headerSettings
            headerProp.draw_props(layout, "Curve", altSceneProp, objName)
        elif self.splineType == "Crawlspace":
            if game_data.z64.is_mm():
                layout.label(text="Warning: MM doesn't have crawlspaces implemented.", icon="ERROR")
            layout.label(text="This counts as a camera for index purposes.", icon="INFO")
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

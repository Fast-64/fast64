import bpy

from bpy.types import PropertyGroup, Object, UILayout
from bpy.props import EnumProperty, PointerProperty, StringProperty, IntProperty
from bpy.utils import register_class, unregister_class
from ...utility import prop_split
from ..utility import drawEnumWithCustom, is_game_oot, get_game_props
from ..collision.constants import enum_camera_crawlspace_stype
from ..actor.properties import Z64_ActorHeaderProperty
from ..scene.properties import Z64_AlternateSceneHeaderProperty


enum_spline = [("Path", "Path", "Path"), ("Crawlspace", "Crawlspace", "Crawlspace")]


class Z64_SplineProperty(PropertyGroup):
    splineType: EnumProperty(items=enum_spline, default="Path")
    index: IntProperty(min=0)  # only used for crawlspace, not path
    headerSettings: PointerProperty(type=Z64_ActorHeaderProperty)
    camSType: EnumProperty(items=enum_camera_crawlspace_stype, default="CAM_SET_CRAWLSPACE")
    camSTypeCustom: StringProperty(default="CAM_SET_CRAWLSPACE")

    # MM exclusive
    opt_path_index: IntProperty(name="Additional Path Index", min=-1, default=-1)
    custom_value: IntProperty(name="Custom Value", min=-1, default=-1)

    def draw_props(
        self,
        layout: UILayout,
        altSceneProp: Z64_AlternateSceneHeaderProperty,
        objName: str,
    ):
        camIndexName = "Path Index" if self.splineType == "Path" else "Camera Index"
        prop_split(layout, self, "splineType", "Type")
        prop_split(layout, self, "index", camIndexName)

        if not is_game_oot():
            prop_split(layout, self, "opt_path_index", "Additional Path Index")
            prop_split(layout, self, "custom_value", "Custom Value")

        if self.splineType == "Path":
            headerProp: Z64_ActorHeaderProperty = get_game_props(bpy.data.objects[objName], "path_header_settings")
            headerProp.draw_props(layout, "Curve", altSceneProp, objName)
        elif self.splineType == "Crawlspace":
            layout.label(text="This counts as a camera for index purposes.", icon="INFO")
            drawEnumWithCustom(layout, self, "camSType", "Camera S Type", "")


oot_spline_classes = (Z64_SplineProperty,)


def spline_props_register():
    for cls in oot_spline_classes:
        register_class(cls)

    Object.ootSplineProperty = PointerProperty(type=Z64_SplineProperty)


def spline_props_unregister():
    for cls in reversed(oot_spline_classes):
        unregister_class(cls)

    del Object.ootSplineProperty

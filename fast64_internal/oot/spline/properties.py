from bpy.types import PropertyGroup, Object
from bpy.props import EnumProperty, PointerProperty, StringProperty, IntProperty
from bpy.utils import register_class, unregister_class
from ..oot_collision_classes import ootEnumCameraCrawlspaceSType
from ..actor.properties import OOTActorHeaderProperty


ootSplineEnum = [("Path", "Path", "Path"), ("Crawlspace", "Crawlspace", "Crawlspace")]


class OOTSplineProperty(PropertyGroup):
    splineType: EnumProperty(items=ootSplineEnum, default="Path")
    index: IntProperty(min=0)  # only used for crawlspace, not path
    headerSettings: PointerProperty(type=OOTActorHeaderProperty)
    camSType: EnumProperty(items=ootEnumCameraCrawlspaceSType, default="CAM_SET_CRAWLSPACE")
    camSTypeCustom: StringProperty(default="CAM_SET_CRAWLSPACE")


oot_spline_classes = (
    OOTSplineProperty,
)


def spline_props_register():
    for cls in oot_spline_classes:
        register_class(cls)

    Object.ootSplineProperty = PointerProperty(type=OOTSplineProperty)


def spline_props_unregister():

    for cls in reversed(oot_spline_classes):
        unregister_class(cls)

    del Object.ootSplineProperty

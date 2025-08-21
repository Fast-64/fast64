import bpy
from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty, FloatProperty, PointerProperty
from bpy.types import PropertyGroup, UILayout
from bpy.utils import register_class, unregister_class
from ..utility import prop_split
from ..f3d.f3d_material import ootEnumDrawLayers

from .mk64_constants import enum_surface_types, enum_actor_types

from ..render_settings import on_update_render_settings

# ------------------------------------------------------------------------
#    Import Properties
# ------------------------------------------------------------------------


class MK64_ImportProperties(PropertyGroup):
    """
    Properties for importing courses, used in the import panel
    found under scene.fast64.mk64
    """

    name: StringProperty(name="Name")
    path: StringProperty(name="Directory", subtype="FILE_PATH")
    base_path: StringProperty(name="Directory", subtype="FILE_PATH")
    remove_doubles: BoolProperty(name="Remove Doubles", default=True)
    import_normals: BoolProperty(name="Import Normals", default=True)
    enable_render_Mode_Default: BoolProperty(name="Set Render Mode by Default", default=True)

    def draw_props(self, layout: UILayout):
        prop_split(layout, self, "name", "Name")
        prop_split(layout, self, "path", "File")
        prop_split(layout, self, "base_path", "Base Path")
        layout.prop(self, "remove_doubles")
        layout.prop(self, "import_normals")

        layout.prop(self, "enable_render_Mode_Default")


# ------------------------------------------------------------------------
#    Export Properties
# ------------------------------------------------------------------------


class MK64_ExportProperties(PropertyGroup):
    """
    Properties for exporting courses, used in the export panel
    found under scene.fast64.mk64
    """

    name: StringProperty(name="Name")
    export_path: StringProperty(name="Directory", subtype="FILE_PATH")
    decomp_path: StringProperty(name="Directory", subtype="FILE_PATH")
    enable_render_Mode_Default: BoolProperty(name="Set Render Mode by Default", default=True)

    def draw_props(self, layout: UILayout):
        prop_split(layout, self, "name", "Name")
        prop_split(layout, self, "export_path", "export_path")
        prop_split(layout, self, "decomp_path", "decomp_path")


# ------------------------------------------------------------------------
#    Scene Properties
# ------------------------------------------------------------------------


class MK64_Properties(PropertyGroup):
    """Global MK64 Scene Properties found under scene.fast64.mk64"""

    # Import Course DL
    course_DL_import_settings: bpy.props.PointerProperty(type=MK64_ImportProperties)
    # exporter settings, merge with above later?
    course_export_settings: bpy.props.PointerProperty(type=MK64_ExportProperties)
    scale: FloatProperty(name="F3D Blender Scale", default=100, update=on_update_render_settings)

    @staticmethod
    def upgrade_changed_props():
        pass


# ------------------------------------------------------------------------
#    Course Data Properties
# ------------------------------------------------------------------------


class MK64_ObjectProperties(PropertyGroup):
    """
    Properties for course data, linked to empty objects
    found under object.fast64.mk64
    """

    obj_type: EnumProperty(
        name="Object Type",
        items=[
            ("Course Root", "Course Root", "Course Root"),
            ("Actor", "Actor", "Actor"),
        ],
    )
    actor_type: EnumProperty(name="Actor Type", items=enum_actor_types)

    # for mesh objects
    has_col: BoolProperty(name="Has Collision", default=True)
    col_type: EnumProperty(name="Collision Type", items=enum_surface_types, default="SURFACE_DEFAULT")
    section_id: IntProperty(name="section_id", default=255, min=0, max=255)


class MK64_CurveProperties(PropertyGroup):
    """
    Properties for curve data, linked to curve objects
    found under curve.fast64.mk64
    """

    section_id: IntProperty(name="section_id", default=255, min=0, max=255)


mk64_property_classes = (
    MK64_ImportProperties,
    MK64_ExportProperties,
    MK64_ObjectProperties,
    MK64_CurveProperties,
    MK64_Properties,
)


def mk64_props_register():
    for cls in mk64_property_classes:
        register_class(cls)


def mk64_props_unregister():
    for cls in reversed(mk64_property_classes):
        unregister_class(cls)

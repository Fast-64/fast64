from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty, FloatProperty, PointerProperty
from bpy.types import PropertyGroup, UILayout
from bpy.utils import register_class, unregister_class
from ...utility import prop_split
from ...f3d.f3d_material import ootEnumDrawLayers

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
        # prop_split(layout, self, "decomp_path", "decomp_path")


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
            ("Item", "Item", "Item"),
        ],
    )

    def draw_props(self, layout: UILayout):
        prop_split(layout, self, "obj_type", "object type")


class MK64_MeshProperties(PropertyGroup):
    """
    Properties for mesh data, linked to mesh objects
    found under mesh.fast64.mk64
    """

    has_col: BoolProperty(name="Has Collision", default=True)

    def draw_props(self, layout: UILayout):
        prop_split(layout, self, "has_col", "Has Collision")


class MK64_CurveProperties(PropertyGroup):
    """
    Properties for curve data, linked to curve objects
    found under curve.fast64.mk64
    """

    has_col: BoolProperty(name="Has Collision", default=True)

    def draw_props(self, layout: UILayout):
        prop_split(layout, self, "has_col", "Has Collision")


mk64_property_classes = [
    MK64_ImportProperties,
    MK64_ExportProperties,
    MK64_ObjectProperties,
    MK64_MeshProperties,
    MK64_CurveProperties,
]


def f3d_props_register():
    for cls in mk64_property_classes:
        register_class(cls)


def f3d_props_unregister():
    for cls in reversed(mk64_property_classes):
        unregister_class(cls)

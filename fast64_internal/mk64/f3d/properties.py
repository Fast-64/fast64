from bpy.props import StringProperty, BoolProperty
from bpy.types import PropertyGroup, UILayout
from bpy.utils import register_class, unregister_class
from ...utility import prop_split
from ...f3d.f3d_material import ootEnumDrawLayers


class MK64CourseDLImportSettings(PropertyGroup):
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


mk64_dl_writer_classes = [
    MK64CourseDLImportSettings,
]


def f3d_props_register():
    for cls in mk64_dl_writer_classes:
        register_class(cls)


def f3d_props_unregister():
    for cls in reversed(mk64_dl_writer_classes):
        unregister_class(cls)

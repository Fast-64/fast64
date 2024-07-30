from bpy.props import StringProperty, EnumProperty, FloatProperty, BoolProperty
from bpy.types import PropertyGroup, UILayout
from bpy.utils import register_class, unregister_class
from ...utility import prop_split
from ...render_settings import (
    on_update_render_settings,
)
from ...f3d.f3d_material import ootEnumDrawLayers


class MK64CourseDLImportSettings(PropertyGroup):
    name: StringProperty(name="Name")
    path: StringProperty(name="Directory", subtype="FILE_PATH")
    basePath: StringProperty(name="Directory", subtype="FILE_PATH")
    scale: FloatProperty(name="F3D Blender Scale", default=100, update=on_update_render_settings)
    removeDoubles: BoolProperty(name="Remove Doubles", default=True)
    importNormals: BoolProperty(name="Import Normals", default=True)
    enableRenderModeDefault: BoolProperty(name="Set Render Mode by Default", default=True)

    def draw_props(self, layout: UILayout):
        prop_split(layout, self, "name", "Name")
        prop_split(layout, self, "path", "File")
        prop_split(layout, self, "basePath", "Base Path")
        prop_split(layout, self, "scale", "Scale")
        layout.prop(self, "removeDoubles")
        layout.prop(self, "importNormals")

        layout.prop(self, "enableRenderModeDefault")


mk64_dl_writer_classes = [
    MK64CourseDLImportSettings,
]


def f3d_props_register():
    for cls in mk64_dl_writer_classes:
        register_class(cls)


def f3d_props_unregister():
    for cls in reversed(mk64_dl_writer_classes):
        unregister_class(cls)

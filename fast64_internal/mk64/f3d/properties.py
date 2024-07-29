from bpy.props import StringProperty, EnumProperty, FloatProperty, BoolProperty
from bpy.types import PropertyGroup, UILayout
from bpy.utils import register_class, unregister_class
from ...utility import prop_split
from ...render_settings import (
    on_update_render_settings,
)
from ...f3d.f3d_material import ootEnumDrawLayers


class MK64CourseDLImportSettings(PropertyGroup):
    DLImportName: StringProperty(name="Name")
    DLImportPath: StringProperty(name="Directory", subtype="FILE_PATH")
    DLImportBasePath: StringProperty(name="Directory", subtype="FILE_PATH")
    blenderF3DScale: FloatProperty(name="F3D Blender Scale", default=100, update=on_update_render_settings)
    DLImportDrawLayer: EnumProperty(name="Draw Layer", items=ootEnumDrawLayers)
    DLRemoveDoubles: BoolProperty(name="Remove Doubles", default=True)
    DLImportNormals: BoolProperty(name="Import Normals", default=True)
    EnableRenderModeDefault: BoolProperty(name="Set Render Mode by Default", default=True)

    def draw_props(self, layout: UILayout):
        prop_split(layout, self, "DLImportName", "Name")
        prop_split(layout, self, "DLImportPath", "File")
        prop_split(layout, self, "DLImportBasePath", "Base Path")
        prop_split(layout, self, "blenderF3DScale", "Scale")
        prop_split(layout, self, "DLImportDrawLayer", "Draw Layer")
        layout.prop(self, "DLRemoveDoubles")
        layout.prop(self, "DLImportNormals")

        prop_split(layout, self, "EnableRenderModeDefault", "Enable Render Mode by Default")


mk64_dl_writer_classes = [
    MK64CourseDLImportSettings,
]


def f3d_props_register():
    for cls in mk64_dl_writer_classes:
        register_class(cls)


def f3d_props_unregister():
    for cls in reversed(mk64_dl_writer_classes):
        unregister_class(cls)

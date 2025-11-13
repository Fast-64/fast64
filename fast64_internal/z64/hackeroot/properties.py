import bpy

from bpy.utils import register_class, unregister_class

from ..scene.properties import OOTBootupSceneOptions
from .operators import HackerOoT_ClearBootupScene


class HackerOoTSettings(bpy.types.PropertyGroup):
    export_ifdefs: bpy.props.BoolProperty(default=True)

    def draw_props(self, context: bpy.types.Context, layout: bpy.types.UILayout):
        export_box = layout.box()
        export_box.label(text="Export Settings")
        export_box.prop(self, "export_ifdefs", text="Export ifdefs")

        boot_box = export_box.box().column()

        bootOptions: OOTBootupSceneOptions = context.scene.fast64.oot.bootupSceneOptions
        bootOptions.draw_props(boot_box)

        boot_box.label(text="Note: Scene boot config changes aren't detected by the make process.", icon="ERROR")
        boot_box.operator(HackerOoT_ClearBootupScene.bl_idname, text="Undo Boot To Scene (HackerOOT Repo)")


classes = (HackerOoTSettings,)


def hackeroot_props_register():
    for cls in classes:
        register_class(cls)


def hackeroot_props_unregister():
    for cls in reversed(classes):
        unregister_class(cls)

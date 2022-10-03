from bpy.utils import register_class, unregister_class
from bpy.props import StringProperty, FloatProperty
from bpy.types import Scene
from ....utility import prop_split
from ....render_settings import on_update_render_settings
from ...panel import OOT_Panel


class OOT_FileSettingsPanel(OOT_Panel):
    bl_idname = "OOT_PT_file_settings"
    bl_label = "OOT File Settings"
    bl_options = set()  # default to being open

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.scale_y = 1.1  # extra padding, makes it easier to see these main settings
        prop_split(col, context.scene, "ootBlenderScale", "OOT Scene Scale")
        prop_split(col, context.scene, "ootActorBlenderScale", "OOT Actor Scale")

        prop_split(col, context.scene, "ootDecompPath", "Decomp Path")
        col.prop(context.scene.fast64.oot, "hackerFeaturesEnabled")


oot_classes = (OOT_FileSettingsPanel,)


def file_register():
    for cls in oot_classes:
        register_class(cls)

    Scene.ootBlenderScale = FloatProperty(name="Blender To OOT Scale", default=10, update=on_update_render_settings)
    Scene.ootActorBlenderScale = FloatProperty(name="Blender To OOT Actor Scale", default=1000)
    Scene.ootDecompPath = StringProperty(name="Decomp Folder", subtype="FILE_PATH")


def file_unregister():
    for cls in reversed(oot_classes):
        unregister_class(cls)

    del Scene.ootBlenderScale
    del Scene.ootActorBlenderScale
    del Scene.ootDecompPath

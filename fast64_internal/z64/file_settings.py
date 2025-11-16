from bpy.utils import register_class, unregister_class
from bpy.props import StringProperty, FloatProperty
from bpy.types import Scene

from ..game_data import game_data
from ..utility import prop_split
from ..render_settings import on_update_render_settings
from ..panels import OOT_Panel


class OOT_FileSettingsPanel(OOT_Panel):
    bl_idname = "Z64_PT_file_settings"
    bl_label = "Workspace Settings"
    bl_options = set()  # default to being open

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.scale_y = 1.1  # extra padding, makes it easier to see these main settings
        prop_split(col, context.scene, "ootBlenderScale", "OOT Scene Scale")

        prop_split(col, context.scene, "ootDecompPath", "Decomp Path")

        version = "oot_version" if game_data.z64.is_oot() else "mm_version"
        prop_split(col, context.scene.fast64.oot, version, "Game Version")
        if context.scene.fast64.oot.oot_version == "Custom":
            prop_split(col, context.scene.fast64.oot, "oot_version_custom", "Custom Version")

        col.prop(context.scene.fast64.oot, "headerTabAffectsVisibility")

        if game_data.z64.is_oot():
            col.prop(context.scene.fast64.oot, "hackerFeaturesEnabled")

            if not context.scene.fast64.oot.hackerFeaturesEnabled:
                col.prop(context.scene.fast64.oot, "mm_features")

        if game_data.z64.is_mm() or not context.scene.fast64.oot.hackerFeaturesEnabled:
            col.prop(context.scene.fast64.oot, "useDecompFeatures")
        col.prop(context.scene.fast64.oot, "exportMotionOnly")

        if game_data.z64.is_oot():
            col.prop(context.scene.fast64.oot, "use_new_actor_panel")


oot_classes = (OOT_FileSettingsPanel,)


def file_register():
    for cls in oot_classes:
        register_class(cls)

    Scene.ootBlenderScale = FloatProperty(name="Blender To OOT Scale", default=10, update=on_update_render_settings)
    Scene.ootDecompPath = StringProperty(name="Decomp Folder", subtype="FILE_PATH")


def file_unregister():
    for cls in reversed(oot_classes):
        unregister_class(cls)

    del Scene.ootBlenderScale
    del Scene.ootDecompPath

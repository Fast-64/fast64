import bpy
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

        if game_data.z64.is_oot():
            prop_split(col, context.scene, "oot_decomp_path", "Decomp Path")
        else:
            prop_split(col, context.scene.fast64.oot, "mm_decomp_path", "Decomp Path")

        is_oot = game_data.z64.is_oot()
        version = "oot_version" if is_oot else "mm_version"
        prop_split(col, context.scene.fast64.oot, version, "Game Version")
        if context.scene.fast64.oot.oot_version == "Custom":
            prop_split(col, context.scene.fast64.oot, "oot_version_custom", "Custom Version")

        is_decomp = context.scene.fast64.oot.feature_set == "default"
        if is_oot:
            prop_split(col, context.scene.fast64.oot, "feature_set", "Feature Set")

        col.prop(context.scene.fast64.oot, "headerTabAffectsVisibility")

        if is_oot and is_decomp:
            col.prop(context.scene.fast64.oot, "mm_features")

        if game_data.z64.is_mm() or is_decomp:
            col.prop(context.scene.fast64.oot, "useDecompFeatures")

        col.prop(context.scene.fast64.oot, "exportMotionOnly")

        if is_oot:
            col.prop(context.scene.fast64.oot, "use_new_actor_panel")


oot_classes = (OOT_FileSettingsPanel,)


def file_register():
    for cls in oot_classes:
        register_class(cls)

    Scene.ootBlenderScale = FloatProperty(name="Blender To OOT Scale", default=10, update=on_update_render_settings)

    # TODO: remove `ootDecompPath` entirely
    def get_decomp_path():
        game_data.z64.update(bpy.context, None)
        if game_data.z64.is_oot():
            return bpy.context.scene.fast64.oot.oot_decomp_path
        else:
            return bpy.context.scene.fast64.oot.mm_decomp_path

    Scene.ootDecompPath = StringProperty(name="Decomp Folder", subtype="FILE_PATH", get=lambda self: get_decomp_path())


def file_unregister():
    for cls in reversed(oot_classes):
        unregister_class(cls)

    del Scene.ootBlenderScale
    del Scene.ootDecompPath

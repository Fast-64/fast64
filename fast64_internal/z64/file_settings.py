from bpy.utils import register_class, unregister_class
from bpy.props import StringProperty, FloatProperty, BoolProperty
from bpy.types import Scene
from ..utility import prop_split
from ..render_settings import on_update_render_settings
from ..panels import Z64_Panel


class OOT_FileSettingsPanel(Z64_Panel):
    bl_idname = "Z64_PT_file_settings"
    bl_label = "Workspace Settings"
    bl_options = set()  # default to being open

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.scale_y = 1.1  # extra padding, makes it easier to see these main settings

        prop_split(col, context.scene, "ootBlenderScale", "Scene Scale")
        prop_split(col, context.scene, "ootDecompPath", "Decomp Path")

        if context.scene.gameEditorMode == "OOT":
            version = "oot_version"
        else:
            version = "mm_version"

        prop_split(col, context.scene.fast64.oot, version, "Version")

        if getattr(context.scene.fast64.oot, version) == "Custom":
            prop_split(col, context.scene.fast64.oot, "version_custom", "Custom Version")

        col.prop(context.scene.fast64.oot, "headerTabAffectsVisibility")
        col.prop(context.scene.fast64.oot, "hackerFeaturesEnabled")

        if not context.scene.fast64.oot.hackerFeaturesEnabled:
            col.prop(context.scene.fast64.oot, "useDecompFeatures")
        col.prop(context.scene.fast64.oot, "exportMotionOnly")
        col.prop(context.scene.fast64.oot, "use_new_actor_panel")

        if context.scene.gameEditorMode == "OOT":
            col.prop(context.scene.fast64.oot, "mm_features")


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

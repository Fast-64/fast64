from bpy.utils import register_class, unregister_class

from ...panels import OOT_Panel


class HackerOoTSettingsPanel(OOT_Panel):
    bl_idname = "Z64_PT_hackeroot_settings"
    bl_label = "HackerOoT Settings"

    def draw(self, context):
        if context.scene.fast64.oot.feature_set == "hackeroot":
            context.scene.fast64.oot.hackeroot_settings.draw_props(context, self.layout)
        else:
            self.layout.label(text="HackerOoT features are disabled.", icon="QUESTION")


panel_classes = (HackerOoTSettingsPanel,)


def hackeroot_panels_register():
    for cls in panel_classes:
        register_class(cls)


def hackeroot_panels_unregister():
    for cls in reversed(panel_classes):
        unregister_class(cls)

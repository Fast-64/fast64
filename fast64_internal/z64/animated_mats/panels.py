from bpy.utils import register_class, unregister_class

from ...panels import OOT_Panel
from ..utility import is_oot_features, is_hackeroot


class Z64_AnimatedMaterialsPanel(OOT_Panel):
    bl_idname = "Z64_PT_animated_materials"
    bl_label = "Animated Materials Exporter"

    def draw(self, context):
        if not is_oot_features() or is_hackeroot():
            context.scene.fast64.oot.anim_mats_export_settings.draw_props(self.layout.box())
            context.scene.fast64.oot.anim_mats_import_settings.draw_props(self.layout.box())
        else:
            self.layout.label(text="MM features are disabled.", icon="QUESTION")


panel_classes = (Z64_AnimatedMaterialsPanel,)


def animated_mats_panels_register():
    for cls in panel_classes:
        register_class(cls)


def animated_mats_panels_unregister():
    for cls in reversed(panel_classes):
        unregister_class(cls)

from bpy.utils import register_class, unregister_class
from bpy.types import Context

from ...panels import SM64_Panel

from .repo_settings import draw_repo_settings


class SM64_GeneralSettingsPanel(SM64_Panel):
    bl_idname = "SM64_PT_general_settings"
    bl_label = "SM64 General Settings"

    def draw(self, context: Context):
        col = self.layout.column()
        sm64_props = context.scene.fast64.sm64

        if sm64_props.export_type == "C":
            # If the repo settings tab is open, we pass show_repo_settings as False
            # because we want to draw those specfic properties in the repo settings box
            sm64_props.draw_props(col, not sm64_props.sm64_repo_settings_tab)
            col.separator()
            draw_repo_settings(context.scene, col)
        else:
            sm64_props.draw_props(col, True)


classes = (SM64_GeneralSettingsPanel,)


def settings_panels_register():
    for cls in classes:
        register_class(cls)


def settings_panels_unregister():
    for cls in classes:
        unregister_class(cls)

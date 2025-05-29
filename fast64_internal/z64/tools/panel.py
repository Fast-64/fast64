from bpy.utils import register_class, unregister_class
from ...panels import Z64_Panel
from .operators import (
    OOT_AddWaterBox,
    OOT_AddDoor,
    OOT_AddScene,
    OOT_AddRoom,
    OOT_AddCutscene,
    OOT_AddPath,
    OOTClearTransformAndLock,
    OOTQuickImport,
    Z64_AddActorCutscenes,
)


class OoT_ToolsPanel(Z64_Panel):
    bl_idname = "Z64_PT_tools"
    bl_label = "Tools"

    def draw(self, context):
        col = self.layout.row(align=True)
        col.operator(OOT_AddWaterBox.bl_idname)
        col.operator(OOT_AddDoor.bl_idname)

        col = self.layout.row(align=True)
        col.operator(OOT_AddScene.bl_idname)
        col.operator(OOT_AddRoom.bl_idname)

        col = self.layout.row(align=True)
        col.operator(OOT_AddCutscene.bl_idname)
        col.operator(OOT_AddPath.bl_idname)

        col = self.layout.row(align=True)
        col.operator(OOTClearTransformAndLock.bl_idname)
        col.operator(OOTQuickImport.bl_idname)

        col = self.layout.row(align=True)
        col.operator(Z64_AddActorCutscenes.bl_idname)


oot_operator_panel_classes = [
    OoT_ToolsPanel,
]

toolOpsToRegister = [
    OOT_AddWaterBox,
    OOT_AddDoor,
    OOT_AddScene,
    OOT_AddRoom,
    OOT_AddCutscene,
    OOT_AddPath,
    OOTClearTransformAndLock,
    OOTQuickImport,
    Z64_AddActorCutscenes,
]


def oot_operator_panel_register():
    for cls in oot_operator_panel_classes:
        register_class(cls)


def oot_operator_panel_unregister():
    for cls in oot_operator_panel_classes:
        unregister_class(cls)


def oot_operator_register():
    for cls in toolOpsToRegister:
        register_class(cls)


def oot_operator_unregister():
    for cls in reversed(toolOpsToRegister):
        unregister_class(cls)

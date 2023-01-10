from bpy.utils import register_class, unregister_class
from ...panels import OOT_Panel
from .operators import (
    OOT_AddWaterBox,
    OOT_AddDoor,
    OOT_AddScene,
    OOT_AddRoom,
    OOT_AddCutscene,
    OOT_AddPath,
)

from ..actor_collider import OOT_AddActorCollider, OOT_CopyColliderProperties, drawColliderVisibilityOperators
from ...utility_anim import ArmatureApplyWithMeshOperator


class OoT_ToolsPanel(OOT_Panel):
    bl_idname = "OOT_PT_tools"
    bl_label = "OOT Tools"

    def draw(self, context):
        col = self.layout.column()
        col.operator(OOT_AddWaterBox.bl_idname)
        col.operator(OOT_AddDoor.bl_idname)
        col.operator(OOT_AddScene.bl_idname)
        col.operator(OOT_AddRoom.bl_idname)
        col.operator(OOT_AddCutscene.bl_idname)
        col.operator(OOT_AddPath.bl_idname)

        col.label(text="")
        col.label(text="Armatures")
        col.operator(ArmatureApplyWithMeshOperator.bl_idname)

        col.label(text="")
        col.label(text="Actor Colliders")
        col.label(text="Do not scale armatures with joint sphere colliders.", icon="ERROR")
        col.label(text="Applying scale will mess up joint sphere translations.")
        addOp = col.operator(OOT_AddActorCollider.bl_idname, text="Add Joint Sphere Collider (Bones)")
        addOp.shape = "COLSHAPE_JNTSPH"
        addOp.parentToBone = True

        col.operator(
            OOT_AddActorCollider.bl_idname, text="Add Joint Sphere Collider (Object)"
        ).shape = "COLSHAPE_JNTSPH"
        col.operator(OOT_AddActorCollider.bl_idname, text="Add Cylinder Collider").shape = "COLSHAPE_CYLINDER"
        col.operator(OOT_AddActorCollider.bl_idname, text="Add Mesh Collider").shape = "COLSHAPE_TRIS"
        col.operator(OOT_AddActorCollider.bl_idname, text="Add Quad Collider (Properties Only)").shape = "COLSHAPE_QUAD"

        drawColliderVisibilityOperators(col)

        col.operator(OOT_CopyColliderProperties.bl_idname, text="Copy Collider Properties (From Active To Selected)")


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

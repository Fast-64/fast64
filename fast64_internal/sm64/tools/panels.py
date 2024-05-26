from bpy.utils import register_class, unregister_class

from ...utility import prop_split
from ...utility_anim import ArmatureApplyWithMeshOperator
from ...panels import SM64_Panel, sm64GoalImport

from .operators import AddBoneGroups, CreateMetarig, SM64_AddWaterBox, SM64_AddrConv


class SM64_ArmatureToolsPanel(SM64_Panel):
    bl_idname = "SM64_PT_armature_tools"
    bl_label = "SM64 Tools"

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.operator(ArmatureApplyWithMeshOperator.bl_idname)
        col.operator(AddBoneGroups.bl_idname)
        col.operator(CreateMetarig.bl_idname)
        col.operator(SM64_AddWaterBox.bl_idname)


class SM64_AddressConvertPanel(SM64_Panel):
    bl_idname = "SM64_PT_addr_conv"
    bl_label = "SM64 Address Converter"
    goal = sm64GoalImport

    def draw(self, context):
        col = self.layout.column()
        segToVirtOp = col.operator(SM64_AddrConv.bl_idname, text="Convert Segmented To Virtual")
        segToVirtOp.segToVirt = True
        virtToSegOp = col.operator(SM64_AddrConv.bl_idname, text="Convert Virtual To Segmented")
        virtToSegOp.segToVirt = False
        prop_split(col, context.scene, "convertibleAddr", "Address")
        col.prop(context.scene, "levelConvert")


classes = (SM64_ArmatureToolsPanel, SM64_AddressConvertPanel)


def tools_panels_register():
    for cls in classes:
        register_class(cls)


def tools_panels_unregister():
    for cls in classes:
        unregister_class(cls)

from .kcs_gfx import *
from .kcs_col import *
from .kcs_utils import *
from .kcs_ui import *
from .kcs_props import *
from .kcs_operators import *
from bpy.utils import register_class, unregister_class
# ------------------------------------------------------------------------
#    Registration
# ------------------------------------------------------------------------

kcs_classes = (
    StageProp,
    BankIndex,
    KCS_Scene_Props,
    NodeProp,
    CamProp,
    ObjProp,
    LvlProp,
    EntProp,
    MeshProp,
    ColProp,
    TextureProp,
    TexScrollProp,
    KCS_OT_Export,
    KCS_OT_Export_Gfx,
    KCS_OT_Import_Stage,
    KCS_OT_Add_Level,
    KCS_OT_Add_Block,
    KCS_OT_Add_Ent,
    KCS_OT_Add_Node,
    KCS_OT_Import_NLD_Gfx,
    KCS_OT_Import_Col,
    KCS_OT_Add_Tex,
    KCS_OT_Add_Pal,
)

kcs_panel_classes = (
    KCS_PROP_PT_Panel,
    KCS_IO_PT_Panel,
    OBJ_PT_Panel,
    MESH_PT_Panel,
    NODE_PT_Panel,
    CAM_PT_Panel,
    COL_PT_Panel,
    SCROLL_PT_Panel
)

def kcs_register(registerPanels):
    for cls in kcs_classes:
        register_class(cls)
    if registerPanels:
        for cls in kcs_panel_classes:
            register_class(cls)
    

    bpy.types.Scene.KCS_scene = PointerProperty(type = KCS_Scene_Props)
    bpy.types.Curve.KCS_node = PointerProperty(type = NodeProp)
    bpy.types.Camera.KCS_cam = PointerProperty(type = CamProp)
    bpy.types.Object.KCS_lvl = PointerProperty(type = LvlProp)
    bpy.types.Object.KCS_ent = PointerProperty(type = EntProp)
    bpy.types.Object.KCS_obj = PointerProperty(type = ObjProp)
    bpy.types.Object.KCS_mesh = PointerProperty(type = MeshProp)
    bpy.types.Material.KCS_col = PointerProperty(type = ColProp)
    bpy.types.Material.KCS_tx_scroll = PointerProperty(type = TexScrollProp)

def kcs_unregister(unregisterPanels):
    for cls in reversed(kcs_classes):
        unregister_class(cls)
    if unregisterPanels:
        for cls in reversed(kcs_panel_classes):
            unregister_class(cls)
    
    
    del bpy.types.Scene.KCS_scene
    del bpy.types.Curve.KCS_node
    del bpy.types.Camera.KCS_cam
    del bpy.types.Object.KCS_lvl
    del bpy.types.Object.KCS_ent
    del bpy.types.Object.KCS_obj
    del bpy.types.Object.KCS_mesh
    del bpy.types.Material.KCS_col
    del bpy.types.Material.KCS_tx_scroll
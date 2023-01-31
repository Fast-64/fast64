# ------------------------------------------------------------------------
#    Header
# ------------------------------------------------------------------------
import bpy
from bpy.types import Operator
from bpy.utils import register_class, unregister_class

from pathlib import Path

from .kcs_gfx import import_geo_bin, export_geo_c
from .kcs_col import add_node, import_col_bin, export_col_c
from .kcs_utils import parse_stage_table

from ..utility import PluginError

# ------------------------------------------------------------------------
#    IO Operators
# ------------------------------------------------------------------------

# import a collision file / level block file
class KCS_Import_Col(Operator):
    bl_label = "Import Col Data"
    bl_idname = "kcs.import_col"

    def execute(self, context: bpy.types.Context):
        scene = context.scene.KCS_scene
        bank_id = scene.import_bank_id.bank_id()
        file = Path(scene.decomp_path) / "assets" / "misc" / ("bank_%d" % bank_id[0]) / ("%d" % bank_id[1])
        if scene.file_format == "binary":
            name = file / "level.bin"
            if not name.exists():
                name = file / "misc.bin"
            if not name.exists():
                raise PluginError(f"Could not find file {name}, geo Bank/ID does not exist")
            import_col_bin(name, context, "KCS Col {}-{}".format(*bank_id))
        else:
            raise PluginError("C importing is not supported yet")
        return {"FINISHED"}


# import one gfx file
class KCS_Import_NLD_Gfx(Operator):
    bl_label = "Import Gfx Data"
    bl_idname = "kcs.import_nld_gfx"

    def execute(self, context: bpy.types.Context):
        scene = context.scene.KCS_scene
        bank_id = scene.import_bank_id.bank_id()
        file = Path(scene.decomp_path) / "assets" / "geo" / ("bank_%d" % bank_id[0]) / ("%d" % bank_id[1])
        if scene.file_format == "binary":
            name = file / "geo.bin"
            if not name.exists():
                name = file / "block.bin"
            if not name.exists():
                raise PluginError(f"Could not find file {name}, geo Bank/ID does not exist")
            import_geo_bin(
                name, context, "KCS Gfx {}-{}".format(*bank_id), Path(scene.decomp_path) / "assets" / "image"
            )
        else:
            raise PluginError("C importing is not supported yet")
        return {"FINISHED"}


# import an entire stage (gfx, level block)
class KCS_Import_Stage(Operator):
    bl_label = "Import Stage"
    bl_idname = "kcs.import_stage"

    def execute(self, context: bpy.types.Context):
        scene = context.scene.KCS_scene
        stage_table = Path(scene.decomp_path) / "data" / "misc" / "kirby.066630.2.c"  # this will probably change later
        stage = parse_stage_table(*scene.import_stage.stage, stage_table)

        gfx_bank, gfx_ID = [eval(a) for a in stage["geo"]]
        col_bank, col_ID = [eval(a) for a in stage["level_block"]]

        file_gfx = Path(scene.decomp_path) / "assets" / "geo" / ("bank_%d" % gfx_bank) / ("%d" % gfx_ID)
        file_col = Path(scene.decomp_path) / "assets" / "misc" / ("bank_%d" % col_bank) / ("%d" % col_ID)

        if scene.file_format == "binary":
            # import gfx
            name = file_gfx / "geo.bin"
            if not name.exists():
                name = file_gfx / "block.bin"
            if not name.exists():
                raise PluginError(f"Could not find file {name}, geo Bank/ID does not exist")
            import_geo_bin(
                name,
                context,
                "KCS Level {}-{}-{}".format(*scene.import_stage.stage),
                Path(scene.decomp_path) / "assets" / "image",
            )
            # import collision
            name = file_col / "level.bin"
            if not name.exists():
                name = file_col / "misc.bin"
            if not name.exists():
                raise PluginError(f"Could not find file {name}, misc Bank/ID selected is not a level")
            import_col_bin(name, context, "KCS Col {}-{}-{}".format(*scene.import_stage.stage))

        else:
            raise PluginError("C importing is not supported yet")
        return {"FINISHED"}


# export an area
class KCS_Export(Operator):
    bl_label = "Export Area"
    bl_idname = "kcs.export_area"

    def execute(self, context: bpy.types.Context):
        return {"FINISHED"}


# export a gfx file
class KCS_Export_Gfx(Operator):
    bl_label = "Export Gfx"
    bl_idname = "kcs.export_gfx"

    def execute(self, context: bpy.types.Context):
        scene = context.scene.KCS_scene
        if scene.file_format == "binary":
            raise PluginError("Binary exports are not supported")
        # need a KCS object
        obj = context.selected_objects[0]
        while obj:
            if not obj.KCS_obj.KCS_obj_type == "Graphics":
                obj = obj.parent
            else:
                break
        if not obj:
            raise PluginError('Obj is not Empty with type "Graphics"')

        bank_id = scene.export_bank_id.bank_id()
        file = Path(scene.decomp_path) / "assets" / "geo" / ("bank_%d" % bank_id[0]) / ("%d" % bank_id[1])
        file.mkdir(exist_ok=True, parents=True)
        name = file / "geo"
        export_geo_c(name, obj, context)
        return {"FINISHED"}


# export a misc file
class KCS_Export_Col(Operator):
    bl_label = "Export Col"
    bl_idname = "kcs.export_col"

    def execute(self, context: bpy.types.Context):
        scene = context.scene.KCS_scene
        if scene.file_format == "binary":
            raise PluginError("Binary exports are not supported")
        # need a KCS object
        obj = context.selected_objects[0]
        while obj:
            if not obj.KCS_obj.KCS_obj_type == "Collision":
                obj = obj.parent
            else:
                break
        if not obj:
            raise PluginError('Obj is not Empty with type "Collision"')
        bank_id = scene.export_bank_id.bank_id()
        file = Path(scene.decomp_path) / "assets" / "misc" / ("bank_%d" % bank_id[0]) / ("%d" % bank_id[1])
        file.mkdir(exist_ok=True, parents=True)
        name = file / "level"
        export_col_c(name, obj, context)
        return {"FINISHED"}


# ------------------------------------------------------------------------
#    Helper Operators
# ------------------------------------------------------------------------

# these operators are added to panels to make things easier for the users
# their purpose is to aid in level creation

# add a star block object and link it to the context object
# cube has side length of 40
class KCS_Add_Block(Operator):
    bl_label = "Add Breakable Block"
    bl_idname = "kcs.add_kcsblock"

    def execute(self, context: bpy.types.Context):
        # context vars
        scale = bpy.context.scene.KCS_scene.scale
        Rt = context.object
        collection = context.object.users_collection[0]
        # get singleton instance of block data
        Block = BreakableBlockDat()
        BlockGfxDat = Block.Instance_Gfx(Block)
        BlockColDat = Block.Instance_Col(Block)
        BlockGfxObj = bpy.data.objects.new("KCS Block Gfx", BlockGfxDat)
        BlockColObj = bpy.data.objects.new("KCS Block Col", BlockColDat)

        # link parent and transform
        collection.objects.link(BlockGfxObj)
        Parent(Rt, BlockGfxObj, 0)
        BlockGfxObj.matrix_world *= scale
        BlockGfxObj.KCS_mesh.MeshType = "Graphics"

        collection.objects.link(BlockColObj)
        Parent(BlockGfxObj, BlockColObj, 0)
        BlockColObj.matrix_world *= scale
        BlockColObj.KCS_mesh.MeshType = "Collision"
        BlockColObj.KCS_mesh.ColMeshType = "Breakable"

        # setup mats
        Block.Instance_Mat_Gfx(Block, BlockGfxObj)
        Block.Instance_Mat_Col(Block, BlockColObj)

        Rt.select_set(True)
        bpy.context.view_layer.objects.active = Rt
        return {"FINISHED"}


# adds a level empty with the hierarchy setup needed to have one basic node
class KCS_Add_Level(Operator):
    bl_label = "Add Level Empty"
    bl_idname = "kcs.add_kcslevel"

    def execute(self, context: bpy.types.Context):
        collection = bpy.context.scene.collection
        Lvl = make_empty("KCS Level Rt", "PLAIN_AXES", collection)
        Lvl.KCS_obj.KCS_obj_type = "Level"
        Col = make_empty("KCS Level Col", "PLAIN_AXES", collection)
        Col.KCS_obj.KCS_obj_type = "Collision"
        Parent(Lvl, Col, 0)
        Gfx = make_empty("KCS Level Gfx", "PLAIN_AXES", collection)
        Gfx.KCS_obj.KCS_obj_type = "Graphics"
        Parent(Lvl, Gfx, 0)
        # Make Node
        PathData = bpy.data.curves.new("KCS Path Node", "CURVE")
        PathData.splines.new("POLY")
        PathData.splines[0].points.add(4)
        for i, s in enumerate(PathData.splines[0].points):
            s.co = (i - 2, 0, 0, 0)
        Node = bpy.data.objects.new("KCS Node", PathData)
        collection.objects.link(Node)
        Parent(Col, Node, 0)
        # make camera
        CamDat = bpy.data.cameras.new("KCS Node Cam")
        CamObj = bpy.data.objects.new("KCS Node Cam", CamDat)
        collection.objects.link(CamObj)
        Parent(Node, CamObj, 0)
        # Make Camera Volume
        Vol = make_empty("KCS Cam Volume", "CUBE", collection)
        Vol.KCS_obj.KCS_obj_type = "Camera Volume"
        Parent(CamObj, Vol, 0)
        Lvl.select_set(True)
        return {"FINISHED"}


# adds a node to the collision parent
class KCS_Add_Node(Operator):
    bl_label = "Add Node"
    bl_idname = "kcs.add_kcsnode"

    def execute(self, context: bpy.types.Context):
        Rt = context.object
        collection = context.object.users_collection[0]
        add_node(Rt, collection)
        return {"FINISHED"}


# adds an entity to the collision parent
class KCS_Add_Ent(Operator):
    bl_label = "Add Entity"
    bl_idname = "kcs.add_kcsent"

    def execute(self, context: bpy.types.Context):
        node = context.object.data.KCS_node
        obj = bpy.data.objects.new("Entity %d" % node.NodeNum, None)
        collection = context.object.users_collection[0]
        collection.objects.link(obj)
        obj.KCS_obj.KCS_obj_type = "Entity"
        Parent(context.object, obj, 0)
        obj.location = context.object.data.splines[0].points[0].co.xyz + context.object.location
        return {"FINISHED"}


# adds a texture to the current texture scroll
class KCS_Add_Tex(Operator):
    bl_label = "Add Texture"
    bl_idname = "kcs.add_tex"

    def execute(self, context: bpy.types.Context):
        mat = context.material
        scr = mat.KCS_tx_scroll
        scr.Textures.add()
        return {"FINISHED"}


# adds a palette to the current texture scroll
class KCS_Add_Pal(Operator):
    bl_label = "Add Palette"
    bl_idname = "kcs.add_pal"

    def execute(self, context: bpy.types.Context):
        mat = context.material
        scr = mat.KCS_tx_scroll
        scr.Palettes.add()
        return {"FINISHED"}


# ------------------------------------------------------------------------
#    Registration
# ------------------------------------------------------------------------


kcs_operators = (
    KCS_Export,
    KCS_Export_Gfx,
    KCS_Export_Col,
    KCS_Import_Stage,
    KCS_Add_Level,
    KCS_Add_Block,
    KCS_Add_Ent,
    KCS_Add_Node,
    KCS_Import_NLD_Gfx,
    KCS_Import_Col,
    KCS_Add_Tex,
    KCS_Add_Pal,
)


def kcs_operator_register():
    for cls in kcs_operators:
        register_class(cls)


def kcs_operator_unregister():
    for cls in reversed(kcs_operators):
        unregister_class(cls)

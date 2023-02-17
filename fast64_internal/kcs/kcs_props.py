# ------------------------------------------------------------------------
#    Header
# ------------------------------------------------------------------------
from __future__ import annotations

import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    FloatProperty,
    FloatVectorProperty,
    EnumProperty,
    PointerProperty,
    IntVectorProperty,
    BoolVectorProperty,
    CollectionProperty,
)
from bpy.types import PropertyGroup
from bpy.utils import register_class, unregister_class

from .kcs_data import entity_enum

# ------------------------------------------------------------------------
#    UI Callbacks
# ------------------------------------------------------------------------

# callbacks are defined in the props section, so the callback funcs
# belond here


def UpdateEnt(objprop: EntProp, context: bpy.types.Context):
    id = objprop.Entity.split(",")
    objprop.BankNum = int(id[0])


# ------------------------------------------------------------------------
#    Scene Properties
# ------------------------------------------------------------------------

# World
class StageProp(PropertyGroup):
    world: IntProperty(name="World", description="World to place level in", default=1, min=1, max=7)
    level: IntProperty(name="Level", description="Which level in selected world to overwrite", default=1, min=1, max=5)
    area: IntProperty(name="Area", description="Area", default=1, min=1, max=10)

    def draw(self, layout: bpy.types.UILayout):
        layout.prop(self, "world")
        layout.prop(self, "level")
        layout.prop(self, "area")

    @property
    def stage(self):
        return (self.world, self.level, self.area)


# generic bank / ID for various ops
class BankIndex(PropertyGroup):
    bank: IntProperty(name="Bank", description="Bank for Data", default=0, min=0, max=7)
    id: IntProperty(name="ID", description="ID for Data", default=1, min=1, max=1200)

    def draw(self, layout: bpy.types.UILayout):
        layout.prop(self, "bank")
        layout.prop(self, "id")

    def bank_id(self):
        return (self.bank, self.id)


# importing / exporting
class KCS_Scene_Props(PropertyGroup):
    scale: FloatProperty(
        name="Scale",
        description="Level Scale",
        default=100,
        min=0.0001,
    )
    decomp_path: StringProperty(
        name="Decomp Folder", description="Choose a directory:", default="", maxlen=1024, subtype="DIR_PATH"
    )
    export_stage: PointerProperty(type=StageProp, description="Stage to export area into")
    import_stage: PointerProperty(type=StageProp, description="Stage to import area into")
    export_bank_id: PointerProperty(
        type=BankIndex,
        description="Bank/Index for Non Level Data",
    )
    import_bank_id: PointerProperty(
        type=BankIndex,
        description="Bank/Index for Non Level Data",
    )
    file_format: EnumProperty(
        name="Format", description="The file format for data", items=[("binary", "binary", ""), ("C", "C", "")]
    )
    clean_up: BoolProperty(name="Clean Up", description="Post process imports to be cleaner", default=True)


# ------------------------------------------------------------------------
#    Node Properties
# ------------------------------------------------------------------------

# on a path
class NodeProp(PropertyGroup):
    entrance_location: EnumProperty(
        name="Entrance Location",
        description="Where you start on node after warp",
        default="walk start",
        items=[
            ("walk start", "walk start", ""),
            ("walk end", "walk end", ""),
            ("appear start", "appear start", ""),
            ("appear end", "appear end", ""),
        ],
    )
    entrance_action: EnumProperty(
        name="Entrance Action",
        description="Action when entering node after warp",
        default="walk",
        items=[
            ("walk", "walk", ""),
            ("stand", "stand", ""),
            ("jump up", "jump up", ""),
            ("jump forward", "jump forward", ""),
            ("climb wall up", "climb wall up", ""),
            ("climb wall down", "climb wall down", ""),
            ("climb rope up", "climb rope up", ""),
            ("climb rope down", "climb rope down", ""),
            ("walking (unk)", "walking (unk)", ""),
            ("jumping (unk)", "jumping (unk)", ""),
            ("fall from air", "fall from air", ""),
        ],
    )
    lock_forward: BoolProperty(name="Lock Forward", description="Stop Going Forward")
    lock_backward: BoolProperty(name="Lock Backward", description="Stop Going Backwards")
    enable_warp: BoolProperty(name="Enable Warp", description="Warps kirby if you walk past warp col type in this node")
    looping: BoolProperty(name="Looping", description="Used in Boss Stages")
    node_num: IntProperty(name="Node Number", description="Number of Curr Node", default=0, min=0)
    prev_node: IntProperty(name="Prev Node", description="Dest Node When Walking Back", default=1, min=0)
    next_node: IntProperty(name="Next Node", description="Dest Node When Walking Forward", default=2, min=0)
    stage_dest: PointerProperty(type=StageProp, name="Stage Dest", description="Stage destination to warp to")
    warp_node: IntProperty(name="Dest Node", description="Node of warp destination", default=1, min=0)

    @property
    def entrance_int(self):
        return (self.get("entrance_location") << 8) + self.get("entrance_action")


# camera
class CamProp(PropertyGroup):
    axis_locks: BoolVectorProperty(name="Locks", default=(1, 1, 1), description="Stops Cam From Moving", subtype="XYZ")
    pan_ahead: BoolProperty(name="Pan Ahead", description="Pans Camera in X/Z plane ahead of kirby")
    pan_vertical: BoolProperty(name="Pan Vertical", description="Pans Camera in Y axis to follow kirby")
    pan_below: BoolProperty(name="Pan Below", description="Pans Camera in Y axis to follow kirby while falling only")
    profile_view: BoolProperty(name="ProfileView", description="View Kirby From Side")
    node_num: IntProperty(name="Node Number", description="Number of Curr Node", default=1, min=1)
    follow_yaw: FloatVectorProperty(
        name="Yaw", description="The Theta Rotation from kirby to cam while following", size=2, default=(90.0, 90.0)
    )
    follow_pitch: FloatVectorProperty(
        name="Pitch", description="The Phi Rotation from kirby to cam while following", size=2, default=(120.0, 120.0)
    )
    follow_radius: FloatVectorProperty(
        name="Radius", description="How far the camera is from kirby while following", size=2, default=(600.0, 600.0)
    )
    clip_planes: FloatVectorProperty(
        name="Near/Far Clip", description="Camera Clip Planes", size=2, default=(128.0, 12800.0)
    )
    focus_location: FloatVectorProperty(
        name="Focus position", description="9999 to not use", size=3, default=(9999.0, 9999.0, 9999.0), max=9999.0
    )
    cam_bounds_x: FloatVectorProperty(
        name="X bounds",
        description="Follows Kirby in this range, Locks at Bound otherwise",
        max=9999.0,
        min=-9999.0,
        default=(-9999.0, 9999.0),
        size=2,
    )
    cam_bounds_y: FloatVectorProperty(
        name="Y bounds",
        size=2,
        description="Follows Kirby in this range, Locks at Bound otherwise",
        max=9999.0,
        min=-9999.0,
        default=(-9999.0, 9999.0),
    )
    cam_bounds_z: FloatVectorProperty(
        name="Z bounds",
        description="Follows Kirby in this range, Locks at Bound otherwise",
        size=2,
        default=(-9999.0, 9999.0),
        max=9999.0,
        min=-9999.0,
    )
    cam_bounds_pitch: FloatVectorProperty(
        name="Pitch bounds",
        description="Follows Kirby in this range, Locks at Bound otherwise",
        size=2,
        default=(0.0, 359.0),
        max=359.0,
        min=0.0,
    )
    cam_bounds_yaw: FloatVectorProperty(
        name="Yaw bounds",
        description="Follows Kirby in this range, Locks at Bound otherwise",
        size=2,
        default=(10, 170),
        max=359.0,
        min=0.0,
    )


# ------------------------------------------------------------------------
#    Collision Properties
# ------------------------------------------------------------------------

# col tri material
class ColProp(PropertyGroup):
    norm_type: IntProperty(name="Norm Type", description="Bitwise Normal Type", default=1, min=0)
    col_type: IntProperty(name="Col Type", description="Collision Type", default=0, min=0)
    col_param: IntProperty(
        name="Col Param/Break Condition", description="Collision Param for certain ColTypes", default=0
    )
    warp_num: IntProperty(name="WarpNum", description="Number of Node warp is on", min=1)

    @property
    def params(self):
        return self.norm_type, self.col_type, self.col_param, self.warp_num


# col obj
class MeshProp(PropertyGroup):
    mesh_type: EnumProperty(
        name="Mesh Type", items=[("None", "None", ""), ("Collision", "Collision", ""), ("Graphics", "Graphics", "")]
    )
    col_mesh_type: EnumProperty(
        name="Type of Mesh",
        description="Type of Col Mesh",
        items=[
            ("Default", "Default", ""),
            ("Water", "Water", ""),
            ("Breakable", "Breakable", ""),
        ],
        default="Default",
    )


# ------------------------------------------------------------------------
#    Object Properties
# ------------------------------------------------------------------------

# obj classification
class ObjProp(PropertyGroup):
    KCS_obj_type: EnumProperty(
        name="Object Type",
        items=[
            ("None", "None", ""),
            ("Level", "Level", ""),
            ("Graphics", "Graphics", ""),
            ("Collision", "Collision", ""),
            ("Entity", "Entity", ""),
            ("Camera Volume", "Camera Volume", ""),
        ],
    )


# entities
class EntProp(PropertyGroup):
    entity: EnumProperty(
        name="Entity ID",
        description="Name of Entity",
        items=entity_enum,
        update=UpdateEnt,
    )
    bank_num: IntProperty(name="BankNum", description="The bank the entity is from", default=0, min=0)
    index_num: IntProperty(name="IndexNum", description="The index the entity is from", default=0, min=0)
    action: IntProperty(name="Action", description="The action of this specific entity", default=0, min=0)
    flags: IntProperty(name="Flags", description="Flags for spawning or other conditions", default=0, min=0, max=255)
    respawn: IntProperty(name="Respawn", description="Respawn after killing", default=0)
    eeprom_data: IntProperty(name="Eep", description="An eep flag to check, if true spawn", default=0, min=0)


# level base object properties (used for exporting/ID on import)
class LvlProp(PropertyGroup):
    Skybox_ID: IntProperty(name="Skybox_ID", description="ID of level's skybox", default=13, min=0, max=72)

    Music_ID: IntProperty(name="Music_ID", description="ID of level's music", default=0, min=0, max=64)


# ------------------------------------------------------------------------
#    Graphics Properties
# ------------------------------------------------------------------------

# a minimalist texture prop. Only requires a source
class TextureProp(PropertyGroup):
    Bank: IntProperty(name="Bank", description="Bank of texture", default=0, min=0, max=7)
    Index: IntProperty(name="Index", description="Index of texture", default=1, min=1, max=1500)

    def draw(self, layout: bpy.types.UILayout):
        box = layout.box()
        row = box.row()
        row.prop(self, "Bank")
        row.prop(self, "Index")


class TexScrollProp(PropertyGroup):
    Textures: CollectionProperty(name="Textures", type=TextureProp)
    Palettes: CollectionProperty(name="Palettes", type=TextureProp)

    def add_texture(self, tex):
        self.Textures.add()
        tex = self.Textures[-1]
        tex.Source = tex

    def add_palette(self, tex):
        self.Palettes.add()
        tex = self.Palettes[-1]
        tex.Source = tex


# ------------------------------------------------------------------------
#    Registration
# ------------------------------------------------------------------------


kcs_properties = (
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
)


def kcs_property_register():
    for cls in kcs_properties:
        register_class(cls)

    bpy.types.Scene.KCS_scene = PointerProperty(type=KCS_Scene_Props)
    bpy.types.Curve.KCS_node = PointerProperty(type=NodeProp)
    bpy.types.Camera.KCS_cam = PointerProperty(type=CamProp)
    bpy.types.Object.KCS_lvl = PointerProperty(type=LvlProp)
    bpy.types.Object.KCS_ent = PointerProperty(type=EntProp)
    bpy.types.Object.KCS_obj = PointerProperty(type=ObjProp)
    bpy.types.Object.KCS_mesh = PointerProperty(type=MeshProp)
    bpy.types.Material.KCS_col = PointerProperty(type=ColProp)
    bpy.types.Material.KCS_tx_scroll = PointerProperty(type=TexScrollProp)


def kcs_property_unregister():
    for cls in reversed(kcs_properties):
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

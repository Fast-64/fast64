# ------------------------------------------------------------------------
#    Header
# ------------------------------------------------------------------------

# this is sort of the controlling file because it has all
# the panels and UI which people will be interacting with

import bpy
from bpy.utils import register_class, unregister_class
from bpy.types import (
    Panel,
    Menu,
)

from pathlib import Path

from .kcs_props import *
from .kcs_operators import *

# ------------------------------------------------------------------------
#    Panels
# ------------------------------------------------------------------------

# viewport details panel that sets global IO settings
class KCS_PROP_PT_Panel(Panel):
    bl_label = "KCS Props"
    bl_idname = "KCS_PROP_PT_Panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Kirby64"
    bl_context = "objectmode"

    @classmethod
    def poll(self, context: bpy.types.Context):
        if GameCheck(context):
            return None
        return context.scene is not None

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        KCS_scene = context.scene.KCS_scene
        layout.prop(KCS_scene, "scale")
        layout.prop(KCS_scene, "decomp_path")
        layout.prop(KCS_scene, "file_format")
        layout.label(text="Import Options")
        row = layout.row()
        row.prop(KCS_scene, "clean_up")
        layout.operator("kcs.add_kcslevel")


# viewport panel that shows import/export operators
class KCS_IO_PT_Panel(Panel):
    bl_label = "KCS I/O"
    bl_idname = "KCS_IO_PT_Panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Kirby64"
    bl_context = "objectmode"

    @classmethod
    def poll(self, context: bpy.types.Context):
        if GameCheck(context):
            return None
        return context.scene is not None

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        scene = context.scene
        KCS_scene = scene.KCS_scene
        layout.label(text="Export Selected Level")
        KCS_scene.export_stage.draw(layout)
        layout.operator("kcs.export_area")
        layout.label(text="Export Selected Geo")
        KCS_scene.export_bank_id.draw(layout)
        layout.operator("kcs.export_gfx")
        layout.operator("kcs.export_col")
        layout.separator()
        layout.label(text="Import Area")
        KCS_scene.import_stage.draw(layout)
        layout.operator("kcs.import_stage")
        layout.separator()
        layout.label(text="Import Bank Data")
        KCS_scene.import_bank_id.draw(layout)
        layout.operator("kcs.import_nld_gfx")
        layout.operator("kcs.import_col")


# texture scrol panel that goes below f3d material settings
class SCROLL_PT_Panel(Panel):
    bl_label = "KCS Tx Scroll Settings"
    bl_idname = "SCROLL_PT_Panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(self, context: bpy.types.Context):
        if context.object.type != "MESH" or GameCheck(context):
            return None
        return context.material is not None

    def draw(self, context: bpy.types.Context):
        KCSmesh = context.object.KCS_mesh
        if KCSmesh.mesh_type == "Graphics":
            layout = self.layout
            mat = context.material
            scroll = mat.KCS_tx_scroll
            box = layout.box()
            box.label(text="KCS Texture Scroll Properties")
            box_tex = box.box()
            box_tex.label(text="textures")
            box_tex.operator("kcs.add_tex")
            [t.draw(box_tex) for t in scroll.Textures]
            box_tex = box.box()
            box_tex.label(text="palettes")
            box_tex.operator("kcs.add_pal")
            [t.draw(box_tex) for t in scroll.Palettes]


# collision tri settings per material
class COL_PT_Panel(Panel):
    bl_label = "KCS Col Settings"
    bl_idname = "COL_PT_Panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(self, context: bpy.types.Context):
        if context.object.type != "MESH" or GameCheck(context):
            return None
        return context.material is not None

    def draw(self, context: bpy.types.Context):
        KCSmesh = context.object.KCS_mesh
        if KCSmesh.mesh_type == "Collision":
            layout = self.layout
            mat = context.material
            col = mat.KCS_col
            box = layout.box()
            box.label(text="KCS Collision Type Info")
            box.prop(col, "NormType")
            if KCSmesh.col_mesh_type == "Breakable":
                box.label(text="Collision Type must be brekaable (9)")
            box.prop(col, "ColType")
            box.prop(col, "ColParam")
            box.prop(col, "WarpNum")


# path node settings, goes on curve/path
class NODE_PT_Panel(Panel):
    bl_label = "KCS Node Settings"
    bl_idname = "NODE_PT_Panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(self, context: bpy.types.Context):
        if context.object.type != "CURVE" or GameCheck(context):
            return None
        return context.object.data is not None

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        curve = context.object.data
        node_props = curve.KCS_node
        box = layout.box()
        box.label(text="KCS Node Path/Container")

        b = box.box()
        b.label(text="Create Entity Linked to this Node")
        b.operator("kcs.add_kcsent")

        box.separator()
        row = box.row()
        row.prop(node_props, "node_num")
        row.prop(node_props, "enable_warp")

        if node_props.enable_warp:
            new_box = box.box()
            row = new_box.box()
            row.label(text="Warp Settings")
            col = row.column()
            col.alignment = "LEFT"
            col.prop(node_props, "entrance_location")
            col.prop(node_props, "entrance_action")

            row = box.row()
            node_props.stage_dest.draw(row.column())
            row.prop(node_props, "warp_node")

        box.separator()
        row = box.row()
        row.prop(node_props, "lock_forward")
        row.prop(node_props, "lock_backward")
        row.prop(node_props, "looping")

        box.separator()
        row = box.row()
        row.prop(node_props, "next_node")
        row.prop(node_props, "prev_node")


# camera settings, goes on camera object
class CAM_PT_Panel(Panel):
    bl_label = "KCS Cam Settings"
    bl_idname = "CAM_PT_Panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(self, context: bpy.types.Context):
        if context.object.type != "CAMERA" or GameCheck(context):
            return None
        return context.object.data is not None

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        camera = context.object.data
        camera_prop = camera.KCS_cam
        box = layout.box()

        new_box = box.box()
        row = new_box.row()
        new_box.label(text="Locks will make camera stay inside cam bounds while following kirby.")
        row.prop(camera_prop, "profile_view")
        row.prop(camera_prop, "axis_locks")
        if any(camera_prop.axis_locks):
            new_box.label(text="Bounds only used while axis is locked.")
        if not camera_prop.axis_locks[0]:
            new_box.prop(camera_prop, "cam_bounds_x")
        if not camera_prop.axis_locks[1]:
            new_box.prop(camera_prop, "cam_bounds_y")
        if not camera_prop.axis_locks[2]:
            new_box.prop(camera_prop, "cam_bounds_z")
        new_box.label(text="Yaw and pitch bounds always in affect unless camera is fully locked.")
        new_box.prop(camera_prop, "cam_bounds_pitch")
        new_box.prop(camera_prop, "cam_bounds_yaw")

        box.label(text="Pans begin when camera hits bounds.")
        row = box.row()
        row.prop(camera_prop, "pan_ahead")
        row.prop(camera_prop, "pan_vertical")
        row.prop(camera_prop, "pan_below")

        box.label(text="Camera position while following kirby.")
        grid = box.column_flow()
        grid.prop(camera_prop, "follow_yaw")
        grid.prop(camera_prop, "follow_pitch")
        grid.prop(camera_prop, "follow_radius")

        box.prop(camera_prop, "clip_planes")
        box.label(text="Position to focus camera. 9999 focuses on kirby.")
        box.prop(camera_prop, "focus_location")


# generic object settings. Has switch(haha) so it can choose the correct
# display based on the type of object it is
class OBJ_PT_Panel(Panel):
    bl_label = "KCS Obj Panel"
    bl_idname = "OBJ_PT_Panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(self, context: bpy.types.Context):
        if context.object.type != "EMPTY" or GameCheck(context):
            return None
        return context.object is not None

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        obj = context.object
        objprop = obj.KCS_obj
        layout.prop(context.scene, "gameEditorMode")
        box = self.layout.box().column()
        box.box().label(text="KCS Object Handler")
        box.prop(objprop, "KCS_obj_type")
        if objprop.KCS_obj_type == "Entity":
            draw_Ent_empty(box, context)
        elif objprop.KCS_obj_type == "Level":
            draw_Lvl_empty(box, context)
        elif objprop.KCS_obj_type == "Graphics":
            draw_Gfx_empty(box, context)
        elif objprop.KCS_obj_type == "Collision":
            draw_Col_empty(box, context)
        elif objprop.KCS_obj_type == "Camera Volume":
            box = box.box()
            box.label(text="KCS Camera Bounds Container")
            box.label(text="Make this object the child of a camera node.")
            box.label(text="This object should not be rotated.")
            box.label(text="The volume contained by this object represents the x/y/z bounds of camera movement.")
        else:
            box.separator()
            box = box.box()
            box.label(text="This obj will be ignored")


# mesh settings. mesh can be col or gfx. there is no overlap like in sm64
class MESH_PT_Panel(Panel):
    bl_label = "KCS Mesh Panel"
    bl_idname = "MESH_PT_Panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(self, context: bpy.types.Context):
        if context.object.type != "MESH" or GameCheck(context):
            return None
        return context.object is not None

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        obj = context.object
        meshprop = obj.KCS_mesh
        layout.prop(context.scene, "gameEditorMode")
        box = self.layout.box().column()
        box.prop(meshprop, "mesh_type")
        if meshprop.mesh_type == "Gfx":
            draw_Gfx(box, context)
        elif meshprop.mesh_type == "Collision":
            draw_Col(box, context)
        else:
            draw_Gfx(box, context)


# ------------------------------------------------------------------------
#    Conditional draws
# ------------------------------------------------------------------------


def draw_Ent_empty(box: bpy.types.UILayout, context: bpy.types.Context):
    obj = context.object
    entprop = obj.KCS_ent
    box.separator()
    box = box.box()
    box.label(text="KCS Entity Properties")
    box.prop(entprop, "Entity")
    box.separator()

    row = box.row()
    row.prop(entprop, "BankNum")
    row.prop(entprop, "IndexNum")
    box.prop(entprop, "Action")
    box.separator()

    row = box.row()
    row.prop(entprop, "Flags")
    row.prop(entprop, "Respawn")
    row.prop(entprop, "Eep")


def draw_Lvl_empty(box: bpy.types.UILayout, context: bpy.types.Context):
    obj = context.object
    lvlprop = obj.KCS_lvl
    box.separator()
    box = box.box()
    box.label(text="KCS Level Properties")
    box.prop(lvlprop, "Skybox_ID")
    box.prop(lvlprop, "Music_ID")


def draw_Gfx_empty(box: bpy.types.UILayout, context: bpy.types.Context):
    box = box.box()
    box.label(text="KCS Level Gfx Container")
    box.label(text="Make this object the child of the level empty.")
    box.label(text="Make all gfx meshes children of this empty.")
    box.operator("kcs.add_kcsblock")


def draw_Col_empty(box: bpy.types.UILayout, context: bpy.types.Context):
    box = box.box()
    box.label(text="KCS Level Col Container")
    box.label(text="Make this object the child of the level empty.")
    box.label(text="Make all Col meshes children of this empty.")
    box.operator("kcs.add_kcsnode")


def draw_Col(box: bpy.types.UILayout, context: bpy.types.Context):
    obj = context.object
    colprop = obj.KCS_mesh
    box.separator()
    box = box.box()
    box.label(text="KCS Col Properties")
    row = box.row()
    row.prop(colprop, "col_mesh_type", expand=True)
    if colprop.mesh_type == "Default":
        box.label(text="Make mesh a child of level collision empty.")
        box.label(text="Use materials to select different collision types.")
    elif colprop.mesh_type == "Water":
        box.label(text="Make mesh a child of level collision empty.")
        box.label(text="Water is formed by the inner surface of planes and has no collision types.")
    elif colprop.mesh_type == "Breakable":
        box.label(text="Make mesh a child of linked graphics mesh.")
        box.label(text="Must use only one material with collision type breakable.")


def draw_Gfx(box: bpy.types.UILayout, context: bpy.types.Context):
    box = box.box()
    box.label(text="KCS Gfx Mesh")
    box.label(text="Make mesh a child of level graphics empty, or child of another gfx mesh.")
    box.label(text="Will act as empty transform for child meshes.")


# check the proper game enum is selected
# return True (aka exit) when not KCS
def GameCheck(context: bpy.types.Context):
    if context.scene.gameEditorMode != "KCS":
        return True
    return None


# ------------------------------------------------------------------------
#    Registration
# ------------------------------------------------------------------------


kcs_panel_classes = (
    KCS_PROP_PT_Panel,
    KCS_IO_PT_Panel,
    OBJ_PT_Panel,
    MESH_PT_Panel,
    NODE_PT_Panel,
    CAM_PT_Panel,
    COL_PT_Panel,
    SCROLL_PT_Panel,
)


def kcs_panel_register():
    for cls in kcs_panel_classes:
        register_class(cls)


def kcs_panel_unregister():
    for cls in reversed(kcs_panel_classes):
        unregister_class(cls)

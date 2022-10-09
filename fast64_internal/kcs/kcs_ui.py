# ------------------------------------------------------------------------
#    Header
# ------------------------------------------------------------------------

#this is sort of the controlling file because it has all
#the panels and UI which people will be interacting with

import bpy
from bpy.types import (Panel,
                       Menu,
                       )

from pathlib import Path

from .kcs_gfx import *
from .kcs_col import *
from .kcs_utils import *
from .kcs_props import *
from .kcs_operators import *

# ------------------------------------------------------------------------
#    Panels
# ------------------------------------------------------------------------

#viewport details panel that sets global IO settings
class KCS_PROP_PT_Panel(Panel):
    bl_label = "KCS Props"
    bl_idname = "KCS_PROP_PT_Panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Kirby64"
    bl_context = "objectmode"
    @classmethod
    def poll(self,context):
        if GameCheck(context): return None
        return context.scene is not None
    def draw(self,context):
        layout = self.layout
        KCS_scene = context.scene.KCS_scene
        layout.prop(KCS_scene, "Scale")
        layout.prop(KCS_scene, "Decomp_path")
        layout.prop(KCS_scene, "Format")
        layout.label(text = "Import Options")
        row = layout.row()
        row.prop(KCS_scene, "CleanUp")
#        row.prop(KCS_scene, "IgnoreAdHoc")
        layout.operator("kcs.add_kcslevel")

#viewport panel that shows import/export operators
class KCS_IO_PT_Panel(Panel):
    bl_label = "KCS I/O"
    bl_idname = "KCS_IO_PT_Panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Kirby64"
    bl_context = "objectmode"
    @classmethod
    def poll(self,context):
        if GameCheck(context): return None
        return context.scene is not None
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        KCS_scene = scene.KCS_scene
        layout.label(text = "Export Selected Level")
        layout.operator("kcs.export_area")
        layout.label(text = "Export Selected Geo")
        layout.operator("kcs.export_gfx")
        layout.separator()
        layout.label(text="Import Area")
        layout.prop(KCS_scene, "ImpWorld")
        layout.prop(KCS_scene, "ImpLevel")
        layout.prop(KCS_scene, "ImpArea")
        layout.operator("kcs.import_stage")
        layout.separator()
        layout.label(text = "Import Bank Data")
        layout.prop(KCS_scene, "ImpBank")
        layout.prop(KCS_scene, "ImpID")
        layout.operator("kcs.import_nld_gfx")
        layout.operator("kcs.import_col")

#texture scrol panel that goes below f3d material settings
class SCROLL_PT_Panel(Panel):
    bl_label = "KCS Tx Scroll Settings"
    bl_idname = "SCROLL_PT_Panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {'HIDE_HEADER'}
    @classmethod
    def poll(self,context):
        if context.object.type != "MESH" or GameCheck(context):
            return None
        return context.material is not None
    def draw(self, context):
        KCSmesh = context.object.KCS_mesh
        if KCSmesh.MeshType == 'Graphics':
            layout = self.layout
            mat = context.material
            scroll = mat.KCS_tx_scroll
            box = layout.box()
            box.label(text = "KCS Texture Scroll Properties")
            box_tex = box.box()
            box_tex.label(text = "textures")
            box_tex.operator("kcs.add_tex")
            [t.draw(box_tex) for t in scroll.Textures]
            box_tex = box.box()
            box_tex.label(text = "palettes")
            box_tex.operator("kcs.add_pal")
            [t.draw(box_tex) for t in scroll.Palettes]

#collision tri settings per material
class COL_PT_Panel(Panel):
    bl_label = "KCS Col Settings"
    bl_idname = "COL_PT_Panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {'HIDE_HEADER'}
    @classmethod
    def poll(self,context):
        if context.object.type != "MESH" or GameCheck(context):
            return None
        return context.material is not None

    def draw(self, context):
        KCSmesh = context.object.KCS_mesh
        if KCSmesh.MeshType == 'Collision':
            layout = self.layout
            mat = context.material
            col = mat.KCS_col
            box = layout.box()
            box.label(text = "KCS Collision Type Info")
            box.prop(col,'NormType')
            if KCSmesh.ColMeshType == 'Breakable':
                box.label(text = 'Collision Type must be brekaable (9)')
            box.prop(col,'ColType')
            box.prop(col,'ColParam')
            box.prop(col,'WarpNum')

#path node settings, goes on curve/path
class NODE_PT_Panel(Panel):
    bl_label = "KCS Node Settings"
    bl_idname = "NODE_PT_Panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {'HIDE_HEADER'}
    @classmethod
    def poll(self,context):
        if context.object.type != "CURVE" or GameCheck(context):
            return None
        return context.object.data is not None

    def draw(self, context):
        layout = self.layout
        obj = context.object.data
        nodeprop = obj.KCS_node
        box = layout.box()        
        box.label(text = "KCS Node Path/Container")
        
        b = box.box()
        b.label(text = "Create Entity Linked to this Node")
        b.operator("kcs.add_kcsent")
        
        box.separator()
        row = box.row()
        row.prop(nodeprop, "NodeNum")
        row.prop(nodeprop, "EnWarp")
        
        row = box.row()
        row.label(text = "Warp Settings")
        col = row.column()
        col.alignment = 'LEFT'
        col.prop(nodeprop,"EntranceLocation")
        col.prop(nodeprop,"EntranceAction")
        
        row = box.row()
        row.prop(nodeprop, "Warp")
        row.prop(nodeprop, "WarpNode")
        
        box.separator()
        row = box.row()
        row.prop(nodeprop, "LockForward")
        row.prop(nodeprop, "LockBackward")
        row.prop(nodeprop, "Looping")
        
        box.separator()
        row = box.row()
        row.prop(nodeprop, "NextNode")
        row.prop(nodeprop, "PrevNode")

#camera settings, goes on camera object
class CAM_PT_Panel(Panel):
    bl_label = "KCS Cam Settings"
    bl_idname = "CAM_PT_Panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {'HIDE_HEADER'}
    @classmethod
    def poll(self,context):
        if context.object.type != "CAMERA" or GameCheck(context):
            return None
        return context.object.data is not None

    def draw(self, context):
        layout = self.layout
        obj = context.object.data
        camprop = obj.KCS_cam
        box = layout.box()
        box.label(text="Locks will make camera stay inside cam bounds while following kirby.")
        row = box.row()
        row.prop(camprop, "ProfileView")
        row.prop(camprop,"AxisLocks")
        box.separator()
        box.label(text="Pans begin when camera hits bounds.")
        row = box.row()
        row.prop(camprop,"PanH")
        row.prop(camprop,"PanUpDown")
        row.prop(camprop,"PanDown")
        box.separator()
        box.label(text = "Camera position while following kirby.")
        grid = box.column_flow()
        grid.prop(camprop,"Yaw")
        grid.prop(camprop,"Pitch")
        grid.prop(camprop,"Radius")
        grid.prop(camprop,"Clips")
        box.separator()
        box.label(text = "Position to focus camera. 9999 focuses on kirby.")
        box.separator()
        row = box.row()
        row.prop(camprop,'Foc')
        box.label(text="Camera Bound Pairs Determined by Camera Volume.")
        box.label(text="Bounds only used while axis is locked.")
        box.prop(camprop,'CamPitchBound')
        box.prop(camprop,'CamYawBound')

#generic object settings. Has switch(haha) so it can choose the correct
#display based on the type of object it is
class OBJ_PT_Panel(Panel):
    bl_label = "KCS Obj Panel"
    bl_idname = "OBJ_PT_Panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(self,context):
        if context.object.type != "EMPTY" or GameCheck(context):
            return None
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        obj = context.object
        objprop = obj.KCS_obj
        layout.prop(context.scene,"gameEditorMode")
        box = self.layout.box().column()
        box.box().label(text= 'KCS Object Handler')
        box.prop(objprop,"KCS_obj_type")
        if objprop.KCS_obj_type == "Entity":
            draw_Ent_empty(box,context)
        elif objprop.KCS_obj_type == "Level":
            draw_Lvl_empty(box,context)
        elif objprop.KCS_obj_type == "Graphics":
            draw_Gfx_empty(box,context)
        elif objprop.KCS_obj_type == "Collision":
            draw_Col_empty(box,context)
        elif objprop.KCS_obj_type == "Camera Volume":
            box = box.box()
            box.label(text = 'KCS Camera Bounds Container')
            box.label(text = 'Make this object the child of a camera node.')
            box.label(text = "This object should not be rotated.")
            box.label(text = "The volume contained by this object represents the x/y/z bounds of camera movement.")
        else:
            box.separator()
            box = box.box()
            box.label(text = "This obj will be ignored")

#mesh settings. mesh can be col or gfx. there is no overlap like in sm64
class MESH_PT_Panel(Panel):
    bl_label = "KCS Mesh Panel"
    bl_idname = "MESH_PT_Panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(self,context):
        if context.object.type != "MESH" or GameCheck(context):
            return None
        return context.object is not None
    def draw(self, context):
        layout = self.layout
        obj = context.object
        meshprop = obj.KCS_mesh
        layout.prop(context.scene,"gameEditorMode")
        box = self.layout.box().column()
        box.prop(meshprop,"MeshType")
        if meshprop.MeshType == "Gfx":
            draw_Gfx(box,context)
        elif meshprop.MeshType == "Collision":
            draw_Col(box,context)
        else:
            draw_Gfx(box,context)

# ------------------------------------------------------------------------
#    Conditional draws
# ------------------------------------------------------------------------

def draw_Ent_empty(box,context):
    obj = context.object
    entprop = obj.KCS_ent
    box.separator()
    box = box.box()
    box.label(text = 'KCS Entity Properties')
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

def draw_Lvl_empty(box,context):
    obj = context.object
    lvlprop = obj.KCS_lvl
    box.separator()
    box = box.box()
    box.label(text = 'KCS Level Properties')
    box.prop(lvlprop, "World")
    box.prop(lvlprop, "Level")
    box.prop(lvlprop, "Area")
    box.prop(lvlprop, "Skybox_ID")
    box.prop(lvlprop, "Music_ID")

def draw_Gfx_empty(box,context):
    box = box.box()
    box.label(text = 'KCS Level Gfx Container')
    box.label(text = 'Make this object the child of the level empty.')
    box.label(text = "Make all gfx meshes children of this empty.")
    box.operator("kcs.add_kcsblock")

def draw_Col_empty(box,context):
    box = box.box()
    box.label(text = 'KCS Level Col Container')
    box.label(text = 'Make this object the child of the level empty.')
    box.label(text = "Make all Col meshes children of this empty.")
    box.operator("kcs.add_kcsnode")

def draw_Col(box,context):
    obj = context.object
    colprop = obj.KCS_mesh
    box.separator()
    box = box.box()
    box.label(text = 'KCS Col Properties')
    row = box.row()
    row.prop(colprop, "ColMeshType",expand=True)
    if colprop.MeshType=="Default":
        box.label(text = "Make mesh a child of level collision empty.")
        box.label(text = "Use materials to select different collision types.")
    elif colprop.MeshType=="Water":
        box.label(text = "Make mesh a child of level collision empty.")
        box.label(text = "Water is formed by the inner surface of planes and has no collision types.")
    elif colprop.MeshType=="Breakable":
        box.label(text = "Make mesh a child of linked graphics mesh.")
        box.label(text = "Must use only one material with collision type breakable.")

def draw_Gfx(box,context):
    box = box.box()
    box.label(text = 'KCS Gfx Mesh')
    box.label(text = 'Make mesh a child of level graphics empty, or child of another gfx mesh.')

#check the proper game enum is selected
#return True (aka exit) when not KCS
def GameCheck(context):
    if context.scene.gameEditorMode != "KCS":
        return True
    return None
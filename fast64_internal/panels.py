
import bpy
from .fast64_internal import *

class SM64_Panel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SM64'

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == 'SM64'

class OOT_Panel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'OOT'

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == 'OOT'

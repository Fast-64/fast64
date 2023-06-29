import bpy
from bpy.props import IntProperty, StringProperty, PointerProperty

from .ActionData import *

class ActionListProps(bpy.types.PropertyGroup):
    actor_id: IntProperty(name = 'Actor ID',
        description = 'Cutscene actor ID. Use -1 for Link. Not the same as actor number.',
        default=-1, min=-1)

class ActionPointProps(bpy.types.PropertyGroup):
    start_frame: IntProperty(name = 'Start Frame', 
        description = 'Key point start frame within cutscene',
        default=0, min=0)
    action_id: StringProperty(name = 'Action ID', default='0x0001',
        description = 'Actor action. Meaning is unique for each different actor.')

def CheckGetActionList(op, context):
    obj = context.view_layer.objects.active
    if IsActionPoint(obj):
        obj = obj.parent
    if not IsActionList(obj):
        op.report({'WARNING'}, 'Select an action list or action point.')
        return None
    return obj    

class ZCAMEDIT_OT_add_action_point(bpy.types.Operator):
    '''Add a point to a Link or actor action list'''
    bl_idname = 'zcamedit.add_action_point'
    bl_label = 'Add point to current action'

    def execute(self, context):
        al_object = CheckGetActionList(self, context)
        if not al_object:
            return {'CANCELLED'}
        CreateDefaultActionPoint(context, al_object, True)
        return {'FINISHED'}

class ZCAMEDIT_OT_create_action_preview(bpy.types.Operator):
    '''Create a preview empty object for a Link or actor action list'''
    bl_idname = 'zcamedit.create_action_preview'
    bl_label = 'Create preview object for action'

    def execute(self, context):
        al_object = CheckGetActionList(self, context)
        if not al_object:
            return {'CANCELLED'}
        CreateOrInitPreview(context, al_object.parent, al_object.zc_alist.actor_id, True)
        return {'FINISHED'}

class ZCAMEDIT_PT_action_controls_panel(bpy.types.Panel):
    bl_label = 'zcamedit Action Controls'
    bl_idname = 'ZCAMEDIT_PT_action_controls_panel'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'
    bl_options = {'HIDE_HEADER'}
    
    def draw(self, context):
        layout = self.layout
        obj = context.view_layer.objects.active
        if IsActionPoint(obj):
            r = layout.row()
            r.label(text = 'Action point:')
            r.prop(obj.zc_apoint, 'start_frame')
            r.prop(obj.zc_apoint, 'action_id')
            obj = obj.parent
        if IsActionList(obj):
            r = layout.row()
            r.label(text = 'Action list:')
            r.prop(obj.zc_alist, 'actor_id')
            layout.operator('zcamedit.add_action_point')
            layout.operator('zcamedit.create_action_preview')
        if IsPreview(obj):
            r = layout.row()
            r.label(text = 'Preview:')
            r.prop(obj.zc_alist, 'actor_id')
        

def ActionControls_register():
    bpy.utils.register_class(ZCAMEDIT_OT_add_action_point)
    bpy.utils.register_class(ZCAMEDIT_OT_create_action_preview)
    bpy.utils.register_class(ZCAMEDIT_PT_action_controls_panel)
    bpy.utils.register_class(ActionListProps)
    bpy.utils.register_class(ActionPointProps)
    bpy.types.Object.zc_alist = PointerProperty(type=ActionListProps)
    bpy.types.Object.zc_apoint = PointerProperty(type=ActionPointProps)
    
def ActionControls_unregister():
    del bpy.types.Object.zc_apoint
    del bpy.types.Object.zc_alist
    bpy.utils.unregister_class(ActionPointProps)
    bpy.utils.unregister_class(ActionListProps)
    bpy.utils.unregister_class(ZCAMEDIT_PT_action_controls_panel)
    bpy.utils.unregister_class(ZCAMEDIT_OT_create_action_preview)
    bpy.utils.unregister_class(ZCAMEDIT_OT_add_action_point)
    

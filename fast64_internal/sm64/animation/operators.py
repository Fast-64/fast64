from typing import TYPE_CHECKING

import bpy
from bpy.utils import register_class, unregister_class
from bpy.types import Context, Scene, Action
from bpy.props import EnumProperty, StringProperty, IntProperty
from bpy.app.handlers import persistent

from ...operators import OperatorBase, SearchEnumOperatorBase
from ...utility import copyPropertyGroup
from ...utility_anim import get_action

from .importing import import_animations, get_enum_from_import_preset
from .exporting import export_animation, export_animation_table
from .utility import (
    animation_operator_checks,
    check_for_headers_in_table,
    get_action_props,
    get_active_diff_slot,
    get_anim_obj,
    get_scene_anim_props,
    get_anim_props,
    get_anim_actor_name,
)
from .constants import enum_anim_tables, enum_animated_behaviours

if TYPE_CHECKING:
    from .properties import SM64_AnimProperties, SM64_AnimHeaderProperties


@persistent
def emulate_no_loop(scene: Scene):
    if scene.gameEditorMode != "SM64":
        return
    anim_props: SM64_AnimProperties = scene.fast64.sm64.animation
    played_action: Action = anim_props.played_action
    if not played_action:
        return
    if not bpy.context.screen.is_animation_playing or anim_props.played_header >= len(
        get_action_props(played_action).headers
    ):
        anim_props.played_action = None
        return

    frame = scene.frame_current
    header_props = get_action_props(played_action).headers[anim_props.played_header]
    _start, loop_start, end = (
        anim_props.played_cached_start,
        anim_props.played_cached_loop_start,
        anim_props.played_cached_loop_end,
    )
    if header_props.backwards:
        if frame < loop_start:
            if header_props.no_loop:
                scene.frame_set(loop_start)
            else:
                scene.frame_set(end - 1)
    elif frame >= end:
        if header_props.no_loop:
            scene.frame_set(end - 1)
        else:
            scene.frame_set(loop_start)


class SM64_PreviewAnim(OperatorBase):
    bl_idname = "scene.sm64_preview_animation"
    bl_label = "Preview Animation"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    context_mode = "OBJECT"
    icon = "PLAY"

    played_header: IntProperty(name="Header", min=0, default=0)
    played_action: StringProperty(name="Action")

    def execute_operator(self, context):
        animation_operator_checks(context)
        played_action = get_action(self.played_action)
        scene = context.scene
        anim_props = scene.fast64.sm64.animation
        action_props = get_action_props(played_action)

        context.object.animation_data.action = played_action
        if bpy.app.version >= (5, 0, 0):
            context.object.animation_data.action_slot = action_props.get_slot(played_action)

        if self.played_header >= len(action_props.headers):
            raise ValueError("Invalid Header Index")
        header_props: SM64_AnimHeaderProperties = action_props.headers[self.played_header]
        start_frame, loop_start, end = header_props.get_loop_points(played_action)
        scene.frame_set(start_frame)
        scene.render.fps = 30

        if bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()  # in case it was already playing, stop it
        bpy.ops.screen.animation_play()

        anim_props.played_header = self.played_header
        anim_props.played_action = played_action
        anim_props.played_cached_start = start_frame
        anim_props.played_cached_loop_start = loop_start
        anim_props.played_cached_loop_end = end


# TODO: update these to use CollectionOperatorBase
class SM64_AnimTableOps(OperatorBase):
    bl_idname = "scene.sm64_table_operations"
    bl_label = "Table Operations"
    bl_description = "Move, remove, clear or add table elements"
    bl_options = {"UNDO"}

    index: IntProperty()
    op_name: StringProperty()
    action_name: StringProperty()
    header_variant: IntProperty()

    @classmethod
    def is_enabled(cls, context: Context, op_name: str, index: int, **_kwargs):
        table_elements = get_anim_props(context).elements
        if op_name == "MOVE_UP" and index == 0:
            return False
        elif op_name == "MOVE_DOWN" and index >= len(table_elements) - 1:
            return False
        elif op_name == "CLEAR" and len(table_elements) == 0:
            return False
        return True

    def execute_operator(self, context):
        anim_props = get_anim_props(context)
        table_elements = anim_props.elements
        if self.op_name == "MOVE_UP":
            table_elements.move(self.index, self.index - 1)
        elif self.op_name == "MOVE_DOWN":
            table_elements.move(self.index, self.index + 1)
        elif self.op_name == "ADD":
            if self.index != -1:
                table_element = table_elements[self.index]
            table_elements.add()
            if self.action_name:  # set based on action variant
                table_elements[-1].set_variant(bpy.data.actions[self.action_name], self.header_variant)
            elif self.index != -1:  # copy from table
                copyPropertyGroup(table_element, table_elements[-1])
            if self.index != -1:
                table_elements.move(len(table_elements) - 1, self.index + 1)
        elif self.op_name == "ADD_ALL":
            action = bpy.data.actions[self.action_name]
            for header_variant in range(len(get_action_props(action).headers)):
                if check_for_headers_in_table([(action, header_variant)], table_elements, anim_props.is_dma):
                    continue
                table_elements.add()
                table_elements[-1].set_variant(action, header_variant)
        elif self.op_name == "REMOVE":
            table_elements.remove(self.index)
        elif self.op_name == "CLEAR":
            table_elements.clear()
        else:
            raise NotImplementedError(f"Unimplemented table op {self.op_name}")


class SM64_AnimVariantOps(OperatorBase):
    bl_idname = "scene.sm64_header_variant_operations"
    bl_label = "Header Variant Operations"
    bl_description = "Move, remove, clear or add variants"
    bl_options = {"UNDO"}

    index: IntProperty()
    op_name: StringProperty()
    action_name: StringProperty()

    @classmethod
    def is_enabled(cls, context: Context, action_name: str, op_name: str, index: int, **_kwargs):
        action_props = get_action_props(get_action(action_name))
        headers = action_props.headers
        if op_name == "REMOVE" and index == 0:
            return False
        elif op_name == "MOVE_UP" and index <= 0:
            return False
        elif op_name == "MOVE_DOWN" and index >= len(headers) - 1:
            return False
        elif op_name == "CLEAR" and len(headers) <= 1:
            return False
        return True

    def execute_operator(self, context):
        action = get_action(self.action_name)
        action_props = get_action_props(action)
        headers = action_props.headers
        variants = action_props.header_variants
        variant_position = self.index - 1
        if self.op_name == "MOVE_UP":
            if self.index - 1 == 0:
                variants.add()
                copyPropertyGroup(headers[0], variants[-1])
                copyPropertyGroup(headers[self.index], headers[0])
                copyPropertyGroup(variants[-1], headers[self.index])
                variants.remove(len(variants) - 1)
            else:
                variants.move(variant_position, variant_position - 1)
        elif self.op_name == "MOVE_DOWN":
            if self.index == 0:
                variants.add()
                copyPropertyGroup(headers[0], variants[-1])
                copyPropertyGroup(headers[1], headers[0])
                copyPropertyGroup(variants[-1], headers[1])
                variants.remove(len(variants) - 1)
            else:
                variants.move(variant_position, variant_position + 1)
        elif self.op_name == "ADD":
            variants.add()
            added_variant = variants[-1]

            copyPropertyGroup(action_props.headers[self.index], added_variant)
            variants.move(len(variants) - 1, variant_position + 1)
            action_props.update_variant_numbers()
            added_variant.action = action
            added_variant.expand_tab = True
            added_variant.use_custom_name = False
            added_variant.use_custom_enum = False
            added_variant.custom_name = added_variant.get_name(get_anim_actor_name(context), action)
        elif self.op_name == "REMOVE":
            variants.remove(variant_position)
        elif self.op_name == "CLEAR":
            variants.clear()
        else:
            raise NotImplementedError(f"Unimplemented table op {self.op_name}")
        action_props.update_variant_numbers()


class SM64_AddNLATracksToTable(OperatorBase):
    bl_idname = "scene.sm64_add_nla_tracks_to_table"
    bl_label = "Add Existing NLA Tracks To Animation Table"
    bl_description = "Adds all NLA tracks in the selected armature to the animation table"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    context_mode = "OBJECT"
    icon = "NLA"

    @classmethod
    def poll(cls, context):
        if get_anim_obj(context) is None or get_anim_obj(context).animation_data is None:
            return False
        actions = get_anim_props(context).actions
        for track in context.object.animation_data.nla_tracks:
            for strip in track.strips:
                if strip.action is not None and strip.action not in actions:
                    return True
        return False

    def execute_operator(self, context):
        assert self.__class__.poll(context)
        anim_props = get_anim_props(context)
        for track in context.object.animation_data.nla_tracks:
            for strip in track.strips:
                action = strip.action
                if action is None or action in anim_props.actions:
                    continue
                for header_variant in range(len(get_action_props(action).headers)):
                    anim_props.elements.add()
                    anim_props.elements[-1].set_variant(action, header_variant)


class SM64_SetActionSlotFromObj(OperatorBase):
    bl_idname = "scene.sm64_set_action_slot_from_object"
    bl_label = "Set to active slot"
    bl_description = "Sets the action slot to the object's active slot"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    context_mode = "OBJECT"
    icon = "ACTION_SLOT"

    action_name: StringProperty(name="Action Name", default="")

    @classmethod
    def is_enabled(cls, context: Context, action_name: str, **_kwargs):
        return get_active_diff_slot(context, get_action(action_name)) is not None

    def execute_operator(self, context):
        animation_operator_checks(context)
        obj = get_anim_obj(context)
        action = get_action(self.action_name)
        action_props = get_action_props(action)
        action_props.slot_identifier = obj.animation_data.action_slot.identifier


class SM64_ExportAnimTable(OperatorBase):
    bl_idname = "scene.sm64_export_anim_table"
    bl_label = "Export Animation Table"
    bl_description = "Exports the animation table of the selected armature"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    context_mode = "OBJECT"
    icon = "EXPORT"

    @classmethod
    def poll(cls, context):
        return get_anim_obj(context) is not None

    def execute_operator(self, context):
        animation_operator_checks(context)
        export_animation_table(context, context.object)
        self.report({"INFO"}, "Exported animation table successfully!")


class SM64_ExportAnim(OperatorBase):
    bl_idname = "scene.sm64_export_anim"
    bl_label = "Export Individual Animation"
    bl_description = "Exports the select action of the selected armature"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    context_mode = "OBJECT"
    icon = "ACTION"

    @classmethod
    def poll(cls, context):
        return get_anim_obj(context) is not None

    def execute_operator(self, context):
        animation_operator_checks(context)
        export_animation(context, context.object)
        self.report({"INFO"}, "Exported animation successfully!")


class SM64_ImportAnim(OperatorBase):
    bl_idname = "scene.sm64_import_anim"
    bl_label = "Import Animation(s)"
    bl_description = "Imports animations into the call context's animation propreties, scene or object"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    context_mode = "OBJECT"
    icon = "IMPORT"

    def execute_operator(self, context):
        import_animations(context)


class SM64_SearchAnimPresets(SearchEnumOperatorBase):
    bl_idname = "scene.search_mario_anim_enum_operator"
    bl_property = "preset_animation"

    preset_animation: EnumProperty(items=get_enum_from_import_preset)

    def update_enum(self, context: Context):
        get_scene_anim_props(context).importing.preset_animation = self.preset_animation


class SM64_SearchAnimTablePresets(SearchEnumOperatorBase):
    bl_idname = "scene.search_anim_table_enum_operator"
    bl_property = "preset"

    preset: EnumProperty(items=enum_anim_tables)

    def update_enum(self, context: Context):
        get_scene_anim_props(context).importing.preset = self.preset


class SM64_SearchAnimatedBhvs(SearchEnumOperatorBase):
    bl_idname = "scene.search_animated_behavior_enum_operator"
    bl_property = "behaviour"

    behaviour: EnumProperty(items=enum_animated_behaviours)

    def update_enum(self, context: Context):
        get_anim_props(context).behaviour = self.behaviour


classes = (
    SM64_ExportAnimTable,
    SM64_ExportAnim,
    SM64_PreviewAnim,
    SM64_AnimTableOps,
    SM64_AnimVariantOps,
    SM64_AddNLATracksToTable,
    SM64_SetActionSlotFromObj,
    SM64_ImportAnim,
    SM64_SearchAnimPresets,
    SM64_SearchAnimatedBhvs,
    SM64_SearchAnimTablePresets,
)


def anim_ops_register():
    for cls in classes:
        register_class(cls)

    bpy.app.handlers.frame_change_pre.append(emulate_no_loop)


def anim_ops_unregister():
    for cls in reversed(classes):
        unregister_class(cls)

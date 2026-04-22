import bpy

from ..sm64_utility import get_object_actor_name
from ...gltf_utility import GlTF2SubExtension

from .properties import SM64_ArmatureAnimProperties
from .utility import get_action_props, is_obj_animatable, get_anim_owners


# TODO blender_to_sm64_scale
class SM64AnimationGlTFExtension(GlTF2SubExtension):
    ACTION_EXTENSION_NAME = "FAST64_sm64_anim"
    OBJECT_EXTENSION_NAME = "FAST64_sm64_node_anim_table"

    HEADER_EXTENSION_NAME = "FAST64_sm64_header"
    TABLE_ELEMENT_EXTENSION_NAME = "FAST64_sm64_table_element"

    def gather_any_animation_hook(self, gltf2_animation, blender_action, blender_object, export_settings):
        if blender_object and is_obj_animatable(blender_object):
            action_props = get_action_props(blender_action)
            actor_name = get_object_actor_name(blender_object)
            anim_props: SM64_ArmatureAnimProperties = blender_object.fast64.sm64.animation
            data = action_props.to_dict(
                export_type="GLTF",
                action=blender_action,
                actor_name=actor_name,
                gen_enums=anim_props.get_gen_enums("GLTF"),
                dma=anim_props.is_dma,
                export_seperately=anim_props.export_seperately,
                updates_table=anim_props.update_table,
                gltf_extension=self,
            )
            self.append_extension(gltf2_animation, self.ACTION_EXTENSION_NAME, data)

    def gather_node_hook(self, gltf2_node, blender_object, export_settings):
        if blender_object and is_obj_animatable(blender_object):
            if export_settings.get("gltf_export_id") != "FAST64_SM64_ANIM_TABLE_EXPORT":
                return
            anim_props = blender_object.fast64.sm64.animation
            data = anim_props.to_dict(
                export_type="GLTF", actor_name=get_object_actor_name(blender_object), gltf_extension=self
            )
            self.append_extension(gltf2_node, self.OBJECT_EXTENSION_NAME, data)

    def gather_import_animation_channel_after_hook(
        self, gltf_animation, gltf_node, path, channel, blender_action, import_settings
    ):
        if blender_action.get("already_imported"):
            return
        blender_action["already_imported"] = True
        data = self.get_extension(gltf_animation, self.ACTION_EXTENSION_NAME)
        if data and blender_action:
            get_action_props(blender_action).from_dict(data, export_type="GLTF", gltf_extension=self)

    def gather_import_node_after_hook(self, vnode, gltf_node, blender_object, import_settings):
        data = self.get_extension(gltf_node, self.OBJECT_EXTENSION_NAME)
        if data and blender_object:
            blender_object.fast64.sm64.animation.from_dict(data, export_type="GLTF", gltf_extension=self)

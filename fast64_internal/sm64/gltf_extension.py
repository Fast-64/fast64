import bpy
from ..gltf_utility import GlTF2SubExtension
from .animation.gltf import SM64AnimationGlTFExtension


class SM64Extensions(GlTF2SubExtension):
    def post_init(self):
        self.anim_ext = SM64AnimationGlTFExtension(self.extension)

    def gather_any_animation_hook(self, gltf2_animation, blender_action, blender_object, export_settings):
        self.anim_ext.gather_any_animation_hook(gltf2_animation, blender_action, blender_object, export_settings)

    def gather_node_hook(self, gltf2_node, blender_object, export_settings):
        self.anim_ext.gather_node_hook(gltf2_node, blender_object, export_settings)

    def gather_import_animation_channel_after_hook(
        self, gltf_animation, gltf_node, path, channel, blender_action, import_settings
    ):
        self.anim_ext.gather_import_animation_channel_after_hook(
            gltf_animation, gltf_node, path, channel, blender_action, import_settings
        )

    def gather_import_node_after_hook(self, vnode, gltf_node, blender_object, import_settings):
        self.anim_ext.gather_import_node_after_hook(vnode, gltf_node, blender_object, import_settings)

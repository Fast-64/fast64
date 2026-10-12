from ..gltf_utility import GlTF2SubExtension
from .animation.gltf import SM64AnimationGlTFExtension
from .geolayout.gltf import SM64GeoGlTFExtension


class SM64Extensions(GlTF2SubExtension):
    SCENE_SETTING_EXTENSION_NAME = "FAST64_scene_sm64_settings"

    def post_init(self):
        self.anim_ext = SM64AnimationGlTFExtension(self.extension)
        self.geo_ext = SM64GeoGlTFExtension(self.extension)

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

    def gather_joint_hook(self, gltf2_node, blender_bone, export_settings):
        self.geo_ext.gather_joint_hook(gltf2_node, blender_bone, export_settings)

    def gather_scene_hook(self, gltf2_scene, blender_scene, export_settings):
        self.append_extension(
            gltf2_scene,
            self.SCENE_SETTING_EXTENSION_NAME,
            {"blender_scale": blender_scene.fast64.sm64.blender_to_sm64_scale},
        )

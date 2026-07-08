from bpy.types import PoseBone
from typing import TYPE_CHECKING

from ...gltf_utility import GlTF2SubExtension


if TYPE_CHECKING:
    from ..custom_cmd.properties import SM64_CustomCmdProperties

CMD_TO_GLTF = {
    "TranslateRotate": "TRANSLATE_ROTATE",
    "DisplayList": "DISPLAY_LIST",
    "HeldObject": "HELD_OBJECT",
    "StartRenderArea": "START_RENDER_AREA",
    "SwitchOption": "SWITCH_OPTION",
    "DisplayListWithOffset": "ANIMATED_PART",
}


class SM64GeoGlTFExtension(GlTF2SubExtension):
    BONE_EXTENSION_NAME = "FAST64_joint_sm64_geo"

    def gather_joint_hook(self, gltf2_node, blender_bone: PoseBone, export_settings):
        bone = blender_bone.bone
        data = {
            "geo_cmd": CMD_TO_GLTF.get(bone.geo_cmd, bone.geo_cmd.upper()),
        }
        if bone.geo_cmd == "Custom":
            custom: SM64_CustomCmdProperties = bone.fast64.sm64.custom
            if custom.preset == "NONE":
                conf_type = "NO_PRESET"
            else:
                conf_type = "PRESET"
            data["custom"] = custom.to_dict(conf_type, bone)
        self.append_extension(gltf2_node, self.BONE_EXTENSION_NAME, data)

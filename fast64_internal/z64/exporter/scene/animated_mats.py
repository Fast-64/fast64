import bpy
import re

from dataclasses import dataclass
from bpy.types import Object
from typing import Optional
from pathlib import Path

from ....utility import CData, PluginError, exportColor, scaleToU8, toAlnum, get_new_empty_object, indent
from ...utility import getObjectList, is_hackeroot
from ...scene.properties import OOTSceneHeaderProperty
from ...animated_mats.properties import (
    Z64_AnimatedMatColorParams,
    Z64_AnimatedMatTexScrollParams,
    Z64_AnimatedMatTexCycleParams,
    Z64_AnimatedMaterial,
    Z64_AnimatedMaterialExportSettings,
    Z64_AnimatedMaterialImportSettings,
)

from ...importer.scene_header import parse_animated_material


class AnimatedMatColorParams:
    def __init__(
        self,
        props: Z64_AnimatedMatColorParams,
        segment_num: int,
        type_num: int,
        base_name: str,
        index: int,
        type: str,
        suffix: str = "",
    ):
        is_draw_color = type == "color"
        self.segment_num = segment_num
        self.type_num = type_num
        self.base_name = base_name
        self.header_suffix = f"_{index:02}"
        self.name = f"{self.base_name}{suffix}ColorParams{self.header_suffix}"
        self.frame_length = len(props.keyframes) if is_draw_color else props.keyframe_length
        self.prim_colors: list[tuple[int, int, int, int, int]] = []
        self.env_colors: list[tuple[int, int, int, int]] = []
        self.frames: list[int] = []

        for keyframe in props.keyframes:
            prim = exportColor(keyframe.prim_color[0:3]) + [scaleToU8(keyframe.prim_color[3])]
            self.prim_colors.append((prim[0], prim[1], prim[2], prim[3], keyframe.prim_lod_frac))

            if not is_draw_color or props.use_env_color:
                self.env_colors.append(tuple(exportColor(keyframe.env_color[0:3]) + [scaleToU8(keyframe.env_color[3])]))

            if not is_draw_color:
                self.frames.append(keyframe.frame_num)

            if not is_draw_color and keyframe.frame_num > self.frame_length:
                raise PluginError("ERROR: the frame number cannot be higher than the total frame count!")

        self.frame_count = len(self.frames)

        if not is_draw_color:
            assert len(self.frames) == len(self.prim_colors) == len(self.env_colors)

        if is_draw_color and props.use_env_color:
            assert len(self.prim_colors) == len(self.env_colors)

    def to_c(self, all_externs: bool = True):
        data = CData()
        prim_array_name = f"{self.base_name}ColorPrimColor{self.header_suffix}"
        env_array_name = f"{self.base_name}ColorEnvColor{self.header_suffix}"
        frames_array_name = f"{self.base_name}ColorKeyFrames{self.header_suffix}"
        params_name = f"AnimatedMatColorParams {self.name}"

        if len(self.env_colors) == 0:
            env_array_name = "NULL"

        if len(self.frames) == 0:
            frames_array_name = "NULL"

        # .h
        if all_externs:
            data.header = (
                f"extern F3DPrimColor {prim_array_name}[];\n"
                + (f"extern F3DEnvColor {env_array_name}[];\n" if len(self.env_colors) > 0 else "")
                + (f"extern u16 {frames_array_name}[];\n" if len(self.frames) > 0 else "")
                + f"extern {params_name};\n"
            )

        # .c
        data.source = (
            (
                (f"F3DPrimColor {prim_array_name}[]" + " = {\n" + indent)
                + f",\n{indent}".join(
                    "{ " + f"{entry[0]}, {entry[1]}, {entry[2]}, {entry[3]}, {entry[4]}" + " }"
                    for entry in self.prim_colors
                )
                + "\n};\n\n"
            )
            + (
                (
                    (f"F3DEnvColor {env_array_name}[]" + " = {\n" + indent)
                    + f",\n{indent}".join(
                        "{ " + f"{entry[0]}, {entry[1]}, {entry[2]}, {entry[3]}" + " }" for entry in self.env_colors
                    )
                    + "\n};\n\n"
                )
                if len(self.env_colors) > 0
                else ""
            )
            + (
                (
                    (f"u16 {frames_array_name}[]" + " = {\n" + indent)
                    + f",\n{indent}".join(f"{entry}" for entry in self.frames)
                    + "\n};\n\n"
                )
                if len(self.frames) > 0
                else ""
            )
            + (
                (params_name + " = {\n")
                + (indent + f"{self.frame_length},\n")
                + (indent + f"{self.frame_count},\n")
                + (indent + f"{prim_array_name},\n")
                + (indent + f"{env_array_name},\n")
                + (indent + f"{frames_array_name},\n")
                + "};\n\n"
            )
        )

        return data


class AnimatedMatTexScrollParams:
    def __init__(
        self,
        props: Z64_AnimatedMatTexScrollParams,
        segment_num: int,
        type_num: int,
        base_name: str,
        index: int,
        type: str,
        suffix: str = "",
    ):
        self.segment_num = segment_num
        self.type_num = type_num
        self.base_name = base_name
        self.header_suffix = f"_{index:02}"
        self.texture_1 = (
            "{ "
            + f"{props.texture_1.step_x}, {props.texture_1.step_y}, {props.texture_1.width}, {props.texture_1.height}"
            + " },"
        )
        self.texture_2: Optional[str] = None

        if type == "two_tex_scroll":
            self.name = f"{self.base_name}{suffix}TwoTexScrollParams{self.header_suffix}"
            self.texture_2 = (
                "{ "
                + f"{props.texture_2.step_x}, {props.texture_2.step_y}, {props.texture_2.width}, {props.texture_2.height}"
                + " },"
            )
        else:
            self.name = f"{self.base_name}{suffix}TexScrollParams{self.header_suffix}"

    def to_c(self, all_externs: bool = True):
        data = CData()
        params_name = f"AnimatedMatTexScrollParams {self.name}[]"

        # .h
        if all_externs:
            data.header = f"extern {params_name};\n"

        # .c
        data.source = f"{params_name}" + " = {\n" + indent + self.texture_1

        if self.texture_2 is not None:
            data.source += "\n" + indent + self.texture_2

        data.source += "\n};\n\n"

        return data


class AnimatedMatTexCycleParams:
    def __init__(
        self,
        props: Z64_AnimatedMatTexCycleParams,
        segment_num: int,
        type_num: int,
        base_name: str,
        index: int,
        type: str,
        suffix: str = "",
    ):
        self.segment_num = segment_num
        self.type_num = type_num
        self.base_name = base_name
        self.header_suffix = f"_{index:02}"
        self.name = f"{self.base_name}{suffix}TexCycleParams{self.header_suffix}"
        self.textures: list[str] = []
        self.texture_indices: list[int] = []

        for texture in props.textures:
            self.textures.append(texture.symbol)

        for keyframe in props.keyframes:
            assert keyframe.texture_index < len(self.textures), "ERROR: invalid AnimatedMatTexCycle texture index"
            self.texture_indices.append(keyframe.texture_index)

        self.frame_length = len(self.texture_indices)
        assert len(self.textures) > 0, "you need at least one texture symbol (Animated Material)"
        assert len(self.texture_indices) > 0, "you need at least one texture index (Animated Material)"

    def to_c(self, all_externs: bool = True):
        data = CData()
        texture_array_name = f"{self.base_name}CycleTextures{self.header_suffix}"
        texture_indices_array_name = f"{self.base_name}CycleTextureIndices{self.header_suffix}"
        params_name = f"AnimatedMatTexCycleParams {self.name}"

        # .h
        if all_externs:
            data.header = (
                f"extern TexturePtr {texture_array_name}[];\n"
                + f"extern u8 {texture_indices_array_name}[];\n"
                + f"extern {params_name};\n"
            )

        # .c
        data.source = (
            (
                (f"TexturePtr {texture_array_name}[]" + " = {\n")
                + indent
                + f",\n{indent}".join(texture for texture in self.textures)
                + "\n};\n\n"
            )
            + (
                (f"u8 {texture_indices_array_name}[]" + " = {\n")
                + indent
                + ", ".join(f"{index}" for index in self.texture_indices)
                + "\n};\n\n"
            )
            + (
                (params_name + " = {\n")
                + indent
                + f"{self.frame_length}, {texture_array_name}, {texture_indices_array_name},"
                + "\n};\n\n"
            )
        )

        return data


class AnimatedMaterial:
    def __init__(self, props: Z64_AnimatedMaterial, base_name: str, suffix: str = ""):
        self.name = base_name
        self.entries: list[AnimatedMatColorParams | AnimatedMatTexScrollParams | AnimatedMatTexCycleParams] = []

        if len(props.entries) == 0:
            return

        type_list_map: dict[
            str, tuple[AnimatedMatColorParams | AnimatedMatTexScrollParams | AnimatedMatTexCycleParams, str, int]
        ] = {
            "tex_scroll": (AnimatedMatTexScrollParams, "tex_scroll_params", 0),
            "two_tex_scroll": (AnimatedMatTexScrollParams, "tex_scroll_params", 1),
            "color": (AnimatedMatColorParams, "color_params", 2),
            "color_lerp": (AnimatedMatColorParams, "color_params", 3),
            "color_nonlinear_interp": (AnimatedMatColorParams, "color_params", 4),
            "tex_cycle": (AnimatedMatTexCycleParams, "tex_cycle_params", 5),
        }

        for i, item in enumerate(props.entries):
            type = item.type if item.type != "Custom" else item.typeCustom
            if type != "Custom":
                class_def, prop_name, type_num = type_list_map[type]
                self.entries.append(
                    class_def(getattr(item, prop_name), item.segment_num, type_num, base_name, i, type, suffix)
                )

    def to_c(self, all_externs: bool = True):
        data = CData()

        for entry in self.entries:
            data.append(entry.to_c(all_externs))

        array_name = f"AnimatedMaterial {self.name}[]"

        # .h
        data.header += f"extern {array_name};\n"

        # .c
        data.source += array_name + " = {\n" + indent

        if len(self.entries) > 0:
            entries = [
                f"MATERIAL_SEGMENT_NUM({entry.segment_num}), "
                + f"{entry.type_num}, "
                + f"{'&' if entry.type_num in {2, 3, 4, 5} else ''}{entry.name}"
                for entry in self.entries
            ]

            # the last entry's segment need to be negative
            if len(self.entries) > 0 and self.entries[-1].segment_num > 0:
                entries[-1] = f"LAST_{entries[-1]}"

            data.source += f",\n{indent}".join("{ " + entry + " }" for entry in entries)
        else:
            data.source += "{ 0, 6, NULL }"

        data.source += "\n};\n"
        return data


@dataclass
class SceneAnimatedMaterial:
    """This class hosts Animated Materials data for scenes"""

    name: str
    animated_material: Optional[AnimatedMaterial]

    # add a macro for the segment number for convenience (only if using animated materials)
    mat_seg_num_macro = "\n".join(
        [
            "// Animated Materials requires the segment number to be offset by 7",
            "#ifndef MATERIAL_SEGMENT_NUM",
            "#define MATERIAL_SEGMENT_NUM(n) ((n) - 7)",
            "#endif\n",
            "// The last entry also requires to be a negative number",
            "#ifndef LAST_MATERIAL_SEGMENT_NUM",
            "#define LAST_MATERIAL_SEGMENT_NUM(n) -MATERIAL_SEGMENT_NUM(n)",
            "#endif\n\n",
        ]
    )

    @staticmethod
    def new(name: str, props: OOTSceneHeaderProperty, is_reuse: bool):
        return SceneAnimatedMaterial(name, AnimatedMaterial(props.animated_material, name) if not is_reuse else None)

    @staticmethod
    def export():
        """Exports animated materials data as C files, this should be called to do a separate export from the scene."""

        settings: Z64_AnimatedMaterialExportSettings = bpy.context.scene.fast64.oot.anim_mats_export_settings
        export_obj: Object = settings.export_obj
        name = toAlnum(export_obj.name)
        assert name is not None

        # convert props
        entries: list[AnimatedMaterial] = [
            AnimatedMaterial(item, f"{name}_AnimatedMaterial_{i:02}", "_")
            for i, item in enumerate(export_obj.fast64.oot.animated_materials.items)
        ]
        assert len(entries) > 0, "The Animated Material list is empty!"

        filename = f"{name.lower()}_anim_mats"

        # create C data
        data = CData()
        data.header += f'#include "{settings.get_include_name()}"\n'

        if is_hackeroot():
            data.header += '#include "config.h"\n\n'

            if bpy.context.scene.fast64.oot.hackeroot_settings.export_ifdefs:
                data.header += "#if ENABLE_ANIMATED_MATERIALS\n\n"
        else:
            data.header += "\n"

        if not settings.is_custom_path:
            data.source += f'#include "assets/objects/{settings.object_name}/{filename}.h"\n\n'

            if is_hackeroot() and bpy.context.scene.fast64.oot.hackeroot_settings.export_ifdefs:
                data.source += "#if ENABLE_ANIMATED_MATERIALS\n\n"

        data.header += SceneAnimatedMaterial.mat_seg_num_macro

        for entry in entries:
            c_data = entry.to_c(False)
            c_data.source += "\n"
            data.append(c_data)

        if is_hackeroot():
            if not settings.is_custom_path:
                data.header += "\n"
        else:
            data.source = data.source[:-1]

        extra = ""
        if is_hackeroot() and bpy.context.scene.fast64.oot.hackeroot_settings.export_ifdefs:
            extra = "#endif\n"

        data.source += extra

        if not settings.is_custom_path:
            data.header += extra

        # write C data
        if settings.is_custom_path:
            export_path = Path(settings.export_path)
            export_path.mkdir(exist_ok=True)
        else:
            export_path = Path(bpy.context.scene.ootDecompPath) / "assets" / "objects" / settings.object_name

        export_path = export_path.resolve()
        assert export_path.exists(), f"This path doesn't exist: {repr(export_path)}"

        if settings.is_custom_path:
            c_path = export_path / f"{filename}.inc.c"
            c_path.write_text(data.header + "\n" + data.source)
        else:
            h_path = export_path / f"{filename}.h"
            h_path.write_text(data.header)

            c_path = export_path / f"{filename}.c"
            c_path.write_text(data.source)

    @staticmethod
    def from_data():
        """Imports animated materials data from C files, this should be called to do a separate import from the scene."""

        settings: Z64_AnimatedMaterialImportSettings = bpy.context.scene.fast64.oot.anim_mats_import_settings
        import_path = Path(settings.import_path).resolve()

        file_data = import_path.read_text()
        array_names = [
            match.group(1)
            for match in re.finditer(r"AnimatedMaterial\s([a-zA-Z0-9_]*)\[\]\s=\s\{", file_data, re.DOTALL)
        ]

        new_obj = get_new_empty_object("Actor Animated Materials")
        new_obj.ootEmptyType = "Animated Materials"

        for array_name in array_names:
            parse_animated_material(new_obj.fast64.oot.animated_materials.items.add(), file_data, array_name)

    def get_cmd(self):
        """Returns the animated material scene command"""

        if is_hackeroot() and bpy.context.scene.fast64.oot.hackeroot_settings.export_ifdefs:
            return (
                "#if ENABLE_ANIMATED_MATERIALS\n"
                + indent
                + f"SCENE_CMD_ANIMATED_MATERIAL_LIST({self.name}),\n"
                + "#endif\n"
            )
        else:
            return indent + f"SCENE_CMD_ANIMATED_MATERIAL_LIST({self.name}),\n"

    def to_c(self):
        data = CData()

        if self.animated_material is not None:
            if is_hackeroot() and bpy.context.scene.fast64.oot.hackeroot_settings.export_ifdefs:
                data.source += "#if ENABLE_ANIMATED_MATERIALS\n"
                data.header += "#if ENABLE_ANIMATED_MATERIALS\n"

            data.append(self.animated_material.to_c())

            extra = ""
            if is_hackeroot() and bpy.context.scene.fast64.oot.hackeroot_settings.export_ifdefs:
                extra = "#endif\n"

            data.source += extra + "\n"
            data.header += "\n" + extra

        return data


@dataclass
class ActorAnimatedMaterial:
    """This class hosts Animated Materials data for actors"""

    name: str
    entries: list[AnimatedMaterial]

    @staticmethod
    def new(name: str, scene_obj: Object, header_index: int):
        obj_list = getObjectList(scene_obj.children_recursive, "EMPTY", "Animated Materials")
        entries: list[AnimatedMaterial] = []

        for obj in obj_list:
            entries.extend(
                [AnimatedMaterial(item, name, header_index) for item in obj.fast64.oot.animated_materials.items]
            )

        return ActorAnimatedMaterial(name, entries)

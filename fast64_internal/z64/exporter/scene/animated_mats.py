import bpy
import re

from dataclasses import dataclass
from bpy.types import Object
from typing import Optional, Any
from pathlib import Path

from ....game_data import game_data
from ....utility import CData, PluginError, exportColor, scaleToU8, toAlnum, get_new_empty_object, indent
from ...utility import getObjectList, is_hackeroot
from ...scene.properties import OOTSceneHeaderProperty
from ..collision.surface import SurfaceType
from ..collision import CollisionHeader

from ...animated_mats.properties import (
    Z64_AnimatedMatColorParams,
    Z64_AnimatedMatTexScrollParams,
    Z64_AnimatedMatTexCycleParams,
    Z64_AnimatedMatTexTimedCycleParams,
    Z64_AnimatedMatTextureParams,
    Z64_AnimatedMatMultiTextureParams,
    Z64_AnimatedMatSurfaceSwapParams,
    Z64_AnimatedMatColorSwitchParams,
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
        type: str,
        base_name: str,
        index: int,
        use_macros: bool,
        col_header: CollisionHeader,
        suffix: str = "",
    ):
        is_draw_color = type == "anim_mat_type_color"
        is_draw_color_cycle = type == "anim_mat_type_color_cycle"
        is_col_or_cycle = is_draw_color or is_draw_color_cycle
        self.segment_num = segment_num
        self.type = type
        self.base_name = base_name
        self.use_macros = use_macros
        self.header_suffix = f"_{index:02}"
        self.name = f"{self.base_name}{suffix}ColorParams{self.header_suffix}"
        self.frame_length = len(props.keyframes) if is_draw_color else props.keyframe_length
        self.prim_colors: list[tuple[int, int, int, int, int]] = []
        self.env_colors: list[tuple[int, int, int, int]] = []
        self.frames: list[int] = []

        for keyframe in props.keyframes:
            prim = exportColor(keyframe.prim_color[0:3]) + [scaleToU8(keyframe.prim_color[3])]
            self.prim_colors.append((prim[0], prim[1], prim[2], prim[3], keyframe.prim_lod_frac))

            if not is_col_or_cycle or props.use_env_color:
                self.env_colors.append(tuple(exportColor(keyframe.env_color[0:3]) + [scaleToU8(keyframe.env_color[3])]))

            if not is_draw_color:
                self.frames.append(keyframe.duration if is_draw_color_cycle else keyframe.frame_num)

            if not is_col_or_cycle and keyframe.frame_num > self.frame_length:
                raise PluginError("ERROR: the frame number cannot be higher than the total frame count!")

        self.frame_count = len(self.frames)

        if not is_col_or_cycle:
            assert len(self.frames) == len(self.prim_colors) == len(self.env_colors)

        if is_draw_color and props.use_env_color:
            assert len(self.prim_colors) == len(self.env_colors)

        if is_draw_color_cycle:
            assert len(self.frames) == len(self.prim_colors)

            if props.use_env_color:
                assert len(self.frames) == len(self.prim_colors) == len(self.env_colors)

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
        length = f"ARRAY_COUNT({frames_array_name})" if self.use_macros else self.frame_count
        data.source = (
            (
                (f"F3DPrimColor {prim_array_name}[]" + " = {\n" + indent)
                + f"\n{indent}".join(
                    "{ " + f"{entry[0]}, {entry[1]}, {entry[2]}, {entry[3]}, {entry[4]}" + " },"
                    for entry in self.prim_colors
                )
                + "\n};\n\n"
            )
            + (
                (
                    (f"F3DEnvColor {env_array_name}[]" + " = {\n" + indent)
                    + f"\n{indent}".join(
                        "{ " + f"{entry[0]}, {entry[1]}, {entry[2]}, {entry[3]}" + " }," for entry in self.env_colors
                    )
                    + "\n};\n\n"
                )
                if len(self.env_colors) > 0
                else ""
            )
            + (
                (
                    (f"u16 {frames_array_name}[]" + " = {\n" + indent)
                    + f"\n{indent}".join(f"{entry}," for entry in self.frames)
                    + "\n};\n\n"
                )
                if len(self.frames) > 0
                else ""
            )
            + (
                (params_name + " = {\n")
                + (indent + f"{self.frame_length},\n")
                + (indent + f"{length},\n")
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
        type: str,
        base_name: str,
        index: int,
        use_macros: bool,
        col_header: CollisionHeader,
        suffix: str = "",
    ):
        self.segment_num = segment_num
        self.type = type
        self.base_name = base_name
        self.header_suffix = f"_{index:02}"
        self.texture_1 = (
            "{ "
            + f"{props.texture_1.step_x}, {props.texture_1.step_y}, {props.texture_1.width}, {props.texture_1.height}"
            + " },"
        )
        self.texture_2: Optional[str] = None

        if "two_tex" in type:
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
        type: str,
        base_name: str,
        index: int,
        use_macros: bool,
        col_header: CollisionHeader,
        suffix: str = "",
    ):
        self.segment_num = segment_num
        self.type = type
        self.base_name = base_name
        self.use_macros = use_macros
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


class AnimatedMatTexTimedCycleParams:
    def __init__(
        self,
        props: Z64_AnimatedMatTexTimedCycleParams,
        segment_num: int,
        type: str,
        base_name: str,
        index: int,
        use_macros: bool,
        col_header: CollisionHeader,
        suffix: str = "",
    ):
        self.segment_num = segment_num
        self.type = type
        self.base_name = base_name
        self.header_suffix = f"_{index:02}"
        self.name = f"{self.base_name}{suffix}TexTimedCycleParams{self.header_suffix}"
        self.use_macros = use_macros
        self.entries: dict[str, int] = {}  # entries["texture_symbol"] = duration

        for keyframe in props.keyframes:
            self.entries[keyframe.symbol] = keyframe.duration

        assert len(self.entries) > 1, "ERROR: this type requires at least two entries"

    def to_c(self, all_externs: bool = True):
        data = CData()
        array_name = f"{self.base_name}TexTimedCycleKeyframes{self.header_suffix}"
        params_name = f"AnimatedMatTexTimedCycleParams {self.name}"

        # .h
        if all_externs:
            data.header = f"extern AnimatedMatTexTimedCycleKeyframe {array_name}[];\n" + f"extern {params_name};\n"

        # .c
        length = f"ARRAY_COUNT({array_name})" if self.use_macros else f"{len(self.entries)}"
        data.source = (
            (f"AnimatedMatTexTimedCycleKeyframe {array_name}[]" + " = {\n")
            + indent
            + f"\n{indent}".join("{ " + f"{symbol}, {duration}" + " }," for symbol, duration in self.entries.items())
            + "\n};\n\n"
        ) + ((params_name + " = {\n") + indent + f"{length}, {array_name}" + "\n};\n\n")

        return data


class AnimatedMatTextureParams:
    def __init__(
        self,
        props: Z64_AnimatedMatTextureParams,
        segment_num: int,
        type: str,
        base_name: str,
        index: int,
        use_macros: bool,
        col_header: CollisionHeader,
        suffix: str = "",
    ):
        self.segment_num = segment_num
        self.type = type
        self.base_name = base_name
        self.header_suffix = f"_{index:02}"
        self.name = f"{self.base_name}{suffix}TextureParams{self.header_suffix}"
        self.texture_1 = props.texture_1
        self.texture_2 = props.texture_2
        assert len(self.texture_1) > 0
        assert len(self.texture_2) > 0

    def to_c(self, all_externs: bool = True):
        data = CData()
        params_name = f"AnimatedMatTextureParams {self.name}"

        # .h
        if all_externs:
            data.header = f"extern {params_name};\n"

        # .c
        data.source = params_name + " = {\n" + indent + "{ " + f"{self.texture_1}, {self.texture_2}" + " }" + "\n};\n\n"

        return data


class AnimatedMatMultiTextureParams:
    def __init__(
        self,
        props: Z64_AnimatedMatMultiTextureParams,
        segment_num: int,
        type: str,
        base_name: str,
        index: int,
        use_macros: bool,
        col_header: CollisionHeader,
        suffix: str = "",
    ):
        self.segment_num = segment_num
        self.type = type
        self.base_name = base_name
        self.header_suffix = f"_{index:02}"
        self.name = f"{self.base_name}{suffix}TextureParams{self.header_suffix}"

        self.min_prim_alpha: int = props.min_prim_alpha
        self.max_prim_alpha: int = props.max_prim_alpha
        self.min_env_alpha: int = props.min_env_alpha
        self.max_env_alpha: int = props.max_env_alpha
        self.speed: int = props.speed
        self.use_texture_refs: bool = props.use_texture_refs
        self.texture_1: str = props.texture_1
        self.texture_2: str = props.texture_2
        self.segment_1: int = props.segment_1
        self.segment_2: int = props.segment_2

    def to_c(self, all_externs: bool = True):
        data = CData()
        params_name = f"AnimatedMatMultiTextureParams {self.name}"

        # .h
        if all_externs:
            data.header = f"extern {params_name};\n"

        # .c
        data.source = (
            params_name
            + " = {\n"
            + indent
            + f"{self.min_prim_alpha}, "
            + f"{self.max_prim_alpha}, "
            + f"{self.min_env_alpha}, "
            + f"{self.max_env_alpha}, "
            + f"{self.speed}, "
            + (
                f"{self.texture_1}, {self.texture_2}, {self.segment_1}, {self.segment_2},"
                if self.use_texture_refs
                else "NULL, NULL, 0, 0"
            )
            + "\n};\n\n"
        )

        return data


class AnimatedMatEventParams:
    def __init__(
        self,
        props,
        segment_num: int,
        type: str,
        base_name: str,
        index: int,
        use_macros: bool,
        col_header: CollisionHeader,
        suffix: str = "",
    ):
        self.segment_num = segment_num
        self.type = type

    def to_c(self, all_externs: bool = True):
        return CData()


class AnimatedMatSurfaceSwapParams:
    def __init__(
        self,
        props: Z64_AnimatedMatSurfaceSwapParams,
        segment_num: int,
        type: str,
        base_name: str,
        index: int,
        use_macros: bool,
        col_header: CollisionHeader,
        suffix: str = "",
    ):
        self.segment_num = segment_num
        self.type = type
        self.base_name = base_name
        self.header_suffix = f"_{index:02}"
        self.name = f"{self.base_name}{suffix}SurfaceSwapParams{self.header_suffix}"
        self.surface_type = SurfaceType.new(props.col_settings, use_macros)

        ignore_cam = props.col_settings.ignoreCameraCollision
        ignore_entity = props.col_settings.ignoreActorCollision
        ignore_proj = props.col_settings.ignoreProjectileCollision

        if ignore_proj or ignore_entity or ignore_cam:
            flag1 = ("COLPOLY_IGNORE_PROJECTILES" if use_macros else "(1 << 2)") if ignore_proj else ""
            flag2 = ("COLPOLY_IGNORE_ENTITY" if use_macros else "(1 << 1)") if ignore_entity else ""
            flag3 = ("COLPOLY_IGNORE_CAMERA" if use_macros else "(1 << 0)") if ignore_cam else ""
            self.flags_a = "(" + " | ".join(flag for flag in [flag1, flag2, flag3] if len(flag) > 0) + ")"
        else:
            self.flags_a = "COLPOLY_IGNORE_NONE" if use_macros else "0"

        if props.col_settings.conveyorOption == "Land":
            self.flags_b = "COLPOLY_IS_FLOOR_CONVEYOR" if use_macros else "(1 << 0)"
        else:
            self.flags_b = "COLPOLY_IGNORE_NONE" if use_macros else "0"

        self.multitexture: Optional[AnimatedMatMultiTextureParams] = None
        if props.use_multitexture:
            self.multitexture = AnimatedMatMultiTextureParams(
                props.multitexture_params,
                self.segment_num,
                self.base_name,
                "anim_mat_type_multitexture",
                index,
                use_macros,
                col_header,
                suffix,
            )

        self.meshes: list[int] = []
        self.surface_index = -1

        if props.use_tris:
            assert len(props.meshes) > 0, "ERROR: this context requires at least one entry"

            # TODO: find a less dumb way to get the index
            for entry in col_header.collisionPoly.polyList:
                if entry.index_to_obj is not None:
                    index = list(entry.index_to_obj.keys())[-1]
                    mesh_obj = list(entry.index_to_obj.values())[-1]

                    for item in props.meshes:
                        if mesh_obj is item.mesh_obj:
                            self.meshes.append(index)
                            break
        else:
            assert props.material is not None, "ERROR: this context requires a material to be set"

            # TODO: find a less dumb way to get the index
            for i, entry in enumerate(col_header.surfaceType.surfaceTypeList):
                if entry.data_material is props.material:
                    self.surface_index = i
                    break

            assert self.surface_index >= 0, "ERROR: surface index not found, is the selected material assigned?"

    def to_c(self, all_externs: bool = True):
        data = CData()

        params_name = f"AnimatedMatSurfaceSwapParams {self.name}"
        data.append(self.multitexture.to_c() if self.multitexture is not None else CData())

        # .h
        if all_externs:
            data.header += f"extern {params_name};\n"

        # .c
        indices = (", ".join(f"{index}" for index in self.meshes) + ", ") if len(self.meshes) > 0 else ""
        data.source += (
            params_name
            + " = {\n"
            + f"{self.surface_type.getEntryC()}\n"
            + (indent + f"{self.surface_index},\n")
            + (indent + f"{self.flags_a},\n")
            + (indent + f"{self.flags_b},\n")
            + (indent + f"{'&' + self.multitexture.name if self.multitexture is not None else 'NULL'},\n")
            + (indent + "{ " f"{indices}" + "-1" + " },")
            + "\n};\n\n"
        )

        return data


class AnimatedMatColorSwitchParams:
    def __init__(
        self,
        props: Z64_AnimatedMatColorSwitchParams,
        segment_num: int,
        type: str,
        base_name: str,
        index: int,
        use_macros: bool,
        col_header: CollisionHeader,
        suffix: str = "",
    ):
        color_1 = props.color_1
        color_2 = props.color_2
        self.segment_num = segment_num
        self.type = type
        self.base_name = base_name
        self.use_macros = use_macros
        self.header_suffix = f"_{index:02}"
        self.name = f"{self.base_name}{suffix}ColorSwitchParams{self.header_suffix}"
        self.prim_colors: list[tuple[int, int, int, int, int]] = []
        self.env_colors: list[tuple[int, int, int, int]] = [(-1, -1, -1, -1), (-1, -1, -1, -1)]
        self.use_env_colors: list[bool] = [self.bool_to_c(color_1.use_env_color), self.bool_to_c(color_2.use_env_color)]

        prim = exportColor(color_1.prim_color[0:3]) + [scaleToU8(color_1.prim_color[3])]
        self.prim_colors.append((prim[0], prim[1], prim[2], prim[3], color_1.prim_lod_frac))
        if color_1.use_env_color:
            self.env_colors[0] = tuple(exportColor(color_1.env_color[0:3]) + [scaleToU8(color_1.env_color[3])])

        prim = exportColor(color_2.prim_color[0:3]) + [scaleToU8(color_2.prim_color[3])]
        self.prim_colors.append((prim[0], prim[1], prim[2], prim[3], color_2.prim_lod_frac))
        if color_2.use_env_color:
            self.env_colors[1] = tuple(exportColor(color_2.env_color[0:3]) + [scaleToU8(color_2.env_color[3])])

        assert len(self.prim_colors) == 2, "ERROR: unexpected prim color list length"

    def bool_to_c(self, value: bool):
        return "true" if value else "false"

    def to_c(self, all_externs: bool = True):
        data = CData()
        params_name = f"AnimatedMatColorSwitchParams {self.name}"

        # .h
        if all_externs:
            data.header = f"extern {params_name};\n"

        # .c
        data.source = (
            (params_name + " = {\n")
            + indent
            + "{ "
            + f", ".join(
                "{ " + f"{entry[0]}, {entry[1]}, {entry[2]}, {entry[3]}, {entry[4]}" + " }"
                for entry in self.prim_colors
            )
            + " },\n"
            + indent
            + "{ "
            + f", ".join("{ " + f"{entry[0]}, {entry[1]}, {entry[2]}, {entry[3]}" + " }" for entry in self.env_colors)
            + " },\n"
            + indent
            + "{ "
            + f"{self.use_env_colors[0]}, {self.use_env_colors[1]}"
            + " },\n"
            + "};\n\n"
        )

        return data


class AnimatedMaterial:
    def __init__(
        self,
        props: Z64_AnimatedMaterial,
        base_name: str,
        use_macros: bool,
        col_header: CollisionHeader,
        suffix: str = "",
    ):
        self.name = base_name
        self.entries = []
        self.event_map: dict[int, tuple[str, str, CData]] = {}  # type index to event data
        self.cam_type = (
            game_data.z64.get_enum_value("anim_mats_cam_type", props.cam_type)
            if props.cam_type != "Custom"
            else props.cam_type_custom
        )
        self.cam_on_event = "true" if props.cam_on_event and self.cam_type != "anim_mat_camera_type_none" else "false"

        if len(props.entries) == 0:
            return

        type_list_map: dict[str, tuple[Any, Optional[str]]] = {
            "anim_mat_type_tex_scroll": (AnimatedMatTexScrollParams, "tex_scroll_params"),
            "anim_mat_type_two_tex_scroll": (AnimatedMatTexScrollParams, "tex_scroll_params"),
            "anim_mat_type_color": (AnimatedMatColorParams, "color_params"),
            "anim_mat_type_color_lerp": (AnimatedMatColorParams, "color_params"),
            "anim_mat_type_color_nonlinear_interp": (AnimatedMatColorParams, "color_params"),
            "anim_mat_type_tex_cycle": (AnimatedMatTexCycleParams, "tex_cycle_params"),
            "anim_mat_type_color_cycle": (AnimatedMatColorParams, "color_params"),
            "anim_mat_type_tex_timed_cycle": (AnimatedMatTexTimedCycleParams, "tex_timed_cycle_params"),
            "anim_mat_type_texture": (AnimatedMatTextureParams, "texture_params"),
            "anim_mat_type_multitexture": (AnimatedMatMultiTextureParams, "multitexture_params"),
            "anim_mat_type_event": (AnimatedMatEventParams, None),
            "anim_mat_type_surface_swap": (AnimatedMatSurfaceSwapParams, "surface_params"),
            "anim_mat_type_oscillating_two_tex": (AnimatedMatTexScrollParams, "tex_scroll_params"),
            "anim_mat_type_color_switch": (AnimatedMatColorSwitchParams, "color_switch_params"),
        }

        for i, item in enumerate(props.entries):
            type = item.type if item.type != "Custom" else item.type_custom
            if type != "Custom" and type != "anim_mat_type_none":
                class_def, prop_name = type_list_map[type]
                props = getattr(item, prop_name) if type != "anim_mat_type_event" else None
                self.entries.append(
                    class_def(props, item.segment_num, type, base_name, i, use_macros, col_header, suffix)
                )
                script_data = item.events.export(base_name, i)
                if script_data is not None:
                    data_name, script_name = item.events.get_symbols(base_name, i)
                    self.event_map[i] = (data_name, script_name, script_data)

    def to_c(self, all_externs: bool = True):
        data = CData()

        is_extended = is_hackeroot()

        for i, entry in enumerate(self.entries):
            data.append(entry.to_c(all_externs))

            if is_extended and len(self.event_map) > 0 and i in self.event_map:
                _, _, event_data = self.event_map[i]
                if all_externs:
                    data.header += event_data.header

                data.source += event_data.source

        array_name = f"AnimatedMaterial {self.name}[]"

        # .h
        data.header += f"extern {array_name};\n"

        # .c
        data.source += array_name + " = {\n" + indent

        if len(self.entries) > 0:
            entries = []
            for i, entry in enumerate(self.entries):
                if not is_extended:
                    script_name = ""
                elif len(self.event_map) > 0 and i in self.event_map:
                    _, script_name, _ = self.event_map[i]
                    script_name = f" &{script_name},"
                else:
                    script_name = " NULL,"

                entries.append(
                    f"MATERIAL_SEGMENT_NUM(0x{entry.segment_num:02X}), "
                    + f"{game_data.z64.get_enum_value('anim_mats_type', entry.type)}, "
                    + (
                        f"{'&' if 'tex_scroll' not in entry.type else ''}{entry.name},"
                        if entry.type != "anim_mat_type_event"
                        else "NULL,"
                    )
                    + script_name
                )

            # the last entry's segment need to be negative
            if len(self.entries) > 0 and self.entries[-1].segment_num > 0:
                entries[-1] = f"LAST_{entries[-1]}"

            data.source += f"\n{indent}".join("{ " + entry + " }," for entry in entries)
        else:
            data.source += "{ 0, 6, NULL, NULL }," if is_extended else "{ 0, 6, NULL },"

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
    def new(name: str, props: OOTSceneHeaderProperty, is_reuse: bool, use_macros: bool, col_header: CollisionHeader):
        return SceneAnimatedMaterial(
            name, AnimatedMaterial(props.animated_material, name, use_macros, col_header) if not is_reuse else None
        )

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
            export_path = Path(bpy.path.abspath(settings.export_path))
            export_path.mkdir(exist_ok=True)
        else:
            export_path = bpy.context.scene.fast64.oot.get_decomp_path() / "assets" / "objects" / settings.object_name

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
        import_path = Path(bpy.path.abspath(settings.import_path)).resolve()

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

        if is_hackeroot():
            am = self.animated_material
            assert am is not None
            cmd = f"SCENE_CMD_ANIMATED_MATERIAL_LIST({self.name}, MATERIAL_CAM_PARAMS({am.cam_type}, {am.cam_on_event})),\n"
        else:
            cmd = f"SCENE_CMD_ANIMATED_MATERIAL_LIST({self.name}),\n"

        if is_hackeroot() and bpy.context.scene.fast64.oot.hackeroot_settings.export_ifdefs:
            return "#if ENABLE_ANIMATED_MATERIALS\n" + indent + cmd + "#endif\n"
        else:
            return indent + cmd

    def to_c(self, is_scene: bool = True):
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
            data.header += ("\n" if not is_scene else "") + extra

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

from dataclasses import dataclass
from bpy.types import Object
from ....utility import CData, PluginError, exportColor, scaleToU8, indent
from ...utility import getObjectList
from ...animated_mats.properties import (
    Z64_AnimatedMatColorParams,
    Z64_AnimatedMatTexScrollParams,
    Z64_AnimatedMatTexCycleParams,
    Z64_AnimatedMaterial,
)


class AnimatedMatColorParams:
    def __init__(
        self,
        props: Z64_AnimatedMatColorParams,
        segment_num: int,
        type_num: int,
        base_name: str,
        header_index: int,
        index: int,
    ):
        # the code adds back 7 when processing animated materials
        self.segment_num = segment_num - 7
        self.type_num = type_num
        self.base_name = base_name
        self.header_index = header_index
        self.header_suffix = f"_{index:02}"
        self.name = f"{self.base_name}ColorParams{self.header_suffix}"
        self.frame_length = props.frame_count
        self.prim_colors: list[tuple[int, int, int, int]] = []
        self.env_colors: list[tuple[int, int, int]] = []
        self.frames: list[int] = []

        for keyframe in props.keyframes:
            prim = exportColor(keyframe.prim_color[0:3]) + [scaleToU8(keyframe.prim_color[3])]
            self.prim_colors.append((prim[0], prim[1], prim[2], prim[3], keyframe.prim_lod_frac))
            self.env_colors.append(tuple(exportColor(keyframe.env_color[0:3]) + [scaleToU8(keyframe.env_color[3])]))
            self.frames.append(keyframe.frame_num)

            if keyframe.frame_num > self.frame_length:
                raise PluginError("ERROR: the frame number cannot be higher than the total frame count!")

        self.frame_count = len(self.frames)
        assert len(self.frames) == len(self.prim_colors) == len(self.env_colors)

    def to_c(self):
        data = CData()
        prim_array_name = f"{self.base_name}ColorPrimColor{self.header_suffix}"
        env_array_name = f"{self.base_name}ColorEnvColor{self.header_suffix}"
        frames_array_name = f"{self.base_name}ColorKeyFrames{self.header_suffix}"
        params_name = f"AnimatedMatColorParams {self.name}"

        # .h
        data.header = (
            f"extern F3DPrimColor {prim_array_name}[];\n"
            + f"extern F3DEnvColor {env_array_name}[];\n"
            + f"extern u16 {frames_array_name}[];\n"
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
                (f"F3DEnvColor {env_array_name}[]" + " = {\n" + indent)
                + f",\n{indent}".join(
                    "{ " + f"{entry[0]}, {entry[1]}, {entry[2]}, {entry[3]}" + " }" for entry in self.env_colors
                )
                + "\n};\n\n"
            )
            + (
                (f"u16 {frames_array_name}[]" + " = {\n" + indent)
                + f",\n{indent}".join(f"{entry}" for entry in self.frames)
                + "\n};\n\n"
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
        header_index: int,
        index: int,
    ):
        # the code adds back 7 when processing animated materials
        self.segment_num = segment_num - 7
        self.type_num = type_num
        self.base_name = base_name
        self.header_index = header_index
        self.header_suffix = f"_{index:02}"
        self.name = f"{self.base_name}TexScrollParams{self.header_suffix}"
        self.entries: list[str] = []

        for item in props.entries:
            self.entries.append("{ " + f"{item.step_x}, {item.step_y}, {item.width}, {item.height}" + " }")

    def to_c(self):
        data = CData()
        params_name = f"AnimatedMatTexScrollParams {self.name}[]"

        # .h
        data.header = f"extern {params_name};\n"

        # .c
        data.source = (
            f"{params_name}" + " = {\n" + indent + f",\n{indent}".join(entry for entry in self.entries) + "\n};\n\n"
        )

        return data


class AnimatedMatTexCycleParams:
    def __init__(
        self,
        props: Z64_AnimatedMatTexCycleParams,
        segment_num: int,
        type_num: int,
        base_name: str,
        header_index: int,
        index: int,
    ):
        # the code adds back 7 when processing animated materials
        self.segment_num = segment_num - 7
        self.type_num = type_num
        self.base_name = base_name
        self.header_index = header_index
        self.header_suffix = f"_{index:02}"
        self.name = f"{self.base_name}TexCycleParams{self.header_suffix}"
        self.textures: list[str] = []
        self.frames: list[int] = []

        for keyframe in props.keyframes:
            self.textures.append(keyframe.texture)
            self.frames.append(keyframe.frame_num)

    def to_c(self):
        data = CData()
        texture_array_name = f"{self.base_name}CycleTextures{self.header_suffix}"
        frame_array_name = f"{self.base_name}CycleKeyFrames{self.header_suffix}"
        params_name = f"AnimatedMatTexCycleParams {self.name}"

        # .h
        data.header = (
            f"extern TexturePtr {texture_array_name}[];\n"
            + f"extern u8 {frame_array_name}[];\n"
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
                (f"u8 {frame_array_name}[]" + " = {\n")
                + indent
                + ", ".join(f"{frame}" for frame in self.frames)
                + "\n};\n\n"
            )
            + (
                (params_name + " = {\n")
                + indent
                + f"{len(self.frames)}, {texture_array_name}, {frame_array_name},"
                + "\n};\n\n"
            )
        )

        return data


class AnimatedMaterial:
    def __init__(self, props: Z64_AnimatedMaterial, base_name: str, scene_header_index: int):
        self.name = base_name
        self.scene_header_index = scene_header_index
        self.header_index = props.header_index
        self.entries: list[AnimatedMatColorParams | AnimatedMatTexScrollParams | AnimatedMatTexCycleParams] = []

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
            if item.type != "Custom":
                class_def, prop_name, type_num = type_list_map[item.type]
                # example: `self.tex_scroll_entries.append(AnimatedMatTexScrollParams(item.tex_scroll_params, base_name, header_index))`
                self.entries.append(
                    class_def(getattr(item, prop_name), item.segment_num, type_num, base_name, self.header_index, i)
                )

        # the last entry's segment need to be negative
        if len(self.entries) > 0 and self.entries[-1].segment_num > 0:
            self.entries[-1].segment_num = -self.entries[-1].segment_num

    def to_c(self):
        data = CData()

        for entry in self.entries:
            if entry.header_index == -1 or entry.header_index == self.scene_header_index:
                data.append(entry.to_c())

        if len(self.entries) > 0:
            array_name = f"AnimatedMaterial {self.name}[]"

            # .h
            data.header += f"extern {array_name};"

            # .c
            data.source += (
                (array_name + " = {\n" + indent)
                + f",\n{indent}".join(
                    "{ "
                    + f"{entry.segment_num} /* {abs(entry.segment_num) + 7} */, "
                    + f"{entry.type_num}, "
                    + f"{'&' if entry.type_num in {2, 3, 4, 5} else ''}{entry.name}"
                    + " }"
                    for entry in self.entries
                )
                + "\n};\n\n"
            )
        else:
            raise PluginError("ERROR: Trying to export animated materials with empty entries!")

        return data


@dataclass
class SceneAnimatedMaterial:
    """This class hosts exit data"""

    name: str
    header_index: int
    entries: list[AnimatedMaterial]

    @staticmethod
    def new(name: str, scene_obj: Object, header_index: int):
        obj_list = getObjectList(scene_obj.children_recursive, "EMPTY", "Animated Materials")
        entries: list[AnimatedMaterial] = []

        for obj in obj_list:
            if obj.z64_anim_mats_property.mode == "Scene":
                entries.extend(
                    [AnimatedMaterial(item, name, header_index) for item in obj.z64_anim_mats_property.items]
                )

        last_index = -1
        for entry in entries:
            if entry.header_index >= 0:
                if entry.header_index > last_index:
                    last_index = entry.header_index
                else:
                    raise PluginError("ERROR: Animated Materials header indices are not consecutives!")

        return SceneAnimatedMaterial(name, header_index, entries)

    def get_cmd(self):
        """Returns the sound settings, misc settings, special files and skybox settings scene commands"""

        return indent + f"SCENE_CMD_ANIMATED_MATERIAL_LIST({self.name}),\n"

    def to_c(self):
        data = CData()

        for entry in self.entries:
            data.append(entry.to_c())

        return data

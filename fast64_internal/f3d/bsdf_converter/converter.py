import numpy as np
import dataclasses
import typing
import math

import bpy
from bpy.types import (
    Mesh,
    Object,
    Material,
    ShaderNodeOutputMaterial,
    ShaderNodeBsdfPrincipled,
    ShaderNodeMixShader,
    ShaderNodeBsdfTransparent,
    ShaderNodeBackground,
    ShaderNodeMath,
    ShaderNodeMixRGB,
    ShaderNodeVertexColor,
    ShaderNodeTexCoord,
    ShaderNodeUVMap,
    ShaderNodeTexImage,
    ShaderNodeMapping,
    ShaderNode,
)

from ...utility import get_clean_color, colorToLuminance, PluginError

from ..f3d_material import (
    combiner_uses,
    createF3DMat,
    get_output_method,
    getDefaultMaterialPreset,
    is_mat_f3d,
    all_combiner_uses,
    set_blend_to_output_method,
    trunc_10_2,
    update_all_node_values,
    convertColorAttribute,
    F3DMaterialProperty,
    RDPSettings,
    TextureProperty,
    TextureFieldProperty,
    CombinerProperty,
)
from ..f3d_gbi import isUcodeF3DEX3
from ..f3d_writer import getColorLayer


# Ideally we'd use mathutils.Color here but it does not support alpha (and mul for some reason)
@dataclasses.dataclass
class Color:
    r: float = 1.0
    g: float = 1.0
    b: float = 1.0
    a: float = 1.0

    def wrap(self, min_value: float, max_value: float):
        def wrap_value(value, min_value=min_value, max_value=max_value):
            range_width = max_value - min_value
            return ((value - min_value) % range_width) + min_value

        return Color(wrap_value(self.r), wrap_value(self.g), wrap_value(self.b), wrap_value(self.a))

    def to_clean_list(self):
        def round_and_clamp(value):
            return round(max(min(value, 1.0), 0.0), 4)

        return [
            round_and_clamp(self.r),
            round_and_clamp(self.g),
            round_and_clamp(self.b),
            round_and_clamp(self.a),
        ]

    def __sub__(self, other):
        return Color(self.r - other.r, self.g - other.g, self.b - other.b, self.a - other.a)

    def __add__(self, other):
        return Color(self.r + other.r, self.g + other.g, self.b + other.b, self.a + other.a)

    def __mul__(self, other):
        return Color(self.r * other.r, self.g * other.g, self.b * other.b, self.a * other.a)

    def __iter__(self):
        yield self.r
        yield self.g
        yield self.b
        yield self.a

    def __getitem__(self, key: int):
        return list(self)[key]


def get_color_component(inp: str, f3d_mat: F3DMaterialProperty, previous_alpha: float) -> float:
    if inp == "0":
        return 0.0
    elif inp == "1":
        return 1.0
    elif inp.startswith("COMBINED"):
        return previous_alpha
    elif inp == "LOD_FRACTION":
        return 0.0  # Fast64 always uses black, let's do that for now
    elif inp == "PRIM_LOD_FRAC":
        return f3d_mat.prim_lod_frac
    elif inp == "PRIMITIVE_ALPHA":
        return f3d_mat.prim_color[3]
    elif inp == "ENV_ALPHA":
        return f3d_mat.env_color[3]
    elif inp == "K4":
        return f3d_mat.k4
    elif inp == "K5":
        return f3d_mat.k5


def get_color_from_input(inp: str, previous_color: Color, f3d_mat: F3DMaterialProperty, is_alpha: bool) -> Color:
    if inp == "COMBINED" and not is_alpha:
        return previous_color
    elif inp == "CENTER":
        return Color(*get_clean_color(f3d_mat.key_center), previous_color.a)
    elif inp == "SCALE":
        return Color(*list(f3d_mat.key_scale), previous_color.a)
    elif inp == "PRIMITIVE":
        return Color(*get_clean_color(f3d_mat.prim_color, True))
    elif inp == "ENVIRONMENT":
        return Color(*get_clean_color(f3d_mat.env_color, True))
    elif inp == "SHADE":
        if f3d_mat.rdp_settings.g_lighting and f3d_mat.set_lights and f3d_mat.use_default_lighting:
            return Color(*get_clean_color(f3d_mat.default_light_color), previous_color.a)
        return Color(1.0, 1.0, 1.0, previous_color.a)
    else:
        value = get_color_component(inp, f3d_mat, previous_color.a)
        if value is not None:
            return Color(value, value, value, value)
        return Color(1.0, 1.0, 1.0, 1.0)


def fake_color_from_cycle(cycle: list[str], previous_color: Color, f3d_mat: F3DMaterialProperty, is_alpha=False):
    a, b, c, d = [get_color_from_input(inp, previous_color, f3d_mat, is_alpha) for inp in cycle]
    sign_extended_c = c.wrap(-1.0, 1.0001)
    unwrapped_result = (a - b) * sign_extended_c + d
    result = unwrapped_result.wrap(-0.5, 1.5)
    if is_alpha:
        result = Color(previous_color.r, previous_color.g, previous_color.b, result.a)
    return result


def get_fake_color(f3d_mat: F3DMaterialProperty):
    """Try to emulate solid colors"""
    fake_color = Color()
    cycle: CombinerProperty
    combiners = [f3d_mat.combiner1]
    if f3d_mat.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE":
        combiners.append(f3d_mat.combiner2)
    for cycle in combiners:
        fake_color = fake_color_from_cycle([cycle.A, cycle.B, cycle.C, cycle.D], fake_color, f3d_mat)
        fake_color = fake_color_from_cycle(
            [cycle.A_alpha, cycle.B_alpha, cycle.C_alpha, cycle.D_alpha], fake_color, f3d_mat, True
        )
    return fake_color.to_clean_list()


@dataclasses.dataclass
class AbstractedN64Texture:
    """Very abstracted representation of a N64 texture"""

    tex: bpy.types.Image
    offset: tuple[float, float] = (0.0, 0.0)
    scale: tuple[float, float] = (1.0, 1.0)
    repeat: bool = False
    set_color: bool = False
    set_alpha: bool = False
    packed_alpha: bool = False
    alpha_as_color: bool = False  # tex0 alpha, gathered in bsdf to f3d


@dataclasses.dataclass
class AbstractedN64Material:
    """Very abstracted representation of a N64 material"""

    lighting: bool = False
    uv_gen: bool = False
    point_filtering: bool = False
    vertex_color: str | None | bool = False
    vertex_alpha: str | None | bool = False
    alpha_is_median: bool = False
    backface_culling: bool = False
    output_method: str = "OPA"
    color: Color = dataclasses.field(default_factory=Color)
    textures: list[AbstractedN64Texture] = dataclasses.field(default_factory=list)
    texture_sets_col: bool = False
    texture_sets_alpha: bool = False
    uv_map: str = ""

    @property
    def main_texture(self):
        return self.textures[0] if self.textures else None


def f3d_tex_to_abstracted(f3d_tex: TextureProperty, set_color: bool, set_alpha: bool):
    def to_offset(low: float, tex_size: int):
        offset = -trunc_10_2(low) * (1.0 / tex_size)
        if offset == -0.0:
            offset = 0.0
        return offset

    if f3d_tex.tex is None:
        print("No texture set")

    abstracted_tex = AbstractedN64Texture(f3d_tex.tex, repeat=not f3d_tex.S.clamp or not f3d_tex.T.clamp)
    size = f3d_tex.tex_size
    if size != [0, 0]:
        abstracted_tex.offset = (to_offset(f3d_tex.S.low, size[0]), to_offset(f3d_tex.T.low, size[1]))
    abstracted_tex.scale = (2.0 ** (f3d_tex.S.shift * -1.0), 2.0 ** (f3d_tex.T.shift * -1.0))
    abstracted_tex.set_color, abstracted_tex.set_alpha = set_color, set_alpha
    abstracted_tex.packed_alpha = f3d_tex.tex_format in {"I4", "I8"}

    return abstracted_tex


def f3d_mat_to_abstracted(material: Material):
    f3d_mat: F3DMaterialProperty = material.f3d_mat
    rdp: RDPSettings = f3d_mat.rdp_settings
    use_dict = all_combiner_uses(f3d_mat)
    textures = [f3d_mat.tex0] if use_dict["Texture 0"] and f3d_mat.tex0.tex_set else []
    textures += [f3d_mat.tex1] if use_dict["Texture 1"] and f3d_mat.tex1.tex_set else []
    g_packed_normals = rdp.g_packed_normals if isUcodeF3DEX3(bpy.context.scene.f3d_type) else False
    abstracted_mat = AbstractedN64Material(
        rdp.g_lighting and use_dict["Shade"],
        rdp.g_tex_gen and rdp.g_lighting,
        rdp.g_mdsft_text_filt == "G_TF_POINT",
        (not rdp.g_lighting or g_packed_normals) and combiner_uses(f3d_mat, ["SHADE"], checkAlpha=False),
        not rdp.g_fog and combiner_uses(f3d_mat, ["SHADE"], checkColor=False),
        False,
        rdp.g_cull_back,
        get_output_method(material, True),
        get_fake_color(f3d_mat),
    )
    for i in range(2):
        tex_prop = getattr(f3d_mat, f"tex{i}")
        check_list = [f"TEXEL{i}", f"TEXEL{i}_ALPHA"]
        sets_color = combiner_uses(f3d_mat, check_list, checkColor=True, checkAlpha=False)
        sets_alpha = combiner_uses(f3d_mat, check_list, checkColor=False, checkAlpha=True)
        if sets_color or sets_alpha:
            abstracted_mat.textures.append(f3d_tex_to_abstracted(tex_prop, sets_color, sets_alpha))
        abstracted_mat.texture_sets_col |= sets_color
        abstracted_mat.texture_sets_alpha |= sets_alpha
    # print(abstracted_mat)
    return abstracted_mat


def material_to_bsdf(material: Material, put_alpha_into_color=False):
    abstracted_mat = f3d_mat_to_abstracted(material)

    target_name = f"{material.name}_bsdf"
    new_material = bpy.data.materials.new(name=target_name)
    new_material.use_nodes = True
    nodes = new_material.node_tree.nodes
    links = new_material.node_tree.links
    nodes.clear()

    set_blend_to_output_method(new_material, abstracted_mat.output_method)
    new_material.use_backface_culling = abstracted_mat.backface_culling
    new_material.alpha_threshold = 0.125

    node_x = node_y = alpha_y_offset = 0

    def set_location(node, set_x=False, x_offset=0, y_offset=0):  # some polish stuff
        nonlocal node_x, node_y
        node.location = (node_x - node.width + x_offset, node_y + y_offset)
        if set_x:
            node_x -= padded_from_node(node)

    def padded_from_node(node):
        return node.width + 50

    T = typing.TypeVar("T")

    def create_node(typ: T, name: str, location=False, x_offset=0, y_offset=0):
        node: T = nodes.new(typ.__name__)
        node.name = node.label = name
        set_location(node, location, x_offset=x_offset, y_offset=y_offset)
        return node

    output_node = create_node(ShaderNodeOutputMaterial, "Output", True)
    node_y -= 25

    # final shader node
    if abstracted_mat.lighting:
        print("Creating bsdf principled shader node")
        shader_node = create_node(ShaderNodeBsdfPrincipled, "Shader", True)
        links.new(shader_node.outputs[0], output_node.inputs[0])
        alpha_input = shader_node.inputs["Alpha"]
        color_input = shader_node.inputs["Base Color"]
        if bpy.data.version >= (4, 2, 0):
            node_y -= 22
            alpha_y_offset -= 88
        else:
            node_y -= 80
            alpha_y_offset -= 462
    else:  # use a mix shader of transparent bsdf and background and use fac as alpha
        print("Creating unlit shader node")
        mix_shader = create_node(ShaderNodeMixShader, "Mix Shader", True)
        links.new(mix_shader.outputs[0], output_node.inputs[0])
        alpha_input = mix_shader.inputs["Fac"]

        transparent_node = create_node(ShaderNodeBsdfTransparent, "Transparency Shader", y_offset=-47)
        links.new(transparent_node.outputs[0], mix_shader.inputs[1])
        alpha_y_offset += transparent_node.height + 47

        background_node = create_node(
            ShaderNodeBackground, "Background Shader", True, y_offset=-47 - transparent_node.height
        )
        links.new(background_node.outputs[0], mix_shader.inputs[2])
        color_input = background_node.inputs["Color"]
        node_y -= 172

    # cutout is removed in 4.2, it relies on the math node, glTF exporter supports this of course.
    if bpy.app.version >= (4, 2, 0) and abstracted_mat.output_method == "CLIP":
        print("Creating alpha clip node")
        alpha_clip = create_node(ShaderNodeMath, "Alpha Clip", True, y_offset=alpha_y_offset)
        alpha_clip.operation = "GREATER_THAN"
        alpha_clip.use_clamp = True
        alpha_clip.inputs[1].default_value = 0.125
        links.new(alpha_clip.outputs[0], alpha_input)
        alpha_input = alpha_clip.inputs[0]

    vertex_color = None
    vertex_color_mul = None
    if abstracted_mat.vertex_color:  # create vertex color mul node
        print("Creating vertex color node, mix rgb node and setting color input")
        vertex_color_mul = create_node(ShaderNodeMixRGB, "Vertex Color Mul", True)
        vertex_color_mul.use_clamp, vertex_color_mul.blend_type = True, "MULTIPLY"
        vertex_color_mul.inputs[0].default_value = 1
        links.new(vertex_color_mul.outputs[0], color_input)
        color_input = vertex_color_mul.inputs[2]
    if abstracted_mat.vertex_alpha:  # create vertex alpha mul node
        print("Creating vertex alpha node, mul node and setting color input")
        vertex_alpha_mul = create_node(ShaderNodeMath, "Vertex Alpha Mul", True, y_offset=alpha_y_offset)
        vertex_alpha_mul.use_clamp, vertex_alpha_mul.operation = True, "MULTIPLY"
        links.new(vertex_alpha_mul.outputs[0], alpha_input)
        alpha_input = vertex_alpha_mul.inputs[1]

    # create vertex color node
    if abstracted_mat.vertex_color or (put_alpha_into_color and abstracted_mat.vertex_alpha):
        vertex_color = create_node(
            ShaderNodeVertexColor, "Vertex Color", True, y_offset=0 if abstracted_mat.vertex_color else alpha_y_offset
        )
        vertex_color.layer_name = "Col"
    if abstracted_mat.vertex_color:  # link vertex color to vertex color mul
        links.new(vertex_color.outputs[0], vertex_color_mul.inputs[1])
    if abstracted_mat.vertex_alpha:
        if put_alpha_into_color:  # link vertex color's alpha to vertex alpha mul
            links.new(vertex_color.outputs[1], vertex_alpha_mul.inputs[0])
        else:  # create vertex alpha node
            vertex_alpha = create_node(ShaderNodeVertexColor, "Vertex Alpha", True, y_offset=alpha_y_offset)
            vertex_alpha.layer_name = "Alpha"
            links.new(vertex_alpha.outputs[0], vertex_alpha_mul.inputs[0])

    # support for glTF base color which gets multiplied on to textures
    mix_rgb = False
    if abstracted_mat.texture_sets_col and abstracted_mat.color[:3] != [1.0, 1.0, 1.0]:
        print(f"Creating color mul node {abstracted_mat.color} and setting color input")
        color_mul = create_node(ShaderNodeMixRGB, "Color Mul")
        color_mul.use_clamp, color_mul.blend_type = True, "MULTIPLY"
        color_mul.inputs[0].default_value = 1
        color_mul.inputs[1].default_value = abstracted_mat.color
        links.new(color_mul.outputs[0], color_input)
        color_input = color_mul.inputs[2]
        mix_rgb = True
    if abstracted_mat.texture_sets_alpha and abstracted_mat.color[3] != 1.0 and abstracted_mat.output_method != "OPA":
        print(f"Setting alpha mul node {abstracted_mat.color[3]} and setting alpha input")
        alpha_mul = create_node(ShaderNodeMath, "Alpha Mul", y_offset=alpha_y_offset)
        alpha_mul.use_clamp, alpha_mul.operation = True, "MULTIPLY"
        alpha_mul.inputs[0].default_value = abstracted_mat.color[3]
        links.new(alpha_mul.outputs[0], alpha_input)
        alpha_input = alpha_mul.inputs[1]
        mix_rgb = True
    if mix_rgb:
        node_x -= 140 + 50

    uv_map_output = None
    if abstracted_mat.textures:  # create uv_map
        if abstracted_mat.uv_gen:
            print("Creating generated UVmap node (Camera output)")
            uv_map_node = create_node(ShaderNodeTexCoord, "UVMap")
            uv_map_output = uv_map_node.outputs["Camera"]
        else:
            print("Creating UVmap node")
            uv_map_node = create_node(ShaderNodeUVMap, "UVMap")
            uv_map_node.uv_map = "UVMap"
            uv_map_output = uv_map_node.outputs["UV"]

    tex_color_inputs = [color_input, None]
    tex_alpha_inputs = [alpha_input, None]
    assert len(abstracted_mat.textures) <= 2, "Too many textures"
    if len(abstracted_mat.textures) == 2:
        if all(abstracted_tex.set_color for abstracted_tex in abstracted_mat.textures):
            print("Creating mix rgb node for multi texture, setting color input")
            color_mul = create_node(ShaderNodeMixRGB, "Multitexture Color Mul", True)
            color_mul.use_clamp, color_mul.blend_type = True, "MULTIPLY"
            color_mul.inputs[0].default_value = 1
            tex_color_inputs = [color_mul.inputs[1], color_mul.inputs[2]]
            links.new(color_mul.outputs[0], color_input)
        if all(abstracted_tex.set_alpha for abstracted_tex in abstracted_mat.textures):
            print("Creating mix rgb node for multi texture, setting alpha input")
            alpha_mul = create_node(ShaderNodeMath, "Multitexture Alpha Mul", True, y_offset=alpha_y_offset)
            alpha_mul.use_clamp, alpha_mul.operation = True, "MULTIPLY"
            tex_alpha_inputs = [alpha_mul.inputs[0], alpha_mul.inputs[1]]
            links.new(alpha_mul.outputs[0], alpha_input)

    tex_x_offset = tex_y_offset = 0
    texture_nodes = []
    for abstracted_tex, tex_color_input, tex_alpha_input in zip(
        abstracted_mat.textures, tex_color_inputs, tex_alpha_inputs
    ):  # create invidual texture nodes and link them
        tex_node = create_node(ShaderNodeTexImage, "Texture", y_offset=tex_y_offset)
        tex_node.image = abstracted_tex.tex
        tex_node.extension = "REPEAT" if abstracted_tex.repeat else "EXTEND"
        tex_node.interpolation = "Closest" if abstracted_mat.point_filtering else "Linear"
        texture_nodes.append(tex_node)
        new_x_offset = -padded_from_node(tex_node)
        tex_y_offset -= (tex_node.height * 2) + 125

        assert uv_map_output
        if abstracted_tex.offset != (0.0, 0.0) or abstracted_tex.scale != (1.0, 1.0):
            mapping_node = create_node(ShaderNodeMapping, "Mapping", x_offset=new_x_offset, y_offset=tex_y_offset + 98)
            mapping_node.vector_type = "POINT"
            tex_y_offset -= mapping_node.height
            mapping_node.inputs["Location"].default_value = abstracted_tex.offset + (0.0,)
            mapping_node.inputs["Scale"].default_value = abstracted_tex.scale + (1.0,)
            links.new(uv_map_output, mapping_node.inputs[0])
            links.new(mapping_node.outputs[0], tex_node.inputs[0])

            new_x_offset -= padded_from_node(mapping_node)
        else:
            links.new(uv_map_output, tex_node.inputs[0])

        if abstracted_tex.set_color:
            links.new(tex_node.outputs[0], tex_color_input)
        if abstracted_tex.set_alpha:
            if abstracted_tex.packed_alpha:  # i4/i8
                links.new(tex_node.outputs[0], tex_alpha_input)
            else:
                links.new(tex_node.outputs[1], tex_alpha_input)

        if new_x_offset < tex_x_offset:
            tex_x_offset = new_x_offset
    node_x += tex_x_offset  # update node location

    if abstracted_mat.textures:  # update uv_map node location
        if len(abstracted_mat.textures) > 1:
            node_y += tex_y_offset / len(texture_nodes)
        else:
            node_y -= 30
        set_location(uv_map_node, True)

    color_input.default_value = abstracted_mat.color[:3] + [1.0]
    alpha_input.default_value = abstracted_mat.color[3]

    return new_material


def apply_alpha(blender_mesh: Mesh):
    color_layer = getColorLayer(blender_mesh, layer="Col")
    alpha_layer = getColorLayer(blender_mesh, layer="Alpha")
    if not color_layer or not alpha_layer:
        return
    color = np.empty(len(blender_mesh.loops) * 4, dtype=np.float32)
    alpha = np.empty(len(blender_mesh.loops) * 4, dtype=np.float32)
    color_layer.foreach_get("color", color)
    alpha_layer.foreach_get("color", alpha)
    alpha = alpha.reshape(-1, 4)
    color = color.reshape(-1, 4)

    # Calculate alpha from the median of the alpha layer RGB
    alpha_median = np.median(alpha[:, :3], axis=1)
    color[:, 3] = alpha_median

    color = color.flatten()
    color_layer.foreach_set("color", color)


def find_output_node(material: Material):
    if not material.use_nodes:
        return None
    for node in material.node_tree.nodes:
        if isinstance(node, ShaderNodeOutputMaterial) and node.is_active_output:
            return node
    return None


def find_mix_shader_with_transparent(material: Material):
    """
    Find mix shader with transparent BSDF, return first one's Fac input and the non transparent BSDF input
    """
    output_node = find_output_node(material)
    if output_node is None:
        return (None, None)

    # check if transparent bsdf is connected
    shaders: list[tuple[ShaderNodeMixShader, ShaderNode, ShaderNode]] = []
    for mix_shader in find_linked_nodes(output_node, lambda node: node.bl_idname == "ShaderNodeMixShader"):
        transparent, non_transparent = None, None
        for inp in mix_shader.inputs:
            if inp.name == "Fac" and not inp.links:
                continue
            link = inp.links[0]
            if link.from_node.bl_idname == "ShaderNodeBsdfTransparent":
                transparent = link.from_node
            else:
                non_transparent = link.from_node
        if transparent and non_transparent:
            shaders.append((mix_shader, transparent, non_transparent))

    if len(shaders) == 0:
        return (None, None)
    if len(shaders) > 1:
        print(f"WARNING: More than 1 transparent shader connected to a mix shader in {material.name}. Using first one.")
    mix_shader, _transparent_bsdf, non_transparent_bsdf = shaders[0]

    return mix_shader, non_transparent_bsdf


def find_linked_nodes(
    starting_node: ShaderNode | None,
    node_check: callable,
    specific_input_sockets: list[str] | None = None,
    specific_output_sockets: list[str] | None = None,
    verbose=False,  # small debug feature
):
    if starting_node is None:
        return []
    nodes: list[ShaderNode] = []
    for inp in starting_node.inputs:
        if specific_input_sockets is not None and inp.name not in specific_input_sockets:
            continue
        if verbose:
            print(f"Searching from {inp.name}")
        for link in inp.links:
            if specific_output_sockets is None or link.from_socket.name in specific_output_sockets:
                if verbose:
                    print(f"Checking {link.from_node.bl_idname} {link.from_socket.name}")
                if node_check(link.from_node):
                    nodes.append(link.from_node)
                    if verbose:
                        print("Valid node added, recursive search is skipped")
                    continue
            elif verbose:
                print(f"Skipped output socket {link.from_socket.name}")
            if verbose:
                print(f"Searching recursively in {link.from_node.bl_idname}")
            nodes.extend(find_linked_nodes(link.from_node, node_check, specific_output_sockets=specific_output_sockets))
    return list(dict.fromkeys(nodes).keys())


def bsdf_mat_to_abstracted(material: Material):
    abstracted_mat = AbstractedN64Material()

    output_node = find_output_node(material)
    if output_node is None:
        abstracted_mat.color = material.diffuse_color
        return abstracted_mat

    mix_shader, color_shader = find_mix_shader_with_transparent(material)
    using_mix_shader = mix_shader is not None and color_shader is not None
    if using_mix_shader:
        alpha_shader, alpha_inp = mix_shader, "Fac"
    else:  # no transparent mix shader, use the first found shader's inputs for searches
        shaders = find_linked_nodes(
            output_node,
            lambda node: node.bl_idname.startswith("ShaderNodeBsdf")
            or node.bl_idname.removeprefix("ShaderNode")
            in {"Background", "Emission", "SubsurfaceScattering", "VolumeAbsorption", "VolumeScatter"},
            specific_input_sockets={"Surface"},
        )
        if len(shaders) == 0:
            abstracted_mat.color = material.diffuse_color
            print(f"WARNING: No shader connected to {material.name}. Using default color.")
            return abstracted_mat
        if len(shaders) > 1:
            print(f"WARNING: More than 1 shader connected to {material.name}. Using first shader.")
        color_shader = alpha_shader = shaders[0]
        alpha_inp = "Alpha"
    if color_shader.bl_idname in {"Background", "Emission"}:  # is unlit
        abstracted_mat.lighting = False
    else:
        abstracted_mat.lighting = True

    # set color_inp to Base Color if the input exists, otherwise try Color, if neither work assert
    color_inp = next(("Base Color" for inp in color_shader.inputs if inp.name == "Base Color"), None)
    if color_inp is None:
        color_inp = next(("Color" for inp in color_shader.inputs if inp.name == "Color"), None)
    assert color_inp is not None, f"Could not find color input in {material.name}"

    # vertex colors
    def get_vtx_layer(nodes):
        layer_names = list(dict.fromkeys([node.layer_name for node in nodes]).keys())
        if len(layer_names) > 1:
            print(f"WARNING: More than 1 color layer used in {material.name}. Using first layer.")
        return layer_names[0]

    vtx_color_nodes = find_linked_nodes(
        color_shader,
        lambda node: node.bl_idname == "ShaderNodeVertexColor",
        specific_input_sockets={color_inp},
    )
    abstracted_mat.vertex_color = get_vtx_layer(vtx_color_nodes) if len(vtx_color_nodes) > 0 else None
    # vertex alpha can sometimes be derived from the mean of the color, this is done by the f3d to bsdf converter as well
    # because of this, we need to handle both cases
    real_vtx_alpha_nodes = find_linked_nodes(
        alpha_shader,
        lambda node: node.bl_idname == "ShaderNodeVertexColor",
        specific_input_sockets={alpha_inp},
        specific_output_sockets={"Alpha"},
    )
    mean_vtx_alpha_nodes = find_linked_nodes(
        alpha_shader,
        lambda node: node.bl_idname == "ShaderNodeVertexColor",
        specific_input_sockets={alpha_inp},
        specific_output_sockets={"Color"},
    )
    if real_vtx_alpha_nodes and mean_vtx_alpha_nodes:
        print(f"WARNING: Mixing real and averaged (from color) vertex alpha in {material.name}.")
    vtx_alpha_nodes = list(dict.fromkeys(real_vtx_alpha_nodes + mean_vtx_alpha_nodes).keys())
    abstracted_mat.vertex_alpha = get_vtx_layer(vtx_alpha_nodes) if len(vtx_alpha_nodes) > 0 else None
    abstracted_mat.alpha_is_median = len(mean_vtx_alpha_nodes) > 0

    # textures and their respective uv maps and properties like filtering and uvgen
    found_uv_map_nodes = []
    alpha_textures = find_linked_nodes(  # textures that use alpha as alpha
        alpha_shader,
        lambda node: node.bl_idname == "ShaderNodeTexImage",
        specific_input_sockets={alpha_inp},
        specific_output_sockets={"Alpha"},
    )
    packed_textures = find_linked_nodes(  # textures that use color as alpha
        alpha_shader,
        lambda node: node.bl_idname == "ShaderNodeTexImage",
        specific_input_sockets={alpha_inp},
        specific_output_sockets={"Color"},
    )
    color_textures = find_linked_nodes(  # textures that use color as color
        color_shader,
        lambda node: node.bl_idname == "ShaderNodeTexImage",
        specific_input_sockets={color_inp},
        specific_output_sockets={"Color"},
    )
    alpha_as_color_textures = find_linked_nodes(  # textures that use alpha as color
        color_shader,
        lambda node: node.bl_idname == "ShaderNodeTexImage",
        specific_input_sockets={color_inp},
        specific_output_sockets={"Alpha"},
    )
    textures: list[ShaderNodeTexImage] = list(
        dict.fromkeys(color_textures + alpha_as_color_textures + packed_textures + alpha_textures).keys()
    )
    if len(textures) > 2:
        print(f"WARNING: More than 2 textures connected to {material.name}.")
    for tex_node in textures[:2]:
        abstracted_tex = AbstractedN64Texture(tex_node.image)
        found_uv_map_nodes.extend(
            find_linked_nodes(
                tex_node,
                lambda node: node.bl_idname == "ShaderNodeUVMap",
                specific_input_sockets={"Vector"},
                specific_output_sockets={"UV"},
            )
        )
        mapping = find_linked_nodes(tex_node, lambda node: node.bl_idname == "ShaderNodeMapping")
        if len(mapping) > 1:
            print(f"WARNING: More than 1 mapping node connected to {tex_node.name}.")
        elif len(mapping) == 1:
            mapping = mapping[0]
            abstracted_tex.offset = tuple(mapping.inputs["Location"].default_value)
            abstracted_tex.scale = tuple(mapping.inputs["Scale"].default_value)
        uv_gen = find_linked_nodes(
            tex_node,
            lambda node: node.bl_idname == "ShaderNodeTexCoord",
            specific_input_sockets={"Vector"},
            specific_output_sockets={"Camera", "Window", "Reflection"},
        )
        if uv_gen:
            abstracted_mat.uv_gen = True
        if tex_node.interpolation == "Closest":
            abstracted_mat.point_filtering = True
        abstracted_tex.repeat = tex_node.extension == "REPEAT"
        abstracted_tex.set_color = tex_node in color_textures
        abstracted_tex.set_alpha = tex_node in alpha_textures
        abstracted_tex.packed_alpha = tex_node in packed_textures
        abstracted_tex.alpha_as_color = tex_node in alpha_as_color_textures
        if abstracted_tex.set_color:
            abstracted_mat.texture_sets_col = True
        if abstracted_tex.set_alpha:
            abstracted_mat.texture_sets_alpha = True
        abstracted_mat.textures.append(abstracted_tex)
    found_uv_map_names = list(dict.fromkeys([node.uv_map for node in found_uv_map_nodes]).keys())
    if len(found_uv_map_names) > 1:
        print(f"WARNING: More than 1 UV map being used in {material.name}. Using first UV map.")
    abstracted_mat.uv_map = found_uv_map_names[0] if len(found_uv_map_names) > 0 else ""

    # very simple search for color mul nodes, only really for glTF import support
    # (glTF materials can have tex multiplied by base color multiplied vertex colors + lighting!)

    def get_solid_color(nodes):
        solid_colors = []
        for node in nodes:
            solid_color, non_solid = None, False
            for inp in node.inputs:  # find all nodes that are multiplied by solid colors but have another input
                if not inp.name.startswith("Fac"):
                    if inp.links:
                        non_solid = True
                    else:
                        solid_color = inp.default_value
            if solid_color is not None and non_solid:
                solid_colors.append(solid_color)
        if len(solid_colors) > 1:
            print(
                f"WARNING: More than 1 solid color/alpha multiplied by a link node in {material.name}. Using first node."
            )
        if len(solid_colors) > 0:
            return solid_colors[0]

    solid_color = get_solid_color(
        find_linked_nodes(
            color_shader,
            lambda node: node.bl_idname.startswith("ShaderNodeMix") and node.blend_type == "MULTIPLY",
            specific_input_sockets={color_inp},
        )
    )
    if solid_color:
        assert hasattr(solid_color, "__iter__"), f"Expected list, got {type(solid_color)}"
        abstracted_mat.color = Color(*solid_color[:3], abstracted_mat.color.a)
    solid_alpha = get_solid_color(
        find_linked_nodes(
            alpha_shader,
            lambda node: node.bl_idname == "ShaderNodeMath" and node.operation == "MULTIPLY",
            specific_input_sockets={alpha_inp},
        )
    )
    if solid_alpha:
        assert isinstance(solid_alpha, float | int), f"Expected float, got {type(solid_alpha)}"
        abstracted_mat.color.a = solid_alpha

    # get default color shader values given no links
    if not color_shader.inputs[color_inp].links:
        abstracted_mat.color.r, abstracted_mat.color.g, abstracted_mat.color.b = color_shader.inputs[
            color_inp
        ].default_value[:3]
    if not alpha_shader.inputs[alpha_inp].links:
        abstracted_mat.color.a = alpha_shader.inputs[alpha_inp].default_value

    abstracted_mat.backface_culling = material.use_backface_culling
    if bpy.app.version < (4, 2, 0):  # before 4.2 we can just use the blend mode
        abstracted_mat.output_method = {"CLIP": "CLIP", "BLEND": "XLU"}.get(material.blend_method, "OPA")
    elif alpha_textures or abstracted_mat.color.a < 1.0:  # otherwise we check if alpha is not 1 or uses a texture
        abstracted_mat.output_method = "XLU"
    # check if there is a "clip" node connected to alpha
    greater_than_nodes = find_linked_nodes(
        alpha_shader,
        lambda node: node.bl_idname == "ShaderNodeMath" and node.operation == "GREATER_THAN",
        specific_input_sockets={alpha_inp},
    )
    if len(greater_than_nodes) > 0:
        abstracted_mat.output_method = "CLIP"
    return abstracted_mat


def material_to_f3d(
    obj: Object,
    material: Material,
    lights_for_colors=False,
    default_to_fog=False,
    set_rendermode_without_fog=False,
):
    print(f"Converting BSDF material {material.name}")

    abstracted_mat = bsdf_mat_to_abstracted(material)

    preset = getDefaultMaterialPreset("Shaded Solid")
    new_material = createF3DMat(obj, preset=preset, append=False)
    target_name = f"{material.name}_f3d"
    new_material.name = target_name
    f3d_mat: F3DMaterialProperty = new_material.f3d_mat
    rdp: RDPSettings = f3d_mat.rdp_settings

    if abstracted_mat.color is not None:
        f3d_mat.default_light_color = tuple(abstracted_mat.color)
        f3d_mat.prim_color = tuple(abstracted_mat.color)
    if lights_for_colors:
        f3d_mat.set_lights = True

    for i, abstracted_tex in enumerate(abstracted_mat.textures):
        f3d_tex: TextureProperty = getattr(f3d_mat, f"tex{i}")
        f3d_tex.tex = abstracted_tex.tex
        f3d_tex.tex_set = True
        f3d_tex.autoprop = abstracted_tex.offset == (0, 0) and abstracted_tex.scale == (1, 1)
        s: TextureFieldProperty = f3d_tex.S
        t: TextureFieldProperty = f3d_tex.T
        s.low = abstracted_tex.offset[0]
        t.low = abstracted_tex.offset[1]
        s.shift = int(-math.log2(abstracted_tex.scale[0]))
        t.shift = int(-math.log2(abstracted_tex.scale[1]))
        if abstracted_tex.packed_alpha:  # if color is being used as alpha, assume intensity texture
            f3d_tex.tex_format = "I8"

    combiner1: CombinerProperty = f3d_mat.combiner1
    combiner2: CombinerProperty = f3d_mat.combiner2

    def set_combiner_cycle(inputs: list[str], suffix=""):
        assert len(inputs) <= 3, f"Too many inputs for combiner cycle: {inputs}"
        for inp_attr in ("A", "B", "C", "D"):  # default all to 0
            for combiner in (combiner1, combiner2):
                setattr(combiner, f"{inp_attr}{suffix}", "0")
        if len(inputs) > 2:  # if inputs cannot fit into 1 cycle, pass in the result of cycle 2 to A for one more mul
            setattr(combiner2, f"A{suffix}", "COMBINED")
        else:  # if inputs can fit, pass in the result of cycle 1 to d (no mul)
            setattr(combiner2, f"D{suffix}", "COMBINED")
        if len(inputs) == 0:  # if no inputs, set D to 1
            setattr(combiner1, f"D{suffix}", "1")
        elif len(inputs) == 1:  # if only one input, set D to it (no mul)
            setattr(combiner1, f"D{suffix}", inputs[0])
        else:
            for i, inp in enumerate(inputs):
                if i == 0:
                    setattr(combiner1, f"A{suffix}", inp)
                elif i == 1 or i == 2:
                    setattr(combiner1 if i == 1 else combiner2, f"C{suffix}", inp)

    # Given an abstracted material we need to create a combiner with some variation,
    # to simplify we create a list of every needed input and pass that on to set_combiner_cycle
    color_inputs, alpha_inputs = [], []
    for i, abstracted_tex in enumerate(abstracted_mat.textures[:2]):
        if abstracted_tex.set_color:
            color_inputs.append(f"TEXEL{i}")
        if abstracted_tex.set_alpha:
            alpha_inputs.append(f"TEXEL{i}")
        if abstracted_tex.alpha_as_color:
            color_inputs.append(f"TEXEL{i}_ALPHA")
    if abstracted_mat.color[:3] != [1, 1, 1]:
        if lights_for_colors and abstracted_mat.lighting:
            color_inputs.append("SHADE")
        else:
            color_inputs.append("PRIMITIVE")
    if abstracted_mat.color[3] != 1:
        alpha_inputs.append("PRIMITIVE")
    if (abstracted_mat.lighting or abstracted_mat.vertex_color is not None) and "SHADE" not in color_inputs:
        color_inputs.append("SHADE")
    if abstracted_mat.vertex_alpha is not None:
        alpha_inputs.append("SHADE")

    required_inputs = max(len(color_inputs), len(alpha_inputs))
    if required_inputs > 3:
        raise PluginError("Too many inputs for combiner")
    set_combiner_cycle(color_inputs)
    set_combiner_cycle(alpha_inputs, "_alpha")

    rdp.g_tex_gen = abstracted_mat.uv_gen
    rdp.g_packed_normals = (
        bool(abstracted_mat.vertex_color) and abstracted_mat.lighting and isUcodeF3DEX3(bpy.context.scene.f3d_type)
    )
    rdp.g_lighting = abstracted_mat.lighting if not bool(abstracted_mat.vertex_color) or rdp.g_packed_normals else False
    rdp.g_fog = default_to_fog
    rdp.g_cull_back = abstracted_mat.backface_culling
    rdp.g_mdsft_text_filt = "G_TF_POINT" if abstracted_mat.point_filtering else "G_TF_BILERP"
    use_2cycle = required_inputs > 2 or rdp.g_fog
    rdp.g_mdsft_cycletype = "G_CYC_2CYCLE" if use_2cycle else "G_CYC_1CYCLE"
    f3d_mat.draw_layer.set_generic_draw_layer(abstracted_mat.output_method)

    main_rendermode = {"OPA": "G_RM_AA_ZB_OPA_SURF", "XLU": "G_RM_AA_ZB_XLU_SURF", "CLIP": "G_RM_AA_ZB_TEX_EDGE"}[
        abstracted_mat.output_method
    ]
    if use_2cycle:
        rdp.rendermode_preset_cycle_1 = "G_RM_FOG_SHADE_A" if rdp.g_fog else "G_RM_PASS"
        rdp.rendermode_preset_cycle_2 = main_rendermode + "2"
    else:
        rdp.rendermode_preset_cycle_1 = main_rendermode
    rdp.set_rendermode = set_rendermode_without_fog or rdp.g_fog  # sm64 should only set rendermode for fog

    with bpy.context.temp_override(material=new_material):
        update_all_node_values(new_material, bpy.context)  # Update nodes

    return new_material, abstracted_mat


def obj_to_f3d(
    obj: Object,
    converted_materials: dict[Material, tuple[Material, AbstractedN64Material]],
    lights_for_colors=False,
    default_to_fog=False,
    set_rendermode_without_fog=False,
):
    assert obj.type == "MESH"
    if not any(mat for mat in obj.data.materials if not is_mat_f3d(mat)):
        if obj.data.materials:
            return False
        else:
            preset = getDefaultMaterialPreset("Shaded Solid")
            createF3DMat(obj, preset=preset)
            return True
    print(f"Converting BSDF materials in {obj.name}")
    uvs = np.empty((len(obj.data.loops), 2), dtype=np.float32) if len(obj.data.uv_layers) != 1 else None
    colors = np.ones((len(obj.data.loops), 4), dtype=np.float32)  # TODO: should col and alpha be seperate?

    # populate a dict of material -> list of loop indices
    loop_indexes: dict[Material, list] = {}
    for poly in obj.data.polygons:
        material = obj.data.materials[poly.material_index] if poly.material_index < len(obj.data.materials) else None
        if material is None:
            continue
        if material not in loop_indexes:
            loop_indexes[material] = []
        for loop_idx in poly.loop_indices:
            loop_indexes[material].append(loop_idx)

    def get_layer_and_convert(layer_name: str | None):  # get color layer, convert it if needed
        layer = obj.data.vertex_colors.get(layer_name or "", obj.data.vertex_colors.active)
        if layer is None:
            return None
        layer_name = layer.name
        convertColorAttribute(obj.data, layer_name)
        return obj.data.vertex_colors[layer_name]  # HACK: layer cannot be trusted

    for index, material_slot in enumerate(obj.material_slots):
        material = material_slot.material
        if material is None or is_mat_f3d(material):
            continue
        if material not in converted_materials:
            converted_materials[material] = material_to_f3d(
                obj, material, lights_for_colors, default_to_fog, set_rendermode_without_fog
            )
        new_material, abstracted_mat = converted_materials[material]
        obj.material_slots[index].material = new_material

        if uvs is not None:  # apply the used uv or fallback on active
            uv_map_layer = obj.data.uv_layers.get(abstracted_mat.uv_map or "", obj.data.uv_layers.active)
            print(f"Updating main UV map with {uv_map_layer.name} UVs from {material.name}.")
            if uv_map_layer is not None:
                for loop_index in loop_indexes[material]:
                    uvs[loop_index] = uv_map_layer.data[loop_index].uv

        # apply the used color/alpha or fallback on active
        col_layer = get_layer_and_convert(abstracted_mat.vertex_color)
        if col_layer is not None:
            for loop_idx in loop_indexes[material]:
                colors[loop_idx, :3] = col_layer.data[loop_idx].color[:3]
        alpha_layer = get_layer_and_convert(abstracted_mat.vertex_alpha)
        if alpha_layer is not None:
            if abstracted_mat.alpha_is_median:
                for loop_idx in loop_indexes[material]:
                    colors[loop_idx, 3] = colorToLuminance(alpha_layer.data[loop_idx].color)
            else:
                for loop_idx in loop_indexes[material]:
                    colors[loop_idx, 3] = alpha_layer.data[loop_idx].color[3]

    if uvs is not None:  # If there wasn´t exactly one UV map, we need to create one singular UV map
        while len(obj.data.uv_layers.values()) > 0:
            obj.data.uv_layers.remove(obj.data.uv_layers.values()[0])
        obj.data.uv_layers.new(name="UVMap")
        obj.data.uv_layers.active = obj.data.uv_layers["UVMap"]
        obj.data.uv_layers["UVMap"].data.foreach_set("uv", uvs.flatten())

    while len(obj.data.vertex_colors) > 0:  # remove all existing colors
        obj.data.vertex_colors.remove(obj.data.vertex_colors[0])
    # get the alpha as rgb, then flatten it
    alpha_layer = obj.data.color_attributes.new("Alpha", "FLOAT_COLOR", "CORNER")
    alpha_layer.data.foreach_set("color", np.repeat(colors[:, 3][:, np.newaxis], 4, axis=1).flatten())
    # set the alpha to 1 for the color layer
    color_layer = obj.data.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    colors[:, 3] = 1
    color_layer.data.foreach_set("color", colors.flatten())
    return True


def obj_to_bsdf(obj: Object, converted_materials: dict[Material, Material], put_alpha_into_color: bool):
    assert obj.type == "MESH"
    print(f"Converting F3D materials in {obj.name}")
    if not any(mat for mat in obj.data.materials if is_mat_f3d(mat)):
        return False
    if put_alpha_into_color:
        apply_alpha(obj.data)
    for index, material_slot in enumerate(obj.material_slots):
        material = material_slot.material
        if material is None or not is_mat_f3d(material):
            continue
        if material in converted_materials:
            obj.material_slots[index].material = converted_materials[material]
        else:
            converted_materials[material] = material_to_bsdf(material, put_alpha_into_color)
            obj.material_slots[index].material = converted_materials[material]
    return True

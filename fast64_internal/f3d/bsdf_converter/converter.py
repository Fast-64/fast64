import numpy as np
import typing
import math

import bpy
from bpy.types import (
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
)

from ...utility import colorToLuminance, PluginError

from ..abstract_materials import apply_alpha, bsdf_mat_to_abstracted, f3d_mat_to_abstracted, AbstractedN64Material
from ..f3d_material import (
    createF3DMat,
    getDefaultMaterialPreset,
    is_mat_f3d,
    set_blend_to_output_method,
    update_all_node_values,
    convertColorAttribute,
    F3DMaterialProperty,
    RDPSettings,
    TextureProperty,
    TextureFieldProperty,
    CombinerProperty,
)
from ..f3d_gbi import isUcodeF3DEX3


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

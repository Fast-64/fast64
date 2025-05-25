import dataclasses
import hashlib
import json
import time
import traceback
from pathlib import Path
from typing import Any

import bpy
from bpy.types import (
    Panel,
    NodeTree,
    ShaderNodeTree,
    NodeLink,
    NodeSocket,
    ColorRamp,
    ColorMapping,
    TexMapping,
    Node,
    Material,
)
from bpy.utils import register_class, unregister_class
from mathutils import Color, Vector, Euler

from ..render_settings import update_scene_props_from_render_settings

from ..utility import PluginError, to_valid_file_name
from ..operators import OperatorBase

# Enable this to show the gather operator, this is a development feature
SHOW_GATHER_OPERATOR = False
ALWAYS_RELOAD = False

SERIALIZED_NODE_LIBRARY_PATH = Path(__file__).parent / "node_library" / "main.json"

GENERAL_EXCLUDE = (
    "rna_type",
    "type",
    "bl_icon",
    "bl_label",
    "bl_idname",
    "bl_description",
    "bl_static_type",
    "bl_height_default",
    "bl_width_default",
    "bl_width_max",
    "bl_width_min",
    "bl_height_max",
    "bl_height_min",
    "socket_idname",
    "color_tag",
)
EXCLUDE_FROM_NODE = GENERAL_EXCLUDE + (
    "inputs",
    "outputs",
    "dimensions",
    "interface",
    "internal_links",
    "image_user",
    "image",
    "select",
    "name",
    "location_absolute",
    "location",
)
EXCLUDE_FROM_GROUP_INPUT_OUTPUT = GENERAL_EXCLUDE + (
    "bl_subtype_label",
    "bl_socket_idname",
    "display_shape",
    "label",
    "identifier",
    "is_output",
    "is_linked",
    "is_multi_input",
    "node",
    "is_unavailable",
    "show_expanded",
    "link_limit",
    "default_attribute_name",
    "name",
    "index",
    "position",
    "parent",
    "socket_type",
    "in_out",
    "item_type",
    "default_input",  # poorly documented, what does it do?
)

GLOBAL_DEFAULTS = {
    "attribute_domain": "POINT",
    "attribute_type": "GEOMETRY",
    "blend_color": (0.800000011920929, 0.800000011920929, 0.800000011920929),
    "blend_factor": 0.0,
    "blend_type": "MIX",
    "brightness": 1.0,
    "clamp": True,
    "clamp_type": "MINMAX",
    "color": (0.6079999804496765, 0.6079999804496765, 0.6079999804496765),
    "color_ramp": {
        "color_mode": "RGB",
        "elements": (
            {"alpha": 1.0, "color": (0.0, 0.0, 0.0, 1.0), "position": 0.0},
            {"alpha": 1.0, "color": (1.0, 1.0, 1.0, 1.0), "position": 1.0},
        ),
        "hue_interpolation": "NEAR",
        "interpolation": "LINEAR",
        "serialized_type": "ColorRamp",
    },
    "contrast": 1.0,
    "convert_from": "WORLD",
    "convert_to": "CAMERA",
    "data_type": "FLOAT",
    "default_value": 0.0,
    "description": "",
    "enabled": True,
    "extension": "REPEAT",
    "height": 100.0,
    "hide": False,
    "hide_value": False,
    "interpolation": "Closest",
    "interpolation_type": "LINEAR",
    "invert": False,
    "is_active_output": True,
    "label": "",
    "label_size": 20,
    "mapping": "FLAT",
    "mapping_x": "X",
    "mapping_y": "Y",
    "mapping_z": "Z",
    "max": (1.0, 1.0, 1.0),
    "max_value": 3.4028234663852886e38,
    "min": (0.0, 0.0, 0.0),
    "min_value": -3.4028234663852886e38,
    "mute": False,
    "node_tree": {"name": "MixValue", "serialized_type": "NodeTree"},
    "noise_dimensions": "2D",
    "operation": "MULTIPLY",
    "parent": None,
    "projection": "FLAT",
    "projection_blend": 0.0,
    "rotation": (0.0, 0.0, 0.0),
    "rotation_type": "X_AXIS",
    "saturation": 1.0,
    "scale": (1.0, 1.0, 1.0),
    "show_options": True,
    "show_preview": False,
    "show_texture": False,
    "shrink": True,
    "text": None,
    "translation": (0.0, 0.0, 0.0),
    "use_alpha": False,
    "use_clamp": False,
    "use_color_ramp": False,
    "use_custom_color": False,
    "use_max": False,
    "use_min": False,
    "vector_type": "POINT",
    "width": 16.0,
    "width_hidden": 42.0,
    "subtype": "NONE",
    "clamp": False,
    "pin_gizmo": False,
    "warning_propagation": "ALL",
    "is_inspect_output": False,
    "factor_mode": "UNIFORM",
    "clamp_factor": True,
    "clamp_result": False,
    "normalize": True,
    "noise_type": "FBM",
    "mode": "RGB",
    # unused in shader nodes
    "hide_in_modifier": False,
    "force_non_field": False,
    "layer_selection_field": False,
}


class DefaultDefinition:
    def __init__(self, names: list[str], defaults: dict[str, Any]):
        self.names = names
        self.defaults = GLOBAL_DEFAULTS | defaults


DEFAULTS = [
    DefaultDefinition(["NodeSocketInt"], {"default_value": 0, "max_value": 1, "min_value": 0}),
    DefaultDefinition(["NodeSocketVector", "NodeSocketRotation"], {"default_value": (0.0, 0.0, 0.0)}),
    DefaultDefinition(["NodeSocketVectorEuler"], {"default_value": (0.0, 0.0, 0.0), "enabled": False}),
    DefaultDefinition(["NodeSocketColor"], {"default_value": (0.0, 0.0, 0.0, 1.0)}),
    DefaultDefinition(["ShaderNodeMixRGB"], {"data_type": "RGBA", "width": 140.0}),
    DefaultDefinition(["NodeSocketVectorDirection"], {"subtype": "DIRECTION", "default_value": (0.0, 0.0, 0.0)}),
    DefaultDefinition(["ShaderNodeVectorTransform"], {"vector_type": "NORMAL", "width": 140.0}),
    DefaultDefinition(
        ["ShaderNodeVectorRotate", "ShaderNodeSeparateXYZ", "ShaderNodeBsdfTransparent", "ShaderNodeTexImage"],
        {"hide": True, "width": 140.0},
    ),
    DefaultDefinition(["ShaderNodeVectorMath"], {"operation": "ADD", "width": 140.0}),
    DefaultDefinition(["ShaderNodeTexNoise"], {"show_texture": True, "width": 140.0}),
    DefaultDefinition(["NodeSocketFloatUnsigned"], {"default_value": 1.5}),
    DefaultDefinition(["NodeSocketFloatFactor"], {"default_value": 0.5}),
    DefaultDefinition(["NodeSocketFloatAngle"], {"default_value": -1.5707963705062866}),
    DefaultDefinition(
        [
            "NodeGroupInput",
            "NodeGroupOutput",
            "ShaderNodeBsdfTransparent",
            "ShaderNodeCameraData",
            "ShaderNodeClamp",
            "ShaderNodeCombineRGB",
            "ShaderNodeCombineXYZ",
            "ShaderNodeGamma",
            "ShaderNodeGroup",
            "ShaderNodeMapRange",
            "ShaderNodeMath",
            "ShaderNodeMixShader",
            "ShaderNodeNewGeometry",
            "ShaderNodeRGBToBW",
            "ShaderNodeSeparateRGB",
            "ShaderNodeValue",
        ],
        {"width": 140.0},
    ),
]
DEFAULTS = {name: definition.defaults for definition in DEFAULTS for name in definition.names}

SCENE_PROPERTIES_VERSION = 2


class ErrorState:
    def __init__(self, error_message_queue: list[str] = None):
        self.error_message_queue = error_message_queue or []
        self.errors = []

    def copy(self, message: str = None):
        errors = ErrorState(self.error_message_queue.copy() + ([message] if message else []))
        errors.errors = self.errors
        return errors


def print_with_exc(error_state: ErrorState, exc: Exception):
    message = "\n".join(error_state.error_message_queue)
    print(message + ":\n" + str(exc))
    print(traceback.format_exc())
    error_state.errors.append((message, exc))


def createOrUpdateSceneProperties():
    group = bpy.data.node_groups.get("SceneProperties")
    upgrade_group = bool(group and group.get("version", -1) < SCENE_PROPERTIES_VERSION)

    if group and not upgrade_group:
        # Group is ready and up to date
        return

    if upgrade_group and group:
        # Need to upgrade; remove old outputs
        if bpy.app.version >= (4, 0, 0):
            for item in group.interface.items_tree:
                if item.item_type == "SOCKET" and item.in_out == "OUTPUT":
                    group.interface.remove(item)
        else:
            for out in group.outputs:
                group.outputs.remove(out)
        new_group = group
    else:
        print("Creating Scene Properties")
        # create a group
        new_group = bpy.data.node_groups.new("SceneProperties", "ShaderNodeTree")
        # create group outputs
        new_group.nodes.new("NodeGroupOutput")

    new_group["version"] = SCENE_PROPERTIES_VERSION

    # Create outputs
    if bpy.app.version >= (4, 0, 0):
        tree_interface = new_group.interface

        _nodeFogEnable: NodeSocketFloat = tree_interface.new_socket(
            "FogEnable", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )
        _nodeFogColor: NodeSocketColor = tree_interface.new_socket(
            "FogColor", socket_type="NodeSocketColor", in_out="OUTPUT"
        )
        _nodeF3D_NearClip: NodeSocketFloat = tree_interface.new_socket(
            "F3D_NearClip", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )
        _nodeF3D_FarClip: NodeSocketFloat = tree_interface.new_socket(
            "F3D_FarClip", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )
        _nodeBlender_Game_Scale: NodeSocketFloat = tree_interface.new_socket(
            "Blender_Game_Scale", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )
        _nodeFogNear: NodeSocketFloat = tree_interface.new_socket(
            "FogNear", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )
        _nodeFogFar: NodeSocketFloat = tree_interface.new_socket(
            "FogFar", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )

        _nodeAmbientColor: NodeSocketColor = tree_interface.new_socket(
            "AmbientColor", socket_type="NodeSocketColor", in_out="OUTPUT"
        )
        _nodeLight0Color: NodeSocketColor = tree_interface.new_socket(
            "Light0Color", socket_type="NodeSocketColor", in_out="OUTPUT"
        )
        _nodeLight0Dir: NodeSocketVector = tree_interface.new_socket(
            "Light0Dir", socket_type="NodeSocketVector", in_out="OUTPUT"
        )
        _nodeLight0Size: NodeSocketFloat = tree_interface.new_socket(
            "Light0Size", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )
        _nodeLight1Color: NodeSocketColor = tree_interface.new_socket(
            "Light1Color", socket_type="NodeSocketColor", in_out="OUTPUT"
        )
        _nodeLight1Dir: NodeSocketVector = tree_interface.new_socket(
            "Light1Dir", socket_type="NodeSocketVector", in_out="OUTPUT"
        )
        _nodeLight1Size: NodeSocketFloat = tree_interface.new_socket(
            "Light1Size", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )

    else:
        _nodeFogEnable: NodeSocketInt = new_group.outputs.new("NodeSocketInt", "FogEnable")
        _nodeFogColor: NodeSocketColor = new_group.outputs.new("NodeSocketColor", "FogColor")
        _nodeF3D_NearClip: NodeSocketFloat = new_group.outputs.new("NodeSocketFloat", "F3D_NearClip")
        _nodeF3D_FarClip: NodeSocketFloat = new_group.outputs.new("NodeSocketFloat", "F3D_FarClip")
        _nodeBlender_Game_Scale: NodeSocketFloat = new_group.outputs.new("NodeSocketFloat", "Blender_Game_Scale")
        _nodeFogNear: NodeSocketInt = new_group.outputs.new("NodeSocketInt", "FogNear")
        _nodeFogFar: NodeSocketInt = new_group.outputs.new("NodeSocketInt", "FogFar")

        _nodeAmbientColor: NodeSocketColor = new_group.outputs.new("NodeSocketColor", "AmbientColor")
        _nodeLight0Color: NodeSocketColor = new_group.outputs.new("NodeSocketColor", "Light0Color")
        _nodeLight0Dir: NodeSocketVectorDirection = new_group.outputs.new("NodeSocketVectorDirection", "Light0Dir")
        _nodeLight0Size: NodeSocketInt = new_group.outputs.new("NodeSocketInt", "Light0Size")
        _nodeLight1Color: NodeSocketColor = new_group.outputs.new("NodeSocketColor", "Light1Color")
        _nodeLight1Dir: NodeSocketVectorDirection = new_group.outputs.new("NodeSocketVectorDirection", "Light1Dir")
        _nodeLight1Size: NodeSocketInt = new_group.outputs.new("NodeSocketInt", "Light1Size")

    # Set outputs from render settings
    sceneOutputs: NodeGroupOutput = new_group.nodes["Group Output"]
    renderSettings: "Fast64RenderSettings_Properties" = bpy.context.scene.fast64.renderSettings

    update_scene_props_from_render_settings(sceneOutputs, renderSettings)


def createScenePropertiesForMaterial(material: Material):
    node_tree = material.node_tree

    # Either create or update SceneProperties if needed
    createOrUpdateSceneProperties()

    # create a new group node to hold the tree
    scene_props = node_tree.nodes.new(type="ShaderNodeGroup")
    scene_props.name = "SceneProperties"
    scene_props.location = (-320, -23)
    scene_props.node_tree = bpy.data.node_groups["SceneProperties"]

    # Fog links to reroutes and the CalcFog block
    node_tree.links.new(scene_props.outputs["FogEnable"], node_tree.nodes["FogEnable"].inputs[0])
    node_tree.links.new(scene_props.outputs["FogColor"], node_tree.nodes["FogColor"].inputs[0])
    node_tree.links.new(scene_props.outputs["F3D_NearClip"], node_tree.nodes["CalcFog"].inputs["F3D_NearClip"])
    node_tree.links.new(scene_props.outputs["F3D_FarClip"], node_tree.nodes["CalcFog"].inputs["F3D_FarClip"])
    node_tree.links.new(
        scene_props.outputs["Blender_Game_Scale"], node_tree.nodes["CalcFog"].inputs["Blender_Game_Scale"]
    )
    node_tree.links.new(scene_props.outputs["FogNear"], node_tree.nodes["CalcFog"].inputs["FogNear"])
    node_tree.links.new(scene_props.outputs["FogFar"], node_tree.nodes["CalcFog"].inputs["FogFar"])

    # Lighting links to reroutes. The colors are connected to other reroutes for update_light_colors,
    # the others go directly to the Shade Color block.
    node_tree.links.new(scene_props.outputs["AmbientColor"], node_tree.nodes["AmbientColor"].inputs[0])
    node_tree.links.new(scene_props.outputs["Light0Color"], node_tree.nodes["Light0Color"].inputs[0])
    node_tree.links.new(scene_props.outputs["Light0Dir"], node_tree.nodes["Light0Dir"].inputs[0])
    node_tree.links.new(scene_props.outputs["Light0Size"], node_tree.nodes["Light0Size"].inputs[0])
    node_tree.links.new(scene_props.outputs["Light1Color"], node_tree.nodes["Light1Color"].inputs[0])
    node_tree.links.new(scene_props.outputs["Light1Dir"], node_tree.nodes["Light1Dir"].inputs[0])
    node_tree.links.new(scene_props.outputs["Light1Size"], node_tree.nodes["Light1Size"].inputs[0])


def get_bl_idname(owner: object):
    return getattr(owner, "bl_idname", None) or getattr(owner, "bl_socket_idname", None)


def convert_bl_idname_to_3_2(owner: NodeSocket | Node):
    bl_idname = get_bl_idname(owner)
    if bpy.app.version >= (4, 0, 0):
        if bl_idname == "NodeSocketVector" and getattr(owner, "subtype", "DIRECTION") == "DIRECTION":
            return "NodeSocketVectorDirection"
        if bl_idname == "ShaderNodeMix" and getattr(owner, "data_type", "") == "RGBA":
            return "ShaderNodeMixRGB"
        if bl_idname == "ShaderNodeCombineColor" and getattr(owner, "mode", "") == "RGB":
            return "ShaderNodeCombineRGB"
    return bl_idname


def get_defaults_bl_idname(owner: object):
    return DEFAULTS.get(convert_bl_idname_to_3_2(owner), GLOBAL_DEFAULTS)


def convert_bl_idname_from_3_2(bl_idname: str, data: dict):
    if bpy.app.version >= (4, 0, 0):
        if bl_idname == "NodeSocketVectorDirection":
            data["subtype"] = "DIRECTION"
            return "NodeSocketVector"
        elif bl_idname == "ShaderNodeMixRGB":
            data["data_type"] = "RGBA"
            return "ShaderNodeMix"
        elif bl_idname == "ShaderNodeCombineRGB":
            data["mode"] = "RGB"
            return "ShaderNodeCombineColor"
        elif bl_idname == "NodeSocketInt":
            return "NodeSocketFloat"
    return bl_idname


def convert_inputs_to_3_2(node: Node, inputs: list):
    inputs = list(inputs)
    if node.bl_idname == "ShaderNodeMix" and getattr(node, "data_type", "") == "RGBA":
        return inputs[0:1] + inputs[6:8]
    return inputs


def convert_outputs_to_3_2(node: Node, outputs: list):
    outputs = list(outputs)
    if node.bl_idname == "ShaderNodeMix" and getattr(node, "data_type", "") == "RGBA":
        return outputs[2:3]
    return outputs


def convert_in_i_from_3_2(i: int, serialized_node: "SerializedNode"):
    if bpy.app.version >= (4, 0, 0):
        if serialized_node.bl_idname == "ShaderNodeMixRGB" and i >= 1 and i <= 2:
            return i + 5
    return i


def convert_out_i_from_3_2(i: int, serialized_node: "SerializedNode"):
    if bpy.app.version >= (4, 0, 0):
        if serialized_node.bl_idname == "ShaderNodeMixRGB" and i == 0:
            return 2
    return i


def get_attributes(owner: object, excludes=None):
    data = {}
    excludes = excludes or []
    attributes = [attr.identifier for attr in owner.bl_rna.properties if attr.identifier not in excludes]
    defaults = get_defaults_bl_idname(owner)

    for attr in attributes:
        value = getattr(owner, attr)
        serialized_value = value
        if isinstance(value, (Color, Vector, Euler)) or (hasattr(value, "__iter__") and type(value) is not str):
            serialized_value = tuple(value)
        elif isinstance(value, ColorRamp):
            serialized_value = {
                "serialized_type": "ColorRamp",
                "color_mode": value.color_mode,
                "elements": [
                    {"alpha": e.alpha, "color": tuple(e.color), "position": e.position} for e in value.elements
                ],
                "hue_interpolation": value.hue_interpolation,
                "interpolation": value.interpolation,
            }
        elif isinstance(value, (ColorMapping, TexMapping)):
            serialized_value = {"serialized_type": "Default", "data": get_attributes(value, excludes)}
        elif isinstance(value, NodeTree):
            serialized_value = {"serialized_type": "NodeTree", "name": value.name}
        elif isinstance(value, Node):
            serialized_value = {"serialized_type": "Node", "name": value.name}
        if attr not in defaults or serialized_value != defaults[attr]:
            data[attr] = serialized_value
    return dict(sorted(data.items()))


@dataclasses.dataclass
class SerializedLink:
    node: str = ""
    name: str | None = None
    index: int = 0

    def to_json(self):
        data = {"node": self.node, "index": self.index}
        if self.name:
            data["name"] = self.name
        return data

    def from_json(self, data: dict):
        self.node = data.get("node")
        self.name = data.get("name")
        self.index = data.get("index")
        return self


@dataclasses.dataclass
class SerializedInputValue:
    name: str | None = None
    data: dict[str, object] = dataclasses.field(default_factory=dict)

    def to_json(self):
        data = {}
        if self.name is not None:
            data["name"] = self.name
        if self.data:
            data.update(self.data)
        return data

    def from_json(self, data: dict):
        self.name = data.pop("name", None)
        self.data = data
        return self


@dataclasses.dataclass
class SerializedGroupInputValue(SerializedInputValue):
    bl_idname: str = ""

    def to_json(self):
        return super().to_json() | {"bl_idname": self.bl_idname}

    def from_json(self, data: dict):
        self.bl_idname = data.pop("bl_idname", None)
        super().from_json(data)
        return self


@dataclasses.dataclass
class SerializedOutputValue(SerializedInputValue):
    links: list[SerializedLink] = dataclasses.field(default_factory=list)

    def to_json(self):
        data = super().to_json()
        if self.links:
            data["links"] = [link.to_json() for link in self.links]
        return data

    def from_json(self, data: dict):
        self.links = [SerializedLink().from_json(link) for link in data.pop("links", [])]
        super().from_json(data)
        return self


@dataclasses.dataclass
class SerializedNode:
    bl_idname: str = ""
    location: tuple[float, float] = (0, 0)
    data: dict[str, object] = dataclasses.field(default_factory=dict)
    inputs: dict[int, SerializedInputValue] = dataclasses.field(default_factory=dict)
    outputs: dict[int, SerializedOutputValue] = dataclasses.field(default_factory=dict)

    def to_json(self):
        data = {"bl_idname": self.bl_idname}
        data["location"] = self.location
        if self.data:
            data.update(self.data)
        if self.inputs:
            data["inputs"] = {i: inp.to_json() for i, inp in self.inputs.items()}
        if self.outputs:
            data["outputs"] = {i: out.to_json() for i, out in self.outputs.items() if out.data or out.links}
        return data

    def from_json(self, data: dict):
        self.bl_idname = data.pop("bl_idname", None)
        self.location = data.pop("location", (0, 0))
        self.inputs = {int(i): SerializedInputValue().from_json(inp) for i, inp in data.pop("inputs", {}).items()}
        self.outputs = {int(i): SerializedOutputValue().from_json(out) for i, out in data.pop("outputs", {}).items()}
        self.data = data
        return self


def dict_hash(dictionary: dict[str, Any]) -> str:
    """MD5 hash of a dictionary. https://stackoverflow.com/a/67438471"""
    dhash = hashlib.md5()
    # We need to sort arguments so {'a': 1, 'b': 2} is
    # the same as {'b': 2, 'a': 1}
    encoded = json.dumps(dictionary, sort_keys=True).encode()
    dhash.update(encoded)
    return dhash.hexdigest()


@dataclasses.dataclass
class SerializedNodeTree:
    name: str = ""
    nodes: dict[str, SerializedNode] = dataclasses.field(default_factory=dict)
    links: list[SerializedLink] = dataclasses.field(default_factory=list)

    inputs: list[SerializedGroupInputValue] = dataclasses.field(default_factory=list)
    outputs: list[SerializedGroupInputValue] = dataclasses.field(default_factory=list)

    cached_hash: str = ""

    def to_json(self):
        print(f"Serializing node tree {self.name} to json")
        data = {"name": self.name, "nodes": {name: node.to_json() for name, node in self.nodes.items()}}
        if self.links:
            data["links"] = [link.to_json() for link in self.links]
        if self.inputs:
            data["inputs"] = [inp.to_json() for inp in self.inputs]
        if self.outputs:
            data["outputs"] = [out.to_json() for out in self.outputs]
        data["cached_hash"] = dict_hash(data)
        data["bpy_ver"] = bpy.app.version
        return data

    def from_json(self, data: dict):
        self.name = data["name"]
        self.nodes = {name: SerializedNode().from_json(node) for name, node in data["nodes"].items()}
        self.links = [SerializedLink().from_json(link) for link in data.get("links", [])]
        self.inputs = [SerializedGroupInputValue().from_json(inp) for inp in data.get("inputs", [])]
        self.outputs = [SerializedGroupInputValue().from_json(out) for out in data.get("outputs", [])]
        self.cached_hash = data["cached_hash"]
        return self

    def from_node_tree(self, node_tree: NodeTree):
        is_new = bpy.app.version >= (4, 0, 0)
        print(f"Serializing node tree {node_tree.name}")
        for in_out in ("INPUT", "OUTPUT"):
            prop = in_out.lower() + "s"
            self_prop = getattr(self, prop)
            if is_new:
                sockets = [socket for socket in node_tree.interface.items_tree.values() if socket.in_out == in_out]
            else:
                sockets = getattr(node_tree, prop)
            for socket in sockets:
                self_prop.append(
                    SerializedGroupInputValue(
                        socket.name,
                        get_attributes(socket, EXCLUDE_FROM_GROUP_INPUT_OUTPUT),
                        convert_bl_idname_to_3_2(socket),
                    )
                )
        for node in node_tree.nodes:
            if hasattr(node, "location_absolute"):
                location = node.location_absolute
            else:
                location = node.location
                parent = node.parent
                while parent is not None:
                    location = tuple(x + y for x, y in zip(parent.location, location))
                    parent = parent.parent

            serialized_node = SerializedNode(
                convert_bl_idname_to_3_2(node),
                tuple(round(0.0 if x == -0 else x, 4) for x in location),
                get_attributes(node, EXCLUDE_FROM_NODE),
            )
            self.nodes[node.name] = serialized_node
        for serialized_node, node in zip(self.nodes.values(), node_tree.nodes):
            inputs = convert_inputs_to_3_2(node, node.inputs)
            for i, inp in enumerate(inputs):
                name = None
                if not any(other for other in inputs if other != inp and other.name == inp.name):
                    name = inp.name
                serialized_node.inputs[i] = SerializedInputValue(
                    name, get_attributes(inp, EXCLUDE_FROM_GROUP_INPUT_OUTPUT)
                )
            outputs = convert_outputs_to_3_2(node, node.outputs)
            for i, out in enumerate(outputs):
                name = None
                if not any(other for other in outputs if other != out and other.name == out.name):
                    name = out.name
                serialized_node.outputs[i] = serialized_out = SerializedOutputValue(
                    name, get_attributes(out, EXCLUDE_FROM_GROUP_INPUT_OUTPUT)
                )
                link: NodeLink
                for link in out.links:
                    name = None
                    inputs = convert_inputs_to_3_2(link.to_node, link.to_node.inputs)
                    if not any(
                        other for other in inputs if other == link.to_socket and other.name == link.to_socket.name
                    ):
                        name = link.to_socket.name
                    serialized_out.links.append(SerializedLink(link.to_node.name, name, inputs.index(link.to_socket)))
        return self


@dataclasses.dataclass
class SerializedMaterialNodeTree(SerializedNodeTree):
    dependencies: dict[str, SerializedNodeTree] = dataclasses.field(default_factory=dict)

    def to_json(self):
        data = super().to_json()
        data["dependencies"] = [to_valid_file_name(name) for name in self.dependencies.keys()]
        return data

    def from_json(self, data: dict):
        super().from_json(data)
        for name in data["dependencies"]:
            self.dependencies[name] = SerializedNodeTree()
        return self

    def load(self, path: Path):
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        self.from_json(data)
        for name, node_tree in self.dependencies.items():
            with Path(path.parent / (name + ".json")).open("r", encoding="utf-8") as f:
                data = json.load(f)
            node_tree.from_json(data)
        return self

    def dump(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.to_json(), f, indent="\t")
        for name, node_tree in self.dependencies.items():
            with Path(path.parent / to_valid_file_name(name + ".json")).open("w") as f:
                json.dump(node_tree.to_json(), f, indent="\t")


class GatherF3DNodes(OperatorBase):
    bl_idname = "material.f3d_gather_f3d_nodes"
    bl_label = "Gather F3D Nodes"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    @classmethod
    def poll(cls, context):
        return context.material is not None

    def execute_operator(self, context):
        material = context.material
        assert material and material.node_tree

        node_groups: dict[str, SerializedNodeTree] = {}
        for node_group in bpy.data.node_groups.values():
            node_groups[node_group.name] = SerializedNodeTree(node_group.name).from_node_tree(node_group)
        material_nodes = SerializedMaterialNodeTree(material.name, dependencies=node_groups).from_node_tree(
            material.node_tree
        )
        material_nodes.dump(SERIALIZED_NODE_LIBRARY_PATH)

        load_f3d_nodes()


class GatherF3DNodesPanel(Panel):
    bl_label = "Gather F3D Nodes"
    bl_idname = "MATERIAL_PT_GatherF3DNodes"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        col = self.layout.column()
        col.operator(GatherF3DNodes.bl_idname)


SERIALIZED_NODE_LIBRARY: SerializedMaterialNodeTree | None = None
NODE_LIBRARY_EXCEPTION: Exception | None = None


def load_f3d_nodes():
    global SERIALIZED_NODE_LIBRARY, NODE_LIBRARY_EXCEPTION
    try:
        start = time.perf_counter()
        SERIALIZED_NODE_LIBRARY = SerializedMaterialNodeTree().load(SERIALIZED_NODE_LIBRARY_PATH)
        end = time.perf_counter()
        print(f"Loaded f3d_nodes.json in {end - start:.3f} seconds")
    except Exception as exc:
        NODE_LIBRARY_EXCEPTION = exc
        traceback.print_exc()
        print(f"Failed to load f3d_nodes.json: {exc}")


def set_node_prop(prop: object, attr: str, value: object, nodes, errors: ErrorState):
    if not hasattr(prop, attr):
        return
    if isinstance(value, dict) and "serialized_type" in value:
        if value["serialized_type"] == "Default":
            for key, val in value["data"].items():
                set_node_prop(getattr(prop, attr), key, val, nodes, errors)
        elif value["serialized_type"] == "ColorRamp":
            prop_value = getattr(prop, attr)
            assert isinstance(prop_value, ColorRamp), f"Expected ColorRamp, got {type(prop_value)}"
            prop_value.color_mode = value["color_mode"]
            for element in prop_value.elements:
                try:  # HACK: Bug with this iter? copy doesn´t work either
                    prop_value.elements.remove(element)
                except:
                    pass
            for serialized_element in value["elements"]:
                element = prop_value.elements.new(serialized_element["position"])
                element.color = serialized_element["color"]
                element.alpha = serialized_element["alpha"]
            prop_value.hue_interpolation = value["hue_interpolation"]
            prop_value.interpolation = value["interpolation"]
        elif value["serialized_type"] == "NodeTree":
            setattr(prop, attr, bpy.data.node_groups[value["name"]])
        elif value["serialized_type"] == "Node":
            setattr(prop, attr, nodes[value["name"]])
        else:
            raise ValueError(f"Unknown serialized type {value['serialized_type']}")
        return
    existing_value = getattr(prop, attr, None)
    try:
        setattr(prop, attr, value)
    except Exception as exc:
        print_with_exc(
            errors.copy(
                f'Failed to set "{attr}" ({existing_value}, {type(existing_value)}) to "{value}" ({type(value)})'
            ),
            exc,
        )


def set_attrs(owner: object, attrs: dict[str, object], nodes: dict[str, Node], excludes: set[str], errors: ErrorState):
    defaults = get_defaults_bl_idname(owner)
    for attr, value in attrs.items():
        try:
            set_node_prop(owner, attr, value, nodes, errors)
        except Exception as exc:
            print_with_exc(errors, exc)
    for key, value in defaults.items():
        if hasattr(owner, key) and key not in attrs and key not in excludes:
            cur_errors = errors.copy("Failed to set default value")
            try:
                if isinstance(value, tuple):
                    value = list(value)
                set_node_prop(owner, key, value, nodes, cur_errors)
            except Exception as exc:
                print_with_exc(cur_errors, exc)


def try_name_then_index(collection, name: str | None, index: int):
    if name is not None and name in collection:
        return collection[name]
    elif index < len(collection):
        return collection[index]


def set_values_and_create_links(
    node_tree: ShaderNodeTree, serialized_node_tree: SerializedNodeTree, new_nodes: list[Node], errors: ErrorState
):
    def get_name(i: int, inp: SerializedInputValue, socket: NodeSocket | None = None):
        if socket is not None:
            return f'"{socket.name}"'
        if inp.name is not None:
            return f'"{inp.name}"'
        return str(i)

    links, nodes = node_tree.links, node_tree.nodes

    for node, serialized_node in zip(new_nodes, serialized_node_tree.nodes.values()):
        cur_errors = errors.copy(f'Failed to set values for node "{node.name}"')
        try:
            set_attrs(node, serialized_node.data, nodes, EXCLUDE_FROM_NODE, cur_errors)
        except Exception as exc:
            print_with_exc(cur_errors, exc)

    for serialized_node, node in zip(serialized_node_tree.nodes.values(), new_nodes):
        for i, serialized_inp in serialized_node.inputs.items():
            name = get_name(i, serialized_inp)
            cur_errors = errors.copy(f'Failed to set values for input {name} of node "{node.label or node.name}"')
            try:
                inp = try_name_then_index(node.inputs, serialized_inp.name, convert_in_i_from_3_2(i, serialized_node))
                if inp is None:
                    raise IndexError("Socket not found")
                cur_errors = errors.copy(
                    f'Failed to set values for input "{inp.name}" (serialized has {name}) of node "{node.label or node.name}"'
                )
                set_attrs(inp, serialized_inp.data, nodes, EXCLUDE_FROM_GROUP_INPUT_OUTPUT, cur_errors)
            except Exception as exc:
                print_with_exc(cur_errors, exc)
        for i, serialized_out in serialized_node.outputs.items():
            name = get_name(i, serialized_out)
            cur_errors = errors.copy(
                f'Failed to set values and links for output {name} of node "{node.label or node.name}"'
            )
            try:
                out_index = convert_out_i_from_3_2(i, serialized_node)
                out = try_name_then_index(node.outputs, serialized_out.name, out_index)
                if out is None:
                    raise IndexError("Socket not found")
                cur_errors = errors.copy(
                    f'Failed to set values for output "{out.name}" (serialized has {name}) of node "{node.label or node.name}"'
                )
                try:
                    set_attrs(out, serialized_out.data, nodes, EXCLUDE_FROM_GROUP_INPUT_OUTPUT, cur_errors)
                except Exception as exc:
                    print_with_exc(cur_errors, exc)

                cur_errors = errors.copy(
                    f'Failed to set links for output "{out.name}" (serialized has {name}) of node "{node.label or node.name}"'
                )
                for serialized_link in serialized_out.links:
                    # needed because modern blender (4.4) is written by monkeys and a type writer. god bless my never ending patience
                    out = try_name_then_index(node.outputs, serialized_out.name, out_index)
                    link_errors = cur_errors.copy(
                        f'Failed to set links to input socket {get_name(serialized_link.index, serialized_link)} of node "{serialized_link.name}"'
                    )
                    try:
                        serialized_target_node = serialized_node_tree.nodes[serialized_link.node]
                        inp = try_name_then_index(
                            nodes[serialized_link.node].inputs,
                            serialized_link.name,
                            convert_in_i_from_3_2(serialized_link.index, serialized_target_node),
                        )
                        if inp is None:
                            raise IndexError("Socket not found")
                        links.new(inp, out)
                    except Exception as exc:
                        print_with_exc(link_errors, exc)
            except Exception as exc:
                print_with_exc(cur_errors, exc)


def add_input_output(
    node_tree: NodeTree | ShaderNodeTree, serialized_node_tree: SerializedNodeTree, errors: ErrorState
):
    is_new = bpy.app.version >= (4, 0, 0)
    if is_new:
        interface = node_tree.interface
        interface.clear()
    else:
        node_tree.inputs.clear()
        node_tree.outputs.clear()
    for in_out in ("INPUT", "OUTPUT"):
        for serialized in serialized_node_tree.inputs if in_out == "INPUT" else serialized_node_tree.outputs:
            cur_errors = errors.copy(f'Failed to add "{in_out}" socket "{serialized.name}"')
            try:
                bl_idname = convert_bl_idname_from_3_2(serialized.bl_idname, serialized.data)
                if is_new:
                    socket = interface.new_socket(serialized.name, socket_type=bl_idname, in_out=in_out)
                else:
                    socket = getattr(node_tree, in_out.lower() + "s").new(bl_idname, serialized.name)
                set_attrs(socket, serialized.data, node_tree.nodes, EXCLUDE_FROM_GROUP_INPUT_OUTPUT, cur_errors)
            except Exception as exc:
                print_with_exc(cur_errors, exc)
    node_tree.interface_update(bpy.context)
    if hasattr(node_tree, "update"):
        node_tree.update()


def create_nodes(node_tree: NodeTree | ShaderNodeTree, serialized_node_tree: SerializedNodeTree, errors: ErrorState):
    nodes = node_tree.nodes
    nodes.clear()
    new_nodes: list[Node] = []
    for name, serialized_node in serialized_node_tree.nodes.items():
        cur_errors = errors.copy(f'Failed to create node "{name}"')
        try:
            node = nodes.new(convert_bl_idname_from_3_2(serialized_node.bl_idname, serialized_node.data))
            node.name = name
            node.location = serialized_node.location
            new_nodes.append(node)
        except Exception as exc:
            print_with_exc(cur_errors, exc)
    cur_errors = errors.copy(f'Failed to add sockets for node group "{node_tree.name}"')
    try:
        add_input_output(node_tree, serialized_node_tree, cur_errors)
    except Exception as exc:
        print_with_exc(cur_errors, exc)
    return new_nodes


def is_f3d_mat(material: Material):
    from .f3d_material import F3D_MAT_CUR_VERSION

    return material.is_f3d and material.mat_ver >= F3D_MAT_CUR_VERSION


def generate_f3d_node_groups(forced=True):
    if SERIALIZED_NODE_LIBRARY is None:
        raise PluginError(
            f"Failed to load f3d_nodes.json {str(NODE_LIBRARY_EXCEPTION)}, see console"
        ) from NODE_LIBRARY_EXCEPTION
    if not forced and not any(is_f3d_mat(material) for material in bpy.data.materials):
        return
    errors = ErrorState()
    update_materials = False
    new_node_trees: list[tuple[NodeTree, list[Node]]] = []
    for serialized_node_group in SERIALIZED_NODE_LIBRARY.dependencies.values():
        node_tree = None
        if serialized_node_group.name in bpy.data.node_groups:
            node_tree = bpy.data.node_groups[serialized_node_group.name]
            if node_tree.get("fast64_cached_hash", None) == serialized_node_group.cached_hash and not ALWAYS_RELOAD:
                continue
            if node_tree.type == "UNDEFINED":
                bpy.data.node_groups.remove(node_tree, do_unlink=True)
                node_tree = None
                update_materials = True
        if node_tree:
            print(
                f'Node group "{serialized_node_group.name}" already exists, but serialized node group hash changed, updating'
            )
        else:
            print(f'Creating node group "{serialized_node_group.name}"')
            node_tree = bpy.data.node_groups.new(serialized_node_group.name, "ShaderNodeTree")
            node_tree.use_fake_user = True
        cur_errors = errors.copy(f'Failed to create node group "{serialized_node_group.name}"')
        try:
            new_node_trees.append(
                (serialized_node_group, node_tree, create_nodes(node_tree, serialized_node_group, cur_errors))
            )
        except Exception as exc:
            print_with_exc(cur_errors, exc)
    for serialized_node_group, node_tree, new_nodes in new_node_trees:
        cur_errors = errors.copy(f'Failed to create links for node group "{serialized_node_group.name}"')
        try:
            set_values_and_create_links(node_tree, serialized_node_group, new_nodes, cur_errors)
            node_tree["fast64_cached_hash"] = serialized_node_group.cached_hash
        except Exception as exc:
            print_with_exc(cur_errors, exc)
    update_f3d_materials(force=update_materials)


def create_f3d_nodes_in_material(material: Material, errors: ErrorState = None):
    from .f3d_material import update_all_node_values

    errors = ErrorState() or errors
    assert is_f3d_mat(material), f"Material {material.name} is not an up to date f3d material"
    material.use_nodes = True
    new_nodes = create_nodes(material.node_tree, SERIALIZED_NODE_LIBRARY, errors)
    set_values_and_create_links(material.node_tree, SERIALIZED_NODE_LIBRARY, new_nodes, errors)
    createScenePropertiesForMaterial(material)
    material.f3d_update_flag = False
    with bpy.context.temp_override(material=material):
        update_all_node_values(material, bpy.context)


def update_f3d_materials(force=False):
    for material in bpy.data.materials:
        errors = ErrorState([f"Failed to update material {material.name}"])
        try:
            if is_f3d_mat(material) and (
                material.node_tree.get("fast64_cached_hash", None) != SERIALIZED_NODE_LIBRARY.cached_hash or force
            ):
                print(f'Updating material "{material.name}"\'s nodes')
                create_f3d_nodes_in_material(material, errors)
                material.node_tree["fast64_cached_hash"] = SERIALIZED_NODE_LIBRARY.cached_hash
        except Exception as exc:
            print_with_exc(errors, exc)


if SHOW_GATHER_OPERATOR:
    f3d_node_gen_classes = (GatherF3DNodes, GatherF3DNodesPanel)
else:
    f3d_node_gen_classes = tuple()


def f3d_node_gen_register():
    load_f3d_nodes()
    for cls in f3d_node_gen_classes:
        register_class(cls)


def f3d_node_gen_unregister():
    for cls in reversed(f3d_node_gen_classes):
        unregister_class(cls)

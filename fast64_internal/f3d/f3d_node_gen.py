import dataclasses
import hashlib
import json
from pathlib import Path
import time
import traceback
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

from ..utility import PluginError, to_valid_file_name
from ..operators import OperatorBase

# Enable this to show the gather operator, this is a development feature
SHOW_GATHER_OPERATOR = True
INCLUDE_DEFAULT = True  # include default if link exists
ALWAYS_RELOAD = True

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

DEFAULTS = {
    "hide": False,
    "mute": False,
    "show_preview": False,
    "label": "",
    "description": "",
    "parent": None,
    "show_texture": False,
    "use_custom_color": False,
    "show_options": True,
    "width": 16.0,
    "width_hidden": 42.0,
    "height": 100.0,
    "text": None,
    "hide_value": False,
    "subtype": "NONE",
    # unused in shader nodes
    "hide_in_modifier": False,
    "force_non_field": False,
    "layer_selection_field": False,
    "enabled": True,
}


def convert_to_3_2(prop: NodeSocket | Node):
    bl_idname = getattr(prop, "bl_idname", None) or getattr(prop, "bl_socket_idname", None)
    if bpy.app.version >= (4, 0, 0):
        if bl_idname == "NodeSocketVector" and prop.subtype == "DIRECTION":
            return "NodeSocketVectorDirection"
    return bl_idname


def convert_from_3_2(bl_idname: str, data: dict):
    if bpy.app.version >= (4, 0, 0):
        if bl_idname == "NodeSocketVectorDirection":
            data["subtype"] = "DIRECTION"
            return "NodeSocketVector"
    return bl_idname


def get_attributes(prop, excludes=None):
    data = {}
    excludes = excludes or []
    attributes = [attr.identifier for attr in prop.bl_rna.properties if attr.identifier not in excludes]

    for attr in attributes:
        value = getattr(prop, attr)
        if attr not in DEFAULTS or value != DEFAULTS[attr]:
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
            elif isinstance(value, int) and not isinstance(value, bool):
                serialized_value = int(value)
            data[attr] = serialized_value
    return dict(sorted(data.items()))


@dataclasses.dataclass
class SerializedLink:
    node: str = ""
    socket: str | int = ""  # when more than one socket with the same name, we still prefer str for readability

    def to_json(self):
        return {"node": self.node, "socket": self.socket}

    def from_json(self, data: dict):
        self.node = data.get("node")
        self.socket = data.get("socket")
        return self


@dataclasses.dataclass
class SerializedInputValue:
    data: dict[str, object] = dataclasses.field(default_factory=dict)

    def to_json(self):
        return {"data": self.data}

    def from_json(self, data: dict):
        self.data = data.get("data")
        return self


@dataclasses.dataclass
class SerializedGroupInputValue(SerializedInputValue):
    name: str = ""
    bl_idname: str = ""

    def to_json(self):
        return super().to_json() | {"name": self.name, "bl_idname": self.bl_idname}

    def from_json(self, data: dict):
        super().from_json(data)
        self.name = data.get("name")
        self.bl_idname = data.get("bl_idname")
        return self


@dataclasses.dataclass
class SerializedNode:
    bl_idname: str = ""
    data: dict[str, object] = dataclasses.field(default_factory=dict)
    inputs: list[SerializedInputValue] = dataclasses.field(default_factory=list)
    outputs: list[list[SerializedLink]] = dataclasses.field(default_factory=list)

    def to_json(self):
        data = {"bl_idname": self.bl_idname, "data": self.data}
        if self.inputs:
            data["inputs"] = [inp.to_json() for inp in self.inputs]
        if self.outputs:
            data["outputs"] = [[out.to_json() for out in outs] for outs in self.outputs]
        return data

    def from_json(self, data: dict):
        self.bl_idname = data["bl_idname"]
        self.data = data["data"]
        if "inputs" in data:
            self.inputs = [SerializedInputValue().from_json(inp) for inp in data["inputs"]]
        if "outputs" in data:
            self.outputs = [[SerializedLink().from_json(out) for out in outs] for outs in data["outputs"]]
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
        return data

    def from_json(self, data: dict):
        self.name = data["name"]
        self.nodes = {name: SerializedNode().from_json(node) for name, node in data["nodes"].items()}
        if "links" in data:
            self.links = [SerializedLink().from_json(link) for link in data["links"]]
        if "inputs" in data:
            self.inputs = [SerializedGroupInputValue().from_json(inp) for inp in data["inputs"]]
        if "outputs" in data:
            self.outputs = [SerializedGroupInputValue().from_json(out) for out in data["outputs"]]
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
                bl_idname = convert_to_3_2(socket)
                self_prop.append(
                    SerializedGroupInputValue(
                        get_attributes(socket, EXCLUDE_FROM_GROUP_INPUT_OUTPUT), socket.name, bl_idname
                    )
                )
        for node in node_tree.nodes:
            serialized_node = SerializedNode(node.bl_idname, get_attributes(node, EXCLUDE_FROM_NODE))
            self.nodes[node.name] = serialized_node
        for serialized_node, node in zip(self.nodes.values(), node_tree.nodes):
            for inp in node.inputs:
                exclude = EXCLUDE_FROM_GROUP_INPUT_OUTPUT
                if not INCLUDE_DEFAULT and inp.links:
                    exclude = exclude + ("default_value",)
                serialized_node.inputs.append(SerializedInputValue(get_attributes(inp, exclude)))
            for out in node.outputs:
                serialized_outputs = []
                serialized_node.outputs.append(serialized_outputs)
                link: NodeLink
                for link in out.links:
                    repeated_socket_name = any(
                        s for s in link.to_node.inputs if s != link.to_socket and s.name == link.to_socket.name
                    )
                    index = link.to_socket.name
                    if repeated_socket_name:
                        index = list(link.to_node.inputs).index(link.to_socket)
                    serialized_outputs.append(SerializedLink(link.to_node.name, index))
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
        with path.open("r") as f:
            data = json.load(f)
        self.from_json(data)
        for name, node_tree in self.dependencies.items():
            with Path(path.parent / (name + ".json")).open("r") as f:
                data = json.load(f)
            node_tree.from_json(data)
        return self

    def dump(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
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


def set_node_prop(prop: object, attr: str, value: object, nodes):
    if isinstance(value, dict) and "serialized_type" in value:
        if value["serialized_type"] == "Default":
            for key, val in value["data"].items():
                set_node_prop(getattr(prop, attr), key, val, nodes)
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
    as_list = value if isinstance(value, list) else [value]
    if (
        hasattr(existing_value, "__iter__")
        and not isinstance(existing_value, str)
        and len(existing_value) != len(as_list)
    ):
        new_value = list(existing_value)
        for i, elem in enumerate(as_list):
            new_value[i] = elem
        value = new_value
    try:
        setattr(prop, attr, value)
    except Exception as exc:
        raise Exception(f"Failed to set {attr} of {prop.name} to {value}: {exc}") from exc


def set_values_and_create_links(
    node_tree: ShaderNodeTree, serialized_node_tree: SerializedNodeTree, new_nodes: list[Node]
):
    links, nodes = node_tree.links, node_tree.nodes

    for node, serialized_node in zip(new_nodes, serialized_node_tree.nodes.values()):
        try:
            for attr, value in serialized_node.data.items():
                set_node_prop(node, attr, value, nodes)
            node.update()
        except Exception as exc:
            print(f"Failed to set values for node {node.name}: {exc}")
    if hasattr(node_tree, "update"):
        node_tree.update()
    for serialized_node, node in zip(serialized_node_tree.nodes.values(), new_nodes):
        for i, serialized_inp in enumerate(serialized_node.inputs):
            name = str(i)
            try:
                inp = node.inputs[i]
                name = inp.name
                for attr, value in serialized_inp.data.items():
                    set_node_prop(inp, attr, value, nodes)
            except Exception as exc:
                print(f"Failed to set default values for input {name} of node {node.name}: {exc}")
        for i, serialized_outs in enumerate(serialized_node.outputs):
            try:
                name = str(i)
                out = node.outputs[i]
                for serialized_out in serialized_outs:
                    try:
                        name = out.name
                        links.new(nodes[serialized_out.node].inputs[serialized_out.socket], out)
                    except Exception as exc:
                        print(
                            f"Failed to create links for output socket {name} of node {node.name} to node {serialized_out.node} with socket {serialized_out.socket}: {exc}"
                        )
            except Exception as exc:
                print(f"Failed to set links for output {name} of node {node.name}: {exc}")


def add_input_output(node_tree: NodeTree | ShaderNodeTree, serialized_node_tree: SerializedNodeTree):
    is_new = bpy.app.version >= (4, 0, 0)
    if is_new:
        interface = node_tree.interface
        interface.clear()
    else:
        node_tree.inputs.clear()
        node_tree.outputs.clear()
    for in_out in ("INPUT", "OUTPUT"):
        for serialized in serialized_node_tree.inputs if in_out == "INPUT" else serialized_node_tree.outputs:
            bl_idname = convert_from_3_2(serialized.bl_idname, serialized.data)
            if is_new:
                socket = interface.new_socket(serialized.name, socket_type=bl_idname, in_out=in_out)
            else:
                socket = getattr(node_tree, in_out.lower() + "s").new(bl_idname, serialized.name)
            for attr, value in serialized.data.items():
                try:
                    set_node_prop(socket, attr, value, {})
                except Exception as exc:
                    print(f"Failed to set default values for {in_out} socket {socket.name}: {exc}")
    node_tree.interface_update(bpy.context)
    if hasattr(node_tree, "update"):
        node_tree.update()


def create_nodes(node_tree: NodeTree | ShaderNodeTree, serialized_node_tree: SerializedNodeTree):
    nodes = node_tree.nodes
    nodes.clear()
    new_nodes: list[Node] = []
    for name, serialized_node in serialized_node_tree.nodes.items():
        node = nodes.new(serialized_node.bl_idname)
        node.name = name
        new_nodes.append(node)
    add_input_output(node_tree, serialized_node_tree)
    return new_nodes


def generate_f3d_node_groups():
    if SERIALIZED_NODE_LIBRARY is None:
        raise PluginError(
            f"Failed to load f3d_nodes.json {str(NODE_LIBRARY_EXCEPTION)}, see console"
        ) from NODE_LIBRARY_EXCEPTION
    new_node_trees: list[tuple[NodeTree, list[Node]]] = []
    for serialized_node_group in SERIALIZED_NODE_LIBRARY.dependencies.values():
        if serialized_node_group.name in bpy.data.node_groups:
            node_tree = bpy.data.node_groups[serialized_node_group.name]
            if node_tree.get("fast64_cached_hash", None) == serialized_node_group.cached_hash and not ALWAYS_RELOAD:
                continue
            print("Node group already exists, but serialized node group hash changed, updating")
        else:
            print(f"Creating node group {serialized_node_group.name}")
            node_tree = bpy.data.node_groups.new(serialized_node_group.name, "ShaderNodeTree")
            node_tree.use_fake_user = True
        try:
            new_node_trees.append((serialized_node_group, node_tree, create_nodes(node_tree, serialized_node_group)))
        except Exception as exc:
            raise PluginError(f"Failed on creating group {serialized_node_group.name}: {exc}") from exc
    for serialized_node_group, node_tree, new_nodes in new_node_trees:
        try:
            set_values_and_create_links(node_tree, serialized_node_group, new_nodes)
            node_tree["fast64_cached_hash"] = serialized_node_group.cached_hash
        except Exception as exc:
            raise PluginError(f"Failed on group {serialized_node_group.name}: {exc}") from exc


def create_f3d_nodes_in_material(material: Material):
    generate_f3d_node_groups()
    material.use_nodes = True
    new_nodes = create_nodes(material.node_tree, SERIALIZED_NODE_LIBRARY)
    set_values_and_create_links(material.node_tree, SERIALIZED_NODE_LIBRARY, new_nodes)


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

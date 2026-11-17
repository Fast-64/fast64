import bpy
from bpy.types import NodeTree


class F3DMaterial_UpdateLock:
    material: bpy.types.Material = None

    def __init__(self, material: bpy.types.Material):
        self.material = material
        if self.mat_is_locked():
            # Disallow access to locked materials
            self.material = None

    def __enter__(self):
        if self.mat_is_locked():
            return None

        self.lock_material()
        return self.material

    def __exit__(self, exc_type, exc_value, traceback):
        self.unlock_material()
        if exc_value:
            print("\nExecution type:", exc_type)
            print("\nExecution value:", exc_value)
            print("\nTraceback:", traceback)

    def mat_is_locked(self):
        return getattr(self.material, "f3d_update_flag", True) or not getattr(self.material, "is_f3d", False)

    def lock_material(self):
        if hasattr(self.material, "f3d_update_flag"):
            self.material.f3d_update_flag = True

    def unlock_material(self):
        if hasattr(self.material, "f3d_update_flag"):
            self.material.f3d_update_flag = False


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
    "select",
    "is_inactive",
    "is_icon_visible",
    "parent",
)
EXCLUDE_FROM_NODE = GENERAL_EXCLUDE + (
    "inputs",
    "outputs",
    "dimensions",
    "interface",
    "internal_links",
    "image_user",
    "texture_mapping",
    "color_mapping",
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
    "socket_type",
    "in_out",
    "item_type",
    "inferred_structure_type",
    "default_input",  # poorly documented, what does it do?
)


def node_tree_copy(src: NodeTree, dst: NodeTree):
    def copy_attributes(src, dst, excludes=None):
        fails, excludes = [], excludes if excludes else []
        attributes = {attr.identifier for attr in src.bl_rna.properties if attr.identifier not in excludes}
        for attr in attributes:
            try:
                setattr(dst, attr, getattr(src, attr))
            except Exception as exc:  # pylint: disable=broad-except
                fails.append((dst, attr, exc))
        if fails:
            print(f"Failed to copy all attributes: {fails}")

    dst.nodes.clear()
    dst.links.clear()

    node_mapping = {}  # To not have to look up the new node for linking
    for src_node in src.nodes:  # Copy all nodes
        node_mapping[src_node] = dst.nodes.new(src_node.bl_idname)

    for src_node, dst_node in node_mapping.items():
        if src_node.parent is not None:
            dst_node.parent = node_mapping[src_node.parent]
        copy_attributes(src_node, dst_node, excludes=EXCLUDE_FROM_NODE)

    for src_node, dst_node in node_mapping.items():
        input_output_exclude = EXCLUDE_FROM_GROUP_INPUT_OUTPUT
        if src_node.type == "REROUTE":
            input_output_exclude += ("default_value",)
        for src_input, dst_input in zip(src_node.inputs, dst_node.inputs):  # Copy all inputs
            copy_attributes(src_input, dst_input, excludes=input_output_exclude)
        for src_output, dst_output in zip(src_node.outputs, dst_node.outputs):  # Copy all outputs
            copy_attributes(src_output, dst_output, excludes=input_output_exclude)

        for i, src_input in enumerate(src_node.inputs):  # Link all nodes
            for link in src_input.links:
                connected_node = node_mapping[link.from_node]
                dst.links.new(connected_node.outputs[link.from_socket.name], dst_node.inputs[i])

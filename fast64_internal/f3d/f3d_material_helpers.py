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


EXCLUDE_FROM_NODE = (
    "rna_type",
    "type",
    "inputs",
    "outputs",
    "dimensions",
    "interface",
    "internal_links",
    "texture_mapping",
    "color_mapping",
    "image_user",
)
EXCLUDE_FROM_INPUT_OUTPUT = (
    "rna_type",
    "label",
    "identifier",
    "is_output",
    "is_linked",
    "is_multi_input",
    "node",
    "bl_idname",
    "default_value",
    "is_unavailable",
)


def node_tree_copy(src: NodeTree, dst: NodeTree):
    def copy_attributes(src, dst, excludes=None):
        fails, excludes = [], excludes if excludes else []
        attributes = (attr.identifier for attr in src.bl_rna.properties if attr.identifier not in excludes)
        for attr in attributes:
            try:
                setattr(dst, attr, getattr(src, attr))
            except Exception as exc:  # pylint: disable=broad-except
                fails.append(exc)
        if fails:
            raise AttributeError("Failed to copy all attributes: " + str(fails))

    dst.nodes.clear()
    dst.links.clear()

    node_mapping = {}  # To not have to look up the new node for linking
    for src_node in src.nodes:  # Copy all nodes
        new_node = dst.nodes.new(src_node.bl_idname)
        copy_attributes(src_node, new_node, excludes=EXCLUDE_FROM_NODE)
        node_mapping[src_node] = new_node
    for src_node, dst_node in node_mapping.items():
        for i, src_input in enumerate(src_node.inputs):  # Link all nodes
            for link in src_input.links:
                connected_node = dst.nodes[link.from_node.name]
                dst.links.new(connected_node.outputs[link.from_socket.name], dst_node.inputs[i])

        for src_input, dst_input in zip(src_node.inputs, dst_node.inputs):  # Copy all inputs
            copy_attributes(src_input, dst_input, excludes=EXCLUDE_FROM_INPUT_OUTPUT)
        for src_output, dst_output in zip(src_node.outputs, dst_node.outputs):  # Copy all outputs
            copy_attributes(src_output, dst_output, excludes=EXCLUDE_FROM_INPUT_OUTPUT)

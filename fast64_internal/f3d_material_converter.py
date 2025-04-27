# This is not in the f3d package since copying materials requires copying collision settings from all games as well.

import bpy
from bpy.utils import register_class, unregister_class
from .f3d.f3d_material import *
from .f3d.f3d_material_helpers import node_tree_copy
from .utility import *
from bl_operators.presets import AddPresetBase


def upgrade_f3d_version_all_meshes() -> None:
    objs = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    f3d_node_tree = get_f3d_node_tree()

    # Remove original v2 node groups so that they can be recreated.
    deleteGroups = []
    for node_tree in bpy.data.node_groups:
        if node_tree.name[-6:] == "F3D v" + str(F3D_MAT_CUR_VERSION):
            deleteGroups.append(node_tree)
    for deleteGroup in deleteGroups:
        bpy.data.node_groups.remove(deleteGroup)

    set_best_draw_layer_for_materials()

    # Dict of non-f3d materials : converted f3d materials
    # handles cases where materials are used in multiple objects
    materialDict = {}
    for obj in objs:
        upgradeF3DVersionOneObject(obj, materialDict, f3d_node_tree)


def upgradeF3DVersionOneObject(obj, materialDict, f3d_node_tree: bpy.types.NodeTree):
    for index in range(len(obj.material_slots)):
        material = obj.material_slots[index].material
        if material is not None and material.is_f3d and material not in materialDict:
            convertF3DtoNewVersion(obj, index, material, f3d_node_tree)
            materialDict[material] = material


V4PresetName = {
    "Unlit Texture": "sm64_unlit_texture",
    "Unlit Texture Cutout": "sm64_unlit_texture_cutout",
    "Shaded Solid": "sm64_shaded_solid",
    "Shaded Texture": "sm64_shaded_texture",
    "Shaded Texture Cutout": "sm64_shaded_texture_cutout",
    "Shaded Texture Transparent": "sm64_shaded_texture_transparent",
    "Environment Mapped": "sm64_environment_map",
    "Decal On Shaded Solid": "sm64_decal",
    "Vertex Colored Texture": "sm64_vertex_colored_texture",
    "Fog Shaded Texture": "sm64_fog_shaded_texture",
    "Fog Shaded Texture Cutout": "sm64_fog_shaded_texture_cutout",
    "Fog Shaded Texture Transparent": "sm64_fog_shaded_texture_transparent",
    "Vertex Colored Texture Transparent": "sm64_vertex_colored_texture_transparent",
    "Shaded Noise": "sm64_shaded_noise",
}


def getV4PresetName(name):
    newName = None
    if name in V4PresetName:
        newName = V4PresetName[name]
    else:
        newName = "Custom"
    return newName


def get_group_from_polygon(obj: bpy.types.Object, polygon: bpy.types.MeshPolygon):
    sample_vert: bpy.types.MeshVertex = obj.data.vertices[polygon.vertices[0]]
    if len(sample_vert.groups):
        g: bpy.types.VertexGroupElement = None
        for g in sample_vert.groups:
            if g.weight > 0.99:
                return obj.vertex_groups[sample_vert.groups[0].group]
    return None


def has_valid_mat_ver(material: bpy.types.Material):
    return getattr(material, "mat_ver", -1) >= 1


def set_best_draw_layer_for_materials():
    bone_map = {}
    for armature in bpy.data.armatures:
        bone: bpy.types.Bone = None
        for bone in armature.bones:
            bone_map[bone.name] = bone

    finished_mats = set()

    objects = bpy.data.objects
    obj: bpy.types.Object = None
    for obj in objects:
        if obj.type != "MESH" or len(obj.material_slots) < 1:
            continue

        p: bpy.types.MeshPolygon = None
        for p in obj.data.polygons:
            mat: bpy.types.Material = obj.material_slots[p.material_index].material
            if not has_valid_mat_ver(mat) or mat.mat_ver >= 4 or mat.name in finished_mats:
                continue
            mat.f3d_update_flag = True
            # default to object's draw layer
            with bpy.context.temp_override(material=mat):
                mat.f3d_mat.draw_layer.sm64 = obj.draw_layer_static

            if len(obj.vertex_groups) == 0:
                continue  # object doesn't have vertex groups

            # get vertex group in the polygon
            group = get_group_from_polygon(obj, p)
            if isinstance(group, bpy.types.VertexGroup):
                # check for matching bone from group name
                bone = bone_map.get(group.name)
                if bone is not None:
                    mat.f3d_update_flag = True
                    # override material draw later with bone's draw layer
                    with bpy.context.temp_override(material=mat):
                        mat.f3d_mat.draw_layer.sm64 = bone.draw_layer
            finished_mats.add(mat.name)

    for obj in objects:
        if obj.type != "MESH":
            continue
        for mat_slot in obj.material_slots:
            mat: bpy.types.Material = mat_slot.material
            if not has_valid_mat_ver(mat) or mat.mat_ver >= 4 or mat.name in finished_mats:
                continue

            mat.f3d_update_flag = True
            with bpy.context.temp_override(material=mat):
                mat.f3d_mat.draw_layer.sm64 = obj.draw_layer_static
            finished_mats.add(mat.name)


def convertF3DtoNewVersion(
    obj: bpy.types.Object | bpy.types.Bone, index: int, material, f3d_node_tree: bpy.types.NodeTree
):
    try:
        if not has_valid_mat_ver(material):
            return
        if material.mat_ver > 3:
            oldPreset = AddPresetBase.as_filename(material.f3d_mat.presetName)
        else:
            oldPreset = material.get("f3d_preset")

        update_preset_manual_v4(material, getV4PresetName(oldPreset))
        # HACK: We can´t just lock, so make is_f3d temporarly false
        material.is_f3d, material.f3d_update_flag = False, True
        # Convert before node tree changes, as old materials store some values in the actual nodes
        if material.mat_ver <= 3:
            convertToNewMat(material)

        node_tree_copy(f3d_node_tree, material.node_tree)

        material.is_f3d, material.f3d_update_flag = True, False
        material.mat_ver = F3D_MAT_CUR_VERSION

        createScenePropertiesForMaterial(material)
        with bpy.context.temp_override(material=material):
            update_all_node_values(material, bpy.context)  # Reload everything

    except Exception as exc:
        print("Failed to upgrade", material.name)
        traceback.print_exc()


def convertAllBSDFtoF3D(objs, renameUV):
    # Dict of non-f3d materials : converted f3d materials
    # handles cases where materials are used in multiple objects
    materialDict = {}
    for obj in objs:
        if renameUV:
            for uv_layer in obj.data.uv_layers:
                uv_layer.name = "UVMap"
        for index in range(len(obj.material_slots)):
            material = obj.material_slots[index].material
            if material is not None and not material.is_f3d:
                if material in materialDict:
                    print("Existing material")
                    obj.material_slots[index].material = materialDict[material]
                else:
                    print("New material")
                    convertBSDFtoF3D(obj, index, material, materialDict)


def convertBSDFtoF3D(obj, index, material, materialDict):
    if not material.use_nodes:
        newMaterial = createF3DMat(obj, preset="Shaded Solid", index=index)
        with bpy.context.temp_override(material=newMaterial):
            newMaterial.f3d_mat.default_light_color = material.diffuse_color
        updateMatWithName(newMaterial, material, materialDict)

    elif "Principled BSDF" in material.node_tree.nodes:
        tex0Node = material.node_tree.nodes["Principled BSDF"].inputs["Base Color"]
        if len(tex0Node.links) == 0:
            newMaterial = createF3DMat(obj, preset=getDefaultMaterialPreset("Shaded Solid"), index=index)
            with bpy.context.temp_override(material=newMaterial):
                newMaterial.f3d_mat.default_light_color = tex0Node.default_value
            updateMatWithName(newMaterial, material, materialDict)
        else:
            if isinstance(tex0Node.links[0].from_node, bpy.types.ShaderNodeTexImage):
                if "convert_preset" in material:
                    presetName = material["convert_preset"]
                    if presetName not in [enumValue[0] for enumValue in enumMaterialPresets]:
                        raise PluginError(
                            "During BSDF to F3D conversion, for material '"
                            + material.name
                            + "',"
                            + " enum '"
                            + presetName
                            + "' was not found in material preset enum list."
                        )
                else:
                    presetName = getDefaultMaterialPreset("Shaded Texture")
                newMaterial = createF3DMat(obj, preset=presetName, index=index)
                with bpy.context.temp_override(material=newMaterial):
                    newMaterial.f3d_mat.tex0.tex = tex0Node.links[0].from_node.image
                updateMatWithName(newMaterial, material, materialDict)
            else:
                print("Principled BSDF material does not have an Image Node attached to its Base Color.")
    else:
        print("Material is not a Principled BSDF or non-node material.")


def updateMatWithName(f3dMat, oldMat, materialDict):
    f3dMat.name = oldMat.name + "_f3d"
    update_preset_manual(f3dMat, bpy.context)
    materialDict[oldMat] = f3dMat


class BSDFConvert(bpy.types.Operator):
    # set bl_ properties
    bl_idname = "object.convert_bsdf"
    bl_label = "Principled BSDF to F3D Converter"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        try:
            if context.mode != "OBJECT":
                raise PluginError("Operator can only be used in object mode.")

            if context.scene.bsdf_conv_all:
                convertAllBSDFtoF3D(
                    [obj for obj in bpy.data.objects if obj.type == "MESH"],
                    context.scene.rename_uv_maps,
                )
            else:
                if len(context.selected_objects) == 0:
                    raise PluginError("Mesh not selected.")
                elif type(context.selected_objects[0].data) is not bpy.types.Mesh:
                    raise PluginError("Mesh not selected.")

                obj = context.selected_objects[0]
                convertAllBSDFtoF3D([obj], context.scene.rename_uv_maps)

        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        self.report({"INFO"}, "Created F3D material.")
        return {"FINISHED"}  # must return a set


class MatUpdateConvert(bpy.types.Operator):
    # set bl_ properties
    bl_idname = "object.convert_f3d_update"
    bl_label = "Recreate F3D Materials As v" + str(F3D_MAT_CUR_VERSION)
    bl_options = {"UNDO"}

    update_conv_all: bpy.props.BoolProperty(default=True)

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        try:
            if context.mode != "OBJECT":
                raise PluginError("Operator can only be used in object mode.")

            if self.update_conv_all:
                upgrade_f3d_version_all_meshes()
            else:
                if len(context.selected_objects) == 0:
                    raise PluginError("Mesh not selected.")
                elif type(context.selected_objects[0].data) is not bpy.types.Mesh:
                    raise PluginError("Mesh not selected.")

                obj = context.selected_objects[0]
                upgradeF3DVersionOneObject(obj, {}, get_f3d_node_tree())

        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        self.report({"INFO"}, "Created F3D material.")
        return {"FINISHED"}  # must return a set


class F3DMaterialConverterPanel(bpy.types.Panel):
    bl_label = "F3D Material Converter"
    bl_idname = "MATERIAL_PT_F3D_Material_Converter"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Fast64"

    @classmethod
    def poll(cls, context):
        return True
        # return hasattr(context, 'object') and context.object is not None and \
        # 	isinstance(context.object.data, bpy.types.Mesh)

    def draw(self, context):
        # mesh = context.object.data
        self.layout.operator(BSDFConvert.bl_idname)
        self.layout.prop(context.scene, "bsdf_conv_all")
        self.layout.prop(context.scene, "rename_uv_maps")
        op = self.layout.operator(MatUpdateConvert.bl_idname)
        op.update_conv_all = context.scene.update_conv_all
        self.layout.prop(context.scene, "update_conv_all")
        self.layout.operator(ReloadDefaultF3DPresets.bl_idname)


bsdf_conv_classes = (
    BSDFConvert,
    MatUpdateConvert,
)

bsdf_conv_panel_classes = (F3DMaterialConverterPanel,)


def bsdf_conv_panel_regsiter():
    for cls in bsdf_conv_panel_classes:
        register_class(cls)


def bsdf_conv_panel_unregsiter():
    for cls in bsdf_conv_panel_classes:
        unregister_class(cls)


def bsdf_conv_register():
    for cls in bsdf_conv_classes:
        register_class(cls)

    # Moved to Level Root
    bpy.types.Scene.bsdf_conv_all = bpy.props.BoolProperty(name="Convert all objects", default=True)
    bpy.types.Scene.update_conv_all = bpy.props.BoolProperty(name="Convert all objects", default=True)
    bpy.types.Scene.rename_uv_maps = bpy.props.BoolProperty(name="Rename UV maps", default=True)


def bsdf_conv_unregister():
    for cls in bsdf_conv_classes:
        unregister_class(cls)

    del bpy.types.Scene.bsdf_conv_all
    del bpy.types.Scene.update_conv_all
    del bpy.types.Scene.rename_uv_maps

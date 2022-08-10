# This is not in the f3d package since copying materials requires copying collision settings from all games as well.

import bpy, math
from bpy.utils import register_class, unregister_class
from .f3d.f3d_material import *
from .sm64.sm64_collision import CollisionSettings
from .utility import *
from bl_operators.presets import AddPresetBase


def upgradeF3DVersionAll(objs, armatures, version):
    # Remove original v2 node groups so that they can be recreated.
    deleteGroups = []
    for node_tree in bpy.data.node_groups:
        if node_tree.name[-6:] == "F3D v" + str(version):
            deleteGroups.append(node_tree)
    for deleteGroup in deleteGroups:
        bpy.data.node_groups.remove(deleteGroup)

    set_best_draw_layer_for_materials()

    # Dict of non-f3d materials : converted f3d materials
    # handles cases where materials are used in multiple objects
    materialDict = {}
    for obj in objs:
        upgradeF3DVersionOneObject(obj, materialDict, version)

    for armature in armatures:
        for bone in armature.bones:
            if bone.geo_cmd == "Switch":
                for switchOption in bone.switch_options:
                    if switchOption.switchType == "Material":
                        if switchOption.materialOverride in materialDict:
                            switchOption.materialOverride = materialDict[switchOption.materialOverride]
                        for i in range(len(switchOption.specificOverrideArray)):
                            material = switchOption.specificOverrideArray[i].material
                            if material in materialDict:
                                switchOption.specificOverrideArray[i].material = materialDict[material]
                        for i in range(len(switchOption.specificIgnoreArray)):
                            material = switchOption.specificIgnoreArray[i].material
                            if material in materialDict:
                                switchOption.specificIgnoreArray[i].material = materialDict[material]


def upgradeF3DVersionOneObject(obj, materialDict, version):
    for index in range(len(obj.material_slots)):
        material = obj.material_slots[index].material
        if material is not None and material.is_f3d:
            if material in materialDict:
                obj.material_slots[index].material = materialDict[material]
            else:
                convertF3DtoNewVersion(obj, index, material, materialDict, version)


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
        if not isinstance(obj.data, bpy.types.Mesh) or len(obj.material_slots) < 1:
            continue

        p: bpy.types.MeshPolygon = None
        for p in obj.data.polygons:
            mat: bpy.types.Material = obj.material_slots[p.material_index].material
            if not has_valid_mat_ver(mat) or mat.mat_ver >= 4 or mat.name in finished_mats:
                continue

            # default to object's draw layer
            mat.f3d_mat.draw_layer.sm64 = obj.draw_layer_static

            # get vertex group in the polygon
            group = get_group_from_polygon(obj, p)
            if isinstance(group, bpy.types.VertexGroup):
                # check for matching bone from group name
                bone = bone_map.get(group.name)
                if bone is not None:
                    # override material draw later with bone's draw layer
                    mat.f3d_mat.draw_layer.sm64 = bone.draw_layer
            finished_mats.add(mat.name)

    for obj in objects:
        if not isinstance(obj.data, bpy.types.Mesh):
            continue
        for mat_slot in obj.material_slots:
            mat: bpy.types.Material = mat_slot.material
            if not has_valid_mat_ver(mat) or mat.mat_ver >= 4 or mat.name in finished_mats:
                continue

            mat.f3d_mat.draw_layer.sm64 = obj.draw_layer_static
            finished_mats.add(mat.name)


def convertF3DtoNewVersion(obj: bpy.types.Object | bpy.types.Bone, index, material, materialDict, version):
    try:
        if not has_valid_mat_ver(material):
            return
        if material.mat_ver > 3:
            oldPreset = AddPresetBase.as_filename(material.f3d_mat.presetName)
        else:
            oldPreset = material.get("f3d_preset")

        newMat = createF3DMat(obj, preset=getV4PresetName(oldPreset), index=index)

        if material.mat_ver > 3:
            copyPropertyGroup(material.f3d_mat, newMat.f3d_mat)
        else:
            convertToNewMat(newMat, material)

        newMat.f3d_mat.draw_layer.sm64 = material.f3d_mat.draw_layer.sm64

        copyPropertyGroup(material.ootMaterial, newMat.ootMaterial)
        copyPropertyGroup(material.flipbookGroup, newMat.flipbookGroup)
        copyPropertyGroup(material.ootCollisionProperty, newMat.ootCollisionProperty)

        colSettings = CollisionSettings()
        colSettings.load(material)
        colSettings.apply(newMat)

        updateMatWithNewVersionName(newMat, material, materialDict, version)
    except Exception as exc:
        print("Failed to upgrade", material.name)
        print(exc)


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
        f3dMat = newMaterial.f3d_mat if newMaterial.mat_ver > 3 else newMaterial
        f3dMat.default_light_color = material.diffuse_color
        updateMatWithName(newMaterial, material, materialDict)

    elif "Principled BSDF" in material.node_tree.nodes:
        tex0Node = material.node_tree.nodes["Principled BSDF"].inputs["Base Color"]
        tex1Node = material.node_tree.nodes["Principled BSDF"].inputs["Subsurface Color"]
        if len(tex0Node.links) == 0:
            newMaterial = createF3DMat(obj, preset=getDefaultMaterialPreset("Shaded Solid"), index=index)
            f3dMat = newMaterial.f3d_mat if newMaterial.mat_ver > 3 else newMaterial
            f3dMat.default_light_color = tex0Node.default_value
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
                f3dMat = newMaterial.f3d_mat if newMaterial.mat_ver > 3 else newMaterial
                f3dMat.tex0.tex = tex0Node.links[0].from_node.image
                if len(tex1Node.links) > 0 and isinstance(tex1Node.links[0].from_node, bpy.types.ShaderNodeTexImage):
                    f3dMat.tex1.tex = tex1Node.links[0].from_node.image
                updateMatWithName(newMaterial, material, materialDict)
            else:
                print("Principled BSDF material does not have an Image Node attached to its Base Color.")
    else:
        print("Material is not a Principled BSDF or non-node material.")


def updateMatWithName(f3dMat, oldMat, materialDict):
    f3dMat.name = oldMat.name + "_f3d"
    update_preset_manual(f3dMat, bpy.context)
    materialDict[oldMat] = f3dMat


def updateMatWithNewVersionName(f3dMat, oldMat, materialDict, version):
    name = oldMat.name
    f3dMat.name = name
    oldMat.name = name + "_v" + str(oldMat.mat_ver)
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
                    [obj for obj in bpy.data.objects if isinstance(obj.data, bpy.types.Mesh)],
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
    version = 5
    bl_idname = "object.convert_f3d_update"
    bl_label = "Recreate F3D Materials As v" + str(version)
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        try:
            if context.mode != "OBJECT":
                raise PluginError("Operator can only be used in object mode.")

            if context.scene.update_conv_all:
                upgradeF3DVersionAll(
                    [obj for obj in bpy.data.objects if isinstance(obj.data, bpy.types.Mesh)],
                    bpy.data.armatures,
                    self.version,
                )
            else:
                if len(context.selected_objects) == 0:
                    raise PluginError("Mesh not selected.")
                elif type(context.selected_objects[0].data) is not bpy.types.Mesh:
                    raise PluginError("Mesh not selected.")

                obj = context.selected_objects[0]
                upgradeF3DVersionOneObject(obj, {}, self.version)

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
        self.layout.operator(MatUpdateConvert.bl_idname)
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

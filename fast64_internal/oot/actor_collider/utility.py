from ...utility import PluginError, parentObject
from ..oot_f3d_writer import getColliderMat
import bpy, math, mathutils

ootEnumColliderShape = [
    ("COLSHAPE_JNTSPH", "Joint Sphere", "Joint Sphere"),
    ("COLSHAPE_CYLINDER", "Cylinder", "Cylinder"),
    ("COLSHAPE_TRIS", "Triangles", "Triangles"),
    ("COLSHAPE_QUAD", "Quad (Properties Only)", "Quad"),
]

ootEnumColliderType = [
    ("COLTYPE_HIT0", "Blue Blood, White Hitmark", "Blue Blood, White Hitmark"),
    ("COLTYPE_HIT1", "No Blood, Dust Hitmark", "No Blood, Dust Hitmark"),
    ("COLTYPE_HIT2", "Green Blood, Dust Hitmark", "Green Blood, Dust Hitmark"),
    ("COLTYPE_HIT3", "No Blood, White Hitmark", "No Blood, White Hitmark"),
    ("COLTYPE_HIT4", "Water Burst, No hitmark", "Water Burst, No hitmark"),
    ("COLTYPE_HIT5", "No blood, Red Hitmark", "No blood, Red Hitmark"),
    ("COLTYPE_HIT6", "Green Blood, White Hitmark", "Green Blood, White Hitmark"),
    ("COLTYPE_HIT7", "Red Blood, White Hitmark", "Red Blood, White Hitmark"),
    ("COLTYPE_HIT8", "Blue Blood, Red Hitmark", "Blue Blood, Red Hitmark"),
    ("COLTYPE_METAL", "Metal", "Metal"),
    ("COLTYPE_NONE", "None", "None"),
    ("COLTYPE_WOOD", "Wood", "Wood"),
    ("COLTYPE_HARD", "Hard", "Hard"),
    ("COLTYPE_TREE", "Tree", "Tree"),
]

ootEnumColliderElement = [
    ("ELEMTYPE_UNK0", "Element 0", "Element 0"),
    ("ELEMTYPE_UNK1", "Element 1", "Element 1"),
    ("ELEMTYPE_UNK2", "Element 2", "Element 2"),
    ("ELEMTYPE_UNK3", "Element 3", "Element 3"),
    ("ELEMTYPE_UNK4", "Element 4", "Element 4"),
    ("ELEMTYPE_UNK5", "Element 5", "Element 5"),
    ("ELEMTYPE_UNK6", "Element 6", "Element 6"),
    ("ELEMTYPE_UNK7", "Element 7", "Element 7"),
]

ootEnumHitboxSound = [
    ("TOUCH_SFX_NORMAL", "Hurtbox", "Hurtbox"),
    ("TOUCH_SFX_HARD", "Hard", "Hard"),
    ("TOUCH_SFX_WOOD", "Wood", "Wood"),
    ("TOUCH_SFX_NONE", "None", "None"),
]


def getGeometryNodes(shapeName: str):
    nodesName = shapeNameToBlenderName(shapeName)
    if nodesName in bpy.data.node_groups:
        return bpy.data.node_groups[nodesName]
    else:
        node_group = bpy.data.node_groups.new(nodesName, "GeometryNodeTree")
        node_group.use_fake_user = True
        inNode = node_group.nodes.new("NodeGroupInput")
        node_group.inputs.new("NodeSocketGeometry", "Geometry")
        node_group.inputs.new("NodeSocketMaterial", "Material")
        outNode = node_group.nodes.new("NodeGroupOutput")
        node_group.outputs.new("NodeSocketGeometry", "Geometry")

        if nodesName == "oot_collider_sphere":
            # Sphere
            shape = node_group.nodes.new("GeometryNodeMeshUVSphere")
            shape.inputs["Segments"].default_value = 16
            shape.inputs["Rings"].default_value = 8
            shape.inputs["Radius"].default_value = 1

            # Shade Smooth
            smooth = node_group.nodes.new("GeometryNodeSetShadeSmooth")
            node_group.links.new(shape.outputs["Mesh"], smooth.inputs["Geometry"])
            lastNode = smooth

        elif nodesName == "oot_collider_cylinder":

            # Cylinder
            shape = node_group.nodes.new("GeometryNodeMeshCylinder")
            shape.inputs["Vertices"].default_value = 16
            shape.inputs["Radius"].default_value = 1
            shape.inputs["Depth"].default_value = 2

            # Shade Smooth
            smooth = node_group.nodes.new("GeometryNodeSetShadeSmooth")
            node_group.links.new(shape.outputs["Mesh"], smooth.inputs["Geometry"])
            node_group.links.new(shape.outputs["Side"], smooth.inputs["Selection"])

            # Transform
            transform = node_group.nodes.new("GeometryNodeTransform")
            node_group.links.new(smooth.outputs["Geometry"], transform.inputs["Geometry"])
            transform.inputs["Translation"].default_value[2] = 1
            lastNode = transform

        elif nodesName == "oot_collider_triangles":
            lastNode = inNode

        elif nodesName == "oot_collider_quad":
            # Grid
            shape = node_group.nodes.new("GeometryNodeMeshGrid")
            shape.inputs["Size X"].default_value = 2
            shape.inputs["Size Y"].default_value = 2
            shape.inputs["Vertices X"].default_value = 2
            shape.inputs["Vertices Y"].default_value = 2

            # Transform
            transform = node_group.nodes.new("GeometryNodeTransform")
            node_group.links.new(shape.outputs["Mesh"], transform.inputs["Geometry"])
            transform.inputs["Rotation"].default_value[0] = math.radians(90)
            lastNode = transform

        else:
            raise PluginError(f"Could not find node group name: {nodesName}")

        # Set Material
        setMat = node_group.nodes.new("GeometryNodeSetMaterial")
        node_group.links.new(lastNode.outputs["Geometry"], setMat.inputs["Geometry"])
        node_group.links.new(inNode.outputs["Material"], setMat.inputs["Material"])
        node_group.links.new(setMat.outputs["Geometry"], outNode.inputs["Geometry"])

        return node_group


# Apply geometry nodes for the correct collider shape
def applyColliderGeoNodes(obj: bpy.types.Object, material: bpy.types.Material, shapeName: str) -> None:
    if "Collider Shape" not in obj.modifiers:
        modifier = obj.modifiers.new("Collider Shape", "NODES")
    else:
        modifier = obj.modifiers["Collider Shape"]
    modifier.node_group = getGeometryNodes(shapeName)
    modifier["Input_1"] = material


# Update collider callback for collider type property
def updateCollider(self, context: bpy.types.Context) -> None:
    updateColliderOnObj(context.object)


def updateColliderOnObj(obj: bpy.types.Object, updateJointSiblings: bool = True) -> None:
    if obj.ootGeometryType == "Actor Collider":
        colliderProp = obj.ootActorCollider
        if colliderProp.colliderShape == "COLSHAPE_JNTSPH":
            if obj.parent == None:
                return
            queryProp = obj.parent.ootActorCollider
        else:
            queryProp = colliderProp

        alpha = 0.7
        # if colliderProp.colliderShape == "COLSHAPE_TRIS":
        #    material = getColliderMat("oot_collider_cyan", (0, 0.5, 1, alpha))
        if colliderProp.colliderShape == "COLSHAPE_QUAD":
            material = getColliderMat("oot_collider_orange", (0.2, 0.05, 0, alpha))
        elif queryProp.hitbox.enable and queryProp.hurtbox.enable:
            material = getColliderMat("oot_collider_purple", (0.15, 0, 0.05, alpha))
        elif queryProp.hitbox.enable:
            material = getColliderMat("oot_collider_red", (0.2, 0, 0, alpha))
        elif queryProp.hurtbox.enable:
            material = getColliderMat("oot_collider_blue", (0, 0, 0.2, alpha))
        else:
            material = getColliderMat("oot_collider_white", (0.2, 0.2, 0.2, alpha))
        applyColliderGeoNodes(obj, material, colliderProp.colliderShape)

        if updateJointSiblings and colliderProp.colliderShape == "COLSHAPE_JNTSPH" and obj.parent is not None:
            for child in obj.parent.children:
                updateColliderOnObj(child, False)


def addColliderThenParent(
    shapeName: str, obj: bpy.types.Object, bone: bpy.types.Bone | None, notMeshCollider: bool = True
) -> bpy.types.Object:
    colliderObj = addCollider(shapeName, notMeshCollider)
    if bone is not None:

        # If no active bone is set, then parenting operator fails.
        obj.data.bones.active = obj.data.bones[0]
        obj.data.bones[0].select = True

        parentObject(obj, colliderObj, "BONE")
        colliderObj.parent_bone = bone.name
        colliderObj.matrix_world = obj.matrix_world @ obj.pose.bones[bone.name].matrix
    else:
        parentObject(obj, colliderObj)
        # 10 = default value for ootBlenderScale
        colliderObj.matrix_local = mathutils.Matrix.Diagonal(colliderObj.matrix_local.decompose()[2].to_4d())
    updateColliderOnObj(colliderObj)
    return colliderObj


def addCollider(shapeName: str, notMeshCollider: bool) -> bpy.types.Object:
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")

    # Mesh shape only matters for Triangle shape, otherwise will be controlled by geometry nodes.
    location = mathutils.Vector(bpy.context.scene.cursor.location)
    bpy.ops.mesh.primitive_plane_add(size=2, enter_editmode=False, align="WORLD", location=location[:])
    planeObj = bpy.context.view_layer.objects.active
    if notMeshCollider:
        planeObj.data.clear_geometry()
    else:
        material = bpy.data.materials.new(f"Mesh Collider Material")
        planeObj.data.materials.append(material)
    planeObj.name = "Collider"
    planeObj.ootGeometryType = "Actor Collider"

    if shapeName == "COLSHAPE_CYLINDER":
        planeObj.lock_location = (True, True, False)
        planeObj.lock_rotation = (True, True, True)

    actorCollider = planeObj.ootActorCollider
    actorCollider.colliderShape = shapeName
    actorCollider.physics.enable = True
    return planeObj


def shapeNameToBlenderName(shapeName: str) -> str:
    return shapeNameLookup(
        shapeName,
        {
            "COLSHAPE_JNTSPH": "oot_collider_sphere",
            "COLSHAPE_CYLINDER": "oot_collider_cylinder",
            "COLSHAPE_TRIS": "oot_collider_triangles",
            "COLSHAPE_QUAD": "oot_collider_quad",
        },
    )


def shapeNameToSimpleName(shapeName: str) -> str:
    return shapeNameLookup(
        shapeName,
        {
            "COLSHAPE_JNTSPH": "Sphere",
            "COLSHAPE_CYLINDER": "Cylinder",
            "COLSHAPE_TRIS": "Mesh",
            "COLSHAPE_QUAD": "Quad",
        },
    )


def shapeNameLookup(shapeName: str, nameDict: dict[str, str]) -> str:
    if shapeName in nameDict:
        name = nameDict[shapeName]
        return name
    else:
        raise PluginError(f"Could not find shape name {shapeName} in name dictionary.")

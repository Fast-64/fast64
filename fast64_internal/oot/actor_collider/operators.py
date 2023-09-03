import bpy
from ...utility import PluginError, raisePluginError, copyPropertyGroup
from .utility import updateColliderOnObj, addColliderThenParent, ootEnumColliderShape
from bpy.utils import register_class, unregister_class


class OOT_AddActorCollider(bpy.types.Operator):
    bl_idname = "object.oot_add_actor_collider_operator"
    bl_label = "Add Actor Collider"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    shape: bpy.props.EnumProperty(items=ootEnumColliderShape)
    parentToBone: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        try:
            activeObj = bpy.context.view_layer.objects.active
            selectedObjs = bpy.context.selected_objects

            if activeObj is None:
                raise PluginError("No object selected.")

            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.select_all(action="DESELECT")

            if self.parentToBone and self.shape == "COLSHAPE_JNTSPH":
                if isinstance(activeObj.data, bpy.types.Armature):
                    selectedBones = [bone for bone in activeObj.data.bones if bone.select]
                    if len(selectedBones) == 0:
                        raise PluginError("Cannot add joint spheres since no bones are selected on armature.")
                    for bone in selectedBones:
                        addColliderThenParent(self.shape, activeObj, bone, self.shape != "COLSHAPE_TRIS")
                else:
                    raise PluginError("Non armature object selected.")
            else:
                addColliderThenParent(self.shape, activeObj, None, self.shape != "COLSHAPE_TRIS")

        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        return {"FINISHED"}


class OOT_CopyColliderProperties(bpy.types.Operator):
    bl_idname = "object.oot_copy_collider_properties_operator"
    bl_label = "Copy Collider Properties"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        try:
            activeObj = bpy.context.view_layer.objects.active
            selectedObjs = [obj for obj in bpy.context.selected_objects if obj.ootGeometryType == "Actor Collider"]

            if activeObj is None:
                raise PluginError("No object selected.")

            if activeObj.ootGeometryType != "Actor Collider":
                raise PluginError("Active object is not an actor collider.")

            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.select_all(action="DESELECT")

            if (
                activeObj.ootActorCollider.colliderShape == "COLSHAPE_JNTSPH"
                and activeObj.parent is not None
                and isinstance(activeObj.parent.data, bpy.types.Armature)
            ):
                parentCollider = activeObj.parent.ootActorCollider
            else:
                parentCollider = activeObj.ootActorCollider

            for obj in selectedObjs:
                if (
                    obj.ootActorCollider.colliderShape == "COLSHAPE_JNTSPH"
                    and obj.parent is not None
                    and isinstance(obj.parent.data, bpy.types.Armature)
                ):
                    copyPropertyGroup(parentCollider, obj.parent.ootActorCollider)
                else:
                    copyPropertyGroup(parentCollider, obj.ootActorCollider)
                copyPropertyGroup(activeObj.ootActorColliderItem, obj.ootActorColliderItem)

                updateColliderOnObj(obj)

        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        return {"FINISHED"}


actor_collider_ops_classes = (
    OOT_AddActorCollider,
    OOT_CopyColliderProperties,
)


def actor_collider_ops_register():
    for cls in actor_collider_ops_classes:
        register_class(cls)


def actor_collider_ops_unregister():
    for cls in reversed(actor_collider_ops_classes):
        unregister_class(cls)

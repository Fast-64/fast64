import bpy
from .utility import shapeNameToSimpleName
from bpy.utils import register_class, unregister_class


class OOT_ActorColliderPanel(bpy.types.Panel):
    bl_label = "OOT Actor Collider Inspector"
    bl_idname = "OBJECT_PT_OOT_Actor_Collider_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.scene.gameEditorMode == "OOT" and (
            context.object is not None and isinstance(context.object.data, bpy.types.Mesh)
        )

    def draw(self, context: bpy.types.Context):
        obj = context.object
        if obj.ootGeometryType == "Actor Collider":
            box = self.layout.box().column()
            name = shapeNameToSimpleName(obj.ootActorCollider.colliderShape)
            box.box().label(text=f"OOT Actor {name} Collider Inspector")
            obj.ootActorCollider.draw(obj, box)
            obj.ootActorColliderItem.draw(obj, box)


def isActorCollider(context: bpy.types.Context) -> bool:
    return (
        (context.object is not None and isinstance(context.object.data, bpy.types.Mesh))
        and context.object.ootGeometryType == "Actor Collider"
        and context.material is not None
    )


class OOT_ActorColliderMaterialPanel(bpy.types.Panel):
    bl_label = "OOT Actor Collider Material Inspector"
    bl_idname = "OBJECT_PT_OOT_Actor_Collider_Material_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.scene.gameEditorMode == "OOT" and isActorCollider(context)

    def draw(self, context: bpy.types.Context):
        material = context.material
        box = self.layout.box().column()
        box.box().label(text=f"OOT Actor Mesh Collider Inspector")
        material.ootActorColliderItem.draw(None, box)


actor_collider_panel_classes = (OOT_ActorColliderPanel, OOT_ActorColliderMaterialPanel)


def actor_collider_panel_register():
    for cls in actor_collider_panel_classes:
        register_class(cls)


def actor_collider_panel_unregister():
    for cls in reversed(actor_collider_panel_classes):
        unregister_class(cls)

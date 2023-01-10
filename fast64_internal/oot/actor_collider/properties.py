import bpy, os
from bpy.utils import register_class, unregister_class
from ...utility import prop_split
from .utility import (
    updateCollider,
    ootEnumColliderShape,
    ootEnumColliderType,
    ootEnumColliderElement,
    ootEnumHitboxSound,
)


class OOTActorColliderImportExportSettings(bpy.types.PropertyGroup):
    enable: bpy.props.BoolProperty(name="Actor Colliders", default=False)
    chooseSpecific: bpy.props.BoolProperty(name="Choose Specific Colliders")
    specificColliders: bpy.props.StringProperty(name="Colliders (Comma Separated List)")
    jointSphere: bpy.props.BoolProperty(name="Joint Sphere", default=True)
    cylinder: bpy.props.BoolProperty(name="Cylinder", default=True)
    mesh: bpy.props.BoolProperty(name="Mesh", default=True)
    quad: bpy.props.BoolProperty(name="Quad", default=True)
    parentJointSpheresToBone: bpy.props.BoolProperty(name="Parent Joint Spheres To Bones", default=True)

    def draw(self, layout: bpy.types.UILayout, title: str, isImport: bool):
        col = layout.column()
        col.prop(self, "enable", text=title)
        if self.enable:
            col.prop(self, "chooseSpecific")
            if self.chooseSpecific:
                col.prop(self, "specificColliders")
            row = col.row(align=True)
            row.prop(self, "jointSphere", text="Joint Sphere", toggle=1)
            row.prop(self, "cylinder", text="Cylinder", toggle=1)
            row.prop(self, "mesh", text="Mesh", toggle=1)
            row.prop(self, "quad", text="Quad", toggle=1)

            if isImport:
                col.prop(self, "parentJointSpheresToBone")

        return col


# Defaults are from DMG_DEFAULT.
class OOTDamageFlagsProperty(bpy.types.PropertyGroup):
    expandTab: bpy.props.BoolProperty(default=False, name="Damage Flags")
    dekuNut: bpy.props.BoolProperty(default=True, name="Deku Nut")
    dekuStick: bpy.props.BoolProperty(default=True, name="Deku Stick")
    slingshot: bpy.props.BoolProperty(default=True, name="Slingshot")
    explosive: bpy.props.BoolProperty(default=True, name="Bomb")
    boomerang: bpy.props.BoolProperty(default=True, name="Boomerang")
    arrowNormal: bpy.props.BoolProperty(default=True, name="Normal")
    hammerSwing: bpy.props.BoolProperty(default=True, name="Hammer Swing")
    hookshot: bpy.props.BoolProperty(default=True, name="Hookshot")
    slashKokiriSword: bpy.props.BoolProperty(default=True, name="Kokiri")
    slashMasterSword: bpy.props.BoolProperty(default=True, name="Master")
    slashGiantSword: bpy.props.BoolProperty(default=True, name="Giant")
    arrowFire: bpy.props.BoolProperty(default=True, name="Fire")
    arrowIce: bpy.props.BoolProperty(default=True, name="Ice")
    arrowLight: bpy.props.BoolProperty(default=True, name="Light")
    arrowUnk1: bpy.props.BoolProperty(default=True, name="Unk1")
    arrowUnk2: bpy.props.BoolProperty(default=True, name="Unk2")
    arrowUnk3: bpy.props.BoolProperty(default=True, name="Unk3")
    magicFire: bpy.props.BoolProperty(default=True, name="Fire")
    magicIce: bpy.props.BoolProperty(default=True, name="Ice")
    magicLight: bpy.props.BoolProperty(default=True, name="Light")
    shield: bpy.props.BoolProperty(default=False, name="Shield")
    mirrorRay: bpy.props.BoolProperty(default=False, name="Mirror Ray")
    spinKokiriSword: bpy.props.BoolProperty(default=True, name="Kokiri")
    spinGiantSword: bpy.props.BoolProperty(default=True, name="Giant")
    spinMasterSword: bpy.props.BoolProperty(default=True, name="Master")
    jumpKokiriSword: bpy.props.BoolProperty(default=True, name="Kokiri")
    jumpGiantSword: bpy.props.BoolProperty(default=True, name="Giant")
    jumpMasterSword: bpy.props.BoolProperty(default=True, name="Master")
    unknown1: bpy.props.BoolProperty(default=True, name="Unknown 1")
    unblockable: bpy.props.BoolProperty(default=True, name="Unblockable")
    hammerJump: bpy.props.BoolProperty(default=True, name="Hammer Jump")
    unknown2: bpy.props.BoolProperty(default=True, name="Unknown 2")

    def draw(self, layout: bpy.types.UILayout):
        layout.prop(self, "expandTab", text="Damage Flags", icon="TRIA_DOWN" if self.expandTab else "TRIA_RIGHT")

        if self.expandTab:
            row = layout.row(align=True)
            row.prop(self, "dekuNut", toggle=1)
            row.prop(self, "dekuStick", toggle=1)
            row.prop(self, "slingshot", toggle=1)

            row = layout.row(align=True)
            row.prop(self, "explosive", toggle=1)
            row.prop(self, "boomerang", toggle=1)
            row.prop(self, "hookshot", toggle=1)

            row = layout.row(align=True)
            row.prop(self, "hammerSwing", toggle=1)
            row.prop(self, "hammerJump", toggle=1)

            row = layout.row(align=True)
            row.label(text="Slash")
            row.prop(self, "slashKokiriSword", toggle=1)
            row.prop(self, "slashMasterSword", toggle=1)
            row.prop(self, "slashGiantSword", toggle=1)

            row = layout.row(align=True)
            row.label(text="Spin")
            row.prop(self, "spinKokiriSword", toggle=1)
            row.prop(self, "spinMasterSword", toggle=1)
            row.prop(self, "spinGiantSword", toggle=1)

            row = layout.row(align=True)
            row.label(text="Jump")
            row.prop(self, "jumpKokiriSword", toggle=1)
            row.prop(self, "jumpMasterSword", toggle=1)
            row.prop(self, "jumpGiantSword", toggle=1)

            row = layout.row(align=True)
            row.label(text="Arrow")
            row.prop(self, "arrowNormal", toggle=1)
            row.prop(self, "arrowFire", toggle=1)
            row.prop(self, "arrowIce", toggle=1)
            row.prop(self, "arrowLight", toggle=1)

            row = layout.row(align=True)
            row.label(text="Arrow Unknown")
            row.prop(self, "arrowUnk1", toggle=1)
            row.prop(self, "arrowUnk2", toggle=1)
            row.prop(self, "arrowUnk3", toggle=1)

            row = layout.row(align=True)
            row.label(text="Magic")
            row.prop(self, "magicFire", toggle=1)
            row.prop(self, "magicIce", toggle=1)
            row.prop(self, "magicLight", toggle=1)

            row = layout.row(align=True)
            row.prop(self, "shield", toggle=1)
            row.prop(self, "mirrorRay", toggle=1)

            row = layout.row(align=True)
            row.prop(self, "unblockable", toggle=1)
            row.prop(self, "unknown1", toggle=1)
            row.prop(self, "unknown2", toggle=1)

    def to_c(self):
        flags = (
            ((1 if self.dekuNut else 0) << 0)
            | ((1 if self.dekuStick else 0) << 1)
            | ((1 if self.slingshot else 0) << 2)
            | ((1 if self.explosive else 0) << 3)
            | ((1 if self.boomerang else 0) << 4)
            | ((1 if self.arrowNormal else 0) << 5)
            | ((1 if self.hammerSwing else 0) << 6)
            | ((1 if self.hookshot else 0) << 7)
            | ((1 if self.slashKokiriSword else 0) << 8)
            | ((1 if self.slashMasterSword else 0) << 9)
            | ((1 if self.slashGiantSword else 0) << 10)
            | ((1 if self.arrowFire else 0) << 11)
            | ((1 if self.arrowIce else 0) << 12)
            | ((1 if self.arrowLight else 0) << 13)
            | ((1 if self.arrowUnk1 else 0) << 14)
            | ((1 if self.arrowUnk2 else 0) << 15)
            | ((1 if self.arrowUnk3 else 0) << 16)
            | ((1 if self.magicFire else 0) << 17)
            | ((1 if self.magicIce else 0) << 18)
            | ((1 if self.magicLight else 0) << 19)
            | ((1 if self.shield else 0) << 20)
            | ((1 if self.mirrorRay else 0) << 21)
            | ((1 if self.spinKokiriSword else 0) << 22)
            | ((1 if self.spinGiantSword else 0) << 23)
            | ((1 if self.spinMasterSword else 0) << 24)
            | ((1 if self.jumpKokiriSword else 0) << 25)
            | ((1 if self.jumpGiantSword else 0) << 26)
            | ((1 if self.jumpMasterSword else 0) << 27)
            | ((1 if self.unknown1 else 0) << 28)
            | ((1 if self.unblockable else 0) << 29)
            | ((1 if self.hammerJump else 0) << 30)
            | ((1 if self.unknown2 else 0) << 31)
        )
        return format(flags, "#010x")


# AT
class OOTColliderHitboxProperty(bpy.types.PropertyGroup):
    enable: bpy.props.BoolProperty(name="Hitbox (AT)", update=updateCollider, default=False)
    alignPlayer: bpy.props.BoolProperty(name="Player", default=False)
    alignEnemy: bpy.props.BoolProperty(name="Enemy", default=True)
    alignOther: bpy.props.BoolProperty(name="Other", default=False)
    alignSelf: bpy.props.BoolProperty(name="Self", default=False)

    def draw(self, layout: bpy.types.UILayout):
        layout = layout.box().column()
        layout.prop(self, "enable")
        if self.enable:
            alignToggles = layout.row(align=True)
            alignToggles.label(text="Aligned")
            alignToggles.prop(self, "alignPlayer", toggle=1)
            alignToggles.prop(self, "alignEnemy", toggle=1)
            alignToggles.prop(self, "alignOther", toggle=1)
            alignToggles.prop(self, "alignSelf", toggle=1)

    # Note that z_boss_sst_colchk has case where _ON is not set, but other flags are still set.
    def to_c(self):
        flagList = []
        flagList.append("AT_ON") if self.enable else None
        if self.alignPlayer and self.alignEnemy and self.alignOther:
            flagList.append("AT_TYPE_ALL")
        else:
            flagList.append("AT_TYPE_PLAYER") if self.alignPlayer else None
            flagList.append("AT_TYPE_ENEMY") if self.alignEnemy else None
            flagList.append("AT_TYPE_OTHER") if self.alignOther else None
        flagList.append("AT_TYPE_SELF") if self.alignSelf else None

        flagList = ["AT_NONE"] if len(flagList) == 0 else flagList

        return " | ".join(flagList)


# AC
class OOTColliderHurtboxProperty(bpy.types.PropertyGroup):
    enable: bpy.props.BoolProperty(name="Hurtbox (AC)", update=updateCollider, default=True)
    attacksBounceOff: bpy.props.BoolProperty(name="Attacks Bounce Off")
    hurtByPlayer: bpy.props.BoolProperty(name="Player", default=True)
    hurtByEnemy: bpy.props.BoolProperty(name="Enemy", default=False)
    hurtByOther: bpy.props.BoolProperty(name="Other", default=False)
    noDamage: bpy.props.BoolProperty(name="Doesn't Take Damage", default=False)

    def draw(self, layout: bpy.types.UILayout):
        layout = layout.box().column()
        layout.prop(self, "enable")
        if self.enable:
            layout.prop(self, "attacksBounceOff")
            layout.prop(self, "noDamage")
            hurtToggles = layout.row(align=True)
            hurtToggles.label(text="Hurt By")
            hurtToggles.prop(self, "hurtByPlayer", toggle=1)
            hurtToggles.prop(self, "hurtByEnemy", toggle=1)
            hurtToggles.prop(self, "hurtByOther", toggle=1)

    # Note that z_boss_sst_colchk has case where _ON is not set, but other flags are still set.
    def to_c(self):
        flagList = []
        flagList.append("AC_ON") if self.enable else None
        flagList.append("AC_HARD") if self.attacksBounceOff else None
        if self.hurtByPlayer and self.hurtByEnemy and self.hurtByOther:
            flagList.append("AC_TYPE_ALL")
        else:
            flagList.append("AC_TYPE_PLAYER") if self.hurtByPlayer else None
            flagList.append("AC_TYPE_ENEMY") if self.hurtByEnemy else None
            flagList.append("AC_TYPE_OTHER") if self.hurtByOther else None
        flagList.append("AC_NO_DAMAGE") if self.noDamage else None

        flagList = ["AC_NONE"] if len(flagList) == 0 else flagList

        return " | ".join(flagList)


class OOTColliderLayers(bpy.types.PropertyGroup):
    player: bpy.props.BoolProperty(name="Player", default=False)
    type1: bpy.props.BoolProperty(name="Type 1", default=True)
    type2: bpy.props.BoolProperty(name="Type 2", default=False)

    def draw(self, layout: bpy.types.UILayout, name: str):
        collisionLayers = layout.row(align=True)
        collisionLayers.label(text=name)
        collisionLayers.prop(self, "player", toggle=1)
        collisionLayers.prop(self, "type1", toggle=1)
        collisionLayers.prop(self, "type2", toggle=1)


# OC
class OOTColliderPhysicsProperty(bpy.types.PropertyGroup):
    enable: bpy.props.BoolProperty(name="Physics (OC)", update=updateCollider, default=True)
    noPush: bpy.props.BoolProperty(name="Don't Push Others")
    collidesWith: bpy.props.PointerProperty(type=OOTColliderLayers)
    isCollider: bpy.props.PointerProperty(type=OOTColliderLayers)
    skipHurtboxCheck: bpy.props.BoolProperty(name="Skip Hurtbox Check After First Collision")
    isType1: bpy.props.BoolProperty(name="Is Type 1", default=False)
    unk1: bpy.props.BoolProperty(name="Unknown 1", default=False)
    unk2: bpy.props.BoolProperty(name="Unknown 2", default=False)

    def draw(self, layout: bpy.types.UILayout):
        layout = layout.box().column()
        layout.prop(self, "enable")
        if self.enable:
            layout.prop(self, "noPush")
            layout.prop(self, "skipHurtboxCheck")
            layout.prop(self, "isType1")
            self.collidesWith.draw(layout, "Hits Type")
            if not self.isType1:
                self.isCollider.draw(layout, "Is Type")
            row = layout.row(align=True)
            row.prop(self, "unk1")
            row.prop(self, "unk2")

    # Note that z_boss_sst_colchk has case where _ON is not set, but other flags are still set.
    def to_c_1(self):
        flagList = []
        flagList.append("OC1_ON") if self.enable else None
        flagList.append("OC1_NO_PUSH") if self.noPush else None
        if self.collidesWith.player and self.collidesWith.type1 and self.collidesWith.type2:
            flagList.append("OC1_TYPE_ALL")
        else:
            flagList.append("OC1_TYPE_PLAYER") if self.collidesWith.player else None
            flagList.append("OC1_TYPE_1") if self.collidesWith.type1 else None
            flagList.append("OC1_TYPE_2") if self.collidesWith.type2 else None

        flagList = ["OC1_NONE"] if len(flagList) == 0 else flagList

        return " | ".join(flagList)

    # Note that z_boss_sst_colchk has case where _ON is not set, but other flags are still set.
    def to_c_2(self):
        flagList = []
        flagList.append("OC2_UNK1") if self.unk1 else None
        flagList.append("OC2_UNK2") if self.unk2 else None

        flagList.append("OC2_TYPE_PLAYER") if self.isCollider.player else None
        flagList.append("OC2_TYPE_1") if self.isCollider.type1 else None
        flagList.append("OC2_TYPE_2") if self.isCollider.type2 else None

        flagList.append("OC2_FIRST_ONLY") if self.skipHurtboxCheck else None

        flagList = ["OC2_NONE"] if len(flagList) == 0 else flagList

        return " | ".join(flagList)


# Touch
class OOTColliderHitboxItemProperty(bpy.types.PropertyGroup):
    # Flags
    enable: bpy.props.BoolProperty(name="Touch")
    soundEffect: bpy.props.EnumProperty(name="Sound Effect", items=ootEnumHitboxSound)
    drawHitmarksForEveryCollision: bpy.props.BoolProperty(name="Draw Hitmarks For Every Collision")
    closestBumper: bpy.props.BoolProperty(name="Only Collide With Closest Bumper (Quads)")

    # ColliderTouch
    damageFlags: bpy.props.PointerProperty(type=OOTDamageFlagsProperty, name="Damage Flags")
    effect: bpy.props.IntProperty(min=0, max=255, name="Effect")
    damage: bpy.props.IntProperty(min=0, max=255, name="Damage")
    unk7: bpy.props.BoolProperty(name="Unknown 7")

    def draw(self, layout: bpy.types.UILayout):
        layout = layout.box().column()
        layout.prop(self, "enable")
        if self.enable:
            prop_split(layout, self, "soundEffect", "Sound Effect")
            layout.prop(self, "drawHitmarksForEveryCollision")
            layout.prop(self, "closestBumper")
            layout.prop(self, "unk7")
            prop_split(layout, self, "effect", "Effect")
            prop_split(layout, self, "damage", "Damage")
            self.damageFlags.draw(layout)

    # Note that z_boss_sst_colchk has case where _ON is not set, but other flags are still set.
    def to_c_flags(self):
        flagList = []
        flagList.append("TOUCH_ON") if self.enable else None
        flagList.append("TOUCH_NEAREST") if self.closestBumper else None
        flagList.append(self.soundEffect)

        flagList.append("TOUCH_AT_HITMARK") if self.drawHitmarksForEveryCollision else None
        flagList.append("TOUCH_UNK7") if self.unk7 else None

        # note that TOUCH_SFX_NORMAL is the same as 0, but since it is an enum it would usually be included anyway
        flagList = (
            ["TOUCH_NONE"]
            if len(flagList) == 0 or (len(flagList) == 1 and flagList[0] == "TOUCH_SFX_NORMAL")
            else flagList
        )

        return " | ".join(flagList)

    def to_c_damage_flags(self):
        flagList = [self.damageFlags.to_c()]
        flagList.append(format(self.effect, "#04x"))
        flagList.append(format(self.damage, "#04x"))

        return "{ " + ", ".join(flagList) + " }"


# Bump
class OOTColliderHurtboxItemProperty(bpy.types.PropertyGroup):
    # Flags
    enable: bpy.props.BoolProperty(name="Bump")
    hookable: bpy.props.BoolProperty(name="Hookable")
    giveInfoToHit: bpy.props.BoolProperty(name="Give Info To Hit")
    takesDamage: bpy.props.BoolProperty(name="Damageable", default=True)
    hasSound: bpy.props.BoolProperty(name="Has SFX", default=True)
    hasHitmark: bpy.props.BoolProperty(name="Has Hitmark", default=True)

    # ColliderBumpInit
    damageFlags: bpy.props.PointerProperty(type=OOTDamageFlagsProperty, name="Damage Flags")
    effect: bpy.props.IntProperty(min=0, max=255, name="Effect")
    defense: bpy.props.IntProperty(min=0, max=255, name="Damage")

    def draw(self, layout: bpy.types.UILayout):
        layout = layout.box().column()
        layout.prop(self, "enable")
        if self.enable:
            layout.prop(self, "hookable")
            layout.prop(self, "giveInfoToHit")
            row = layout.row(align=True)
            row.prop(self, "takesDamage", toggle=1)
            row.prop(self, "hasSound", toggle=1)
            row.prop(self, "hasHitmark", toggle=1)
            prop_split(layout, self, "effect", "Effect")
            prop_split(layout, self, "defense", "Defense")
            self.damageFlags.draw(layout)

    # Note that z_boss_sst_colchk has case where _ON is not set, but other flags are still set.
    def to_c_flags(self):
        flagList = []
        flagList.append("BUMP_ON") if self.enable else None
        flagList.append("BUMP_HOOKABLE") if self.hookable else None
        flagList.append("BUMP_NO_AT_INFO") if not self.giveInfoToHit else None
        flagList.append("BUMP_NO_DAMAGE") if not self.takesDamage else None
        flagList.append("BUMP_NO_SWORD_SFX") if not self.hasSound else None
        flagList.append("BUMP_NO_HITMARK") if not self.hasHitmark else None
        flagList.append("BUMP_DRAW_HITMARK") if self.hookable else None

        flagList = ["BUMP_NONE"] if len(flagList) == 0 else flagList

        return " | ".join(flagList)

    def to_c_damage_flags(self):
        flagList = [self.damageFlags.to_c()]
        flagList.append(format(self.effect, "#04x"))
        flagList.append(format(self.defense, "#04x"))

        return "{ " + ", ".join(flagList) + " }"


# OCElem
class OOTColliderPhysicsItemProperty(bpy.types.PropertyGroup):
    enable: bpy.props.BoolProperty(name="Object Element")
    unk3: bpy.props.BoolProperty(name="Unknown 3", default=False)

    def draw(self, layout: bpy.types.UILayout):
        layout = layout.box().column()
        layout.prop(self, "enable")
        if self.enable:
            layout.prop(self, "unk3")

    def to_c_flags(self):
        if not self.enable:
            return "OCELEM_NONE"

        flagList = ["OCELEM_ON"]
        flagList.append("OCELEM_UNK3") if self.unk3 else None

        return " | ".join(flagList)


# ColliderInit is for entire collection.
# ColliderInfoInit is for each item of a collection.

# Triangle/Cylinder will use their own object for ColliderInit.
# Joint Sphere will use armature object for ColliderInit.


class OOTActorColliderProperty(bpy.types.PropertyGroup):
    # ColliderInit
    colliderShape: bpy.props.EnumProperty(
        items=ootEnumColliderShape, name="Shape", default="COLSHAPE_CYLINDER", update=updateCollider
    )
    colliderType: bpy.props.EnumProperty(items=ootEnumColliderType, name="Hit Reaction")
    hitbox: bpy.props.PointerProperty(type=OOTColliderHitboxProperty, name="Hitbox (AT)")
    hurtbox: bpy.props.PointerProperty(type=OOTColliderHurtboxProperty, name="Hurtbox (AC)")
    physics: bpy.props.PointerProperty(type=OOTColliderPhysicsProperty, name="Physics (OC)")
    name: bpy.props.StringProperty(name="Struct Name", default="sColliderInit")

    def draw(self, obj: bpy.types.Object, layout: bpy.types.UILayout):
        if obj.ootActorCollider.colliderShape == "COLSHAPE_JNTSPH":
            if obj.parent is not None:
                collider = obj.parent.ootActorCollider
                layout.label(text="Joint Shared", icon="INFO")
                prop_split(layout, collider, "name", "Struct Name")
                prop_split(layout, collider, "colliderType", "Collider Type")
                collider.hitbox.draw(layout)
                collider.hurtbox.draw(layout)
                collider.physics.draw(layout)
            else:
                layout.label(text="Joint sphere colliders must be parented to a bone or object.", icon="ERROR")

        else:
            prop_split(layout, self, "name", "Struct Name")
            if obj.ootActorCollider.colliderShape == "COLSHAPE_QUAD":
                layout.label(text="Geometry is ignored and zeroed.", icon="INFO")
                layout.label(text="Only properties are exported.")
            prop_split(layout, self, "colliderType", "Collider Type")
            self.hitbox.draw(layout)
            self.hurtbox.draw(layout)
            self.physics.draw(layout)

    def to_c(self, tabDepth: int):
        indent = "\t" * tabDepth
        nextIndent = "\t" * (tabDepth + 1)

        physics2 = f"{nextIndent}{self.physics.to_c_2()},\n" if not self.physics.isType1 else ""

        data = (
            f"{indent}{{\n"
            f"{nextIndent}{self.colliderType},\n"
            f"{nextIndent}{self.hitbox.to_c()},\n"
            f"{nextIndent}{self.hurtbox.to_c()},\n"
            f"{nextIndent}{self.physics.to_c_1()},\n"
            f"{physics2}"
            f"{nextIndent}{self.colliderShape},\n"
            f"{indent}}},\n"
        )

        return data


class OOTActorColliderItemProperty(bpy.types.PropertyGroup):
    # ColliderInfoInit
    element: bpy.props.EnumProperty(items=ootEnumColliderElement, name="Element Type")
    limbOverride: bpy.props.IntProperty(min=0, max=256, name="Limb Index")
    touch: bpy.props.PointerProperty(type=OOTColliderHitboxItemProperty, name="Touch")
    bump: bpy.props.PointerProperty(type=OOTColliderHurtboxItemProperty, name="Bump")
    objectElem: bpy.props.PointerProperty(type=OOTColliderPhysicsItemProperty, name="Object Element")

    # obj is None when using mesh collider, where property is on material
    def draw(self, obj: bpy.types.Object | None, layout: bpy.types.UILayout):
        if obj is not None and obj.ootActorCollider.colliderShape == "COLSHAPE_JNTSPH":
            layout.label(text="Joint Specific", icon="INFO")
            if not (
                obj.parent is not None and isinstance(obj.parent.data, bpy.types.Armature) and obj.parent_bone != ""
            ):
                prop_split(layout, self, "limbOverride", "Limb Index")

        if obj is not None and obj.ootActorCollider.colliderShape == "COLSHAPE_TRIS":
            layout = layout.column()
            layout.label(text="Touch/bump defined in materials.", icon="INFO")
            layout.label(text="Materials will not be visualized.")
        else:
            layout = layout.column()
            prop_split(layout, self, "element", "Element Type")
            self.touch.draw(layout)
            self.bump.draw(layout)
            self.objectElem.draw(layout)

    def to_c(self, tabDepth: int):
        indent = "\t" * tabDepth
        nextIndent = "\t" * (tabDepth + 1)

        data = (
            f"{indent}{{\n"
            f"{nextIndent}{self.element},\n"
            f"{nextIndent}{self.touch.to_c_damage_flags()},\n"
            f"{nextIndent}{self.bump.to_c_damage_flags()},\n"
            f"{nextIndent}{self.touch.to_c_flags()},\n"
            f"{nextIndent}{self.bump.to_c_flags()},\n"
            f"{nextIndent}{self.objectElem.to_c_flags()},\n"
            f"{indent}}},\n"
        )

        return data


def drawColliderVisibilityOperators(layout: bpy.types.UILayout):
    col = layout.column()
    col.label(text="Toggle Visibility (Excluding Selected)")
    row = col.row(align=True)
    visibilitySettings = bpy.context.scene.ootColliderVisibility
    row.prop(visibilitySettings, "jointSphere", text="Joint Sphere", toggle=1)
    row.prop(visibilitySettings, "cylinder", text="Cylinder", toggle=1)
    row.prop(visibilitySettings, "mesh", text="Mesh", toggle=1)
    row.prop(visibilitySettings, "quad", text="Quad", toggle=1)


def updateVisibilityJointSphere(self, context):
    updateVisibilityCollider("COLSHAPE_JNTSPH", self.jointSphere)


def updateVisibilityCylinder(self, context):
    updateVisibilityCollider("COLSHAPE_CYLINDER", self.cylinder)


def updateVisibilityMesh(self, context):
    updateVisibilityCollider("COLSHAPE_TRIS", self.mesh)


def updateVisibilityQuad(self, context):
    updateVisibilityCollider("COLSHAPE_QUAD", self.quad)


def updateVisibilityCollider(shapeName: str, visibility: bool) -> None:
    selectedObjs = bpy.context.selected_objects
    for obj in bpy.data.objects:
        if (
            isinstance(obj.data, bpy.types.Mesh)
            and obj.ootGeometryType == "Actor Collider"
            and obj.ootActorCollider.colliderShape == shapeName
            and obj not in selectedObjs
        ):
            obj.hide_set(not visibility)


class OOTColliderVisibilitySettings(bpy.types.PropertyGroup):
    jointSphere: bpy.props.BoolProperty(name="Joint Sphere", default=True, update=updateVisibilityJointSphere)
    cylinder: bpy.props.BoolProperty(name="Cylinder", default=True, update=updateVisibilityCylinder)
    mesh: bpy.props.BoolProperty(name="Mesh", default=True, update=updateVisibilityMesh)
    quad: bpy.props.BoolProperty(name="Quad", default=True, update=updateVisibilityQuad)


actor_collider_props_classes = (
    OOTColliderLayers,
    OOTDamageFlagsProperty,
    OOTColliderHitboxItemProperty,
    OOTColliderHurtboxItemProperty,
    OOTColliderPhysicsItemProperty,
    OOTColliderHitboxProperty,
    OOTColliderHurtboxProperty,
    OOTColliderPhysicsProperty,
    OOTActorColliderProperty,
    OOTActorColliderItemProperty,
    OOTColliderVisibilitySettings,
)


def actor_collider_props_register():
    for cls in actor_collider_props_classes:
        register_class(cls)

    bpy.types.Object.ootActorCollider = bpy.props.PointerProperty(type=OOTActorColliderProperty)
    bpy.types.Object.ootActorColliderItem = bpy.props.PointerProperty(type=OOTActorColliderItemProperty)
    bpy.types.Material.ootActorColliderItem = bpy.props.PointerProperty(type=OOTActorColliderItemProperty)
    bpy.types.Scene.ootColliderLibVer = bpy.props.IntProperty(default=1)
    bpy.types.Scene.ootColliderVisibility = bpy.props.PointerProperty(type=OOTColliderVisibilitySettings)


def actor_collider_props_unregister():
    for cls in reversed(actor_collider_props_classes):
        unregister_class(cls)

    del bpy.types.Object.ootActorCollider
    del bpy.types.Object.ootActorColliderItem
    del bpy.types.Scene.ootColliderLibVer
    del bpy.types.Scene.ootColliderVisibility

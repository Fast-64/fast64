from typing import Callable
import bpy, mathutils, os, re, math
from ...utility import PluginError, hexOrDecInt
from ..oot_model_classes import ootGetActorData, ootGetIncludedAssetData, ootGetActorDataPaths, ootGetLinkData
from .properties import (
    OOTActorColliderItemProperty,
    OOTActorColliderProperty,
    OOTColliderHitboxItemProperty,
    OOTColliderHitboxProperty,
    OOTColliderHurtboxItemProperty,
    OOTColliderHurtboxProperty,
    OOTColliderPhysicsItemProperty,
    OOTColliderPhysicsProperty,
    OOTDamageFlagsProperty,
    OOTActorColliderImportExportSettings,
)
from ..oot_utility import getOrderedBoneList, getOOTScale
from .utility import addColliderThenParent, ootEnumColliderType, ootEnumColliderElement, ootEnumHitboxSound


# has 1 capture group
def flagRegex(commaTerminating: bool = True) -> str:
    return r"\s*([0-9a-zA-Z\_\s\|]*)\s*" + ("," if commaTerminating else ",?")


# has {count} capture groups
def flagListRegex(count: int) -> str:
    regex = ""
    if count < 1:
        return ""
    for i in range(count - 1):
        regex += flagRegex()
    regex += flagRegex(False)
    return regex


# has 3 capture groups
def touchBumpRegex() -> str:
    return r"\{\s*" + flagListRegex(3) + r"\s*\}\s*,"


# has 7 capture groups
def colliderInitRegex() -> str:
    return r"\{\s*" + flagListRegex(5) + "(" + flagRegex() + ")?" + r"\s*\}\s*,"


# has 10 capture groups
def colliderInfoInitRegex() -> str:
    return r"\{\s*" + flagRegex() + touchBumpRegex() + touchBumpRegex() + flagListRegex(3) + r"\s*\}\s*,"


# assumes enums are in numerical order.
def getEnumValue(value: str, enumTuples: list[tuple[str, str, str]]) -> str:
    enumList = [i[0] for i in enumTuples]

    if value in enumList:
        return value
    else:
        try:
            parsedValue = hexOrDecInt(value)
            if parsedValue < len(enumList):
                return parsedValue
            else:
                raise PluginError(f"Out of bounds index: {value}")
        except ValueError:
            raise PluginError(f"Invalid value: {value}")


def parseATFlags(flagData: str, atProp: OOTColliderHitboxProperty):
    flags = [flag.strip() for flag in flagData.split("|")]
    atProp.enable = "AT_ON" in flags
    atProp.alignPlayer = "AT_TYPE_PLAYER" in flags or "AT_TYPE_ALL" in flags
    atProp.alignEnemy = "AT_TYPE_ENEMY" in flags or "AT_TYPE_ALL" in flags
    atProp.alignOther = "AT_TYPE_OTHER" in flags or "AT_TYPE_ALL" in flags
    atProp.alignSelf = "AT_TYPE_SELF" in flags


def parseACFlags(flagData: str, acProp: OOTColliderHurtboxProperty):
    flags = [flag.strip() for flag in flagData.split("|")]
    acProp.enable = "AC_ON" in flags
    acProp.attacksBounceOff = "AC_HARD" in flags
    acProp.hurtByPlayer = "AC_TYPE_PLAYER" in flags or "AC_TYPE_ALL" in flags
    acProp.hurtByEnemy = "AC_TYPE_ENEMY" in flags or "AC_TYPE_ALL" in flags
    acProp.hurtByOther = "AC_TYPE_OTHER" in flags or "AC_TYPE_ALL" in flags
    acProp.noDamage = "AC_NO_DAMAGE" in flags


def parseOCFlags(oc1Data: str, oc2Data: str | None, ocProp: OOTColliderPhysicsProperty):
    flags1 = [flag.strip() for flag in oc1Data.split("|")]
    ocProp.enable = "OC1_ON" in flags1
    ocProp.noPush = "OC1_NO_PUSH" in flags1
    ocProp.collidesWith.player = "OC1_TYPE_PLAYER" in flags1 or "OC1_TYPE_ALL" in flags1
    ocProp.collidesWith.type1 = "OC1_TYPE_1" in flags1 or "OC1_TYPE_ALL" in flags1
    ocProp.collidesWith.type2 = "OC1_TYPE_2" in flags1 or "OC1_TYPE_ALL" in flags1

    if oc2Data is not None:
        flags2 = [flag.strip() for flag in oc2Data.split("|")]
        ocProp.isCollider.player = "OC2_TYPE_PLAYER" in flags2
        ocProp.isCollider.type1 = "OC2_TYPE_1" in flags2
        ocProp.isCollider.type2 = "OC2_TYPE_2" in flags2
        ocProp.skipHurtboxCheck = "OC2_FIRST_ONLY" in flags2
        ocProp.unk1 = "OC2_UNK1" in flags2
        ocProp.unk2 = "OC2_UNK2" in flags2


def parseColliderInit(dataList: list[str], colliderProp: OOTActorColliderProperty):
    colliderProp.colliderType = getEnumValue(dataList[0].strip(), ootEnumColliderType)
    parseATFlags(dataList[1], colliderProp.hitbox)
    parseACFlags(dataList[2], colliderProp.hurtbox)
    parseOCFlags(dataList[3], dataList[4], colliderProp.physics)


def parseDamageFlags(flags: int, flagProp: OOTDamageFlagsProperty):
    flagProp.dekuNut = flags & (1 << 0) != 0
    flagProp.dekuStick = flags & (1 << 1) != 0
    flagProp.slingshot = flags & (1 << 2) != 0
    flagProp.explosive = flags & (1 << 3) != 0
    flagProp.boomerang = flags & (1 << 4) != 0
    flagProp.arrowNormal = flags & (1 << 5) != 0
    flagProp.hammerSwing = flags & (1 << 6) != 0
    flagProp.hookshot = flags & (1 << 7) != 0
    flagProp.slashKokiriSword = flags & (1 << 8) != 0
    flagProp.slashMasterSword = flags & (1 << 9) != 0
    flagProp.slashGiantSword = flags & (1 << 10) != 0
    flagProp.arrowFire = flags & (1 << 11) != 0
    flagProp.arrowIce = flags & (1 << 12) != 0
    flagProp.arrowLight = flags & (1 << 13) != 0
    flagProp.arrowUnk1 = flags & (1 << 14) != 0
    flagProp.arrowUnk2 = flags & (1 << 15) != 0
    flagProp.arrowUnk3 = flags & (1 << 16) != 0
    flagProp.magicFire = flags & (1 << 17) != 0
    flagProp.magicIce = flags & (1 << 18) != 0
    flagProp.magicLight = flags & (1 << 19) != 0
    flagProp.shield = flags & (1 << 20) != 0
    flagProp.mirrorRay = flags & (1 << 21) != 0
    flagProp.spinKokiriSword = flags & (1 << 22) != 0
    flagProp.spinGiantSword = flags & (1 << 23) != 0
    flagProp.spinMasterSword = flags & (1 << 24) != 0
    flagProp.jumpKokiriSword = flags & (1 << 25) != 0
    flagProp.jumpGiantSword = flags & (1 << 26) != 0
    flagProp.jumpMasterSword = flags & (1 << 27) != 0
    flagProp.unknown1 = flags & (1 << 28) != 0
    flagProp.unblockable = flags & (1 << 29) != 0
    flagProp.hammerJump = flags & (1 << 30) != 0
    flagProp.unknown2 = flags & (1 << 31) != 0


def parseTouch(dataList: list[str], touch: OOTColliderHitboxItemProperty, startIndex: int):
    dmgFlags = int(dataList[startIndex + 1].strip(), 16)
    parseDamageFlags(dmgFlags, touch.damageFlags)
    touch.effect = hexOrDecInt(dataList[startIndex + 2])
    touch.damage = hexOrDecInt(dataList[startIndex + 3])

    flags = [flag.strip() for flag in dataList[startIndex + 7].split("|")]
    touch.enable = "TOUCH_ON" in flags

    for flag in flags:
        if flag in [i[0] for i in ootEnumHitboxSound]:
            touch.soundEffect = flag

    touch.drawHitmarksForEveryCollision = "TOUCH_AT_HITMARK" in flags
    touch.closestBumper = "TOUCH_NEAREST" in flags
    touch.unk7 = "TOUCH_UNK7" in flags


def parseBump(dataList: list[str], bump: OOTColliderHurtboxItemProperty, startIndex: int):
    dmgFlags = int(dataList[startIndex + 4].strip(), 16)
    parseDamageFlags(dmgFlags, bump.damageFlags)
    bump.effect = hexOrDecInt(dataList[startIndex + 5])
    bump.defense = hexOrDecInt(dataList[startIndex + 6])

    flags = [flag.strip() for flag in dataList[startIndex + 8].split("|")]
    bump.enable = "BUMP_ON" in flags
    bump.hookable = "BUMP_HOOKABLE" in flags
    bump.giveInfoToHit = "BUMP_NO_AT_INFO" not in flags
    bump.takesDamage = "BUMP_NO_DAMAGE" not in flags
    bump.hasSound = "BUMP_NO_SWORD_SFX" not in flags
    bump.hasHitmark = "BUMP_NO_HITMARK" not in flags


def parseObjectElement(dataList: list[str], objectElem: OOTColliderPhysicsItemProperty, startIndex: int):
    flags = [flag.strip() for flag in dataList[startIndex + 9].split("|")]
    objectElem.enable = "OCELEM_ON" in flags
    objectElem.unk3 = "OCELEM_UNK3" in flags


def parseColliderInfoInit(dataList: list[str], colliderItemProp: OOTActorColliderItemProperty, startIndex: int):
    colliderItemProp.element = getEnumValue(dataList[startIndex], ootEnumColliderElement)
    parseTouch(dataList, colliderItemProp.touch, startIndex)
    parseBump(dataList, colliderItemProp.bump, startIndex)
    parseObjectElement(dataList, colliderItemProp.objectElem, startIndex)


def parseColliderData(
    geometryName: str,
    basePath: str,
    overlayName: str,
    isLink: bool,
    parentObj: bpy.types.Object,
    colliderSettings: OOTActorColliderImportExportSettings,
):
    if not isLink:
        actorData = ootGetActorData(basePath, overlayName)
        currentPaths = ootGetActorDataPaths(basePath, overlayName)
    else:
        actorData = ootGetLinkData(basePath)
        currentPaths = [os.path.join(basePath, f"src/code/z_player_lib.c")]
    actorData = ootGetIncludedAssetData(basePath, currentPaths, actorData) + actorData

    if colliderSettings.chooseSpecific:
        filterNameFunc = lambda geometryName, name: name in [
            value.strip() for value in colliderSettings.specificColliders.split(",") if value.strip() != ""
        ]

    else:
        filterNameFunc = noFilter
        if overlayName == "ovl_Boss_Sst":
            filterNameFunc = filterForSst
        elif overlayName == "ovl_Boss_Va":
            filterNameFunc = filterForVa

    if colliderSettings.cylinder:
        parseCylinderColliders(actorData, parentObj, geometryName, filterNameFunc)

    if colliderSettings.jointSphere:
        parseJointSphereColliders(
            actorData, parentObj, geometryName, filterNameFunc, colliderSettings.parentJointSpheresToBone
        )

    if colliderSettings.mesh:
        parseMeshColliders(actorData, parentObj, geometryName, filterNameFunc)

    if colliderSettings.quad:
        parseQuadColliders(actorData, parentObj, geometryName, filterNameFunc)


def noFilter(name: str, colliderName: str):
    return True


def filterForSst(geometryName: str, colliderName: str):
    if "Hand" in geometryName:
        return "Hand" in colliderName
    elif "Head" in geometryName:
        return "Head" in colliderName
    else:
        return False


def filterForVa(geometryName: str, colliderName: str):
    if "BodySkel" in geometryName:
        return colliderName == "sCylinderInit"
    elif "SupportSkel" in geometryName:
        return colliderName == "sJntSphInitSupport"
    elif "ZapperSkel" in geometryName:
        return colliderName == "sQuadInit"
    elif "StumpSkel" in geometryName:
        return False
    elif "BariSkel" in geometryName:
        return colliderName == "sJntSphInitBari" or colliderName == "sQuadInit"
    else:
        return False


def parseCylinderColliders(
    data: str, parentObj: bpy.types.Object, geometryName: str | None, filterNameFunc: Callable[[str, str], bool]
):
    handledColliders = []
    for match in re.finditer(
        r"ColliderCylinderInit(Type1)?\s*([0-9a-zA-Z\_]*)\s*=\s*\{(.*?)\}\s*;",
        data,
        flags=re.DOTALL,
    ):

        name = match.group(2)
        colliderData = match.group(3)

        if not filterNameFunc(geometryName, name):
            continue

        # This happens because our file including is not ideal and doesn't check for duplicate includes
        if name in handledColliders:
            continue
        handledColliders.append(name)

        dataList = [
            item.strip() for item in colliderData.replace("{", "").replace("}", "").split(",") if item.strip() != ""
        ]
        if len(dataList) < 16 + 6:
            raise PluginError(f"Collider {name} has unexpected struct format.")

        obj = addColliderThenParent("COLSHAPE_CYLINDER", parentObj, None)
        parseColliderInit(dataList, obj.ootActorCollider)
        parseColliderInfoInit(dataList, obj.ootActorColliderItem, 6)

        obj.name = f"Collider {name}"
        obj.ootActorCollider.name = name

        radius = hexOrDecInt(dataList[16]) / bpy.context.scene.ootBlenderScale
        height = hexOrDecInt(dataList[17]) / bpy.context.scene.ootBlenderScale
        yShift = hexOrDecInt(dataList[18]) / bpy.context.scene.ootBlenderScale
        position = [hexOrDecInt(value) / bpy.context.scene.ootBlenderScale for value in dataList[19:22]]

        yUpToZUp = mathutils.Quaternion((1, 0, 0), math.radians(90.0))
        location = mathutils.Vector((0, yShift, 0)) + mathutils.Vector(position)
        obj.matrix_local = mathutils.Matrix.Diagonal(
            mathutils.Vector((radius, radius, height / 2, 1))
        ) @ mathutils.Matrix.Translation(yUpToZUp @ location)


def parseJointSphereColliders(
    data: str,
    parentObj: bpy.types.Object,
    geometryName: str | None,
    filterNameFunc: Callable[[str, str], bool],
    parentToBones: bool,
):
    handledColliders = []
    for match in re.finditer(
        r"ColliderJntSphInit\s*([0-9a-zA-Z\_]*)\s*=\s*\{(.*?)\}\s*;",
        data,
        flags=re.DOTALL,
    ):
        name = match.group(1)
        colliderData = match.group(2)

        if not filterNameFunc(geometryName, name):
            continue

        # This happens because our file including is not ideal and doesn't check for duplicate includes
        if name in handledColliders:
            continue
        handledColliders.append(name)

        dataList = [
            item.strip() for item in colliderData.replace("{", "").replace("}", "").split(",") if item.strip() != ""
        ]
        if len(dataList) < 2 + 6:
            raise PluginError(f"Collider {name} has unexpected struct format.")

        itemsName = dataList[7]

        parentObj.ootActorCollider.name = name

        parseColliderInit(dataList, parentObj.ootActorCollider)
        parseJointSphereCollidersItems(data, parentObj, itemsName, name, parentToBones)


def parseJointSphereCollidersItems(
    data: str, parentObj: bpy.types.Object, itemsName: str, name: str, parentToBones: bool
):
    match = re.search(
        r"ColliderJntSphElementInit\s*" + re.escape(itemsName) + r"\s*\[\s*[0-9A-Fa-fx]*\s*\]\s*=\s*\{(.*?)\}\s*;",
        data,
        flags=re.DOTALL,
    )

    if match is None:
        raise PluginError(f"Could not find {itemsName}.")

    matchData = match.group(1)

    dataList = [item.strip() for item in matchData.replace("{", "").replace("}", "").split(",") if item.strip() != ""]
    if len(dataList) % 16 != 0:
        raise PluginError(f"{itemsName} has unexpected struct format.")

    willParentToBones = isinstance(parentObj.data, bpy.types.Armature) and parentToBones

    if willParentToBones:
        boneList = getOrderedBoneList(parentObj)
    else:
        boneList = None

    count = int(round(len(dataList) / 16))
    for item in [dataList[16 * i : 16 * (i + 1)] for i in range(count)]:

        # Why subtract 1???
        # in SkelAnime_InitFlex: skelAnime->limbCount = skeletonHeader->sh.limbCount + 1;
        # possibly?
        # Note: works with king dodongo, not with ganon2
        # Note: king dodongo count = numElements - 1
        limb = hexOrDecInt(item[10]) - 1

        location = mathutils.Vector(
            [hexOrDecInt(value) / ((getOOTScale(parentObj.ootActorScale))) for value in item[11:14]]
        )
        radius = hexOrDecInt(item[14]) / bpy.context.scene.ootBlenderScale
        scale = hexOrDecInt(item[15]) / 100  # code defined constant

        obj = addColliderThenParent("COLSHAPE_JNTSPH", parentObj, boneList[limb] if willParentToBones else None)
        parseColliderInfoInit(item, obj.ootActorColliderItem, 0)

        yUpToZUp = mathutils.Quaternion((1, 0, 0), math.radians(90.0))

        if willParentToBones:
            obj.matrix_world = (
                parentObj.matrix_world
                @ parentObj.pose.bones[boneList[limb].name].matrix
                @ mathutils.Matrix.Translation(location)
            )
        else:
            obj.matrix_local = mathutils.Matrix.Translation(yUpToZUp @ location)
            obj.ootActorColliderItem.limbOverride = hexOrDecInt(item[10])

        obj.scale.x = radius * scale
        obj.scale.y = radius * scale
        obj.scale.z = radius * scale


def parseMeshColliders(
    data: str, parentObj: bpy.types.Object, geometryName: str | None, filterNameFunc: Callable[[str, str], bool]
):
    handledColliders = []
    for match in re.finditer(
        r"ColliderTrisInit(Type1)?\s*([0-9a-zA-Z\_]*)\s*=\s*\{(.*?)\}\s*;",
        data,
        flags=re.DOTALL,
    ):
        name = match.group(2)
        colliderData = match.group(3)

        if not filterNameFunc(geometryName, name):
            continue

        # This happens because our file including is not ideal and doesn't check for duplicate includes
        if name in handledColliders:
            continue
        handledColliders.append(name)

        dataList = [
            item.strip() for item in colliderData.replace("{", "").replace("}", "").split(",") if item.strip() != ""
        ]
        if len(dataList) < 2 + 6:
            raise PluginError(f"Collider {name} has unexpected struct format.")

        itemsName = dataList[7]

        obj = addColliderThenParent("COLSHAPE_TRIS", parentObj, None)
        obj.name = f"Collider {name}"
        obj.ootActorCollider.name = name
        parseColliderInit(dataList, obj.ootActorCollider)
        parseMeshCollidersItems(data, obj, itemsName, name)


def parseMeshCollidersItems(data: str, obj: bpy.types.Object, itemsName: str, name: str):
    match = re.search(
        r"ColliderTrisElementInit\s*" + re.escape(itemsName) + r"\s*\[\s*[0-9A-Fa-fx]*\s*\]\s*=\s*\{(.*?)\}\s*;",
        data,
        flags=re.DOTALL,
    )

    if match is None:
        raise PluginError(f"Could not find {itemsName}.")

    matchData = match.group(1)

    dataList = [item.strip() for item in matchData.replace("{", "").replace("}", "").split(",") if item.strip() != ""]
    if len(dataList) % 19 != 0:
        raise PluginError(f"{itemsName} has unexpected struct format.")

    yUpToZUp = mathutils.Quaternion((1, 0, 0), math.radians(90.0))
    materialDict = {}  # collider item hash : material index
    vertList = []
    materialIndexList = []
    count = int(round(len(dataList) / 19))
    for item in [dataList[19 * i : 19 * (i + 1)] for i in range(count)]:
        colliderHash = tuple(item[:10])
        if colliderHash not in materialDict:
            material = bpy.data.materials.new(f"{name} Collider Material")
            obj.data.materials.append(material)
            materialDict[colliderHash] = material
            parseColliderInfoInit(item, material.ootActorColliderItem, 0)
        else:
            material = materialDict[colliderHash]

        verts = [
            [
                float(value[:-1] if value[-1] == "f" else value) / bpy.context.scene.ootBlenderScale
                for value in item[3 * i + 10 : 3 * i + 13]
            ]
            for i in range(3)
        ]
        for i in range(3):
            transformedVert = yUpToZUp @ mathutils.Vector(verts[i])
            vertList.append(transformedVert[:])
        materialIndexList.append(obj.data.materials[:].index(material))

    triangleCount = int(len(vertList) / 3)
    faces = [[3 * i + j for j in range(3)] for i in range(triangleCount)]
    obj.data.from_pydata(vertices=vertList, edges=[], faces=faces)
    for i in range(triangleCount):
        obj.data.polygons[i].material_index = materialIndexList[i]


def parseQuadColliders(
    data: str, parentObj: bpy.types.Object, geometryName: str | None, filterNameFunc: Callable[[str, str], bool]
):
    handledColliders = []
    for match in re.finditer(
        r"ColliderQuadInit(Type1)?\s*([0-9a-zA-Z\_]*)\s*=\s*\{(.*?)\}\s*;",
        data,
        flags=re.DOTALL,
    ):
        name = match.group(2)
        colliderData = match.group(3)

        if not filterNameFunc(geometryName, name):
            continue

        # This happens because our file including is not ideal and doesn't check for duplicate includes
        if name in handledColliders:
            continue
        handledColliders.append(name)

        dataList = [
            item.strip() for item in colliderData.replace("{", "").replace("}", "").split(",") if item.strip() != ""
        ]
        if len(dataList) < 16 + 6:
            raise PluginError(f"Collider {name} has unexpected struct format.")

        obj = addColliderThenParent("COLSHAPE_QUAD", parentObj, None)
        parseColliderInit(dataList, obj.ootActorCollider)
        parseColliderInfoInit(dataList, obj.ootActorColliderItem, 6)

        obj.name = f"Collider {name}"
        obj.ootActorCollider.name = name

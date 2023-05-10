import math
from ..utility import PluginError
from .oot_utility import BoxEmpty, convertIntTo2sComplement, getCustomProperty

ootEnumConveyer = [
    ("None", "None", "None"),
    ("Land", "Land", "Land"),
    ("Water", "Water", "Water"),
]

ootEnumFloorSetting = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "Default", "Default"),
    ("0x05", "Void (Small)", "Void (Small)"),
    ("0x06", "Grab Wall", "Grab Wall"),
    ("0x08", "Stop Air Momentum", "Stop Air Momentum"),
    ("0x09", "Fall Instead Of Jumping", "Fall Instead Of Jumping"),
    ("0x0B", "Dive", "Dive"),
    ("0x0C", "Void (Large)", "Void (Large)"),
]

ootEnumWallSetting = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "None", "None"),
    ("0x01", "No Ledge Grab", "No Ledge Grab"),
    ("0x02", "Ladder", "Ladder"),
    ("0x03", "Ladder Top", "Ladder Top"),
    ("0x04", "Vines", "Vines"),
    ("0x05", "Crawl Space", "Crawl Space"),
    ("0x06", "Crawl Space 2", "Crawl Space 2"),
    ("0x07", "Push Block", "Push Block"),
]

ootEnumFloorProperty = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "None", "None"),
    ("0x01", "Haunted Wasteland Camera", "Haunted Wasteland Camera"),
    ("0x02", "Hurt Floor (Spikes)", "Hurt Floor (Spikes)"),
    ("0x03", "Hurt Floor (Lava)", "Hurt Floor (Lava)"),
    ("0x04", "Shallow Sand", "Shallow Sand"),
    ("0x05", "Slippery", "Slippery"),
    ("0x06", "No Fall Damage", "No Fall Damage"),
    ("0x07", "Quicksand Crossing (Epona Uncrossable)", "Quicksand Crossing (Epona Uncrossable)"),
    ("0x08", "Jabu Jabu's Belly", "Jabu Jabu's Belly"),
    ("0x09", "Void", "Void"),
    ("0x0A", "Link Looks Up", "Link Looks Up"),
    ("0x0B", "Quicksand Crossing (Epona Crossable)", "Quicksand Crossing (Epona Crossable)"),
]

ootEnumCollisionTerrain = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "Walkable", "Walkable"),
    ("0x01", "Steep", "Steep"),
    ("0x02", "Walkable (Preserves Exit Flags)", "Walkable (Preserves Exit Flags)"),
    ("0x03", "Walkable (?)", "Walkable (?)"),
]

ootEnumCollisionSound = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "Dirt", "Dirt (aka Earth)"),
    ("0x01", "Sand", "Sand"),
    ("0x02", "Stone", "Stone"),
    ("0x03", "Jabu", "Jabu-Jabu flesh (aka Wet Stone)"),
    ("0x04", "Shallow Water", "Shallow Water"),
    ("0x05", "Deep Water", "Deep Water"),
    ("0x06", "Tall Grass", "Tall Grass"),
    ("0x07", "Lava", "Lava (aka Goo)"),
    ("0x08", "Grass", "Grass (aka Earth 2)"),
    ("0x09", "Bridge", "Bridge (aka Wooden Plank)"),
    ("0x0A", "Wood", "Wood (aka Packed Earth)"),
    ("0x0B", "Soft Dirt", "Soft Dirt (aka Earth 3)"),
    ("0x0C", "Ice", "Ice (aka Ceramic)"),
    ("0x0D", "Carpet", "Carpet (aka Loose Earth)"),
]

ootEnumConveyorSpeed = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "None", "None"),
    ("0x01", "Slow", "Slow"),
    ("0x02", "Medium", "Medium"),
    ("0x03", "Fast", "Fast"),
]

ootEnumCameraCrawlspaceSType = [
    ("Custom", "Custom", "Custom"),
    ("CAM_SET_CRAWLSPACE", "Crawlspace", "Crawlspace"),
]

ootEnumCameraSType = [
    ("Custom", "Custom", "Custom"),
    ("CAM_SET_NONE", "None", "None"),
    ("CAM_SET_NORMAL0", "Normal0", "Normal0"),
    ("CAM_SET_NORMAL1", "Normal1", "Normal1"),
    ("CAM_SET_DUNGEON0", "Dungeon0", "Dungeon0"),
    ("CAM_SET_DUNGEON1", "Dungeon1", "Dungeon1"),
    ("CAM_SET_NORMAL3", "Normal3", "Normal3"),
    ("CAM_SET_HORSE0", "Horse", "Horse"),
    ("CAM_SET_BOSS_GOMA", "Boss_gohma", "Boss_gohma"),
    ("CAM_SET_BOSS_DODO", "Boss_dodongo", "Boss_dodongo"),
    ("CAM_SET_BOSS_BARI", "Boss_barinade", "Boss_barinade"),
    ("CAM_SET_BOSS_FGANON", "Boss_phantom_ganon", "Boss_phantom_ganon"),
    ("CAM_SET_BOSS_BAL", "Boss_volvagia", "Boss_volvagia"),
    ("CAM_SET_BOSS_SHADES", "Boss_bongo", "Boss_bongo"),
    ("CAM_SET_BOSS_MOFA", "Boss_morpha", "Boss_morpha"),
    ("CAM_SET_TWIN0", "Twinrova_platform", "Twinrova_platform"),
    ("CAM_SET_TWIN1", "Twinrova_floor", "Twinrova_floor"),
    ("CAM_SET_BOSS_GANON1", "Boss_ganondorf", "Boss_ganondorf"),
    ("CAM_SET_BOSS_GANON2", "Boss_ganon", "Boss_ganon"),
    ("CAM_SET_TOWER0", "Tower_climb", "Tower_climb"),
    ("CAM_SET_TOWER1", "Tower_unused", "Tower_unused"),
    ("CAM_SET_FIXED0", "Market_balcony", "Market_balcony"),
    ("CAM_SET_FIXED1", "Chu_bowling", "Chu_bowling"),
    ("CAM_SET_CIRCLE0", "Pivot_crawlspace", "Pivot_crawlspace"),
    ("CAM_SET_CIRCLE2", "Pivot_shop_browsing", "Pivot_shop_browsing"),
    ("CAM_SET_CIRCLE3", "Pivot_in_front", "Pivot_in_front"),
    ("CAM_SET_PREREND0", "Prerend_fixed", "Prerend_fixed"),
    ("CAM_SET_PREREND1", "Prerend_pivot", "Prerend_pivot"),
    ("CAM_SET_PREREND3", "Prerend_side_scroll", "Prerend_side_scroll"),
    ("CAM_SET_DOOR0", "Door0", "Door0"),
    ("CAM_SET_DOORC", "Doorc", "Doorc"),
    ("CAM_SET_RAIL3", "Crawlspace", "Crawlspace"),
    ("CAM_SET_START0", "Start0", "Start0"),
    ("CAM_SET_START1", "Start1", "Start1"),
    ("CAM_SET_FREE0", "Free0", "Free0"),
    ("CAM_SET_FREE2", "Free2", "Free2"),
    ("CAM_SET_CIRCLE4", "Pivot_corner", "Pivot_corner"),
    ("CAM_SET_CIRCLE5", "Pivot_water_surface", "Pivot_water_surface"),
    ("CAM_SET_DEMO0", "Cs_0", "Cs_0"),
    ("CAM_SET_DEMO1", "Twisted_Hallway", "Twisted_Hallway"),
    ("CAM_SET_MORI1", "Forest_birds_eye", "Forest_birds_eye"),
    ("CAM_SET_ITEM0", "Slow_chest_cs", "Slow_chest_cs"),
    ("CAM_SET_ITEM1", "Item_unused", "Item_unused"),
    ("CAM_SET_DEMO3", "Cs_3", "Cs_3"),
    ("CAM_SET_DEMO4", "Cs_attention", "Cs_attention"),
    ("CAM_SET_UFOBEAN", "Bean_generic", "Bean_generic"),
    ("CAM_SET_LIFTBEAN", "Bean_lost_woods", "Bean_lost_woods"),
    ("CAM_SET_SCENE0", "Scene_unused", "Scene_unused"),
    ("CAM_SET_SCENE1", "Scene_transition", "Scene_transition"),
    ("CAM_SET_HIDAN1", "Fire_platform", "Fire_platform"),
    ("CAM_SET_HIDAN2", "Fire_staircase", "Fire_staircase"),
    ("CAM_SET_MORI2", "Forest_unused", "Forest_unused"),
    ("CAM_SET_MORI3", "Defeat_poe", "Defeat_poe"),
    ("CAM_SET_TAKO", "Big_octo", "Big_octo"),
    ("CAM_SET_SPOT05A", "Meadow_birds_eye", "Meadow_birds_eye"),
    ("CAM_SET_SPOT05B", "Meadow_unused", "Meadow_unused"),
    ("CAM_SET_HIDAN3", "Fire_birds_eye", "Fire_birds_eye"),
    ("CAM_SET_ITEM2", "Turn_around", "Turn_around"),
    ("CAM_SET_CIRCLE6", "Pivot_vertical", "Pivot_vertical"),
    ("CAM_SET_NORMAL2", "Normal2", "Normal2"),
    ("CAM_SET_FISHING", "Fishing", "Fishing"),
    ("CAM_SET_DEMOC", "Cs_c", "Cs_c"),
    ("CAM_SET_UO_FIBER", "Jabu_tentacle", "Jabu_tentacle"),
    ("CAM_SET_DUNGEON2", "Dungeon2", "Dungeon2"),
    ("CAM_SET_TEPPEN", "Directed_yaw", "Directed_yaw"),
    ("CAM_SET_CIRCLE7", "Pivot_from_side", "Pivot_from_side"),
    ("CAM_SET_NORMAL4", "Normal4", "Normal4"),
]

decomp_compat_map_CameraSType = {
    "CAM_SET_HORSE0": "CAM_SET_HORSE",
    "CAM_SET_BOSS_GOMA": "CAM_SET_BOSS_GOHMA",
    "CAM_SET_BOSS_DODO": "CAM_SET_BOSS_DODONGO",
    "CAM_SET_BOSS_BARI": "CAM_SET_BOSS_BARINADE",
    "CAM_SET_BOSS_FGANON": "CAM_SET_BOSS_PHANTOM_GANON",
    "CAM_SET_BOSS_BAL": "CAM_SET_BOSS_VOLVAGIA",
    "CAM_SET_BOSS_SHADES": "CAM_SET_BOSS_BONGO",
    "CAM_SET_BOSS_MOFA": "CAM_SET_BOSS_MORPHA",
    "CAM_SET_TWIN0": "CAM_SET_BOSS_TWINROVA_PLATFORM",
    "CAM_SET_TWIN1": "CAM_SET_BOSS_TWINROVA_FLOOR",
    "CAM_SET_BOSS_GANON1": "CAM_SET_BOSS_GANONDORF",
    "CAM_SET_BOSS_GANON2": "CAM_SET_BOSS_GANON",
    "CAM_SET_TOWER0": "CAM_SET_TOWER_CLIMB",
    "CAM_SET_TOWER1": "CAM_SET_TOWER_UNUSED",
    "CAM_SET_FIXED0": "CAM_SET_MARKET_BALCONY",
    "CAM_SET_FIXED1": "CAM_SET_CHU_BOWLING",
    "CAM_SET_CIRCLE0": "CAM_SET_PIVOT_CRAWLSPACE",
    "CAM_SET_CIRCLE2": "CAM_SET_PIVOT_SHOP_BROWSING",
    "CAM_SET_CIRCLE3": "CAM_SET_PIVOT_IN_FRONT",
    "CAM_SET_PREREND0": "CAM_SET_PREREND_FIXED",
    "CAM_SET_PREREND1": "CAM_SET_PREREND_PIVOT",
    "CAM_SET_PREREND3": "CAM_SET_PREREND_SIDE_SCROLL",
    "CAM_SET_RAIL3": "CAM_SET_CRAWLSPACE",
    "CAM_SET_CIRCLE4": "CAM_SET_PIVOT_CORNER",
    "CAM_SET_CIRCLE5": "CAM_SET_PIVOT_WATER_SURFACE",
    "CAM_SET_DEMO0": "CAM_SET_CS_0",
    "CAM_SET_DEMO1": "CAM_SET_CS_TWISTED_HALLWAY",
    "CAM_SET_MORI1": "CAM_SET_FOREST_BIRDS_EYE",
    "CAM_SET_ITEM0": "CAM_SET_SLOW_CHEST_CS",
    "CAM_SET_ITEM1": "CAM_SET_ITEM_UNUSED",
    "CAM_SET_DEMO3": "CAM_SET_CS_3",
    "CAM_SET_DEMO4": "CAM_SET_CS_ATTENTION",
    "CAM_SET_UFOBEAN": "CAM_SET_BEAN_GENERIC",
    "CAM_SET_LIFTBEAN": "CAM_SET_BEAN_LOST_WOODS",
    "CAM_SET_SCENE0": "CAM_SET_SCENE_UNUSED",
    "CAM_SET_SCENE1": "CAM_SET_SCENE_TRANSITION",
    "CAM_SET_HIDAN1": "CAM_SET_ELEVATOR_PLATFORM",
    "CAM_SET_HIDAN2": "CAM_SET_FIRE_STAIRCASE",
    "CAM_SET_MORI2": "CAM_SET_FOREST_UNUSED",
    "CAM_SET_MORI3": "CAM_SET_FOREST_DEFEAT_POE",
    "CAM_SET_TAKO": "CAM_SET_BIG_OCTO",
    "CAM_SET_SPOT05A": "CAM_SET_MEADOW_BIRDS_EYE",
    "CAM_SET_SPOT05B": "CAM_SET_MEADOW_UNUSED",
    "CAM_SET_HIDAN3": "CAM_SET_FIRE_BIRDS_EYE",
    "CAM_SET_ITEM2": "CAM_SET_TURN_AROUND",
    "CAM_SET_CIRCLE6": "CAM_SET_PIVOT_VERTICAL",
    "CAM_SET_DEMOC": "CAM_SET_CS_C",
    "CAM_SET_UO_FIBER": "CAM_SET_JABU_TENTACLE",
    "CAM_SET_TEPPEN": "CAM_SET_DIRECTED_YAW",
    "CAM_SET_CIRCLE7": "CAM_SET_PIVOT_FROM_SIDE",
}


class OOTCollisionVertex:
    def __init__(self, position):
        self.position = position


class OOTCollisionPolygon:
    def __init__(self, indices, normal, distance):
        self.indices = indices
        self.normal = normal
        self.distance = distance

    def convertShort02(self, ignoreCamera, ignoreActor, ignoreProjectile):
        vertPart = self.indices[0] & 0x1FFF
        colPart = (1 if ignoreCamera else 0) + (2 if ignoreActor else 0) + (4 if ignoreProjectile else 0)

        return vertPart | (colPart << 13)

    def convertShort04(self, enableConveyor):
        vertPart = self.indices[1] & 0x1FFF
        conveyorPart = 1 if enableConveyor else 0

        return vertPart | (conveyorPart << 13)

    def convertShort06(self):
        return self.indices[2] & 0x1FFF


class OOTPolygonType:
    def __eq__(self, other):
        return (
            self.eponaBlock == other.eponaBlock
            and self.decreaseHeight == other.decreaseHeight
            and self.floorSetting == other.floorSetting
            and self.wallSetting == other.wallSetting
            and self.floorProperty == other.floorProperty
            and self.exitID == other.exitID
            and self.cameraID == other.cameraID
            and self.isWallDamage == other.isWallDamage
            and self.enableConveyor == other.enableConveyor
            and self.conveyorRotation == other.conveyorRotation
            and self.conveyorSpeed == other.conveyorSpeed
            and self.hookshotable == other.hookshotable
            and self.echo == other.echo
            and self.lightingSetting == other.lightingSetting
            and self.terrain == other.terrain
            and self.sound == other.sound
            and self.ignoreCameraCollision == other.ignoreCameraCollision
            and self.ignoreActorCollision == other.ignoreActorCollision
            and self.ignoreProjectileCollision == other.ignoreProjectileCollision
        )

    def __ne__(self, other):
        return (
            self.eponaBlock != other.eponaBlock
            or self.decreaseHeight != other.decreaseHeight
            or self.floorSetting != other.floorSetting
            or self.wallSetting != other.wallSetting
            or self.floorProperty != other.floorProperty
            or self.exitID != other.exitID
            or self.cameraID != other.cameraID
            or self.isWallDamage != other.isWallDamage
            or self.enableConveyor != other.enableConveyor
            or self.conveyorRotation != other.conveyorRotation
            or self.conveyorSpeed != other.conveyorSpeed
            or self.hookshotable != other.hookshotable
            or self.echo != other.echo
            or self.lightingSetting != other.lightingSetting
            or self.terrain != other.terrain
            or self.sound != other.sound
            or self.ignoreCameraCollision != other.ignoreCameraCollision
            or self.ignoreActorCollision != other.ignoreActorCollision
            or self.ignoreProjectileCollision != other.ignoreProjectileCollision
        )

    def __hash__(self):
        return hash(
            (
                self.eponaBlock,
                self.decreaseHeight,
                self.floorSetting,
                self.wallSetting,
                self.floorProperty,
                self.exitID,
                self.cameraID,
                self.isWallDamage,
                self.enableConveyor,
                self.conveyorRotation,
                self.conveyorSpeed,
                self.hookshotable,
                self.echo,
                self.lightingSetting,
                self.terrain,
                self.sound,
                self.ignoreCameraCollision,
                self.ignoreActorCollision,
                self.ignoreProjectileCollision,
            )
        )

    def __init__(self):
        self.eponaBlock = None  # eponaBlock
        self.decreaseHeight = None  # decreaseHeight
        self.floorSetting = None  # floorSetting
        self.wallSetting = None  # wallSetting
        self.floorProperty = None  # floorProperty
        self.exitID = None  # exitID
        self.cameraID = None  # cameraID
        self.isWallDamage = None  # isWallDamage
        self.enableConveyor = None
        self.conveyorRotation = None  # conveyorDirection
        self.conveyorSpeed = None  # conveyorSpeed
        self.hookshotable = None  # hookshotable
        self.echo = None  # echo
        self.lightingSetting = None  # lightingSetting
        self.terrain = None  # terrain
        self.sound = None  # sound
        self.ignoreCameraCollision = None
        self.ignoreActorCollision = None
        self.ignoreProjectileCollision = None

    def convertHigh(self):
        value = (
            ((1 if self.eponaBlock else 0) << 31)
            | ((1 if self.decreaseHeight else 0) << 30)
            | (int(self.floorSetting, 16) << 26)
            | (int(self.wallSetting, 16) << 21)
            | (int(self.floorProperty, 16) << 13)
            | (self.exitID << 8)
            | (self.cameraID << 0)
        )

        return convertIntTo2sComplement(value, 4, False)

    def convertLow(self):
        value = (
            ((1 if self.isWallDamage else 0) << 27)
            | (self.conveyorRotation << 21)
            | (self.conveyorSpeed << 18)
            | ((1 if self.hookshotable else 0) << 17)
            | (int(self.echo, 16) << 11)
            | (self.lightingSetting << 6)
            | (int(self.terrain, 16) << 4)
            | (int(self.sound, 16) << 0)
        )

        return convertIntTo2sComplement(value, 4, False)


class OOTCollision:
    def __init__(self, ownerName):
        self.ownerName = ownerName
        self.bounds = []
        self.vertices = []
        # dict of polygon type : polygon list
        self.polygonGroups = {}
        self.cameraData = None
        self.waterBoxes = []

    def polygonCount(self):
        count = 0
        for polygonType, polygons in self.polygonGroups.items():
            count += len(polygons)
        return count

    def headerName(self):
        return self.ownerName + "_collisionHeader"

    def verticesName(self):
        return self.ownerName + "_vertices"

    def polygonsName(self):
        return self.ownerName + "_polygons"

    def polygonTypesName(self):
        return self.ownerName + "_polygonTypes"

    def camDataName(self):
        return self.ownerName + "_camData"

    def waterBoxesName(self):
        return self.ownerName + "_waterBoxes"


def getPolygonType(collisionProp):
    polygonType = OOTPolygonType()
    polygonType.ignoreCameraCollision = collisionProp.ignoreCameraCollision
    polygonType.ignoreActorCollision = collisionProp.ignoreActorCollision
    polygonType.ignoreProjectileCollision = collisionProp.ignoreProjectileCollision
    polygonType.eponaBlock = collisionProp.eponaBlock
    polygonType.decreaseHeight = collisionProp.decreaseHeight
    polygonType.floorSetting = getCustomProperty(collisionProp, "floorSetting")
    polygonType.wallSetting = getCustomProperty(collisionProp, "wallSetting")
    polygonType.floorProperty = getCustomProperty(collisionProp, "floorProperty")
    polygonType.exitID = collisionProp.exitID
    polygonType.cameraID = collisionProp.cameraID
    polygonType.isWallDamage = collisionProp.isWallDamage
    polygonType.enableConveyor = collisionProp.conveyorOption == "Land"
    if collisionProp.conveyorOption != "None":
        polygonType.conveyorRotation = int(collisionProp.conveyorRotation / (2 * math.pi) * 0x3F)
        polygonType.conveyorSpeed = int(getCustomProperty(collisionProp, "conveyorSpeed"), 16) + (
            4 if collisionProp.conveyorKeepMomentum else 0
        )
    else:
        polygonType.conveyorRotation = 0
        polygonType.conveyorSpeed = 0

    polygonType.hookshotable = collisionProp.hookshotable
    polygonType.echo = collisionProp.echo
    polygonType.lightingSetting = collisionProp.lightingSetting
    polygonType.terrain = getCustomProperty(collisionProp, "terrain")
    polygonType.sound = getCustomProperty(collisionProp, "sound")
    return polygonType


class OOTWaterBox(BoxEmpty):
    def __init__(self, roomIndex, lightingSetting, cameraSetting, flag19, position, scale, emptyScale):
        self.roomIndex = roomIndex
        self.lightingSetting = lightingSetting
        self.cameraSetting = cameraSetting
        self.flag19 = flag19
        BoxEmpty.__init__(self, position, scale, emptyScale)

    def propertyData(self):
        value = (
            ((1 if self.flag19 else 0) << 19)
            | (int(self.roomIndex) << 13)
            | (self.lightingSetting << 8)
            | (self.cameraSetting << 0)
        )
        return convertIntTo2sComplement(value, 4, False)


class OOTCameraData:
    def __init__(self, ownerName):
        self.ownerName = ownerName
        self.camPosDict = {}

    def camDataName(self):
        return self.ownerName + "_camData"

    def camPositionsName(self):
        return self.ownerName + "_camPosData"

    def validateCamPositions(self):
        count = 0
        while count < len(self.camPosDict):
            if count not in self.camPosDict:
                raise PluginError(
                    "Error: Camera positions do not have a consecutive list of indices.\n"
                    + "Missing index: "
                    + str(count)
                )
            count = count + 1


class OOTCameraPosData:
    def __init__(self, camSType, hasPositionData, position, rotation, fov, bgImageOverrideIndex):
        self.camSType = camSType
        self.position = position
        self.rotation = rotation
        self.fov = fov
        self.bgImageOverrideIndex = bgImageOverrideIndex
        self.unknown = -1
        self.hasPositionData = hasPositionData


class OOTCrawlspaceData:
    def __init__(self, camSType):
        self.camSType = camSType
        self.points = []

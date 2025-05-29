import mathutils
from ....f3d.f3d_writer import GfxList
from ....utility import CData, toAlnum


class OOTSkeleton:
    def __init__(self, name):
        self.name = name
        self.segmentID = None
        self.limbRoot = None
        self.hasLOD = False

    def createLimbList(self):
        if self.limbRoot is None:
            return []

        limbList = []
        self.limbRoot.getList(limbList)
        self.limbRoot.setLinks()
        return limbList

    def getNumDLs(self):
        if self.limbRoot is not None:
            return self.limbRoot.getNumDLs()
        else:
            return 0

    def getNumLimbs(self):
        if self.limbRoot is not None:
            return self.limbRoot.getNumLimbs()
        else:
            return 0

    def isFlexSkeleton(self):
        if self.limbRoot is not None:
            return self.limbRoot.isFlexSkeleton()
        else:
            return False

    def limbsName(self):
        return self.name + "Limbs"

    def toC(self):
        limbData = CData()
        data = CData()

        if self.limbRoot is None:
            return data

        limbList = self.createLimbList()
        isFlex = self.isFlexSkeleton()

        data.source += "void* " + self.limbsName() + "[" + str(self.getNumLimbs()) + "] = {\n"
        for limb in limbList:
            limbData.source += limb.toC(self.hasLOD)
            data.source += "\t&" + limb.name() + ",\n"
        limbData.source += "\n"
        data.source += "};\n\n"

        if isFlex:
            data.source += (
                "FlexSkeletonHeader "
                + self.name
                + " = { "
                + self.limbsName()
                + ", "
                + str(self.getNumLimbs())
                + ", "
                + str(self.getNumDLs())
                + " };\n\n"
            )
            data.header = "extern FlexSkeletonHeader " + self.name + ";\n"
        else:
            data.source += (
                "SkeletonHeader " + self.name + " = { " + self.limbsName() + ", " + str(self.getNumLimbs()) + " };\n\n"
            )
            data.header = "extern SkeletonHeader " + self.name + ";\n"

        for limb in limbList:
            name = (self.name + "_" + toAlnum(limb.boneName)).upper()
            if limb.index == 0:
                data.header += "#define " + name + "_POS_LIMB 0\n"
                data.header += "#define " + name + "_ROT_LIMB 1\n"
            else:
                data.header += "#define " + name + "_LIMB " + str(limb.index + 1) + "\n"
        data.header += "#define " + self.name.upper() + "_NUM_LIMBS " + str(len(limbList) + 1) + "\n"

        limbData.append(data)

        return limbData


class OOTDLReference:
    def __init__(self, name: str):
        self.name = name


class OOTLimb:
    def __init__(
        self,
        skeletonName: str,
        boneName: str,
        index: int,
        translation: mathutils.Vector,
        DL: GfxList | OOTDLReference,
        lodDL: GfxList | OOTDLReference,
    ):
        self.skeletonName = skeletonName
        self.boneName = boneName
        self.translation = translation
        self.firstChildIndex = 0xFF
        self.nextSiblingIndex = 0xFF
        self.DL = DL
        self.lodDL = lodDL

        self.isFlex = False
        self.index = index
        self.children = []
        self.inverseRotation = None

    def toC(self, isLOD):
        if not isLOD:
            data = "StandardLimb "
        else:
            data = "LodLimb "

        data += (
            self.name()
            + " = { "
            + "{ "
            + str(int(round(self.translation[0])))
            + ", "
            + str(int(round(self.translation[1])))
            + ", "
            + str(int(round(self.translation[2])))
            + " }, "
            + str(self.firstChildIndex)
            + ", "
            + str(self.nextSiblingIndex)
            + ", "
        )

        if not isLOD:
            data += self.DL.name if self.DL is not None else "NULL"
        else:
            data += (
                "{ "
                + (self.DL.name if self.DL is not None else "NULL")
                + ", "
                + (self.lodDL.name if self.lodDL is not None else "NULL")
                + " }"
            )

        data += " };\n"

        return data

    def name(self):
        return self.skeletonName + "Limb_" + format(self.index, "03")

    def getNumLimbs(self):
        numLimbs = 1
        for child in self.children:
            numLimbs += child.getNumLimbs()
        return numLimbs

    def getNumDLs(self):
        numDLs = 0
        if self.DL is not None or self.lodDL is not None:
            numDLs += 1

        for child in self.children:
            numDLs += child.getNumDLs()

        return numDLs

    def isFlexSkeleton(self):
        if self.isFlex:
            return True
        else:
            for child in self.children:
                if child.isFlexSkeleton():
                    return True
            return False

    def getList(self, limbList):
        # Like ootProcessBone, this must be in depth-first order to match the
        # OoT SkelAnime draw code, so the bones are listed in the file in the
        # same order as they are drawn. This is needed to enable the programmer
        # to get the limb indices and to enable optimization between limbs.
        limbList.append(self)
        for child in self.children:
            child.getList(limbList)

    def setLinks(self):
        if len(self.children) > 0:
            self.firstChildIndex = self.children[0].index
        for i in range(len(self.children)):
            if i < len(self.children) - 1:
                self.children[i].nextSiblingIndex = self.children[i + 1].index
            self.children[i].setLinks()
        # self -> child -> sibling

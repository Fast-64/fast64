from __future__ import annotations
from mathutils import Vector
from dataclasses import dataclass, field, InitVar
from abc import abstractmethod, ABC
from typing import Generic, TypeVar
from ....f3d.f3d_gbi import FMesh
from ....f3d.f3d_writer import GfxList
from ....utility import CData, toAlnum
from ...model_classes import LimbType, LimbSkinType, SkinAnimData


@dataclass
class OOTBaseLimb(ABC):
    skeletonName: str
    boneName: str
    index: int
    translation: Vector
    typeName: LimbType = field(init=False, default=LimbType.INVALID)
    _children: list[OOTBaseLimb] = field(default_factory=list, init=False)
    firstChildIndex: int = field(init=False, default=0xFF)
    nextSiblingIndex: int = field(init=False, default=0xFF)
    mesh: InitVar[FMesh | None] = None
    limbSkinType: InitVar[LimbSkinType] = LimbSkinType.EMPTY

    def __post_init__(self, mesh: FMesh | None, limbSkinType: LimbSkinType) -> None:
        if mesh is None:
            self.DL = None
        else:
            self.DL = mesh.draw

    @property
    def name(self) -> str:
        return f"{self.skeletonName}Limb_{self.index:03}"

    @property
    def children(self) -> list[OOTBaseLimb]:
        return self._children

    @children.setter
    def children(self, children: list[OOTBaseLimb]) -> None:
        self._children = children
        self.firstChildIndex = self._children[0].index

    def addChild(self, child: OOTBaseLimb, index: int | None = None) -> None:
        index = index if index is not None else len(self.children)

        self.children.insert(index, child)
        self.setLinks()

    def recursiveChildren(self) -> list[OOTBaseLimb]:
        children = []
        for child in self.children:
            children.append(child)
            children.extend(child.children)
        return children

    def setLinks(self) -> None:
        if len(self.children) > 0:
            self.firstChildIndex = self.children[0].index
        for i in range(len(self.children)):
            if i < len(self.children) - 1:
                self.children[i].nextSiblingIndex = self.children[i + 1].index
            self.children[i].setLinks()

    def getList(self, limbList: list[OOTBaseLimb]) -> None:
        limbList.append(self)
        for child in self.children:
            child.getList(limbList)

    def getNumLimbs(self):
        numLimbs = 1
        for child in self.children:
            numLimbs += child.getNumLimbs()
        return numLimbs

    @abstractmethod
    def getNumDLs(self) -> int:
        ...

    @abstractmethod
    def typeData(self) -> str:
        ...

    def toC(self) -> str:
        data = f"{self.typeName.value}Limb "

        data += (
            self.name
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

        data += self.typeData()

        data += " };\n"

        return data


@dataclass
class StandardLimb(OOTBaseLimb):
    typeName: LimbType = field(init=False, default=LimbType.STANDARD)
    DL: GfxList | OOTDLReference | None = field(init=False, default=None)

    def getNumDLs(self) -> int:
        numDLs = 0
        if self.DL is not None:
            numDLs += 1
        for child in self.children:
            numDLs += child.getNumDLs()

        return numDLs

    def typeData(self) -> str:
        return self.DL.name if self.DL is not None else "NULL"


@dataclass
class LODLimb(OOTBaseLimb):
    lodDL: GfxList | OOTDLReference | None = None
    typeName: LimbType = field(init=False, default=LimbType.LOD)
    DL: GfxList | OOTDLReference | None = field(init=False, default=None)

    @property
    def dLists(self) -> list[GfxList | OOTDLReference | None]:
        return [self.DL, self.lodDL]

    def getNumDLs(self) -> int:
        numDLs = 0
        if self.DL is not None or self.lodDL is not None:
            numDLs += 1

        for child in self.children:
            numDLs += child.getNumDLs()

        return numDLs

    def typeData(self) -> str:
        data = ""
        data += f"{{ {self.DL.name if self.DL is not None else 'NULL'}, "
        data += f"{self.lodDL.name if self.lodDL is not None else 'NULL'} }}"
        return data


@dataclass
class SkinLimb(OOTBaseLimb):
    typeName: LimbType = field(init=False, default=LimbType.SKIN)
    _segment: SkinAnimData | GfxList | OOTDLReference | None = field(init=False, default=None)

    def __post_init__(self, mesh: FMesh | None, limbSkinType: LimbSkinType) -> None:
        self.setSegment(mesh, limbSkinType)

    def setSegment(
        self,
        segment: FMesh | None,
        segmentType: LimbSkinType,
    ) -> None:
        self._segmentType: LimbSkinType = segmentType
        match segmentType:
            case LimbSkinType.SKIN_LIMB_TYPE_ANIMATED if isinstance(segment, SkinAnimData):
                self._segment = segment
            case LimbSkinType.SKIN_LIMB_TYPE_NORMAL if segment is not None:
                self._segment = segment.draw
            case LimbSkinType.EMPTY | LimbSkinType.SKINNED if segment is None:
                self._segment = None
            case _:
                raise ValueError(
                    f"SkinLimb {self.name} has invalid segmentType, segment combination\n"
                    + f"segmentType is: {segmentType.value}\n"
                    + f"segment is type {type(segment).__name__}"
                )

    @property
    def segmentType(self) -> LimbSkinType:
        return self._segmentType

    @property
    def segment(self) -> SkinAnimData | GfxList | OOTDLReference | None:
        return self._segment

    def getNumDLs(self) -> int:
        numDLs = 0

        if self.segmentType in (LimbSkinType.SKIN_LIMB_TYPE_ANIMATED, LimbSkinType.SKIN_LIMB_TYPE_NORMAL):
            numDLs += 1

        for child in self.children:
            numDLs += child.getNumDLs()
        return numDLs

    def typeData(self) -> str:
        data = ""

        data += f"{self.segmentType.value}, "

        match self.segmentType:
            case LimbSkinType.EMPTY | LimbSkinType.SKINNED:
                data += "NULL"
            case LimbSkinType.SKIN_LIMB_TYPE_ANIMATED if self.segment is not None:
                data += f"&{self.segment.name}"
            case LimbSkinType.SKIN_LIMB_TYPE_NORMAL if self.segment is not None:
                data += self.segment.name
            case _:
                raise ValueError(f"Invalid segment, segmentType combination in SkinLimb {self.name}")

        return data


OOTLimb = TypeVar("OOTLimb", bound=OOTBaseLimb)


@dataclass
class OOTBaseSkeleton(ABC, Generic[OOTLimb]):
    name: str
    limbType: type[OOTLimb]
    limbRoot: OOTLimb | None = None

    @property
    def skeletonName(self) -> str:
        return self.name

    def addChild(self, child: OOTLimb) -> None:
        self.limbRoot = child

    def createLimbList(self) -> list[OOTLimb]:
        if self.limbRoot is None:
            return []

        limbList = []
        self.limbRoot.getList(limbList)
        self.limbRoot.setLinks()
        return limbList

    def getNumLimbs(self) -> int:
        if self.limbRoot is not None:
            return self.limbRoot.getNumLimbs()
        else:
            return 0

    def limbsName(self) -> str:
        return f"{self.name}Limbs"

    @abstractmethod
    def headerData(self) -> CData:
        ...

    def toC(self) -> CData:
        limbData = CData()
        data = CData()

        if self.limbRoot is None:
            return data

        limbList = self.createLimbList()

        data.source += "void* " + self.limbsName() + "[" + str(self.getNumLimbs()) + "] = {\n"
        for limb in limbList:
            limbData.source += limb.toC()
            data.source += "\t&" + limb.name + ",\n"
        limbData.source += "\n"
        data.source += "};\n\n"

        data.append(self.headerData())

        for limb in limbList:
            name = f"{self.name}_{toAlnum(limb.boneName)}".upper()
            if limb.index == 0:
                data.header += f"#define {name}_POS_LIMB 0\n"
                data.header += f"#define {name}_ROT_LIMB 1\n"
            else:
                data.header += f"#define {name}_LIMB {limb.index + 1}\n"
        data.header += f"#define {self.name.upper()}_NUM_LIMBS {len(limbList) + 1}\n"

        limbData.append(data)

        return limbData


@dataclass
class StandardSkeleton(OOTBaseSkeleton[OOTLimb]):
    def headerData(self) -> CData:
        data = CData()

        data.source += f"SkeletonHeader {self.name} = {{ {self.limbsName()}, {self.getNumLimbs()} }};\n\n"
        data.header = f"extern SkeletonHeader {self.name};\n"

        return data


FlexLimb = TypeVar("FlexLimb", StandardLimb, LODLimb)


@dataclass
class FlexSkeleton(OOTBaseSkeleton[FlexLimb]):
    def headerData(self) -> CData:
        data = CData()
        data.source += (
            f"FlexSkeletonHeader {self.name} = {{ {self.limbsName()}, {self.getNumLimbs()}, {self.getNumDLs()} }};\n\n"
        )
        data.header = f"extern FlexSkeletonHeader {self.name};\n"
        return data

    def getNumDLs(self) -> int:
        if self.limbRoot is not None:
            return self.limbRoot.getNumDLs()
        else:
            return 0


class OOTDLReference:
    def __init__(self, name: str):
        self.name = name

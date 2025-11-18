from typing import Optional
from pathlib import Path
from enum import IntFlag
from io import StringIO
from copy import copy
import dataclasses
import numpy as np
import functools
import typing
import re

from bpy.types import Action

from ...f3d.f3d_parser import math_eval

from ...utility import PluginError, cast_integer, encodeSegmentedAddr, intToHex
from ..sm64_constants import MAX_U16, SegmentData
from ..sm64_utility import CommentMatch, adjust_start_end
from ..sm64_classes import RomReader, DMATable, DMATableElement, IntArray

from .constants import HEADER_STRUCT, HEADER_SIZE, TABLE_ELEMENT_PATTERN
from .utility import get_dma_header_name, get_dma_anim_name


@dataclasses.dataclass
class CArrayDeclaration:
    name: str = ""
    path: Path = Path("")
    file_name: str = ""
    values: list[str] | dict[str, str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class SM64_AnimPair:
    values: np.ndarray[typing.Any, np.dtype[np.int16]] = dataclasses.field(compare=False)

    # Importing
    address: int = 0
    end_address: int = 0

    offset: int = 0  # For compressing

    def __post_init__(self):
        assert self.values.size > 0, "values cannot be empty"

    def clean_frames(self):
        mask = self.values != self.values[-1]
        #  Reverse the order, find the last element with the same value
        index = np.argmax(mask[::-1])
        if index != 1:
            self.values = self.values[: 1 if index == 0 else (-index + 1)]
        return self

    def get_frame(self, frame: int):
        return self.values[min(frame, len(self.values) - 1)]


@dataclasses.dataclass
class SM64_AnimData:
    pairs: list[SM64_AnimPair] = dataclasses.field(default_factory=list)
    indice_reference: str | int = ""
    values_reference: str | int = ""

    # Importing
    indices_file_name: str = ""
    values_file_name: str = ""
    value_end_address: int = 0
    indice_end_address: int = 0
    start_address: int = 0
    end_address: int = 0

    @property
    def key(self):
        return (self.indice_reference, self.values_reference)

    def create_tables(self, start_address=-1):
        indice_tables, value_tables = create_tables([self], start_address=start_address)
        assert (
            len(value_tables) == 1 and len(indice_tables) == 1
        ), "Single animation data export should only return 1 of each table."
        return indice_tables[0], value_tables[0]

    def to_c(self, dma: bool = False):
        text_data = StringIO()

        indice_table, value_table = self.create_tables()
        if dma:
            indice_table.to_c(text_data, new_lines=2)
            value_table.to_c(text_data)
        else:
            value_table.to_c(text_data, new_lines=2)
            indice_table.to_c(text_data)

        return text_data.getvalue()

    def to_binary(self, start_address=-1):
        indice_table, value_table = self.create_tables(start_address)
        values_offset = len(indice_table.data) * 2

        data = bytearray()
        data.extend(indice_table.to_binary())
        data.extend(value_table.to_binary())
        return data, values_offset

    def read_binary(self, indices_reader: RomReader, values_reader: RomReader, bone_count: int):
        print(
            f"Reading pairs from indices table at {intToHex(indices_reader.address)}",
            f"and values table at {intToHex(values_reader.address)}.",
        )
        self.indice_reference = indices_reader.start_address
        self.values_reference = values_reader.start_address

        # 3 pairs per bone + 3 for root translation of 2, each 2 bytes
        indices_size = (((bone_count + 1) * 3) * 2) * 2
        indices_values = np.frombuffer(indices_reader.read_data(indices_size), dtype=">u2")
        for i in range(0, len(indices_values), 2):
            max_frame, offset = indices_values[i], indices_values[i + 1]
            address, size = values_reader.start_address + (offset * 2), max_frame * 2

            values = np.frombuffer(values_reader.read_data(size, address), dtype=">i2", count=max_frame)
            self.pairs.append(SM64_AnimPair(values, address, address + size, offset).clean_frames())
        self.indice_end_address = indices_reader.address
        self.value_end_address = max(pair.end_address for pair in self.pairs)

        self.start_address = min(self.indice_reference, self.values_reference)
        self.end_address = max(self.indice_end_address, self.value_end_address)
        return self

    def read_c(self, indice_decl: CArrayDeclaration, value_decl: CArrayDeclaration):
        print(f'Reading data from "{indice_decl.name}" and "{value_decl.name}" c declarations.')
        self.indices_file_name, self.values_file_name = indice_decl.file_name, value_decl.file_name
        self.indice_reference, self.values_reference = indice_decl.name, value_decl.name

        indices_values = np.vectorize(lambda x: int(x, 0), otypes=[np.uint16])(indice_decl.values)
        values_array = np.vectorize(lambda x: int(x, 0), otypes=[np.int16])(value_decl.values)

        for i in range(0, len(indices_values), 2):
            max_frame, offset = indices_values[i], indices_values[i + 1]
            self.pairs.append(SM64_AnimPair(values_array[offset : offset + max_frame], -1, -1, offset).clean_frames())
        return self


class SM64_AnimFlags(IntFlag):
    prop: Optional[str]

    def __new__(cls, value, blender_prop: str | None = None):
        obj = int.__new__(cls, value)
        obj._value_, obj.prop = 1 << value, blender_prop
        return obj

    ANIM_FLAG_NOLOOP = (0, "no_loop")
    ANIM_FLAG_FORWARD = (1, "backwards")
    ANIM_FLAG_2 = (2, "no_acceleration")
    ANIM_FLAG_HOR_TRANS = (3, "only_vertical")
    ANIM_FLAG_VERT_TRANS = (4, "only_horizontal")
    ANIM_FLAG_5 = (5, "disabled")
    ANIM_FLAG_6 = (6, "no_trans")
    ANIM_FLAG_7 = 7

    ANIM_FLAG_BACKWARD = (1, "backwards")  # refresh 16

    # hackersm64
    ANIM_FLAG_NO_ACCEL = (2, "no_acceleration")
    ANIM_FLAG_DISABLED = (5, "disabled")
    ANIM_FLAG_NO_TRANS = (6, "no_trans")
    ANIM_FLAG_UNUSED = 7

    @classmethod
    @functools.cache
    def all_flags(cls):
        flags = SM64_AnimFlags(0)
        for flag in cls.__members__.values():
            flags |= flag
        return flags

    @classmethod
    @functools.cache
    def all_flags_with_prop(cls):
        flags = SM64_AnimFlags(0)
        for flag in cls.__members__.values():
            if flag.prop is not None:
                flags |= flag
        return flags

    @classmethod
    @functools.cache
    def props_to_flags(cls):
        return {flag.prop: flag for flag in cls.__members__.values() if flag.prop is not None}

    @classmethod
    @functools.cache
    def flags_to_names(cls):
        names: dict[SM64_AnimFlags, list[str]] = {}
        for name, flag in cls.__members__.items():
            if flag in names:
                names[flag].append(name)
            else:
                names[flag] = [name]
        return names

    @property
    @functools.cache
    def names(self):
        names: list[str] = []
        for flag, flag_names in SM64_AnimFlags.flags_to_names().items():
            if flag in self:
                names.append("/".join(flag_names))
        if self & ~self.__class__.all_flags():  # flag value outside known flags
            names.append("unknown bits")
        return names

    @classmethod
    @functools.cache
    def evaluate(cls, value: str | int):
        if isinstance(value, cls):  # the value was already evaluated
            return value
        elif isinstance(value, str):
            try:
                value = cls(math_eval(value, cls))
            except Exception as exc:  # pylint: disable=broad-except
                print(f"Failed to evaluate flags {value}: {exc}")
        if isinstance(value, int):  # the value was fully evaluated
            if isinstance(value, cls):
                value = value.value
            # cast to u16 for simplicity
            return cls(cast_integer(value, 16, signed=False))
        else:  # the value was not evaluated
            return value


@dataclasses.dataclass
class SM64_AnimHeader:
    reference: str | int = ""
    flags: SM64_AnimFlags | str = SM64_AnimFlags(0)
    trans_divisor: int = 0
    start_frame: int = 0
    loop_start: int = 0
    loop_end: int = 1
    bone_count: int = 0
    length: int = 0
    indice_reference: Optional[str | int] = None
    values_reference: Optional[str | int] = None
    data: Optional[SM64_AnimData] = None

    enum_name: str = ""
    # Imports
    file_name: str = ""
    end_address: int = 0
    header_variant: int = 0
    table_index: int = 0
    action: Action | None = None

    @property
    def data_key(self):
        return (self.indice_reference, self.values_reference)

    @property
    def flags_comment(self):
        if isinstance(self.flags, SM64_AnimFlags):
            return ", ".join(self.flags.names)
        return ""

    @property
    def c_flags(self):
        return self.flags if isinstance(self.flags, str) else intToHex(self.flags.value, 2)

    def get_reference(self, override: Optional[str | int], expected_type: type, reference_name: str):
        name = reference_name.replace("_", " ")
        if override:
            reference = override
        elif self.data and getattr(self.data, reference_name):
            reference = getattr(self.data, reference_name)
        elif getattr(self, reference_name):
            reference = getattr(self, reference_name)
        else:
            assert False, f"Unknown {name}"

        assert isinstance(
            reference, expected_type
        ), f"{name.capitalize()} must be a {expected_type},is instead {type(reference)}."
        return reference

    def get_values_reference(self, override: Optional[str | int] = None, expected_type: type = str):
        return self.get_reference(override, expected_type, "values_reference")

    def get_indice_reference(self, override: Optional[str | int] = None, expected_type: type = str):
        return self.get_reference(override, expected_type, "indice_reference")

    def to_c(self, values_override: Optional[str] = None, indice_override: Optional[str] = None, dma=False):
        assert not dma or isinstance(  # assert if dma and flags are not SM64_AnimFlags
            self.flags, SM64_AnimFlags
        ), f"Flags must be SM64_AnimFlags for C DMA, is instead {type(self.flags)}"
        return (
            f"static const struct Animation {self.reference}{'[]' if dma else ''} = {{\n"
            + f"\t{self.c_flags}, // flags {self.flags_comment}\n"
            f"\t{self.trans_divisor}, // animYTransDivisor\n"
            f"\t{self.start_frame}, // startFrame\n"
            f"\t{self.loop_start}, // loopStart\n"
            f"\t{self.loop_end}, // loopEnd\n"
            f"\tANIMINDEX_NUMPARTS({self.get_indice_reference(indice_override, str)}), // unusedBoneCount\n"
            f"\t{self.get_values_reference(values_override, str)}, // values\n"
            f"\t{self.get_indice_reference(indice_override, str)}, // index\n"
            "\t0 // length\n"
            "};\n"
        )

    def to_binary(
        self,
        values_override: Optional[int] = None,
        indice_override: Optional[int] = None,
        segment_data: SegmentData | None = None,
        length=0,
    ):
        assert isinstance(
            self.flags, SM64_AnimFlags
        ), f"Flags must be SM64_AnimFlags for binary, is instead {type(self.flags)}"
        values_address = self.get_values_reference(values_override, int)
        indice_address = self.get_indice_reference(indice_override, int)
        if segment_data:
            values_address = int.from_bytes(encodeSegmentedAddr(values_address, segment_data), "big")
            indice_address = int.from_bytes(encodeSegmentedAddr(indice_address, segment_data), "big")

        return HEADER_STRUCT.pack(
            self.flags.value,
            self.trans_divisor,
            self.start_frame,
            self.loop_start,
            self.loop_end,
            self.bone_count,
            values_address,
            indice_address,
            length,
        )

    @staticmethod
    def read_binary(
        reader: RomReader,
        read_headers: dict[str, "SM64_AnimHeader"],
        dma: bool = False,
        bone_count: Optional[int] = None,
        table_index: Optional[int] = None,
    ):
        if str(reader.start_address) in read_headers:
            return read_headers[str(reader.start_address)]
        print(f"Reading animation header at {intToHex(reader.start_address)}.")

        header = SM64_AnimHeader()
        read_headers[str(reader.start_address)] = header
        header.reference = reader.start_address

        header.flags = SM64_AnimFlags.evaluate(reader.read_int(2, True))  # /*0x00*/ s16 flags;
        header.trans_divisor = reader.read_int(2, True)  # /*0x02*/ s16 animYTransDivisor;
        header.start_frame = reader.read_int(2, True)  # /*0x04*/ s16 startFrame;
        header.loop_start = reader.read_int(2, True)  # /*0x06*/ s16 loopStart;
        header.loop_end = reader.read_int(2, True)  # /*0x08*/ s16 loopEnd;

        # /*0x0A*/ s16 unusedBoneCount; (Unused in engine)
        header.bone_count = reader.read_int(2, True)
        if header.bone_count <= 0:
            if bone_count is None:
                raise PluginError(
                    "No bone count in header and no bone count passed in from target armature, cannot figure out"
                )
            header.bone_count = bone_count
            print("Old exports lack a defined bone count, invalid armatures won't be detected")
        elif bone_count is not None and header.bone_count != bone_count:
            raise PluginError(
                f"Imported header's bone count is {header.bone_count} but object's is {bone_count}",
            )

        # /*0x0C*/ const s16 *values;
        # /*0x10*/ const u16 *index;
        if dma:
            header.values_reference = reader.start_address + reader.read_int(4)
            header.indice_reference = reader.start_address + reader.read_int(4)
        else:
            header.values_reference, header.indice_reference = reader.read_ptr(), reader.read_ptr()
        header.length = reader.read_int(4)

        header.end_address = reader.address + 1
        header.table_index = len(read_headers) if table_index is None else table_index

        data = next(
            (other_header.data for other_header in read_headers.values() if header.data_key == other_header.data_key),
            None,
        )
        if not data:
            indices_reader = reader.branch(header.indice_reference)
            values_reader = reader.branch(header.values_reference)
            if indices_reader and values_reader:
                data = SM64_AnimData().read_binary(
                    indices_reader,
                    values_reader,
                    header.bone_count,
                )
        header.data = data

        return header

    @staticmethod
    def read_c(
        header_decl: CArrayDeclaration,
        value_decls,
        indices_decls,
        read_headers: dict[str, "SM64_AnimHeader"],
        table_index: Optional[int] = None,
    ):
        if header_decl.name in read_headers:
            return read_headers[header_decl.name]
        if len(header_decl.values) != 9:
            raise ValueError(f"Header declarion has {len(header_decl.values)} values instead of 9.\n {header_decl}")
        print(f'Reading header "{header_decl.name}" c declaration.')
        header = SM64_AnimHeader()
        read_headers[header_decl.name] = header
        header.reference = header_decl.name
        header.file_name = header_decl.file_name

        # Place the values into a dictionary, handles designated initialization
        if isinstance(header_decl.values, list):
            designated = {}
            for value, var in zip(
                header_decl.values,
                [
                    "flags",
                    "animYTransDivisor",
                    "startFrame",
                    "loopStart",
                    "loopEnd",
                    "unusedBoneCount",
                    "values",
                    "index",
                    "length",
                ],
            ):
                designated[var] = value
        else:
            designated = header_decl.values

        # Read from the dict
        header.flags = SM64_AnimFlags.evaluate(designated["flags"])
        header.trans_divisor = int(designated["animYTransDivisor"], 0)
        header.start_frame = int(designated["startFrame"], 0)
        header.loop_start = int(designated["loopStart"], 0)
        header.loop_end = int(designated["loopEnd"], 0)
        # bone_count = designated["unusedBoneCount"]
        header.values_reference = designated["values"]
        header.indice_reference = designated["index"]

        header.table_index = len(read_headers) if table_index is None else table_index

        data = next(
            (other_header.data for other_header in read_headers.values() if header.data_key == other_header.data_key),
            None,
        )
        if not data:
            indices_decl = next((indice for indice in indices_decls if indice.name == header.indice_reference), None)
            value_decl = next((value for value in value_decls if value.name == header.values_reference), None)
            if indices_decl and value_decl:
                data = SM64_AnimData().read_c(indices_decl, value_decl)
        header.data = data

        return header


@dataclasses.dataclass
class SM64_Anim:
    data: SM64_AnimData | None = None
    headers: list[SM64_AnimHeader] = dataclasses.field(default_factory=list)
    file_name: str = ""

    # Imports
    action_name: str = ""  # Used for the blender action's name
    action: Action | None = None  # Used in the table class to prop function

    @property
    def names(self) -> tuple[list[str], list[str]]:
        names, enums = [], []
        for header in self.headers:
            names.append(header.reference)
            enums.append(header.enum_name)
        return names, enums

    @property
    def header_names(self) -> list[str]:
        return self.names[0]

    @property
    def enum_names(self) -> list[str]:
        return self.names[1]

    def to_binary_dma(self):
        assert self.data
        headers: list[bytes] = []

        indice_offset = HEADER_SIZE * len(self.headers)
        anim_data, values_offset = self.data.to_binary()
        for header in self.headers:
            header_data = header.to_binary(
                indice_offset + values_offset, indice_offset, length=indice_offset + len(anim_data)
            )
            headers.append(header_data)
            indice_offset -= HEADER_SIZE
        return headers, anim_data

    def to_binary(self, start_address: int = 0, segment_data: SegmentData | None = None):
        data: bytearray = bytearray()
        ptrs: list[int] = []
        if self.data:
            anim_data, values_offset = self.data.to_binary()
            indice_offset = start_address + (HEADER_SIZE * len(self.headers))
            values_offset = indice_offset + values_offset
        else:
            anim_data = bytearray()
            indice_offset = values_offset = None
        for header in self.headers:
            if self.data:
                ptrs.extend([start_address + len(data) + 12, start_address + len(data) + 16])
            header_data = header.to_binary(
                values_offset,
                indice_offset,
                segment_data,
            )
            data.extend(header_data)

        data.extend(anim_data)
        return data, ptrs

    def headers_to_c(self, dma: bool) -> str:
        text_data = StringIO()
        for header in self.headers:
            text_data.write(header.to_c(dma=dma))
            text_data.write("\n")
        return text_data.getvalue()

    def to_c(self, dma: bool):
        text_data = StringIO()
        c_headers = self.headers_to_c(dma)
        if dma:
            text_data.write(c_headers)
            text_data.write("\n")
        if self.data:
            text_data.write(self.data.to_c(dma))
            text_data.write("\n")
        if not dma:
            text_data.write(c_headers)
        return text_data.getvalue()


@dataclasses.dataclass
class SM64_AnimTableElement:
    reference: str | int | None = None
    header: SM64_AnimHeader | None = None

    # C exporting
    enum_name: str = ""
    reference_start: int = -1
    reference_end: int = -1
    enum_start: int = -1
    enum_end: int = -1
    enum_val: str = ""

    @property
    def c_name(self):
        if self.reference:
            return self.reference
        return ""

    @property
    def c_reference(self):
        if self.reference:
            return f"&{self.reference}"
        return "NULL"

    @property
    def enum_c(self):
        if self.enum_val:
            return f"{self.enum_name} = {self.enum_val}"
        return self.enum_name

    @property
    def data(self):
        return self.header.data if self.header else None

    def to_c(self, designated: bool):
        if designated and self.enum_name:
            return f"[{self.enum_name}] = {self.c_reference},"
        else:
            return f"{self.c_reference},"


@dataclasses.dataclass
class SM64_AnimTable:
    reference: str | int = ""
    enum_list_reference: str = ""
    enum_list_delimiter: str = ""
    file_name: str = ""
    elements: list[SM64_AnimTableElement] = dataclasses.field(default_factory=list)
    # Importing
    end_address: int = 0
    # C exporting
    values_reference: str = ""
    start: int = -1
    end: int = -1
    enum_list_start: int = -1
    enum_list_end: int = -1

    @property
    def names(self) -> tuple[list[str], list[str]]:
        names, enums = [], []
        for element in self.elements:
            names.append(element.c_name)
            enums.append(element.enum_name)
        return names, enums

    @property
    def header_names(self) -> list[str]:
        return self.names[0]

    @property
    def enum_names(self) -> list[str]:
        return self.names[1]

    @property
    def header_data_sets(self) -> tuple[list[SM64_AnimHeader], list[SM64_AnimData]]:
        # Remove duplicates of data and headers, keep order by using a list
        data_set = []
        headers_set = []
        for element in self.elements:
            if element.data and not element.data in data_set:
                data_set.append(element.data)
            if element.header and not element.header in headers_set:
                headers_set.append(element.header)
        return headers_set, data_set

    @property
    def header_set(self) -> list[SM64_AnimHeader]:
        return self.header_data_sets[0]

    @property
    def has_null_delimiter(self):
        return bool(self.elements and self.elements[-1].reference is None)

    def get_seperate_anims(self):
        print("Getting seperate animations from table.")
        anims: list[SM64_Anim] = []
        headers_set, headers_added = self.header_set, []
        for header in headers_set:
            if header in headers_added:
                continue
            ordered_headers: list[SM64_AnimHeader] = []
            variant = 0
            for other_header in headers_set:
                if other_header.data == header.data:
                    other_header.header_variant = variant
                    ordered_headers.append(other_header)
                    headers_added.append(other_header)
                    variant += 1

            anims.append(SM64_Anim(header.data, ordered_headers, header.file_name))
        return anims

    def get_seperate_anims_dma(self) -> list[SM64_Anim]:
        print("Getting seperate DMA animations from table.")

        anims = []
        header_nums = []
        included_headers: list[SM64_AnimHeader] = []
        data = None
        # For creating duplicates
        data_already_added = []
        headers_already_added = []

        for i, element in enumerate(self.elements):
            assert element.header, f"Header in table element {i} is not set."
            assert element.data, f"Data in table element {i} is not set."
            header_nums.append(i)

            header, data = element.header, element.data
            if header in headers_already_added:
                print(f"Made duplicate of header {i}.")
                header = copy(header)
            header.reference = get_dma_header_name(i)
            headers_already_added.append(header)

            included_headers.append(header)

            # If not at the end of the list and the next element doesn´t have different data
            if (i < len(self.elements) - 1) and self.elements[i + 1].data is data:
                continue

            name = get_dma_anim_name(header_nums)
            file_name = f"{name}.inc.c"
            if data in data_already_added:
                print(f"Made duplicate of header {i}'s data.")
                data = copy(data)
            data_already_added.append(data)

            data.indice_reference, data.values_reference = f"{name}_indices", f"{name}_values"
            # Normal names are possible (order goes by line and file) but would break convention
            for i, included_header in enumerate(included_headers):
                included_header.file_name = file_name
                included_header.indice_reference = data.indice_reference
                included_header.values_reference = data.values_reference
                included_header.data = data
                included_header.header_variant = i
            anims.append(SM64_Anim(data, included_headers, file_name))

            header_nums.clear()
            included_headers = []

        return anims

    def to_binary_dma(self):
        dma_table = DMATable()
        for animation in self.get_seperate_anims_dma():
            headers, data = animation.to_binary_dma()
            end_offset = len(dma_table.data) + (HEADER_SIZE * len(headers)) + len(data)
            for header in headers:
                offset = len(dma_table.data)
                size = end_offset - offset
                dma_table.entries.append(DMATableElement(offset, size))
                dma_table.data.extend(header)
            dma_table.data.extend(data)
        return dma_table.to_binary()

    def to_combined_binary(self, table_address=0, data_address=-1, segment_data: SegmentData | None = None):
        table_data: bytearray = bytearray()
        data: bytearray = bytearray()
        ptrs: list[int] = []
        headers_set, data_set = self.header_data_sets

        # Pre calculate offsets
        table_length = len(self.elements) * 4
        if data_address == -1:
            data_address = table_address + table_length

        headers_length = len(headers_set) * HEADER_SIZE
        indice_tables, value_tables = create_tables(data_set, self.values_reference, data_address + headers_length)

        # Add the animation table
        for i, element in enumerate(self.elements):
            if element.header:
                ptrs.append(table_address + len(table_data))
                header_offset = data_address + (headers_set.index(element.header) * HEADER_SIZE)
                if segment_data:
                    table_data.extend(encodeSegmentedAddr(header_offset, segment_data))
                else:
                    table_data.extend(header_offset.to_bytes(4, byteorder="big"))
                continue
            if element.reference is None:
                table_data.extend(0x0.to_bytes(4, byteorder="big"))
                continue
            assert isinstance(element.reference, int), f"Reference at element {i} is not an int."
            table_data.extend(element.reference.to_bytes(4, byteorder="big"))

        for anim_header in headers_set:  # Add the headers
            if not anim_header.data:
                data.extend(anim_header.to_binary())
                continue
            ptrs.extend([data_address + len(data) + 12, data_address + len(data) + 16])
            data.extend(anim_header.to_binary(segment_data=segment_data))

        for table in indice_tables + value_tables:
            data.extend(table.to_binary())

        return table_data, data, ptrs

    def data_and_headers_to_c(self, dma: bool):
        files_data: dict[str, str] = {}
        animation: SM64_Anim
        for animation in self.get_seperate_anims_dma() if dma else self.get_seperate_anims():
            files_data[animation.file_name] = animation.to_c(dma=dma)
        return files_data

    def data_and_headers_to_c_combined(self):
        text_data = StringIO()
        headers_set, data_set = self.header_data_sets
        if data_set:
            indice_tables, value_tables = create_tables(data_set, self.values_reference)
            for table in value_tables + indice_tables:
                table.to_c(text_data, new_lines=2)
        for anim_header in headers_set:
            text_data.write(anim_header.to_c())
            text_data.write("\n")

        return text_data.getvalue()

    def read_binary(
        self,
        reader: RomReader,
        read_headers: dict[str, SM64_AnimHeader],
        table_index: Optional[int] = None,
        bone_count: Optional[int] = None,
        size: Optional[int] = None,
    ):
        print(f"Reading table at address {reader.start_address}.")
        self.elements.clear()
        self.reference = reader.start_address

        range_size = size or 300
        if table_index is not None:
            range_size = min(range_size, table_index + 1)
        for i in range(range_size):
            ptr = reader.read_ptr()
            if size is None and ptr == 0:  # If no specified size and ptr is NULL, break
                self.elements.append(SM64_AnimTableElement())
                break
            elif table_index is not None and i != table_index:
                continue  # Skip entries until table_index if specified

            header_reader = reader.branch(ptr)
            if header_reader is None:
                self.elements.append(SM64_AnimTableElement(ptr))
            else:
                try:
                    header = SM64_AnimHeader.read_binary(
                        header_reader,
                        read_headers,
                        False,
                        bone_count,
                        i,
                    )
                except Exception as exc:
                    raise PluginError(f"Failed to read header in table element {i}: {str(exc)}") from exc
                self.elements.append(SM64_AnimTableElement(ptr, header))

            if table_index is not None:  # Break if table_index is specified
                break
        else:
            if table_index is not None:
                raise PluginError(f"Table index {table_index} not found in table.")
            if size is None:
                raise PluginError(f"Iterated through {range_size} elements and no NULL was found.")
        self.end_address = reader.address
        return self

    def read_dma_binary(
        self,
        reader: RomReader,
        read_headers: dict[str, SM64_AnimHeader],
        table_index: Optional[int] = None,
        bone_count: Optional[int] = None,
    ):
        dma_table = DMATable()
        dma_table.read_binary(reader)
        self.reference = reader.start_address
        if table_index is not None:
            assert table_index >= 0 and table_index < len(
                dma_table.entries
            ), f"Index {table_index} outside of defined table ({len(dma_table.entries)} entries)."
            entrie = dma_table.entries[table_index]
            header_reader = reader.branch(entrie.address)
            if header_reader is None:
                raise PluginError("Failed to branch into DMA entrie's address")
            return SM64_AnimHeader.read_binary(
                header_reader,
                read_headers,
                True,
                bone_count,
                table_index,
            )

        for i, entrie in enumerate(dma_table.entries):
            header_reader = reader.branch(entrie.address)
            try:
                if not header_reader:
                    raise PluginError("Failed to branch to header's address")
                header = SM64_AnimHeader.read_binary(header_reader, read_headers, True, bone_count, i)
            except Exception as exc:
                raise PluginError(f"Failed to read header in table element {i}: {str(exc)}") from exc
            self.elements.append(SM64_AnimTableElement(reader.start_address, header))
        self.end_address = dma_table.end_address
        return self

    def read_c(
        self,
        c_data: str,
        start: int,
        end: int,
        comment_map: list[CommentMatch],
        read_headers: dict[str, SM64_AnimHeader],
        header_decls: list[CArrayDeclaration],
        values_decls: list[CArrayDeclaration],
        indices_decls: list[CArrayDeclaration],
    ):
        table_start, table_end = adjust_start_end(start, end, comment_map)
        self.start, self.end = table_start, table_end

        for i, element_match in enumerate(re.finditer(TABLE_ELEMENT_PATTERN, c_data[start:end])):
            enum, element, null = (
                element_match.group("enum"),
                element_match.group("element"),
                element_match.group("null"),
            )
            if enum is None and element is None and null is None:  # comment
                continue
            header = None
            if element is not None:
                header_decl = next((header for header in header_decls if header.name == element), None)
                if header_decl:
                    header = SM64_AnimHeader.read_c(
                        header_decl,
                        values_decls,
                        indices_decls,
                        read_headers,
                        i,
                    )
            element_start, element_end = adjust_start_end(
                start + element_match.start(), start + element_match.end(), comment_map
            )
            self.elements.append(
                SM64_AnimTableElement(
                    element,
                    enum_name=enum,
                    reference_start=element_start - table_start,
                    reference_end=element_end - table_start,
                    header=header,
                )
            )


def create_tables(anims_data: list[SM64_AnimData], values_name="", start_address=-1):
    """
    Can generate multiple indices table with only one value table (or multiple if needed),
    which improves compression (this feature is used in table exports).
    Update the animation data with the correct references.
    Returns: indice_tables, value_tables (in that order)
    """

    def add_data(values_table: IntArray, size: int, anim_data: SM64_AnimData, values_address: int):
        data = values_table.data
        for pair in anim_data.pairs:
            pair_values = pair.values
            if len(pair_values) >= MAX_U16:
                raise PluginError(
                    f"Pair frame count ({len(pair_values)}) is higher than the 16 bit max ({MAX_U16}). Too many frames."
                )

            # It's never worth it to find an existing offset for values bigger than 1 frame.
            # From my (@Lilaa3) testing, the only improvement in Mario resulted in just 286 bytes saved.
            offset = None
            if len(pair_values) == 1:
                indices = np.isin(data[:size], pair_values[0]).nonzero()[0]
                offset = indices[0] if indices.size > 0 else None

            if offset is None:  # no existing offset found
                offset = size
                size = offset + len(pair_values)
                if size > MAX_U16:  # exceeded limit, but we may be able to recover with a new table
                    return -1, None
                data[offset:size] = pair_values
            pair.offset = offset

        # build indice table
        indice_values = np.empty((len(anim_data.pairs), 2), np.uint16)
        for i, pair in enumerate(anim_data.pairs):
            indice_values[i] = [len(pair.values), pair.offset]  # Use calculated offsets
        indice_values = indice_values.reshape(-1)
        indice_table = IntArray(indice_values, str(anim_data.indice_reference), 6, -6)

        if values_address == -1:
            anim_data.values_reference = value_table.name
        else:
            anim_data.values_reference = values_address
        return size, indice_table

    indice_tables: list[IntArray] = []
    value_tables: list[IntArray] = []

    values_name = values_name or str(anims_data[0].values_reference)
    indices_address = start_address
    if start_address != -1:
        for anim_data in anims_data:
            anim_data.indice_reference = indices_address
            indices_address += len(anim_data.pairs) * 2 * 2
    values_address = indices_address

    print("Generating compressed value table and offsets.")
    # opt: this is the max size possible, prevents tons of allocations and only about 65 kb
    value_table = IntArray(np.empty(MAX_U16, np.int16), values_name, 8)
    size = 0
    value_tables.append(value_table)
    i = 0  # we can´t use enumarate, as we may repeat
    while i < len(anims_data):
        anim_data = anims_data[i]

        size_before_add = size
        size, indice_table = add_data(value_table, size, anim_data, values_address)
        if size != -1:  # sucefully added the data to the value table
            assert indice_table is not None
            indice_tables.append(indice_table)
            i += 1  # do the next animation
        else:  # Could not add to the value table
            if size_before_add == 0:  # If the table was empty, it is simply invalid
                raise PluginError(f"Index table cannot fit into value table of 16 bit max size ({MAX_U16}).")
            else:  # try again with a fresh value table
                value_table.data.resize(size_before_add, refcheck=False)
                if start_address != -1:
                    values_address += size_before_add * 2
                value_table = IntArray(np.empty(MAX_U16, np.int16), f"{values_name}_{len(value_tables)}", 9)
                value_tables.append(value_table)
                size = 0  # reset size
                # don't increment i, redo
    value_table.data.resize(size, refcheck=False)

    return indice_tables, value_tables

from io import BufferedReader, StringIO
from typing import BinaryIO
from pathlib import Path
import dataclasses
import shutil
import struct
import os
import numpy as np

from ..utility import intToHex, decodeSegmentedAddr, PluginError, toAlnum
from .sm64_constants import insertableBinaryTypes, SegmentData
from .sm64_utility import export_rom_checks, temp_file_path


@dataclasses.dataclass
class InsertableBinaryData:
    data_type: str = ""
    data: bytearray = dataclasses.field(default_factory=bytearray)
    start_address: int = 0
    ptrs: list[int] = dataclasses.field(default_factory=list)

    def write(self, path: Path):
        path.write_bytes(self.to_binary())

    def to_binary(self):
        data = bytearray()
        data.extend(insertableBinaryTypes[self.data_type].to_bytes(4, "big"))  # 0-4
        data.extend(len(self.data).to_bytes(4, "big"))  #                        4-8
        data.extend(self.start_address.to_bytes(4, "big"))  #                    8-12
        data.extend(len(self.ptrs).to_bytes(4, "big"))  #                        12-16
        for ptr in self.ptrs:  #                                                 16-(16 + len(ptr) * 4)
            data.extend(ptr.to_bytes(4, "big"))
        data.extend(self.data)
        return data

    def read(self, file: BufferedReader, expected_type: list = None):
        print(f"Reading insertable binary data from {file.name}")
        reader = RomReader(file)
        type_num = reader.read_int(4)
        if type_num not in insertableBinaryTypes.values():
            raise ValueError(f"Unknown data type: {intToHex(type_num)}")
        self.data_type = next(k for k, v in insertableBinaryTypes.items() if v == type_num)
        if expected_type and self.data_type not in expected_type:
            raise ValueError(f"Unexpected data type: {self.data_type}")

        data_size = reader.read_int(4)
        self.start_address = reader.read_int(4)
        pointer_count = reader.read_int(4)
        self.ptrs = []
        for _ in range(pointer_count):
            self.ptrs.append(reader.read_int(4))

        actual_start = reader.address + self.start_address
        self.data = reader.read_data(data_size, actual_start)
        return self


@dataclasses.dataclass
class RomReader:
    """
    Helper class that simplifies reading data continously from a starting address.
    Can read insertable binary files, in which it can also read data from ROM if provided.
    """

    rom_file: BufferedReader = None
    insertable_file: BufferedReader = None
    start_address: int = 0
    segment_data: SegmentData = dataclasses.field(default_factory=dict)
    insertable: InsertableBinaryData = None
    address: int = dataclasses.field(init=False)

    def __post_init__(self):
        self.address = self.start_address
        if self.insertable_file and not self.insertable:
            self.insertable = InsertableBinaryData().read(self.insertable_file)
        assert self.insertable or self.rom_file

    def branch(self, start_address=-1):
        start_address = self.address if start_address == -1 else start_address
        if self.read_int(1, specific_address=start_address) is None:
            if self.insertable and self.rom_file:
                return RomReader(self.rom_file, start_address=start_address, segment_data=self.segment_data)
            return None
        return RomReader(
            self.rom_file,
            self.insertable_file,
            start_address,
            self.segment_data,
            self.insertable,
        )

    def skip(self, size: int):
        self.address += size

    def read_data(self, size=-1, specific_address=-1):
        if specific_address == -1:
            address = self.address
            self.skip(size)
        else:
            address = specific_address

        if self.insertable:
            data = self.insertable.data[address : address + size]
        else:
            self.rom_file.seek(address)
            data = self.rom_file.read(size)
        if size > 0 and not data:
            raise IndexError(f"Value at {intToHex(address)} not present in data.")
        return data

    def read_ptr(self, specific_address=-1):
        address = self.address if specific_address == -1 else specific_address
        ptr = self.read_int(4, specific_address=specific_address)
        if self.insertable and address in self.insertable.ptrs:
            return ptr
        if ptr and self.segment_data:
            return decodeSegmentedAddr(ptr.to_bytes(4, "big"), self.segment_data)
        return ptr

    def read_int(self, size=4, signed=False, specific_address=-1):
        return int.from_bytes(self.read_data(size, specific_address), "big", signed=signed)

    def read_float(self, size=4, specific_address=-1):
        return struct.unpack(">f", self.read_data(size, specific_address))[0]

    def read_str(self, specific_address=-1):
        ptr = self.read_ptr() if specific_address == -1 else specific_address
        if not ptr:
            return None
        branch = self.branch(ptr)
        text_data = bytearray()
        while True:
            byte = branch.read_data(1)
            if byte == b"\x00" or not byte:
                break
            text_data.append(ord(byte))
        text = text_data.decode("utf-8")
        return text


@dataclasses.dataclass
class BinaryExporter:
    export_rom: Path
    output_rom: Path
    rom_file_output: BinaryIO = dataclasses.field(init=False)
    temp_rom: Path = dataclasses.field(init=False)

    @property
    def tell(self):
        return self.rom_file_output.tell()

    def __enter__(self):
        export_rom_checks(self.export_rom)
        print(f"Binary export started, exporting to {self.output_rom}")
        self.temp_rom = temp_file_path(self.output_rom)
        print(f'Copying "{self.export_rom}" to temporary file "{self.temp_rom}".')
        shutil.copy(self.export_rom, self.temp_rom)
        self.rom_file_output = self.temp_rom.open("rb+")
        return self

    def write_to_range(self, start_address: int, end_address: int, data: bytes | bytearray):
        address_range_str = f"[{intToHex(start_address)}, {intToHex(end_address)}]"
        if end_address < start_address:
            raise PluginError(f"Start address is higher than the end address: {address_range_str}")
        if start_address + len(data) > end_address:
            raise PluginError(
                f"Data ({len(data) / 1000.0} kb) does not fit in range {address_range_str} "
                f"({(end_address - start_address) / 1000.0} kb).",
            )
        print(f"Writing {len(data) / 1000.0} kb to {address_range_str} ({(end_address - start_address) / 1000.0} kb))")
        self.write(data, start_address)

    def seek(self, offset: int, whence: int = 0):
        self.rom_file_output.seek(offset, whence)

    def read(self, n=-1, offset=-1):
        if offset != -1:
            self.seek(offset)
        return self.rom_file_output.read(n)

    def write(self, s: bytes, offset=-1):
        if offset != -1:
            self.seek(offset)
        return self.rom_file_output.write(s)

    def __exit__(self, exc_type, exc_value, traceback):
        if self.temp_rom.exists():
            print(f"Closing temporary file {self.temp_rom}.")
            self.rom_file_output.close()
        else:
            raise FileNotFoundError(f"Temporary file {self.temp_rom} does not exist?")
        if exc_value:
            print("Deleting temporary file because of exception.")
            os.remove(self.temp_rom)
            print("Type:", exc_type, "\nValue:", exc_value, "\nTraceback:", traceback)
        else:
            print(f"Moving temporary file to {self.output_rom}.")
            if os.path.exists(self.output_rom):
                os.remove(self.output_rom)
            self.temp_rom.rename(self.output_rom)


@dataclasses.dataclass
class DMATableElement:
    offset: int = 0
    size: int = 0
    address: int = 0
    end_address: int = 0


@dataclasses.dataclass
class DMATable:
    address_place_holder: int = 0
    entries: list[DMATableElement] = dataclasses.field(default_factory=list)
    data: bytearray = dataclasses.field(default_factory=bytearray)
    address: int = 0
    end_address: int = 0

    def to_binary(self):
        print(
            f"Generating DMA table with {len(self.entries)} entries",
            f"and {len(self.data)} bytes of data",
        )
        data = bytearray()
        data.extend(len(self.entries).to_bytes(4, "big", signed=False))
        data.extend(self.address_place_holder.to_bytes(4, "big", signed=False))

        entries_offset = 8
        entries_length = len(self.entries) * 8
        entrie_data_offset = entries_offset + entries_length

        for entrie in self.entries:
            offset = entrie_data_offset + entrie.offset
            data.extend(offset.to_bytes(4, "big", signed=False))
            data.extend(entrie.size.to_bytes(4, "big", signed=False))
        data.extend(self.data)

        return data

    def read_binary(self, reader: RomReader):
        print("Reading DMA table at", intToHex(reader.start_address))
        self.address = reader.start_address

        num_entries = reader.read_int(4)  # numEntries
        self.address_place_holder = reader.read_int(4)  # addrPlaceholder

        table_size = 0
        for _ in range(num_entries):
            offset = reader.read_int(4)
            size = reader.read_int(4)
            address = self.address + offset
            self.entries.append(DMATableElement(offset, size, address, address + size))
            end_of_entry = offset + size
            if end_of_entry > table_size:
                table_size = end_of_entry
        self.end_address = self.address + table_size
        print(f"Found {len(self.entries)} DMA entries")
        return self


@dataclasses.dataclass
class IntArray:
    data: np.ndarray
    name: str = ""
    wrap: int = 6
    wrap_start: int = 0  # -6 To replicate decomp animation index table formatting

    def to_binary(self):
        return self.data.astype(">i2").tobytes()

    def to_c(self, c_data: StringIO | None = None, new_lines=1):
        assert self.name, "Array must have a name"
        data = self.data
        byte_count = data.itemsize
        data_type = f"{'s' if data.dtype == np.int16 else 'u'}{byte_count * 8}"
        print(f'Generating {data_type} array "{self.name}" with {len(self.data)} elements')

        c_data = c_data or StringIO()
        c_data.write(f"// {len(self.data)}\n")
        c_data.write(f"static const {data_type} {toAlnum(self.name)}[] = {{\n\t")
        i = self.wrap_start
        for value in self.data:
            c_data.write(f"{intToHex(value, byte_count, False)}, ")
            i += 1
            if i >= self.wrap:
                c_data.write("\n\t")
                i = 0

        c_data.write("\n};" + ("\n" * new_lines))
        return c_data

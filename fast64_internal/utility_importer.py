from __future__ import annotations

import re, struct

import bpy
from functools import partial
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO, Any, Union
from numbers import Number
from collections.abc import Sequence

from .utility import transform_mtx_blender_to_n64


# ------------------------------------------------------------------------
#    Generic helper
# ------------------------------------------------------------------------


# eval line if not integer
def eval_or_int(val):
    if type(val) is int:
        return val
    else:
        return eval(val)


def transform_matrix_to_bpy(transform: Matrix) -> Matrix:
    return transform_mtx_blender_to_n64().inverted() @ transform @ transform_mtx_blender_to_n64()


@dataclass
class BankLoads:
    tlb: defualtdict[dict] = field(default_factory=dict)  # proper name?


g_bank_loads = BankLoads()


def get_bank_loads(reset: bool = False) -> BankLoads:
    global g_bank_loads
    if reset:
        g_bank_loads = BankLoads()
    return g_bank_loads


# ------------------------------------------------------------------------
#    Binary Classes
# ------------------------------------------------------------------------


# used to unpack data via BinProcess methods
@dataclass
class PackedFormat:
    format_str: str = ""
    ptr_indices: tuple = field(default_factory=tuple)
    optional_arg_call: callable = None  # callable used to edit format & ptrs, ran manually
    make_str: bool = True  # convert args to strings for blender prop compat
    reorder: tuple = field(
        default_factory=tuple
    )  # reorders args after unpacking, called after post_unpack ptr addressing and make_str
    bit_packing: tuple = field(
        default_factory=tuple
    )  # use a packed bitfield to unpack, each item is num bits, unpacked sequentially, make format all bytes
    post_unpack: callable = None  # called after unpacking, used for doing math to args, useful for f3d
    # it may instead be more convenient to just change the macro name to <macro>BIN for specific processing
    # usually in the case where a binary cmd can be one of several equivalent C macros the pre processor simplifies

    @property
    def format_size(self):
        return struct.calcsize(self.format_str)

    # add optional formatting
    def edit_format(self, *args):
        if not self.optional_arg_call:
            return
        self.format_str = self.optional_arg_call(self.format_str, *args)
        self.ptr_indices = self.optional_arg_call(self.ptr_indices, *args)

    def unpack(self, bin_data: BinaryIO):
        args = list(struct.unpack(self.format_str, bin_data))
        if self.bit_packing:
            args = self.unpack_bits(args)
        if self.post_unpack:
            args = self.post_unpack(args)
        return args

    # format_str must be list of unsigned bytes
    def unpack_bits(self, args: list):
        # combined bytes into one bit chunk of data
        dat = 0
        for shift, byte in enumerate(reversed(args)):
            dat += byte << (shift * 8)
        # unpack in reverse order using bitmask, then shifting data
        args = []
        for bit_field in reversed(self.bit_packing):
            args.append(dat & ((1 << bit_field) - 1))
            dat = dat >> bit_field
        return args[::-1]

    def reorder_args(self, args: list) -> list:
        if self.reorder:
            return [args[index] for index in self.reorder]
        else:
            return args

    def make_args_str(self, args: list) -> list:
        if self.make_str:
            return [str(args[index]) if index not in self.ptr_indices else args[index] for index in range(len(args))]
        else:
            return args


class BinProcess:
    """
    A base class that holds some binary processing functions
    this class is focused on reading data
    """

    # a bit messy, default to str to match C except for ptrs which will always have math ops
    def unpack_type(
        self,
        bin_file: BinaryIO,
        offset: int,
        unpack_str: Union[PackedFormat, str],
        ret_iterable=False,
        make_str: bool = True,
    ):
        if type(unpack_str) is str:
            unpack_str = PackedFormat(unpack_str, make_str=make_str)

        args = unpack_str.unpack(bin_file[offset : offset + unpack_str.format_size])
        args = unpack_str.make_args_str(args)
        for index in unpack_str.ptr_indices:
            args[index] = self.seg2phys(args[index])
        args = unpack_str.reorder_args(args)

        if ret_iterable:
            return args
        if len(args) == 1:
            return args[0]
        else:
            return args

    def seg2phys(self, ptr: int):
        if (seg_num := ptr >> 24) != 0:
            segment = self.banks.tlb[seg_num][0]
            return segment + (ptr & 0xFFFFFF)
        else:
            return ptr

    # get list of pointers, stop at ARR_TERMINATOR
    def get_referece_list(self, start, stop=0):
        x = 0
        start = self.seg2phys(start)
        ref = []
        r = self.unpack_type(start, ">L", 4)
        while r != stop:
            x += 4
            ref.append(r)
            r = self.unpack_type(start + x, ">L", 4)
        ref.append(r)
        return ref

    # using a list of labels, find which symbol corresponds to pointer
    def get_symbol_from_locations(self, symbol_dict, pointer, size=8):
        # throw out non pointers
        if pointer == 0:
            return 0
        closest = None
        chosen_str = None
        for format_str, symbols in symbol_dict.items():
            for sym in symbols:
                if not closest:
                    closest = sym if sym < pointer else None
                    chosen_str = format_str
                    continue
                if sym > pointer:
                    continue
                if (pointer - sym) < (pointer - closest):
                    closest = sym
                    chosen_str = format_str
        if not closest:
            closest = min([sym for sym in symbols for symbols in symbol_dict.values()])
        return chosen_str.format(f"{closest:X}", f"[{(pointer - closest) // size}]")

    # turn dict into an array. usually to be fed into a named tuple
    # dict is: key - offset, value - func->type, name, func->len, arr = None
    # returns: list[ints]
    def extract_dict(self, start, dict):
        output = []
        for k, v in dict.items():
            try:
                # if a function is used for member 4, then call with current results
                if callable(v[3]):
                    # variable length structs are always at the end, and should be arrays
                    # since unpack_type sometimes is not a list and sometimes is, I will
                    # force this result to be a list
                    num = v[3](output)
                    output.append(self.unpack_type(start + k, v[0].format(num), v[2] * num, iter=True))
                else:
                    output.append(self.unpack_type(start + k, v[0], v[2]))
            except:
                output.append(self.unpack_type(start + k, v[0], v[2]))
        return output


# ------------------------------------------------------------------------
#    Array Data parsing
# ------------------------------------------------------------------------


@dataclass
class CDataArray:
    """
    Used as an iterable but also contains the name and var type if called upon
    Generally useful for types that have aliases but functionally act the same
    like Light1 vs Light_t
    """

    var_type: str
    var_name: str
    var_data: any = None

    def __iter__(self):
        for item in self.var_data:
            yield item

    def __len__(self):
        return len(self.var_data)

    def __getitem__(self, index):
        return self.var_data[index]

    def __setitem__(self, index, val):
        self.var_data[index] = val


@dataclass
class Macro:
    cmd: str
    args: list[str, int]

    # strip each arg
    def __post_init__(self):
        self.args = [arg.strip() if type(arg) is str else arg for arg in self.args]
        self.cmd = self.cmd.strip()

    # make new macro that is the indices chosen or supplied args
    def partial(self, *new_args: Any):
        return Macro(self.cmd, (arg for arg in new_args))


@dataclass
class Parser:
    cur_stream: Sequence[Any]
    head: int = -1

    def stream(self):
        while self.head < len(self.cur_stream) - 1:
            self.head += 1
            yield self.cur_stream[self.head]

    def advance_head(self, adv):
        self.head += adv


class ParseException(Exception):
    pass


# basic methods and utility to parse scripts or data streams of bytecode
class DataParser(BinProcess):
    # parsing flow status codes
    _continue_parse = 1
    _break_parse = 2
    _exit_parse = 3  # fully stop script
    _binary_parsing = 0
    _c_parsing = 1

    def __init__(self, parent: DataParser = None, parse_target=None):
        # for forward referencing scripts, keep track of the stream
        if parent:
            self.bin_file = parent.bin_file
            self.parsing_target = parent.parsing_target
            self.parsed_streams = parent.parsed_streams
        else:
            self.bin_file = None
            self.parsing_target = parse_target
            self.parsed_streams = dict()

    def reset_parser(self, entry_id: Any):
        self.parsed_streams[entry_id] = None

    def get_parser(self, entry_id: Any, relative_offset: int = 0) -> Parser:
        parser = self.parsed_streams[entry_id]
        parser.head += relative_offset
        return parser

    # for if you're jumping, you start from the beginning, but if you're starting/stopping
    # then you want to just pickup from the last spot
    def parse_stream_from_start(self, dat_stream: Sequence[Any], entry_id: Any, *args, **kwargs):
        self.reset_parser(entry_id)
        self.parse_stream(dat_stream, entry_id, *args, **kwargs)

    def parse_stream(self, dat_stream: Sequence[Any], entry_id: Any, *args, **kwargs):
        if self.parsing_target == self._c_parsing:
            self.parse_stream_c(dat_stream, entry_id, *args, **kwargs)
        elif self.parsing_target == self._binary_parsing:
            # assuming parsing of one single rom
            self.parse_stream_binary(self.bin_file, entry_id, *args, **kwargs)
        else:
            raise Exception("Unhandled parsing type detected")

    def parse_stream_c(self, dat_stream: Sequence[Any], entry_id: Any, *args, **kwargs):
        """
        C parsing works in the following order:
            * parse C files and collect data into dictionaries[var_name, CDataArray], set to class specific attrs
            * set class.parse_target to DataParser._c_parsing, this is the defualt
            * run parse_stream_from_start(script_stream, entry, *args) w/ script_stream = CDataArray, entry = var_name: str
            * c_macro_split(pre parsed line of C code) -> Macro, assumes MACRO(macro_args) format
            * Macro function is ran, e.g. EXECUTE or gsSPDisplayList
            * jumps enter new recursion depth of parser, rom is supplied using attr self.bin_file
            * repeat until _break_parse, use ParseException to fully exit recursion
        """
        parser = self.parsed_streams.get(entry_id)
        if not parser:
            self.parsed_streams[entry_id] = (parser := Parser(dat_stream))
        for line in parser.stream():
            cur_macro = self.c_macro_split(line)
            if cur_macro.cmd in self._skippable_cmds:
                continue
            func = getattr(self, cur_macro.cmd, None)
            if not func:
                raise Exception(f"Macro {cur_macro} not found in parser function")
            else:
                flow_status = func(cur_macro, *args, **kwargs)
            if flow_status == self._break_parse:
                return

    # entry id in this instance is a pointer, converted to physical address, e.g. file offset
    def parse_stream_binary(self, bin_file: BinaryIO, entry_id: Any, *args, **kwargs):
        """
        Binary parsing works in the following order:
            * set class.parse_target to DataParser._binary_parsing, cls.banks to tlb mapping and class.bin_file to rom
            * run parse_stream_from_start(dat_stream, entry, *args) w/ dat_stream = None, entry = rom_ptr: int
            * binary_cmd_unpack/f"_decode_cmd_{cmd_name.lower()}_bin"(parser, PackedFormat) -> cmd_args
            * cmd specific func or binary_cmd_unpack unpacks cmd using stream and PackedFormat -> cmd_args
            * parser head is advanced the length of PackedFormat! Make sure all bytes are read, even padding
            * Macro function is ran as if were C, e.g. EXECUTE or gsSPDisplayList
            * jumps enter new recursion depth of parser, rom is supplied using attr self.bin_file
            * repeat until _break_parse, use ParseException to fully exit recursion
        """
        parser = self.parsed_streams.get(entry_id)
        if not parser:
            self.parsed_streams[entry_id] = (parser := Parser(bin_file))
            parser.head = entry_id
        flow_status = self._continue_parse
        while flow_status == self._continue_parse:
            cmd_name, packed_fmt = self.binary_cmd_get(parser)  # adv head if MSB not included in packed format
            arg_decode_func = getattr(self, f"_decode_cmd_{cmd_name.lower()}_bin", None)
            if arg_decode_func:
                cmd_name, cmd_args, cmd_len = arg_decode_func(packed_fmt, parser)
            else:
                cmd_args, cmd_len = self.binary_cmd_unpack(parser, cmd_name, packed_fmt)
            parser.advance_head(cmd_len)
            if cmd_name in self._skippable_cmds:
                continue
            cur_macro = Macro(cmd_name, cmd_args)
            func = getattr(self, cur_macro.cmd, None)
            print(cur_macro)
            if not func:
                raise Exception(f"Macro {cur_macro} not found in parser function")
            flow_status = func(cur_macro, *args, **kwargs)
            if flow_status == self._break_parse:
                return
            if flow_status == self._exit_parse:
                raise ParseException(f"Parsing stopped")

    def get_cmd_name(cmd_type: int):
        raise Exception("You must call this from subclass")

    def binary_cmd_unpack(
        self, parser: Parser, cmd_name: str, packed_fmt: PackedFormat
    ) -> tuple[cmd_args, cmd_len:int]:
        # no cmd data
        if not packed_fmt.format_str:
            cmd_args = []
        else:
            cmd_args = self.unpack_type(parser.cur_stream, parser.head, packed_fmt, ret_iterable=True)
        return cmd_args, packed_fmt.format_size

    def binary_cmd_get(self, parser: Parser) -> tuple[cmd_name:str, PackedFormat]:
        raise Exception("You must call this from a sublcass")

    def c_macro_split(self, macro: str) -> list[str]:
        args_start = macro.find("(")
        # have to deal with nested macros, such as with calc_dxt() in f3d
        # maybe there is a way to oneline with regex?
        str_macro = macro[args_start + 1 : macro.rfind(")")] + ","
        nested_paren_regex = "\w*\(([^\)]+)\),"
        arg_regex = "[\w\s*()-]+"
        nested_args = [*re.finditer(nested_paren_regex, str_macro)]
        if not nested_args:
            macro_args = macro[args_start + 1 : macro.rfind(")")].split(",")
        else:
            # check if found arg overlaps with a nested one, if so throw it out
            max_pos = -1
            macro_args = []
            for arg in re.finditer(arg_regex, str_macro):
                if nested_args:
                    if arg.span()[0] > nested_args[0].span()[0] or arg.span()[1] > nested_args[0].span()[0]:
                        max_pos = nested_args[0].span()[1]
                        macro_args.append(nested_args[0].group())
                        nested_args.pop(0)
                        continue
                if arg.span()[0] > max_pos:
                    macro_args.append(arg.group())
        return Macro(macro[:args_start], macro_args)


# ------------------------------------------------------------------------
#    C file scrubbing/processing
# ------------------------------------------------------------------------


# make something more generic here where user can supply their own function
def evaluate_macro(line: str):
    props = bpy.context.scene.fast64.sm64.importer
    if props.version in line:
        return False
    if props.target in line:
        return False
    return True


# gets rid of comments, whitespace and macros in a file
def pre_parse_file(file: TextIO) -> list[str]:
    multi_line_comment_regx = "/\*[^*]*\*+(?:[^/*][^*]*\*+)*/"
    file = re.sub(multi_line_comment_regx, "", file.read())
    skip_macro = 0  # bool to skip during macros
    output_lines = []
    for line in file.splitlines():
        # remove line comment
        if (comment := line.rfind("//")) > -1:
            line = line[:comment]
        # check for macro
        if "#if" in line:
            skip_macro = evaluate_macro(line)
        if "#ifdef" in line:
            skip_macro = evaluate_macro(line)
            continue
        if "#elif" in line:
            skip_macro = evaluate_macro(line)
            continue
        if "#else" in line or "#endif" in line:
            skip_macro = 0
            continue
        if not skip_macro and line:
            output_lines.append(line)
    return output_lines


# given an aggregate file that imports many files, find files with the name of type <filename>
def parse_aggregate_file(
    agg_file: TextIO, file_catches: tuple[callable], root_path: Path, aggregate_path: Path
) -> list[Path]:
    agg_file.seek(0)  # so it may be read multiple times

    file_lines = pre_parse_file(agg_file)
    # remove include and quotes
    remove = {"#include", '"', "'"}
    caught_files = []
    for line in file_lines:
        # if not line:
        # continue
        for r in remove:
            line = line.replace(r, "")
        line = Path(line.strip())
        for callable in file_catches:
            if callable(line):
                caught_files.append(line)
                break

    # include is relative cur aggregate file or root
    def get_file_path(root_path: Path, include: str):
        if (include_file := root_path / include).exists():
            return include_file
        if (include_file := aggregate_path.parent / include).exists():
            return include_file
        raise Exception(f"could not find inclusion file {include}")

    if caught_files:
        return [get_file_path(root_path, include) for include in caught_files]
    else:
        return []


# Search through a C file to find data of typeName[] and split it into a list
# of data types with all comments removed
def get_data_types_from_file(file: TextIO, type_dict, collated=False):
    # from a raw file, create a dict of types. Types should all be arrays
    file_lines = pre_parse_file(file)
    array_bounds_regx = "\[[0-9a-fx]*\]"  # basically [] with any valid number in it
    equality_regx = "\s*="  # finds the first char before the equals sign
    output_variables = {type_name: dict() for type_name in type_dict.keys()}
    type_found = None
    var_dat_buffer = []
    for line in file_lines:
        if type_found is not None:
            # Check for end of array
            if ";" in line:
                output_variables[type_found.var_type][type_found.var_name] = CDataArray(
                    type_found.var_type, type_found.var_name, "".join(var_dat_buffer)
                )
                type_found = None
                var_dat_buffer = []
            else:
                var_dat_buffer.append(line)
            continue
        # name ends at the array bounds, or the equals sign
        match = re.search(array_bounds_regx, line, flags=re.IGNORECASE)
        if not match:
            match = re.search(equality_regx, line, flags=re.IGNORECASE)
        type_collisions = [type_name for type_name in type_dict.keys() if type_name in line]
        if match and type_collisions:
            # there should ideally only be one collision
            type_name = type_collisions[0]
            # type_name plus any extra chars(non greedy) until a space
            name_start = re.search(f"{type_name}.*?\s", line, flags=re.IGNORECASE).span()[1]
            variable_name = line[name_start : match.span()[0]].strip()
            type_found = CDataArray(type_name, variable_name)
    # Now remove newlines from each line, and then split macro ends
    # This makes each member of the array a single macro or array
    for data_type, delimiters in type_dict.items():
        for variable_name, data_array in output_variables[data_type].items():
            data_array.var_data = format_data_arr(data_array.var_data, delimiters)
            output_variables[data_type][variable_name] = data_array

    # if collated, organize by data type, otherwise just take the various dicts raw
    return (
        output_variables
        if collated
        else {vd_key: vd_value for var_dict in output_variables.values() for vd_key, vd_value in var_dict.items()}
    )


# takes a raw string representing data and then formats it into an array
def format_data_arr(raw_data: str, delimiters: tuple[str]) -> list[str]:
    raw_data = raw_data.replace("\n", "")
    arr = []  # arr of data in format
    buf = ""  # buf to put currently processed data in
    pos = 0  # cur position in str
    stack = 0  # stack cnt of parenthesis
    app = 0  # flag to append data
    while pos < len(raw_data):
        char = raw_data[pos]
        if char == delimiters[0]:
            stack += 1
            app = 1
        if char == delimiters[1]:
            stack -= 1
        if app == 1 and stack == 0:
            app = 0
            buf += raw_data[pos : pos + 2]  # get the last parenthesis and comma
            arr.append(buf.strip())
            pos += 2
            buf = ""
            continue
        buf += char
        pos += 1
    # for when the delim characters are nothing
    if buf:
        arr.append(buf)
    return arr

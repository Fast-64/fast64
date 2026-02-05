from __future__ import annotations

import re

import bpy
from functools import partial
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO, Any, Union
from numbers import Number
from collections.abc import Sequence

from .utility import transform_mtx_blender_to_n64

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
    args: list[str]

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

    def stream_binary(self):
        pass

    def update_head(self, adv):
        self.head += adv


# basic methods and utility to parse scripts or data streams of bytecode
class DataParser(BinProcess):
    # parsing flow status codes
    _continue_parse = 1
    _break_parse = 2

    def __init__(self, parent: DataParser = None):
        # for forward referencing scripts, keep track of the stream
        if parent:
            self.parsed_streams = parent.parsed_streams
        else:
            self.parsed_streams = dict()

    # for if you're jumping, you start from the beginning, but if you're starting/stopping
    # then you want to just pickup from the last spot
    def parse_stream_from_start(self, dat_stream: Sequence[Any], entry_id: Any, *args, **kwargs):
        self.reset_parser(entry_id)
        self.parse_stream(dat_stream, entry_id, *args, **kwargs)

    def parse_stream(self, dat_stream: Sequence[Any], entry_id: Any, *args, **kwargs):
        parser = self.parsed_streams.get(entry_id)
        if not parser:
            self.parsed_streams[entry_id] = (parser := Parser(dat_stream))
        for line in parser.stream():
            cur_macro = self.c_macro_split(line)
            func = getattr(self, cur_macro.cmd, None)
            if not func:
                raise Exception(f"Macro {cur_macro} not found in parser function")
            else:
                flow_status = func(cur_macro, *args, **kwargs)
            if flow_status == self._break_parse:
                return

    # entry id in this instance is a pointer, converted to physical address, e.g. file offset
    def parse_stream_binary(self, bin_file: BinaryIO, entry_id: Any, *args, **kwargs):
        parser = self.parsed_streams.get(entry_id)
        if not parser:
            self.parsed_streams[entry_id] = (parser := Parser(bin_file))
        for line in parser.stream_binary():
            cmd_type, cmd_len = self.binary_cmd_get(parser)
            # get a specific decoding function to make a macro
            func = getattr(self, f"decode_cmd_{cmd_type}_bin", None)
            # use a generic class (const?) var tuple to decode into a macro
            if func:
                cur_macro = func(parser)
            else:
                unpack_str = getattr(self, f"unpack_cmd_{cmd_type}_bin", None)
                # if still no func
                if not unpack_str:
                    raise Exception(f"No decoding for cmd {cmd_type}")
                cur_macro = self.unpack_type(parser.cur_stream, parser.head, *unpack_str)
            else:
                flow_status = func(cur_macro, *args, **kwargs)
            parser.update_head(cmd_len)
            if flow_status == self._break_parse:
                return

    def reset_parser(self, entry_id: Any):
        self.parsed_streams[entry_id] = None

    def get_parser(self, entry_id: Any, relative_offset: int = 0) -> Parser:
        parser = self.parsed_streams[entry_id]
        parser.head += relative_offset
        return parser

    # MSB is cmd type, use cmd type to execute class specific logic for length
    # default is 2nd MSB is length, used in level scripts and geo layouts
    def binary_cmd_get(self, parser: Parser) -> tuple[int, int]:
        cmd_type, cmd_len = self.unpack_type(parser.cur_stream, parser.head, ">BB", 2)
        func = getattr(self, f"cmd_len_{cmd_type}_bin", None)
        if func:
            cmd_len = func(bin_file, offset, cmd_type)
        return cmd_type, cmd_len

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


def transform_matrix_to_bpy(transform: Matrix) -> Matrix:
    return transform_mtx_blender_to_n64().inverted() @ transform @ transform_mtx_blender_to_n64()


# ------------------------------------------------------------------------
#    Binary Classes
# ------------------------------------------------------------------------


# just a base class that holds some binary processing
# this class is focused on reading data
class BinProcess:
    # unpack type
    def unpack_type(self, file, offset, type, length, iter=False):
        a = struct.unpack(type, file[offset : offset + length])
        if iter:
            return a
        if len(a) == 1:
            return a[0]
        else:
            return a

    @staticmethod
    def seg2phys(num):
        if num >> 24 == 4:
            return num & 0xFFFFFF
        else:
            return num

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
            variable_name = line[line.find(type_name) + len(type_name) : match.span()[0]].strip()
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

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


@dataclass
class Macro:
    cmd: str
    args: list[str]

    # strip each arg
    def __post_init__(self):
        self.args = [arg.strip() for arg in self.args]
        self.cmd = self.cmd.strip()


@dataclass
class Parser:
    cur_stream: Sequence[Any]
    head: int = -1

    def stream(self):
        while self.head < len(self.cur_stream) - 1:
            self.head += 1
            yield self.cur_stream[self.head]


# basic methods and utility to parse scripts or data streams of bytecode
class DataParser:

    # parsing flow status codes
    continue_parse = 1
    break_parse = 2

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
            if flow_status == self.break_parse:
                return

    def reset_parser(self, entry_id: Any):
        self.parsed_streams[entry_id] = None

    def get_parser(self, entry_id: Any, relative_offset: int = 0):
        parser = self.parsed_streams[entry_id]
        parser.head += relative_offset
        return parser

    def c_macro_split(self, macro: str) -> list[str]:
        args_start = macro.find("(")
        return Macro(macro[:args_start], macro[args_start + 1 : macro.rfind(")")].split(","))


def transform_matrix_to_bpy(transform: Matrix) -> Matrix:
    return transform_mtx_blender_to_n64().inverted() @ transform @ transform_mtx_blender_to_n64()


def evaluate_macro(line: str):
    scene = bpy.context.scene
    if scene.level_import.version in line:
        return False
    if scene.level_import.target in line:
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
        if (comment := line.rfind("//")) > 0:
            line = line[:comment]
        # check for macro
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
def parse_aggregate_file(dat: TextIO, filenames: Union[str, tuple[str]], root_path: Path) -> list[Path]:
    dat.seek(0)  # so it may be read multiple times
    # make it an iterator even if it isn't on call
    if isinstance(filenames, str):
        filenames = (filenames,)
    file_lines = pre_parse_file(dat)
    # remove include and quotes inefficiently from lines with the filenames we are searching for
    file_lines = [
        c.replace("#include ", "").replace('"', "").replace("'", "")
        for c in file_lines
        if any(filename in c for filename in filenames)
    ]
    # deal with duplicate pathing (such as /actors/actors etc.)
    Extra = root_path.relative_to(Path(bpy.path.abspath(bpy.context.scene.decompPath)))
    for e in Extra.parts:
        files = [c.replace(e + "/", "") for c in file_lines]
    if file_lines:
        return [root_path / c for c in file_lines]
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
        if type_found:
            # Check for end of array
            if ";" in line:
                output_variables[type_found[0]][type_found[1]] = "".join(var_dat_buffer)
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
            type_found = (type_name, variable_name)
    # Now remove newlines from each line, and then split macro ends
    # This makes each member of the array a single macro or array
    for data_type, delimiters in type_dict.items():
        for variable, data in output_variables[data_type].items():
            output_variables[data_type][variable] = format_data_arr(data, delimiters)

    # if collated, organize by data type, otherwise just take the various dicts raw
    return (
        output_variables
        if collated
        else {vd_key: vd_value for var_dict in output_variables.values() for vd_key, vd_value in var_dict.items()}
    )


# takes a raw string representing data and then formats it into an array
def format_data_arr(raw_data: str, delimiters: tuple[str]):
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

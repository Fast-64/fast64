# TODO
# current temporary binary/data array image IO tool
# remove print logging

import struct
import math
import zlib
import re
from functools import lru_cache

# ------------------------------------------------------------------------
#    helper funcs
# ------------------------------------------------------------------------


# convert data to 8 bit int
@lru_cache(maxsize=255)
def CB_int(val, bits):
    return int(((val * 255) + (2 ** (bits - 1)) - 1) / (2 ** (bits) - 1))


def CB_float(val, bits):
    return val / (2**bits - 1)


# one bit alpha
def OBA(val):
    if val:
        return 255
    else:
        return 0


# unpacks individual bits
# format is csv, num_bits in each param, max is 8
def unpack_bits(format_str: str, byte_stream: bytes, offset: int, length: int):
    data_out = []
    byte_data = int.from_bytes(byte_stream[offset : offset + length], "big")
    byte_mask = (1 << (length * 8)) - 1
    # convert length to number of bits in byte data
    length = length * 8
    for unpack_str in format_str.split(","):
        unpack_str = int(unpack_str.strip())
        dat_mask = ((1 << unpack_str) - 1) << (8 - unpack_str + length - 8)
        # print("byte_data: 0x{:X} data mask: 0x{:X} append: 0x{:X}".format(byte_data, dat_mask, (byte_data & dat_mask) >> (8 - unpack_str + length - 8)))
        data_out.append((byte_data & dat_mask) >> (8 - unpack_str + length - 8))
        length = length - unpack_str
    return data_out


# written for RGBA16 palette
def get_palette(byte_stream: bytes, im_siz: int):
    shifts = [5, 5, 5, 1]
    pal_out = []
    for tx in range(2**im_siz):
        a = unpack_bits("5, 5, 5, 1", byte_stream, tx * 2, 2)
        pal_out.append((*(CB_float(c, s) if s > 1 else OBA(c) / 255 for c, s in zip(a, shifts)),))
    return pal_out


# ------------------------------------------------------------------------
#    image funcs
# ------------------------------------------------------------------------


# byte_stream is bin, image is png
# Alpha changed to true because N64 graphics does not like PNGS with no alpha YES!!!
def convert_I_tex(width: int, height: int, im_siz: int, byte_stream: bytes, pal_stream: bytes = None):
    if im_siz == 8:
        rows = convert_byte_stream(byte_stream, width, height, [8], 1, 1, add_alpha=True)
    else:
        rows = convert_byte_stream(byte_stream, width, height, [4, 4], 2, 1, add_alpha=True)
    return rows


def convert_IA_tex(width: int, height: int, im_siz: int, byte_stream: bytes, pal_stream: bytes = None):
    if im_siz == 16:
        rows = convert_byte_stream(byte_stream, width, height, [8, 8], 1, 2)
    if im_siz == 8:
        rows = convert_byte_stream(byte_stream, width, height, [4, 4], 1, 1)
    else:
        rows = convert_byte_stream(byte_stream, width, height, [3, 1, 3, 1], 2, 1)
    return rows


def convert_RGBA_tex(width: int, height: int, im_siz: int, byte_stream: bytes, pal_stream: bytes = None):
    if im_siz == 16:
        rows = convert_byte_stream(byte_stream, width, height, [5, 5, 5, 1], 1, 2)
    else:
        rows = convert_byte_stream(byte_stream, width, height, [8, 8, 8, 8], 1, 4)
    return rows


def convert_CI_tex(width: int, height: int, im_siz: int, byte_stream: bytes, pal_stream: bytes = None):
    p = get_palette(pal_stream, im_siz)
    if im_siz == 4:
        rows = convert_byte_stream(byte_stream, width, height, [4, 4], 2, 1, is_ci=True)
    else:
        rows = convert_byte_stream(byte_stream, width, height, [8], 1, 1, is_ci=True)
    out_rows = []
    for tx in rows:
        out_rows.extend(p[tx])
    return out_rows


# change IA31 to IA88 or rgba5551 to rgba8888 as needed
def convert_byte_stream(
    byte_stream: bytes,
    width: int,
    height: int,
    channel_bits: list,
    tx_per_byte: int,
    byte_per_tx: int,
    add_alpha=False,
    is_ci=False,
):
    data_out = []
    for im_row in range(height):
        # you can only iterate min one byte at a time
        # so tx_per_byte halves iteration steps for im_siz==4 textures
        for tx in range(0, width // tx_per_byte):
            tx = tx + (im_row * width // tx_per_byte)
            channels = unpack_bits(",".join([str(a) for a in channel_bits]), byte_stream, byte_per_tx * tx, byte_per_tx)
            if add_alpha:
                channels.append(0xFF)
            if is_ci:
                data_out.extend(channels)
                continue
            for c, s in zip(channels, channel_bits):
                if s == 1:
                    data_out.append(OBA(c) / 255)
                if s < 8:
                    data_out.append(CB_float(c, s))
                else:
                    data_out.append(c)
    return data_out


def convert_tex(fmt: str, width: int, height: int, im_siz: int, byte_stream: bytes, pal_stream: bytes = None):
    # I dislike this formulation but calling globals() is worse
    funcs = {
        "G_IM_FMT_CI": convert_CI_tex,
        "G_IM_FMT_I": convert_I_tex,
        "G_IM_FMT_IA": convert_IA_tex,
        "G_IM_FMT_RGBA": convert_RGBA_tex,
    }
    byte_stream = bytes([int(a.strip(), 0x10) for a in byte_stream.split(",") if "0x" in a])
    if pal_stream:
        pal_stream = bytes([int(a.strip(), 0x10) for a in pal_stream.split(",") if "0x" in a])
    im_siz = int(re.search("\d+", im_siz).group())
    return funcs.get(fmt)(int(width), int(height), im_siz, byte_stream, pal_stream)


if __name__ == "__main__":
    textures = dict()
    # with open("tmp_tex_examples.c", "r", newline="") as c_file:
    #     # For textures, try u8, and s16 aswell
    #     textures.update(
    #         get_data_types_from_file(
    #             c_file,
    #             {
    #                 "Texture": [None, None],
    #                 "u8": [None, None],
    #                 "s16": [None, None],
    #             },
    #         )
    #     )
    # print(list(textures.keys()))
    # pal = textures["jrb_dl_E050_O021_CI_ci4_pal_rgba16"]
    # tex = textures["jrb_dl_E050_O021_CI_ci4"]
    # pal_stream = bytes([int(a.strip(), 0x10) for a in pal.var_data[0].split(",") if "0x" in a])
    # tex_stream = bytes([int(a.strip(), 0x10) for a in tex.var_data[0].split(",") if "0x" in a])
    # im = convert_tex("CI", 4, 4, 4, pal_stream, tex_stream)
    # print(im)

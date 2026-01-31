# TODO
# current temporary binary/data array image IO tool
# remove bitstring dep

import struct

# import png
import math

# from bitstring import *

# convert bin to png


def MakeImage(name):
    return open(name + ".png", "wb")


# file is bin, image is png
# Alpha changed to true because N64 graphics does not like PNGS with no alpha YES!!!
def I(width, height, depth, file, image):
    if depth > 4:
        w = png.Writer(width, height, greyscale=True, bitdepth=depth, alpha=True)
        rows = CreateIRows(width, height, depth // 2, 1, file)
    else:
        w = png.Writer(width, height, greyscale=True, bitdepth=8, alpha=True)
        rows = EditIFile(file, width, height, [4, 4], 2, 1)
    w.write(image, rows)


def IA(width, height, depth, file, image):
    if depth > 4:
        w = png.Writer(width, height, greyscale=True, bitdepth=depth // 2, alpha=True)
        rows = CreateRows(width, height, depth // 2, 2, file)
    else:
        w = png.Writer(width, height, greyscale=True, bitdepth=8, alpha=True)
        rows = EditFile(file, width, height, [5, 8, 5, 8], 2, 1)
    w.write(image, rows)


def RGBA(width, height, depth, file, image):
    if depth == 16:
        RGBA16(width, height, file, image)
    else:
        RGBA32(width, height, file, image)


def RGBA32(width, height, file, image):
    w = png.Writer(width, height, greyscale=False, bitdepth=8, alpha=True)
    rows = CreateRows(width, height, 8, 4, file)
    w.write(image, rows)


def RGBA16(width, height, file, image):
    w = png.Writer(width, height, greyscale=False, bitdepth=8, alpha=True)
    rows = EditFile(file, width, height, [3, 3, 3, 8], 1, 2)
    w.write(image, rows)


def CI(width, height, depth, p, file, image):
    p = GetPalette(p, depth, 2)
    w = png.Writer(width, height, palette=p, bitdepth=depth)
    rows = CreateRows(width, height, depth, 1, file)
    w.write(image, rows)


def CreateIRows(width, height, depth, Channels, file):
    rows = []
    for r in range(height):
        L = int((depth / 8) * Channels * width)  # bytes per row
        bin = BitArray(file[L * r : L * r + L])
        a = bin.unpack("%d*uint:%d" % (width * Channels, depth))
        a = [b & 0xFF for b in a]
        AlphaAdd = [0xFF] * (len(a) * 2)
        AlphaAdd[0::2] = a
        rows.append(AlphaAdd)
    return rows


def CreateRows(width, height, depth, Channels, file):
    rows = []
    for r in range(height):
        L = int((depth / 8) * Channels * width)  # bytes per row
        bin = BitArray(file[L * r : L * r + L])
        a = bin.unpack("%d*uint:%d" % (width * Channels, depth))
        a = [b & 0xFF for b in a]
        rows.append(a)
    return rows


# change I4 to IA88
def EditIFile(file, width, height, shifts, PpB, b):
    newfile = []
    for x in range(height):
        row = []
        for pixel in range(0, width // PpB):
            pixel = pixel + x * width // PpB
            bin = file[b * pixel : b * pixel + b]
            bin = pack(">%dB" % b, *bin)
            upack = ["uint:%d" % (8 - a) if a != 8 else "uint:1" for a in shifts]
            channels = bin.unpack(",".join(upack))
            channels = [CB(c, 8 - s) if s < 8 else OBA(c) for c, s in zip(channels, shifts)]
            AlphaAdd = [0xFF] * (len(channels) * 2)
            AlphaAdd[0::2] = channels
            p = struct.pack(">%dB" % len(AlphaAdd), *AlphaAdd)
            row.extend(p)
        newfile.append(row)
    return newfile


# change IA31 to IA88 or rgba5551 to rgba8888
def EditFile(file, width, height, shifts, PpB, b):
    newfile = []
    for x in range(height):
        row = []
        for pixel in range(0, width // PpB):
            pixel = pixel + x * width // PpB
            bin = file[b * pixel : b * pixel + b]
            bin = pack(">%dB" % b, *bin)
            upack = ["uint:%d" % (8 - a) if a != 8 else "uint:1" for a in shifts]
            channels = bin.unpack(",".join(upack))
            channels = [CB(c, 8 - s) if s < 8 else OBA(c) for c, s in zip(channels, shifts)]
            p = struct.pack(">%dB" % len(channels), *channels)
            row.extend(p)
        newfile.append(row)
    return newfile


# convert bits
def CB(val, bits):
    return int(((val * 255) + (2 ** (bits - 1)) - 1) / (2 ** (bits) - 1))


# one bit alpha
def OBA(val):
    if val:
        return 255
    else:
        return 0


# Palette is [Binary Region,format],every palette uses either IA16 or RGBA16
def GetPalette(palette, depth, bpp):
    bin = palette[0]
    # pad bin for the times when only partial palettes are used
    if len(bin) < ((2**depth) * 2):
        bin += bytes(((2**depth) * 2) - len(bin))
    shifts = [3, 3, 3, 8]
    o = []
    for p in range(2**depth):
        b = BitArray(bin[p * 2 : p * 2 + 2])
        a = b.unpack("3*uint:5,uint:1")
        a = [CB(c, 8 - s) if s < 8 else OBA(c) for c, s in zip(a, shifts)]
        o.append(tuple(a))
    return o


def MakeRGBA(file, Bpp, Alpha):
    r = png.Reader(file)
    re = r.read()
    depth = re[3]["bitdepth"]
    channels = re[3]["planes"]
    if channels == 3:
        shifts = [3, 3, 3]
    else:
        shifts = [3, 3, 3, 7]
    if depth == 8 and Bpp == 16:
        # two bytes per pixel, need to convert to rgba5551
        rows = []
        for r in re[2]:
            for W in range(0, len(r), channels):
                b = r[W : W + channels]
                a = [c >> s for c, s in zip(b, shifts)]
                if len(shifts) == 3:
                    a.append(1)
                b = pack("3*uint:5,uint:1", *a)
                rows.append(b.bytes)
        return rows
    else:
        if channels == 3:
            solid = bytes([0xFF])
        else:
            solid = bytes()
        bin = []
        for r in re[2]:
            for W in range(0, len(r), channels):
                bin.append(r[W : W + channels] + solid)
        return bin


def MakeCI(file, Bpp, Alpha):
    r = png.Reader(file)
    re = r.read()
    Pal = re[3]["palette"]
    Pbin = []
    shifts = [3, 3, 3, 7]
    for p in Pal:
        b = [a >> s for a, s in zip(p, shifts)]
        if len(p) == 4:
            b = pack("3*uint:5,uint:1", *b)
        else:
            b = pack("3*uint:5,uint:1", *b, 1)
        Pbin.append(b.bytes)
    bin = []
    for p in re[2]:
        for w in range(0, re[0], (8 // Bpp)):
            b = p[w : w + (8 // Bpp)]
            b = pack("%d*uint:%d" % ((8 // Bpp), Bpp), *b)
            bin.append(b.bytes)
    return [bin, Pbin]


def MakeIntensity(file, Bpp, Alpha):
    r = png.Reader(file)
    re = r.read()
    depth = re[3]["bitdepth"]
    channels = re[3]["planes"]
    if channels - Alpha > 1:
        # This means it has an alpha channel we must ignore
        bin = []
        for r in re[2]:
            last = 0
            for W in range(0, len(r), channels * depth // 8):
                b = r[W : W + (max(1, Bpp // 8))]
                b = [a for a in b]
                if last == 0 and Bpp == 4:
                    last = ((b[0] >> (depth - 4)) & 0xF) << (depth - 4)
                    continue
                elif (8 - Bpp) > 0:
                    a = b[0] >> (depth - 4)
                else:
                    a = b[0] >> (depth - Bpp)
                bin.append(bytes([a + last]))
                last = 0
        return bin
    else:
        # This should mean its all ready to go
        if Bpp == 4:
            shifts = [4, 7]
        else:
            shifts = [0, 0]
        bin = []
        for r in re[2]:
            last = 0
            for W in range(0, len(r), channels * depth // 8):
                b = r[W : W + (max(1, Bpp // 8)) * channels]
                b = [a for a in b]
                if last == 0 and Bpp == 4:
                    if Alpha:
                        last = ((b[0] >> (depth - 4)) & 0xE) << (depth - 4)
                        last += ((b[1] >> (depth - 1)) & 0xF) << (depth - 4)
                    else:
                        last = ((b[0] >> (depth - 4)) & 0xF) << (depth - 4)
                    continue
                elif Bpp == 4:
                    if Alpha:
                        a = (b[0] >> (depth - 4)) & 0xE
                        a += b[1] >> (depth - 1)
                    else:
                        a = b[0] >> (depth - 4)
                else:
                    a = b[0] >> (depth - Bpp)
                    if Alpha:
                        a = ((b[0] >> (depth - Bpp // 2)) << (Bpp // 2)) + (b[1] >> (depth - Bpp // 2))
                bin.append(bytes([a + last]))
                last = 0
        return bin

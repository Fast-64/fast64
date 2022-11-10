from .sm64_constants import loadSegmentAddresses
from ..utility import PluginError


def ExtendBank0x04(romfile, segmentData, segment4):

    # Extend bank 0x04
    romfile.seek(loadSegmentAddresses[0x04] + 4)
    oldStart = int.from_bytes(romfile.read(4), "big")
    romfile.seek(loadSegmentAddresses[0x04] + 4)
    romfile.write(int.to_bytes(segment4[0], 4, "big"))

    romfile.seek(loadSegmentAddresses[0x04] + 8)
    oldEnd = int.from_bytes(romfile.read(4), "big")
    romfile.seek(loadSegmentAddresses[0x04] + 8)
    romfile.write(int.to_bytes(segment4[1], 4, "big"))

    romfile.seek(oldStart)
    oldData = romfile.read(oldEnd - oldStart)

    if oldEnd - oldStart > segment4[1] - segment4[0]:
        print("Not enough space to copy old data.")
        raise PluginError("Not enough space to copy old data.")

    romfile.seek(segment4[0])
    romfile.write(oldData)

    segmentData[0x04] = (segment4[0], segment4[1])


def DisableLowPolyMario(romfile, geoStartAddress):
    # disable low poly mario
    romfile.seek(geoStartAddress + 0x42)
    romfile.write(bytearray.fromhex("2E 18"))


def readSegment4(romfile, segmentData):
    romfile.seek(loadSegmentAddresses[0x04] + 0x4)
    seg4start = int.from_bytes(romfile.read(4), "big")
    romfile.seek(loadSegmentAddresses[0x04] + 0x8)
    seg4end = int.from_bytes(romfile.read(4), "big")
    segmentData[0x04] = (seg4start, seg4end)

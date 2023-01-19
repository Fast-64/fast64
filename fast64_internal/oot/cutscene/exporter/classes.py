class OOTCSTextbox:
    def __init__(self):
        self.textboxType = None
        self.messageId = "0x0000"
        self.ocarinaSongAction = "0x0000"
        self.startFrame = 0
        self.endFrame = 1
        self.type = "0x0000"
        self.topOptionBranch = "0x0000"
        self.bottomOptionBranch = "0x0000"
        self.ocarinaMessageId = "0x0000"


class OOTCSLighting:
    def __init__(self):
        self.index = 1
        self.startFrame = 0


class OOTCSTime:
    def __init__(self):
        self.startFrame = 0
        self.hour = 23
        self.minute = 59


class OOTCSBGM:
    def __init__(self):
        self.value = "0x0000"
        self.startFrame = 0
        self.endFrame = 1


class OOTCSMisc:
    def __init__(self):
        self.operation = 1
        self.startFrame = 0
        self.endFrame = 1


class OOTCS0x09:
    def __init__(self):
        self.startFrame = 0
        self.unk2 = "0x00"
        self.unk3 = "0x00"
        self.unk4 = "0x00"


class OOTCSUnk:
    def __unk__(self):
        self.unk1 = "0x00000000"
        self.unk2 = "0x00000000"
        self.unk3 = "0x00000000"
        self.unk4 = "0x00000000"
        self.unk5 = "0x00000000"
        self.unk6 = "0x00000000"
        self.unk7 = "0x00000000"
        self.unk8 = "0x00000000"
        self.unk9 = "0x00000000"
        self.unk10 = "0x00000000"
        self.unk11 = "0x00000000"
        self.unk12 = "0x00000000"


class OOTCSList:
    def __init__(self):
        self.listType = None
        self.entries = []
        self.unkType = "0x0001"
        self.fxType = "1"
        self.fxStartFrame = 0
        self.fxEndFrame = 0


class OOTCutscene:
    def __init__(self):
        self.name = ""
        self.csEndFrame = 100
        self.csWriteTerminator = False
        self.csTermIdx = 0
        self.csTermStart = 99
        self.csTermEnd = 100
        self.csLists = []

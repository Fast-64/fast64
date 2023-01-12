class OOTCSTextbox:
    def __init__(self):
        self.textboxType = None
        self.textID = "0x0000"
        self.ocarinaAction = "0x0000"
        self.startFrame = 0
        self.endFrame = 1
        self.textboxType = "0x0000"
        self.topOptionTextID = "0x0000"
        self.bottomOptionTextID = "0x0000"
        self.ocarinaMessageId = "0x0000"


class OOTCSLighting:
    def __init__(self):
        self.lightSettingsIndex = 1
        self.startFrame = 0


class OOTCSTime:
    def __init__(self):
        self.startFrame = 0
        self.hour = 23
        self.minute = 59


class OOTCSBGM:
    def __init__(self):
        self.csSeqID = "0x0000"
        self.startFrame = 0
        self.endFrame = 1


class OOTCSMisc:
    def __init__(self):
        self.csMiscType = 1
        self.startFrame = 0
        self.endFrame = 1


class OOTCS0x09:
    def __init__(self):
        self.startFrame = 0
        self.rumbleSourceStrength = "0x00"
        self.rumbleDuration = "0x00"
        self.rumbleDecreaseRate = "0x00"


class OOTCSUnk:
    def __unk__(self):
        self.unk1 = "0x00000000"
        self.rumbleSourceStrength = "0x00000000"
        self.rumbleDuration = "0x00000000"
        self.rumbleDecreaseRate = "0x00000000"
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

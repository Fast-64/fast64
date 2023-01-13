class OOTCSText:
    def __init__(self):
        self.textboxType = "0x0000"
        self.textID = "0x0000"
        self.ocarinaAction = "0x0000"
        self.startFrame = 0
        self.endFrame = 1
        self.textType = "0x0000"
        self.topOptionTextID = "0x0000"
        self.bottomOptionTextID = "0x0000"
        self.ocarinaMessageId = "0x0000"


class OOTCSLightSettings:
    def __init__(self):
        self.lightSettingsIndex = 1
        self.startFrame = 0


class OOTCSTime:
    def __init__(self):
        self.startFrame = 0
        self.hour = 23
        self.minute = 59


class OOTCSSeq:
    def __init__(self):
        self.csSeqID = "0x0000"
        self.csSeqPlayer = "0x0000"
        self.startFrame = 0
        self.endFrame = 1


class OOTCSMisc:
    def __init__(self):
        self.csMiscType = 1
        self.startFrame = 0
        self.endFrame = 1


class OOTCSRumble:
    def __init__(self):
        self.startFrame = 0
        self.rumbleSourceStrength = "0x00"
        self.rumbleDuration = "0x00"
        self.rumbleDecreaseRate = "0x00"


class OOTCSList:
    def __init__(self):
        self.listType = None
        self.entries = []
        self.transitionType = "1"
        self.transitionStartFrame = 0
        self.transitionEndFrame = 0


class OOTCutscene:
    def __init__(self):
        self.name = ""
        self.csEndFrame = 100
        self.csWriteTerminator = False
        self.csTermIdx = 0
        self.csTermStart = 99
        self.csTermEnd = 100
        self.csLists = []

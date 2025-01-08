from dataclasses import dataclass
from typing import Optional
from bpy.types import Context


@dataclass
class Z64_BaseElement:
    id: str
    key: str
    name: str
    index: int


# ---

# TODO: get this from XML

ootEnumMusicSeq = [
    # see https://github.com/zeldaret/oot/blob/9f09505d34619883748a7dab05071883281c14fd/include/sequence.h#L4-L118
    ("Custom", "Custom", "Custom"),
    ("NA_BGM_GENERAL_SFX", "General Sound Effects", "General Sound Effects"),
    ("NA_BGM_NATURE_AMBIENCE", "Nature Ambiance", "Nature Ambiance"),
    ("NA_BGM_FIELD_LOGIC", "Hyrule Field", "Hyrule Field"),
    (
        "NA_BGM_FIELD_INIT",
        "Hyrule Field (Initial Segment From Loading Area)",
        "Hyrule Field (Initial Segment From Loading Area)",
    ),
    ("NA_BGM_FIELD_DEFAULT_1", "Hyrule Field (Moving Segment 1)", "Hyrule Field (Moving Segment 1)"),
    ("NA_BGM_FIELD_DEFAULT_2", "Hyrule Field (Moving Segment 2)", "Hyrule Field (Moving Segment 2)"),
    ("NA_BGM_FIELD_DEFAULT_3", "Hyrule Field (Moving Segment 3)", "Hyrule Field (Moving Segment 3)"),
    ("NA_BGM_FIELD_DEFAULT_4", "Hyrule Field (Moving Segment 4)", "Hyrule Field (Moving Segment 4)"),
    ("NA_BGM_FIELD_DEFAULT_5", "Hyrule Field (Moving Segment 5)", "Hyrule Field (Moving Segment 5)"),
    ("NA_BGM_FIELD_DEFAULT_6", "Hyrule Field (Moving Segment 6)", "Hyrule Field (Moving Segment 6)"),
    ("NA_BGM_FIELD_DEFAULT_7", "Hyrule Field (Moving Segment 7)", "Hyrule Field (Moving Segment 7)"),
    ("NA_BGM_FIELD_DEFAULT_8", "Hyrule Field (Moving Segment 8)", "Hyrule Field (Moving Segment 8)"),
    ("NA_BGM_FIELD_DEFAULT_9", "Hyrule Field (Moving Segment 9)", "Hyrule Field (Moving Segment 9)"),
    ("NA_BGM_FIELD_DEFAULT_A", "Hyrule Field (Moving Segment 10)", "Hyrule Field (Moving Segment 10)"),
    ("NA_BGM_FIELD_DEFAULT_B", "Hyrule Field (Moving Segment 11)", "Hyrule Field (Moving Segment 11)"),
    ("NA_BGM_FIELD_ENEMY_INIT", "Hyrule Field (Enemy Approaches)", "Hyrule Field (Enemy Approaches)"),
    ("NA_BGM_FIELD_ENEMY_1", "Hyrule Field (Enemy Near Segment 1)", "Hyrule Field (Enemy Near Segment 1)"),
    ("NA_BGM_FIELD_ENEMY_2", "Hyrule Field (Enemy Near Segment 2)", "Hyrule Field (Enemy Near Segment 2)"),
    ("NA_BGM_FIELD_ENEMY_3", "Hyrule Field (Enemy Near Segment 3)", "Hyrule Field (Enemy Near Segment 3)"),
    ("NA_BGM_FIELD_ENEMY_4", "Hyrule Field (Enemy Near Segment 4)", "Hyrule Field (Enemy Near Segment 4)"),
    (
        "NA_BGM_FIELD_STILL_1",
        "Hyrule Field (Standing Still Segment 1)",
        "Hyrule Field (Standing Still Segment 1)",
    ),
    (
        "NA_BGM_FIELD_STILL_2",
        "Hyrule Field (Standing Still Segment 2)",
        "Hyrule Field (Standing Still Segment 2)",
    ),
    (
        "NA_BGM_FIELD_STILL_3",
        "Hyrule Field (Standing Still Segment 3)",
        "Hyrule Field (Standing Still Segment 3)",
    ),
    (
        "NA_BGM_FIELD_STILL_4",
        "Hyrule Field (Standing Still Segment 4)",
        "Hyrule Field (Standing Still Segment 4)",
    ),
    ("NA_BGM_DUNGEON", "Dodongo's Cavern", "Dodongo's Cavern"),
    ("NA_BGM_KAKARIKO_ADULT", "Kakariko Village (Adult)", "Kakariko Village (Adult)"),
    ("NA_BGM_ENEMY", "Enemy Battle", "Enemy Battle"),
    ("NA_BGM_BOSS", "Boss Battle 00", "Boss Battle 00"),
    ("NA_BGM_INSIDE_DEKU_TREE", "Inside the Deku Tree", "Inside the Deku Tree"),
    ("NA_BGM_MARKET", "Market", "Market"),
    ("NA_BGM_TITLE", "Title Theme", "Title Theme"),
    ("NA_BGM_LINK_HOUSE", "Link's House", "Link's House"),
    ("NA_BGM_GAME_OVER", "Game Over", "Game Over"),
    ("NA_BGM_BOSS_CLEAR", "Boss Clear", "Boss Clear"),
    ("NA_BGM_ITEM_GET", "Item Get", "Item Get"),
    ("NA_BGM_OPENING_GANON", "Opening Ganon", "Opening Ganon"),
    ("NA_BGM_HEART_GET", "Heart Get", "Heart Get"),
    ("NA_BGM_OCA_LIGHT", "Prelude Of Light", "Prelude Of Light"),
    ("NA_BGM_JABU_JABU", "Inside Jabu-Jabu's Belly", "Inside Jabu-Jabu's Belly"),
    ("NA_BGM_KAKARIKO_KID", "Kakariko Village (Child)", "Kakariko Village (Child)"),
    ("NA_BGM_GREAT_FAIRY", "Great Fairy's Fountain", "Great Fairy's Fountain"),
    ("NA_BGM_ZELDA_THEME", "Zelda's Theme", "Zelda's Theme"),
    ("NA_BGM_FIRE_TEMPLE", "Fire Temple", "Fire Temple"),
    ("NA_BGM_OPEN_TRE_BOX", "Open Treasure Chest", "Open Treasure Chest"),
    ("NA_BGM_FOREST_TEMPLE", "Forest Temple", "Forest Temple"),
    ("NA_BGM_COURTYARD", "Hyrule Castle Courtyard", "Hyrule Castle Courtyard"),
    ("NA_BGM_GANON_TOWER", "Ganondorf's Theme", "Ganondorf's Theme"),
    ("NA_BGM_LONLON", "Lon Lon Ranch", "Lon Lon Ranch"),
    ("NA_BGM_GORON_CITY", "Goron City", "Goron City"),
    ("NA_BGM_FIELD_MORNING", "Hyrule Field Morning Theme", "Hyrule Field Morning Theme"),
    ("NA_BGM_SPIRITUAL_STONE", "Spiritual Stone Get", "Spiritual Stone Get"),
    ("NA_BGM_OCA_BOLERO", "Bolero of Fire", "Bolero of Fire"),
    ("NA_BGM_OCA_MINUET", "Minuet of Woods", "Minuet of Woods"),
    ("NA_BGM_OCA_SERENADE", "Serenade of Water", "Serenade of Water"),
    ("NA_BGM_OCA_REQUIEM", "Requiem of Spirit", "Requiem of Spirit"),
    ("NA_BGM_OCA_NOCTURNE", "Nocturne of Shadow", "Nocturne of Shadow"),
    ("NA_BGM_MINI_BOSS", "Mini-Boss Battle", "Mini-Boss Battle"),
    ("NA_BGM_SMALL_ITEM_GET", "Obtain Small Item", "Obtain Small Item"),
    ("NA_BGM_TEMPLE_OF_TIME", "Temple of Time", "Temple of Time"),
    ("NA_BGM_EVENT_CLEAR", "Escape from Lon Lon Ranch", "Escape from Lon Lon Ranch"),
    ("NA_BGM_KOKIRI", "Kokiri Forest", "Kokiri Forest"),
    ("NA_BGM_OCA_FAIRY_GET", "Obtain Fairy Ocarina", "Obtain Fairy Ocarina"),
    ("NA_BGM_SARIA_THEME", "Lost Woods", "Lost Woods"),
    ("NA_BGM_SPIRIT_TEMPLE", "Spirit Temple", "Spirit Temple"),
    ("NA_BGM_HORSE", "Horse Race", "Horse Race"),
    ("NA_BGM_HORSE_GOAL", "Horse Race Goal", "Horse Race Goal"),
    ("NA_BGM_INGO", "Ingo's Theme", "Ingo's Theme"),
    ("NA_BGM_MEDALLION_GET", "Obtain Medallion", "Obtain Medallion"),
    ("NA_BGM_OCA_SARIA", "Ocarina Saria's Song", "Ocarina Saria's Song"),
    ("NA_BGM_OCA_EPONA", "Ocarina Epona's Song", "Ocarina Epona's Song"),
    ("NA_BGM_OCA_ZELDA", "Ocarina Zelda's Lullaby", "Ocarina Zelda's Lullaby"),
    ("NA_BGM_OCA_SUNS", "Sun's Song", "Sun's Song"),
    ("NA_BGM_OCA_TIME", "Song of Time", "Song of Time"),
    ("NA_BGM_OCA_STORM", "Song of Storms", "Song of Storms"),
    ("NA_BGM_NAVI_OPENING", "Fairy Flying", "Fairy Flying"),
    ("NA_BGM_DEKU_TREE_CS", "Deku Tree", "Deku Tree"),
    ("NA_BGM_WINDMILL", "Windmill Hut", "Windmill Hut"),
    ("NA_BGM_HYRULE_CS", "Legend of Hyrule", "Legend of Hyrule"),
    ("NA_BGM_MINI_GAME", "Shooting Gallery", "Shooting Gallery"),
    ("NA_BGM_SHEIK", "Sheik's Theme", "Sheik's Theme"),
    ("NA_BGM_ZORA_DOMAIN", "Zora's Domain", "Zora's Domain"),
    ("NA_BGM_APPEAR", "Enter Zelda", "Enter Zelda"),
    ("NA_BGM_ADULT_LINK", "Goodbye to Zelda", "Goodbye to Zelda"),
    ("NA_BGM_MASTER_SWORD", "Master Sword", "Master Sword"),
    ("NA_BGM_INTRO_GANON", "Ganon Intro", "Ganon Intro"),
    ("NA_BGM_SHOP", "Shop", "Shop"),
    ("NA_BGM_CHAMBER_OF_SAGES", "Chamber of the Sages", "Chamber of the Sages"),
    ("NA_BGM_FILE_SELECT", "File Select", "File Select"),
    ("NA_BGM_ICE_CAVERN", "Ice Cavern", "Ice Cavern"),
    ("NA_BGM_DOOR_OF_TIME", "Open Door of Temple of Time", "Open Door of Temple of Time"),
    ("NA_BGM_OWL", "Kaepora Gaebora's Theme", "Kaepora Gaebora's Theme"),
    ("NA_BGM_SHADOW_TEMPLE", "Shadow Temple", "Shadow Temple"),
    ("NA_BGM_WATER_TEMPLE", "Water Temple", "Water Temple"),
    ("NA_BGM_BRIDGE_TO_GANONS", "Ganon's Castle Bridge", "Ganon's Castle Bridge"),
    ("NA_BGM_OCARINA_OF_TIME", "Ocarina of Time", "Ocarina of Time"),
    ("NA_BGM_GERUDO_VALLEY", "Gerudo Valley", "Gerudo Valley"),
    ("NA_BGM_POTION_SHOP", "Potion Shop", "Potion Shop"),
    ("NA_BGM_KOTAKE_KOUME", "Kotake & Koume's Theme", "Kotake & Koume's Theme"),
    ("NA_BGM_ESCAPE", "Escape from Ganon's Castle", "Escape from Ganon's Castle"),
    ("NA_BGM_UNDERGROUND", "Ganon's Castle Under Ground", "Ganon's Castle Under Ground"),
    ("NA_BGM_GANONDORF_BOSS", "Ganondorf Battle", "Ganondorf Battle"),
    ("NA_BGM_GANON_BOSS", "Ganon Battle", "Ganon Battle"),
    ("NA_BGM_END_DEMO", "Seal of Six Sages", "Seal of Six Sages"),
    ("NA_BGM_STAFF_1", "End Credits I", "End Credits I"),
    ("NA_BGM_STAFF_2", "End Credits II", "End Credits II"),
    ("NA_BGM_STAFF_3", "End Credits III", "End Credits III"),
    ("NA_BGM_STAFF_4", "End Credits IV", "End Credits IV"),
    ("NA_BGM_FIRE_BOSS", "King Dodongo & Volvagia Boss Battle", "King Dodongo & Volvagia Boss Battle"),
    ("NA_BGM_TIMED_MINI_GAME", "Mini-Game", "Mini-Game"),
    ("NA_BGM_CUTSCENE_EFFECTS", "Various Cutscene Sounds", "Various Cutscene Sounds"),
    ("NA_BGM_NO_MUSIC", "No Music", "No Music"),
    ("NA_BGM_NATURE_SFX_RAIN", "Nature Ambiance: Rain", "Nature Ambiance: Rain"),
]

ootEnumNightSeq = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "General Night", "NATURE_ID_GENERAL_NIGHT"),
    ("0x01", "Market Entrance", "NATURE_ID_MARKET_ENTRANCE"),
    ("0x02", "Kakariko Region", "NATURE_ID_KAKARIKO_REGION"),
    ("0x03", "Market Ruins", "NATURE_ID_MARKET_RUINS"),
    ("0x04", "Kokiri Region", "NATURE_ID_KOKIRI_REGION"),
    ("0x05", "Market Night", "NATURE_ID_MARKET_NIGHT"),
    ("0x06", "NATURE_ID_06", "NATURE_ID_06"),
    ("0x07", "Ganon's Lair", "NATURE_ID_GANONS_LAIR"),
    ("0x08", "NATURE_ID_08", "NATURE_ID_08"),
    ("0x09", "NATURE_ID_09", "NATURE_ID_09"),
    ("0x0A", "Wasteland", "NATURE_ID_WASTELAND"),
    ("0x0B", "Colossus", "NATURE_ID_COLOSSUS"),
    ("0x0C", "Nature DMT", "NATURE_ID_DEATH_MOUNTAIN_TRAIL"),
    ("0x0D", "NATURE_ID_0D", "NATURE_ID_0D"),
    ("0x0E", "NATURE_ID_0E", "NATURE_ID_0E"),
    ("0x0F", "NATURE_ID_0F", "NATURE_ID_0F"),
    ("0x10", "NATURE_ID_10", "NATURE_ID_10"),
    ("0x11", "NATURE_ID_11", "NATURE_ID_11"),
    ("0x12", "NATURE_ID_12", "NATURE_ID_12"),
    ("0x13", "None", "NATURE_ID_NONE"),
    ("0xFF", "Disabled", "NATURE_ID_DISABLED"),
]

enum_seq_id = [
    ("Custom", "Custom", "Custom"),
    ("NA_BGM_GENERAL_SFX", "General Sound Effects", "General Sound Effects"),
    ("NA_BGM_AMBIENCE", "Ambient background noises", "Ambient background noises"),
    ("NA_BGM_TERMINA_FIELD", "Termina Field", "Termina Field"),
    ("NA_BGM_CHASE", "Chase", "Chase"),
    ("NA_BGM_MAJORAS_THEME", "Majora's Theme", "Majora's Theme"),
    ("NA_BGM_CLOCK_TOWER", "Clock Tower", "Clock Tower"),
    ("NA_BGM_STONE_TOWER_TEMPLE", "Stone Tower Temple", "Stone Tower Temple"),
    ("NA_BGM_INV_STONE_TOWER_TEMPLE", "Stone Tower Temple Upside-down", "Stone Tower Temple Upside-down"),
    ("NA_BGM_FAILURE_0", "Missed Event 1", "Missed Event 1"),
    ("NA_BGM_FAILURE_1", "Missed Event 2", "Missed Event 2"),
    ("NA_BGM_HAPPY_MASK_SALESMAN", "Happy Mask Saleman's Theme", "Happy Mask Saleman's Theme"),
    ("NA_BGM_SONG_OF_HEALING", "Song Of Healing", "Song Of Healing"),
    ("NA_BGM_SWAMP_REGION", "Southern Swamp", "Southern Swamp"),
    ("NA_BGM_ALIEN_INVASION", "Ghost Attack", "Ghost Attack"),
    ("NA_BGM_SWAMP_CRUISE", "Boat Cruise", "Boat Cruise"),
    ("NA_BGM_SHARPS_CURSE", "Sharp's Curse", "Sharp's Curse"),
    ("NA_BGM_GREAT_BAY_REGION", "Great Bay Coast", "Great Bay Coast"),
    ("NA_BGM_IKANA_REGION", "Ikana Valley", "Ikana Valley"),
    ("NA_BGM_DEKU_PALACE", "Deku Palace", "Deku Palace"),
    ("NA_BGM_MOUNTAIN_REGION", "Mountain Village", "Mountain Village"),
    ("NA_BGM_PIRATES_FORTRESS", "Pirates' Fortress", "Pirates' Fortress"),
    ("NA_BGM_CLOCK_TOWN_DAY_1", "Clock Town, First Day", "Clock Town, First Day"),
    ("NA_BGM_CLOCK_TOWN_DAY_2", "Clock Town, Second Day", "Clock Town, Second Day"),
    ("NA_BGM_CLOCK_TOWN_DAY_3", "Clock Town, Third Day", "Clock Town, Third Day"),
    ("NA_BGM_FILE_SELECT", "File Select", "File Select"),
    ("NA_BGM_CLEAR_EVENT", "Event Clear", "Event Clear"),
    ("NA_BGM_ENEMY", "Battle", "Battle"),
    ("NA_BGM_BOSS", "Boss Battle", "Boss Battle"),
    ("NA_BGM_WOODFALL_TEMPLE", "Woodfall Temple", "Woodfall Temple"),
    ("NA_BGM_CLOCK_TOWN_MAIN_SEQUENCE", "NA_BGM_CLOCK_TOWN_MAIN_SEQUENCE", "NA_BGM_CLOCK_TOWN_MAIN_SEQUENCE"),
    ("NA_BGM_OPENING", "Opening", "Opening"),
    ("NA_BGM_INSIDE_A_HOUSE", "House", "House"),
    ("NA_BGM_GAME_OVER", "Game Over", "Game Over"),
    ("NA_BGM_CLEAR_BOSS", "Boss Clear", "Boss Clear"),
    ("NA_BGM_GET_ITEM", "Item Catch", "Item Catch"),
    ("NA_BGM_CLOCK_TOWN_DAY_2_PTR", "NA_BGM_CLOCK_TOWN_DAY_2_PTR", "NA_BGM_CLOCK_TOWN_DAY_2_PTR"),
    ("NA_BGM_GET_HEART", "Get A Heart Container", "Get A Heart Container"),
    ("NA_BGM_TIMED_MINI_GAME", "Mini Game", "Mini Game"),
    ("NA_BGM_GORON_RACE", "Goron Race", "Goron Race"),
    ("NA_BGM_MUSIC_BOX_HOUSE", "Music Box House", "Music Box House"),
    ("NA_BGM_FAIRY_FOUNTAIN", "Fairy's Fountain", "Fairy's Fountain"),
    ("NA_BGM_ZELDAS_LULLABY", "Zelda's Theme", "Zelda's Theme"),
    ("NA_BGM_ROSA_SISTERS", "Rosa Sisters", "Rosa Sisters"),
    ("NA_BGM_OPEN_CHEST", "Open Treasure Box", "Open Treasure Box"),
    ("NA_BGM_MARINE_RESEARCH_LAB", "Marine Research Laboratory", "Marine Research Laboratory"),
    ("NA_BGM_GIANTS_THEME", "Giants' Theme", "Giants' Theme"),
    ("NA_BGM_SONG_OF_STORMS", "Guru-Guru's Song", "Guru-Guru's Song"),
    ("NA_BGM_ROMANI_RANCH", "Romani Ranch", "Romani Ranch"),
    ("NA_BGM_GORON_VILLAGE", "Goron Village", "Goron Village"),
    ("NA_BGM_MAYORS_OFFICE", "Mayor's Meeting", "Mayor's Meeting"),
    ("NA_BGM_OCARINA_EPONA", "Ocarina “Epona's Song”", "Ocarina “Epona's Song”"),
    ("NA_BGM_OCARINA_SUNS", "Ocarina “Sun's Song”", "Ocarina “Sun's Song”"),
    ("NA_BGM_OCARINA_TIME", "Ocarina “Song Of Time”", "Ocarina “Song Of Time”"),
    ("NA_BGM_OCARINA_STORM", "Ocarina “Song Of Storms”", "Ocarina “Song Of Storms”"),
    ("NA_BGM_ZORA_HALL", "Zora Hall", "Zora Hall"),
    ("NA_BGM_GET_NEW_MASK", "Get A Mask", "Get A Mask"),
    ("NA_BGM_MINI_BOSS", "Middle Boss Battle", "Middle Boss Battle"),
    ("NA_BGM_GET_SMALL_ITEM", "Small Item Catch", "Small Item Catch"),
    ("NA_BGM_ASTRAL_OBSERVATORY", "Astral Observatory", "Astral Observatory"),
    ("NA_BGM_CAVERN", "Cavern", "Cavern"),
    ("NA_BGM_MILK_BAR", "Milk Bar", "Milk Bar"),
    ("NA_BGM_ZELDA_APPEAR", "Enter Zelda", "Enter Zelda"),
    ("NA_BGM_SARIAS_SONG", "Woods Of Mystery", "Woods Of Mystery"),
    ("NA_BGM_GORON_GOAL", "Goron Race Goal", "Goron Race Goal"),
    ("NA_BGM_HORSE", "Horse Race", "Horse Race"),
    ("NA_BGM_HORSE_GOAL", "Horse Race Goal", "Horse Race Goal"),
    ("NA_BGM_INGO", "Gorman Track", "Gorman Track"),
    ("NA_BGM_KOTAKE_POTION_SHOP", "Magic Hags' Potion Shop", "Magic Hags' Potion Shop"),
    ("NA_BGM_SHOP", "Shop", "Shop"),
    ("NA_BGM_OWL", "Owl", "Owl"),
    ("NA_BGM_SHOOTING_GALLERY", "Shooting Gallery", "Shooting Gallery"),
    ("NA_BGM_OCARINA_SOARING", "Ocarina “Song Of Soaring”", "Ocarina “Song Of Soaring”"),
    ("NA_BGM_OCARINA_HEALING", "Ocarina “Song Of Healing”", "Ocarina “Song Of Healing”"),
    ("NA_BGM_INVERTED_SONG_OF_TIME", "Ocarina “Inverted Song Of Time”", "Ocarina “Inverted Song Of Time”"),
    ("NA_BGM_SONG_OF_DOUBLE_TIME", "Ocarina “Song Of Double Time”", "Ocarina “Song Of Double Time”"),
    ("NA_BGM_SONATA_OF_AWAKENING", "Sonata of Awakening", "Sonata of Awakening"),
    ("NA_BGM_GORON_LULLABY", "Goron Lullaby", "Goron Lullaby"),
    ("NA_BGM_NEW_WAVE_BOSSA_NOVA", "New Wave Bossa Nova", "New Wave Bossa Nova"),
    ("NA_BGM_ELEGY_OF_EMPTINESS", "Elegy Of Emptiness", "Elegy Of Emptiness"),
    ("NA_BGM_OATH_TO_ORDER", "Oath To Order", "Oath To Order"),
    ("NA_BGM_SWORD_TRAINING_HALL", "Swordsman's School", "Swordsman's School"),
    ("NA_BGM_OCARINA_LULLABY_INTRO", "Ocarina “Goron Lullaby Intro”", "Ocarina “Goron Lullaby Intro”"),
    ("NA_BGM_LEARNED_NEW_SONG", "Get The Ocarina", "Get The Ocarina"),
    ("NA_BGM_BREMEN_MARCH", "Bremen March", "Bremen March"),
    ("NA_BGM_BALLAD_OF_THE_WIND_FISH", "Ballad Of The Wind Fish", "Ballad Of The Wind Fish"),
    ("NA_BGM_SONG_OF_SOARING", "Song Of Soaring", "Song Of Soaring"),
    ("NA_BGM_MILK_BAR_DUPLICATE", "NA_BGM_MILK_BAR_DUPLICATE", "NA_BGM_MILK_BAR_DUPLICATE"),
    ("NA_BGM_FINAL_HOURS", "Last Day", "Last Day"),
    ("NA_BGM_MIKAU_RIFF", "Mikau", "Mikau"),
    ("NA_BGM_MIKAU_FINALE", "Mikau", "Mikau"),
    ("NA_BGM_FROG_SONG", "Frog Song", "Frog Song"),
    ("NA_BGM_OCARINA_SONATA", "Ocarina “Sonata Of Awakening”", "Ocarina “Sonata Of Awakening”"),
    ("NA_BGM_OCARINA_LULLABY", "Ocarina “Goron Lullaby”", "Ocarina “Goron Lullaby”"),
    ("NA_BGM_OCARINA_NEW_WAVE", "Ocarina “New Wave Bossa Nova”", "Ocarina “New Wave Bossa Nova”"),
    ("NA_BGM_OCARINA_ELEGY", "Ocarina “Elegy of Emptiness”", "Ocarina “Elegy of Emptiness”"),
    ("NA_BGM_OCARINA_OATH", "Ocarina “Oath To Order”", "Ocarina “Oath To Order”"),
    ("NA_BGM_MAJORAS_LAIR", "Majora Boss Room", "Majora Boss Room"),
    ("NA_BGM_OCARINA_LULLABY_INTRO_PTR", "NA_BGM_OCARINA_LULLABY_INTRO", "NA_BGM_OCARINA_LULLABY_INTRO"),
    ("NA_BGM_OCARINA_GUITAR_BASS_SESSION", "Bass and Guitar Session", "Bass and Guitar Session"),
    ("NA_BGM_PIANO_SESSION", "Piano Solo", "Piano Solo"),
    ("NA_BGM_INDIGO_GO_SESSION", "The Indigo-Go's", "The Indigo-Go's"),
    ("NA_BGM_SNOWHEAD_TEMPLE", "Snowhead Temple", "Snowhead Temple"),
    ("NA_BGM_GREAT_BAY_TEMPLE", "Great Bay Temple", "Great Bay Temple"),
    ("NA_BGM_NEW_WAVE_SAXOPHONE", "New Wave Bossa Nova", "New Wave Bossa Nova"),
    ("NA_BGM_NEW_WAVE_VOCAL", "New Wave Bossa Nova", "New Wave Bossa Nova"),
    ("NA_BGM_MAJORAS_WRATH", "Majora's Wrath Battle", "Majora's Wrath Battle"),
    ("NA_BGM_MAJORAS_INCARNATION", "Majora's Incarnate Battle", "Majora's Incarnate Battle"),
    ("NA_BGM_MAJORAS_MASK", "Majora's Mask Battle", "Majora's Mask Battle"),
    ("NA_BGM_BASS_PLAY", "Bass Practice", "Bass Practice"),
    ("NA_BGM_DRUMS_PLAY", "Drums Practice", "Drums Practice"),
    ("NA_BGM_PIANO_PLAY", "Piano Practice", "Piano Practice"),
    ("NA_BGM_IKANA_CASTLE", "Ikana Castle", "Ikana Castle"),
    ("NA_BGM_GATHERING_GIANTS", "Calling The Four Giants", "Calling The Four Giants"),
    ("NA_BGM_KAMARO_DANCE", "Kamaro's Dance", "Kamaro's Dance"),
    ("NA_BGM_CREMIA_CARRIAGE", "Cremia's Carriage", "Cremia's Carriage"),
    ("NA_BGM_KEATON_QUIZ", "Keaton's Quiz", "Keaton's Quiz"),
    ("NA_BGM_END_CREDITS", "The End / Credits", "The End / Credits"),
    ("NA_BGM_OPENING_LOOP", "NA_BGM_OPENING_LOOP", "NA_BGM_OPENING_LOOP"),
    ("NA_BGM_TITLE_THEME", "Title Theme", "Title Theme"),
    ("NA_BGM_DUNGEON_APPEAR", "Woodfall Rises", "Woodfall Rises"),
    ("NA_BGM_WOODFALL_CLEAR", "Southern Swamp Clears", "Southern Swamp Clears"),
    ("NA_BGM_SNOWHEAD_CLEAR", "Snowhead Clear", "Snowhead Clear"),
    ("NA_BGM_INTO_THE_MOON", "To The Moon", "To The Moon"),
    ("NA_BGM_GOODBYE_GIANT", "The Giants' Exit", "The Giants' Exit"),
    ("NA_BGM_TATL_AND_TAEL", "Tatl and Tael", "Tatl and Tael"),
    ("NA_BGM_MOONS_DESTRUCTION", "Moon's Destruction", "Moon's Destruction"),
    ("NA_BGM_END_CREDITS_SECOND_HALF", "The End / Credits (Half 2)", "The End / Credits (Half 2)"),
]

enum_ambiance_id = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "AMBIENCE_ID_00", "AMBIENCE_ID_00"),
    ("0x01", "AMBIENCE_ID_01", "AMBIENCE_ID_01"),
    ("0x02", "AMBIENCE_ID_02", "AMBIENCE_ID_02"),
    ("0x03", "AMBIENCE_ID_03", "AMBIENCE_ID_03"),
    ("0x04", "AMBIENCE_ID_04", "AMBIENCE_ID_04"),
    ("0x05", "AMBIENCE_ID_05", "AMBIENCE_ID_05"),
    ("0x06", "AMBIENCE_ID_06", "AMBIENCE_ID_06"),
    ("0x07", "AMBIENCE_ID_07", "AMBIENCE_ID_07"),
    ("0x08", "AMBIENCE_ID_08", "AMBIENCE_ID_08"),
    ("0x09", "AMBIENCE_ID_09", "AMBIENCE_ID_09"),
    ("0x0A", "AMBIENCE_ID_0A", "AMBIENCE_ID_0A"),
    ("0x0B", "AMBIENCE_ID_0B", "AMBIENCE_ID_0B"),
    ("0x0C", "AMBIENCE_ID_0C", "AMBIENCE_ID_0C"),
    ("0x0D", "AMBIENCE_ID_0D", "AMBIENCE_ID_0D"),
    ("0x0E", "AMBIENCE_ID_0E", "AMBIENCE_ID_0E"),
    ("0x0F", "AMBIENCE_ID_0F", "AMBIENCE_ID_0F"),
    ("0x10", "AMBIENCE_ID_10", "AMBIENCE_ID_10"),
    ("0x11", "AMBIENCE_ID_11", "AMBIENCE_ID_11"),
    ("0x12", "AMBIENCE_ID_12", "AMBIENCE_ID_12"),
    ("0x13", "AMBIENCE_ID_13", "AMBIENCE_ID_13"),
    ("0xFF", "AMBIENCE_ID_DISABLED", "AMBIENCE_ID_DISABLED"),
]


ootEnumGlobalObject = [
    ("Custom", "Custom", "Custom"),
    ("OBJECT_INVALID", "None", "None"),
    ("OBJECT_GAMEPLAY_FIELD_KEEP", "Overworld", "gameplay_field_keep"),
    ("OBJECT_GAMEPLAY_DANGEON_KEEP", "Dungeon", "gameplay_dangeon_keep"),
]

mm_enum_global_object = [
    ("Custom", "Custom", "Custom"),
    ("GAMEPLAY_FIELD_KEEP", "Overworld", "gameplay_field_keep"),
    ("GAMEPLAY_DANGEON_KEEP", "Dungeon", "gameplay_dangeon_keep"),
]

ootEnumDrawConfig = [
    ("Custom", "Custom", "Custom"),
    ("SDC_DEFAULT", "Default", "Default"),
    ("SDC_HYRULE_FIELD", "Hyrule Field (Spot00)", "Spot00"),
    ("SDC_KAKARIKO_VILLAGE", "Kakariko Village (Spot01)", "Spot01"),
    ("SDC_ZORAS_RIVER", "Zora's River (Spot03)", "Spot03"),
    ("SDC_KOKIRI_FOREST", "Kokiri Forest (Spot04)", "Spot04"),
    ("SDC_LAKE_HYLIA", "Lake Hylia (Spot06)", "Spot06"),
    ("SDC_ZORAS_DOMAIN", "Zora's Domain (Spot07)", "Spot07"),
    ("SDC_ZORAS_FOUNTAIN", "Zora's Fountain (Spot08)", "Spot08"),
    ("SDC_GERUDO_VALLEY", "Gerudo Valley (Spot09)", "Spot09"),
    ("SDC_LOST_WOODS", "Lost Woods (Spot10)", "Spot10"),
    ("SDC_DESERT_COLOSSUS", "Desert Colossus (Spot11)", "Spot11"),
    ("SDC_GERUDOS_FORTRESS", "Gerudo's Fortress (Spot12)", "Spot12"),
    ("SDC_HAUNTED_WASTELAND", "Haunted Wasteland (Spot13)", "Spot13"),
    ("SDC_HYRULE_CASTLE", "Hyrule Castle (Spot15)", "Spot15"),
    ("SDC_DEATH_MOUNTAIN_TRAIL", "Death Mountain Trail (Spot16)", "Spot16"),
    ("SDC_DEATH_MOUNTAIN_CRATER", "Death Mountain Crater (Spot17)", "Spot17"),
    ("SDC_GORON_CITY", "Goron City (Spot18)", "Spot18"),
    ("SDC_LON_LON_RANCH", "Lon Lon Ranch (Spot20)", "Spot20"),
    ("SDC_FIRE_TEMPLE", "Fire Temple (Hidan)", "Hidan"),
    ("SDC_DEKU_TREE", "Inside the Deku Tree (Ydan)", "Ydan"),
    ("SDC_DODONGOS_CAVERN", "Dodongo's Cavern (Ddan)", "Ddan"),
    ("SDC_JABU_JABU", "Inside Jabu Jabu's Belly (Bdan)", "Bdan"),
    ("SDC_FOREST_TEMPLE", "Forest Temple (Bmori1)", "Bmori1"),
    ("SDC_WATER_TEMPLE", "Water Temple (Mizusin)", "Mizusin"),
    ("SDC_SHADOW_TEMPLE_AND_WELL", "Shadow Temple (Hakadan)", "Hakadan"),
    ("SDC_SPIRIT_TEMPLE", "Spirit Temple (Jyasinzou)", "Jyasinzou"),
    ("SDC_INSIDE_GANONS_CASTLE", "Inside Ganon's Castle (Ganontika)", "Ganontika"),
    ("SDC_GERUDO_TRAINING_GROUND", "Gerudo Training Ground (Men)", "Men"),
    ("SDC_DEKU_TREE_BOSS", "Gohma's Lair (Ydan Boss)", "Ydan Boss"),
    ("SDC_WATER_TEMPLE_BOSS", "Morpha's Lair (Mizusin Bs)", "Mizusin Bs"),
    ("SDC_TEMPLE_OF_TIME", "Temple of Time (Tokinoma)", "Tokinoma"),
    ("SDC_GROTTOS", "Grottos (Kakusiana)", "Kakusiana"),
    ("SDC_CHAMBER_OF_THE_SAGES", "Chamber of the Sages (Kenjyanoma)", "Kenjyanoma"),
    ("SDC_GREAT_FAIRYS_FOUNTAIN", "Great Fairy Fountain", "Great Fairy Fountain"),
    ("SDC_SHOOTING_GALLERY", "Shooting Gallery (Syatekijyou)", "Syatekijyou"),
    ("SDC_CASTLE_COURTYARD_GUARDS", "Castle Hedge Maze (Day) (Hairal Niwa)", "Hairal Niwa"),
    ("SDC_OUTSIDE_GANONS_CASTLE", "Ganon's Castle Exterior (Ganon Tou)", "Ganon Tou"),
    ("SDC_ICE_CAVERN", "Ice Cavern (Ice Doukuto)", "Ice Doukuto"),
    (
        "SDC_GANONS_TOWER_COLLAPSE_EXTERIOR",
        "Ganondorf's Death Scene (Tower Escape Exterior) (Ganon Final)",
        "Ganon Final",
    ),
    ("SDC_FAIRYS_FOUNTAIN", "Fairy Fountain", "Fairy Fountain"),
    ("SDC_THIEVES_HIDEOUT", "Thieves' Hideout (Gerudoway)", "Gerudoway"),
    ("SDC_BOMBCHU_BOWLING_ALLEY", "Bombchu Bowling Alley (Bowling)", "Bowling"),
    ("SDC_ROYAL_FAMILYS_TOMB", "Royal Family's Tomb (Hakaana Ouke)", "Hakaana Ouke"),
    ("SDC_LAKESIDE_LABORATORY", "Lakeside Laboratory (Hylia Labo)", "Hylia Labo"),
    ("SDC_LON_LON_BUILDINGS", "Lon Lon Ranch House & Tower (Souko)", "Souko"),
    ("SDC_MARKET_GUARD_HOUSE", "Guard House (Miharigoya)", "Miharigoya"),
    ("SDC_POTION_SHOP_GRANNY", "Granny's Potion Shop (Mahouya)", "Mahouya"),
    ("SDC_CALM_WATER", "Calm Water", "Calm Water"),
    ("SDC_GRAVE_EXIT_LIGHT_SHINING", "Grave Exit Light Shining", "Grave Exit Light Shining"),
    ("SDC_BESITU", "Ganondorf Test Room (Besitu)", "Besitu"),
    ("SDC_FISHING_POND", "Fishing Pond (Turibori)", "Turibori"),
    ("SDC_GANONS_TOWER_COLLAPSE_INTERIOR", "Ganon's Tower (Collapsing) (Ganon Sonogo)", "Ganon Sonogo"),
    ("SDC_INSIDE_GANONS_CASTLE_COLLAPSE", "Inside Ganon's Castle (Collapsing) (Ganontika Sonogo)", "Ganontika Sonogo"),
]

mm_enum_draw_config = [
    ("Custom", "Custom", "Custom"),
    ("SCENE_DRAW_CFG_DEFAULT", "Default", "Default"),
    ("SCENE_DRAW_CFG_MAT_ANIM", "Material Animated", "Material Animated"),
    ("SCENE_DRAW_CFG_NOTHING", "Nothing", "Nothing"),
    ("SCENE_DRAW_CFG_GREAT_BAY_TEMPLE", "Great Bay Temple", "Great Bay Temple"),
    ("SCENE_DRAW_CFG_MAT_ANIM_MANUAL_STEP", "Material Animated (manual step)", "Material Animated (manual step)"),
]

ootEnumCollisionSound = [
    ("Custom", "Custom", "Custom"),
    ("SURFACE_MATERIAL_DIRT", "Dirt", "Dirt (aka Earth)"),
    ("SURFACE_MATERIAL_SAND", "Sand", "Sand"),
    ("SURFACE_MATERIAL_STONE", "Stone", "Stone"),
    ("SURFACE_MATERIAL_JABU", "Jabu", "Jabu-Jabu flesh (aka Wet Stone)"),
    ("SURFACE_MATERIAL_WATER_SHALLOW", "Shallow Water", "Shallow Water"),
    ("SURFACE_MATERIAL_WATER_DEEP", "Deep Water", "Deep Water"),
    ("SURFACE_MATERIAL_TALL_GRASS", "Tall Grass", "Tall Grass"),
    ("SURFACE_MATERIAL_LAVA", "Lava", "Lava (aka Goo)"),
    ("SURFACE_MATERIAL_GRASS", "Grass", "Grass (aka Earth 2)"),
    ("SURFACE_MATERIAL_BRIDGE", "Bridge", "Bridge (aka Wooden Plank)"),
    ("SURFACE_MATERIAL_WOOD", "Wood", "Wood (aka Packed Earth)"),
    ("SURFACE_MATERIAL_DIRT_SOFT", "Soft Dirt", "Soft Dirt (aka Earth 3)"),
    ("SURFACE_MATERIAL_ICE", "Ice", "Ice (aka Ceramic)"),
    ("SURFACE_MATERIAL_CARPET", "Carpet", "Carpet (aka Loose Earth)"),
]

mm_enum_surface_material = [
    ("Custom", "Custom", "Custom"),
    ("SURFACE_MATERIAL_DIRT", "Dirt", "Dirt (aka Earth)"),
    ("SURFACE_MATERIAL_SAND", "Sand", "Sand"),
    ("SURFACE_MATERIAL_STONE", "Stone", "Stone"),
    ("SURFACE_MATERIAL_DIRT_SHALLOW", "Shallow Dirt", "Shallow Dirt"),
    ("SURFACE_MATERIAL_WATER_SHALLOW", "Shallow Water", "Shallow Water"),
    ("SURFACE_MATERIAL_WATER_DEEP", "Deep Water", "Deep Water"),
    ("SURFACE_MATERIAL_TALL_GRASS", "Tall Grass", "Tall Grass"),
    ("SURFACE_MATERIAL_LAVA", "Lava", "Lava (aka Goo)"),
    ("SURFACE_MATERIAL_GRASS", "Grass", "Grass (aka Earth 2)"),
    ("SURFACE_MATERIAL_BRIDGE", "Bridge", "Bridge (aka Wooden Plank)"),
    ("SURFACE_MATERIAL_WOOD", "Wood", "Wood (aka Packed Earth)"),
    ("SURFACE_MATERIAL_DIRT_SOFT", "Soft Dirt", "Soft Dirt (aka Earth 3)"),
    ("SURFACE_MATERIAL_ICE", "Ice", "Ice (aka Ceramic)"),
    ("SURFACE_MATERIAL_CARPET", "Carpet", "Carpet (aka Loose Earth)"),
    ("SURFACE_MATERIAL_SNOW", "Snow", "Snow"),
]

# ---

ootEnumSkybox = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "None", "None"),
    ("0x01", "Standard Sky", "Standard Sky"),
    ("0x02", "Hylian Bazaar", "Hylian Bazaar"),
    ("0x03", "Brown Cloudy Sky", "Brown Cloudy Sky"),
    ("0x04", "Market Ruins", "Market Ruins"),
    ("0x05", "Black Cloudy Night", "Black Cloudy Night"),
    ("0x07", "Link's House", "Link's House"),
    ("0x09", "Market (Main Square, Day)", "Market (Main Square, Day)"),
    ("0x0A", "Market (Main Square, Night)", "Market (Main Square, Night)"),
    ("0x0B", "Happy Mask Shop", "Happy Mask Shop"),
    ("0x0C", "Know-It-All Brothers' House", "Know-It-All Brothers' House"),
    ("0x0E", "Kokiri Twins' House", "Kokiri Twins' House"),
    ("0x0F", "Stable", "Stable"),
    ("0x10", "Stew Lady's House", "Stew Lady's House"),
    ("0x11", "Kokiri Shop", "Kokiri Shop"),
    ("0x13", "Goron Shop", "Goron Shop"),
    ("0x14", "Zora Shop", "Zora Shop"),
    ("0x16", "Kakariko Potions Shop", "Kakariko Potions Shop"),
    ("0x17", "Hylian Potions Shop", "Hylian Potions Shop"),
    ("0x18", "Bomb Shop", "Bomb Shop"),
    ("0x1A", "Dog Lady's House", "Dog Lady's House"),
    ("0x1B", "Impa's House", "Impa's House"),
    ("0x1C", "Gerudo Tent", "Gerudo Tent"),
    ("0x1D", "Environment Color", "Environment Color"),
    ("0x20", "Mido's House", "Mido's House"),
    ("0x21", "Saria's House", "Saria's House"),
    ("0x22", "Dog Guy's House", "Dog Guy's House"),
]

mm_enum_skybox = [
    ("Custom", "Custom", "Custom"),
    ("SKYBOX_NONE", "None", "0x00"),
    ("SKYBOX_NORMAL_SKY", "Standard Sky", "0x01"),
    ("SKYBOX_2", "SKYBOX_2", "0x02"),
    ("SKYBOX_3", "SKYBOX_3", "0x03"),
    ("SKYBOX_CUTSCENE_MAP", "Cutscene Map", "0x05"),
]

ootEnumCloudiness = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "Sunny", "Sunny"),
    ("0x01", "Cloudy", "Cloudy"),
]

mm_enum_skybox_config = [
    ("Custom", "Custom", "Custom"),
    ("SKYBOX_CONFIG_0", "SKYBOX_CONFIG_0", "0x00"),
    ("SKYBOX_CONFIG_1", "SKYBOX_CONFIG_1", "0x01"),
    ("SKYBOX_CONFIG_2", "SKYBOX_CONFIG_2", "0x02"),
    ("SKYBOX_CONFIG_3", "SKYBOX_CONFIG_3", "0x03"),
    ("SKYBOX_CONFIG_4", "SKYBOX_CONFIG_4", "0x04"),
    ("SKYBOX_CONFIG_5", "SKYBOX_CONFIG_5", "0x05"),
    ("SKYBOX_CONFIG_6", "SKYBOX_CONFIG_6", "0x06"),
    ("SKYBOX_CONFIG_7", "SKYBOX_CONFIG_7", "0x07"),
    ("SKYBOX_CONFIG_8", "SKYBOX_CONFIG_8", "0x08"),
    ("SKYBOX_CONFIG_9", "SKYBOX_CONFIG_9", "0x09"),
    ("SKYBOX_CONFIG_10", "SKYBOX_CONFIG_10", "0x0A"),
    ("SKYBOX_CONFIG_11", "SKYBOX_CONFIG_11", "0x0B"),
    ("SKYBOX_CONFIG_12", "SKYBOX_CONFIG_12", "0x0C"),
    ("SKYBOX_CONFIG_13", "SKYBOX_CONFIG_13", "0x0D"),
    ("SKYBOX_CONFIG_14", "SKYBOX_CONFIG_14", "0x0E"),
    ("SKYBOX_CONFIG_15", "SKYBOX_CONFIG_15", "0x0F"),
    ("SKYBOX_CONFIG_16", "SKYBOX_CONFIG_16", "0x10"),
    ("SKYBOX_CONFIG_17", "SKYBOX_CONFIG_17", "0x11"),
    ("SKYBOX_CONFIG_18", "SKYBOX_CONFIG_18", "0x12"),
    ("SKYBOX_CONFIG_19", "SKYBOX_CONFIG_19", "0x13"),
    ("SKYBOX_CONFIG_20", "SKYBOX_CONFIG_20", "0x14"),
    ("SKYBOX_CONFIG_21", "SKYBOX_CONFIG_21", "0x15"),
    ("SKYBOX_CONFIG_22", "SKYBOX_CONFIG_22", "0x16"),
    ("SKYBOX_CONFIG_23", "SKYBOX_CONFIG_23", "0x17"),
    ("SKYBOX_CONFIG_24", "SKYBOX_CONFIG_24", "0x18"),
    ("SKYBOX_CONFIG_25", "SKYBOX_CONFIG_25", "0x19"),
    ("SKYBOX_CONFIG_26", "SKYBOX_CONFIG_26", "0x1A"),
    ("SKYBOX_CONFIG_27", "SKYBOX_CONFIG_27", "0x1B"),
]

ootEnumLinkIdle = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "Default", "Default"),
    ("0x01", "Sneezing", "Sneezing"),
    ("0x02", "Wiping Forehead", "Wiping Forehead"),
    ("0x04", "Yawning", "Yawning"),
    ("0x07", "Gasping For Breath", "Gasping For Breath"),
    ("0x09", "Brandish Sword", "Brandish Sword"),
    ("0x0A", "Adjust Tunic", "Adjust Tunic"),
    ("0xFF", "Hops On Epona", "Hops On Epona"),
]

mm_enum_environment_type = [
    ("Custom", "Custom", "Custom"),
    ("ROOM_ENV_DEFAULT", "Default", "0x00"),
    ("ROOM_ENV_COLD", "Cold", "0x01"),
    ("ROOM_ENV_WARM", "Warm", "0x02"),
    ("ROOM_ENV_HOT", "Hot", "0x03"),
    ("ROOM_ENV_UNK_STRETCH_1", "Unknown Stretch 1", "0x04"),
    ("ROOM_ENV_UNK_STRETCH_2", "Unknown Stretch 2", "0x05"),
    ("ROOM_ENV_UNK_STRETCH_3", "Unknown Stretch 3", "0x06"),
]

# see RoomType enum
ootEnumRoomBehaviour = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "Default", "Default"),
    ("0x01", "Dungeon Behavior (Z-Target, Sun's Song)", "Dungeon Behavior (Z-Target, Sun's Song)"),
    ("0x02", "Disable Backflips/Sidehops", "Disable Backflips/Sidehops"),
    ("0x03", "Disable Color Dither", "Disable Color Dither"),
    ("0x04", "(?) Horse Camera Related", "(?) Horse Camera Related"),
    ("0x05", "Disable Darker Screen Effect (NL/Spins)", "Disable Darker Screen Effect (NL/Spins)"),
]

mm_enum_room_type = [
    ("Custom", "Custom", "Custom"),
    ("ROOM_TYPE_NORMAL", "Normal", "0x00"),
    ("ROOM_TYPE_DUNGEON", "Dungeon", "0x01"),
    ("ROOM_TYPE_INDOORS", "Indoors", "0x02"),
    ("ROOM_TYPE_3", "Type 3", "0x03"),
    ("ROOM_TYPE_4", "Type 4 (Horse related)", "0x04"),
    ("ROOM_TYPE_BOSS", "Boss", "0x05"),
]

ootEnumFloorSetting = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "Default", "Default"),
    ("0x05", "Trigger Respawn", "Trigger Respawn"),
    ("0x06", "Grab Wall", "Grab Wall"),
    ("0x08", "Stop Air Momentum", "Stop Air Momentum"),
    ("0x09", "Fall Instead Of Jumping", "Fall Instead Of Jumping"),
    ("0x0B", "Dive Animation", "Dive Animation"),
    ("0x0C", "Trigger Void", "Trigger Void"),
]

mm_enum_floor_property = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "Default", "FLOOR_PROPERTY_0"),
    ("0x01", "Frontflip Jump Animation", "FLOOR_PROPERTY_1"),
    ("0x02", "Sideflip Jump Animation", "FLOOR_PROPERTY_2"),
    ("0x05", "Trigger Respawn (sets human no mask)", "FLOOR_PROPERTY_5"),
    ("0x06", "Grab Wall", "FLOOR_PROPERTY_6"),
    ("0x07", "Unknown (sets speed to 0)", "FLOOR_PROPERTY_7"),
    ("0x08", "Stop Air Momentum", "FLOOR_PROPERTY_8"),
    ("0x09", "Fall Instead Of Jumping", "FLOOR_PROPERTY_9"),
    ("0x0B", "Dive Animation", "FLOOR_PROPERTY_11"),
    ("0x0C", "Trigger Void", "FLOOR_PROPERTY_12"),
    ("0x0D", "Trigger Void (runs `Player_Action_1`)", "FLOOR_PROPERTY_13"),
]

ootEnumFloorProperty = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "Default", "Default"),
    ("0x01", "Haunted Wasteland Camera", "Haunted Wasteland Camera"),
    ("0x02", "Fire (damages every 6s)", "Fire (damages every 6s)"),
    ("0x03", "Fire (damages every 3s)", "Fire (damages every 3s)"),
    ("0x04", "Shallow Sand", "Shallow Sand"),
    ("0x05", "Slippery", "Slippery"),
    ("0x06", "Ignore Fall Damage", "Ignore Fall Damage"),
    ("0x07", "Quicksand Crossing (Blocks Epona)", "Quicksand Crossing (Epona Uncrossable)"),
    ("0x08", "Jabu Jabu's Belly Floor", "Jabu Jabu's Belly Floor"),
    ("0x09", "Trigger Void", "Trigger Void"),
    ("0x0A", "Stops Air Momentum", "Stops Air Momentum"),
    ("0x0B", "Grotto Exit Animation", "Link Looks Up"),
    ("0x0C", "Quicksand Crossing (Epona Crossable)", "Quicksand Crossing (Epona Crossable)"),
]

mm_enum_floor_type = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "Default", "FLOOR_TYPE_0"),
    ("0x01", "Unused (?)", "FLOOR_TYPE_1"),
    ("0x02", "Fire Damages (burns Player every second)", "FLOOR_TYPE_2"),
    ("0x03", "Fire Damages 2 (burns Player every second)", "FLOOR_TYPE_3"),
    ("0x04", "Shallow Sand", "FLOOR_TYPE_4"),
    ("0x05", "Ice (Slippery)", "FLOOR_TYPE_5"),
    ("0x06", "Ignore Fall Damages", "FLOOR_TYPE_6"),
    ("0x07", "Quicksand (blocks Epona)", "FLOOR_TYPE_7"),
    ("0x08", "Jabu Jabu's Belly Floor (Unused)", "FLOOR_TYPE_8"),
    ("0x09", "Triggers Void", "FLOOR_TYPE_9"),
    ("0x0A", "Stops Air Momentum", "FLOOR_TYPE_10"),
    ("0x0B", "Grotto Exit Animation", "FLOOR_TYPE_11"),
    ("0x0C", "Quicksand (doesn't block Epona)", "FLOOR_TYPE_12"),
    ("0x0D", "Deeper Shallow Sand", "FLOOR_TYPE_13"),
    ("0x0E", "Shallow Snow", "FLOOR_TYPE_14"),
    ("0x0F", "Deeper Shallow Snow", "FLOOR_TYPE_15"),
]

enum_floor_effect = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "Default", "FLOOR_EFFECT_0"),
    ("0x01", "Steep/Slippery Slope", "FLOOR_EFFECT_1"),
    ("0x02", "Walkable (Preserves Exit Flags)", "FLOOR_EFFECT_2"),
]

ootEnumCameraSType = [
    ("Custom", "Custom", "Custom"),
    ("CAM_SET_NONE", "None", "None"),
    ("CAM_SET_NORMAL0", "Normal0", "Normal0"),
    ("CAM_SET_NORMAL1", "Normal1", "Normal1"),
    ("CAM_SET_DUNGEON0", "Dungeon0", "Dungeon0"),
    ("CAM_SET_DUNGEON1", "Dungeon1", "Dungeon1"),
    ("CAM_SET_NORMAL3", "Normal3", "Normal3"),
    ("CAM_SET_HORSE0", "Horse", "Horse"),
    ("CAM_SET_BOSS_GOMA", "Boss_gohma", "Boss_gohma"),
    ("CAM_SET_BOSS_DODO", "Boss_dodongo", "Boss_dodongo"),
    ("CAM_SET_BOSS_BARI", "Boss_barinade", "Boss_barinade"),
    ("CAM_SET_BOSS_FGANON", "Boss_phantom_ganon", "Boss_phantom_ganon"),
    ("CAM_SET_BOSS_BAL", "Boss_volvagia", "Boss_volvagia"),
    ("CAM_SET_BOSS_SHADES", "Boss_bongo", "Boss_bongo"),
    ("CAM_SET_BOSS_MOFA", "Boss_morpha", "Boss_morpha"),
    ("CAM_SET_TWIN0", "Twinrova_platform", "Twinrova_platform"),
    ("CAM_SET_TWIN1", "Twinrova_floor", "Twinrova_floor"),
    ("CAM_SET_BOSS_GANON1", "Boss_ganondorf", "Boss_ganondorf"),
    ("CAM_SET_BOSS_GANON2", "Boss_ganon", "Boss_ganon"),
    ("CAM_SET_TOWER0", "Tower_climb", "Tower_climb"),
    ("CAM_SET_TOWER1", "Tower_unused", "Tower_unused"),
    ("CAM_SET_FIXED0", "Market_balcony", "Market_balcony"),
    ("CAM_SET_FIXED1", "Chu_bowling", "Chu_bowling"),
    ("CAM_SET_CIRCLE0", "Pivot_crawlspace", "Pivot_crawlspace"),
    ("CAM_SET_CIRCLE2", "Pivot_shop_browsing", "Pivot_shop_browsing"),
    ("CAM_SET_CIRCLE3", "Pivot_in_front", "Pivot_in_front"),
    ("CAM_SET_PREREND0", "Prerend_fixed", "Prerend_fixed"),
    ("CAM_SET_PREREND1", "Prerend_pivot", "Prerend_pivot"),
    ("CAM_SET_PREREND3", "Prerend_side_scroll", "Prerend_side_scroll"),
    ("CAM_SET_DOOR0", "Door0", "Door0"),
    ("CAM_SET_DOORC", "Doorc", "Doorc"),
    ("CAM_SET_RAIL3", "Crawlspace", "Crawlspace"),
    ("CAM_SET_START0", "Start0", "Start0"),
    ("CAM_SET_START1", "Start1", "Start1"),
    ("CAM_SET_FREE0", "Free0", "Free0"),
    ("CAM_SET_FREE2", "Free2", "Free2"),
    ("CAM_SET_CIRCLE4", "Pivot_corner", "Pivot_corner"),
    ("CAM_SET_CIRCLE5", "Pivot_water_surface", "Pivot_water_surface"),
    ("CAM_SET_DEMO0", "Cs_0", "Cs_0"),
    ("CAM_SET_DEMO1", "Twisted_Hallway", "Twisted_Hallway"),
    ("CAM_SET_MORI1", "Forest_birds_eye", "Forest_birds_eye"),
    ("CAM_SET_ITEM0", "Slow_chest_cs", "Slow_chest_cs"),
    ("CAM_SET_ITEM1", "Item_unused", "Item_unused"),
    ("CAM_SET_DEMO3", "Cs_3", "Cs_3"),
    ("CAM_SET_DEMO4", "Cs_attention", "Cs_attention"),
    ("CAM_SET_UFOBEAN", "Bean_generic", "Bean_generic"),
    ("CAM_SET_LIFTBEAN", "Bean_lost_woods", "Bean_lost_woods"),
    ("CAM_SET_SCENE0", "Scene_unused", "Scene_unused"),
    ("CAM_SET_SCENE1", "Scene_transition", "Scene_transition"),
    ("CAM_SET_HIDAN1", "Fire_platform", "Fire_platform"),
    ("CAM_SET_HIDAN2", "Fire_staircase", "Fire_staircase"),
    ("CAM_SET_MORI2", "Forest_unused", "Forest_unused"),
    ("CAM_SET_MORI3", "Defeat_poe", "Defeat_poe"),
    ("CAM_SET_TAKO", "Big_octo", "Big_octo"),
    ("CAM_SET_SPOT05A", "Meadow_birds_eye", "Meadow_birds_eye"),
    ("CAM_SET_SPOT05B", "Meadow_unused", "Meadow_unused"),
    ("CAM_SET_HIDAN3", "Fire_birds_eye", "Fire_birds_eye"),
    ("CAM_SET_ITEM2", "Turn_around", "Turn_around"),
    ("CAM_SET_CIRCLE6", "Pivot_vertical", "Pivot_vertical"),
    ("CAM_SET_NORMAL2", "Normal2", "Normal2"),
    ("CAM_SET_FISHING", "Fishing", "Fishing"),
    ("CAM_SET_DEMOC", "Cs_c", "Cs_c"),
    ("CAM_SET_UO_FIBER", "Jabu_tentacle", "Jabu_tentacle"),
    ("CAM_SET_DUNGEON2", "Dungeon2", "Dungeon2"),
    ("CAM_SET_TEPPEN", "Directed_yaw", "Directed_yaw"),
    ("CAM_SET_CIRCLE7", "Pivot_from_side", "Pivot_from_side"),
    ("CAM_SET_NORMAL4", "Normal4", "Normal4"),
]

mm_enum_camera_setting_type = [
    ("Custom", "Custom", "Custom"),
    ("CAM_SET_NONE", "None", "None"),
    ("CAM_SET_NORMAL0", "Normal0", "Generic camera 0, used in various places 'NORMAL0'"),
    ("CAM_SET_NORMAL3", "Normal3", "Generic camera 3, used in various places 'NORMAL3'"),
    (
        "CAM_SET_PIVOT_DIVING",
        "Pivot_Diving",
        "Player diving from the surface of the water to underwater not as zora 'CIRCLE5'",
    ),
    ("CAM_SET_HORSE", "Horse", "Reiding a horse 'HORSE0'"),
    (
        "CAM_SET_ZORA_DIVING",
        "Zora_Diving",
        "Parallel's Pivot Diving, but as Zora. However, Zora does not dive like a human. So this setting appears to not be used 'ZORA0'",
    ),
    (
        "CAM_SET_PREREND_FIXED",
        "Prerend_Fixed",
        "Unused remnant of OoT: camera is fixed in position and rotation 'PREREND0'",
    ),
    (
        "CAM_SET_PREREND_PIVOT",
        "Prerend_Pivot",
        "Unused remnant of OoT: Camera is fixed in position with fixed pitch, but is free to rotate in the yaw direction 360 degrees 'PREREND1'",
    ),
    (
        "CAM_SET_DOORC",
        "Doorc",
        "Generic room door transitions, camera moves and follows player as the door is open and closed 'DOORC'",
    ),
    ("CAM_SET_DEMO0", "Demo0", "Unknown, possibly related to treasure chest game as goron? 'DEMO0'"),
    ("CAM_SET_FREE0", "Free0", "Free Camera, manual control is given, no auto-updating eye or at 'FREE0'"),
    ("CAM_SET_BIRDS_EYE_VIEW_0", "Birds_Eye_View_0", "Appears unused. Camera is a top-down view 'FUKAN0'"),
    ("CAM_SET_NORMAL1", "Normal1", "Generic camera 1, used in various places 'NORMAL1'"),
    (
        "CAM_SET_NANAME",
        "Naname",
        "Unknown, slanted or tilted. Behaves identical to Normal0 except with added roll 'NANAME'",
    ),
    ("CAM_SET_CIRCLE0", "Circle0", "Used in Curiosity Shop, Pirates Fortress, Mayor's Residence 'CIRCLE0'"),
    ("CAM_SET_FIXED0", "Fixed0", "Used in Sakon's Hideout puzzle rooms, milk bar stage 'FIXED0'"),
    ("CAM_SET_SPIRAL_DOOR", "Spiral_Door", "Exiting a Spiral Staircase 'SPIRAL'"),
    ("CAM_SET_DUNGEON0", "Dungeon0", "Generic dungeon camera 0, used in various places 'DUNGEON0'"),
    (
        "CAM_SET_ITEM0",
        "Item0",
        "Getting an item and holding it above Player's head (from small chest, freestanding, npc, ...) 'ITEM0'",
    ),
    ("CAM_SET_ITEM1", "Item1", "Looking at player while playing the ocarina 'ITEM1'"),
    ("CAM_SET_ITEM2", "Item2", "Bottles: drinking, releasing fairy, dropping fish 'ITEM2'"),
    ("CAM_SET_ITEM3", "Item3", "Bottles: catching fish or bugs, showing an item 'ITEM3'"),
    ("CAM_SET_NAVI", "Navi", "Song of Soaring, variations of playing Song of Time 'NAVI'"),
    ("CAM_SET_WARP_PAD_MOON", "Warp_Pad_Moon", "Warp circles from Goron Trial on the moon 'WARP0'"),
    ("CAM_SET_DEATH", "Death", "Player death animation when health goes to 0 'DEATH'"),
    ("CAM_SET_REBIRTH", "Rebirth", "Unknown set with camDataId = -9 (it's not being revived by a fairy) 'REBIRTH'"),
    (
        "CAM_SET_LONG_CHEST_OPENING",
        "Long_Chest_Opening",
        "Long cutscene when opening a big chest with a major item 'TREASURE'",
    ),
    ("CAM_SET_MASK_TRANSFORMATION", "Mask_Transformation", "Putting on a transformation mask 'TRANSFORM'"),
    ("CAM_SET_ATTENTION", "Attention", "Unknown, set with camDataId = -15 'ATTENTION'"),
    ("CAM_SET_WARP_PAD_ENTRANCE", "Warp_Pad_Entrance", "Warp pad from start of a dungeon to the boss-room 'WARP1'"),
    ("CAM_SET_DUNGEON1", "Dungeon1", "Generic dungeon camera 1, used in various places 'DUNGEON1'"),
    (
        "CAM_SET_FIXED1",
        "Fixed1",
        "Fixes camera in place, used in various places eg. entering Stock Pot Inn, hiting a switch, giving witch a red potion, shop browsing 'FIXED1'",
    ),
    (
        "CAM_SET_FIXED2",
        "Fixed2",
        "Used in Pinnacle Rock after defeating Sea Monsters, and by Tatl in Fortress 'FIXED2'",
    ),
    ("CAM_SET_MAZE", "Maze", "Unused. Set to use Camera_Parallel2(), which is only Camera_Noop() 'MAZE'"),
    (
        "CAM_SET_REMOTEBOMB",
        "Remotebomb",
        "Unused. Set to use Camera_Parallel2(), which is only Camera_Noop(). But also related to Play_ChangeCameraSetting? 'REMOTEBOMB'",
    ),
    ("CAM_SET_CIRCLE1", "Circle1", "Unknown 'CIRCLE1'"),
    (
        "CAM_SET_CIRCLE2",
        "Circle2",
        "Looking at far-away NPCs eg. Garo in Road to Ikana, Hungry Goron, Tingle 'CIRCLE2'",
    ),
    (
        "CAM_SET_CIRCLE3",
        "Circle3",
        "Used in curiosity shop, goron racetrack, final room in Sakon's hideout, other places 'CIRCLE3'",
    ),
    ("CAM_SET_CIRCLE4", "Circle4", "Used during the races on the doggy racetrack 'CIRCLE4'"),
    ("CAM_SET_FIXED3", "Fixed3", "Used in Stock Pot Inn Toilet and Tatl cutscene after woodfall 'FIXED3'"),
    (
        "CAM_SET_TOWER_ASCENT",
        "Tower_Ascent",
        "Various climbing structures (Snowhead climb to the temple entrance) 'TOWER0'",
    ),
    ("CAM_SET_PARALLEL0", "Parallel0", "Unknown 'PARALLEL0'"),
    ("CAM_SET_NORMALD", "Normald", "Unknown, set with camDataId = -20 'NORMALD'"),
    ("CAM_SET_SUBJECTD", "Subjectd", "Unknown, set with camDataId = -21 'SUBJECTD'"),
    (
        "CAM_SET_START0",
        "Start0",
        "Entering a room, either Dawn of a New Day reload, or entering a door where the camera is fixed on the other end 'START0'",
    ),
    (
        "CAM_SET_START2",
        "Start2",
        "Entering a scene, camera is put at a low angle eg. Grottos, Deku Palace, Stock Pot Inn 'START2'",
    ),
    ("CAM_SET_STOP0", "Stop0", "Called in z_play 'STOP0'"),
    ("CAM_SET_BOAT_CRUISE", "Boat_Cruise", " Koume's boat cruise 'JCRUISING'"),
    (
        "CAM_SET_VERTICAL_CLIMB",
        "Vertical_Climb",
        "Large vertical climbs, such as Mountain Village wall or Pirates Fortress ladder. 'CLIMBMAZE'",
    ),
    ("CAM_SET_SIDED", "Sided", "Unknown, set with camDataId = -24 'SIDED'"),
    ("CAM_SET_DUNGEON2", "Dungeon2", "Generic dungeon camera 2, used in various places 'DUNGEON2'"),
    ("CAM_SET_BOSS_ODOLWA", "Boss_Odolwa", "Odolwa's Lair, also used in GBT entrance: 'BOSS_SHIGE'"),
    ("CAM_SET_KEEPBACK", "Keepback", "Unknown. Possibly related to climbing something? 'KEEPBACK'"),
    ("CAM_SET_CIRCLE6", "Circle6", "Used in select regions from Ikana 'CIRCLE6'"),
    ("CAM_SET_CIRCLE7", "Circle7", "Unknown 'CIRCLE7'"),
    ("CAM_SET_MINI_BOSS", "Mini_Boss", "Used during the various minibosses of the 'CHUBOSS'"),
    ("CAM_SET_RFIXED1", "Rfixed1", "Talking to Koume stuck on the floor in woods of mystery 'RFIXED1'"),
    (
        "CAM_SET_TREASURE_CHEST_MINIGAME",
        "Treasure_Chest_Minigame",
        "Treasure Chest Shop in East Clock Town, minigame location 'TRESURE1'",
    ),
    ("CAM_SET_HONEY_AND_DARLING_1", "Honey_And_Darling_1", "Honey and Darling Minigames 'BOMBBASKET'"),
    (
        "CAM_SET_CIRCLE8",
        "Circle8",
        "Used by Stone Tower moving platforms, Falling eggs in Marine Lab, Bugs into soilpatch cutscene 'CIRCLE8'",
    ),
    (
        "CAM_SET_BIRDS_EYE_VIEW_1",
        "Birds_Eye_View_1",
        "Camera is a top-down view. Used in Fisherman's minigame and Deku Palace 'FUKAN1'",
    ),
    ("CAM_SET_DUNGEON3", "Dungeon3", "Generic dungeon camera 3, used in various places 'DUNGEON3'"),
    ("CAM_SET_TELESCOPE", "Telescope", "Observatory telescope and Curiosity Shop Peep-Hole 'TELESCOPE'"),
    ("CAM_SET_ROOM0", "Room0", "Certain rooms eg. inside the clock tower 'ROOM0'"),
    ("CAM_SET_RCIRC0", "Rcirc0", "Used by a few NPC cutscenes, focus close on the NPC 'RCIRC0'"),
    ("CAM_SET_CIRCLE9", "Circle9", "Used by Sakon Hideout entrance and Deku Palace Maze 'CIRCLE9'"),
    ("CAM_SET_ONTHEPOLE", "Onthepole", "Somewhere in Snowhead Temple and Woodfall Temple 'ONTHEPOLE'"),
    (
        "CAM_SET_INBUSH",
        "Inbush",
        "Various bush environments eg. grottos, Swamp Spider House, Termina Field grass bushes, Deku Palace near bean 'INBUSH'",
    ),
    ("CAM_SET_BOSS_MAJORA", "Boss_Majora", "Majora's Lair: 'BOSS_LAST'"),
    ("CAM_SET_BOSS_TWINMOLD", "Boss_Twinmold", "Twinmold's Lair: 'BOSS_INI'"),
    ("CAM_SET_BOSS_GOHT", "Boss_Goht", "Goht's Lair: 'BOSS_HAK'"),
    ("CAM_SET_BOSS_GYORG", "Boss_Gyorg", "Gyorg's Lair: 'BOSS_KON'"),
    ("CAM_SET_CONNECT0", "Connect0", "Smoothly and gradually return camera to Player after a cutscene 'CONNECT0'"),
    ("CAM_SET_PINNACLE_ROCK", "Pinnacle_Rock", "Pinnacle Rock pit 'MORAY'"),
    ("CAM_SET_NORMAL2", "Normal2", "Generic camera 2, used in various places 'NORMAL2'"),
    ("CAM_SET_HONEY_AND_DARLING_2", "Honey_And_Darling_2", "'BOMBBOWL'"),
    ("CAM_SET_CIRCLEA", "Circlea", "Unknown, Circle 10 'CIRCLEA'"),
    ("CAM_SET_WHIRLPOOL", "Whirlpool", "Great Bay Temple Central Room Whirlpool 'WHIRLPOOL'"),
    ("CAM_SET_CUCCO_SHACK", "Cucco_Shack", "'KOKKOGAME'"),
    ("CAM_SET_GIANT", "Giant", "Giants Mask in Twinmold's Lair 'GIANT'"),
    ("CAM_SET_SCENE0", "Scene0", "Entering doors to a new scene 'SCENE0'"),
    ("CAM_SET_ROOM1", "Room1", "Certain rooms eg. some rooms in Stock Pot Inn 'ROOM1'"),
    ("CAM_SET_WATER2", "Water2", "Swimming as Zora in Great Bay Temple 'WATER2'"),
    ("CAM_SET_WOODFALL_SWAMP", "Woodfall_Swamp", "Woodfall inside the swamp, but not on the platforms, 'SOKONASI'"),
    ("CAM_SET_FORCEKEEP", "Forcekeep", "Unknown 'FORCEKEEP'"),
    ("CAM_SET_PARALLEL1", "Parallel1", "Unknown 'PARALLEL1'"),
    ("CAM_SET_START1", "Start1", "Used when entering the lens cave 'START1'"),
    ("CAM_SET_ROOM2", "Room2", "Certain rooms eg. Deku King's Chamber, Ocean Spider House 'ROOM2'"),
    ("CAM_SET_NORMAL4", "Normal4", "Generic camera 4, used in Ikana Graveyard 'NORMAL4'"),
    ("CAM_SET_ELEGY_SHELL", "Elegy_Shell", "cutscene after playing elegy of emptyness and spawning a shell 'SHELL'"),
    ("CAM_SET_DUNGEON4", "Dungeon4", "Used in Pirates Fortress Interior, hidden room near hookshot 'DUNGEON4'"),
]

# ---


@dataclass
class Z64_Data:
    """Contains data related to OoT, like actors or objects"""

    def __init__(self, game: str):
        self.game = game
        self.update(None, game, True)  # forcing the update as we're in the init function

        self.enum_floor_effect = enum_floor_effect

    def update(self, context: Optional[Context], game: Optional[str], force: bool = False):
        from .enum_data import Z64_EnumData
        from .object_data import Z64_ObjectData
        from .actor_data import Z64_ActorData

        if context is not None:
            next_game = context.scene.gameEditorMode
        elif game is not None:
            next_game = game
        else:
            raise ValueError("ERROR: invalid values for context and game")

        # don't update if the game is the same (or we don't want to force one)
        if not force and next_game == self.game:
            return

        self.game = next_game
        self.enumData = Z64_EnumData(self.game)
        self.objectData = Z64_ObjectData(self.game)
        self.actorData = Z64_ActorData(self.game)

        if self.game == "OOT":
            self.cs_index_start = 4
            self.ootEnumMusicSeq = ootEnumMusicSeq
            self.ootEnumNightSeq = ootEnumNightSeq
            self.ootEnumGlobalObject = ootEnumGlobalObject
            self.ootEnumSkybox = ootEnumSkybox
            self.ootEnumCloudiness = ootEnumCloudiness
            self.ootEnumLinkIdle = ootEnumLinkIdle
            self.ootEnumRoomBehaviour = ootEnumRoomBehaviour
            self.ootEnumDrawConfig = ootEnumDrawConfig
            self.ootEnumFloorSetting = ootEnumFloorSetting
            self.ootEnumFloorProperty = ootEnumFloorProperty
            self.ootEnumCollisionSound = ootEnumCollisionSound
            self.ootEnumCameraSType = ootEnumCameraSType
        elif self.game == "MM":
            self.cs_index_start = 1
            self.ootEnumMusicSeq = enum_seq_id
            self.ootEnumNightSeq = enum_ambiance_id
            self.ootEnumGlobalObject = mm_enum_global_object
            self.ootEnumSkybox = mm_enum_skybox
            self.ootEnumCloudiness = mm_enum_skybox_config
            self.ootEnumLinkIdle = mm_enum_environment_type
            self.ootEnumRoomBehaviour = mm_enum_room_type
            self.ootEnumDrawConfig = mm_enum_draw_config
            self.ootEnumFloorSetting = mm_enum_floor_property
            self.ootEnumFloorProperty = mm_enum_floor_type
            self.ootEnumCollisionSound = mm_enum_surface_material
            self.ootEnumCameraSType = mm_enum_camera_setting_type
        else:
            raise ValueError(f"ERROR: unsupported game {repr(self.game)}")

    def get_enum(self, context, prop_name: str):
        self.update(context, None)

        match prop_name:
            case "globalObject":
                return self.ootEnumGlobalObject
            case "skyboxID":
                return self.ootEnumSkybox
            case "skyboxCloudiness":
                return self.ootEnumCloudiness
            case "musicSeq":
                return self.ootEnumMusicSeq
            case "nightSeq":
                return self.ootEnumNightSeq
            case "roomBehaviour":
                return self.ootEnumRoomBehaviour
            case "linkIdleMode":
                return self.ootEnumLinkIdle
            case "drawConfig":
                return self.ootEnumDrawConfig
            case "floorSetting":
                return self.ootEnumFloorSetting
            case "floorProperty":
                return self.ootEnumFloorProperty
            case "sound":
                return self.ootEnumCollisionSound
            case "camSType":
                return self.ootEnumCameraSType
            case "actor_id":
                return self.actorData.ootEnumActorID
            case "chest_content":
                return self.actorData.ootEnumChestContent
            case "navi_msg_id":
                return self.actorData.ootEnumNaviMessageData
            case "collectibles":
                return self.actorData.ootEnumCollectibleItems
            case "objectKey":
                return self.objectData.ootEnumObjectKey
            case "csDestination":
                return self.enumData.ootEnumCsDestination
            case "seqId":
                return self.enumData.ootEnumSeqId
            case "playerCueID":
                return self.enumData.ootEnumCsPlayerCueId
            case "ocarinaAction":
                return self.enumData.ootEnumOcarinaSongActionId
            case "csTextType":
                return self.enumData.ootEnumCsTextType
            case "csSeqPlayer":
                return self.enumData.ootEnumCsFadeOutSeqPlayer
            case "csMiscType":
                return self.enumData.ootEnumCsMiscType
            case "transitionType":
                return self.enumData.ootEnumCsTransitionType
            case _:
                raise ValueError(f"ERROR: unknown value {repr(prop_name)}")

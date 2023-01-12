ootEnumCSTextboxTypeEntryC = {
    "Text": "CS_TEXT",
    "None": "CS_TEXT_NONE",
    "LearnSong": "CS_TEXT_OCARINA_ACTION",
}

ootEnumCSListTypeListC = {
    "Textbox": "CS_TEXT_LIST",
    "FX": "CS_TRANSITION",
    "Lighting": "CS_LIGHT_SETTING_LIST",
    "Time": "CS_TIME_LIST",
    "PlayBGM": "CS_START_SEQ_LIST",
    "StopBGM": "CS_STOP_SEQ_LIST",
    "FadeBGM": "CS_FADE_OUT_SEQ_LIST",
    "Misc": "CS_MISC_LIST",
    "0x09": "CS_RUMBLE_CONTROLLER_LIST",
}

ootEnumCSListTypeEntryC = {
    "Textbox": None,  # special case
    "FX": None,  # no list entries
    "Lighting": "CS_LIGHT_SETTING",
    "Time": "CS_TIME",
    "PlayBGM": "CS_START_SEQ",
    "StopBGM": "CS_STOP_SEQ",
    "FadeBGM": "CS_FADE_OUT_SEQ",
    "Misc": "CS_MISC",
    "0x09": "CS_RUMBLE_CONTROLLER",
}

ootEnumCSWriteType = [
    ("Custom", "Custom", "Provide the name of a cutscene header variable"),
    ("Embedded", "Embedded", "Cutscene data is within scene header (deprecated)"),
    ("Object", "Object", "Reference to Blender object representing cutscene"),
]

ootEnumCSListType = [
    ("Textbox", "Textbox", "Textbox"),
    ("FX", "Transition", "Transition"),
    ("Lighting", "Lighting", "Lighting"),
    ("Time", "Time", "Time"),
    ("PlayBGM", "Play BGM", "Play BGM"),
    ("StopBGM", "Stop BGM", "Stop BGM"),
    ("FadeBGM", "Fade BGM", "Fade BGM"),
    ("Misc", "Misc", "Misc"),
    ("0x09", "Rumble Controller", "Rumble Controller"),
]

ootEnumCSListTypeIcons = [
    "ALIGN_BOTTOM",
    "COLORSET_10_VEC",
    "LIGHT_SUN",
    "TIME",
    "PLAY",
    "SNAP_FACE",
    "IPO_EASE_IN_OUT",
    "OPTIONS",
    "OUTLINER_OB_FORCE_FIELD",
]

ootEnumCSTextboxType = [("Text", "Text", "Text"), ("None", "None", "None"), ("LearnSong", "Learn Song", "Learn Song")]

ootEnumCSTextboxTypeIcons = ["FILE_TEXT", "HIDE_ON", "FILE_SOUND"]

ootEnumCSTransitionType = [
    # see https://github.com/zeldaret/oot/blob/b4c97ce17eb35329b4a7e3d98d7f06d558683f6d/include/z64cutscene.h#L219-L233
    ("Custom", "Custom", "Custom"),
    ("CS_TRANS_GRAY_FILL_IN", "Gray Fill In", "Gray Fill In"),
    ("CS_TRANS_BLUE_FILL_IN", "Blue Fill In", "Blue Fill In"),
    ("CS_TRANS_RED_FILL_OUT", "Red Fill Out", "Red Fill Out"),
    ("CS_TRANS_GREEN_FILL_OUT", "Green Fill Out", "Green Fill Out"),
    ("CS_TRANS_GRAY_FILL_OUT", "Gray Fill Out", "Gray Fill Out"),
    ("CS_TRANS_BLUE_FILL_OUT", "Blue Fill Out", "Blue Fill Out"),
    ("CS_TRANS_RED_FILL_IN", "Red Fill In", "Red Fill In"),
    ("CS_TRANS_GREEN_FILL_IN", "Green Fill In", "Green Fill In"),
    ("CS_TRANS_TRIGGER_INSTANCE", "Trigger Instance", "Trigger Instance"),
    ("CS_TRANS_BLACK_FILL_OUT", "Black Fill Out", "Black Fill Out"),
    ("CS_TRANS_BLACK_FILL_IN", "Black Fill In", "Black Fill In"),
    ("CS_TRANS_BLACK_FILL_OUT_TO_HALF", "Black Fill Out To Half", "Black Fill Out To Half"),
    ("CS_TRANS_BLACK_FILL_IN_FROM_HALF", "Black Fill In From Half", "Black Fill In From Half"),
]

ootEnumCSMiscType = [
    # see https://github.com/zeldaret/oot/blob/b4c97ce17eb35329b4a7e3d98d7f06d558683f6d/include/z64cutscene.h#L167-L204
    ("Custom", "Custom", "Custom"),
    ("CS_MISC_RAIN", " Rain", " Rain"),
    ("CS_MISC_LIGHTNING", " Lightning", " Lightning"),
    ("CS_MISC_SET_CSFLAG_0", " Set CS Flag 0", " Set CS Flag 0"),
    ("CS_MISC_LIFT_FOG", " Lift Fog", " Lift Fog"),
    ("CS_MISC_CLOUDY_SKY", " Cloudy Sky", " Cloudy Sky"),
    ("CS_MISC_FADE_KOKIRI_GRASS_ENV_ALPHA", " Fade Kokiri Grass Env Alpha", " Fade Kokiri Grass Env Alpha"),
    ("CS_MISC_SNOW", " Snow", " Snow"),
    ("CS_MISC_SET_CSFLAG_1", " Set CS Flag 1", " Set CS Flag 1"),
    ("CS_MISC_DEKU_TREE_DEATH", " Deku Tree Death", " Deku Tree Death"),
    ("CS_MISC_STOP_CUTSCENE", " Stop Cutscene", " Stop Cutscene"),
    ("CS_MISC_TRIFORCE_FLASH", " Triforce Flash", " Triforce Flash"),
    ("CS_MISC_SET_LOCKED_VIEWPOINT", " Set Locked Viewpoint", " Set Locked Viewpoint"),
    ("CS_MISC_SHOW_TITLE_CARD", " Show Title Card", " Show Title Card"),
    ("CS_MISC_QUAKE_START", " Quake Start", " Quake Start"),
    ("CS_MISC_QUAKE_STOP", " Quake Stop", " Quake Stop"),
    ("CS_MISC_STOP_STORM_AND_ADVANCE_TO_DAY", " Stop Storm And Advance To Day", " Stop Storm And Advance To Day"),
    ("CS_MISC_SET_FLAG_FAST_WINDMILL", " Set Flag Fast Windmill", " Set Flag Fast Windmill"),
    ("CS_MISC_SET_FLAG_WELL_DRAINED", " Set Flag Well Drained", " Set Flag Well Drained"),
    ("CS_MISC_SET_FLAG_LAKE_HYLIA_RESTORED", " Set Flag Lake Hylia Restored", " Set Flag Lake Hylia Restored"),
    ("CS_MISC_VISMONO_BLACK_AND_WHITE", " Vismono Black And White", " Vismono Black And White"),
    ("CS_MISC_VISMONO_SEPIA", " Vismono Sepia", " Vismono Sepia"),
    ("CS_MISC_HIDE_ROOM", " Hide Room", " Hide Room"),
    ("CS_MISC_TIME_ADVANCE_TO_NIGHT", " Time Advance To Night", " Time Advance To Night"),
    ("CS_MISC_SET_TIME_BASED_LIGHT_SETTING", " Set Time Based Light Setting", " Set Time Based Light Setting"),
    ("CS_MISC_RED_PULSATING_LIGHTS", " Red Pulsating Lights", " Red Pulsating Lights"),
    ("CS_MISC_HALT_ALL_ACTORS", " Halt All Actors", " Halt All Actors"),
    ("CS_MISC_RESUME_ALL_ACTORS", " Resume All Actors", " Resume All Actors"),
    ("CS_MISC_SET_CSFLAG_3", " Set CS Flag 3", " Set CS Flag 3"),
    ("CS_MISC_SET_CSFLAG_4", " Set CS Flag 4", " Set CS Flag 4"),
    ("CS_MISC_SANDSTORM_FILL", " Sandstorm Fill", " Sandstorm Fill"),
    ("CS_MISC_SUNSSONG_START", " Sun's Song Start", " Sunssong Start"),
    ("CS_MISC_FREEZE_TIME", " Freeze Time", " Freeze Time"),
    ("CS_MISC_LONG_SCARECROW_SONG", " Long Scarecrow Song", " Long Scarecrow Song"),
]

ootEnumCSDestinationType = [
    # see https://github.com/zeldaret/oot/blob/b4c97ce17eb35329b4a7e3d98d7f06d558683f6d/include/z64cutscene.h#L235-L356
    ("Custom", "Custom", "Custom"),
    ("CS_DEST_CUTSCENE_MAP_GANON_HORSE", "Cutscene Map Ganon Horse", "Cutscene Map Ganon Horse"),
    ("CS_DEST_CUTSCENE_MAP_THREE_GODDESSES", "Cutscene Map Three Goddesses", "Cutscene Map Three Goddesses"),
    ("CS_DEST_GERUDO_VALLEY_DIN_PART_1", "Gerudo Valley Din Part 1", "Gerudo Valley Din Part 1"),
    ("CS_DEST_DEATH_MOUNTAIN_TRAIL_NAYRU", "Death Mountain Trail Nayru", "Death Mountain Trail Nayru"),
    ("CS_DEST_KOKIRI_FOREST_FARORE", "Kokiri Forest Farore", "Kokiri Forest Farore"),
    ("CS_DEST_CUTSCENE_MAP_TRIFORCE_CREATION", "Cutscene Map Triforce Creation", "Cutscene Map Triforce Creation"),
    ("CS_DEST_KOKIRI_FOREST_RECEIVE_KOKIRI_EMERALD", "Kokiri Forest Receive Kokiri Emerald", "Kokiri Forest Receive Kokiri Emerald"),
    ("CS_DEST_TEMPLE_OF_TIME_FROM_MASTER_SWORD", "Temple Of Time From Master Sword", "Temple Of Time From Master Sword"),
    ("CS_DEST_GERUDO_VALLEY_DIN_PART_2", "Gerudo Valley Din Part 2", "Gerudo Valley Din Part 2"),
    ("CS_DEST_LINKS_HOUSE_INTRO", "Links House Intro", "Links House Intro"),
    ("CS_DEST_KOKIRI_FOREST_INTRO", "Kokiri Forest Intro", "Kokiri Forest Intro"),
    ("CS_DEST_DEATH_MOUNTAIN_TRAIL_FROM_GORON_RUBY", "Death Mountain Trail From Goron Ruby", "Death Mountain Trail From Goron Ruby"),
    ("CS_DEST_ZORAS_FOUNTAIN_FROM_ZORAS_SAPPHIRE", "Zoras Fountain From Zoras Sapphire", "Zoras Fountain From Zoras Sapphire"),
    ("CS_DEST_KOKIRI_FOREST_FROM_KOKIRI_EMERALD", "Kokiri Forest From Kokiri Emerald", "Kokiri Forest From Kokiri Emerald"),
    ("CS_DEST_TEMPLE_OF_TIME_KOKIRI_EMERALD_RESTORED", "Temple Of Time Kokiri Emerald Restored", "Temple Of Time Kokiri Emerald Restored"),
    ("CS_DEST_TEMPLE_OF_TIME_GORON_RUBY_RESTORED", "Temple Of Time Goron Ruby Restored", "Temple Of Time Goron Ruby Restored"),
    ("CS_DEST_TEMPLE_OF_TIME_ZORAS_SAPPHIRE_RESTORED", "Temple Of Time Zoras Sapphire Restored", "Temple Of Time Zoras Sapphire Restored"),
    ("CS_DEST_TEMPLE_OF_TIME_AFTER_LIGHT_MEDALLION", "Temple Of Time After Light Medallion", "Temple Of Time After Light Medallion"),
    ("CS_DEST_DEATH_MOUNTAIN_TRAIL", "Death Mountain Trail", "Death Mountain Trail"),
    ("CS_DEST_LAKE_HYLIA_WATER_RESTORED", "Lake Hylia Water Restored", "Lake Hylia Water Restored"),
    ("CS_DEST_DESERT_COLOSSUS_REQUIEM", "Desert Colossus Requiem", "Desert Colossus Requiem"),
    ("CS_DEST_CUTSCENE_MAP_GANONDORF_DEFEATED_CREDITS", "Cutscene Map Ganondorf Defeated Credits", "Cutscene Map Ganondorf Defeated Credits"),
    ("CS_DEST_JABU_JABU", "Jabu Jabu", "Jabu Jabu"),
    ("CS_DEST_CHAMBER_OF_SAGES_LIGHT_MEDALLION", "Chamber Of Sages Light Medallion", "Chamber Of Sages Light Medallion"),
    ("CS_DEST_TEMPLE_OF_TIME_KOKIRI_EMERALD_RESTORED_2", "Temple Of Time Kokiri Emerald Restored 2", "Temple Of Time Kokiri Emerald Restored 2"),
    ("CS_DEST_TEMPLE_OF_TIME_GORON_RUBY_RESTORED_2", "Temple Of Time Goron Ruby Restored 2", "Temple Of Time Goron Ruby Restored 2"),
    ("CS_DEST_TEMPLE_OF_TIME_ZORAS_SAPPHIRE_RESTORED_2", "Temple Of Time Zoras Sapphire Restored 2", "Temple Of Time Zoras Sapphire Restored 2"),
    ("CS_DEST_CHAMBER_OF_SAGES_FOREST_MEDALLION", "Chamber Of Sages Forest Medallion", "Chamber Of Sages Forest Medallion"),
    ("CS_DEST_CHAMBER_OF_SAGES_FIRE_MEDALLION", "Chamber Of Sages Fire Medallion", "Chamber Of Sages Fire Medallion"),
    ("CS_DEST_CHAMBER_OF_SAGES_WATER_MEDALLION", "Chamber Of Sages Water Medallion", "Chamber Of Sages Water Medallion"),
    ("CS_DEST_HYRULE_FIELD_FLASHBACK", "Hyrule Field Flashback", "Hyrule Field Flashback"),
    ("CS_DEST_HYRULE_FIELD_FROM_ZELDA_ESCAPE", "Hyrule Field From Zelda Escape", "Hyrule Field From Zelda Escape"),
    ("CS_DEST_CUTSCENE_MAP_GANONDORF_FROM_MASTER_SWORD", "Cutscene Map Ganondorf From Master Sword", "Cutscene Map Ganondorf From Master Sword"),
    ("CS_DEST_HYRULE_FIELD_INTRO_DREAM", "Hyrule Field Intro Dream", "Hyrule Field Intro Dream"),
    ("CS_DEST_CUTSCENE_MAP_SHEIKAH_LEGEND", "Cutscene Map Sheikah Legend", "Cutscene Map Sheikah Legend"),
    ("CS_DEST_TEMPLE_OF_TIME_ZELDA_REVEAL", "Temple Of Time Zelda Reveal", "Temple Of Time Zelda Reveal"),
    ("CS_DEST_TEMPLE_OF_TIME_GET_LIGHT_ARROWS", "Temple Of Time Get Light Arrows", "Temple Of Time Get Light Arrows"),
    ("CS_DEST_LAKE_HYLIA_FROM_LAKE_RESTORED", "Lake Hylia From Lake Restored", "Lake Hylia From Lake Restored"),
    ("CS_DEST_KAKARIKO_VILLAGE_DRAIN_WELL", "Kakariko Village Drain Well", "Kakariko Village Drain Well"),
    ("CS_DEST_WINDMILL_FROM_WELL_DRAINED", "Windmill From Well Drained", "Windmill From Well Drained"),
    ("CS_DEST_TEMPLE_OF_TIME_FROM_ALL_STONES_RESTORED", "Temple Of Time From All Stones Restored", "Temple Of Time From All Stones Restored"),
    ("CS_DEST_TEMPLE_OF_TIME_AFTER_LIGHT_MEDALLION_ALT", "Temple Of Time After Light Medallion Alt", "Temple Of Time After Light Medallion Alt"),
    ("CS_DEST_KAKARIKO_VILLAGE_NOCTURNE_PART_2", "Kakariko Village Nocturne Part 2", "Kakariko Village Nocturne Part 2"),
    ("CS_DEST_DESERT_COLOSSUS_FROM_REQUIEM", "Desert Colossus From Requiem", "Desert Colossus From Requiem"),
    ("CS_DEST_TEMPLE_OF_TIME_FROM_LIGHT_ARROWS", "Temple Of Time From Light Arrows", "Temple Of Time From Light Arrows"),
    ("CS_DEST_KAKARIKO_VILLAGE_FROM_NOCTURNE", "Kakariko Village From Nocturne", "Kakariko Village From Nocturne"),
    ("CS_DEST_HYRULE_FIELD_FROM_ZELDAS_COURTYARD", "Hyrule Field From Zeldas Courtyard", "Hyrule Field From Zeldas Courtyard"),
    ("CS_DEST_TEMPLE_OF_TIME_SONG_OF_TIME", "Temple Of Time Song Of Time", "Temple Of Time Song Of Time"),
    ("CS_DEST_HYRULE_FIELD_FROM_SONG_OF_TIME", "Hyrule Field From Song Of Time", "Hyrule Field From Song Of Time"),
    ("CS_DEST_GERUDO_VALLEY_CREDITS", "Gerudo Valley Credits", "Gerudo Valley Credits"),
    ("CS_DEST_GERUDO_FORTRESS_CREDITS", "Gerudo Fortress Credits", "Gerudo Fortress Credits"),
    ("CS_DEST_KAKARIKO_VILLAGE_CREDITS", "Kakariko Village Credits", "Kakariko Village Credits"),
    ("CS_DEST_DEATH_MOUNTAIN_TRAIL_CREDITS_PART_1", "Death Mountain Trail Credits Part 1", "Death Mountain Trail Credits Part 1"),
    ("CS_DEST_GORON_CITY_CREDITS", "Goron City Credits", "Goron City Credits"),
    ("CS_DEST_LAKE_HYLIA_CREDITS", "Lake Hylia Credits", "Lake Hylia Credits"),
    ("CS_DEST_ZORAS_FOUNTAIN_CREDITS", "Zoras Fountain Credits", "Zoras Fountain Credits"),
    ("CS_DEST_ZORAS_DOMAIN_CREDITS", "Zoras Domain Credits", "Zoras Domain Credits"),
    ("CS_DEST_KOKIRI_FOREST_CREDITS_PART_1", "Kokiri Forest Credits Part 1", "Kokiri Forest Credits Part 1"),
    ("CS_DEST_KOKIRI_FOREST_CREDITS_PART_2", "Kokiri Forest Credits Part 2", "Kokiri Forest Credits Part 2"),
    ("CS_DEST_HYRULE_FIELD_CREDITS", "Hyrule Field Credits", "Hyrule Field Credits"),
    ("CS_DEST_LON_LON_RANCH_CREDITS_PART_1_ALT", "Lon Lon Ranch Credits Part 1 Alt", "Lon Lon Ranch Credits Part 1 Alt"),
    ("CS_DEST_KAKARIKO_VILLAGE_FROM_TRAIL_OWL", "Kakariko Village From Trail Owl", "Kakariko Village From Trail Owl"),
    ("CS_DEST_HYRULE_FIELD_FROM_LAKE_HYLIA_OWL", "Hyrule Field From Lake Hylia Owl", "Hyrule Field From Lake Hylia Owl"),
    ("CS_DEST_CUTSCENE_MAP_DEKU_SPROUT_PART_2", "Cutscene Map Deku Sprout Part 2", "Cutscene Map Deku Sprout Part 2"),
    ("CS_DEST_KOKIRI_FOREST_DEKU_SPROUT_PART_3", "Kokiri Forest Deku Sprout Part 3", "Kokiri Forest Deku Sprout Part 3"),
    ("CS_DEST_DEATH_MOUNTAIN_TRAIL_CREDITS_PART_2", "Death Mountain Trail Credits Part 2", "Death Mountain Trail Credits Part 2"),
    ("CS_DEST_TEMPLE_OF_TIME_CREDITS", "Temple Of Time Credits", "Temple Of Time Credits"),
    ("CS_DEST_ZELDAS_COURTYARD_CREDITS", "Zeldas Courtyard Credits", "Zeldas Courtyard Credits"),
    ("CS_DEST_LON_LON_RANCH_CREDITS_PART_1", "Lon Lon Ranch Credits Part 1", "Lon Lon Ranch Credits Part 1"),
    ("CS_DEST_LON_LON_RANCH_CREDITS_PART_2", "Lon Lon Ranch Credits Part 2", "Lon Lon Ranch Credits Part 2"),
    ("CS_DEST_LON_LON_RANCH_CREDITS_PART_3", "Lon Lon Ranch Credits Part 3", "Lon Lon Ranch Credits Part 3"),
    ("CS_DEST_LON_LON_RANCH_CREDITS_PART_4", "Lon Lon Ranch Credits Part 4", "Lon Lon Ranch Credits Part 4"),
    ("CS_DEST_LON_LON_RANCH_CREDITS_PART_5", "Lon Lon Ranch Credits Part 5", "Lon Lon Ranch Credits Part 5"),
    ("CS_DEST_LON_LON_RANCH_CREDITS_PART_6", "Lon Lon Ranch Credits Part 6", "Lon Lon Ranch Credits Part 6"),
    ("CS_DEST_LON_LON_RANCH_1", "Lon Lon Ranch 1", "Lon Lon Ranch 1"),
    ("CS_DEST_LON_LON_RANCH_2", "Lon Lon Ranch 2", "Lon Lon Ranch 2"),
    ("CS_DEST_LON_LON_RANCH_3", "Lon Lon Ranch 3", "Lon Lon Ranch 3"),
    ("CS_DEST_LON_LON_RANCH_4", "Lon Lon Ranch 4", "Lon Lon Ranch 4"),
    ("CS_DEST_LON_LON_RANCH_5", "Lon Lon Ranch 5", "Lon Lon Ranch 5"),
    ("CS_DEST_LON_LON_RANCH_6", "Lon Lon Ranch 6", "Lon Lon Ranch 6"),
    ("CS_DEST_LON_LON_RANCH_7", "Lon Lon Ranch 7", "Lon Lon Ranch 7"),
    ("CS_DEST_LON_LON_RANCH_8", "Lon Lon Ranch 8", "Lon Lon Ranch 8"),
    ("CS_DEST_LON_LON_RANCH_9", "Lon Lon Ranch 9", "Lon Lon Ranch 9"),
    ("CS_DEST_LON_LON_RANCH_10", "Lon Lon Ranch 10", "Lon Lon Ranch 10"),
    ("CS_DEST_LON_LON_RANCH_11", "Lon Lon Ranch 11", "Lon Lon Ranch 11"),
    ("CS_DEST_LON_LON_RANCH_12", "Lon Lon Ranch 12", "Lon Lon Ranch 12"),
    ("CS_DEST_LON_LON_RANCH_13", "Lon Lon Ranch 13", "Lon Lon Ranch 13"),
    ("CS_DEST_LON_LON_RANCH_14", "Lon Lon Ranch 14", "Lon Lon Ranch 14"),
    ("CS_DEST_LON_LON_RANCH_15", "Lon Lon Ranch 15", "Lon Lon Ranch 15"),
    ("CS_DEST_LON_LON_RANCH_FROM_EPONAS_SONG", "Lon Lon Ranch From Eponas Song", "Lon Lon Ranch From Eponas Song"),
    ("CS_DEST_STONES_RESTORED_CONDITIONAL", "Stones Restored Conditional", "Stones Restored Conditional"),
    ("CS_DEST_DESERT_COLOSSUS_FROM_CHAMBER_OF_SAGES", "Desert Colossus From Chamber Of Sages", "Desert Colossus From Chamber Of Sages"),
    ("CS_DEST_GRAVEYARD_FROM_CHAMBER_OF_SAGES", "Graveyard From Chamber Of Sages", "Graveyard From Chamber Of Sages"),
    ("CS_DEST_DEATH_MOUNTAIN_CRATER_FROM_CHAMBER_OF_SAGES", "Death Mountain Crater From Chamber Of Sages", "Death Mountain Crater From Chamber Of Sages"),
    ("CS_DEST_SACRED_FOREST_MEADOW_WARP_PAD", "Sacred Forest Meadow Warp Pad", "Sacred Forest Meadow Warp Pad"),
    ("CS_DEST_KOKIRI_FOREST_FROM_CHAMBER_OF_SAGES", "Kokiri Forest From Chamber Of Sages", "Kokiri Forest From Chamber Of Sages"),
    ("CS_DEST_DESERT_COLOSSUS_FROM_NABOORU_CAPTURE", "Desert Colossus From Nabooru Capture", "Desert Colossus From Nabooru Capture"),
    ("CS_DEST_TEMPLE_OF_TIME_FRONT_OF_PEDESTAL", "Temple Of Time Front Of Pedestal", "Temple Of Time Front Of Pedestal"),
    ("CS_DEST_HYRULE_FIELD_TITLE_SCREEN", "Hyrule Field Title Screen", "Hyrule Field Title Screen"),
    ("CS_DEST_TITLE_SCREEN_DEMO", "Title Screen Demo", "Title Screen Demo"),
    ("CS_DEST_GRAVEYARD_SUNS_SONG_PART_2", "Graveyard Suns Song Part 2", "Graveyard Suns Song Part 2"),
    ("CS_DEST_ROYAL_FAMILYS_TOMB_SUNS_SONG_PART_3", "Royal Familys Tomb Suns Song Part 3", "Royal Familys Tomb Suns Song Part 3"),
    ("CS_DEST_GANONS_CASTLE_DISPEL_FOREST_BEAM", "Ganons Castle Dispel Forest Beam", "Ganons Castle Dispel Forest Beam"),
    ("CS_DEST_GANONS_CASTLE_DISPEL_WATER_BEAM", "Ganons Castle Dispel Water Beam", "Ganons Castle Dispel Water Beam"),
    ("CS_DEST_GANONS_CASTLE_DISPEL_SHADOW_BEAM", "Ganons Castle Dispel Shadow Beam", "Ganons Castle Dispel Shadow Beam"),
    ("CS_DEST_GANONS_CASTLE_DISPEL_FIRE_BEAM", "Ganons Castle Dispel Fire Beam", "Ganons Castle Dispel Fire Beam"),
    ("CS_DEST_GANONS_CASTLE_DISPEL_LIGHT_BEAM", "Ganons Castle Dispel Light Beam", "Ganons Castle Dispel Light Beam"),
    ("CS_DEST_GANONS_CASTLE_DISPEL_SPIRIT_BEAM", "Ganons Castle Dispel Spirit Beam", "Ganons Castle Dispel Spirit Beam"),
    ("CS_DEST_GANONS_CASTLE_DISPEL_BARRIER_CONDITONAL", "Ganons Castle Dispel Barrier Conditonal", "Ganons Castle Dispel Barrier Conditonal"),
    ("CS_DEST_HYRULE_FIELD_FROM_FAIRY_OCARINA", "Hyrule Field From Fairy Ocarina", "Hyrule Field From Fairy Ocarina"),
    ("CS_DEST_HYRULE_FIELD_FROM_IMPA_ESCORT", "Hyrule Field From Impa Escort", "Hyrule Field From Impa Escort"),
    ("CS_DEST_FROM_RAURU_FINAL_MESSAGE_CONDITIONAL", "From Rauru Final Message Conditional", "From Rauru Final Message Conditional"),
    ("CS_DEST_HYRULE_FIELD_CREDITS_SKY", "Hyrule Field Credits Sky", "Hyrule Field Credits Sky"),
    ("CS_DEST_GANON_BATTLE_TOWER_COLLAPSE", "Ganon Battle Tower Collapse", "Ganon Battle Tower Collapse"),
    ("CS_DEST_ZELDAS_COURTYARD_RECEIVE_LETTER", "Zeldas Courtyard Receive Letter", "Zeldas Courtyard Receive Letter"),
]

ootEnumTextType = [
    # see https://github.com/zeldaret/oot/blob/542012efa68d110d6b631f9d149f6e5f4e68cc8e/include/z64cutscene.h#L206-L212
    ("Custom", "Custom", "Custom"),
    ("CS_TEXT_NORMAL", "Normal Text", "Normal Text"),
    ("CS_TEXT_CHOICE", "Choice", "Choice"),
    ("CS_TEXT_OCARINA_ACTION", "Ocarina Action", "Ocarina Action"),
    ("CS_TEXT_GORON_RUBY", "Goron Ruby (use alt text)", "Goron Ruby (use alt text)"),
    ("CS_TEXT_ZORA_SAPPHIRE", "Zora Sapphire (use alt text)", "Zora Sapphire (use alt text)"),
]

ootEnumOcarinaAction = [
    # see https://github.com/zeldaret/oot/blob/b4c97ce17eb35329b4a7e3d98d7f06d558683f6d/include/z64ocarina.h#L25-L76
    # note: "teach" and "playback" are the only types used in cutscenes but in theory every ones could be used
    ("Custom", "Custom", "Custom"),
    ("OCARINA_ACTION_TEACH_MINUET", "Teach Minuet", "Teach Minuet"),
    ("OCARINA_ACTION_TEACH_BOLERO", "Teach Bolero", "Teach Bolero"),
    ("OCARINA_ACTION_TEACH_SERENADE", "Teach Serenade", "Teach Serenade"),
    ("OCARINA_ACTION_TEACH_REQUIEM", "Teach Requiem", "Teach Requiem"),
    ("OCARINA_ACTION_TEACH_NOCTURNE", "Teach Nocturne", "Teach Nocturne"),
    ("OCARINA_ACTION_TEACH_PRELUDE", "Teach Prelude", "Teach Prelude"),
    ("OCARINA_ACTION_TEACH_SARIA", "Teach Saria", "Teach Saria"),
    ("OCARINA_ACTION_TEACH_EPONA", "Teach Epona", "Teach Epona"),
    ("OCARINA_ACTION_TEACH_LULLABY", "Teach Lullaby", "Teach Lullaby"),
    ("OCARINA_ACTION_TEACH_SUNS", "Teach Suns", "Teach Suns"),
    ("OCARINA_ACTION_TEACH_TIME", "Teach Time", "Teach Time"),
    ("OCARINA_ACTION_TEACH_STORMS", "Teach Storms", "Teach Storms"),
    ("OCARINA_ACTION_PLAYBACK_MINUET", "Play back Minuet", "Play back Minuet"),
    ("OCARINA_ACTION_PLAYBACK_BOLERO", "Play back Bolero", "Play back Bolero"),
    ("OCARINA_ACTION_PLAYBACK_SERENADE", "Play back Serenade", "Play back Serenade"),
    ("OCARINA_ACTION_PLAYBACK_REQUIEM", "Play back Requiem", "Play back Requiem"),
    ("OCARINA_ACTION_PLAYBACK_NOCTURNE", "Play back Nocturne", "Play back Nocturne"),
    ("OCARINA_ACTION_PLAYBACK_PRELUDE", "Play back Prelude", "Play back Prelude"),
    ("OCARINA_ACTION_PLAYBACK_SARIA", "Play back Saria", "Play back Saria"),
    ("OCARINA_ACTION_PLAYBACK_EPONA", "Play back Epona", "Play back Epona"),
    ("OCARINA_ACTION_PLAYBACK_LULLABY", "Play back Lullaby", "Play back Lullaby"),
    ("OCARINA_ACTION_PLAYBACK_SUNS", "Play back Suns", "Play back Suns"),
    ("OCARINA_ACTION_PLAYBACK_TIME", "Play back Time", "Play back Time"),
    ("OCARINA_ACTION_PLAYBACK_STORMS", "Play back Storms", "Play back Storms"),
]

ootEnumSeqPlayer = [
    # see https://github.com/zeldaret/oot/blob/b4c97ce17eb35329b4a7e3d98d7f06d558683f6d/include/z64cutscene.h#L214-L217
    ("Custom", "Custom", "Custom"),
    ("CS_FADE_OUT_FANFARE", "Fanfare", "Fanfare"),
    ("CS_FADE_OUT_BGM_MAIN", "BGM Main", "BGM Main"),
]

ootCSSubPropToName = {
    "startFrame": "Start Frame",
    "endFrame": "End Frame",

    # TextBox
    "textID": "Text ID",
    "ocarinaAction": "Ocarina Action",
    "csTextType": "Text Type",
    "topOptionTextID": "Text ID for Top Option",
    "bottomOptionTextID": "Text ID for Bottom Option",
    "ocarinaMessageId": "Ocarina Message ID",

    # Lighting
    "lightSettingsIndex": "Light Settings Index",

    # Time
    "hour": "Hour",
    "minute": "Minute",

    # BGM
    "csSeqID": "BGM ID",
    "csSeqPlayer": "Seq Player Type",

    # Misc
    "csMiscType": "Misc Type",

    # Rumble
    "rumbleSourceStrength": "Source Strength",
    "rumbleDuration": "Duration",
    "rumbleDecreaseRate": "Decrease Rate",
}

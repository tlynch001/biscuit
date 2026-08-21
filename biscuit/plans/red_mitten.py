"""Cinematic visual director for Biscuit and the Red Mitten.

Spoken strings are slices of the authored beat narration. Concatenating
``spoken`` across the plan must reproduce the literary text exactly
(whitespace-normalized). This file does not rewrite the story.

The director knows the whole film. Each image prompt describes only what
belongs in the current frame.
"""

from __future__ import annotations

from typing import Any

PLANNER_ID = "biscuit_and_the_red_mitten"

BISCUIT = (
    "a small cream-gold retriever mix with russet ears, slightly scruffy winter fur, "
    "and a faded red cloth bandana knotted at the throat"
)

VISUAL_BIBLE: dict[str, str] = {
    "biscuit": (
        f"Biscuit is {BISCUIT}. Ordinary dog, never clothed. Same animal in every frame: "
        "cream-gold coat, russet ears, nick in the left ear, faded red bandana — not a collar tag."
    ),
    "empty_road": (
        "Isolated two-lane county blacktop through open Midwest farm country in deep winter. "
        "Packed snow on pavement and shoulders. Fence. Field. Fence. Iron-gray overcast sky. "
        "Ice on the wire. No town. Distant grain bins only if they stay tiny on the horizon."
    ),
    "sedan_ditch": (
        "A rusted sedan nosed down in the snow-filled ditch beside the blacktop, never on the "
        "pavement, never driving. Passenger door hanging open. Snow on the seats. The car is a "
        "left-behind object, not traffic."
    ),
    "open_field": (
        "Open snow-covered field leaving the road behind. Deep crust. Sparse fence far to one side. "
        "A distant dark treeline. Heavy sky. Wind writing over the white. Empty of buildings."
    ),
    "creek_woods": (
        "Darker, more enclosed winter landscape. Frozen creek, ice at the edges, a crack of black "
        "water. Bare trees closing in. Dying flat light. Remote from the road."
    ),
    "culvert_mouth": (
        "Weathered concrete culvert where the creek disappears. Gray wet throat. Low. Dim. "
        "The road above is not part of this frame."
    ),
    "culvert_interior": (
        "Enclosed wet concrete pipe. Sweating walls. Almost no light. Sound of water ticking. "
        "No sky, no road, no vehicles."
    ),
    "woman": (
        "Young mother, early thirties, slight and spent. Thin gray cloth coat, wet jeans, indoor "
        "shoes packed with snow. Dark hair iced at the temples. No gloves."
    ),
    "child": (
        "About four. Navy snowsuit, dark curls in the hood, plastic cup clipped to the suit. "
        "One brighter red child's mitten; the other hand may be bare until the mitten is returned."
    ),
    "snowplow": (
        "Tired orange municipal snowplow, blade down, amber hazard lights. It enters the visual "
        "story only at the distant-amber reveal, never before."
    ),
    "driver": (
        "Older man, early sixties, solid. Canvas chore coat, orange vest, heavy gloves, wool cap, "
        "gray mustache with ice in it. He appears only with the plow."
    ),
}

SEQUENCES: list[dict[str, Any]] = [
    {
        "id": "empty_road",
        "title": "Empty road",
        "location_id": "empty_road",
        "summary": "Establish the isolated winter road. Biscuit arrives alone.",
    },
    {
        "id": "abandoned_sedan",
        "title": "Abandoned sedan",
        "location_id": "sedan_ditch",
        "summary": "The car is discovered in the ditch. The mitten is found here.",
    },
    {
        "id": "field_trail",
        "title": "Field / trail",
        "location_id": "open_field",
        "summary": "Biscuit leaves the road and crosses open country toward the trees.",
    },
    {
        "id": "creek_woods",
        "title": "Creek / woods",
        "location_id": "creek_woods",
        "summary": "The country closes in. Ice, black water, darker trees.",
    },
    {
        "id": "culvert",
        "title": "Culvert",
        "location_id": "culvert_interior",
        "summary": "He enters the concrete throat and finds the woman and child.",
    },
    {
        "id": "return_to_road",
        "title": "Return to road",
        "location_id": "sedan_ditch",
        "summary": "He leaves them and climbs back to the established road and sedan.",
    },
    {
        "id": "snowplow_rescue",
        "title": "Snowplow arrival / rescue",
        "location_id": "sedan_ditch",
        "summary": "The plow appears for the first time. The driver follows Biscuit to the culvert.",
    },
    {
        "id": "departure",
        "title": "Departure / empty road",
        "location_id": "empty_road",
        "summary": "The plow leaves. Biscuit remains and goes on. The country empties.",
    },
]


def shots() -> list[dict[str, Any]]:
    """Return ordered cinematic shots covering every spoken word of Red Mitten."""

    return [
        {
            "id": "empty_road",
            "sequence_id": "empty_road",
            "location_id": "empty_road",
            "beat_id": "the_road",
            "title": "A road without a town",
            "emotion": "isolation",
            "characters": [],
            "motion": "static",
            "break_after": 0.7,
            "reference_shot_id": "",
            "shot_description": "Empty two-lane winter road. No dog, no car, no plow.",
            "spoken": (
                "The road ran without a town to finish it. Fence. Field. A sky the color of wet iron. "
                "Ice stood on the wire in little teeth."
            ),
            "visible_elements": [
                "two-lane county blacktop",
                "packed snow",
                "fence and wire",
                "open field",
                "iron-gray sky",
            ],
            "forbidden_elements": ["biscuit", "sedan", "snowplow", "people", "culvert", "mitten"],
            "continuity": {
                "geography": "isolated rural road",
                "biscuit": "absent",
                "mitten": "absent",
                "sedan_revealed": False,
                "people_revealed": False,
                "plow_revealed": False,
            },
            "local_prompt": (
                "Wide cinematic still photograph of an isolated two-lane county blacktop running "
                "straight through deep winter farm country. Packed snow on the pavement and shoulders. "
                "Wooden fence posts and wire receding along one side. A white field beyond. Ice standing "
                "on the fence wire. Heavy iron-gray overcast sky. Empty landscape. Documentary grain. "
                "Flat winter light."
            ),
        },
        {
            "id": "biscuit_on_road",
            "sequence_id": "empty_road",
            "location_id": "empty_road",
            "beat_id": "the_road",
            "title": "Along the packed shoulder",
            "emotion": "isolation",
            "characters": ["biscuit"],
            "motion": "slow_zoom_in",
            "break_after": 0.55,
            "reference_shot_id": "empty_road",
            "shot_description": "Biscuit alone on the established empty road.",
            "spoken": (
                "Biscuit came along the packed shoulder, nose down, his faded red bandana "
                "the only worn thing in all that new white. No cars. No houses near enough to matter. "
                "The wind had a smell in it that did not belong to rabbits or diesel. He stopped. "
                "He tasted the air again. Then he turned into it."
            ),
            "visible_elements": ["biscuit", "empty road", "fence", "field", "iron sky"],
            "forbidden_elements": ["sedan", "snowplow", "people", "culvert", "mitten"],
            "continuity": {
                "geography": "same empty road",
                "biscuit": "on_shoulder",
                "mitten": "absent",
                "sedan_revealed": False,
                "people_revealed": False,
                "plow_revealed": False,
            },
            "local_prompt": (
                f"Wide winter road still. {BISCUIT.capitalize()} walking alone along the packed "
                "snowy shoulder of a two-lane county blacktop, nose down. Open farm country, fence and "
                "field, iron-gray sky. Blowing snow. The road is otherwise empty."
            ),
        },
        {
            "id": "sedan_in_ditch",
            "sequence_id": "abandoned_sedan",
            "location_id": "sedan_ditch",
            "beat_id": "the_car",
            "title": "The open door",
            "emotion": "unease",
            "characters": ["biscuit"],
            "motion": "static",
            "break_after": 0.55,
            "reference_shot_id": "biscuit_on_road",
            "shot_description": "Sedan physically off the roadway in the ditch. Biscuit small against it.",
            "spoken": (
                "A car sat in the ditch with its door hanging open. The wind moved the door and let it "
                "fall back. Snow was already on the seats. A cup lay on its side on the floorboard. "
                "The engine was dead. Biscuit stopped in the road. He went to the running board and "
                "sniffed the wet rubber, the cloth, the cold metal. People had been here. The cloth "
                "still held them, and was losing them."
            ),
            "visible_elements": ["sedan in ditch", "hanging passenger door", "biscuit", "winter road"],
            "forbidden_elements": ["snowplow", "woman", "child", "culvert", "mitten"],
            "continuity": {
                "geography": "sedan off the roadway in the ditch beside the blacktop",
                "biscuit": "at_sedan",
                "mitten": "absent",
                "sedan_revealed": True,
                "people_revealed": False,
                "plow_revealed": False,
            },
            "local_prompt": (
                "Wide cinematic still of a rusted sedan nosed down in the snow-filled ditch beside a "
                f"two-lane winter road, passenger door hanging open. Snow already on the seats. {BISCUIT} "
                "small in the road near the car. Wind. Iron-gray sky. Documentary winter light."
            ),
        },
        {
            "id": "mitten_by_tire",
            "sequence_id": "abandoned_sedan",
            "location_id": "sedan_ditch",
            "beat_id": "the_mitten",
            "title": "A red thing in the white",
            "emotion": "recognition",
            "characters": ["biscuit"],
            "motion": "slow_zoom_in",
            "break_after": 0.65,
            "reference_shot_id": "sedan_in_ditch",
            "shot_description": "Child's mitten discovered at the sedan's rear tire.",
            "spoken": (
                "Beside the tire, half in a drift, a child's mitten. Red. Brighter than his bandana. "
                "He nosed it. Snow fell off the cuff. The lining still held a little heat, and a smell "
                "of soap and skin. He picked it up. It was bigger in his mouth than it had looked on "
                "the ground. He did not put it down."
            ),
            "visible_elements": ["red child's mitten", "rear tire", "biscuit", "sedan wheel well"],
            "forbidden_elements": ["snowplow", "woman", "child", "culvert"],
            "continuity": {
                "geography": "same sedan in the ditch",
                "biscuit": "at_rear_tire",
                "mitten": "picked_up",
                "sedan_revealed": True,
                "people_revealed": False,
                "plow_revealed": False,
            },
            "local_prompt": (
                "Medium cinematic still at a rusted sedan's rear wheel in a snowy ditch. A child's "
                f"bright red mitten half in a drift beside the tire. {BISCUIT} lowering his cream "
                "muzzle toward the mitten, faded red bandana at his throat. Flat overcast winter light. "
                "Documentary grain."
            ),
        },
        {
            "id": "leaving_the_road",
            "sequence_id": "field_trail",
            "location_id": "road_bank",
            "beat_id": "the_tracks",
            "title": "Off the blacktop",
            "emotion": "urgency",
            "characters": ["biscuit"],
            "motion": "slow_zoom_out",
            "break_after": 0.5,
            "reference_shot_id": "sedan_in_ditch",
            "shot_description": "Transition: Biscuit leaves the road for the field. Road and sedan fall to the margin.",
            "spoken": (
                "Prints left the road and climbed the bank. One large. One small, dragging at the heel. "
                "They went into the field toward a line of trees that might have been a creek."
            ),
            "visible_elements": [
                "biscuit with mitten",
                "ditch bank",
                "open field ahead",
                "distant treeline",
                "road and sedan at the edge of frame",
            ],
            "forbidden_elements": ["snowplow", "woman", "child", "culvert"],
            "continuity": {
                "geography": "leaving road via ditch bank into the field",
                "biscuit": "climbing_bank",
                "mitten": "in_mouth",
                "sedan_revealed": True,
                "people_revealed": False,
                "plow_revealed": False,
            },
            "local_prompt": (
                "Wide still from a snowy ditch bank looking into an open field. "
                f"{BISCUIT.capitalize()} climbing away from the roadway through deep snow, a bright red "
                "child's mitten held in his mouth. A dark line of trees far ahead. Behind him, at the "
                "edge of frame, the two-lane road and a sedan in the ditch are already falling away. "
                "Blowing snow. Iron sky."
            ),
        },
        {
            "id": "field_crossing",
            "sequence_id": "field_trail",
            "location_id": "open_field",
            "beat_id": "the_tracks",
            "title": "Where the road-sound died",
            "emotion": "endurance",
            "characters": ["biscuit"],
            "motion": "static",
            "break_after": 0.7,
            "reference_shot_id": "",
            "shot_description": "Biscuit alone in open country. Narration may speak of tracks; the picture is isolation.",
            "spoken": (
                "The snow was filling them as he watched. A print was a print, and then it was only a "
                "dent, and then it was nothing. He went after what remained, mitten in his teeth, chest "
                "wading the drift. The field took the sound of the road away. Wire sang. Biscuit's paws "
                "broke the crust and found the hard dirt under it. The small prints stopped. Then they "
                "were gone. He cast left. He cast right. Farther on they were on the ground again, "
                "shallower. He kept the mitten and went."
            ),
            "visible_elements": ["biscuit", "red mitten in mouth", "wide snow field", "distant treeline", "sparse fence"],
            "forbidden_elements": ["road", "sedan", "snowplow", "woman", "child", "culvert", "houses"],
            "continuity": {
                "geography": "open field; road and sedan no longer visible",
                "biscuit": "crossing_field",
                "mitten": "in_mouth",
                "sedan_revealed": True,
                "people_revealed": False,
                "plow_revealed": False,
            },
            "local_prompt": (
                "Wide winter field beneath a heavy iron-gray sky. "
                f"{BISCUIT.capitalize()} walking away from camera through deep snow toward a distant "
                "dark treeline. Bright red child's mitten held in his mouth. Blowing snow. Sparse fence "
                "line far to one side."
            ),
        },
        {
            "id": "creek_woods",
            "sequence_id": "creek_woods",
            "location_id": "creek_woods",
            "beat_id": "the_creek",
            "title": "The ground stops talking",
            "emotion": "dread",
            "characters": ["biscuit"],
            "motion": "static",
            "break_after": 0.65,
            "reference_shot_id": "",
            "shot_description": "Creek and darker trees. Remote from the road. No people yet.",
            "spoken": (
                "At the creek the tracks ended. Ice. A crack of black water. No house. No light. "
                "The trees were only a darker weather. Biscuit stood with his ears flat and the mitten "
                "dripping. He went along the bank, upstream, then down. The smell thinned. Then it "
                "gathered again, low, where the water went into the dark."
            ),
            "visible_elements": ["frozen creek", "black water", "bare trees", "biscuit", "wet red mitten"],
            "forbidden_elements": ["road", "sedan", "snowplow", "woman", "child", "culvert", "houses", "lights"],
            "continuity": {
                "geography": "creek at the treeline; road not visible",
                "biscuit": "at_creek",
                "mitten": "in_mouth",
                "sedan_revealed": True,
                "people_revealed": False,
                "plow_revealed": False,
            },
            "local_prompt": (
                "A frozen creek at a dark winter treeline. Ice at the edges and a crack of black water. "
                f"{BISCUIT.capitalize()} on the bank, ears slightly flat, a wet red child's mitten in his "
                "mouth. Bare trees closing in. Flat dying winter light. Enclosed woods, remote country."
            ),
        },
        {
            "id": "culvert_mouth",
            "sequence_id": "culvert",
            "location_id": "culvert_mouth",
            "beat_id": "the_culvert",
            "title": "The throat",
            "emotion": "discovery",
            "characters": ["biscuit"],
            "motion": "slow_zoom_in",
            "break_after": 0.4,
            "reference_shot_id": "",
            "shot_description": "Concrete culvert mouth. He goes in. Occupants not yet visible.",
            "spoken": (
                "The creek went under the road through a concrete throat. He smelled milk and wet wool. "
                "He went in."
            ),
            "visible_elements": ["concrete culvert mouth", "creek water", "biscuit entering with mitten"],
            "forbidden_elements": ["woman", "child", "snowplow", "sedan", "road surface", "driver"],
            "continuity": {
                "geography": "culvert at creek level; road above is not shown",
                "biscuit": "entering_culvert",
                "mitten": "in_mouth",
                "sedan_revealed": True,
                "people_revealed": False,
                "plow_revealed": False,
            },
            "local_prompt": (
                "The mouth of a weathered concrete culvert where a winter creek disappears into darkness. "
                f"Gray wet walls. {BISCUIT.capitalize()} entering the dark throat, a red child's mitten in "
                "his mouth. Enclosed, low, dim. Documentary grain."
            ),
        },
        {
            "id": "culvert_discovery",
            "sequence_id": "culvert",
            "location_id": "culvert_interior",
            "beat_id": "the_culvert",
            "title": "They were there",
            "emotion": "discovery",
            "characters": ["biscuit", "woman", "child"],
            "motion": "static",
            "break_after": 0.7,
            "reference_shot_id": "culvert_mouth",
            "shot_description": "First reveal of the woman and child.",
            "spoken": (
                "They were there. A woman against the wall. A child in her lap. One bare hand. Ice in "
                "the woman's hair. The child's eyes were open too. Neither of them spoke. Water ticked "
                "somewhere in the dark behind them."
            ),
            "visible_elements": ["culvert interior", "woman", "child", "biscuit", "mitten in biscuit's mouth"],
            "forbidden_elements": ["snowplow", "sedan", "road", "driver"],
            "continuity": {
                "geography": "inside the culvert",
                "biscuit": "with_them",
                "mitten": "in_mouth",
                "sedan_revealed": True,
                "people_revealed": True,
                "plow_revealed": False,
            },
            "local_prompt": (
                "Interior of a dark concrete culvert. A young woman in a thin gray cloth coat sitting "
                "against the curved wet wall, dark hair iced at the temples, no gloves. A small child in "
                "a navy snowsuit in her lap, dark curls in the hood, one red mitten, one bare chapped hand. "
                f"{BISCUIT.capitalize()} just inside the mouth, a bright red child's mitten still in his "
                "teeth. Almost no light. Concrete sweating."
            ),
        },
        {
            "id": "culvert_vigil",
            "sequence_id": "culvert",
            "location_id": "culvert_interior",
            "beat_id": "the_hand",
            "title": "What he could put back",
            "emotion": "tenderness",
            "characters": ["biscuit", "woman", "child"],
            "motion": "static",
            "break_after": 0.9,
            "reference_shot_id": "culvert_discovery",
            "shot_description": "Mitten returned. They stay. Stillness covers the long wait.",
            "spoken": (
                "He dropped the mitten on the bare hand and pressed against them. The child made a small "
                "sound. The woman's fingers found his fur and stayed, clumsy with cold. He licked the "
                "knuckles. Then he was still. The wind moved through the pipe. Time passed. No one else "
                "came down the bank."
            ),
            "visible_elements": ["culvert interior", "woman", "child with both mittens", "biscuit pressed against them"],
            "forbidden_elements": ["snowplow", "sedan", "road", "driver"],
            "continuity": {
                "geography": "inside the culvert",
                "biscuit": "with_them",
                "mitten": "on_child",
                "sedan_revealed": True,
                "people_revealed": True,
                "plow_revealed": False,
            },
            "local_prompt": (
                "Interior of a dark concrete culvert, close and still. The child in a navy snowsuit now "
                "has the bright red mitten on the previously bare hand. The woman in the thin gray coat "
                f"has her ungloved fingers in the fur of {BISCUIT}, who is pressed against them. Dim wet "
                "concrete. Almost no light."
            ),
        },
        {
            "id": "return_climb",
            "sequence_id": "return_to_road",
            "location_id": "road_bank",
            "beat_id": "the_blacktop",
            "title": "Back to the blacktop",
            "emotion": "determination",
            "characters": ["biscuit"],
            "motion": "slow_zoom_out",
            "break_after": 0.5,
            "reference_shot_id": "leaving_the_road",
            "shot_description": "He leaves them and climbs to the established road and sedan. No plow.",
            "spoken": (
                "Nothing came. After a time he left them. Not far. He climbed the iced slope to the "
                "blacktop, where a machine might still pass. The sedan's door still hung open in the ditch."
            ),
            "visible_elements": ["biscuit climbing", "iced bank", "blacktop above", "sedan in ditch", "hanging door"],
            "forbidden_elements": ["snowplow", "woman", "child", "driver"],
            "continuity": {
                "geography": "return path: bank to road and sedan",
                "biscuit": "climbing_to_road",
                "mitten": "left_with_child",
                "sedan_revealed": True,
                "people_revealed": True,
                "plow_revealed": False,
            },
            "local_prompt": (
                f"{BISCUIT.capitalize()} climbing an iced snowy bank toward a two-lane blacktop above. "
                "Ahead, a rusted sedan sits in the ditch with its door hanging open. White dusk. Empty "
                "winter road. Documentary still."
            ),
        },
        {
            "id": "barking_on_road",
            "sequence_id": "return_to_road",
            "location_id": "sedan_ditch",
            "beat_id": "the_blacktop",
            "title": "The country ate the sound",
            "emotion": "determination",
            "characters": ["biscuit"],
            "motion": "static",
            "break_after": 0.85,
            "reference_shot_id": "sedan_in_ditch",
            "shot_description": "Empty road and sedan. Biscuit barking. The plow has not yet entered the picture.",
            "spoken": (
                "He stood in the middle of the road and barked. He barked until his throat caught. "
                "The country ate the sound."
            ),
            "visible_elements": ["biscuit in the road", "empty blacktop", "sedan in ditch", "hanging door"],
            "forbidden_elements": ["snowplow", "woman", "child", "driver"],
            "continuity": {
                "geography": "established road and sedan; still empty of traffic",
                "biscuit": "in_road",
                "mitten": "left_with_child",
                "sedan_revealed": True,
                "people_revealed": True,
                "plow_revealed": False,
            },
            "local_prompt": (
                "Wide still of an empty two-lane winter road at white dusk. "
                f"{BISCUIT.capitalize()} standing alone in the middle of the blacktop. Behind him a rusted "
                "sedan in the ditch with its door hanging open. Fence. Iron sky. The country is empty."
            ),
        },
        {
            "id": "amber_far",
            "sequence_id": "snowplow_rescue",
            "location_id": "empty_road",
            "beat_id": "the_plow",
            "title": "Amber, late",
            "emotion": "interruption",
            "characters": ["biscuit"],
            "motion": "slow_zoom_in",
            "break_after": 0.7,
            "reference_shot_id": "empty_road",
            "shot_description": "First appearance of the snowplow: distant amber on the long road.",
            "spoken": "First a noise under the wind. Then amber, late, a long way off.",
            "visible_elements": ["long empty road", "distant amber lights", "distant snowplow", "biscuit small in foreground"],
            "forbidden_elements": ["woman", "child", "culvert"],
            "continuity": {
                "geography": "long straight road; plow still far away",
                "biscuit": "watching_from_road",
                "mitten": "left_with_child",
                "sedan_revealed": True,
                "people_revealed": True,
                "plow_revealed": True,
            },
            "local_prompt": (
                "Very wide winter road at dusk. A long straight two-lane blacktop through empty farm "
                "country. Far in the distance, tiny amber hazard lights of a snowplow approaching through "
                f"blowing snow. In the foreground, {BISCUIT} is a small dark shape on the road, watching. "
                "The landscape is still mostly empty sky and white fields."
            ),
        },
        {
            "id": "plow_at_sedan",
            "sequence_id": "snowplow_rescue",
            "location_id": "sedan_ditch",
            "beat_id": "the_plow",
            "title": "It slowed for the hanging door",
            "emotion": "interruption",
            "characters": ["biscuit", "driver"],
            "motion": "static",
            "break_after": 0.55,
            "reference_shot_id": "sedan_in_ditch",
            "shot_description": "Plow stopped at the sedan. Driver on the ground.",
            "spoken": (
                "A plow, high and loud, throwing a wall of snow. It slowed for the hanging door. "
                "A man got down in a canvas coat. He looked in the car. He shut the door once, and the "
                "wind opened it again. He looked at the dog."
            ),
            "visible_elements": ["orange snowplow", "sedan in ditch", "hanging door", "driver", "biscuit"],
            "forbidden_elements": ["woman", "child", "culvert"],
            "continuity": {
                "geography": "plow at the established sedan / road",
                "biscuit": "with_driver",
                "mitten": "left_with_child",
                "sedan_revealed": True,
                "people_revealed": True,
                "plow_revealed": True,
            },
            "local_prompt": (
                "A tired orange snowplow stopped on a two-lane winter road, blade down, amber lights "
                "washing the snow. A rusted sedan in the ditch with its door hanging open. An older man "
                "in a canvas chore coat, orange vest, wool cap, and gray mustache standing beside the "
                f"sedan. {BISCUIT} in the road watching him. White dusk."
            ),
        },
        {
            "id": "leading_driver",
            "sequence_id": "snowplow_rescue",
            "location_id": "road_bank",
            "beat_id": "the_pull",
            "title": "Followed",
            "emotion": "insistence",
            "characters": ["biscuit", "driver"],
            "motion": "slow_zoom_in",
            "break_after": 0.55,
            "reference_shot_id": "return_climb",
            "shot_description": "Driver follows Biscuit off the road toward the culvert mouth.",
            "spoken": (
                "Biscuit ran to the ditch and back. To the man. To the ditch. The man shouted once. "
                "Biscuit barked from the dark of the pipe. The man came down the bank, one glove on the "
                "fence post, and followed."
            ),
            "visible_elements": ["driver on the bank", "biscuit", "culvert mouth", "fence post"],
            "forbidden_elements": ["woman", "child"],
            "continuity": {
                "geography": "road to bank to culvert; people still inside the pipe",
                "biscuit": "leading",
                "mitten": "left_with_child",
                "sedan_revealed": True,
                "people_revealed": True,
                "plow_revealed": True,
            },
            "local_prompt": (
                "Winter ditch bank below a farm road. An older man in a canvas chore coat, orange vest, "
                "wool cap, and heavy gloves coming down through snow, one glove on a fence post. "
                f"{BISCUIT.capitalize()} ahead of him, facing a dark concrete culvert mouth in the bank. "
                "Blowing snow."
            ),
        },
        {
            "id": "rescue_in_culvert",
            "sequence_id": "snowplow_rescue",
            "location_id": "culvert_interior",
            "beat_id": "the_lift",
            "title": "We're going",
            "emotion": "extraction",
            "characters": ["biscuit", "woman", "child", "driver"],
            "motion": "static",
            "break_after": 0.55,
            "reference_shot_id": "culvert_vigil",
            "shot_description": "Driver lifts the child. The woman is gotten up.",
            "spoken": (
                "The man went to his knees in the wet concrete. He took the child. The woman tried to "
                "stand and could not, so he came back for her and got her up. He said, We're going. "
                "That was all."
            ),
            "visible_elements": ["culvert interior", "driver", "child", "woman", "biscuit"],
            "forbidden_elements": ["sedan", "full snowplow body"],
            "continuity": {
                "geography": "inside the culvert during rescue",
                "biscuit": "at_threshold",
                "mitten": "on_child",
                "sedan_revealed": True,
                "people_revealed": True,
                "plow_revealed": True,
            },
            "local_prompt": (
                "Inside the wet concrete culvert at dusk. An older man in a canvas coat and orange vest "
                "on his knees, lifting the small child in the navy snowsuit. The woman in the thin gray "
                f"coat trying to rise. {BISCUIT.capitalize()} at the threshold, not in the way. Amber light "
                "reaching in from the mouth. Documentary still."
            ),
        },
        {
            "id": "running_board",
            "sequence_id": "snowplow_rescue",
            "location_id": "sedan_ditch",
            "beat_id": "the_lift",
            "title": "No farther",
            "emotion": "extraction",
            "characters": ["biscuit", "woman", "child", "driver"],
            "motion": "static",
            "break_after": 0.95,
            "reference_shot_id": "plow_at_sedan",
            "shot_description": "They reach the plow. Biscuit stops at the running board.",
            "spoken": (
                "They climbed the bank in the plow light. Biscuit walked behind them as far as the "
                "truck's running board. No farther."
            ),
            "visible_elements": ["snowplow", "running board", "driver", "woman", "child", "biscuit stopping"],
            "forbidden_elements": [],
            "continuity": {
                "geography": "back at the road / plow",
                "biscuit": "at_running_board",
                "mitten": "on_child",
                "sedan_revealed": True,
                "people_revealed": True,
                "plow_revealed": True,
            },
            "local_prompt": (
                "Dusk at an orange snowplow beside a winter road. An older driver helping a woman in a "
                "thin gray coat and a child in a navy snowsuit toward the cab. Amber plow light on the "
                f"snow. {BISCUIT.capitalize()} standing at the truck's running board, going no farther. "
                "A rusted sedan in the ditch nearby."
            ),
        },
        {
            "id": "plow_recedes",
            "sequence_id": "departure",
            "location_id": "empty_road",
            "beat_id": "the_record",
            "title": "Amber shrinking",
            "emotion": "aftertaste",
            "characters": ["biscuit"],
            "motion": "slow_zoom_out",
            "break_after": 0.65,
            "reference_shot_id": "amber_far",
            "shot_description": "The plow leaves. The country begins to empty.",
            "spoken": (
                "The cab door shut. Heat leaked out and was gone. The plow moved off, amber shrinking "
                "on the long straight road. Biscuit stood by the sedan."
            ),
            "visible_elements": ["distant receding snowplow", "amber lights", "empty road", "biscuit", "sedan in ditch"],
            "forbidden_elements": ["woman", "child", "driver outside the cab"],
            "continuity": {
                "geography": "road emptying as the plow recedes",
                "biscuit": "by_sedan",
                "mitten": "gone_with_child",
                "sedan_revealed": True,
                "people_revealed": True,
                "plow_revealed": True,
            },
            "local_prompt": (
                "Long straight winter road at nightfall. A snowplow already small, amber lights shrinking "
                f"away down the empty blacktop. {BISCUIT.capitalize()} standing by a rusted sedan in the "
                "ditch. The country becoming empty again."
            ),
        },
        {
            "id": "biscuit_goes_on",
            "sequence_id": "departure",
            "location_id": "empty_road",
            "beat_id": "the_record",
            "title": "Small under that iron sky",
            "emotion": "aftertaste",
            "characters": ["biscuit"],
            "motion": "static",
            "break_after": 0.7,
            "reference_shot_id": "biscuit_on_road",
            "shot_description": "Biscuit continues. The landscape is empty again.",
            "spoken": (
                "Snow was already taking the field back. He shook the ice from his coat and went on, "
                "small under that iron sky."
            ),
            "visible_elements": ["biscuit walking on", "empty road or shoulder", "field", "iron sky"],
            "forbidden_elements": ["snowplow", "woman", "child", "driver"],
            "continuity": {
                "geography": "empty road and field again",
                "biscuit": "going_on",
                "mitten": "gone_with_child",
                "sedan_revealed": True,
                "people_revealed": True,
                "plow_revealed": True,
            },
            "local_prompt": (
                "Wide elemental winter still. "
                f"{BISCUIT.capitalize()} walking away along the packed shoulder of an empty two-lane "
                "county road, small under an iron-gray sky. Fence. Field. Fence. Blowing snow taking "
                "the country back."
            ),
        },
        {
            "id": "hanging_door",
            "sequence_id": "departure",
            "location_id": "sedan_ditch",
            "beat_id": "the_record",
            "title": "The road kept no record",
            "emotion": "aftertaste",
            "characters": [],
            "motion": "slow_zoom_in",
            "break_after": 1.2,
            "reference_shot_id": "sedan_in_ditch",
            "shot_description": "Final still: abandoned door gathering white. No figures.",
            "spoken": "Behind him the open door gathered white. The road kept no record.",
            "visible_elements": ["sedan in ditch", "hanging door gathering snow", "empty road", "field"],
            "forbidden_elements": ["biscuit", "snowplow", "people"],
            "continuity": {
                "geography": "sedan remains; everyone else is gone",
                "biscuit": "gone",
                "mitten": "gone_with_child",
                "sedan_revealed": True,
                "people_revealed": True,
                "plow_revealed": True,
            },
            "local_prompt": (
                "A rusted sedan in a snow-filled ditch beside an empty winter road, passenger door "
                "hanging open, snow gathering on the seats and the hanging door. Empty of figures. "
                "Fence and field and iron sky. The country keeping nothing. Documentary still."
            ),
        },
    ]


# Older registry code expected this name.
units = shots

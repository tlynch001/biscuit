"""Hand-directed visual beats and pauses for Biscuit and the Red Mitten.

Spoken strings are slices of the authored beat narration. Concatenating
``spoken`` within a beat must reproduce that beat's literary text exactly
(whitespace-normalized). This file does not rewrite the story.
"""

from __future__ import annotations

from typing import Any

PLANNER_ID = "biscuit_and_the_red_mitten"

BASE_FACTS = [
    "contemporary rural Midwest; two-lane county blacktop through open farm country",
    "incoming blizzard; wind over frozen fields; overcast iron afternoon thinning toward white dusk",
    "snow filling tracks as they are made",
    "no town square; no houses near enough to matter unless a shot is inside the culvert or at distant grain bins",
    "no cars on the roadway; the only car in this story is a stalled sedan in the ditch, never driving, never parked on the pavement",
    "no incidental people, animals, or traffic; only characters named for this shot",
    "Biscuit is a small cream-gold retriever mix with a faded red bandana; ordinary dog; never wearing clothes",
    "two reds only: Biscuit's faded bandana and a child's brighter red mitten, when present",
    "no readable signs, plates, lettering, captions, or watermarks",
]


def units() -> list[dict[str, Any]]:
    """Return ordered visual beats covering every spoken word of Red Mitten."""

    return [
        # --- the_road ---
        {
            "beat_id": "the_road",
            "id": "empty_road",
            "spoken": "The road ran without a town to finish it.",
            "break_after": 0.9,
            "characters": [],
            "motion": "slow_zoom_in",
            "visual": (
                "Wide empty two-lane county blacktop disappearing into blowing snow. "
                "No cars, no people, no houses, no town. Fence posts far off. Iron-gray sky. "
                "Packed snow on the shoulder. Documentary winter still."
            ),
        },
        {
            "beat_id": "the_road",
            "id": "fence_field_sky",
            "spoken": "Fence. Field. A sky the color of wet iron.",
            "ssml": 'Fence.<break time="0.28s" /> Field.<break time="0.4s" /> A sky the color of wet iron.',
            "break_after": 0.7,
            "characters": [],
            "motion": "pan_right",
            "visual": (
                "Fence and a field going white under an iron-gray overcast sky. "
                "No cars, no people, no houses. Wide country, not a close-up of Biscuit."
            ),
        },
        {
            "beat_id": "the_road",
            "id": "ice_wire",
            "spoken": "Ice stood on the wire in little teeth.",
            "break_after": 0.85,
            "characters": [],
            "motion": "slow_zoom_in",
            "visual": (
                "Close detail of ice standing on fence wire like little teeth. "
                "No cars, no people, no houses. Flat winter light."
            ),
        },
        {
            "beat_id": "the_road",
            "id": "biscuit_shoulder",
            "spoken": (
                "Biscuit came along the packed shoulder, nose down, his faded red bandana "
                "the only worn thing in all that new white."
            ),
            "break_after": 0.55,
            "characters": ["biscuit"],
            "motion": "pan_left",
            "visual": (
                "Biscuit alone on the packed snowy shoulder, nose down, faded red bandana. "
                "Empty road beside him. No other animals, no people, no cars."
            ),
        },
        {
            "beat_id": "the_road",
            "id": "no_cars_houses",
            "spoken": "No cars. No houses near enough to matter.",
            "ssml": 'No cars.<break time="0.4s" /> No houses near enough to matter.',
            "break_after": 1.1,
            "characters": [],
            "motion": "slow_zoom_out",
            "reuse": "empty_road",
            "visual": (
                "Hold the empty road: no cars on the pavement, no houses near enough to matter. "
                "Do not invent traffic, driveways, or a town."
            ),
        },
        {
            "beat_id": "the_road",
            "id": "wind_smell",
            "spoken": "The wind had a smell in it that did not belong to rabbits or diesel.",
            "break_after": 0.7,
            "characters": ["biscuit"],
            "motion": "pan_right",
            "visual": (
                "Biscuit small on the empty shoulder, wind moving snow across the field. "
                "No cars, no people. The country is the subject."
            ),
        },
        {
            "beat_id": "the_road",
            "id": "he_stopped",
            "spoken": "He stopped.",
            "break_after": 1.5,
            "characters": ["biscuit"],
            "motion": "static",
            "visual": (
                "Biscuit stopped on the packed shoulder of the empty road. Still. "
                "No cars, no people. Simple composition: dog, snow, road."
            ),
        },
        {
            "beat_id": "the_road",
            "id": "tasted_air",
            "spoken": "He tasted the air again.",
            "break_after": 0.85,
            "characters": ["biscuit"],
            "motion": "slow_zoom_in",
            "visual": (
                "Close still of Biscuit lifting his nose into the wind. Faded red bandana. "
                "Empty winter country behind him. No cars, no people."
            ),
        },
        {
            "beat_id": "the_road",
            "id": "turned_into_it",
            "spoken": "Then he turned into it.",
            "break_after": 1.0,
            "characters": ["biscuit"],
            "motion": "pan_left",
            "visual": (
                "Biscuit turning off the empty road into the field, away from the pavement. "
                "No cars, no people."
            ),
        },
        # --- the_car ---
        {
            "beat_id": "the_car",
            "id": "sedan_in_ditch",
            "spoken": "A car sat in the ditch with its door hanging open.",
            "break_after": 0.7,
            "characters": [],
            "motion": "slow_zoom_in",
            "facts_add": [
                "a rusted sedan is nosed into the ditch with the passenger door hanging open; it is not on the roadway"
            ],
            "visual": (
                "A rusted sedan nosed into the snowy ditch, passenger door hanging open. "
                "The roadway above it is empty — no other cars, no traffic. No people."
            ),
        },
        {
            "beat_id": "the_car",
            "id": "door_in_wind",
            "spoken": "The wind moved the door and let it fall back.",
            "break_after": 0.65,
            "characters": [],
            "motion": "pan_right",
            "visual": (
                "The hanging sedan door in the ditch, moved by wind. Empty road. No people. "
                "The car remains in the ditch, not on the pavement."
            ),
        },
        {
            "beat_id": "the_car",
            "id": "interior_dead",
            "spoken": "Snow was already on the seats. A cup lay on its side on the floorboard. The engine was dead.",
            "ssml": (
                "Snow was already on the seats.<break time=\"0.4s\" /> "
                "A cup lay on its side on the floorboard.<break time=\"0.55s\" /> "
                "The engine was dead."
            ),
            "break_after": 0.8,
            "characters": [],
            "motion": "slow_zoom_in",
            "visual": (
                "Interior of the stalled sedan: snow on the seats, a cup on its side on the floorboard. "
                "Empty child-seat shape, no lettering. No people in the car. Dead, cold interior."
            ),
        },
        {
            "beat_id": "the_car",
            "id": "biscuit_in_road",
            "spoken": "Biscuit stopped in the road.",
            "break_after": 1.2,
            "characters": ["biscuit"],
            "motion": "static",
            "visual": (
                "Biscuit stopped in the empty roadway, small, looking toward the sedan in the ditch. "
                "No other cars. Door still hanging. No people."
            ),
        },
        {
            "beat_id": "the_car",
            "id": "sniff_running_board",
            "spoken": "He went to the running board and sniffed the wet rubber, the cloth, the cold metal.",
            "break_after": 0.5,
            "characters": ["biscuit"],
            "motion": "slow_zoom_in",
            "visual": (
                "Biscuit at the sedan's running board in the ditch, sniffing wet rubber and cold metal. "
                "Faded bandana. No people. Car still in the ditch."
            ),
        },
        {
            "beat_id": "the_car",
            "id": "people_had_been",
            "spoken": "People had been here. The cloth still held them, and was losing them.",
            "ssml": (
                "People had been here.<break time=\"0.9s\" /> "
                "The cloth still held them, and was losing them."
            ),
            "break_after": 0.95,
            "characters": ["biscuit"],
            "motion": "slow_zoom_in",
            "visual": (
                "Close on Biscuit's muzzle at wet car cloth. No people visible — they have already left. "
                "The sedan remains empty, in the ditch."
            ),
        },
        # --- the_mitten ---
        {
            "beat_id": "the_mitten",
            "id": "mitten_in_drift",
            "spoken": "Beside the tire, half in a drift, a child's mitten. Red. Brighter than his bandana.",
            "ssml": (
                "Beside the tire, half in a drift, a child's mitten.<break time=\"0.35s\" /> "
                "Red.<break time=\"0.28s\" /> Brighter than his bandana."
            ),
            "break_after": 0.7,
            "characters": ["biscuit"],
            "motion": "slow_zoom_in",
            "facts_add": ["a child's bright red mitten lies beside the sedan's rear tire, half-buried"],
            "visual": (
                "Close still: a child's bright red mitten beside a rusted rear tire, half-buried in snow. "
                "Biscuit's muzzle nearby. Faded bandana duller than the mitten. No people. No other cars."
            ),
        },
        {
            "beat_id": "the_mitten",
            "id": "nosed_mitten",
            "spoken": "He nosed it. Snow fell off the cuff.",
            "ssml": 'He nosed it.<break time="0.4s" /> Snow fell off the cuff.',
            "break_after": 0.5,
            "characters": ["biscuit"],
            "motion": "slow_zoom_in",
            "visual": (
                "Biscuit nosing the red mitten; snow falling off the cuff. Close, simple. No people."
            ),
        },
        {
            "beat_id": "the_mitten",
            "id": "lining_heat",
            "spoken": "The lining still held a little heat, and a smell of soap and skin.",
            "break_after": 0.65,
            "characters": ["biscuit"],
            "motion": "static",
            "visual": (
                "Extreme close still of the red mitten's cuff and lining, Biscuit's nose just in frame. "
                "No people, no extra props."
            ),
        },
        {
            "beat_id": "the_mitten",
            "id": "picked_up",
            "spoken": "He picked it up. It was bigger in his mouth than it had looked on the ground.",
            "ssml": (
                "He picked it up.<break time=\"0.55s\" /> "
                "It was bigger in his mouth than it had looked on the ground."
            ),
            "break_after": 0.5,
            "characters": ["biscuit"],
            "motion": "slow_zoom_in",
            "facts_add": ["Biscuit carries the child's bright red mitten in his mouth"],
            "facts_remove": ["a child's bright red mitten lies beside the sedan's rear tire, half-buried"],
            "visual": (
                "Biscuit lifting the red mitten in his teeth. It looks large in his mouth. "
                "Faded bandana. Sedan tire behind him. No people."
            ),
        },
        {
            "beat_id": "the_mitten",
            "id": "did_not_put_down",
            "spoken": "He did not put it down.",
            "break_after": 1.15,
            "characters": ["biscuit"],
            "motion": "static",
            "visual": (
                "Biscuit standing with the red mitten held in his mouth. He is not dropping it. "
                "Empty winter ditch. No people."
            ),
        },
        # --- the_tracks ---
        {
            "beat_id": "the_tracks",
            "id": "prints_on_bank",
            "spoken": "Prints left the road and climbed the bank. One large. One small, dragging at the heel.",
            "ssml": (
                "Prints left the road and climbed the bank.<break time=\"0.4s\" /> "
                "One large.<break time=\"0.28s\" /> One small, dragging at the heel."
            ),
            "break_after": 0.55,
            "characters": [],
            "motion": "pan_left",
            "visual": (
                "Ditch bank climbing into a bare field: two sets of footprints, one large, one small and dragging. "
                "Empty road behind. No people in frame. Snow starting to fill the prints."
            ),
        },
        {
            "beat_id": "the_tracks",
            "id": "toward_trees",
            "spoken": "They went into the field toward a line of trees that might have been a creek.",
            "break_after": 0.55,
            "characters": ["biscuit"],
            "motion": "pan_right",
            "visual": (
                "Footprints heading into a white field toward a dark treeline. Biscuit small, mitten in his mouth. "
                "No houses, no cars in the field."
            ),
        },
        {
            "beat_id": "the_tracks",
            "id": "prints_filling",
            "spoken": (
                "The snow was filling them as he watched. A print was a print, and then it was only a dent, "
                "and then it was nothing."
            ),
            "ssml": (
                "The snow was filling them as he watched.<break time=\"0.5s\" /> "
                "A print was a print, and then it was only a dent, and then it was nothing."
            ),
            "break_after": 0.75,
            "characters": [],
            "motion": "slow_zoom_in",
            "visual": (
                "Close on footprints softening into dents, then nearly gone under new snow. "
                "No people, no cars. Simple ground-level still."
            ),
        },
        {
            "beat_id": "the_tracks",
            "id": "wading_drift",
            "spoken": "He went after what remained, mitten in his teeth, chest wading the drift.",
            "break_after": 0.7,
            "characters": ["biscuit"],
            "motion": "pan_left",
            "visual": (
                "Biscuit wading a drift, red mitten in his teeth, following fading prints. "
                "Empty field. No people, no houses."
            ),
        },
        # --- the_field ---
        {
            "beat_id": "the_field",
            "id": "field_took_sound",
            "spoken": "The field took the sound of the road away. Wire sang.",
            "ssml": (
                "The field took the sound of the road away.<break time=\"0.55s\" /> Wire sang."
            ),
            "break_after": 0.7,
            "characters": ["biscuit"],
            "motion": "slow_zoom_out",
            "visual": (
                "Biscuit small in a wide white field, fence wire in the wind. No road visible. "
                "No buildings. Mitten in his mouth."
            ),
        },
        {
            "beat_id": "the_field",
            "id": "paws_crust",
            "spoken": "Biscuit's paws broke the crust and found the hard dirt under it.",
            "break_after": 0.5,
            "characters": ["biscuit"],
            "motion": "slow_zoom_in",
            "visual": (
                "Close still of Biscuit's paws breaking snow crust to hard dirt. Simple. No people."
            ),
        },
        {
            "beat_id": "the_field",
            "id": "prints_gone",
            "spoken": "The small prints stopped. Then they were gone. He cast left. He cast right.",
            "ssml": (
                "The small prints stopped.<break time=\"0.55s\" /> Then they were gone.<break time=\"0.45s\" /> "
                "He cast left.<break time=\"0.28s\" /> He cast right."
            ),
            "break_after": 0.6,
            "characters": ["biscuit"],
            "motion": "pan_right",
            "visual": (
                "Biscuit in the field where small prints end. Casting left, then implied right. "
                "Empty white ground. Mitten in his mouth. No people."
            ),
        },
        {
            "beat_id": "the_field",
            "id": "shallower_went",
            "spoken": "Farther on they were on the ground again, shallower. He kept the mitten and went.",
            "ssml": (
                "Farther on they were on the ground again, shallower.<break time=\"0.45s\" /> "
                "He kept the mitten and went."
            ),
            "break_after": 0.7,
            "characters": ["biscuit"],
            "motion": "pan_left",
            "visual": (
                "Shallower prints again; Biscuit going on with the red mitten. Treeline ahead. No houses."
            ),
        },
        # --- the_creek ---
        {
            "beat_id": "the_creek",
            "id": "tracks_ended",
            "spoken": "At the creek the tracks ended. Ice. A crack of black water.",
            "ssml": (
                "At the creek the tracks ended.<break time=\"0.45s\" /> Ice.<break time=\"0.28s\" /> "
                "A crack of black water."
            ),
            "break_after": 0.7,
            "characters": ["biscuit"],
            "motion": "slow_zoom_in",
            "visual": (
                "Frozen creek at a treeline. Tracks ending. Ice with a crack of black water. "
                "Biscuit standing back. No house, no light, no people."
            ),
        },
        {
            "beat_id": "the_creek",
            "id": "no_house_no_light",
            "spoken": "No house. No light.",
            "ssml": 'No house.<break time="0.4s" /> No light.',
            "break_after": 1.15,
            "characters": [],
            "motion": "slow_zoom_out",
            "visual": (
                "Wide winter creek country: no house, no window light, no road. Darker trees only. "
                "Do not add a farmhouse or streetlamp."
            ),
        },
        {
            "beat_id": "the_creek",
            "id": "ears_flat",
            "spoken": "The trees were only a darker weather. Biscuit stood with his ears flat and the mitten dripping.",
            "ssml": (
                "The trees were only a darker weather.<break time=\"0.55s\" /> "
                "Biscuit stood with his ears flat and the mitten dripping."
            ),
            "break_after": 0.75,
            "characters": ["biscuit"],
            "motion": "static",
            "visual": (
                "Biscuit at the frozen creek, ears flat, wet red mitten dripping. Dark trees. "
                "No house, no people."
            ),
        },
        {
            "beat_id": "the_creek",
            "id": "smell_to_dark",
            "spoken": (
                "He went along the bank, upstream, then down. The smell thinned. "
                "Then it gathered again, low, where the water went into the dark."
            ),
            "ssml": (
                "He went along the bank, upstream, then down.<break time=\"0.45s\" /> "
                "The smell thinned.<break time=\"0.7s\" /> "
                "Then it gathered again, low, where the water went into the dark."
            ),
            "break_after": 0.8,
            "characters": ["biscuit"],
            "motion": "pan_right",
            "visual": (
                "Biscuit along an icy bank toward a dark concrete opening where water goes under. "
                "No people yet. Mitten in his mouth."
            ),
        },
        # --- the_culvert ---
        {
            "beat_id": "the_culvert",
            "id": "concrete_throat",
            "spoken": "The creek went under the road through a concrete throat. He smelled milk and wet wool. He went in.",
            "ssml": (
                "The creek went under the road through a concrete throat.<break time=\"0.45s\" /> "
                "He smelled milk and wet wool.<break time=\"0.4s\" /> He went in."
            ),
            "break_after": 0.55,
            "characters": ["biscuit"],
            "motion": "slow_zoom_in",
            "visual": (
                "Mouth of a concrete culvert under the road, Biscuit entering with the mitten. "
                "Gray wet walls. No people visible yet. Road above, no traffic."
            ),
        },
        {
            "beat_id": "the_culvert",
            "id": "they_were_there",
            "spoken": "They were there. A woman against the wall. A child in her lap.",
            "ssml": (
                "They were there.<break time=\"1.1s\" /> "
                "A woman against the wall.<break time=\"0.35s\" /> A child in her lap."
            ),
            "break_after": 0.6,
            "characters": ["biscuit", "woman", "child"],
            "motion": "slow_zoom_in",
            "facts_add": [
                "a woman in a thin gray coat and a small child in a navy snowsuit are inside the concrete culvert, not on the road"
            ],
            "visual": (
                "Interior of the culvert: woman sitting against the curve in a thin gray coat, "
                "small child in a navy snowsuit in her lap. Biscuit at the mouth, mitten in his teeth. "
                "Almost no light. They are not standing on the blacktop."
            ),
        },
        {
            "beat_id": "the_culvert",
            "id": "bare_hand_ice",
            "spoken": "One bare hand. Ice in the woman's hair.",
            "ssml": "One bare hand.<break time=\"0.4s\" /> Ice in the woman's hair.",
            "break_after": 0.55,
            "characters": ["woman", "child"],
            "motion": "slow_zoom_in",
            "visual": (
                "Close still: child's one bare hand, one red mitten missing; ice in the woman's dark hair. "
                "Navy snowsuit. No gore. Culvert concrete. Low light."
            ),
        },
        {
            "beat_id": "the_culvert",
            "id": "eyes_open_water",
            "spoken": "The child's eyes were open too. Neither of them spoke. Water ticked somewhere in the dark behind them.",
            "ssml": (
                "The child's eyes were open too.<break time=\"0.55s\" /> "
                "Neither of them spoke.<break time=\"0.7s\" /> "
                "Water ticked somewhere in the dark behind them."
            ),
            "break_after": 0.9,
            "characters": ["woman", "child"],
            "motion": "static",
            "visual": (
                "Quiet still of the child in the woman's lap, eyes open, both silent. Dark wet culvert. "
                "No extra people. No daylight highway scene."
            ),
        },
        # --- the_hand ---
        {
            "beat_id": "the_hand",
            "id": "dropped_mitten",
            "spoken": "He dropped the mitten on the bare hand and pressed against them.",
            "break_after": 0.6,
            "characters": ["biscuit", "woman", "child"],
            "motion": "slow_zoom_in",
            "facts_add": ["the child's bright red mitten is on the bare hand; Biscuit is not carrying it"],
            "facts_remove": ["Biscuit carries the child's bright red mitten in his mouth"],
            "visual": (
                "Biscuit dropping the red mitten onto the child's bare hand, pressing against them. "
                "Culvert interior. Low light. No extra people."
            ),
        },
        {
            "beat_id": "the_hand",
            "id": "child_sound_fingers",
            "spoken": "The child made a small sound. The woman's fingers found his fur and stayed, clumsy with cold.",
            "ssml": (
                "The child made a small sound.<break time=\"0.55s\" /> "
                "The woman's fingers found his fur and stayed, clumsy with cold."
            ),
            "break_after": 0.6,
            "characters": ["biscuit", "woman", "child"],
            "motion": "slow_zoom_in",
            "visual": (
                "Woman's ungloved fingers in Biscuit's scruff; child in the navy snowsuit. Culvert. Quiet."
            ),
        },
        {
            "beat_id": "the_hand",
            "id": "still_in_pipe",
            "spoken": (
                "He licked the knuckles. Then he was still. The wind moved through the pipe. "
                "Time passed. No one else came down the bank."
            ),
            "ssml": (
                "He licked the knuckles.<break time=\"0.45s\" /> Then he was still.<break time=\"0.7s\" /> "
                "The wind moved through the pipe.<break time=\"0.55s\" /> Time passed.<break time=\"0.85s\" /> "
                "No one else came down the bank."
            ),
            "break_after": 1.1,
            "characters": ["biscuit", "woman", "child"],
            "motion": "static",
            "visual": (
                "The three of them still in the culvert. No one on the bank. No rescuer yet. "
                "Wind implied at the pipe mouth. Do not add the plow or the driver."
            ),
        },
        # --- the_blacktop ---
        {
            "beat_id": "the_blacktop",
            "id": "left_them_not_far",
            "spoken": "Nothing came. After a time he left them. Not far.",
            "ssml": (
                "Nothing came.<break time=\"0.9s\" /> After a time he left them.<break time=\"0.4s\" /> Not far."
            ),
            "break_after": 0.65,
            "characters": ["biscuit"],
            "motion": "pan_right",
            "visual": (
                "Biscuit leaving the culvert mouth, climbing. Woman and child not in this frame — they remain inside. "
                "No plow yet. Empty winter ditch."
            ),
        },
        {
            "beat_id": "the_blacktop",
            "id": "climbed_blacktop",
            "spoken": "He climbed the iced slope to the blacktop, where a machine might still pass.",
            "break_after": 0.55,
            "characters": ["biscuit"],
            "motion": "slow_zoom_out",
            "visual": (
                "Biscuit climbing the iced slope to the empty blacktop. No cars passing. Dusk. No people."
            ),
        },
        {
            "beat_id": "the_blacktop",
            "id": "door_still_hung",
            "spoken": "The sedan's door still hung open in the ditch.",
            "break_after": 0.75,
            "characters": [],
            "motion": "static",
            "reuse": "sedan_in_ditch",
            "visual": (
                "The same stalled sedan in the ditch, door still hanging open. Empty road. No traffic."
            ),
        },
        {
            "beat_id": "the_blacktop",
            "id": "barked_in_road",
            "spoken": "He stood in the middle of the road and barked. He barked until his throat caught.",
            "ssml": (
                "He stood in the middle of the road and barked.<break time=\"0.45s\" /> "
                "He barked until his throat caught."
            ),
            "break_after": 0.55,
            "characters": ["biscuit"],
            "motion": "slow_zoom_in",
            "visual": (
                "Biscuit alone in the middle of the empty blacktop, barking. White dusk. "
                "Sedan in the ditch behind him. No other traffic, no people."
            ),
        },
        {
            "beat_id": "the_blacktop",
            "id": "country_ate_sound",
            "spoken": "The country ate the sound.",
            "break_after": 1.25,
            "characters": ["biscuit"],
            "motion": "slow_zoom_out",
            "visual": (
                "Wide empty country swallowing the dog. No answering lights, no cars, no houses. Iron sky."
            ),
        },
        # --- the_plow ---
        {
            "beat_id": "the_plow",
            "id": "amber_late",
            "spoken": "First a noise under the wind. Then amber, late, a long way off.",
            "ssml": (
                "First a noise under the wind.<break time=\"0.55s\" /> Then amber, late, a long way off."
            ),
            "break_after": 0.65,
            "characters": ["biscuit"],
            "motion": "pan_left",
            "facts_add": ["a snowplow with amber light is approaching on the long road; it is the only moving vehicle"],
            "visual": (
                "Far amber plow light on the long straight empty road. Biscuit small in the foreground. "
                "No other cars. Dusk."
            ),
        },
        {
            "beat_id": "the_plow",
            "id": "plow_wall",
            "spoken": "A plow, high and loud, throwing a wall of snow. It slowed for the hanging door.",
            "ssml": (
                "A plow, high and loud, throwing a wall of snow.<break time=\"0.5s\" /> "
                "It slowed for the hanging door."
            ),
            "break_after": 0.55,
            "characters": [],
            "motion": "pan_left",
            "visual": (
                "Snowplow filling the frame with amber light, blade throwing snow, slowing near the hanging sedan door. "
                "No other traffic. The sedan stays in the ditch."
            ),
        },
        {
            "beat_id": "the_plow",
            "id": "man_at_car",
            "spoken": "A man got down in a canvas coat. He looked in the car.",
            "ssml": "A man got down in a canvas coat.<break time=\"0.4s\" /> He looked in the car.",
            "break_after": 0.5,
            "characters": ["driver"],
            "motion": "slow_zoom_in",
            "facts_add": ["the plow driver in a canvas coat and orange vest is at the stalled sedan"],
            "visual": (
                "Older man in canvas chore coat, orange vest, wool cap, gray mustache, standing by the open sedan. "
                "Biscuit not required in frame. No other people."
            ),
        },
        {
            "beat_id": "the_plow",
            "id": "door_and_dog",
            "spoken": "He shut the door once, and the wind opened it again. He looked at the dog.",
            "ssml": (
                "He shut the door once, and the wind opened it again.<break time=\"0.7s\" /> "
                "He looked at the dog."
            ),
            "break_after": 0.85,
            "characters": ["biscuit", "driver"],
            "motion": "static",
            "facts_add": ["the sedan door is hanging open again after the wind opened it"],
            "visual": (
                "Driver looking at Biscuit in the road. Sedan door hanging open again. Amber plow light. "
                "No extra workers, no extra vehicles."
            ),
        },
        # --- the_pull ---
        {
            "beat_id": "the_pull",
            "id": "ditch_and_back",
            "spoken": "Biscuit ran to the ditch and back. To the man. To the ditch.",
            "ssml": (
                "Biscuit ran to the ditch and back.<break time=\"0.3s\" /> To the man.<break time=\"0.28s\" /> "
                "To the ditch."
            ),
            "break_after": 0.45,
            "characters": ["biscuit", "driver"],
            "motion": "pan_right",
            "visual": (
                "Biscuit running between the man at the sedan and the ditch. Simple action. Empty road otherwise."
            ),
        },
        {
            "beat_id": "the_pull",
            "id": "barked_from_pipe",
            "spoken": "The man shouted once. Biscuit barked from the dark of the pipe.",
            "ssml": "The man shouted once.<break time=\"0.5s\" /> Biscuit barked from the dark of the pipe.",
            "break_after": 0.55,
            "characters": ["biscuit", "driver"],
            "motion": "slow_zoom_in",
            "visual": (
                "Biscuit at the culvert mouth in the dark concrete, barking. Driver up the bank. No extra people."
            ),
        },
        {
            "beat_id": "the_pull",
            "id": "followed",
            "spoken": "The man came down the bank, one glove on the fence post, and followed.",
            "break_after": 0.75,
            "characters": ["biscuit", "driver"],
            "motion": "pan_left",
            "visual": (
                "Driver halfway down the bank, one glove on a fence post, following the dog, not the road. "
                "Orange vest. Culvert below."
            ),
        },
        # --- the_lift ---
        {
            "beat_id": "the_lift",
            "id": "knees_child",
            "spoken": "The man went to his knees in the wet concrete. He took the child.",
            "ssml": (
                "The man went to his knees in the wet concrete.<break time=\"0.45s\" /> He took the child."
            ),
            "break_after": 0.7,
            "characters": ["biscuit", "woman", "child", "driver"],
            "motion": "slow_zoom_in",
            "visual": (
                "Driver on his knees in the culvert, lifting the child in the navy snowsuit. "
                "Woman still sitting. Biscuit at the threshold, not in the way. Plow light at the mouth."
            ),
        },
        {
            "beat_id": "the_lift",
            "id": "got_her_up",
            "spoken": "The woman tried to stand and could not, so he came back for her and got her up.",
            "break_after": 0.55,
            "characters": ["woman", "driver"],
            "motion": "slow_zoom_in",
            "visual": (
                "Driver helping the woman in the thin gray coat to stand in the wet culvert. "
                "She is not walking far on her own. No extra rescuers."
            ),
        },
        {
            "beat_id": "the_lift",
            "id": "were_going",
            "spoken": "He said, We're going. That was all.",
            "ssml": "He said, We're going.<break time=\"0.7s\" /> That was all.",
            "break_after": 1.0,
            "characters": ["driver"],
            "motion": "static",
            "visual": (
                "Close still of the driver's face in plow light, mouth closed after speaking. "
                "Canvas coat, wool cap, ice in the mustache. Not theatrical."
            ),
        },
        {
            "beat_id": "the_lift",
            "id": "no_farther",
            "spoken": (
                "They climbed the bank in the plow light. Biscuit walked behind them as far as the "
                "truck's running board. No farther."
            ),
            "ssml": (
                "They climbed the bank in the plow light.<break time=\"0.45s\" /> "
                "Biscuit walked behind them as far as the truck's running board.<break time=\"0.7s\" /> "
                "No farther."
            ),
            "break_after": 0.95,
            "characters": ["biscuit", "woman", "child", "driver"],
            "motion": "slow_zoom_out",
            "facts_add": [
                "the woman and child are with the driver at the plow; they are leaving the culvert"
            ],
            "facts_remove": [
                "a woman in a thin gray coat and a small child in a navy snowsuit are inside the concrete culvert, not on the road"
            ],
            "visual": (
                "They climb the bank in amber plow light. Biscuit stops at the truck's running board. "
                "He does not get in. No other vehicles."
            ),
        },
        # --- the_record ---
        {
            "beat_id": "the_record",
            "id": "plow_receding",
            "spoken": "The cab door shut. Heat leaked out and was gone. The plow moved off, amber shrinking on the long straight road.",
            "ssml": (
                "The cab door shut.<break time=\"0.4s\" /> Heat leaked out and was gone.<break time=\"0.55s\" /> "
                "The plow moved off, amber shrinking on the long straight road."
            ),
            "break_after": 0.7,
            "characters": ["biscuit"],
            "motion": "pan_right",
            "facts_add": ["the plow is receding down the long straight road; Biscuit is alone again"],
            "facts_remove": [
                "a snowplow with amber light is approaching on the long road; it is the only moving vehicle",
                "the plow driver in a canvas coat and orange vest is at the stalled sedan",
                "the woman and child are with the driver at the plow; they are leaving the culvert",
            ],
            "visual": (
                "Night coming. Plow small and amber, receding on the long straight empty road. "
                "Biscuit on the shoulder. No other cars. Sedan still in the ditch."
            ),
        },
        {
            "beat_id": "the_record",
            "id": "field_taken_back",
            "spoken": "Biscuit stood by the sedan. Snow was already taking the field back.",
            "ssml": "Biscuit stood by the sedan.<break time=\"0.5s\" /> Snow was already taking the field back.",
            "break_after": 0.65,
            "characters": ["biscuit"],
            "motion": "slow_zoom_out",
            "visual": (
                "Biscuit by the stalled sedan in the ditch. Snow filling the field. No people. "
                "Door still hanging. Empty road."
            ),
        },
        {
            "beat_id": "the_record",
            "id": "went_on",
            "spoken": "He shook the ice from his coat and went on, small under that iron sky.",
            "break_after": 0.75,
            "characters": ["biscuit"],
            "motion": "pan_right",
            "visual": (
                "Biscuit shaking ice from his coat, walking south on the shoulder, tiny under an iron sky. "
                "No houses. No people. No cars on the road."
            ),
        },
        {
            "beat_id": "the_record",
            "id": "road_kept_no_record",
            "spoken": "Behind him the open door gathered white. The road kept no record.",
            "ssml": (
                "Behind him the open door gathered white.<break time=\"0.7s\" /> The road kept no record."
            ),
            "break_after": 1.2,
            "characters": [],
            "motion": "slow_zoom_in",
            "visual": (
                "The sedan's open door gathering snow. Empty road keeping nothing. No people, no traffic. "
                "Last still: elemental, unsentimental."
            ),
        },
    ]

"""Cinematic visual director for Biscuit and the Red Mitten.

Spoken strings are slices of the authored beat narration. Concatenating
``spoken`` across the plan must reproduce the literary text exactly
(whitespace-normalized). This file does not rewrite the story.

Unspoken shots have empty ``spoken`` text. They visualize implied travel
through the established topology; they do not invent plot.
"""

from __future__ import annotations

from typing import Any

from biscuit.world import Entity, Location, World, derived_forbidden, identity_lines

PLANNER_ID = "biscuit_and_the_red_mitten"

BISCUIT = (
    "a small cream-gold retriever mix with russet ears, slightly scruffy winter fur, "
    "and a faded red cloth bandana knotted at the throat"
)
SEDAN = (
    "the same faded brown-tan four-door American sedan, dull factory paint, rust at the "
    "wheel wells, nose angled down in the north-side ditch off the packed blacktop, "
    "passenger door hanging open"
)
WOMAN = (
    "the same young woman, early thirties, slight, thin gray cloth coat, wet jeans, "
    "indoor shoes packed with snow, dark hair iced at the temples, no gloves"
)
CHILD = (
    "the same small child of about four, navy snowsuit, dark curls in the hood, a plastic "
    "cup clipped to the suit"
)
DRIVER = (
    "the same older man, early sixties, solid, canvas chore coat, orange vest, heavy gloves, "
    "wool cap, gray mustache with ice in it"
)
SNOWPLOW = (
    "the same tired orange municipal snowplow, blade down, amber hazard lights"
)

_OUT = (
    "empty_road",
    "sedan_ditch",
    "road_bank",
    "open_field",
    "treeline",
    "creek_woods",
    "culvert_mouth",
    "culvert_interior",
)
_RETURN = tuple(reversed(_OUT))
_RESCUE = _OUT[1:]  # sedan_ditch → culvert_interior


def world() -> World:
    locations = {
        "empty_road": Location(
            id="empty_road",
            label="Empty county road",
            description=(
                "Isolated two-lane county blacktop through open Midwest farm country. "
                "Packed snow on pavement and shoulders. Fence. Field. Fence. Iron-gray sky."
            ),
            adjacent=("sedan_ditch",),
            never_show=("culvert",),
            prompt_forbid=("culvert",),
        ),
        "sedan_ditch": Location(
            id="sedan_ditch",
            label="Road at the abandoned sedan",
            description="The same stretch of blacktop, with the brown-tan sedan in the north-side ditch.",
            adjacent=("empty_road", "road_bank"),
            never_show=("culvert",),
            prompt_forbid=("culvert",),
        ),
        "road_bank": Location(
            id="road_bank",
            label="Ditch bank",
            description="Snowy bank leaving the blacktop. Field opening ahead. Road may sit at the top edge.",
            adjacent=("sedan_ditch", "open_field"),
            never_show=("culvert",),
            prompt_forbid=("culvert", "snowplow"),
        ),
        "open_field": Location(
            id="open_field",
            label="Open field",
            description="Deep snow-covered field. Distant dark treeline. Road gone unless a shot is a bank-edge transition.",
            adjacent=("road_bank", "treeline"),
            never_show=("sedan", "snowplow", "culvert"),
            remote_from=("empty_road", "sedan_ditch", "culvert_mouth", "culvert_interior"),
            prompt_forbid=("culvert", "sedan", "snowplow", "blacktop"),
        ),
        "treeline": Location(
            id="treeline",
            label="Treeline",
            description="The dark line of trees at the far side of the field, growing near.",
            adjacent=("open_field", "creek_woods"),
            never_show=("sedan", "snowplow"),
            remote_from=("empty_road", "sedan_ditch"),
            prompt_forbid=("sedan", "snowplow", "blacktop", "culvert"),
        ),
        "creek_woods": Location(
            id="creek_woods",
            label="Creek / woods",
            description="Darker enclosed winter woods. Frozen creek, ice, a crack of black water. Remote from the road.",
            adjacent=("treeline", "culvert_mouth"),
            never_show=("sedan", "snowplow"),
            remote_from=("empty_road", "sedan_ditch"),
            prompt_forbid=("sedan", "snowplow", "blacktop", "two-lane"),
        ),
        "culvert_mouth": Location(
            id="culvert_mouth",
            label="Culvert mouth",
            description="Weathered concrete culvert where the creek disappears. The road is not in this frame.",
            adjacent=("creek_woods", "culvert_interior"),
            never_show=("sedan", "snowplow"),
            remote_from=("empty_road", "sedan_ditch"),
            prompt_forbid=("sedan", "snowplow", "blacktop", "two-lane"),
        ),
        "culvert_interior": Location(
            id="culvert_interior",
            label="Culvert interior",
            description="Enclosed wet concrete pipe. Almost no light. No sky, no road, no vehicles.",
            adjacent=("culvert_mouth",),
            never_show=("sedan", "snowplow"),
            remote_from=("empty_road", "sedan_ditch"),
            prompt_forbid=("sedan", "snowplow", "blacktop", "two-lane"),
        ),
    }
    road_zone = ("empty_road", "sedan_ditch")
    people_after = (
        "culvert_interior",
        "culvert_mouth",
        "creek_woods",
        "treeline",
        "open_field",
        "road_bank",
        "sedan_ditch",
        "empty_road",
    )
    entities = {
        "biscuit": Entity(id="biscuit", canonical=f"Biscuit is {BISCUIT}.", kind="character", first_shot="biscuit_on_road"),
        "sedan": Entity(
            id="sedan",
            canonical=SEDAN + ". It never moves. The passenger door stays hanging open. Snow gathers on it.",
            kind="prop",
            movable=False,
            home_location="sedan_ditch",
            first_shot="sedan_in_ditch",
            allowed_locations=("sedan_ditch", "road_bank"),
        ),
        "mitten": Entity(
            id="mitten",
            canonical="one brighter red child's knitted mitten, not Biscuit's faded bandana",
            kind="prop",
            first_shot="mitten_by_tire",
        ),
        "road": Entity(
            id="road",
            canonical="the same isolated two-lane county blacktop, packed snow, fence and field under iron sky",
            kind="set",
            movable=False,
            home_location="empty_road",
            allowed_locations=road_zone + ("road_bank",),
        ),
        "field": Entity(
            id="field",
            canonical="the same open snow-covered field with a distant dark treeline and sparse fence far to one side",
            kind="set",
            movable=False,
            home_location="open_field",
            allowed_locations=("open_field", "road_bank", "treeline"),
        ),
        "creek": Entity(
            id="creek",
            canonical="the same frozen creek at the dark treeline, ice at the edges, a crack of black water",
            kind="set",
            movable=False,
            home_location="creek_woods",
            allowed_locations=("creek_woods", "culvert_mouth", "treeline"),
        ),
        "culvert": Entity(
            id="culvert",
            canonical="the same weathered concrete culvert, gray wet throat, low, dim, at creek level",
            kind="set",
            movable=False,
            home_location="culvert_mouth",
            first_shot="culvert_mouth",
            allowed_locations=("culvert_mouth", "culvert_interior", "creek_woods"),
        ),
        "woman": Entity(
            id="woman",
            canonical=WOMAN,
            kind="character",
            first_shot="culvert_discovery",
            allowed_locations=people_after,
        ),
        "child": Entity(
            id="child",
            canonical=CHILD,
            kind="character",
            first_shot="culvert_discovery",
            allowed_locations=people_after,
        ),
        "snowplow": Entity(
            id="snowplow",
            canonical=SNOWPLOW,
            kind="vehicle",
            movable=True,
            home_location="sedan_ditch",
            first_shot="amber_far",
            allowed_locations=("empty_road", "sedan_ditch"),
        ),
        "driver": Entity(
            id="driver",
            canonical=DRIVER,
            kind="character",
            first_shot="plow_at_sedan",
            allowed_locations=_OUT,
        ),
    }
    return World(
        locations=locations,
        entities=entities,
        journeys={
            "outbound": _OUT,
            "return": _RETURN,
            "rescue": _RESCUE,
        },
        weather="incoming blizzard; wind over frozen fields; snow filling tracks as they are made",
        light="iron afternoon thinning toward a white dusk, then nightfall",
    )


SEQUENCES: list[dict[str, Any]] = [
    {"id": "empty_road", "title": "Empty road", "location_id": "empty_road", "summary": "Establish the isolated winter road. Biscuit arrives alone."},
    {"id": "abandoned_sedan", "title": "Abandoned sedan", "location_id": "sedan_ditch", "summary": "The car is discovered in the ditch. The mitten is found here."},
    {"id": "field_trail", "title": "Field / trail", "location_id": "open_field", "summary": "Biscuit leaves the road and crosses open country toward the trees."},
    {"id": "creek_woods", "title": "Creek / woods", "location_id": "creek_woods", "summary": "The country closes in. Ice, black water, darker trees."},
    {"id": "culvert", "title": "Culvert", "location_id": "culvert_interior", "summary": "He enters the concrete throat and finds the woman and child."},
    {"id": "return_to_road", "title": "Return to road", "location_id": "sedan_ditch", "summary": "He recrosses the established field and climbs back to the road and sedan."},
    {"id": "snowplow_rescue", "title": "Snowplow arrival / rescue", "location_id": "sedan_ditch", "summary": "The plow appears at the road. Biscuit leads the driver back through the field to the remote culvert, then they return."},
    {"id": "departure", "title": "Departure / empty road", "location_id": "empty_road", "summary": "The plow leaves. Biscuit remains and goes on."},
]


_SEQUENCE_LIGHT = {
    "empty_road": "iron afternoon",
    "abandoned_sedan": "iron afternoon",
    "field_trail": "iron afternoon thinning",
    "creek_woods": "dying winter light",
    "culvert": "almost no light",
    "return_to_road": "white dusk",
    "snowplow_rescue": "white dusk",
    "departure": "nightfall",
}

_MITTEN_STATE = {
    "mitten_by_tire": "beside_tire_then_in_biscuit_mouth",
    "leaving_the_road": "in_biscuit_mouth",
    "field_crossing": "in_biscuit_mouth",
    "creek_woods": "in_biscuit_mouth",
    "culvert_mouth": "in_biscuit_mouth",
    "culvert_discovery": "in_biscuit_mouth",
    "culvert_vigil": "on_child_hand",
    "rescue_in_culvert": "on_child_hand",
    "rescue_return_field": "on_child_hand",
    "running_board": "on_child_hand",
}


def _fill(shot: dict[str, Any], world_obj: World, *, revealed: set[str]) -> dict[str, Any]:
    visible = list(shot.get("visible_entities") or [])
    shot["visible_entities"] = visible
    shot["visible_elements"] = list(shot.get("visible_elements") or visible)
    shot["entity_identity"] = identity_lines(world_obj, visible)
    shot["forbidden_elements"] = derived_forbidden(
        world_obj,
        str(shot.get("location_id") or ""),
        revealed=revealed | set(visible),
    )
    continuity = dict(shot.get("continuity") or {})
    continuity.setdefault("weather", world_obj.weather)
    continuity.setdefault("light", _SEQUENCE_LIGHT.get(str(shot.get("sequence_id") or ""), world_obj.light))
    mitten = _MITTEN_STATE.get(str(shot.get("id") or ""))
    if mitten:
        continuity.setdefault("mitten", mitten)
    if "sedan" in visible:
        continuity.setdefault("sedan_door", "passenger_door_hanging_open")
        continuity.setdefault("sedan_location", "north_side_ditch")
    if "snowplow" in visible:
        continuity.setdefault("snowplow_location", "on_the_road")
    shot["continuity"] = continuity
    return shot


def shots() -> list[dict[str, Any]]:
    """Return ordered cinematic shots covering every spoken word of Red Mitten."""

    w = world()
    revealed: set[str] = set()
    filled: list[dict[str, Any]] = []
    for shot in _shot_defs():
        filled.append(_fill(shot, w, revealed=revealed))
        revealed.update(shot["visible_entities"])
    return filled


def _shot_defs() -> list[dict[str, Any]]:
    return [
        {
            "id": "empty_road",
            "sequence_id": "empty_road",
            "location_id": "empty_road",
            "beat_id": "the_road",
            "title": "A road without a town",
            "emotion": "isolation",
            "characters": [],
            "visible_entities": ["road"],
            "motion": "static",
            "break_after": 0.7,
            "reference_shot_id": "",
            "shot_description": "Empty two-lane winter road. No dog, no car, no plow.",
            "spoken": (
                "The road ran without a town to finish it. Fence. Field. A sky the color of wet iron. "
                "Ice stood on the wire in little teeth."
            ),
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
            "visible_entities": ["biscuit", "road"],
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
            "visible_entities": ["biscuit", "sedan", "road"],
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
            "local_prompt": (
                f"Wide cinematic still of {SEDAN}. {BISCUIT} small in the road near the car. "
                "Wind. Iron-gray sky. Documentary winter light."
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
            "visible_entities": ["biscuit", "sedan", "mitten"],
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
            "local_prompt": (
                f"Medium cinematic still at the rear wheel of {SEDAN}. A child's bright red knitted "
                f"mitten half in a drift beside the tire. {BISCUIT} lowering his cream muzzle toward "
                "the mitten, faded red bandana at his throat. Flat overcast winter light."
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
            "visible_entities": ["biscuit", "mitten", "road", "sedan", "field"],
            "motion": "slow_zoom_out",
            "break_after": 0.5,
            "reference_shot_id": "sedan_in_ditch",
            "shot_description": "Transition: Biscuit leaves the road for the field. Road and sedan fall to the margin.",
            "spoken": (
                "Prints left the road and climbed the bank. One large. One small, dragging at the heel. "
                "They went into the field toward a line of trees that might have been a creek."
            ),
            "local_prompt": (
                "Wide still from a snowy ditch bank looking into an open field. "
                f"{BISCUIT.capitalize()} climbing away from the roadway through deep snow, a bright red "
                "child's mitten held in his mouth. A dark line of trees far ahead. Behind him, at the "
                f"edge of frame, {SEDAN} and the two-lane blacktop are already falling away. Blowing snow."
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
            "visible_entities": ["biscuit", "mitten", "field"],
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
            "visible_entities": ["biscuit", "mitten", "creek"],
            "motion": "static",
            "break_after": 0.65,
            "reference_shot_id": "",
            "travel_path": ["open_field", "treeline", "creek_woods"],
            "shot_description": "Creek and darker trees. Remote from the road. No people yet.",
            "spoken": (
                "At the creek the tracks ended. Ice. A crack of black water. No house. No light. "
                "The trees were only a darker weather. Biscuit stood with his ears flat and the mitten "
                "dripping. He went along the bank, upstream, then down. The smell thinned. Then it "
                "gathered again, low, where the water went into the dark."
            ),
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
            "visible_entities": ["biscuit", "mitten", "culvert", "creek"],
            "motion": "slow_zoom_in",
            "break_after": 0.4,
            "reference_shot_id": "",
            "shot_description": "Concrete culvert mouth. He goes in. Occupants not yet visible.",
            "spoken": (
                "The creek went under the road through a concrete throat. He smelled milk and wet wool. "
                "He went in."
            ),
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
            "visible_entities": ["biscuit", "mitten", "woman", "child", "culvert"],
            "motion": "static",
            "break_after": 0.7,
            "reference_shot_id": "culvert_mouth",
            "shot_description": "First reveal of the woman and child.",
            "spoken": (
                "They were there. A woman against the wall. A child in her lap. One bare hand. Ice in "
                "the woman's hair. The child's eyes were open too. Neither of them spoke. Water ticked "
                "somewhere in the dark behind them."
            ),
            "local_prompt": (
                "Interior of a dark concrete culvert. "
                f"{WOMAN.capitalize()} sitting against the curved wet wall. "
                f"{CHILD} in her lap, one red mitten, one bare chapped hand. "
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
            "visible_entities": ["biscuit", "mitten", "woman", "child", "culvert"],
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
            "local_prompt": (
                "Interior of a dark concrete culvert, close and still. "
                f"{CHILD.capitalize()} now has the bright red mitten on the previously bare hand. "
                f"{WOMAN} has her ungloved fingers in the fur of {BISCUIT}, who is pressed against them. "
                "Dim wet concrete. Almost no light."
            ),
        },
        {
            "id": "return_across_field",
            "sequence_id": "return_to_road",
            "location_id": "open_field",
            "beat_id": "the_blacktop",
            "title": "Back through the field",
            "emotion": "determination",
            "characters": ["biscuit"],
            "visible_entities": ["biscuit", "field"],
            "motion": "static",
            "break_after": 0.45,
            "reference_shot_id": "field_crossing",
            "travel_path": ["culvert_interior", "culvert_mouth", "creek_woods", "treeline", "open_field"],
            "shot_description": "Implied return: Biscuit recrosses the established open field. Culvert and road are both out of frame.",
            "spoken": "Nothing came. After a time he left them. Not far.",
            "local_prompt": (
                "Wide winter field, the same open country as before. "
                f"{BISCUIT.capitalize()} walking through deep snow, no mitten in his mouth, heading "
                "toward the unseen far side of the field. Dark treeline behind him. Sparse fence. "
                "Iron-gray dusk. Empty of people and vehicles."
            ),
        },
        {
            "id": "return_to_sedan",
            "sequence_id": "return_to_road",
            "location_id": "sedan_ditch",
            "beat_id": "the_blacktop",
            "title": "The country ate the sound",
            "emotion": "determination",
            "characters": ["biscuit"],
            "visible_entities": ["biscuit", "sedan", "road"],
            "motion": "static",
            "break_after": 0.85,
            "reference_shot_id": "sedan_in_ditch",
            "travel_path": ["open_field", "road_bank", "sedan_ditch"],
            "shot_description": "Back at the established road and sedan. Still no plow.",
            "spoken": (
                "He climbed the iced slope to the blacktop, where a machine might still pass. "
                "The sedan's door still hung open in the ditch. He stood in the middle of the road "
                "and barked. He barked until his throat caught. The country ate the sound."
            ),
            "local_prompt": (
                "Wide still of an empty two-lane winter road at white dusk. "
                f"{BISCUIT.capitalize()} standing alone in the middle of the blacktop. Behind him, "
                f"{SEDAN}. Fence. Iron sky. The country is empty."
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
            "visible_entities": ["biscuit", "road", "snowplow"],
            "motion": "slow_zoom_in",
            "break_after": 0.7,
            "reference_shot_id": "empty_road",
            "shot_description": "First appearance of the snowplow: distant amber on the long road.",
            "spoken": "First a noise under the wind. Then amber, late, a long way off.",
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
            "visible_entities": ["biscuit", "sedan", "road", "snowplow", "driver"],
            "motion": "static",
            "break_after": 0.55,
            "reference_shot_id": "sedan_in_ditch",
            "shot_description": "Plow stopped at the sedan. Driver on the ground. Culvert is not here.",
            "spoken": (
                "A plow, high and loud, throwing a wall of snow. It slowed for the hanging door. "
                "A man got down in a canvas coat. He looked in the car. He shut the door once, and the "
                "wind opened it again. He looked at the dog."
            ),
            "local_prompt": (
                f"{SNOWPLOW.capitalize()} stopped on a two-lane winter road, amber lights washing the snow. "
                f"{SEDAN}. {DRIVER} standing beside the sedan. {BISCUIT} in the road watching him. White dusk."
            ),
        },
        {
            "id": "leading_at_road",
            "sequence_id": "snowplow_rescue",
            "location_id": "sedan_ditch",
            "beat_id": "the_pull",
            "title": "To the man. To the ditch.",
            "emotion": "insistence",
            "characters": ["biscuit", "driver"],
            "visible_entities": ["biscuit", "driver", "sedan", "road", "snowplow"],
            "motion": "static",
            "break_after": 0.35,
            "reference_shot_id": "plow_at_sedan",
            "shot_description": "Biscuit runs between the driver and the roadside ditch. The remote culvert is not visible.",
            "spoken": (
                "Biscuit ran to the ditch and back. To the man. To the ditch. The man shouted once."
            ),
            "local_prompt": (
                f"{BISCUIT.capitalize()} in the snowy roadside ditch near {SEDAN}, turning back toward "
                f"{DRIVER} standing in the road. {SNOWPLOW} stopped on the blacktop behind them. "
                "Open country beyond the ditch, not a drain. White dusk."
            ),
        },
        {
            "id": "driver_down_bank",
            "sequence_id": "snowplow_rescue",
            "location_id": "road_bank",
            "beat_id": "the_pull",
            "title": "And followed",
            "emotion": "insistence",
            "characters": ["biscuit", "driver"],
            "visible_entities": ["biscuit", "driver", "field"],
            "motion": "slow_zoom_in",
            "break_after": 0.4,
            "reference_shot_id": "leaving_the_road",
            "shot_description": "Driver leaves the road and follows Biscuit down the bank toward the field. No culvert.",
            "spoken": (
                "Biscuit barked from the dark of the pipe. The man came down the bank, one glove on the "
                "fence post, and followed."
            ),
            "local_prompt": (
                "Snowy ditch bank below a farm fence. "
                f"{DRIVER.capitalize()} coming down through snow, one heavy glove on a fence post. "
                f"{BISCUIT} ahead of him, already entering the open field, a dark treeline far ahead. "
                "The blacktop is only at the top edge of frame. Blowing snow."
            ),
        },
        {
            "id": "lead_across_field",
            "sequence_id": "snowplow_rescue",
            "location_id": "open_field",
            "beat_id": "the_pull",
            "title": "Across the established field",
            "emotion": "insistence",
            "characters": ["biscuit", "driver"],
            "visible_entities": ["biscuit", "driver", "field"],
            "motion": "static",
            "break_after": 2.6,
            "unspoken": True,
            "hold_seconds": 2.6,
            "reference_shot_id": "field_crossing",
            "shot_description": "Unspoken: Biscuit leads the driver across the same open field toward the treeline.",
            "spoken": "",
            "local_prompt": (
                "Wide winter field, the same open country established earlier. "
                f"{BISCUIT.capitalize()} wading deep snow toward a distant dark treeline. "
                f"{DRIVER.capitalize()} following behind him, small in the white. Sparse fence. Iron dusk sky. "
                "Empty of vehicles."
            ),
        },
        {
            "id": "approach_creek_woods",
            "sequence_id": "snowplow_rescue",
            "location_id": "creek_woods",
            "beat_id": "the_pull",
            "title": "The established woods",
            "emotion": "insistence",
            "characters": ["biscuit", "driver"],
            "visible_entities": ["biscuit", "driver", "creek"],
            "motion": "static",
            "break_after": 2.2,
            "unspoken": True,
            "hold_seconds": 2.2,
            "reference_shot_id": "creek_woods",
            "travel_path": ["open_field", "treeline", "creek_woods"],
            "shot_description": "Unspoken: Biscuit and the driver reach the same dark creek/woods, still far from the road.",
            "spoken": "",
            "local_prompt": (
                "The same frozen creek at a dark winter treeline established earlier. "
                f"{BISCUIT.capitalize()} leading {DRIVER} along the icy bank. "
                "Bare trees closing in. Ice and a crack of black water. "
                "Enclosed woods, remote country. No vehicles."
            ),
        },
        {
            "id": "arrive_remote_culvert",
            "sequence_id": "snowplow_rescue",
            "location_id": "culvert_mouth",
            "beat_id": "the_lift",
            "title": "The pipe, far from the road",
            "emotion": "insistence",
            "characters": ["biscuit", "driver"],
            "visible_entities": ["biscuit", "driver", "culvert", "creek"],
            "motion": "static",
            "break_after": 2.4,
            "unspoken": True,
            "hold_seconds": 2.4,
            "reference_shot_id": "culvert_mouth",
            "shot_description": "Unspoken: driver arrives at the remote culvert mouth. Road, sedan, and plow are not here.",
            "spoken": "",
            "local_prompt": (
                "The same weathered concrete culvert mouth at a frozen winter creek, enclosed by dark trees. "
                f"{DRIVER.capitalize()} standing in snow at the gray throat. {BISCUIT} at the dark opening. "
                "Dim dusk in the woods. No vehicles."
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
            "visible_entities": ["biscuit", "woman", "child", "driver", "culvert", "mitten"],
            "motion": "static",
            "break_after": 0.55,
            "reference_shot_id": "culvert_vigil",
            "shot_description": "Driver lifts the child inside the remote culvert.",
            "spoken": (
                "The man went to his knees in the wet concrete. He took the child. The woman tried to "
                "stand and could not, so he came back for her and got her up. He said, We're going. "
                "That was all."
            ),
            "local_prompt": (
                "Inside the wet concrete culvert. "
                f"{DRIVER.capitalize()} on his knees, lifting {CHILD}. "
                f"{WOMAN} trying to rise. {BISCUIT.capitalize()} at the threshold, not in the way. "
                "Dim light at the mouth. Documentary still."
            ),
        },
        {
            "id": "rescue_return_field",
            "sequence_id": "snowplow_rescue",
            "location_id": "open_field",
            "beat_id": "the_lift",
            "title": "Back across the field",
            "emotion": "extraction",
            "characters": ["biscuit", "woman", "child", "driver"],
            "visible_entities": ["biscuit", "woman", "child", "driver", "field"],
            "motion": "static",
            "break_after": 2.5,
            "unspoken": True,
            "hold_seconds": 2.5,
            "reference_shot_id": "lead_across_field",
            "travel_path": ["culvert_interior", "culvert_mouth", "creek_woods", "treeline", "open_field"],
            "shot_description": "Unspoken: they recross the established field toward the road. The plow is not in this country.",
            "spoken": "",
            "local_prompt": (
                "Wide winter field at dusk. "
                f"{DRIVER.capitalize()} carrying {CHILD}, {WOMAN} leaning on him, "
                f"{BISCUIT} walking behind through deep snow. Dark treeline behind them. "
                "They are small in the open white. Empty of vehicles."
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
            "visible_entities": ["biscuit", "woman", "child", "driver", "snowplow", "sedan", "road"],
            "motion": "static",
            "break_after": 0.95,
            "reference_shot_id": "plow_at_sedan",
            "travel_path": ["open_field", "road_bank", "sedan_ditch"],
            "shot_description": "They reach the plow that waited at the road. Biscuit stops at the running board.",
            "spoken": (
                "They climbed the bank in the plow light. Biscuit walked behind them as far as the "
                "truck's running board. No farther."
            ),
            "local_prompt": (
                f"Dusk at {SNOWPLOW}. {DRIVER.capitalize()} helping {WOMAN} and {CHILD} "
                f"toward the cab. Amber light on the snow. {BISCUIT.capitalize()} standing at the truck's "
                f"running board, going no farther. {SEDAN} in the ditch nearby."
            ),
        },
        {
            "id": "plow_recedes",
            "sequence_id": "departure",
            "location_id": "sedan_ditch",
            "beat_id": "the_record",
            "title": "Amber shrinking",
            "emotion": "aftertaste",
            "characters": ["biscuit"],
            "visible_entities": ["biscuit", "sedan", "road", "snowplow"],
            "motion": "slow_zoom_out",
            "break_after": 0.65,
            "reference_shot_id": "amber_far",
            "shot_description": "The plow leaves. The country begins to empty.",
            "spoken": (
                "The cab door shut. Heat leaked out and was gone. The plow moved off, amber shrinking "
                "on the long straight road. Biscuit stood by the sedan."
            ),
            "local_prompt": (
                "Long straight winter road at nightfall. "
                f"{SNOWPLOW.capitalize()} already small, amber lights shrinking away down the empty blacktop. "
                f"{BISCUIT.capitalize()} standing by {SEDAN}. The country becoming empty again."
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
            "visible_entities": ["biscuit", "road"],
            "motion": "static",
            "break_after": 0.7,
            "reference_shot_id": "biscuit_on_road",
            "shot_description": "Biscuit continues. The landscape is empty again.",
            "spoken": (
                "Snow was already taking the field back. He shook the ice from his coat and went on, "
                "small under that iron sky."
            ),
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
            "visible_entities": ["sedan", "road"],
            "motion": "slow_zoom_in",
            "break_after": 1.2,
            "reference_shot_id": "sedan_in_ditch",
            "shot_description": "Final still: the same sedan, door gathering white. No figures.",
            "spoken": "Behind him the open door gathered white. The road kept no record.",
            "local_prompt": (
                f"{SEDAN.capitalize()}, snow gathering on the seats and the hanging door. Empty of figures. "
                "Fence and field and iron sky. The country keeping nothing. Documentary still."
            ),
        },
    ]


# Older registry code expected this name.
units = shots
VISUAL_BIBLE = {
    entity_id: entity.canonical for entity_id, entity in world().entities.items()
}
VISUAL_BIBLE.update({loc.id: loc.description for loc in world().locations.values()})

# Logical production-design plates. Stories never store provider file ids.
REFERENCE_ASSETS: list[dict[str, Any]] = [
    {
        "id": "biscuit_master",
        "category": "character",
        "entity_ids": ["biscuit"],
        "priority": 90,
        "description": (
            "Small cream-gold retriever mix, russet ears, scruffy winter fur, faded red "
            "cloth bandana knotted at the throat. The same dog in every frame."
        ),
        "why": "Recurring protagonist. Independent generation keeps inventing a different dog.",
        "continuity_notes": "Bandana is faded cloth, never as bright as the child's mitten.",
    },
    {
        "id": "empty_road_master",
        "category": "location",
        "location_ids": ["empty_road"],
        "priority": 92,
        "description": (
            "Isolated two-lane county blacktop through open Midwest farm country. Packed snow "
            "on pavement and shoulders. Fence. Field. Iron-gray sky. No traffic."
        ),
        "why": "Road geometry and emptiness must stay stable whenever the camera is on the empty road.",
        "continuity_notes": "No cars, no plow, no culvert. The sedan is not here yet or has already been left behind.",
    },
    {
        "id": "roadside_ditch_master",
        "category": "location",
        "location_ids": ["sedan_ditch", "road_bank"],
        "priority": 100,
        "description": (
            "The same stretch of blacktop at the abandoned sedan: packed two-lane, north-side "
            "ditch, snowbank, and distant tree-line. Establishes road / ditch / shoulder geography."
        ),
        "why": (
            "This is the continuity failure that started the art-direction work. The ditch, "
            "shoulder, and road kept reinventing themselves between shots."
        ),
        "continuity_notes": "North-side ditch. No unexpected traffic. Culvert is not visible from here.",
    },
    {
        "id": "abandoned_car_master",
        "category": "vehicle",
        "entity_ids": ["sedan"],
        "priority": 95,
        "description": (
            "The same faded brown-tan four-door American sedan, dull factory paint, rust at "
            "the wheel wells, nose angled down in the north-side ditch, passenger door hanging open."
        ),
        "why": "Vehicle model, damage, orientation, and snow accumulation must not move or change.",
        "continuity_notes": "It never moves. Passenger door stays open. Snow gathers on it. Not in the field or culvert.",
    },
    {
        "id": "open_field_master",
        "category": "location",
        "location_ids": ["open_field", "treeline"],
        "priority": 88,
        "description": (
            "The same open snow-covered field with a distant dark treeline and sparse fence "
            "far to one side. Road gone unless the camera is still on the bank edge."
        ),
        "why": "The field is crossed outbound, return, and during the rescue. Scale and horizon must hold.",
        "continuity_notes": "No sedan, no snowplow, no culvert, no blacktop in the middle of the field.",
    },
    {
        "id": "creek_woods_master",
        "category": "location",
        "location_ids": ["creek_woods"],
        "priority": 84,
        "description": (
            "Darker enclosed winter woods. The same frozen creek, ice at the edges, a crack of black water."
        ),
        "why": "The woods close the country in. Creek geometry must stay recognizable on the return journey.",
        "continuity_notes": "Remote from the road. No sedan, no plow, no two-lane blacktop.",
    },
    {
        "id": "culvert_master",
        "category": "location",
        "location_ids": ["culvert_mouth", "culvert_interior"],
        "priority": 93,
        "description": (
            "The same weathered concrete culvert: gray wet throat, low, dim, at creek level. "
            "Mouth and interior share one geometry."
        ),
        "why": "Culvert shape and surrounding terrain were being reinvented. Discovery and rescue share this place.",
        "continuity_notes": "No road, no sedan, no snowplow. Almost no light inside.",
    },
    {
        "id": "child_master",
        "category": "character",
        "entity_ids": ["child"],
        "priority": 82,
        "description": (
            "The same small child of about four, navy snowsuit, dark curls in the hood, "
            "one red mitten, one bare hand, a plastic cup clipped to the suit."
        ),
        "why": "The child is found once and carried home. Identity must not drift.",
        "continuity_notes": "Never walking after the field. She is held or sitting.",
    },
    {
        "id": "woman_master",
        "category": "character",
        "entity_ids": ["woman"],
        "priority": 80,
        "description": (
            "The same young woman, early thirties, slight, thin gray cloth coat, wet jeans, "
            "indoor shoes packed with snow, dark hair iced at the temples, no gloves."
        ),
        "why": "Adult victim identity must remain the same woman from the culvert to the plow.",
        "continuity_notes": "She does not walk far once found. Sitting or being carried.",
    },
    {
        "id": "man_master",
        "category": "character",
        "entity_ids": ["driver"],
        "priority": 80,
        "description": (
            "The same older man, early sixties, solid, canvas chore coat, orange vest, "
            "heavy gloves, wool cap, gray mustache with ice in it."
        ),
        "why": "The driver is the only adult helper. A new face on the return would break the rescue.",
        "continuity_notes": "Appears only after the plow arrives.",
    },
    {
        "id": "snowplow_master",
        "category": "vehicle",
        "entity_ids": ["snowplow"],
        "priority": 76,
        "description": "The same tired orange municipal snowplow, blade down, amber hazard lights.",
        "why": "The plow is a late, important vehicle. It must not appear as a different truck.",
        "continuity_notes": "Stays on the road. Never in the field, woods, or culvert.",
    },
    {
        "id": "red_mitten_master",
        "category": "prop",
        "entity_ids": ["mitten"],
        "priority": 58,
        "description": "One brighter red child's knitted mitten, not Biscuit's faded bandana.",
        "why": "The title object is small and easy to lose or confuse with the bandana.",
        "continuity_notes": "Brighter than the bandana. One mitten only until it is returned to the child.",
    },
]

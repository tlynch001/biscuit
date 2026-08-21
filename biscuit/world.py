"""Reusable director geography: locations, entities, and spatial checks.

This is not a generic film engine. It exists so a story plan can declare
a small topology and persistent identities, then fail closed when a shot
teleports a character or shows something that cannot be in frame.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class Location:
    """One place the camera can be."""

    id: str
    label: str
    description: str
    adjacent: tuple[str, ...]
    never_show: tuple[str, ...] = ()
    remote_from: tuple[str, ...] = ()
    prompt_forbid: tuple[str, ...] = ()


@dataclass(frozen=True)
class Entity:
    """A recurring character, prop, vehicle, or set piece."""

    id: str
    canonical: str
    kind: str
    movable: bool = True
    home_location: str | None = None
    first_shot: str | None = None
    allowed_locations: tuple[str, ...] | None = None


@dataclass
class World:
    locations: dict[str, Location]
    entities: dict[str, Entity]
    journeys: dict[str, tuple[str, ...]] = field(default_factory=dict)
    weather: str = ""
    light: str = ""

    def location(self, location_id: str) -> Location:
        return self.locations[location_id]

    def entity(self, entity_id: str) -> Entity:
        return self.entities[entity_id]


def shortest_path(world: World, start: str, end: str) -> list[str] | None:
    """Breadth-first path including ``start`` and ``end``. Same node is ``[start]``."""

    if start == end:
        return [start]
    if start not in world.locations or end not in world.locations:
        return None
    queue: list[list[str]] = [[start]]
    seen = {start}
    while queue:
        path = queue.pop(0)
        for neighbor in world.locations[path[-1]].adjacent:
            if neighbor in seen:
                continue
            if neighbor not in world.locations:
                continue
            next_path = path + [neighbor]
            if neighbor == end:
                return next_path
            seen.add(neighbor)
            queue.append(next_path)
    return None


def is_adjacent_or_same(world: World, a: str, b: str) -> bool:
    if a == b:
        return True
    loc = world.locations.get(a)
    return bool(loc and b in loc.adjacent)


def walk_covers(world: World, path: Iterable[str]) -> bool:
    nodes = list(path)
    if len(nodes) < 2:
        return True
    for left, right in zip(nodes, nodes[1:]):
        if not is_adjacent_or_same(world, left, right):
            return False
    return True


def derived_forbidden(world: World, location_id: str, *, revealed: set[str]) -> list[str]:
    """Entities that must not be named or shown in this location/state."""

    loc = world.locations.get(location_id)
    forbidden: list[str] = []
    if loc:
        forbidden.extend(loc.never_show)
    for entity in world.entities.values():
        if entity.first_shot and entity.id not in revealed:
            if entity.id not in forbidden:
                forbidden.append(entity.id)
        allowed = entity.allowed_locations
        if allowed is not None and location_id not in allowed and entity.id not in forbidden:
            forbidden.append(entity.id)
    return forbidden


def identity_lines(world: World, visible_entities: Iterable[str]) -> list[str]:
    lines: list[str] = []
    for entity_id in visible_entities:
        entity = world.entities.get(entity_id)
        if entity and entity.canonical:
            lines.append(entity.canonical)
    return lines


def validate_spatial_plan(world: World, shots: list[dict[str, Any]]) -> list[str]:
    """Return human-readable errors. Empty list means the plan is spatially sane."""

    errors: list[str] = []
    shot_ids = [str(shot.get("id") or "") for shot in shots]
    shot_index = {shot_id: i for i, shot_id in enumerate(shot_ids) if shot_id}
    last_location: dict[str, str] = {}
    last_shot_for: dict[str, str] = {}
    previous_location = ""

    for shot in shots:
        shot_id = str(shot.get("id") or "")
        location_id = str(shot.get("location_id") or "")
        visible = [str(item) for item in (shot.get("visible_entities") or [])]
        travel = [str(item) for item in (shot.get("travel_path") or [])]
        loc = world.locations.get(location_id)
        if not location_id or loc is None:
            errors.append(f"{shot_id}: unknown location {location_id!r}.")
            continue

        unknown_hops = [node for node in travel if node not in world.locations]
        if unknown_hops:
            errors.append(f"{shot_id}: travel_path has unknown location(s) {unknown_hops}.")

        if previous_location and not is_adjacent_or_same(world, previous_location, location_id):
            if not travel:
                errors.append(
                    f"{shot_id}: camera jumps {previous_location} → {location_id} "
                    "without an adjacent hop or travel_path."
                )
            elif not walk_covers(world, travel):
                errors.append(f"{shot_id}: travel_path is not a walk on the topology: {travel}.")
            elif travel[0] != previous_location or travel[-1] != location_id:
                errors.append(
                    f"{shot_id}: travel_path must start at {previous_location} and end at {location_id}."
                )

        for entity_id in visible:
            entity = world.entities.get(entity_id)
            if entity is None:
                errors.append(f"{shot_id}: unknown entity {entity_id!r}.")
                continue
            if entity.first_shot:
                first_index = shot_index.get(entity.first_shot)
                current_index = shot_index.get(shot_id)
                if first_index is None:
                    errors.append(f"{entity_id}: first_shot {entity.first_shot!r} is missing.")
                elif current_index is not None and current_index < first_index:
                    errors.append(
                        f"{shot_id}: {entity_id} is visible before its reveal shot {entity.first_shot}."
                    )
            if entity.allowed_locations is not None and location_id not in entity.allowed_locations:
                errors.append(
                    f"{shot_id}: {entity_id} cannot appear at {location_id}."
                )
            if not entity.movable and entity.home_location and location_id != entity.home_location:
                allowed = entity.allowed_locations
                if allowed is None or location_id not in allowed:
                    errors.append(
                        f"{shot_id}: immovable {entity_id} left its home {entity.home_location}."
                    )
            if entity_id in loc.never_show:
                errors.append(f"{shot_id}: {entity_id} is never-show at {location_id}.")

            if entity.movable and entity_id in last_location:
                prev = last_location[entity_id]
                if not is_adjacent_or_same(world, prev, location_id):
                    path = travel if travel else None
                    if path is None:
                        accounted = False
                        # Intervening shots since this entity last appeared may form the walk.
                        prev_shot = last_shot_for.get(entity_id)
                        if prev_shot is not None:
                            start_i = shot_index[prev_shot]
                            end_i = shot_index[shot_id]
                            hop = [str(shots[i].get("location_id") or "") for i in range(start_i, end_i + 1)]
                            accounted = walk_covers(world, hop)
                        if not accounted:
                            errors.append(
                                f"{shot_id}: {entity_id} teleports {prev} → {location_id}."
                            )
                    elif not walk_covers(world, path):
                        errors.append(f"{shot_id}: {entity_id} travel_path is not a legal walk.")

            last_location[entity_id] = location_id
            last_shot_for[entity_id] = shot_id

        previous_location = location_id

    return errors


def world_to_dict(world: World) -> dict[str, Any]:
    return {
        "locations": {
            loc.id: {
                "label": loc.label,
                "description": loc.description,
                "adjacent": list(loc.adjacent),
                "never_show": list(loc.never_show),
                "remote_from": list(loc.remote_from),
                "prompt_forbid": list(loc.prompt_forbid),
            }
            for loc in world.locations.values()
        },
        "entities": {
            entity.id: {
                "canonical": entity.canonical,
                "kind": entity.kind,
                "movable": entity.movable,
                "home_location": entity.home_location,
                "first_shot": entity.first_shot,
                "allowed_locations": list(entity.allowed_locations) if entity.allowed_locations is not None else None,
            }
            for entity in world.entities.values()
        },
        "journeys": {name: list(path) for name, path in world.journeys.items()},
        "weather": world.weather,
        "light": world.light,
    }

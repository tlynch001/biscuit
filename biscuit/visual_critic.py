"""Shot-intent records for a future generated-image critic.

This module does not inspect pixels. Current image providers do not expose a
reliable vision/validation API in this pipeline. Each shot stores intended
location, visible elements, and forbidden/premature elements so a later
inspector can compare a generated still against local frame intent.
"""

from __future__ import annotations

from typing import Any

from biscuit.models import Scene


def critic_record(scene: Scene) -> dict[str, Any]:
    """Return inspectable intent for a shot. Never claims to have seen the image."""

    return {
        "status": "not_implemented",
        "reason": "No reliable generated-image inspection in the current pipeline.",
        "intended_location_id": scene.location_id or None,
        "visible_elements": list(scene.visible_elements),
        "forbidden_elements": list(scene.forbidden_elements),
        "questions": [
            "Is this actually the intended location?",
            "Are forbidden or premature story elements visible?",
            "Is Biscuit carrying the mitten when he should be?",
            "Has a vehicle appeared before its introduction?",
            "Does the image contradict established geography?",
            "Is the composition broadly consistent with the intended shot?",
        ],
    }

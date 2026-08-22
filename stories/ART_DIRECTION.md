# Biscuit art direction

The story describes the narrative.
The visual plan describes the movie.
The reference library establishes the world.
The shot prompt tells the camera what to photograph.

Prompt text and continuity metadata are not enough. Independent image
generations still reinvent the road, the ditch, the car, and the dog.
Biscuit therefore supports a small virtual art department: **reference
assets**.

## 1. What a reference asset is

A reference asset is an **approved image** that establishes something that
must stay visually consistent. It is production-design material. It is not
necessarily a frame in the finished video.

Logical names only. Stories and visual plans never store vendor file ids:

```yaml
art_direction:
  mode: directed
```

```json
{
  "reference_assets": [
    "roadside_ditch_master",
    "abandoned_car_master",
    "biscuit_master"
  ]
}
```

The persistent registry (`output/<story_id>/reference_assets.json`) resolves
those names to a local image, a provider name, and an optional cached
provider file id.

## 2. Why Biscuit uses them

Without approved plates, each still is asked to reconstruct the world from
prose. That produces drifting car placement, changing ditch geometry,
surprise traffic, and new faces. References are ingredients for one
photograph — typically location + character + critical object — not a blend
of different story beats.

## 3. Automatic vs directed illustration

| Mode | Story YAML | Illustration |
| --- | --- | --- |
| **automatic** (default) | omit `art_direction` or set `mode: automatic` | `story → prompts → illustrate` with no human checkpoint |
| **directed** | `art_direction.mode: directed` | propose masters, wait for approval, then shoot |

Existing stories stay automatic. Directed mode is opt-in. It is a pipeline
capability, not a mandatory obstacle.

## 4. How to provide a manual reference

Put a file anywhere readable, then register it:

```bash
python -m biscuit.cli \
  --config config/config.example.yaml \
  --story stories/biscuit_and_the_red_mitten.yaml \
  --register-reference abandoned_car_master \
  --reference-file references/red_mitten/abandoned_car_master.jpg \
  --reference-category vehicle \
  --approve-reference abandoned_car_master \
  --through-stage direct
```

Biscuit copies the image into `output/<story_id>/references/` and records
the content hash. A later xAI run uploads it once and caches the returned
`file_id` in the registry, never in the story YAML.

## 5. How generated references are approved

```text
reference required
      ↓
--generate-reference ID     (writes a candidate, does not approve)
      ↓
human reviews output/<story>/references/candidates/<id>.png
      ↓
--approve-reference ID
  or --reject-reference ID
  or replace the file with --register-reference
```

There is no GUI. Inspect files, edit `reference_assets.json` if needed, and
re-run `direct`.

`--generate-reference` on an **approved** master is refused unless you pass
`--force-references`. Ordinary `--force` will not do this.

## 6. How provider file ids are cached

The registry stores `provider` + `provider_file_id` + `content_hash`.
If the local bytes still match and the file id belongs to the current
provider, Biscuit does not upload again. Changing the local image clears
the cached id so the next illustrate uploads the new bytes.

xAI upload: `POST https://api.x.ai/v1/files` (purpose `assistants`).
xAI use: `POST /v1/images/edits` with `image: {file_id}` or
`images: [{file_id}, ...]` (maximum three).

## 7. How to inspect the art-direction plan

After `--through-stage direct`:

| File | Role |
| --- | --- |
| `art_direction.md` | Human checklist: identity, assets, status, shot assignments, unresolved items |
| `art_direction.json` | Machine-readable copy of the same plan |
| `reference_assets.json` | Persistent registry |
| `visual_plan.json` | Cinematic shots, now including `reference_assets` |

## 8. How to resume illustration after approval

```bash
# Plan only (development provider, no paid images)
python -m biscuit.cli \
  --config config/config.example.yaml \
  --story stories/biscuit_and_the_red_mitten.yaml \
  --through-stage direct

# After registering / approving masters:
python -m biscuit.cli \
  --config config/config.yaml \
  --story stories/biscuit_and_the_red_mitten.yaml \
  --from-stage illustrate
```

Directed illustration **fails clearly** if a selected reference is missing
or unapproved. It names the ids.

## 9. Promoting a generated shot to an anchor

Do **not** default to “scene N output becomes scene N+1's reference.”
Bad generations must not become hereditary. Approved masters outrank
promoted frames.

To promote a still you actually like:

```bash
python -m biscuit.cli \
  --story stories/biscuit_and_the_red_mitten.yaml \
  --promote-shot 7 \
  --as-reference roadside_composition_anchor_07 \
  --through-stage direct
```

Then edit `needed_by_shots` in the registry so later shots may select it.
Composition anchors are never implied for unrelated shots.

## 10. The xAI three-reference limit

xAI Imagine multi-image edits accept **at most three** source images.
The planner ranks candidates and records why the winners won. The image
provider receives the already-selected logical ids; it does not re-rank.
Typical order of importance: location, primary character, critical object
or second character. Ties are deterministic (category, then id).

Shot prompts still contain textual continuity. References lock identity
and geography; the prompt says what happens in **this** shot.

## Red Mitten example

Episode Two is the first directed story. It proposes masters such as:

- `biscuit_master`
- `roadside_ditch_master`
- `abandoned_car_master`
- `culvert_master`
- `open_field_master`
- `man_master` / `child_master` / `woman_master`

A roadside sedan shot should select the ditch, the car, and Biscuit — not
the culvert, the field, and the car as if they were three different times.

Generate **only** the planning artifacts (no paid APIs, no finished film):

```bash
python -m biscuit.cli \
  --config config/config.example.yaml \
  --story stories/biscuit_and_the_red_mitten.yaml \
  --through-stage direct \
  --verbose
```

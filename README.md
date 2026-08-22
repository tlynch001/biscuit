# Biscuit

Biscuit is an automated AI story-video production pipeline.

You give it a YAML story. It expands that story into scenes, writes a narration
script, generates (or placeholders) scene images, synthesizes speech, and
assembles a narrated `video.mp4` with supporting YouTube assets.

The first recurring protagonist is **Biscuit the dog**. Stories lean toward
cinematic, sentimental internet melodrama. Phase 1 ships an end-to-end local
pipeline that produces a real video without paid AI calls.

```bash
python -m biscuit.cli \
  --config config/config.example.yaml \
  --story stories/biscuit_in_the_snow.yaml
```

## Architecture

The orchestrator knows *what* must happen. Providers know *how*.

```text
story YAML
   |
   v
parse / validate  (+ character library)
   |
   v
story provider  -->  scene manifest.json
   |
   +--> script.txt
   +--> image prompts (character-consistent)
   |
   +--> narration provider  -->  narration.mp3 + narration_timing.json
   +--> image provider      -->  scenes/001.png ...
   |
   v
timed assets
   |
   v
FFmpeg assembly  -->  video.mp4
   |
   +--> thumbnail.png
   +--> title.txt
   +--> description.txt
   +--> optional YouTube upload (disabled by default)
```

Stages: `parse` → `expand` → `prompts` → `direct` → `narrate` →
`illustrate` → `assemble` → `package` → `publish`.

`direct` is the art-direction checkpoint. Automatic stories write a short
note and continue. Directed stories propose a reference-asset library and
stop being able to illustrate until those assets are approved. See
[`stories/ART_DIRECTION.md`](stories/ART_DIRECTION.md).

Each expensive stage writes inspectable artifacts. The pipeline is resumable:
rerunning later stages reuses audio, images, and prompts unless you pass
`--force`.

```
biscuit/
  cli.py              thin CLI
  pipeline.py         stage orchestrator
  references.py       reference-asset registry and shot selection
  art_direction.py    planner, checklist, directed-illustration gate
  config.py           YAML + .env (secrets by env-var name only)
  story.py            YAML schema, validation, character resolution
  models.py           StorySpec, Character, Scene, StoryManifest, timing
  prompts.py          character-consistent image prompt builder
  timing.py           narration alignment → scene durations
  artifacts.py        output layout
  providers/          story / image / narration implementations
  video.py            FFmpeg Ken Burns + concat
  publishing.py       title, description, thumbnail
  youtube.py          optional Data API v3 uploader
characters/           reusable character library
stories/              story YAML
```

Characters are first-class. `characters/biscuit.yaml` is merged into every
story that references it. Appearance, visual anchors, and optional reference
image paths travel with the character. Image providers receive opaque
`CharacterReference` objects; vendor-specific `--cref` / image-to-image flags
do not leak into the rest of the app.

Writing quality for Biscuit stories lives in [`stories/STORYTELLING.md`](stories/STORYTELLING.md).
Art direction — reference assets, approval, and the directed illustration
checkpoint — lives in [`stories/ART_DIRECTION.md`](stories/ART_DIRECTION.md).
Episode One (`stories/biscuit_in_the_snow.yaml`) is the quality benchmark, not
a plot to clone. The current story provider is `template` (authored beats);
there is no production LLM story writer yet.

Narration timing drives scene length. ElevenLabs uses the `with-timestamps`
endpoint (same generation, character alignment included). The development
narrator synthesizes deterministic word timings and scales them to the real
audio duration.

## Installation

Python 3.11+ is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional YouTube extra (only if you will enable uploading):

```bash
pip install -e ".[youtube]"
```

## System packages

| Tool | Why |
| --- | --- |
| **FFmpeg** (and `ffprobe`) | Required to assemble `video.mp4` and to mux narration. `apt install ffmpeg` / `brew install ffmpeg`. |
| **espeak-ng** | Optional. The development narrator uses it for spoken audio without ElevenLabs. If missing, Biscuit writes timed silence instead. `apt install espeak-ng`. |

Pillow, PyYAML, python-dotenv, and requests are Python dependencies.

## Configuration

Copy `config/config.example.yaml` to `config/config.yaml` (git-ignored) if you
want local overrides. The CLI falls back to the example file when
`config/config.yaml` is absent.

Nothing in YAML is a secret. Provider blocks name an environment variable,
for example `api_key_env: ELEVENLABS_API_KEY`. Inline keys such as `api_key:`
are rejected.

Defaults that matter:

- `image.provider: development` (safe; no paid image calls)
- `narration.provider: development`
- `story_provider.provider: template`
- `youtube.enabled: false`
- video 1920×1080 at 30 fps
- ElevenLabs model stays `eleven_multilingual_v2` (not v3)

### Image providers

**Safe development mode** (default):

```yaml
image:
  provider: development
```

**OpenAI Images** (explicit opt-in; requires `OPENAI_API_KEY`):

```yaml
image:
  provider: openai
  openai:
    model: gpt-image-2
    quality: medium
    api_key_env: OPENAI_API_KEY
```

**xAI Grok Imagine** (explicit opt-in; requires `XAI_API_KEY`):

```yaml
image:
  provider: xai
  xai:
    model: grok-imagine-image-quality
    aspect_ratio: "16:9"
    resolution: "2k"
    api_key_env: XAI_API_KEY
```

A flatter form is also accepted and mapped onto `image.xai`:

```yaml
image:
  provider: xai
  model: grok-imagine-image-quality
  aspect_ratio: "16:9"
  resolution: "2k"
```

There is no automatic OpenAI → xAI fallback. Switch providers in YAML and
restart the illustrate stage. Existing paid stills are reused unless you
pass `--force` or `--regenerate-image N`.

`gpt-image-2` accepts arbitrary resolutions that meet the official
constraints (multiples of 16, max edge 3840px, aspect ≤ 3:1,
655,360–8,294,400 pixels). Biscuit therefore requests **1920×1088** for a
1920×1080 canvas (1080 is not a multiple of 16) and cover-crops 4px
locally. Older GPT Image models still use the fixed enum
(`1024x1024` / `1536x1024` / `1024x1536`). Nothing is stretched.

Image cache lives next to the PNGs (`work/NNN.image.hash`). Stamps are JSON
with an explicit `provider` (legacy files are a bare hash). A matching
fingerprint skips the API.

If the prompt, size, provider, model, quality, xAI aspect/resolution, or
reference files change:

- **development** regenerates automatically (free)
- **openai** and **xai** *reuse* an existing **paid** PNG and warn, so a
  config flip cannot quietly spend a full story. Pass `--regenerate-image N`
  or `--force` to spend on purpose.
- Switching **development → openai** or **development → xai** replaces
  placeholder cards automatically. No `--regenerate-image` is required;
  missing PNGs and leftover development stills are generated, while
  successful paid stills from a partial run are kept.
- Switching from one paid provider to another (including openai ↔ xai) is
  conservative: valid paid assets are not silently replaced.

The exact prompt sent to the API is `image_prompts/NNN.txt`. If the API
returns a `revised_prompt`, that is stored as `image_prompts/NNN.revised.txt`.

## Environment variables

Copy `.env.example` to `.env` (git-ignored):

```
ELEVENLABS_API_KEY=
OPENAI_API_KEY=
XAI_API_KEY=
```

| Variable | When it is needed |
| --- | --- |
| `ELEVENLABS_API_KEY` | `narration.provider: elevenlabs` |
| `OPENAI_API_KEY` | `image.provider: openai` (also reserved for a future LLM story provider) |
| `XAI_API_KEY` | `image.provider: xai` |

YouTube does **not** use an env var. It uses OAuth files under `secrets/`
(also git-ignored). Never commit `.env`, `config/config.yaml`, or anything in
`secrets/`.

## Development / mock mode

Phase 1 is designed to run fully offline:

- **Story provider `template`** — authored beats become scenes. No LLM.
- **Image provider `development`** — cinematic placeholder stills (Pillow).
  The *real* image prompt is still written to `image_prompts/`.
- **Narration provider `development`** — `espeak-ng` if present, otherwise
  timed silence, plus deterministic `narration_timing.json`.

Switch image generation later without touching the orchestrator:

```yaml
image:
  provider: openai
```

or:

```yaml
image:
  provider: xai
```

Switch narration later without touching the orchestrator:

```yaml
narration:
  provider: elevenlabs
  # Development/espeak + synthetic timing only. Not an ElevenLabs control.
  words_per_minute: 170
  elevenlabs:
    model_id: eleven_multilingual_v2
    # Official voice_settings.speed (1.0 default, range 0.7–1.2).
    # 0.7 = slowest supported; use this for a slower storyteller cadence.
    speed: 0.7
```

`words_per_minute` never reaches the ElevenLabs API. Real speaking rate is
only `narration.elevenlabs.speed`, a unitless multiplier (`< 1` slower,
`> 1` faster). There is no documented WPM-to-speed conversion; do not treat
80–100 WPM as an API unit. Keep `model_id: eleven_multilingual_v2` (v3 has
no speed control).

## How to run the example story

```bash
python -m biscuit.cli \
  --config config/config.example.yaml \
  --story stories/biscuit_in_the_snow.yaml
```

Useful flags:

| Flag | Purpose |
| --- | --- |
| `--verbose` | Debug logging |
| `--dry-run` | Validate and print the plan; generate nothing |
| `--from-stage STAGE` | Resume from a later stage |
| `--through-stage STAGE` | Stop after a stage |
| `--force` | Ignore caches inside the selected range |
| `--new-run` | Isolate this run in a timestamped subdirectory |
| `--regenerate-image N` | Rebuild only scene `N` (1-based, repeatable). Other scene images stay cached. |
| `--register-reference ID` | Copy a local image into the story reference library (`--reference-file` required). |
| `--approve-reference ID` | Mark a planned or candidate master approved. Repeatable. |
| `--reject-reference ID` | Reject a candidate. Repeatable. |
| `--generate-reference ID` | Create a candidate plate. Does not approve it. |
| `--promote-shot N` | Promote generated scene `N` to a composition anchor (`--as-reference` required). |
| `--force-references` | Allow replacing approved masters. Ordinary `--force` will not. |

Examples:

```bash
# Generate remaining paid stills (replaces development placeholders / missing
# PNGs; keeps successful paid images). Requires image.provider: openai or xai.
python -m biscuit.cli \
  --config config/config.yaml \
  --story stories/biscuit_in_the_snow.yaml \
  --from-stage illustrate \
  --through-stage illustrate

# Regenerate ElevenLabs narration (picks up elevenlabs.speed)
python -m biscuit.cli \
  --config config/config.yaml \
  --story stories/biscuit_in_the_snow.yaml \
  --from-stage narrate \
  --through-stage narrate \
  --force

# Rebuild video from existing images and narration (no paid APIs).
# Includes the end hold / fade-to-black / black landing.
python -m biscuit.cli \
  --config config/config.yaml \
  --story stories/biscuit_in_the_snow.yaml \
  --from-stage assemble

# Stop after prompts so you can edit image_prompts/*.txt
python -m biscuit.cli --story stories/biscuit_in_the_snow.yaml --through-stage prompts

# Scene 4 looks wrong: redo only that still, then continue (assemble sees the new PNG)
python -m biscuit.cli \
  --config config/config.yaml \
  --story stories/biscuit_in_the_snow.yaml \
  --regenerate-image 4
```

First **paid** single-scene test (after `image.provider: openai` or
`image.provider: xai`, with the matching key in `.env`). Do not run this
unless you intend to spend a credit:

```bash
python -m biscuit.cli \
  --config config/config.yaml \
  --story stories/biscuit_in_the_snow.yaml \
  --from-stage illustrate \
  --through-stage illustrate \
  --regenerate-image 1
```

xAI smoke test for Episode Three (prompts reused; stills generated with
Grok Imagine). Requires `XAI_API_KEY` in `.env` and `image.provider: xai`
in `config/config.yaml`:

```bash
# .env
XAI_API_KEY=...

python -m biscuit.cli \
  --config config/config.yaml \
  --story stories/biscuit_and_the_child_upstairs.yaml \
  --through-stage illustrate \
  --verbose
```

Stages: `parse`, `expand`, `prompts`, `direct`, `narrate`, `illustrate`,
`assemble`, `package`, `publish`.

## Generated artifacts

Default layout (reused across runs so assets can be cached):

```text
output/<story_id>/
  run.json
  manifest.json
  script.txt                 # literary spoken script (authored beats)
  performance.txt            # SSML performance script sent to ElevenLabs
  visual_plan.json           # cinematic shots, locations, local prompts
  art_direction.md           # human-readable reference / continuity plan
  art_direction.json         # machine-readable shot-to-reference assignments
  reference_assets.json      # persistent registry (status, paths, cached file ids)
  references/                # approved or candidate master images
  narration.mp3
  narration_timing.json
  image_prompts/001.txt ...          # exact prompt sent (plus optional .revised.txt)
  scenes/001.png ...
  work/                 # image hash stamps, assemble fingerprint, clips
  video.mp4
  thumbnail.png
  title.txt
  description.txt
```

`script.txt` is the literary narration. `performance.txt` is what ElevenLabs
Multilingual v2 receives: the same spoken words with inferred (or directed)
`<break time="Ns" />` pauses. Unspoken geography holds appear as break-only
paragraphs in `performance.txt`; they do not add spoken words. `visual_plan.json`
is the director's inspectable shot list. Episode Two
(`biscuit_and_the_red_mitten.yaml`) expands into a small number of
location-aware cinematic shots (about two dozen unique stills), not one image
per sentence. The director keeps an explicit location topology, persistent
entity identities, and implied travel shots when narration skips a crossing.
Other stories stay one scene per authored beat but still get a performance
script.

Image prompts for planned shots describe only the current frame. Global story
state stays in the director; it is not dumped into every prompt. Recurring
objects inherit a canonical identity (the same brown-tan sedan, not "an
abandoned car"). Optional `reference_shot_id` values are passed to image
providers as `CharacterReference(kind="shot_continuity")` when the prior PNG
exists. Directed stories prefer approved **reference assets** (logical names
such as `abandoned_car_master`) over generated-shot chaining. xAI uploads
those masters once via `POST /v1/files` and sends up to three `file_id`
values to `POST /v1/images/edits`. Local-path data-URI edits remain available
for `grok-imagine-image-2.x`. Text-only generation is unchanged when no
references are selected.

Inspect the Red Mitten visual and art-direction plan in development
**before** spending image credits. This stops after planning; it does not
generate reference plates, finished stills, or video:

```bash
python -m biscuit.cli \
  --config config/config.example.yaml \
  --story stories/biscuit_and_the_red_mitten.yaml \
  --through-stage direct \
  --verbose
```

Then read:

- `output/biscuit_and_the_red_mitten/visual_plan.json`
- `output/biscuit_and_the_red_mitten/art_direction.md`
- `output/biscuit_and_the_red_mitten/art_direction.json`
- `output/biscuit_and_the_red_mitten/reference_assets.json`

Keep `image.provider: development`. Do not run `--from-stage illustrate`
until the required masters are registered and approved. Ordinary `--force`
will not delete approved reference images.

`--through-stage prompts` still writes image prompts. For directed stories
it also writes a preliminary art-direction plan. `--through-stage direct`
is the explicit human checkpoint.

If unspoken geography holds were generated with a previous build, re-run from
`narrate` so scene durations pick up planned `hold_seconds`. Existing ElevenLabs
audio can be reused; the pipeline pads silence to match the holds. Then
`assemble`. Images do not need to be regenerated.

To regenerate the full film after inspecting the plan, use `--force` so older
stills are not kept:

```bash
python -m biscuit.cli \
  --config config/config.yaml \
  --story stories/biscuit_and_the_red_mitten.yaml \
  --force \
  --verbose
```

Stop after illustration if you only want stills:

```bash
python -m biscuit.cli \
  --config config/config.yaml \
  --story stories/biscuit_and_the_red_mitten.yaml \
  --through-stage illustrate \
  --force \
  --verbose
```

`manifest.json` is the inspectable scene representation: narration, prompts,
characters present, motion, duration, and asset paths.

`--new-run` writes to `output/<story_id>/<UTC-timestamp>/` instead.

## Provider architecture

Three registries (`story`, `image`, `narration`) map a YAML name to a class.

```python
@story_registry.register("template")
class TemplateStoryProvider(StoryProvider):
    def expand(self, spec: StorySpec) -> StoryManifest: ...
```

A future OpenAI / Grok / Claude story expander or another TTS vendor
registers the same way. Paid image providers are **openai** (`gpt-image-2`
via the OpenAI Images API) and **xai** (`grok-imagine-image-quality` via
`https://api.x.ai/v1/images/generations`). The pipeline constructs
providers from config and never imports a vendor SDK at the orchestration
layer.

Image requests include:

- the scene
- the fully built prompt (for cinematic shots: the local frame photograph,
  style, in-frame identity; not a global world-state dump)
- resolved `Character` objects
- opaque `CharacterReference` paths (if the library provided any)

If those reference files exist on disk, the OpenAI provider switches to
`/v1/images/edits` so they can be used as identity references. That
multipart protocol stays inside `biscuit/providers/image_openai.py`. The
xAI provider uses JSON `POST /v1/images/edits` only when the configured
model is a documented Imagine 2.x edit model; `grok-imagine-image-quality`
stays on `/v1/images/generations`. The character library currently ships
`references: []`; without files, providers use strong structured prompts.
GPT Image does not guarantee character identity across scenes.

ElevenLabs support is implemented against the `text-to-speech/{id}/with-timestamps`
endpoint. The **performance** script (`performance.txt`) is sent when
`narration.provider: elevenlabs`. Alignment is mapped onto visual-beat
paragraphs. `script.txt` remains the literary spoken words. Speaking rate is
`voice_settings.speed` (default 1.0, documented range 0.7–1.2). Biscuit uses
`eleven_multilingual_v2` on purpose; do not switch it to v3.

## YouTube

Local packaging (title, description, thumbnail) is on by default and costs
nothing extra.

Uploading is **off** by default:

```yaml
youtube:
  enabled: false
```

Tests never upload. While disabled, no Google library is imported, no OAuth
file is read, and no network call is made.

To enable later: install `biscuit[youtube]`, place a Desktop OAuth client JSON
at `secrets/youtube_client_secret.json`, run once interactively to cache
`secrets/youtube_token.json`, then set `youtube.enabled: true`. Start with
`privacy: unlisted`.

## What is implemented vs deferred

**Implemented**

- Story YAML schema, validation, character library
- Scene manifest + script + character-consistent image prompts
- Development image stills and opt-in OpenAI GPT Image (`gpt-image-2`)
- Development/ElevenLabs narration (`eleven_multilingual_v2`)
- Narration-driven scene timing
- FFmpeg assembly with restrained, duration-scaled Ken Burns motion, fades, and a configurable end hold / fade-to-black
- Cinematic visual plans (`visual_plan.json`) with local shot prompts, location topology, persistent entities, and implied travel shots
- Human-directed reference assets / art direction (`art_direction.md`, `reference_assets.json`)
- Thumbnail, title, description
- Optional YouTube uploader behind `enabled: false`
- Resumable stages, image hash cache, `--regenerate-image N`
- YAML config, `.env` secrets, tests, example story

**Intentionally deferred**

- Pixel-level generated-image critic / vision validation
- Live LLM story expansion (OpenAI/Grok/Claude). Writing rules for that
  future provider are in `stories/STORYTELLING.md`.
- Additional image vendors (Flux, SD, others)
- Guaranteed character identity without reference images
- Background music / stems
- Captions from word timing
- A GUI, database, or cloud runtime
- Enabling YouTube upload in the default config

## Tests

```bash
pytest
```

Tests do not call paid APIs and do not upload to YouTube.

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

Stages: `parse` → `expand` → `prompts` → `narrate` → `illustrate` →
`assemble` → `package` → `publish`.

Each expensive stage writes inspectable artifacts. The pipeline is resumable:
rerunning later stages reuses audio, images, and prompts unless you pass
`--force`.

```
biscuit/
  cli.py              thin CLI
  pipeline.py         stage orchestrator
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

- `image.provider: development`
- `narration.provider: development`
- `story_provider.provider: template`
- `youtube.enabled: false`
- video 1920×1080 at 30 fps

## Environment variables

Copy `.env.example` to `.env` (git-ignored):

```
ELEVENLABS_API_KEY=
OPENAI_API_KEY=
```

| Variable | When it is needed |
| --- | --- |
| `ELEVENLABS_API_KEY` | `narration.provider: elevenlabs` |
| `OPENAI_API_KEY` | Reserved for a future LLM story provider. Unused in Phase 1. |

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

Switch narration later without touching the orchestrator:

```yaml
narration:
  provider: elevenlabs
```

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

Examples:

```bash
# Rebuild video from existing images and narration
python -m biscuit.cli --story stories/biscuit_in_the_snow.yaml --from-stage assemble --force

# Stop after prompts so you can edit image_prompts/*.txt
python -m biscuit.cli --story stories/biscuit_in_the_snow.yaml --through-stage prompts
```

Stages: `parse`, `expand`, `prompts`, `narrate`, `illustrate`, `assemble`,
`package`, `publish`.

## Generated artifacts

Default layout (reused across runs so assets can be cached):

```text
output/<story_id>/
  run.json
  manifest.json
  script.txt
  narration.mp3
  narration_timing.json
  image_prompts/001.txt ...
  scenes/001.png ...
  work/                 # intermediate clips
  video.mp4
  thumbnail.png
  title.txt
  description.txt
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

A future OpenAI / Grok / Claude story expander, Flux/SD image backend, or
another TTS vendor registers the same way. The pipeline constructs providers
from config and never imports a vendor SDK at the orchestration layer.

Image requests include:

- the scene
- the fully built prompt
- resolved `Character` objects
- `CharacterReference` paths (if the library provided any)

ElevenLabs support is implemented against the `text-to-speech/{id}/with-timestamps`
endpoint. Alignment is mapped onto scene paragraphs (the same blank-line
script structure written to `script.txt`).

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

**Implemented in Phase 1**

- Story YAML schema, validation, character library
- Scene manifest + script + image prompts
- Development image stills and development/ElevenLabs narration
- Narration-driven scene timing
- FFmpeg assembly with slow pan / zoom-like drift and fades
- Thumbnail, title, description
- Optional YouTube uploader behind `enabled: false`
- Resumable stages, YAML config, `.env` secrets, tests, example story

**Intentionally deferred**

- Live LLM story expansion (OpenAI/Grok/Claude)
- Real image models (Flux, SD, DALL-E, etc.) and vendor reference-image APIs
- Background music / stems
- Captions from word timing
- A GUI, database, or cloud runtime
- Enabling YouTube upload in the default config

## Tests

```bash
pytest
```

Tests do not call paid APIs and do not upload to YouTube.

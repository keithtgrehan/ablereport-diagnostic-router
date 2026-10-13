# AbleReport

**Turn “there is no sound” into a specific diagnosis, supporting evidence and a next step.**

[Inspect a sample input](llm-router-agent/fixtures/ai_key/no_sound_audio_engine_off.json) · [Read the diagnostic logic](llm-router-agent/src/llm_router_agent/deterministic/no_sound.py) · [Review the tests](llm-router-agent/tests/)

AbleReport is a portfolio prototype for technical troubleshooting in Ableton Live. It reads a structured JSON snapshot of project state, checks a defined set of no-sound conditions and returns a report explaining the result and what to check next.

The product idea is to make a support interaction more useful: **identify an observable condition, show the evidence and give the user a concrete action.**

## See the working example

The [audio-engine fixture](llm-router-agent/fixtures/ai_key/no_sound_audio_engine_off.json) contains:

```json
{
  "project": {
    "transport_running": true,
    "audio_engine_enabled": false
  }
}
```

The diagnostic path identifies `audio_engine_disabled`, cites `$.project.audio_engine_enabled` with the value `false`, and recommends enabling the audio engine, checking the output device and confirming signal at the master meter.

The snippet above is an excerpt; the linked fixture contains the complete demo input. You can run it without Ableton, a model server or an API key.

## What works

| Capability | Why it matters |
| --- | --- |
| Ordered checks for five no-sound conditions | Cover audio-engine state, transport, master mute, master volume and clip presence through an inspectable rule path. |
| Structured diagnostic reports | Return a diagnosis, evidence, checks performed and practical fix steps in a consistent shape. |
| Optional model-generated reports | Explore natural-language assistance within an explicit output contract. |
| Schema and evidence validation for model output | Check the report structure and confirm that cited paths and values match the input. |
| One retry, then deterministic fallback | Preserve a usable baseline when model output fails validation. |
| Fixtures and automated tests | Exercise diagnosis, validation, retry and fallback without relying on a live provider. |

## Why the design starts with rules

**Known conditions deserve explicit checks.** An audio engine being disabled is an observable state. A deterministic rule makes that diagnosis straightforward to explain, test and reproduce. The model is optional because the core user task does not need one.

**Structured input makes evidence checkable.** The input format, called an “AI Key”, is a JSON project-state snapshot. A finding can point to a precise field and value. That gives the reviewer a stronger basis for inspection than an interpretation of a screenshot.

**Validation belongs between generation and use.** Optional model output is checked against the report schema and input evidence. A failed result receives one stricter retry, then returns to the rule-based result with an explanatory note. These checks verify structure and cited data; they do not independently prove every generated explanation is correct.

**Solve one troubleshooting journey before widening coverage.** No-sound diagnosis provides a bounded problem with repeatable examples. Broader routing analysis, musical advice and automatic project editing would need different evidence and tests. Keeping them outside this demo makes the implemented behaviour easier to assess.

## What this project demonstrates

For a customer-facing commercial role, the useful connection is the quality of the handoff: turn a vague problem into a structured question, identify the information needed, and communicate a practical next step.

This portfolio project by Keith Grehan was developed with AI-assisted tooling. It provides a concrete way to discuss requirements, technical trade-offs and the reliability of an AI-assisted workflow. Its demonstrated scope is supplied JSON and selected no-sound cases; direct export from Ableton is a separate integration step.

## Run the demo

Use Python 3.11 or newer. From the repository root:

```bash
cd llm-router-agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m llm_router_agent.cli \
  --ai-key fixtures/ai_key/no_sound_audio_engine_off.json \
  --llm-provider none \
  --no-llm
```

The command prints the diagnostic report as JSON. Additional [fixtures](llm-router-agent/fixtures/ai_key/) demonstrate a stopped transport, muted master, silenced master volume and absent clips.

Run the focused diagnostic checks from the same directory:

```bash
python -m pytest -q tests/test_cli.py tests/test_deterministic_no_sound.py \
  tests/test_deterministic_no_sound_validated.py tests/test_validation.py
```

The [implementation notes](llm-router-agent/ABLE_REPORT_IMPLEMENTATION_NOTES.md) explain the optional model path. The deterministic demo above is the simplest review route; live provider setup is optional.

## Architecture and code guide

```text
Project-state JSON → ordered rules → diagnostic report
        ↓
Optional model → schema + evidence checks → accepted report
                        ↓ validation failure after retry
                  deterministic fallback
```

- [Diagnostic rules and retry/fallback](llm-router-agent/src/llm_router_agent/deterministic/no_sound.py)
- [Report models](llm-router-agent/src/llm_router_agent/models.py)
- [Evidence validation](llm-router-agent/src/llm_router_agent/validation.py)
- [CLI and optional provider wiring](llm-router-agent/src/llm_router_agent/cli.py)
- [Implementation notes](llm-router-agent/ABLE_REPORT_IMPLEMENTATION_NOTES.md)

The package also contains reusable routing and planning components. The no-sound CLI is the focused AbleReport demonstration described here.

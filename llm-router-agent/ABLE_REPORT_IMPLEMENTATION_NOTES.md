# AbleReport Implementation Notes

## What was built (and why)
This repo implements a reliability-first diagnostic engine for AbleReport-style no-sound analysis.

Goal:
- deterministic baseline diagnosis
- optional LLM augmentation
- strict output validation
- safe fallback behavior when LLM output is invalid

This keeps outputs trustworthy even when model responses are malformed or unsupported.

## Demo First

Deterministic run (no LLM):

```bash
cd /Users/keith/GitHub/llm-router-agent-for-ablereport/llm-router-agent
python -m llm_router_agent.cli \
  --ai-key fixtures/ai_key/no_sound_audio_engine_off.json \
  --llm-provider none \
  --no-llm
```

Validated LLM run (with retry + fallback):

```bash
cd /Users/keith/GitHub/llm-router-agent-for-ablereport/llm-router-agent
python -m llm_router_agent.cli \
  --ai-key fixtures/ai_key/no_sound_audio_engine_off.json \
  --llm-provider ollama \
  --llm-model llama3.1:latest \
  --require-llm
```

Alternate fixture examples:

```bash
python -m llm_router_agent.cli --ai-key fixtures/ai_key/no_sound_master_muted.json --llm-provider none --no-llm
python -m llm_router_agent.cli --ai-key fixtures/ai_key/no_sound_no_clips.json --llm-provider none --no-llm
```

## Core Data Definitions

### 1) AI Key (input JSON)
AI Key is deterministic extracted project state used as ground truth evidence source.

Typical fields:
- `project.audio_engine_enabled`
- `project.transport_running`
- `master_track.muted`
- `master_track.volume_db`
- `tracks[*].clips_present`

### 2) Report JSON (output contract)
Report JSON conforms to `DiagnosticReport`:
- `intent`
- `diagnosis`
- `root_cause_category`
- `confidence`
- `evidence[]` (`path`, `value`, `explanation`)
- `checks_run[]`
- `fix_steps[]`
- `notes` (optional; used for fallback messaging)

## Implementation Steps (in order)

1. Deterministic `no_sound` diagnosis.
2. Added `DiagnosticReport` + `EvidenceItem` Pydantic models.
3. Implemented `validate_report()` for schema validation + evidence binding to AI Key.
4. Added validated runner with one strict retry and deterministic fallback.
5. Added CLI flags:
   - `--ai-key`
   - `--no-llm`
   - `--require-llm`
   - `--llm-provider none|ollama|groq|openai`
   - `--llm-model`
6. Added fixtures and automated tests.
7. Added `notes` field so fallback messaging is not mixed into `fix_steps`.

## What validation means
Validation is pass/fail on two layers:
- schema correctness (required fields and shapes)
- evidence correctness:
  - each `evidence.path` must exist in AI Key
  - each `evidence.value` must match value(s) at that path

If `--require-llm` is used and validation fails after retry, output falls back to deterministic and sets `notes` with the validation-failure summary.

## Next steps

1. Add Ollama structured outputs to reduce repair/retry overhead.
2. Expand Groq/OpenAI provider pathways and provider-level tests.
3. Add more intents beyond no-sound (including routing/gain).
4. Integrate real Max for Live AI Key export into the pipeline.

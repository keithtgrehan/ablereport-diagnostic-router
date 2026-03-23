# AbleReport

Deterministic-first diagnostic engine for Ableton Live export data.

AbleReport takes structured **AI Key JSON** exported from an Ableton Live project and turns it into a **schema-locked diagnostic report**. The goal is not to generate vague music advice. The goal is to identify technical and structural problems faster than manual inspection, while keeping every meaningful conclusion tied to explicit evidence in the input.

---

## What AbleReport Is

AbleReport is a diagnostic layer that sits between an Ableton Live project export and a user-facing report.

High-level flow:

```text
Ableton Live Project
-> AI Key JSON Export
-> Diagnostic Engine
   -> Deterministic Checks
   -> Validation Layer
   -> Optional LLM Reasoning
-> DiagnosticReport Output
```

This design is deliberate:

- deterministic checks run first
- output shape is validated against a fixed schema
- LLM reasoning is optional and bounded
- unsupported speculation is not allowed

---

## Core Promise

AbleReport turns Ableton Live export data into structured, evidence-backed diagnostics.

It is built to:

- reduce time to produce a first-pass diagnostic view
- improve consistency of issue detection
- keep outputs auditable through evidence references
- return practical next actions instead of generic commentary

Manual project review is slow. Generic AI summaries are usually vague. AbleReport exists to produce structured, testable diagnosis rather than open-ended opinion.

---

## Product Stance

AbleReport is intentionally opinionated.

### Principles

- Deterministic first
- Schema-locked outputs
- Evidence-linked findings
- Minimal speculation
- Backward-compatible implementation where possible

### Operating rule

If a finding is not supported by the input, it should not appear as fact.

That means:

- every finding must be grounded in explicit evidence from the JSON
- uncertainty must be stated clearly when evidence is weak or incomplete
- recommended actions must be specific and testable
- creative coaching is not the source of truth

---

## What AbleReport Is Not

AbleReport is **not** designed to be:

- an open-ended music coach
- a generative arrangement assistant
- a DAW control layer
- an automated project editor
- a system that hallucinates explanations from thin air

This is a **technical diagnostic system** first.

---

## Current MVP Scope

### In scope

- Accept AI Key JSON
- Produce a schema-locked diagnostic report
- Prioritize signal path, routing, gain, and device chain issues
- Return concise recommended actions

### Out of scope

- Open-ended music coaching
- Generative arrangement advice
- DAW control or automated project editing

---

## Diagnostic Priority Order

AbleReport should inspect issues in a strict order of importance:

1. Missing or broken audio signal path
2. Routing or gain-staging issues
3. Device chain problems
4. Arrangement or structural issues only when strongly evidenced
5. Clear statement of uncertainty when evidence is insufficient

This matters because a missing signal path is more important than stylistic advice, and a routing failure is more important than abstract mix commentary.

---

## Input: AI Key JSON

AbleReport accepts an **AI Key** JSON object representing exported Ableton project data.

Current schema supports these top-level properties:

- `project_name`
- `tracks`
- `devices`
- `routing`
- `timeline`

The current AI Key schema is intentionally permissive at the top level with `additionalProperties: true`. That keeps the system forward-compatible as the Ableton export becomes richer over time.

### Example input

```json
{
  "project_name": "Demo Track",
  "tracks": [
    {
      "name": "Kick",
      "type": "audio",
      "devices": ["EQ Eight", "Saturator", "Utility"]
    },
    {
      "name": "Bass",
      "type": "midi",
      "devices": ["Operator", "Auto Filter"]
    },
    {
      "name": "Pad",
      "type": "audio",
      "devices": []
    }
  ],
  "routing": {
    "master": true
  }
}
```

### Why JSON first

Using structured export data instead of screenshots or free text gives AbleReport three real advantages:

- deterministic inspection becomes possible
- evidence paths can point to exact fields
- the same project can be tested repeatedly and consistently

---

## Output: DiagnosticReport JSON

AbleReport returns a **DiagnosticReport** JSON object.

### Required top-level fields

- `report_version`
- `project_name`
- `summary`
- `findings`
- `limitations`

### Required fields for each finding

- `id`
- `category`
- `severity`
- `title`
- `explanation`
- `evidence`
- `recommended_action`

### Required fields for each evidence item

- `field_path`
- `excerpt`
- `confidence`

### Why this matters

Most AI diagnostics fail because they blur observation, interpretation, and invention. AbleReport forces those apart:

- the input is structured
- the output shape is fixed
- each finding needs evidence
- limitations are explicit

That makes the result more auditable, easier to debug, and more useful for future evaluation.

---

## Example Report Shape

```json
{
  "report_version": "0.1.0",
  "project_name": "Demo Track",
  "summary": "One likely signal-chain issue was detected and should be checked before broader mix review.",
  "findings": [
    {
      "id": "F-001",
      "category": "device_chain",
      "severity": "medium",
      "title": "Audio track has no devices",
      "explanation": "The Pad track is an audio track with an empty device list. This may be valid, but it removes any evidence of processing or utility control on that channel.",
      "evidence": [
        {
          "field_path": "tracks[2].devices",
          "excerpt": "[]",
          "confidence": 0.95
        }
      ],
      "recommended_action": "Confirm whether the Pad track is intentionally unprocessed. If not, inspect the track chain, routing, and expected utilities or inserts."
    }
  ],
  "limitations": [
    "The report only reflects fields present in the supplied AI Key JSON.",
    "No unsupported assumptions were made about missing timeline or routing detail."
  ]
}
```

---

## Architecture

AbleReport is designed as a layered system.

### 1. Ableton export layer
A Live project is exported into AI Key JSON.

### 2. Deterministic diagnostic engine
Concrete rules inspect the JSON for specific technical issues.

Examples:

- missing routing
- broken signal path indicators
- empty device chains
- suspicious gain or utility states
- structural inconsistencies in exported data

### 3. Validation layer
The output is validated against the `DiagnosticReport` schema.

This ensures:

- stable structure
- required fields present
- less downstream fragility
- easier testing

### 4. Optional LLM reasoning layer
An LLM may help convert rule hits into concise explanations, summaries, or prioritised phrasing.

But the LLM is constrained:

- it must not invent facts
- it must not override explicit evidence
- it must remain inside the validated output contract

---

## Deterministic-First Philosophy

AbleReport should always prefer a narrow, grounded answer over a broad but unreliable one.

Good behavior:

- detect one real issue clearly
- cite the exact source field
- explain why it matters
- recommend a specific next check

Bad behavior:

- improvising arrangement advice without evidence
- claiming a routing bug with no routing data
- making creative judgments sound like technical facts

---

## Current State

Based on the project documents available, the current build includes:

- prompt scaffolding
- report schema
- API runner skeleton
- example inputs

That means the project is at a useful early foundation stage, but not yet a finished production system.

---

## What Still Needs To Be Built

### Near-term

- deterministic rule set beyond scaffolding
- JSON parse failure handling
- smoke tests and targeted rule tests
- comparison of deterministic-only output vs optional LLM-assisted explanation layer

### Later

- evaluation dataset
- wider rule coverage
- confidence calibration
- benchmark process for report quality and consistency

---

## Suggested Rule Development Strategy

Do not try to solve everything at once.

Build AbleReport by adding narrowly scoped deterministic rules one at a time.

### Rule template

For each new rule:

1. detect one concrete issue
2. emit one evidence-backed finding
3. keep edits minimal
4. add or update one test
5. preserve existing behavior outside that rule

This matches the project’s existing implementation guidance and keeps the engine stable.

Examples of strong early rules:

- audio track with empty device chain
- missing master routing flag
- malformed or missing track list
- routing object absent where required by current analysis mode
- timeline missing when a rule depends on it

---

## Schemas

### AIKey schema

The current AI Key schema is permissive, which is good for forward compatibility but means downstream rules need to handle incomplete or irregular data defensively.

### DiagnosticReport schema

The current report schema is strict, which is good. It forces:

- predictable output structure
- explicit evidence objects
- controlled top-level fields
- fewer silent format failures

That strictness should stay.

---

## Suggested Repo Structure

The existing docs indicate a structure along these lines:

```text
.
├── docs/           # product docs and architecture notes
├── prompts/        # system and task prompts
├── schemas/        # AIKey and DiagnosticReport JSON schemas
├── examples/       # sample inputs and sample outputs
├── src/            # runner, rules, validation, report assembly
├── tests/          # smoke tests and rule tests
└── README.md
```

If the repo is not yet organised this way, it should be.

---

## Local Setup

Current setup guidance from the project stub is minimal:

```bash
make setup
cp .env.example .env
```

Add your API key to `.env` if the optional LLM layer is enabled.

If you are running deterministic-only mode, the API key should not be required.

---

## Run

```bash
make run
```

---

## Test

```bash
make test
```

---

## Recommended Modes

### Deterministic-only mode
Use this for:

- testing core logic
- validating rules
- debugging outputs
- building confidence in the engine

### Optional LLM-assisted mode
Use this only for:

- compressing explanations
- improving summary wording
- routing to bounded reasoning helpers

The LLM should improve readability, not replace truth.

---

## Failure Handling Principles

AbleReport should fail clearly, not silently.

Recommended behavior:

- invalid JSON -> return a clear parse or validation error
- missing required report fields -> fail schema validation
- incomplete input -> return limited findings plus explicit limitations
- unsupported structures -> note limits instead of inventing interpretations

---

## Evaluation Philosophy

A good AbleReport evaluation set should test:

- whether findings are actually supported by input evidence
- whether important technical issues are prioritised correctly
- whether recommended actions are specific and testable
- whether limitations are honest when data is incomplete
- whether deterministic-only and LLM-assisted modes stay aligned

Do not evaluate this like a creative assistant. Evaluate it like a diagnostic tool.

---

## Why This Product Has Real Potential

The product idea is strong because it avoids the usual weak AI pattern.

It does **not** start from “ask an LLM to review a music project.”
It starts from:

- structured export
- deterministic inspection
- evidence-backed reporting
- bounded reasoning only where useful

That is the right foundation for something that might eventually become reliable enough for repeated use.

---

## Honest Limitations Right Now

Based on the supplied project docs, this is the honest status:

- the architecture is clear
- the product stance is clear
- the schemas are in place
- the operating rules are sensible
- the implementation appears early and narrow
- rule coverage and testing still need real work

That is not a weakness if it is presented honestly. It is an early but well-scoped system with the right design direction.

---

## Roadmap Summary

### Phase 1
- get one or two deterministic rules working end to end
- validate outputs against schema
- add smoke tests

### Phase 2
- expand rule coverage for routing, signal path, and device issues
- improve parse and failure handling
- compare deterministic-only vs optional LLM explanation layer

### Phase 3
- build evaluation dataset
- measure consistency and usefulness
- calibrate confidence and prioritisation

### Phase 4
- widen supported AI Key export detail
- support more nuanced diagnostic categories
- prepare for productised interface or API consumers

---

## Repo Summary

AbleReport is a deterministic-first diagnostic engine for Ableton Live project exports.

It uses structured AI Key JSON as input, applies evidence-backed checks, and produces a schema-locked diagnostic report. It is deliberately narrow, technical, and auditable. Optional LLM support may improve phrasing, but it must never become the source of truth.



# Offline Audio Transcriber & Summarizer (OATS)

## Goal + Stack
Local pipeline for:

`audio file -> offline ASR -> deterministic cleaning/segmentation -> action extraction -> optional validated local LLM -> structured outputs`

Core stack:
- Python 3.11+
- Pydantic v2 (strict schemas/validation)
- Regex-based deterministic extraction
- Offline Whisper backends (`faster-whisper` or `openai-whisper`), with transcript override fallback
- Optional local Ollama for `validated_llm` / `llm_optional`

## Setup
```bash
cd llm-router-agent
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Optional for offline ASR:
```bash
pip install faster-whisper
# or: pip install openai-whisper
```

Optional for LLM modes:
```bash
# make sure Ollama is running locally
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=llama3.1:8b
```

## CLI Modes + Examples
Deterministic only (no LLM):
```bash
PYTHONPATH=src python -m oats \
  --audio /path/to/memo.wav \
  --mode deterministic
```

Strict validated LLM (fails if JSON/schema invalid):
```bash
PYTHONPATH=src python -m oats \
  --audio /path/to/memo.wav \
  --mode validated_llm \
  --ollama-model llama3.1:8b
```

LLM optional (fallback to deterministic on validation failure):
```bash
PYTHONPATH=src python -m oats \
  --audio /path/to/memo.wav \
  --mode llm_optional \
  --include-sentiment
```

Handy dev override (skip ASR, use text file):
```bash
PYTHONPATH=src python -m oats \
  --audio /path/to/memo.wav \
  --transcript-override /path/to/memo.txt
```

## Output Bundle Structure
Each run writes to `runs/<timestamp>/`:

```text
runs/<timestamp>/
  run.json
  report.md
  audio_metadata.json
  transcript_raw.txt
  transcript_clean.txt
  segments.json
  actions_deterministic.json
  actions_final.json
```

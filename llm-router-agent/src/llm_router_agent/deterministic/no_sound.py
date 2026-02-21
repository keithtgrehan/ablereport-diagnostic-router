from __future__ import annotations

import json
from typing import List
from typing import Any

from ..json_io import extract_json_text
from ..router import ModelRegistry, Router, RouterPolicy
from ..validation import validate_report


CHECK_IDS_ORDER = [
    "audio_engine_enabled",
    "transport_running",
    "master_track_muted",
    "master_track_volume_silenced",
    "clips_present_any",
]


def _unknown(reason: str) -> dict:
    return {
        "root_cause_category": "unknown",
        "diagnosis": "Unable to determine cause of no sound from provided AI Key.",
        "confidence": "low",
        "evidence": [
            {
                "path": "$",
                "value": None,
                "explanation": reason,
            }
        ],
        "checks_run": CHECK_IDS_ORDER[:],
        "fix_steps": [
            "Verify your audio interface / output device is selected in Ableton Preferences.",
            "Confirm the Master track is not muted and the volume is not set extremely low.",
            "Confirm at least one track has an audible clip playing and is routed to the Master.",
        ],
    }


def _parse_ai_key_input(ai_key_json: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(ai_key_json, dict):
        return ai_key_json
    if isinstance(ai_key_json, str):
        parsed = json.loads(ai_key_json)
        if not isinstance(parsed, dict):
            raise TypeError("ai_key_json must decode to a JSON object.")
        return parsed
    raise TypeError("ai_key_json must be a dict or JSON string.")


def _build_router(router: Router | None) -> Router:
    if router is not None:
        return router
    registry = ModelRegistry()
    policy = RouterPolicy(default_provider=registry.llm_provider)
    return Router(registry=registry, policy=policy)


def _llm_prompt(ai_key: dict[str, Any], strict: bool, prior_errors: list[str] | None = None) -> str:
    retry_note = "STRICT VALIDATION RETRY." if strict else "FIRST ATTEMPT."
    errors_text = ""
    if prior_errors:
        joined = "; ".join(prior_errors[:8])
        errors_text = f"\nPrior validation errors: {joined}"

    return (
        "Return ONLY valid JSON. No markdown. No commentary.\n"
        f"{retry_note}\n"
        "Task: diagnose the no-sound issue from AI Key.\n"
        "Required schema keys: intent, diagnosis, root_cause_category, confidence, "
        "evidence, checks_run, fix_steps.\n"
        "Rules:\n"
        "- intent must be 'no_sound'\n"
        "- every evidence item must include path, value, explanation\n"
        "- each evidence.path must exist in AI Key\n"
        "- each evidence.value must exactly match AI Key value at that path\n"
        "- checks_run and fix_steps must be arrays of strings\n"
        f"{errors_text}\n\n"
        "AI_KEY_JSON:\n"
        f"{json.dumps(ai_key, ensure_ascii=False)}\n"
    )


def _parse_llm_report(raw_text: str) -> dict[str, Any]:
    extracted = extract_json_text(raw_text)
    if extracted is None:
        raise ValueError("LLM output did not contain JSON.")
    parsed = json.loads(extracted)
    if not isinstance(parsed, dict):
        raise ValueError("LLM output JSON must be an object.")
    return parsed


def _deterministic_with_intent(ai_key: dict[str, Any]) -> dict[str, Any]:
    base = diagnose_no_sound(ai_key)
    return {"intent": "no_sound", **base}


def _fallback_with_note(ai_key: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    report = _deterministic_with_intent(ai_key)
    note = "LLM failed validation; using deterministic fallback."
    if errors:
        note = f"{note} Errors: {'; '.join(errors[:4])}"
    report["notes"] = note
    return report


def diagnose_no_sound_validated(
    ai_key_json: str | dict[str, Any],
    *,
    no_llm: bool = False,
    require_llm: bool = False,
    router: Router | None = None,
) -> dict[str, Any]:
    """
    Run no-sound diagnosis with optional validated LLM path.

    Behavior:
    - if no_llm=True: deterministic report
    - if require_llm=True: try LLM -> validate -> strict retry once on failure
      -> deterministic fallback with "LLM failed validation" note
    - default: deterministic report
    """
    if no_llm and require_llm:
        raise ValueError("no_llm and require_llm cannot both be True.")

    ai_key = _parse_ai_key_input(ai_key_json)

    if no_llm or not require_llm:
        return _deterministic_with_intent(ai_key)

    active_router = _build_router(router)
    validation_errors: list[str] = []

    for attempt_idx in range(2):
        strict = attempt_idx == 1
        prompt = _llm_prompt(ai_key, strict=strict, prior_errors=validation_errors)
        try:
            raw = active_router.invoke("auditor", prompt)
            report_candidate = _parse_llm_report(raw)
        except Exception as exc:
            validation_errors.append(f"attempt {attempt_idx + 1}: invoke/parse failed: {exc}")
            continue

        valid, errors = validate_report(report_candidate, ai_key)
        if valid:
            return report_candidate
        validation_errors.extend([f"attempt {attempt_idx + 1}: {err}" for err in errors])

    return _fallback_with_note(ai_key, validation_errors)


def diagnose_no_sound(ai_key: dict) -> dict:
    """
    Deterministic no-sound diagnosis from an AbleReport AI Key (input JSON).
    Returns a validated report JSON dict (no exceptions on bad input).
    """
    try:
        project = ai_key.get("project", {})
        master = ai_key.get("master_track", {})
        tracks = ai_key.get("tracks", [])
        if not isinstance(project, dict) or not isinstance(master, dict) or not isinstance(tracks, list):
            return _unknown("Invalid AI Key shape: expected dict project/master_track and list tracks.")

        checks_run: List[str] = []

        # 1) audio engine disabled
        checks_run.append("audio_engine_enabled")
        audio_engine_enabled = project.get("audio_engine_enabled", None)
        if audio_engine_enabled is False:
            return {
                "root_cause_category": "audio_engine_disabled",
                "diagnosis": "Ableton audio engine is disabled, so the project cannot output sound.",
                "confidence": "high",
                "evidence": [
                    {
                        "path": "$.project.audio_engine_enabled",
                        "value": audio_engine_enabled,
                        "explanation": "When the audio engine is off, no signal reaches the audio output.",
                    }
                ],
                "checks_run": checks_run,
                "fix_steps": [
                    "In Ableton, ensure the audio engine is enabled (speaker / audio on).",
                    "Open Preferences → Audio and confirm a valid audio device is selected.",
                    "Press play and check that the Master meter shows signal.",
                ],
            }

        if audio_engine_enabled is None:
            return _unknown("Missing key: $.project.audio_engine_enabled")

        # 2) transport stopped
        checks_run.append("transport_running")
        transport_running = project.get("transport_running", None)
        if transport_running is False:
            return {
                "root_cause_category": "transport_stopped",
                "diagnosis": "Transport is not running, so clips are not playing and no sound is produced.",
                "confidence": "high",
                "evidence": [
                    {
                        "path": "$.project.transport_running",
                        "value": transport_running,
                        "explanation": "If transport is stopped, no playback occurs.",
                    }
                ],
                "checks_run": checks_run,
                "fix_steps": [
                    "Press Spacebar to start playback.",
                    "Ensure at least one clip is launched in Session view or playback position contains audio in Arrangement.",
                    "Confirm the Master meter shows activity during playback.",
                ],
            }

        if transport_running is None:
            return _unknown("Missing key: $.project.transport_running")

        # 3) master muted
        checks_run.append("master_track_muted")
        master_muted = master.get("muted", None)
        if master_muted is True:
            return {
                "root_cause_category": "muted_master",
                "diagnosis": "Master track is muted, preventing audio output.",
                "confidence": "high",
                "evidence": [
                    {
                        "path": "$.master_track.muted",
                        "value": master_muted,
                        "explanation": "A muted Master track blocks all outgoing audio.",
                    }
                ],
                "checks_run": checks_run,
                "fix_steps": [
                    "Locate the Master track in Ableton Live.",
                    "Disable the Mute button on the Master track.",
                    "Verify the Master meter shows signal and audio is audible.",
                ],
            }

        if master_muted is None:
            return _unknown("Missing key: $.master_track.muted")

        # 4) master level silenced
        checks_run.append("master_track_volume_silenced")
        master_vol = master.get("volume_db", None)
        if isinstance(master_vol, (int, float)) and master_vol <= -60.0:
            return {
                "root_cause_category": "master_level_silenced",
                "diagnosis": "Master track volume is effectively silenced (very low dB), so no audible output is produced.",
                "confidence": "high",
                "evidence": [
                    {
                        "path": "$.master_track.volume_db",
                        "value": master_vol,
                        "explanation": "A very low Master fader level can make output inaudible.",
                    }
                ],
                "checks_run": checks_run,
                "fix_steps": [
                    "Raise the Master fader to a normal monitoring level (e.g., around -6 dB to 0 dB).",
                    "Check that your speakers/headphones and system volume are on.",
                    "Confirm the Master meter shows signal and audio is audible.",
                ],
            }

        if master_vol is None:
            return _unknown("Missing key: $.master_track.volume_db")
        if not isinstance(master_vol, (int, float)):
            return _unknown("Invalid type for $.master_track.volume_db (expected number).")

        # 5) no clips
        checks_run.append("clips_present_any")
        if not tracks:
            return _unknown("Tracks list is empty; cannot determine if clips are present.")

        any_clip = False
        for t in tracks:
            if not isinstance(t, dict):
                return _unknown("Invalid track entry type; expected dict.")
            cp = t.get("clips_present", None)
            if cp is None:
                return _unknown("Missing key: $.tracks[*].clips_present")
            if cp is True:
                any_clip = True
                break

        if not any_clip:
            return {
                "root_cause_category": "no_clips",
                "diagnosis": "No clips are present on any track, so there is nothing to play and no sound is produced.",
                "confidence": "high",
                "evidence": [
                    {
                        "path": "$.tracks[*].clips_present",
                        "value": False,
                        "explanation": "All tracks show clips_present=false, so no audio/MIDI content is available for playback.",
                    }
                ],
                "checks_run": checks_run,
                "fix_steps": [
                    "Add or record an audio/MIDI clip on at least one track.",
                    "Launch the clip in Session view or place it in Arrangement and enable Arrangement playback.",
                    "Press play and confirm the Master meter shows signal.",
                ],
            }

        # If we reached here, the 5 checks did not find the cause.
        return {
            "root_cause_category": "unknown",
            "diagnosis": "The common no-sound causes were not detected. The issue may involve routing, device states, monitoring, or external audio settings.",
            "confidence": "low",
            "evidence": [
                {
                    "path": "$",
                    "value": None,
                    "explanation": "Audio engine, transport, master mute/level, and clip presence checks did not explain the silence.",
                }
            ],
            "checks_run": checks_run,
            "fix_steps": [
                "Check track routing and ensure tracks are routed to Master (or a valid output).",
                "Check if any track is soloed/muted unexpectedly or monitoring is misconfigured.",
                "Confirm devices/plugins are enabled and not blocking audio (e.g., gates, utility set to -inf, etc.).",
            ],
        }

    except Exception as e:
        return _unknown(f"Unexpected error during diagnosis: {e!r}")

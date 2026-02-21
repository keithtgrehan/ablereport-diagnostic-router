from __future__ import annotations

from typing import List


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

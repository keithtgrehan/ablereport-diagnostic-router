from oats.rules.extract_actions import extract_actions_from_segments
from oats.schemas import Segment


def test_extract_actions_from_markers_and_modal_clauses():
    segments = [
        Segment(
            index=0,
            text="Action item: Keith will finalize the launch checklist by 2026-03-01.",
            start_char=0,
            end_char=76,
        ),
        Segment(
            index=1,
            text="Maria should send the recap by tomorrow.",
            start_char=77,
            end_char=113,
        ),
    ]

    actions = extract_actions_from_segments(segments)
    assert len(actions) == 2

    first = actions[0]
    assert first.task == "finalize the launch checklist by 2026-03-01"
    assert first.owner is None
    assert first.due_date == "2026-03-01"
    assert first.source_segment == 0
    assert first.confidence == 0.9

    second = actions[1]
    assert second.task == "send the recap by tomorrow"
    assert second.owner == "Maria"
    assert second.due_date == "tomorrow"
    assert second.source_segment == 1
    assert second.confidence == 0.75


def test_extract_actions_deduplicates_by_task_text():
    segments = [
        Segment(
            index=0,
            text="We should update the dashboard by Friday.",
            start_char=0,
            end_char=41,
        ),
        Segment(
            index=1,
            text="Next step: we should update the dashboard by Friday.",
            start_char=42,
            end_char=95,
        ),
    ]

    actions = extract_actions_from_segments(segments)
    assert len(actions) == 1
    assert actions[0].task == "update the dashboard by Friday"
    assert actions[0].source_segment == 0


def test_extract_actions_splits_semicolon_and_ignores_noise():
    segments = [
        Segment(
            index=0,
            text="Todo: prep agenda; Alex will invite stakeholders by Monday; general update only",
            start_char=0,
            end_char=84,
        )
    ]

    actions = extract_actions_from_segments(segments)
    assert len(actions) == 2
    assert actions[0].task == "prep agenda"
    assert actions[0].confidence == 0.9
    assert actions[1].task == "invite stakeholders by Monday"
    assert actions[1].owner == "Alex"
    assert actions[1].due_date == "Monday"

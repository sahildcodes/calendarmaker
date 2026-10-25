from datetime import datetime, time
from typing import List, Dict, Any, Optional

def parse_iso_or_time(time_str: str) -> Optional[time]:
    """Helper to parse HH:MM or ISO timestamp to a time object."""
    if not time_str:
        return None
    # If ISO string like 2026-10-24T14:30:00Z
    if 'T' in time_str:
        try:
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            return dt.time()
        except Exception:
            pass
    try:
        parts = time_str.split(':')
        return time(int(parts[0]), int(parts[1]))
    except Exception:
        return None

class ConflictAdvisorService:
    def __init__(self):
        pass

    def check_duplicate(self, new_evt: Dict[str, Any], existing_evt: Dict[str, Any]) -> bool:
        """
        Checks if candidate event is a duplicate of an existing calendar event.
        Matches if titles are very similar and date matches.
        """
        if new_evt.get("start_date") != existing_evt.get("start_date"):
            return False

        t1 = new_evt.get("title", "").lower().strip()
        t2 = existing_evt.get("title", "").lower().strip()

        if not t1 or not t2:
            return False

        # Direct exact match
        if t1 == t2:
            return True

        # Strip common prefixes like course codes to compare core title
        import re
        from difflib import SequenceMatcher

        clean1 = re.sub(r'^[a-z]{2,4}\s*\d{3}\s*[-:]\s*', '', t1)
        clean2 = re.sub(r'^[a-z]{2,4}\s*\d{3}\s*[-:]\s*', '', t2)

        if clean1 == clean2 and len(clean1) > 4:
            return True

        ratio = SequenceMatcher(None, clean1, clean2).ratio()
        if ratio >= 0.78:
            return True

        # Check if both specifically reference the same assignment/exam number
        m1 = re.search(r'\b(hw|homework|project|assignment|exam|midterm|quiz)\s*#?(\d+)\b', t1)
        m2 = re.search(r'\b(hw|homework|project|assignment|exam|midterm|quiz)\s*#?(\d+)\b', t2)
        if m1 and m2:
            # Same type and same number (e.g. hw 4 and homework 4)
            type1 = 'hw' if m1.group(1) in ('hw', 'homework', 'assignment') else m1.group(1)
            type2 = 'hw' if m2.group(1) in ('hw', 'homework', 'assignment') else m2.group(1)
            if type1 == type2 and m1.group(2) == m2.group(2):
                return True

        return False

    def check_time_overlap(self, start1: str, end1: str, start2: str, end2: str) -> bool:
        """Checks if two time intervals on the same day overlap."""
        t_start1 = parse_iso_or_time(start1)
        t_end1 = parse_iso_or_time(end1)
        t_start2 = parse_iso_or_time(start2)
        t_end2 = parse_iso_or_time(end2)

        if not (t_start1 and t_end1 and t_start2 and t_end2):
            return False

        # Overlap if start1 < end2 and end1 > start2
        return (t_start1 < t_end2) and (t_end1 > t_start2)

    def evaluate_priority(self, new_evt: Dict[str, Any], existing_evt: Dict[str, Any]) -> Dict[str, Any]:
        """
        Advises the user on which event is higher priority during a schedule conflict.
        Compares categories, weights, and urgency scores.
        """
        score_new = new_evt.get("priority_score", 5)
        score_exist = existing_evt.get("priority_score", 5)

        cat_new = new_evt.get("category", "Event")
        cat_exist = existing_evt.get("category", "Event")

        title_new = new_evt.get("title", "New Event")
        title_exist = existing_evt.get("title", "Existing Event")

        if score_new > score_exist:
            winner = "new"
            reason = (
                f"'{title_new}' ({cat_new}, Priority {score_new}/10) takes precedence over "
                f"'{title_exist}' ({cat_exist}, Priority {score_exist}/10). "
                f"We advise keeping '{title_new}' and rescheduling or declining '{title_exist}'."
            )
            suggested_action = "keep_new"
        elif score_exist > score_new:
            winner = "existing"
            reason = (
                f"Existing event '{title_exist}' ({cat_exist}, Priority {score_exist}/10) takes precedence over "
                f"new event '{title_new}' ({cat_new}, Priority {score_new}/10). "
                f"We advise keeping '{title_exist}' or shifting '{title_new}' to another available time slot."
            )
            suggested_action = "keep_existing"
        else:
            winner = "tie"
            reason = (
                f"Both '{title_new}' and '{title_exist}' share equal priority ({score_new}/10). "
                f"Please review and decide whether to reschedule one of the events."
            )
            suggested_action = "user_choice"

        return {
            "winner": winner,
            "higher_priority_title": title_new if winner == "new" else (title_exist if winner == "existing" else "Equal"),
            "score_diff": abs(score_new - score_exist),
            "advisory_reason": reason,
            "suggested_action": suggested_action
        }

    def inspect_conflicts_and_duplicates(
        self,
        candidate_events: List[Dict[str, Any]],
        existing_calendar_events: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Inspects candidate events against user's existing calendar.
        Attaches duplicate flags, conflict objects, and priority advice.
        """
        for evt in candidate_events:
            evt_conflicts = []
            evt_duplicates = []

            for exist in existing_calendar_events:
                # 1. Duplicate check
                if self.check_duplicate(evt, exist):
                    evt_duplicates.append(exist)
                    evt["validation_flags"].append({
                        "type": "DUPLICATE_EVENT",
                        "severity": "warning",
                        "message": f"Duplicate detected: '{exist.get('title')}' is already on your Google Calendar on {exist.get('start_date')}."
                    })

                # 2. Time overlap conflict check
                elif evt.get("start_date") == exist.get("start_date"):
                    if self.check_time_overlap(
                        evt.get("start_time", "00:00"), evt.get("end_time", "23:59"),
                        exist.get("start_time", "00:00"), exist.get("end_time", "23:59")
                    ):
                        priority_advice = self.evaluate_priority(evt, exist)
                        conflict_detail = {
                            "existing_event": exist,
                            "overlap_time": f"{exist.get('start_time')} - {exist.get('end_time')}",
                            "priority_advice": priority_advice
                        }
                        evt_conflicts.append(conflict_detail)
                        evt["validation_flags"].append({
                            "type": "SCHEDULE_CONFLICT",
                            "severity": "error",
                            "message": f"Schedule conflict with '{exist.get('title')}': {priority_advice['advisory_reason']}"
                        })

            evt["conflicts"] = evt_conflicts
            evt["duplicates"] = evt_duplicates
            evt["has_conflict"] = len(evt_conflicts) > 0
            evt["has_duplicate"] = len(evt_duplicates) > 0

            # Recompute overall validity
            blocking_errors = [f for f in evt["validation_flags"] if f.get("severity") == "error"]
            evt["is_valid"] = len(blocking_errors) == 0

        return candidate_events

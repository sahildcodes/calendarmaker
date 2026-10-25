import re
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any, Optional
import dateutil.parser

MONTH_NAMES = {
    'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
    'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
    'aug': 8, 'august': 8, 'sep': 9, 'sept': 9, 'september': 9,
    'oct': 10, 'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12
}

DAY_MAPPINGS = {
    'm': 'MO', 'mon': 'MO', 'monday': 'MO',
    't': 'TU', 'tu': 'TU', 'tue': 'TU', 'tues': 'TU', 'tuesday': 'TU',
    'w': 'WE', 'wed': 'WE', 'wednesday': 'WE',
    'th': 'TH', 'thu': 'TH', 'thur': 'TH', 'thurs': 'TH', 'thursday': 'TH',
    'r': 'TH',
    'f': 'FR', 'fri': 'FR', 'friday': 'FR',
    'sa': 'SA', 'sat': 'SA', 'saturday': 'SA',
    'su': 'SU', 'sun': 'SU', 'sunday': 'SU'
}

class EventParserService:
    def __init__(self, reference_date: Optional[date] = None):
        # Local reference date context (Sept 2026)
        self.ref_date = reference_date or date(2026, 9, 13)

    def classify_category(self, text: str) -> Dict[str, Any]:
        """Classifies event type and extracts priority indicators like grade percentages or mandatory attendance."""
        lower = text.lower()
        
        # Check percentage weight: e.g. "25% of grade", "worth 30%"
        weight_match = re.search(r'(\d{1,3})%\s*(?:of\s*(?:total\s*)?grade|weight|final)', lower)
        weight_pct = int(weight_match.group(1)) if weight_match else None

        is_mandatory = bool(re.search(r'\b(mandatory|required|attendance required|graded|must attend)\b', lower))
        
        if re.search(r'\b(final exam|midterm|exam|quiz|test|assessment)\b', lower):
            base_priority = 9
            category = "Exam"
        elif re.search(r'\b(assignment|homework|hw|project|problem set|lab report|essay|paper|due)\b', lower):
            base_priority = 8
            category = "Assignment"
        elif re.search(r'\b(shift|work|job|desk|clinic|volunteer)\b', lower):
            base_priority = 7
            category = "Work"
        elif re.search(r'\b(lecture|class|discussion|recitation|seminar|lab|course|syllabus|calculus|algebra|physics|chemistry|biology|structures)\b', lower) or re.search(r'\b[a-z]{2,4}\s*\d{3}\b', lower):
            base_priority = 6
            category = "Class"
        elif re.search(r'\b(office hours|meeting|advising|conference|standup|review session)\b', lower):
            base_priority = 5
            category = "Meeting"
        elif re.search(r'\b(hackathon|keynote|workshop|symposium|webinar|expo)\b', lower):
            base_priority = 6
            category = "Event"
        else:
            base_priority = 4
            category = "Social"

        priority_score = base_priority
        if weight_pct:
            if weight_pct >= 25:
                priority_score = min(10, priority_score + 2)
            elif weight_pct >= 10:
                priority_score = min(10, priority_score + 1)
        if is_mandatory and priority_score < 9:
            priority_score += 1

        return {
            "category": category,
            "priority_score": priority_score,
            "weight_pct": weight_pct,
            "is_mandatory": is_mandatory
        }

    def parse_time_string(self, time_str: str, meridiem: Optional[str] = None) -> Optional[time]:
        """Converts hours, minutes, and am/pm into a valid datetime.time, handling OCR variations."""
        time_str = time_str.strip().lower()
        
        # Normalize 02.00 or 02;00 -> 02:00, 02.0 -> 02:00
        time_str = re.sub(r'[.;](\d{2})\b', r':\1', time_str)
        time_str = re.sub(r'[.;]0\b', r':00', time_str)

        m = re.match(r'^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$', time_str)
        if m:
            hour = int(m.group(1))
            minute = int(m.group(2)) if m.group(2) else 0
            ampm = m.group(3) or meridiem
            if ampm:
                ampm = ampm.lower()
                if ampm.startswith('p') and hour < 12:
                    hour += 12
                elif ampm.startswith('a') and hour == 12:
                    hour = 0
            if 0 <= hour < 24 and 0 <= minute < 60:
                return time(hour, minute)

        # Handle 3 or 4-digit OCR time e.g. 0300 -> 03:00, 1000 -> 10:00, 930 -> 09:30
        m_digits = re.match(r'^(\d{1,2})([0-5]\d)\s*(am|pm)?$', time_str)
        if m_digits:
            hour = int(m_digits.group(1))
            minute = int(m_digits.group(2))
            ampm = m_digits.group(3) or meridiem
            if ampm:
                ampm = ampm.lower()
                if ampm.startswith('p') and hour < 12:
                    hour += 12
                elif ampm.startswith('a') and hour == 12:
                    hour = 0
            if 0 <= hour < 24 and 0 <= minute < 60:
                return time(hour, minute)

        return None

    def extract_time_range(self, text: str) -> Optional[Dict[str, Any]]:
        """Finds time intervals or specific deadline times."""
        # Pattern 1: 10:00 AM - 11:30 AM or 10:00 - 11:30 AM or 2 to 4 PM
        range_match = re.search(
            r'\b(\d{1,2}(?::\d{2})?)\s*(am|pm)?\s*(?:-|–|—|to|until)\s*(\d{1,2}(?::\d{2})?)\s*(am|pm)\b',
            text, re.IGNORECASE
        )
        if range_match:
            start_raw, start_ampm, end_raw, end_ampm = range_match.groups()
            end_t = self.parse_time_string(end_raw, end_ampm)
            start_t = self.parse_time_string(start_raw, start_ampm or end_ampm)
            if start_t and end_t:
                return {
                    "start_time": start_t.strftime("%H:%M"),
                    "end_time": end_t.strftime("%H:%M"),
                    "is_missing_time": False,
                    "inferred_end_time": False
                }

        # Pattern 2: Single explicit time (e.g. "at 11:59 PM", "due 11:59 PM", "by 5:00 PM")
        single_match = re.search(r'\b(?:at|by|due(?:\s*at)?)\s*(\d{1,2}(?::\d{2})?)\s*(am|pm)\b', text, re.IGNORECASE)
        if not single_match:
            single_match = re.search(r'\b(\d{1,2}:\d{2})\s*(am|pm)\b', text, re.IGNORECASE)

        if single_match:
            t_raw, ampm = single_match.groups()
            t = self.parse_time_string(t_raw, ampm)
            if t:
                # If deadline late at night (e.g. 11:59 PM), duration 30m prior or prompt
                start_dt = datetime.combine(self.ref_date, t)
                end_dt = start_dt + timedelta(hours=1)
                return {
                    "start_time": t.strftime("%H:%M"),
                    "end_time": end_dt.time().strftime("%H:%M"),
                    "is_missing_time": False,
                    "inferred_end_time": True
                }

        return None

    def extract_dates(self, text: str) -> List[Dict[str, Any]]:
        """
        Extracts dates from text and flags ambiguity (e.g. MM/DD vs DD/MM, missing year).
        """
        results = []
        
        # 1. Month Day Year: e.g. "Friday, Oct 24, 2026" or "October 24" or "Nov. 15th"
        month_day_pattern = re.compile(
            r'\b(?:(mon|tue|wed|thu|fri|sat|sun)[a-z]*,?\s*)?'
            r'(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+'
            r'(\d{1,2})(?:st|nd|rd|th)?'
            r'(?:,?\s*(\d{4}))?\b',
            re.IGNORECASE
        )
        for m in month_day_pattern.finditer(text):
            month_str = m.group(2).lower()
            month_num = MONTH_NAMES.get(month_str[:3])
            day_num = int(m.group(3))
            year_str = m.group(4)
            year_num = int(year_str) if year_str else self.ref_date.year

            if month_num and 1 <= day_num <= 31:
                try:
                    d = date(year_num, month_num, day_num)
                    results.append({
                        "date": d.strftime("%Y-%m-%d"),
                        "matched_text": m.group(0),
                        "is_ambiguous": False,
                        "ambiguity_reason": None if year_str else f"Year not specified in text; inferred current year ({year_num})."
                    })
                except ValueError:
                    pass

        # 2. Numeric dates: e.g. "10/24/2026", "04/05/2026", "10-24"
        numeric_pattern = re.compile(r'\b(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\b')
        for m in numeric_pattern.finditer(text):
            p1, p2, p3 = m.group(1), m.group(2), m.group(3)
            num1, num2 = int(p1), int(p2)
            if num1 > 31 or num2 > 31:
                continue

            year = self.ref_date.year
            if p3:
                year = int(p3) if len(p3) == 4 else 2000 + int(p3)

            is_ambiguous = False
            ambiguity_reason = None
            
            # If both num1 <= 12 and num2 <= 12 and num1 != num2, it is ambiguous between MM/DD and DD/MM!
            if num1 <= 12 and num2 <= 12 and num1 != num2:
                is_ambiguous = True
                ambiguity_reason = f"Ambiguous date '{m.group(0)}': could be {num1}/{num2} or {num2}/{num1}. Defaulted to MM/DD."
                month, day = num1, num2
            elif num1 <= 12 and num2 > 12:
                month, day = num1, num2
            elif num1 > 12 and num2 <= 12:
                day, month = num1, num2
            else:
                month, day = num1, num2

            try:
                d = date(year, month, day)
                results.append({
                    "date": d.strftime("%Y-%m-%d"),
                    "matched_text": m.group(0),
                    "is_ambiguous": is_ambiguous,
                    "ambiguity_reason": ambiguity_reason
                })
            except ValueError:
                pass

        # 3. Relative words: "Tomorrow", "Next Monday", "This Friday"
        if re.search(r'\btomorrow\b', text, re.IGNORECASE):
            d = self.ref_date + timedelta(days=1)
            results.append({
                "date": d.strftime("%Y-%m-%d"),
                "matched_text": "Tomorrow",
                "is_ambiguous": False,
                "ambiguity_reason": f"Calculated relative to current date ({self.ref_date.strftime('%b %d, %Y')})."
            })

        return results

    def extract_location(self, text: str) -> Optional[str]:
        """Identifies location such as room numbers, hall names, or meeting platforms."""
        loc_patterns = [
            r'\b(?:room|rm\.?|hall|auditorium|center|building|bldg\.?|lab)\s*[:#-]?\s*([A-Za-z0-9\s-]+?\b(?=(?:\n|$|,|\.|;)))',
            r'\b(zoom(?:\.us)?\b[^\n,]*|google meet|microsoft teams|canvas)\b',
            r'\b(?:location|venue|where)\s*[:#-]?\s*([^\n,;]+)'
        ]
        for pat in loc_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                val = m.group(1) if m.lastindex >= 1 else m.group(0)
                cleaned = val.strip().strip("-:.,")
                if len(cleaned) > 2:
                    return cleaned
        return None

    def extract_days_of_week(self, text: str) -> List[str]:
        """Extracts repeating class days like MWF, TR, Tuesday & Thursday."""
        # Common schedule notation MWF, TR, MW, TTH
        m = re.search(r'\b(MWF|TR|TTH|MW|WF|M/W/F|T/R)\b', text, re.IGNORECASE)
        if m:
            code = m.group(1).upper().replace('/', '')
            if code == "MWF":
                return ["MO", "WE", "FR"]
            elif code in ("TR", "TTH"):
                return ["TU", "TH"]
            elif code == "MW":
                return ["MO", "WE"]
            elif code == "WF":
                return ["WE", "FR"]

        days = []
        for name, code in DAY_MAPPINGS.items():
            if len(name) > 2 and re.search(rf'\b{name}\b', text, re.IGNORECASE):
                if code not in days:
                    days.append(code)
        return days

    def parse_events(self, normalized_text: str) -> List[Dict[str, Any]]:
        """
        Parses full structured calendar events from normalized OCR text.
        Intelligently identifies whether the document is:
        1. A multi-item schedule table (e.g. multiple distinct courses like CS 210, MATH 251, CHEM 102).
        2. A single assignment rubric / announcement document (consolidated into one primary event).
        """
        lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]
        if not lines:
            return []

        # Find all distinct course codes or distinct schedule item headers (e.g., "CS 210", "MATH 251", "CHEM 102", "S 210")
        course_header_pattern = re.compile(
            r'^(?:Course\s*:\s*)?([A-Z]{1,5}\s*\d{2,4}[A-Z]?)',
            re.IGNORECASE
        )
        
        # Check if text contains multiple distinct course codes
        course_matches = []
        for idx, line in enumerate(lines):
            m = course_header_pattern.search(line)
            if m:
                code = m.group(1).upper().replace(" ", "")
                # Avoid counting breadcrumb or title mentions twice
                if not any(cm[1] == code for cm in course_matches):
                    course_matches.append((idx, code, line))

        candidate_blocks = []

        # If 2 or more distinct course codes appear at the start of different lines, split by course
        if len(course_matches) >= 2:
            indices = [cm[0] for cm in course_matches]
            for i in range(len(indices)):
                start_i = indices[i]
                end_i = indices[i+1] if (i + 1 < len(indices)) else len(lines)
                block_text = "\n".join(lines[start_i:end_i])
                candidate_blocks.append(block_text)
        else:
            # Single document (Assignment rubric, Event Flyer, or Single Class)
            candidate_blocks = ["\n".join(lines)]

        events = []
        for block_idx, block_text in enumerate(candidate_blocks):
            block_lines = [l for l in block_text.splitlines() if l.strip()]
            if not block_lines:
                continue

            # Extract category & priority indicators first
            cat_info = self.classify_category(block_text)

            # Smart Title Extraction
            # Ignore lines that are navigation breadcrumbs or form labels
            def is_ignorable_line(line_str: str) -> bool:
                l_lower = line_str.lower().strip()
                if re.match(r'^(courses\s*>|portal\s*>|home\s*>|navigation|menu)', l_lower):
                    return True
                if re.match(r'^(date\s*&?\s*time|location|details\s*&?\s*agenda|rubric|status|grading|notes?)\s*[:#-]?$', l_lower):
                    return True
                return False

            title = None

            # 1. Look for explicit Homework / Assignment / Exam title (e.g. "Homework 4: Dynamic Programming", "CS 101 Midterm")
            hw_pattern = re.compile(
                r'\b((?:Homework|HW|Assignment|Project|Exam|Quiz|Midterm|Final)\s+#?\d+[\s\w:&-]+)',
                re.IGNORECASE
            )
            for l in block_lines:
                if is_ignorable_line(l):
                    continue
                m = hw_pattern.search(l)
                if m and len(m.group(1).strip()) > 5:
                    title = m.group(1).strip()
                    break

            # 2. Look for Event / Hackathon / Keynote / Workshop title
            if not title:
                for l in block_lines[:4]:
                    if is_ignorable_line(l):
                        continue
                    if re.search(r'\b(hackathon|conference|symposium|ceremony|workshop|keynote|meeting|talk|seminar)\b', l, re.IGNORECASE):
                        title = l.strip()
                        break

            # 3. Look for Course Code title line
            if not title:
                for l in block_lines:
                    if is_ignorable_line(l):
                        continue
                    m = course_header_pattern.search(l)
                    if m:
                        title = l.strip()
                        break

            # 4. Fallback to first non-ignorable line
            if not title:
                for l in block_lines:
                    if not is_ignorable_line(l) and len(l) > 4:
                        title = l.strip()
                        break

            if not title:
                title = block_lines[0].strip()

            # Clean prefixes from title
            title = re.sub(r'^(title|course|event|assignment|name)\s*:\s*', '', title, flags=re.IGNORECASE).strip()
            if len(title) > 60:
                title = title[:57] + "..."

            # If title is an assignment and a course code is found, prepend course code cleanly
            course_in_text = re.search(r'\b([A-Z]{2,4}\s*\d{3})\b', block_text)
            if course_in_text and course_in_text.group(1).upper() not in title.upper():
                if cat_info["category"] in ("Assignment", "Exam"):
                    title = f"{course_in_text.group(1).upper()} - {title}"

            # Extract date
            dates = self.extract_dates(block_text)
            date_val = None
            is_ambiguous_date = False
            ambiguity_reason = None

            if dates:
                date_val = dates[0]["date"]
                is_ambiguous_date = dates[0]["is_ambiguous"]
                ambiguity_reason = dates[0]["ambiguity_reason"]
            else:
                # If no specific date found, check for recurring schedule days (e.g. MWF)
                days = self.extract_days_of_week(block_text)
                if days:
                    date_val = self.ref_date.strftime("%Y-%m-%d")
                else:
                    date_val = (self.ref_date + timedelta(days=1)).strftime("%Y-%m-%d")
                    is_ambiguous_date = True
                    ambiguity_reason = "No explicit date found in text. Defaulted to tomorrow."

            # Extract time
            time_range = self.extract_time_range(block_text)
            if time_range:
                start_time = time_range["start_time"]
                end_time = time_range["end_time"]
                is_missing_time = time_range["is_missing_time"]
                inferred_end_time = time_range["inferred_end_time"]
            else:
                # Missing time
                is_missing_time = True
                inferred_end_time = True
                if cat_info["category"] in ("Assignment", "Exam"):
                    start_time = "23:59"
                    end_time = "23:59"
                else:
                    start_time = "09:00"
                    end_time = "10:00"

            # Extract location
            location = self.extract_location(block_text)
            if not location:
                if "canvas" in block_text.lower():
                    location = "Canvas Submission Portal"
                elif "zoom" in block_text.lower():
                    location = "Zoom Online Meeting"

            # Extract recurring days
            rrule_days = self.extract_days_of_week(block_text)
            recurrence = None
            if rrule_days:
                recurrence = f"RRULE:FREQ=WEEKLY;BYDAY={','.join(rrule_days)}"

            # Validation flags
            validation_flags = []
            if is_ambiguous_date:
                validation_flags.append({
                    "type": "AMBIGUOUS_DATE",
                    "severity": "warning",
                    "message": ambiguity_reason or "Date format is ambiguous."
                })
            if is_missing_time:
                validation_flags.append({
                    "type": "MISSING_TIME",
                    "severity": "warning",
                    "message": f"No start/end time found in text. Suggested default: {start_time}."
                })

            # Format clean description snippet
            desc_snippet = "\n".join(l for l in block_lines if not l.startswith("Courses >"))
            if len(desc_snippet) > 300:
                desc_snippet = desc_snippet[:297] + "..."

            # Enforce limits and sanitize event fields
            from backend.security import enforce_event_limits
            evt_dict = {
                "id": f"evt_{block_idx + 1}_{int(datetime.now().timestamp())}",
                "title": title or "Calendar Event",
                "start_date": date_val,
                "end_date": date_val,
                "start_time": start_time,
                "end_time": end_time,
                "is_all_day": False,
                "location": location or "",
                "description": desc_snippet,
                "category": cat_info["category"],
                "priority_score": cat_info["priority_score"],
                "weight_pct": cat_info["weight_pct"],
                "is_mandatory": cat_info["is_mandatory"],
                "recurrence": recurrence,
                "validation_flags": validation_flags,
                "is_valid": len(validation_flags) == 0,
                "status": "ready_for_review"
            }
            events.append(enforce_event_limits(evt_dict))

        return events


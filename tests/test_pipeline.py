import os
import pytest
from datetime import date
from backend.ocr_service import OCRService
from backend.parser_service import EventParserService
from backend.conflict_advisor import ConflictAdvisorService
from backend.calendar_service import CalendarService

@pytest.fixture
def ocr_service():
    return OCRService()

@pytest.fixture
def parser_service():
    return EventParserService(reference_date=date(2026, 9, 13))

@pytest.fixture
def conflict_advisor():
    return ConflictAdvisorService()

@pytest.fixture
def calendar_service(tmp_path):
    data_dir = str(tmp_path / "test_data")
    return CalendarService(data_dir=data_dir)

def test_text_normalization(ocr_service):
    raw = "Due: 11.59 pn — submit assign-\nment on Canvas"
    normalized = ocr_service.normalize_text(raw)
    assert "11:59 PM" in normalized
    assert "-" in normalized
    assert "assignment" in normalized

def test_date_parsing_and_ambiguity(parser_service):
    # Absolute unambiguous
    dates = parser_service.extract_dates("Exam scheduled on October 24, 2026 at 2 PM")
    assert len(dates) == 1
    assert dates[0]["date"] == "2026-10-24"
    assert dates[0]["is_ambiguous"] is False

    # Ambiguous date: 04/05/2026 (both numbers <= 12)
    amb_dates = parser_service.extract_dates("Meeting on 04/05/2026")
    assert len(amb_dates) == 1
    assert amb_dates[0]["is_ambiguous"] is True
    assert "Ambiguous date" in amb_dates[0]["ambiguity_reason"]

    # Unambiguous numeric date: 10/24/2026 (24 > 12)
    unamb_dates = parser_service.extract_dates("Project due on 10/24/2026")
    assert len(unamb_dates) == 1
    assert unamb_dates[0]["date"] == "2026-10-24"
    assert unamb_dates[0]["is_ambiguous"] is False

def test_time_range_extraction(parser_service):
    res = parser_service.extract_time_range("Discussion from 01:30 PM to 03:00 PM in Room 104")
    assert res is not None
    assert res["start_time"] == "13:30"
    assert res["end_time"] == "15:00"

    res_single = parser_service.extract_time_range("Homework due at 11:59 PM")
    assert res_single is not None
    assert res_single["start_time"] == "23:59"

def test_duplicate_detection(conflict_advisor):
    new_evt = {
        "title": "CS 101 - Homework 4: Dynamic Programming",
        "start_date": "2026-10-24",
        "start_time": "23:59"
    }
    existing_evt = {
        "title": "CS 101 Homework 4: Dynamic Programming",
        "start_date": "2026-10-24",
        "start_time": "23:59"
    }
    different_evt = {
        "title": "CS 101 Midterm Examination",
        "start_date": "2026-10-24",
        "start_time": "14:00"
    }
    assert conflict_advisor.check_duplicate(new_evt, existing_evt) is True
    assert conflict_advisor.check_duplicate(new_evt, different_evt) is False

def test_conflict_overlap_and_priority_advisory(conflict_advisor):
    exam_evt = {
        "title": "CS 101 Midterm Exam",
        "start_date": "2026-10-24",
        "start_time": "14:00",
        "end_time": "16:00",
        "category": "Exam",
        "priority_score": 9
    }
    social_evt = {
        "title": "Weekly Board Game Social",
        "start_date": "2026-10-24",
        "start_time": "15:00",
        "end_time": "17:00",
        "category": "Social",
        "priority_score": 3
    }
    
    # Overlap check
    assert conflict_advisor.check_time_overlap(
        exam_evt["start_time"], exam_evt["end_time"],
        social_evt["start_time"], social_evt["end_time"]
    ) is True

    # Priority evaluation
    advice = conflict_advisor.evaluate_priority(exam_evt, social_evt)
    assert advice["winner"] == "new"
    assert "CS 101 Midterm Exam" in advice["advisory_reason"]
    assert "Weekly Board Game Social" in advice["advisory_reason"]
    assert advice["suggested_action"] == "keep_new"

def test_ics_generation(calendar_service):
    events = [{
        "id": "evt_test_1",
        "title": "Algorithms Exam",
        "start_date": "2026-10-24",
        "end_date": "2026-10-24",
        "start_time": "14:00",
        "end_time": "16:00",
        "location": "Room 302",
        "description": "Midterm test",
        "category": "Exam"
    }]
    ics_str = calendar_service.generate_ics(events)
    assert "BEGIN:VCALENDAR" in ics_str
    assert "SUMMARY:Algorithms Exam" in ics_str
    assert "DTSTART:20261024T140000" in ics_str
    assert "CATEGORIES:EXAM" in ics_str
    assert "END:VCALENDAR" in ics_str

def test_google_oauth_config_and_auth_url(calendar_service, monkeypatch):
    monkeypatch.setattr(calendar_service, "get_credentials_path", lambda: calendar_service.credentials_file if os.path.exists(calendar_service.credentials_file) else None)
    if os.path.exists(calendar_service.credentials_file):
        os.remove(calendar_service.credentials_file)
    assert calendar_service.has_client_credentials() is False
    calendar_service.save_client_config(
        client_id="dummy-test-id.apps.googleusercontent.com",
        client_secret="dummy-test-secret"
    )
    assert calendar_service.has_client_credentials() is True
    res = calendar_service.get_auth_url("http://127.0.0.1:8080/api/calendar/oauth-callback")
    assert "accounts.google.com/o/oauth2/auth" in res["auth_url"]
    assert "dummy-test-id.apps.googleusercontent.com" in res["auth_url"]
    assert "state" in res


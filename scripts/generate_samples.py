import os
from PIL import Image, ImageDraw, ImageFont

def generate_samples():
    os.makedirs("samples", exist_ok=True)

    # 1. Assignment Canvas Screenshot
    img1 = Image.new("RGB", (900, 520), color="#1e1e2d")
    draw = ImageDraw.Draw(img1)
    
    # Canvas top bar
    draw.rectangle([(0, 0), (900, 60)], fill="#151521")
    draw.rectangle([(0, 0), (8, 60)], fill="#e11d48")
    
    # Top bar texts
    draw.text((30, 20), "Courses  >  CS 101: Computer Science I  >  Assignments", fill="#94a3b8")
    
    # Main Card
    draw.rectangle([(40, 80), (860, 480)], fill="#27273a", outline="#3b3b54", width=2)
    
    # Title
    draw.text((65, 110), "Homework 4: Dynamic Programming & Recursion", fill="#ffffff")
    draw.rectangle([(65, 145), (280, 147)], fill="#6366f1")
    
    # Metadata badges
    draw.rectangle([(65, 170), (450, 215)], fill="#1a1a27", outline="#475569")
    draw.text((80, 185), "Due: Friday, Oct 24, 2026 at 11:59 PM", fill="#38bdf8")
    
    draw.rectangle([(470, 170), (620, 215)], fill="#1a1a27", outline="#475569")
    draw.text((490, 185), "Points: 100", fill="#a3e635")

    draw.rectangle([(640, 170), (835, 215)], fill="#1a1a27", outline="#475569")
    draw.text((655, 185), "Weight: 20% of final grade", fill="#f43f5e")

    # Body description
    draw.text((65, 240), "Assignment Instructions & Rubric:", fill="#e2e8f0")
    draw.text((65, 275), "• Implement bottom-up dynamic programming solution for the knapsack problem.", fill="#cbd5e1")
    draw.text((65, 305), "• Location: Submit single zip archive to Canvas portal.", fill="#cbd5e1")
    draw.text((65, 335), "• Academic Integrity: All code must be original. Collaboration is strictly prohibited.", fill="#cbd5e1")
    draw.text((65, 365), "• Late Policy: 10% penalty per day late up to 48 hours maximum.", fill="#cbd5e1")
    draw.text((65, 410), "Status: Published  |  Grading: Graded Assignment (Mandatory)", fill="#fbbf24")

    img1.save("samples/assignment_canvas.png")
    print("Saved samples/assignment_canvas.png")

    # 2. Event Flyer Screenshot (Overlaps with CS 101 Midterm / Board Game Social)
    img2 = Image.new("RGB", (850, 560), color="#ffffff")
    draw2 = ImageDraw.Draw(img2)
    
    # Header Banner
    draw2.rectangle([(0, 0), (850, 110)], fill="#312e81")
    draw2.text((50, 25), "ANNUAL CAMPUS HACKATHON 2026", fill="#ffffff")
    draw2.text((50, 65), "Keynote & Team Matchmaking Kickoff Session", fill="#e0e7ff")
    
    # Body
    draw2.rectangle([(30, 130), (820, 520)], fill="#f8fafc", outline="#cbd5e1", width=2)
    
    draw2.text((55, 155), "Event: Annual Campus Hackathon 2026 Kickoff", fill="#0f172a")
    draw2.text((55, 205), "Date: Saturday, Oct 24, 2026", fill="#1e293b")
    draw2.text((55, 245), "Time: 02:30 PM - 04:30 PM", fill="#1e293b")
    draw2.text((55, 295), "Location: Student Union Grand Ballroom, Room 302", fill="#2563eb")
    draw2.text((55, 345), "Attendance: Mandatory for all registered teams", fill="#dc2626")
    draw2.text((55, 395), "Agenda: Keynote speeches, sponsor introductions, team matchmaking, and dinner.", fill="#475569")
    draw2.text((65, 405), "• Event Category: Campus Event / Workshop", fill="#cbd5e1")
    draw2.text((65, 435), "• Note: Attendance recommended for all team captains.", fill="#fbbf24")

    img2.save("samples/event_flyer.png")
    print("Saved samples/event_flyer.png")

    # 3. Schedule Table Screenshot
    img3 = Image.new("RGB", (900, 480), color="#090d16")
    draw3 = ImageDraw.Draw(img3)
    
    # Top banner
    draw3.rectangle([(0, 0), (900, 70)], fill="#111827")
    draw3.text((40, 22), "University Student Portal - Weekly Class Schedule", fill="#f1f5f9")
    
    # Table Box
    draw3.rectangle([(30, 95), (870, 440)], fill="#131d31", outline="#1e293b", width=2)
    
    # Course 1
    draw3.rectangle([(50, 115), (850, 200)], fill="#1e293b")
    draw3.text((70, 130), "Course: CS 210 Data Structures and Algorithms", fill="#60a5fa")
    draw3.text((70, 160), "Days: TR | Time: 01:30 PM - 03:00 PM | Room: Turing Hall 104", fill="#e2e8f0")
    
    # Course 2
    draw3.rectangle([(50, 220), (850, 305)], fill="#1e293b")
    draw3.text((70, 235), "Course: MATH 251 Multivariable Calculus", fill="#34d399")
    draw3.text((70, 265), "Days: MWF | Time: 10:00 AM - 11:15 AM | Room: Science Hall 301", fill="#e2e8f0")

    # Course 3
    draw3.rectangle([(50, 325), (850, 410)], fill="#1e293b")
    draw3.text((70, 340), "Course: CHEM 102 General Chemistry Discussion", fill="#f472b6")
    draw3.text((70, 370), "Date: Friday, Oct 30, 2026 | Time: 02:00 PM - 03:30 PM | Chemistry Annex 12", fill="#e2e8f0")

    img3.save("samples/schedule_courses.png")
    print("Saved samples/schedule_courses.png")

if __name__ == "__main__":
    generate_samples()

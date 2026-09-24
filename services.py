import re
import sqlite3
from datetime import date
from database import audit, connect, transact


class DomainError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def required_text(value, label, maximum=120):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
        raise DomainError(400, f"{label} must be 1 to {maximum} characters.")
    return value.strip()


def positive_int(value, label):
    try:
        number = int(value)
        if number <= 0: raise ValueError()
        return number
    except (TypeError, ValueError):
        raise DomainError(400, f"{label} must be a positive number.")


def rows(sql, args=()):
    with connect() as db:
        return [dict(r) for r in db.execute(sql, args)]


def one(sql, args=()):
    with connect() as db:
        result = db.execute(sql, args).fetchone()
        return dict(result) if result else None


SECTION_SELECT = """
SELECT s.*,c.code,c.title AS course_title,c.credits,i.name AS instructor,
       (SELECT COUNT(*) FROM enrollments e WHERE e.section_id=s.id AND e.status='enrolled') AS enrolled,
       (SELECT COUNT(*) FROM enrollments e WHERE e.section_id=s.id AND e.status='waitlisted') AS waitlisted
FROM sections s JOIN courses c ON c.id=s.course_id
JOIN instructors i ON i.id=s.instructor_id
"""


def students():
    return rows("SELECT s.*,COUNT(e.id) AS active_courses FROM students s LEFT JOIN enrollments e "
                "ON e.student_id=s.id AND e.status='enrolled' GROUP BY s.id ORDER BY s.name")


def create_student(data):
    name = required_text(data.get("name"), "Name")
    email = required_text(data.get("email"), "Email", 250).lower()
    program = required_text(data.get("program"), "Program")
    year = positive_int(data.get("year"), "Year")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or year > 6:
        raise DomainError(400, "Enter a valid email and year from 1 to 6.")
    def work(db):
        number = f"S{date.today().year}{db.execute('SELECT COALESCE(MAX(id),0)+1 FROM students').fetchone()[0]:03}"
        try:
            result = db.execute("INSERT INTO students(student_no,name,email,program,year) VALUES(?,?,?,?,?)",
                                (number,name,email,program,year))
        except sqlite3.IntegrityError:
            raise DomainError(409, "That email already belongs to a student.")
        audit(db,"student.create",f"{number} · {name}")
        return {"id":result.lastrowid,"student_no":number}
    return transact(work)


def courses():
    return rows("SELECT c.*,COUNT(s.id) AS sections FROM courses c LEFT JOIN sections s "
                "ON c.id=s.course_id GROUP BY c.id ORDER BY c.code")


def create_course(data):
    code = required_text(data.get("code"), "Course code", 15).upper()
    title = required_text(data.get("title"), "Title")
    department = required_text(data.get("department"), "Department")
    description = str(data.get("description") or "")[:500]
    credits = positive_int(data.get("credits"), "Credits")
    if not re.fullmatch(r"[A-Z]{2,5}[0-9]{3,4}",code) or credits > 6:
        raise DomainError(400, "Use a code such as CS501 and 1 to 6 credits.")
    def work(db):
        try:
            result=db.execute("INSERT INTO courses(code,title,credits,department,description) VALUES(?,?,?,?,?)",
                              (code,title,credits,department,description))
        except sqlite3.IntegrityError:
            raise DomainError(409, "Course code already exists.")
        audit(db,"course.create",f"{code} · {title}")
        return {"id":result.lastrowid}
    return transact(work)


def sections():
    return rows(SECTION_SELECT+" ORDER BY s.term,s.day,s.start_time,c.code")


def instructors():
    return rows("SELECT * FROM instructors ORDER BY name")


def meeting_days(label):
    return set({"Mon/Wed":("Mon","Wed"),"Tue/Thu":("Tue","Thu"),
                "Mon":("Mon",),"Tue":("Tue",),"Wed":("Wed",),
                "Thu":("Thu",),"Fri":("Fri",)}.get(label,()))


def overlaps(first, second):
    return bool(meeting_days(first["day"]) & meeting_days(second["day"])) and (
        first["start_time"] < second["end_time"] and second["start_time"] < first["end_time"])


def create_section(data):
    course_id = positive_int(data.get("course_id"),"Course")
    instructor_id = positive_int(data.get("instructor_id"),"Instructor")
    capacity = positive_int(data.get("capacity"),"Capacity")
    term = required_text(data.get("term"),"Term",40)
    day = data.get("day")
    start = data.get("start_time")
    end = data.get("end_time")
    room = required_text(data.get("room"),"Room",60)
    if not meeting_days(day) or not isinstance(start,str) or not isinstance(end,str) or (
        not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d",start) or
        not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d",end)
    ) or start >= end or capacity > 300:
        raise DomainError(400,"Choose valid days, times, and capacity (1–300).")
    def work(db):
        if not db.execute("SELECT 1 FROM courses WHERE id=?",(course_id,)).fetchone() or not db.execute(
            "SELECT 1 FROM instructors WHERE id=?",(instructor_id,)).fetchone():
            raise DomainError(404,"Course or instructor not found.")
        peers=db.execute("SELECT * FROM sections WHERE term=? AND (instructor_id=? OR room=?)",
                         (term,instructor_id,room)).fetchall()
        candidate={"day":day,"start_time":start,"end_time":end}
        for peer in peers:
            if overlaps(candidate,peer):
                raise DomainError(409,"The instructor or room already has an overlapping section.")
        result=db.execute("INSERT INTO sections(course_id,instructor_id,term,day,start_time,end_time,room,capacity) "
                          "VALUES(?,?,?,?,?,?,?,?)",
                          (course_id,instructor_id,term,day,start,end,room,capacity))
        audit(db,"section.create",f"Section #{result.lastrowid} · {term}")
        return {"id":result.lastrowid}
    return transact(work)


def enrollments():
    return rows("""
        SELECT e.*,st.name AS student_name,st.student_no,c.code,c.title AS course_title,
               s.term,s.day,s.start_time,s.end_time
        FROM enrollments e JOIN students st ON st.id=e.student_id
        JOIN sections s ON s.id=e.section_id JOIN courses c ON c.id=s.course_id
        WHERE e.status!='dropped' ORDER BY e.id DESC
    """)


def conflict(db, student_id, section, exclude_id=None):
    peers=db.execute(
        "SELECT s.*,c.code FROM enrollments e JOIN sections s ON s.id=e.section_id "
        "JOIN courses c ON c.id=s.course_id "
        "WHERE e.student_id=? AND e.status='enrolled' AND s.term=? AND s.id!=?",
        (student_id,section["term"],exclude_id or section["id"])).fetchall()
    for peer in peers:
        if peer["course_id"]==section["course_id"]:
            return f"Already enrolled in {peer['code']} this term."
        if overlaps(section,peer):
            return f"Schedule overlaps with {peer['code']}."
    return None


def enroll(data):
    student_id=positive_int(data.get("student_id"),"Student")
    section_id=positive_int(data.get("section_id"),"Section")
    def work(db):
        if not db.execute("SELECT 1 FROM students WHERE id=?",(student_id,)).fetchone():
            raise DomainError(404,"Student not found.")
        section=db.execute("SELECT * FROM sections WHERE id=?",(section_id,)).fetchone()
        if not section: raise DomainError(404,"Section not found.")
        existing=db.execute("SELECT * FROM enrollments WHERE student_id=? AND section_id=?",
                            (student_id,section_id)).fetchone()
        if existing and existing["status"]!="dropped":
            raise DomainError(409,"Student is already enrolled or waitlisted.")
        error=conflict(db,student_id,section)
        if error: raise DomainError(409,error)
        count=db.execute("SELECT COUNT(*) FROM enrollments WHERE section_id=? AND status='enrolled'",
                         (section_id,)).fetchone()[0]
        status="enrolled" if count<section["capacity"] else "waitlisted"
        if existing:
            db.execute("UPDATE enrollments SET status=?,created_at=datetime('now') WHERE id=?",
                       (status,existing["id"]))
            record_id=existing["id"]
        else:
            record_id=db.execute("INSERT INTO enrollments(student_id,section_id,status) VALUES(?,?,?)",
                                 (student_id,section_id,status)).lastrowid
        audit(db,"enrollment.create",f"Student #{student_id} → section #{section_id} ({status})")
        return {"id":record_id,"status":status}
    return transact(work)


def drop_enrollment(enrollment_id):
    def work(db):
        enrollment=db.execute("SELECT * FROM enrollments WHERE id=?",(enrollment_id,)).fetchone()
        if not enrollment or enrollment["status"]=="dropped":
            raise DomainError(404,"Active enrollment not found.")
        db.execute("UPDATE enrollments SET status='dropped' WHERE id=?",(enrollment_id,))
        audit(db,"enrollment.drop",f"Enrollment #{enrollment_id}")
        promoted=None
        if enrollment["status"]=="enrolled":
            section=db.execute("SELECT * FROM sections WHERE id=?",(enrollment["section_id"],)).fetchone()
            waiting=db.execute("SELECT * FROM enrollments WHERE section_id=? AND status='waitlisted' "
                               "ORDER BY created_at,id",(section["id"],)).fetchall()
            for candidate in waiting:
                if not conflict(db,candidate["student_id"],section):
                    db.execute("UPDATE enrollments SET status='enrolled' WHERE id=?",(candidate["id"],))
                    promoted=candidate["student_id"]
                    audit(db,"waitlist.promote",f"Student #{promoted} → section #{section['id']}")
                    break
        return {"dropped":enrollment_id,"promoted_student_id":promoted}
    return transact(work)


def attendance(section_id):
    section=one(SECTION_SELECT+" WHERE s.id=?",(section_id,))
    if not section: raise DomainError(404,"Section not found.")
    roster=rows("""
        SELECT st.id,st.name,st.student_no,e.status FROM enrollments e
        JOIN students st ON st.id=e.student_id WHERE e.section_id=? AND e.status='enrolled'
        ORDER BY st.name
    """,(section_id,))
    marks=rows("SELECT student_id,class_date,status FROM attendance WHERE section_id=? "
               "ORDER BY class_date DESC",(section_id,))
    return {"section":section,"roster":roster,"marks":marks}


def mark_attendance(data):
    section_id=positive_int(data.get("section_id"),"Section")
    student_id=positive_int(data.get("student_id"),"Student")
    day=required_text(data.get("class_date"),"Date",10)
    status=data.get("status")
    try: date.fromisoformat(day)
    except ValueError: raise DomainError(400,"Use a YYYY-MM-DD date.")
    if status not in ("present","absent","late"):
        raise DomainError(400,"Attendance must be present, absent, or late.")
    def work(db):
        exists=db.execute("SELECT 1 FROM enrollments WHERE section_id=? AND student_id=? AND status='enrolled'",
                          (section_id,student_id)).fetchone()
        if not exists: raise DomainError(409,"Student is not enrolled in this section.")
        db.execute("INSERT INTO attendance(section_id,student_id,class_date,status) VALUES(?,?,?,?) "
                   "ON CONFLICT(section_id,student_id,class_date) DO UPDATE SET status=excluded.status",
                   (section_id,student_id,day,status))
        audit(db,"attendance.mark",f"Student #{student_id} · section #{section_id} · {day}: {status}")
        return {"saved":True}
    return transact(work)


def gradebook(section_id):
    section=one(SECTION_SELECT+" WHERE s.id=?",(section_id,))
    if not section: raise DomainError(404,"Section not found.")
    roster=rows("SELECT st.id,st.name,st.student_no FROM enrollments e JOIN students st ON st.id=e.student_id "
                "WHERE e.section_id=? AND e.status='enrolled' ORDER BY st.name",(section_id,))
    assessments=rows("SELECT * FROM assessments WHERE section_id=? ORDER BY id",(section_id,))
    scores=rows("SELECT sc.assessment_id,sc.student_id,sc.points FROM scores sc "
                "JOIN assessments a ON a.id=sc.assessment_id WHERE a.section_id=?",(section_id,))
    score_map={(s["student_id"],s["assessment_id"]):s["points"] for s in scores}
    for student in roster:
        earned=0.0
        graded_weight=0.0
        for assessment in assessments:
            score=score_map.get((student["id"],assessment["id"]))
            if score is not None:
                earned += (score/assessment["max_points"])*assessment["weight"]
                graded_weight += assessment["weight"]
        student["grade"] = round(earned/graded_weight*100,1) if graded_weight else None
    return {"section":section,"roster":roster,"assessments":assessments,"scores":scores,
            "total_weight":sum(a["weight"] for a in assessments)}


def create_assessment(data):
    section_id=positive_int(data.get("section_id"),"Section")
    title=required_text(data.get("title"),"Assessment title",100)
    try:
        max_points=float(data.get("max_points"))
        weight=float(data.get("weight"))
        if not (0<max_points<=10000 and 0<weight<=100): raise ValueError()
    except (ValueError,TypeError):
        raise DomainError(400,"Enter positive points and a weight from 0 to 100.")
    def work(db):
        if not db.execute("SELECT 1 FROM sections WHERE id=?",(section_id,)).fetchone():
            raise DomainError(404,"Section not found.")
        total=db.execute("SELECT COALESCE(SUM(weight),0) FROM assessments WHERE section_id=?",
                         (section_id,)).fetchone()[0]
        if total+weight>100.0001:
            raise DomainError(409,f"Assessment weights would exceed 100% (currently {total:g}%).")
        result=db.execute("INSERT INTO assessments(section_id,title,max_points,weight) VALUES(?,?,?,?)",
                          (section_id,title,max_points,weight))
        audit(db,"assessment.create",f"{title} · section #{section_id}")
        return {"id":result.lastrowid}
    return transact(work)


def save_score(data):
    assessment_id=positive_int(data.get("assessment_id"),"Assessment")
    student_id=positive_int(data.get("student_id"),"Student")
    try: points=float(data.get("points"))
    except (ValueError,TypeError): raise DomainError(400,"Enter a numeric score.")
    def work(db):
        assessment=db.execute("SELECT * FROM assessments WHERE id=?",(assessment_id,)).fetchone()
        if not assessment: raise DomainError(404,"Assessment not found.")
        if not 0<=points<=assessment["max_points"]:
            raise DomainError(400,f"Score must be between 0 and {assessment['max_points']:g}.")
        enrolled=db.execute("SELECT 1 FROM enrollments WHERE section_id=? AND student_id=? AND status='enrolled'",
                            (assessment["section_id"],student_id)).fetchone()
        if not enrolled: raise DomainError(409,"Student is not enrolled in this section.")
        db.execute("INSERT INTO scores(assessment_id,student_id,points) VALUES(?,?,?) "
                   "ON CONFLICT(assessment_id,student_id) DO UPDATE SET points=excluded.points",
                   (assessment_id,student_id,points))
        audit(db,"score.save",f"Student #{student_id} · assessment #{assessment_id}: {points:g}")
        return {"saved":True}
    return transact(work)


def announcements():
    return rows("SELECT a.*,c.code,c.title AS course_title FROM announcements a "
                "JOIN sections s ON s.id=a.section_id JOIN courses c ON c.id=s.course_id "
                "ORDER BY a.id DESC LIMIT 100")


def create_announcement(data):
    section_id=positive_int(data.get("section_id"),"Section")
    title=required_text(data.get("title"),"Title",100)
    body=required_text(data.get("body"),"Message",1000)
    def work(db):
        if not db.execute("SELECT 1 FROM sections WHERE id=?",(section_id,)).fetchone():
            raise DomainError(404,"Section not found.")
        result=db.execute("INSERT INTO announcements(section_id,title,body) VALUES(?,?,?)",
                          (section_id,title,body))
        audit(db,"announcement.create",f"Section #{section_id}: {title}")
        return {"id":result.lastrowid}
    return transact(work)


def analytics():
    sections_data=sections()
    with connect() as db:
        attendance_rows=db.execute("""
            SELECT section_id, COUNT(*) total, SUM(CASE WHEN status IN ('present','late') THEN 1 ELSE 0 END) attended
            FROM attendance GROUP BY section_id
        """).fetchall()
    attendance_map={r["section_id"]:r for r in attendance_rows}
    for section in sections_data:
        marks=attendance_map.get(section["id"])
        section["fill_rate"]=round(section["enrolled"]/section["capacity"]*100,1)
        section["attendance_rate"]=round(marks["attended"]/marks["total"]*100,1) if marks else None
        grades=[st["grade"] for st in gradebook(section["id"])["roster"] if st["grade"] is not None]
        section["average_grade"]=round(sum(grades)/len(grades),1) if grades else None
    return {"sections":sections_data}


def overview():
    with connect() as db:
        counts={
            "students":db.execute("SELECT COUNT(*) FROM students").fetchone()[0],
            "courses":db.execute("SELECT COUNT(*) FROM courses").fetchone()[0],
            "sections":db.execute("SELECT COUNT(*) FROM sections").fetchone()[0],
            "enrolled":db.execute("SELECT COUNT(*) FROM enrollments WHERE status='enrolled'").fetchone()[0],
            "waitlisted":db.execute("SELECT COUNT(*) FROM enrollments WHERE status='waitlisted'").fetchone()[0],
        }
    all_sections=sections()
    return {"counts":counts,"sections":all_sections,
            "announcements":announcements()[:4],
            "recent_activity":rows("SELECT * FROM audit_log ORDER BY id DESC LIMIT 8")}


def audit_log():
    return rows("SELECT * FROM audit_log ORDER BY id DESC LIMIT 100")

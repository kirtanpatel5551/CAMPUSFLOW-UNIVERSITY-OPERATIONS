import os
import sqlite3
import threading
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("CAMPUSFLOW_DB", ROOT / "campusflow.db"))
LOCK = threading.RLock()


def connect():
    db = sqlite3.connect(DB_PATH, isolation_level=None, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=15000")
    return db


def transact(work):
    with LOCK, connect() as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            result = work(db)
            db.execute("COMMIT")
            return result
        except Exception:
            db.execute("ROLLBACK")
            raise


def audit(db, action, detail):
    db.execute("INSERT INTO audit_log(action,detail,created_at) VALUES(?,?,datetime('now'))",
               (action, detail))


def initialize(seed=True):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK, connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS students(
                id INTEGER PRIMARY KEY, student_no TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
                program TEXT NOT NULL, year INTEGER NOT NULL CHECK(year BETWEEN 1 AND 6)
            );
            CREATE TABLE IF NOT EXISTS instructors(
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, department TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS courses(
                id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
                credits INTEGER NOT NULL CHECK(credits BETWEEN 1 AND 6),
                department TEXT NOT NULL, description TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS sections(
                id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL REFERENCES courses(id),
                instructor_id INTEGER NOT NULL REFERENCES instructors(id),
                term TEXT NOT NULL, day TEXT NOT NULL, start_time TEXT NOT NULL,
                end_time TEXT NOT NULL, room TEXT NOT NULL,
                capacity INTEGER NOT NULL CHECK(capacity BETWEEN 1 AND 300),
                CHECK(start_time < end_time)
            );
            CREATE TABLE IF NOT EXISTS enrollments(
                id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id),
                section_id INTEGER NOT NULL REFERENCES sections(id),
                status TEXT NOT NULL CHECK(status IN ('enrolled','waitlisted','dropped')),
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(student_id,section_id)
            );
            CREATE INDEX IF NOT EXISTS enrollment_section_status
                ON enrollments(section_id,status,created_at,id);
            CREATE TABLE IF NOT EXISTS attendance(
                id INTEGER PRIMARY KEY, section_id INTEGER NOT NULL REFERENCES sections(id),
                student_id INTEGER NOT NULL REFERENCES students(id), class_date TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('present','absent','late')),
                UNIQUE(section_id,student_id,class_date)
            );
            CREATE TABLE IF NOT EXISTS assessments(
                id INTEGER PRIMARY KEY, section_id INTEGER NOT NULL REFERENCES sections(id),
                title TEXT NOT NULL, max_points REAL NOT NULL CHECK(max_points > 0),
                weight REAL NOT NULL CHECK(weight > 0 AND weight <= 100)
            );
            CREATE TABLE IF NOT EXISTS scores(
                assessment_id INTEGER NOT NULL REFERENCES assessments(id),
                student_id INTEGER NOT NULL REFERENCES students(id),
                points REAL NOT NULL CHECK(points >= 0),
                PRIMARY KEY(assessment_id,student_id)
            );
            CREATE TABLE IF NOT EXISTS announcements(
                id INTEGER PRIMARY KEY, section_id INTEGER NOT NULL REFERENCES sections(id),
                title TEXT NOT NULL, body TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS audit_log(
                id INTEGER PRIMARY KEY, action TEXT NOT NULL, detail TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        count = db.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    if seed and not count:
        seed_data()


def seed_data():
    names = [
        ("Ava Chen","Computer Science",2),("Noah Patel","Computer Science",1),
        ("Mia Johnson","Data Science",2),("Liam Rivera","Computer Science",3),
        ("Sophia Kim","Data Science",1),("Ethan Brown","Computer Science",2),
        ("Isabella Garcia","Information Systems",3),("Oliver Smith","Computer Science",1),
        ("Emma Davis","Data Science",2),("Lucas Wilson","Information Systems",2),
        ("Amelia Martin","Computer Science",4),("James Taylor","Data Science",1),
    ]
    def seed(db):
        db.executemany("INSERT INTO students(student_no,name,email,program,year) VALUES(?,?,?,?,?)",
            [(f"S2026{i:03}",name,f"{name.lower().replace(' ','.')}@example.edu",program,year)
             for i,(name,program,year) in enumerate(names,1)])
        db.executemany("INSERT INTO instructors(name,department) VALUES(?,?)",[
            ("Dr. Maya Shah","Computer Science"),("Dr. Daniel Brooks","Computer Science"),
            ("Prof. Elena Torres","Data Science"),("Dr. Priya Nair","Information Systems")])
        db.executemany("INSERT INTO courses(code,title,credits,department,description) VALUES(?,?,?,?,?)",[
            ("CS501","Advanced Algorithms",3,"Computer Science","Graphs, complexity, and optimization."),
            ("CS520","Distributed Systems",3,"Computer Science","Coordination and fault tolerance."),
            ("CS540","Database Systems",3,"Computer Science","Relational design and transactions."),
            ("DS510","Applied Data Analytics",3,"Data Science","Data pipelines and visual analysis."),
            ("CS560","Software Architecture",3,"Computer Science","Service design and quality attributes."),
            ("IS530","Information Security",3,"Information Systems","Security operations and policy.")])
        db.executemany("INSERT INTO sections(course_id,instructor_id,term,day,start_time,end_time,room,capacity) VALUES(?,?,?,?,?,?,?,?)",[
            (1,1,"Fall 2026","Mon/Wed","09:00","10:15","Science 201",8),
            (2,2,"Fall 2026","Tue/Thu","11:00","12:15","Tech 110",6),
            (3,2,"Fall 2026","Mon/Wed","09:30","10:45","Science 205",7),
            (4,3,"Fall 2026","Tue/Thu","14:00","15:15","Data Lab",9),
            (5,2,"Fall 2026","Fri","10:00","12:30","Tech 204",5),
            (6,4,"Fall 2026","Mon/Wed","13:00","14:15","Science 310",8),
            (1,1,"Spring 2027","Tue/Thu","09:00","10:15","Science 201",10)])
        for student, section in [(1,1),(2,1),(3,1),(4,1),(5,1),(6,2),(7,2),
                                 (8,2),(9,3),(10,4),(11,4),(12,5),(1,4),(2,2)]:
            db.execute("INSERT INTO enrollments(student_id,section_id,status) VALUES(?,?,'enrolled')",
                       (student,section))
        for section,title,max_points,weight in [(1,"Midterm",100,40),(1,"Final project",100,60),
                                                 (2,"Systems lab",50,35),(2,"Final exam",100,65),
                                                 (4,"Data project",100,100)]:
            db.execute("INSERT INTO assessments(section_id,title,max_points,weight) VALUES(?,?,?,?)",
                       (section,title,max_points,weight))
        for assessment,student,points in [(1,1,91),(1,2,84),(1,3,88),(1,4,93),
                                          (2,1,96),(2,2,89),(3,6,45),(3,7,41)]:
            db.execute("INSERT INTO scores VALUES(?,?,?)",(assessment,student,points))
        for student in (1,2,3,4,5):
            db.execute("INSERT INTO attendance(section_id,student_id,class_date,status) VALUES(?,?,?,?)",
                       (1,student,date.today().isoformat(),"present" if student != 5 else "late"))
        db.execute("INSERT INTO announcements(section_id,title,body) VALUES(?,?,?)",
                   (1,"Welcome to Advanced Algorithms","Course materials are available in the student portal."))
        audit(db,"system.seed","Created sample university records")
    transact(seed)

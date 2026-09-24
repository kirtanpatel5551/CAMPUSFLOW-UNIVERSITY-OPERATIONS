import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import database
import services as svc


class CampusWorkflows(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old=database.DB_PATH
        database.DB_PATH=Path(self.tmp.name)/"test.db"
        database.initialize(seed=True)

    def tearDown(self):
        database.DB_PATH=self.old
        self.tmp.cleanup()

    def test_schedule_conflict(self):
        with self.assertRaises(svc.DomainError) as error:
            svc.enroll({"student_id":1,"section_id":3})
        self.assertEqual(error.exception.status,409)
        self.assertIn("overlaps",error.exception.message)

    def test_waitlist_and_automatic_promotion(self):
        # Section 5 has capacity 5 and one existing enrolled student.
        for student in (3,5,6,7):
            svc.enroll({"student_id":student,"section_id":5})
        waiting=svc.enroll({"student_id":8,"section_id":5})
        self.assertEqual(waiting["status"],"waitlisted")
        enrolled=next(e for e in svc.enrollments() if e["student_id"]==3 and e["section_id"]==5)
        result=svc.drop_enrollment(enrolled["id"])
        self.assertEqual(result["promoted_student_id"],8)
        self.assertEqual(next(e for e in svc.enrollments() if e["id"]==waiting["id"])["status"],"enrolled")

    def test_concurrent_last_seat(self):
        with database.connect() as db:
            db.execute("UPDATE sections SET capacity=2 WHERE id=5")
        barrier=threading.Barrier(2)
        def register(student_id):
            barrier.wait()
            return svc.enroll({"student_id":student_id,"section_id":5})["status"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(register,[3,5]))
        self.assertEqual(sorted(statuses),["enrolled","waitlisted"])

    def test_weighted_grades(self):
        book=svc.gradebook(1)
        ava=next(s for s in book["roster"] if s["id"]==1)
        self.assertAlmostEqual(ava["grade"],94.0)
        assessment=svc.create_assessment({"section_id":3,"title":"Lab","max_points":50,"weight":25})
        svc.save_score({"assessment_id":assessment["id"],"student_id":9,"points":40})
        mia=next(s for s in svc.gradebook(3)["roster"] if s["id"]==9)
        self.assertEqual(mia["grade"],80.0)

    def test_grade_weight_rejected(self):
        with self.assertRaises(svc.DomainError) as error:
            svc.create_assessment({"section_id":1,"title":"Extra","max_points":20,"weight":10})
        self.assertEqual(error.exception.status,409)

    def test_attendance_requires_enrollment(self):
        with self.assertRaises(svc.DomainError):
            svc.mark_attendance({"section_id":1,"student_id":12,"class_date":"2026-09-24","status":"present"})
        svc.mark_attendance({"section_id":1,"student_id":1,"class_date":"2026-09-24","status":"late"})
        self.assertTrue(any(m["status"]=="late" and m["student_id"]==1 for m in svc.attendance(1)["marks"]))


if __name__=="__main__":
    unittest.main()

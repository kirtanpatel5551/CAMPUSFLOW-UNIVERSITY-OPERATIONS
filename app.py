import csv
import io
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import database
import services as svc

ROOT=Path(__file__).resolve().parent
PORT=int(os.environ.get("CAMPUSFLOW_PORT","8000"))


class Handler(BaseHTTPRequestHandler):
    def reply(self,status,payload):
        raw=json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(raw)))
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(raw)

    def body(self):
        try:
            size=int(self.headers.get("Content-Length","0"))
            if not 1<=size<=30000: raise ValueError()
            value=json.loads(self.rfile.read(size))
            if not isinstance(value,dict): raise ValueError()
            return value
        except (ValueError,json.JSONDecodeError):
            raise svc.DomainError(400,"Enter a valid JSON request.")

    def route(self,method,path):
        if method=="GET":
            endpoints={
                "/api/overview":svc.overview,"/api/students":lambda:{"students":svc.students()},
                "/api/courses":lambda:{"courses":svc.courses()},
                "/api/instructors":lambda:{"instructors":svc.instructors()},
                "/api/sections":lambda:{"sections":svc.sections()},
                "/api/enrollments":lambda:{"enrollments":svc.enrollments()},
                "/api/analytics":svc.analytics,
                "/api/announcements":lambda:{"announcements":svc.announcements()},
                "/api/audit":lambda:{"entries":svc.audit_log()},
            }
            if path in endpoints: return 200,endpoints[path]()
            match=re.fullmatch(r"/api/sections/(\d+)/attendance",path)
            if match:return 200,svc.attendance(int(match[1]))
            match=re.fullmatch(r"/api/sections/(\d+)/gradebook",path)
            if match:return 200,svc.gradebook(int(match[1]))
        if method=="POST":
            endpoints={
                "/api/students":svc.create_student,"/api/courses":svc.create_course,
                "/api/sections":svc.create_section,"/api/enrollments":svc.enroll,
                "/api/attendance":svc.mark_attendance,
                "/api/assessments":svc.create_assessment,
                "/api/scores":svc.save_score,
                "/api/announcements":svc.create_announcement,
            }
            if path in endpoints:return 201,endpoints[path](self.body())
            match=re.fullmatch(r"/api/enrollments/(\d+)/drop",path)
            if match:return 200,svc.drop_enrollment(int(match[1]))
        raise svc.DomainError(404,"Resource not found.")

    def handle_method(self,method):
        try:
            path=urlparse(self.path).path
            if path.startswith("/api/"):
                status,data=self.route(method,path)
                return self.reply(status,data)
            if method!="GET":raise svc.DomainError(404,"Resource not found.")
            if path=="/analytics.csv":
                output=io.StringIO()
                writer=csv.writer(output)
                writer.writerow(["Term","Course","Section","Instructor","Enrolled","Capacity",
                                 "Fill rate %","Attendance rate %","Average grade %"])
                for sec in svc.analytics()["sections"]:
                    writer.writerow([sec["term"],sec["code"],sec["id"],sec["instructor"],
                                     sec["enrolled"],sec["capacity"],sec["fill_rate"],
                                     sec["attendance_rate"],sec["average_grade"]])
                content=output.getvalue().encode("utf-8-sig")
                content_type="text/csv; charset=utf-8"
            else:
                filename={"/":"index.html","/app.js":"app.js","/style.css":"style.css"}.get(path)
                if not filename:raise svc.DomainError(404,"Page not found.")
                content=(ROOT/"static"/filename).read_bytes()
                content_type={"index.html":"text/html; charset=utf-8",
                              "app.js":"text/javascript; charset=utf-8",
                              "style.css":"text/css; charset=utf-8"}[filename]
            self.send_response(200)
            self.send_header("Content-Type",content_type)
            self.send_header("Content-Length",str(len(content)))
            if path=="/analytics.csv":
                self.send_header("Content-Disposition",'attachment; filename="campusflow-analytics.csv"')
            self.end_headers()
            self.wfile.write(content)
        except svc.DomainError as error:
            self.reply(error.status,{"error":error.message})
        except Exception as error:
            print("Server error:",type(error).__name__,error)
            self.reply(500,{"error":"Unexpected server error."})

    def do_GET(self):self.handle_method("GET")
    def do_POST(self):self.handle_method("POST")


if __name__=="__main__":
    database.initialize()
    server=ThreadingHTTPServer(("127.0.0.1",PORT),Handler)
    print(f"CampusFlow running at http://127.0.0.1:{PORT}")
    try:server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
        print("\nStopped.")

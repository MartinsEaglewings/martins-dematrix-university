from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import os
import psycopg2
from psycopg2.extras import DictCursor

app = Flask(__name__)

# Use an environment secret on hosting, while keeping local development working.
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "mdu-development-secret-key"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "university.db")

# Admin PIN stays on the server and is never placed in JavaScript or HTML.
ADMIN_PIN = "martins_pass_2026"


class PostgreSQLConnection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, params=()):
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        return cursor

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()


def get_db():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured."
        )

    conn = psycopg2.connect(
        database_url,
        cursor_factory=DictCursor
    )
    conn.autocommit = False

    return PostgreSQLConnection(conn)


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            matric_no TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            department TEXT DEFAULT 'Computer Science',
            level TEXT DEFAULT '100 Level',
            phone TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id SERIAL PRIMARY KEY,
            code TEXT NOT NULL,
            title TEXT NOT NULL,
            units INTEGER NOT NULL,
            semester TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            session TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(id),
            FOREIGN KEY(course_id) REFERENCES courses(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL,
            course_code TEXT NOT NULL,
            course_title TEXT NOT NULL,
            units INTEGER NOT NULL,
            score INTEGER NOT NULL,
            grade TEXT NOT NULL,
            grade_point REAL NOT NULL,
            semester TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # NEW: assignments
    conn.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            course_code TEXT DEFAULT '',
            due_date TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Demo courses
    course_count = conn.execute(
        "SELECT COUNT(*) FROM courses"
    ).fetchone()[0]

    if course_count == 0:
        courses = [
            ("GST101", "Use of English", 2, "First"),
            ("CSC101", "Introduction to Computer Science", 3, "First"),
            ("MTH101", "Elementary Mathematics", 3, "First"),
            ("PHY101", "General Physics", 3, "First"),
            ("STA101", "Introduction to Statistics", 2, "First"),
            ("CSC102", "Computer Programming", 3, "Second"),
            ("MTH102", "Calculus", 3, "Second"),
            ("GST102", "Nigerian People and Culture", 2, "Second"),
        ]

        conn.executemany("""
            INSERT INTO courses(code, title, units, semester)
            VALUES (%s, %s, %s, %s)
        """, courses)

    # Demo announcement
    announcement_count = conn.execute(
        "SELECT COUNT(*) FROM announcements"
    ).fetchone()[0]

    if announcement_count == 0:
        conn.execute("""
            INSERT INTO announcements(title, message)
            VALUES (%s, %s)
        """, (
            "Welcome to Martins DeMatrix University",
            "The university portal is now open for student registration."
        ))

    conn.commit()
    conn.close()


# ============================================================
# PUBLIC WEBSITE
# ============================================================

@app.route("/")
def index():
    conn = get_db()

    announcements = conn.execute("""
        SELECT * FROM announcements
        ORDER BY created_at DESC
        LIMIT 5
    """).fetchall()

    assignments = conn.execute("""
        SELECT * FROM assignments
        ORDER BY id DESC
        LIMIT 5
    """).fetchall()

    conn.close()

    return render_template(
        "index.html",
        announcements=announcements,
        assignments=assignments
    )


# ============================================================
# STUDENT REGISTRATION
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db()

        existing = conn.execute(
            "SELECT id FROM students WHERE email = %s",
            (email,)
        ).fetchone()

        if existing:
            conn.close()
            flash("An account with this email already exists.", "error")
            return redirect(url_for("register"))

        matric_no = "MDU" + str(
            conn.execute(
                "SELECT COUNT(*) FROM students"
            ).fetchone()[0] + 1001
        )

        conn.execute("""
            INSERT INTO students
            (matric_no, full_name, email, password)
            VALUES (%s, %s, %s, %s)
        """, (
            matric_no,
            full_name,
            email,
            generate_password_hash(password)
        ))

        conn.commit()
        conn.close()

        flash(
            f"Registration successful. Your matric number is {matric_no}.",
            "success"
        )

        return redirect(url_for("login"))

    return render_template("register.html")


# ============================================================
# STUDENT LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db()

        student = conn.execute(
            "SELECT * FROM students WHERE email = %s",
            (email,)
        ).fetchone()

        conn.close()

        if student and check_password_hash(student["password"], password):
            session["student_id"] = student["id"]
            return redirect(url_for("student_dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


# ============================================================
# STUDENT DASHBOARD
# ============================================================

@app.route("/student/dashboard")
def student_dashboard():
    if "student_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    student = conn.execute(
        "SELECT * FROM students WHERE id = %s",
        (session["student_id"],)
    ).fetchone()

    results = conn.execute("""
        SELECT * FROM results
        WHERE student_id = %s
        ORDER BY id DESC
    """, (session["student_id"],)).fetchall()

    courses = conn.execute("""
        SELECT c.* FROM courses c
        JOIN registrations r ON c.id = r.course_id
        WHERE r.student_id = %s
    """, (session["student_id"],)).fetchall()

    announcements = conn.execute("""
        SELECT * FROM announcements
        ORDER BY created_at DESC
        LIMIT 5
    """).fetchall()

    assignments = conn.execute("""
        SELECT * FROM assignments
        ORDER BY id DESC
        LIMIT 10
    """).fetchall()

    conn.close()

    total_units = sum(row["units"] for row in results)

    total_points = sum(
        row["units"] * row["grade_point"]
        for row in results
    )

    gpa = round(
        total_points / total_units,
        2
    ) if total_units else 0.00

    return render_template(
        "student/dashboard.html",
        student=student,
        results=results,
        courses=courses,
        announcements=announcements,
        assignments=assignments,
        gpa=gpa
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ============================================================
# ADMIN SECURITY
# ============================================================

def admin_required():
    return session.get("admin_logged_in") is True


# ============================================================
# ADMIN LOGIN / DASHBOARD
# ============================================================

@app.route("/admin", methods=["GET", "POST"])
def admin_dashboard():

    # PIN unlock
    if not admin_required():

        if request.method == "POST":
            pin = request.form.get("pin", "")

            if pin == ADMIN_PIN:
                session["admin_logged_in"] = True
                return redirect(url_for("admin_dashboard"))

            flash("Incorrect administrator PIN.", "error")

        return render_template(
            "admin/dashboard.html",
            unlocked=False
        )

    conn = get_db()

    students = conn.execute("""
        SELECT id, matric_no, full_name, email,
               department, level, phone, created_at
        FROM students
        ORDER BY id DESC
    """).fetchall()

    results = conn.execute("""
        SELECT
            results.*,
            students.matric_no,
            students.full_name
        FROM results
        JOIN students ON students.id = results.student_id
        ORDER BY results.id DESC
        LIMIT 50
    """).fetchall()

    announcements = conn.execute("""
        SELECT *
        FROM announcements
        ORDER BY id DESC
    """).fetchall()

    assignments = conn.execute("""
        SELECT *
        FROM assignments
        ORDER BY id DESC
    """).fetchall()

    courses = conn.execute("""
        SELECT *
        FROM courses
        ORDER BY id DESC
    """).fetchall()

    student_count = conn.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    course_count = conn.execute(
        "SELECT COUNT(*) FROM courses"
    ).fetchone()[0]

    result_count = conn.execute(
        "SELECT COUNT(*) FROM results"
    ).fetchone()[0]

    announcement_count = conn.execute(
        "SELECT COUNT(*) FROM announcements"
    ).fetchone()[0]

    assignment_count = conn.execute(
        "SELECT COUNT(*) FROM assignments"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "admin/dashboard.html",
        unlocked=True,
        students=students,
        results=results,
        announcements=announcements,
        assignments=assignments,
        courses=courses,
        student_count=student_count,
        course_count=course_count,
        result_count=result_count,
        announcement_count=announcement_count,
        assignment_count=assignment_count
    )


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("index"))


# ============================================================
# ADMIN - VIEW INDIVIDUAL STUDENT
# ============================================================

@app.route("/admin/student/<int:student_id>")
def admin_student(student_id):

    if not admin_required():
        return redirect(url_for("admin_dashboard"))

    conn = get_db()

    student = conn.execute("""
        SELECT id, matric_no, full_name, email,
               department, level, phone, created_at
        FROM students
        WHERE id = %s
    """, (student_id,)).fetchone()

    if not student:
        conn.close()
        flash("Student account not found.", "error")
        return redirect(url_for("admin_dashboard"))

    results = conn.execute("""
        SELECT *
        FROM results
        WHERE student_id = %s
        ORDER BY id DESC
    """, (student_id,)).fetchall()

    courses = conn.execute("""
        SELECT c.*, r.session
        FROM courses c
        JOIN registrations r ON c.id = r.course_id
        WHERE r.student_id = %s
        ORDER BY c.id DESC
    """, (student_id,)).fetchall()

    conn.close()

    total_units = sum(row["units"] for row in results)

    total_points = sum(
        row["units"] * row["grade_point"]
        for row in results
    )

    gpa = round(
        total_points / total_units,
        2
    ) if total_units else 0.00

    return render_template(
        "admin/student.html",
        student=student,
        results=results,
        courses=courses,
        gpa=gpa
    )


# ============================================================
# ADMIN - ADD RESULT
# ============================================================

@app.route("/admin/result/add", methods=["POST"])
def admin_add_result():

    if not admin_required():
        return redirect(url_for("admin_dashboard"))

    try:
        student_id = int(request.form["student_id"])
        course_code = request.form["course_code"].strip().upper()
        course_title = request.form["course_title"].strip()
        units = int(request.form["units"])
        score = int(request.form["score"])
        semester = request.form["semester"].strip()

        if score < 0 or score > 100:
            raise ValueError

        if units < 1 or units > 10:
            raise ValueError

    except (ValueError, KeyError):
        flash("Invalid result information.", "error")
        return redirect(url_for("admin_dashboard") + "#results")

    if score >= 70:
        grade = "A"
        grade_point = 5.0
    elif score >= 60:
        grade = "B"
        grade_point = 4.0
    elif score >= 50:
        grade = "C"
        grade_point = 3.0
    elif score >= 45:
        grade = "D"
        grade_point = 2.0
    elif score >= 40:
        grade = "E"
        grade_point = 1.0
    else:
        grade = "F"
        grade_point = 0.0

    conn = get_db()

    student = conn.execute(
        "SELECT id FROM students WHERE id = %s",
        (student_id,)
    ).fetchone()

    if not student:
        conn.close()
        flash("Student not found.", "error")
        return redirect(url_for("admin_dashboard") + "#results")

    conn.execute("""
        INSERT INTO results
        (student_id, course_code, course_title,
         units, score, grade, grade_point, semester)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        student_id,
        course_code,
        course_title,
        units,
        score,
        grade,
        grade_point,
        semester
    ))

    conn.commit()
    conn.close()

    flash(
        f"Result posted successfully. Score {score} = Grade {grade}.",
        "success"
    )

    return redirect(url_for("admin_dashboard") + "#results")


# ============================================================
# ADMIN - DELETE RESULT
# ============================================================

@app.route("/admin/result/delete/<int:result_id>", methods=["POST"])
def admin_delete_result(result_id):

    if not admin_required():
        return redirect(url_for("admin_dashboard"))

    conn = get_db()

    conn.execute(
        "DELETE FROM results WHERE id = %s",
        (result_id,)
    )

    conn.commit()
    conn.close()

    flash("Result deleted successfully.", "success")

    return redirect(url_for("admin_dashboard") + "#results")


# ============================================================
# ADMIN - ADD ANNOUNCEMENT
# ============================================================

@app.route("/admin/announcement/add", methods=["POST"])
def admin_add_announcement():

    if not admin_required():
        return redirect(url_for("admin_dashboard"))

    title = request.form.get("title", "").strip()
    message = request.form.get("message", "").strip()

    if not title or not message:
        flash("Announcement title and message are required.", "error")
        return redirect(url_for("admin_dashboard") + "#announcements")

    conn = get_db()

    conn.execute("""
        INSERT INTO announcements(title, message)
        VALUES (%s, %s)
    """, (title, message))

    conn.commit()
    conn.close()

    flash("Public announcement published.", "success")

    return redirect(url_for("admin_dashboard") + "#announcements")


# ============================================================
# ADMIN - DELETE ANNOUNCEMENT
# ============================================================

@app.route("/admin/announcement/delete/<int:announcement_id>", methods=["POST"])
def admin_delete_announcement(announcement_id):

    if not admin_required():
        return redirect(url_for("admin_dashboard"))

    conn = get_db()

    conn.execute(
        "DELETE FROM announcements WHERE id = %s",
        (announcement_id,)
    )

    conn.commit()
    conn.close()

    flash("Announcement deleted.", "success")

    return redirect(url_for("admin_dashboard") + "#announcements")


# ============================================================
# ADMIN - ADD ASSIGNMENT
# ============================================================

@app.route("/admin/assignment/add", methods=["POST"])
def admin_add_assignment():

    if not admin_required():
        return redirect(url_for("admin_dashboard"))

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    course_code = request.form.get("course_code", "").strip().upper()
    due_date = request.form.get("due_date", "").strip()

    if not title or not description:
        flash("Assignment title and description are required.", "error")
        return redirect(url_for("admin_dashboard") + "#assignments")

    conn = get_db()

    conn.execute("""
        INSERT INTO assignments
        (title, description, course_code, due_date)
        VALUES (%s, %s, %s, %s)
    """, (
        title,
        description,
        course_code,
        due_date
    ))

    conn.commit()
    conn.close()

    flash("Assignment published successfully.", "success")

    return redirect(url_for("admin_dashboard") + "#assignments")


# ============================================================
# ADMIN - DELETE ASSIGNMENT
# ============================================================

@app.route("/admin/assignment/delete/<int:assignment_id>", methods=["POST"])
def admin_delete_assignment(assignment_id):

    if not admin_required():
        return redirect(url_for("admin_dashboard"))

    conn = get_db()

    conn.execute(
        "DELETE FROM assignments WHERE id = %s",
        (assignment_id,)
    )

    conn.commit()
    conn.close()

    flash("Assignment deleted.", "success")

    return redirect(url_for("admin_dashboard") + "#assignments")


# ============================================================
# ADMIN - ADD COURSE
# ============================================================

@app.route("/admin/course/add", methods=["POST"])
def admin_add_course():

    if not admin_required():
        return redirect(url_for("admin_dashboard"))

    code = request.form.get("code", "").strip().upper()
    title = request.form.get("title", "").strip()
    semester = request.form.get("semester", "").strip()

    try:
        units = int(request.form.get("units", "0"))
    except ValueError:
        units = 0

    if not code or not title or units < 1 or not semester:
        flash("Complete all course information.", "error")
        return redirect(url_for("admin_dashboard") + "#courses")

    conn = get_db()

    conn.execute("""
        INSERT INTO courses(code, title, units, semester)
        VALUES (%s, %s, %s, %s)
    """, (
        code,
        title,
        units,
        semester
    ))

    conn.commit()
    conn.close()

    flash("Course added successfully.", "success")

    return redirect(url_for("admin_dashboard") + "#courses")


# ============================================================
# ADMIN - DELETE COURSE
# ============================================================

@app.route("/admin/course/delete/<int:course_id>", methods=["POST"])
def admin_delete_course(course_id):

    if not admin_required():
        return redirect(url_for("admin_dashboard"))

    conn = get_db()

    conn.execute(
        "DELETE FROM courses WHERE id = %s",
        (course_id,)
    )

    conn.commit()
    conn.close()

    flash("Course deleted.", "success")

    return redirect(url_for("admin_dashboard") + "#courses")


# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":
    init_db()
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
else:
    init_db()

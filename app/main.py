from flask import Flask, render_template, request, redirect, flash, url_for, session
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from . import model

try:
    from sklearn.tree import DecisionTreeClassifier
except ImportError:
    DecisionTreeClassifier = None

try:
    import numpy as np
except ImportError:
    np = None

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

import os
import random


app = Flask(__name__)
app.config["SECRET_KEY"] = "Wfd8do6H7d74vdesbuRLlMFiAeXeJ7r"
# Flask login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message_category = "danger"


class User(UserMixin):
    def __init__(self, id):
        self.id = id

    def is_admin(self):
        return bool(session["User"]["is_admin"])

    def __repr__(self):
        return f"<{self.id}>"


@login_manager.user_loader
def load_user(userid):
    return User(userid)


def get_skill_level(solved):
    """
    Input: number of puzzles solved (0–5)
    Output: Beginner / Intermediate / Advanced
    """
    try:
        X = [[0], [1], [2], [3], [4], [5]]
        y = ["Beginner", "Beginner", "Beginner", "Intermediate", "Intermediate", "Advanced"]
        model = DecisionTreeClassifier()
        model.fit(X, y)
        return model.predict([[solved]])[0]
    except Exception as e:
        # Fallback rule-based logic
        if solved <= 2:
            return "Beginner"
        elif solved <= 4:
            return "Intermediate"
        else:
            return "Advanced"


@app.route("/")
def index():
    if not current_user.is_authenticated:
        return redirect(url_for("login"))

    if session.get("User", {}).get("Username") == "admin":
        return redirect(url_for("admin_dashboard"))

    success, message, student_course_list = model.get_student_course_list(
        current_user.id
    )
    if not success:
        flash(message, "warning")
        return redirect(url_for("index"))
    success, message, teacher_course_list = model.get_teacher_course_list(
        current_user.id
    )
    if not success:
        flash(message, "warning")
        return redirect(url_for("index"))
    return render_template(
        "index.html",
        teacher_course_list=teacher_course_list,
        student_course_list=student_course_list,
    )


@app.route("/course/<int:CourseID>")
@login_required
def course(CourseID):
    success, message, is_teacher = model.is_teacher(current_user.id, CourseID)
    if not success:
        flash(message, "warning")
        return redirect(url_for("index"))
    success, message, course_data = model.get_course(CourseID)
    if not success:
        flash(message, "warning")
        return redirect(url_for("index"))
    if not course_data:
        flash("This course does not exist or you don't have access to it", "warning")
        return redirect(url_for("index"))
    success, message, content_list = model.get_content_list(CourseID)
    if not success:
        flash(message, "warning")
        return redirect(url_for("index"))
    return render_template(
        "course.html",
        is_teacher=is_teacher,
        course_data=course_data,
        content_list=content_list,
    )


@app.route("/login/", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        flash("You are currently logged in", "primary")
        return redirect(url_for("index"))
    if request.method == "POST":
        Username = request.form.get("Username", "")
        Password = request.form.get("Password", "")
        success, message, raw_user = model.check_login(Username, Password)
        if success:
            login_user(User(raw_user["ID"]))
            session["User"] = raw_user
            success2, message2, is_manager = model.is_manager(current_user.id)
            if success2:
                session["User"]["is_manager"] = is_manager
            else:
                flash(message2, "warning")
                return redirect(url_for("login"))
            # Redirect to appropriate dashboard based on username
            if Username == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("student_dashboard"))
        else:
            flash(message, "warning")
            return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/logout/")
@login_required
def logout():
    logout_user()
    flash("You have logged out successfully", "success")
    return redirect(url_for("login"))


@app.route("/admin-dashboard/")
@login_required
def admin_dashboard():
    success_students, message_students, total_students = model.get_total_students()
    success_courses, message_courses, total_courses = model.get_total_courses()
    
    # Use 0 as fallback if queries fail
    if not success_students:
        total_students = 0
    if not success_courses:
        total_courses = 0
    
    return render_template(
        "admin_dashboard.html",
        total_students=total_students,
        total_courses=total_courses
    )


@app.route("/admin-puzzles/")
@login_required
def admin_puzzles():
    if session.get("User", {}).get("Username") != "admin":
        return redirect(url_for("login"))
    return render_template("puzzles.html")


@app.route("/admin-analytics/")
@login_required
def admin_analytics():
    if session.get("User", {}).get("Username") != "admin":
        return redirect(url_for("login"))
    
    # Fetch real student data from database
    success, message, user_list = model.get_user_list()
    students = []
    if success and user_list:
        for user in user_list:
            name = f"{user.get('First Name', 'Unknown')} {user.get('Last Name', 'User')}"
            solved = user.get('solved', None)
            completion = user.get('completion', None)
            if solved is None:
                solved = 0
            if completion is None:
                completion = random.randint(0, 100)
            students.append({
                "name": name.strip(),
                "solved": solved,
                "completion": completion
            })
    else:
        # Fallback dummy data
        students = [
            {"name": "Rahul", "solved": 2, "completion": 75},
            {"name": "Priya", "solved": 4, "completion": 90},
            {"name": "Aman", "solved": 5, "completion": 100}
        ]

    # Ensure there is at least one data point
    if not students:
        students = [{"name": "No Data", "solved": 0, "completion": 0, "accuracy": 0, "skill": "Beginner"}]

    # Calculate metrics for each student safely
    for student in students:
        solved = student.get("solved", 0) or 0
        completion = student.get("completion", 0) or 0
        if solved < 0:
            solved = 0
        if solved > 5:
            solved = 5
        student["solved"] = solved
        student["completion"] = completion
        student["accuracy"] = (solved / 5) * 100
        student["skill"] = get_skill_level(solved)

    # Ensure there is at least one data point before plotting
    if not students:
        students = [{"name": "No Data", "solved": 0, "completion": 0, "accuracy": 0, "skill": "Beginner"}]

    # Generate graphs
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        static_path = os.path.join(base_dir, 'static')
        if not os.path.exists(static_path):
            os.makedirs(static_path)

        accuracy_chart_path = os.path.join(static_path, 'accuracy_chart.png')
        skill_chart_path = os.path.join(static_path, 'skill_chart.png')

        # Prepare safe plotting data
        names = [student.get("name", "Unknown") or "Unknown" for student in students]
        accuracies = [student.get("accuracy", 0) or 0 for student in students]
        skills = [student.get("skill", "Beginner") or "Beginner" for student in students]

        if len(names) == 0 or len(accuracies) == 0:
            students = [{"name": "No Data", "accuracy": 0, "skill": "Beginner"}]
            names = ["No Data"]
            accuracies = [0]
            skills = ["Beginner"]

        # Bar chart for accuracy
        plt.clf()
        plt.figure(figsize=(8, 4))
        plt.bar(names, accuracies, color='skyblue')
        plt.title('Student Accuracy')
        plt.xlabel('Students')
        plt.ylabel('Accuracy (%)')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(accuracy_chart_path)
        plt.close()

        # Pie chart for skill levels
        skill_counts = {}
        for skill in skills:
            skill_counts[skill] = skill_counts.get(skill, 0) + 1
        labels = list(skill_counts.keys())
        sizes = list(skill_counts.values())
        if not labels or not sizes:
            labels = ["Beginner"]
            sizes = [1]
        colors = ['lightcoral', 'lightskyblue', 'lightgreen']
        plt.clf()
        plt.figure(figsize=(6, 6))
        plt.pie(sizes, labels=labels, colors=colors[:len(labels)], autopct='%1.1f%%', startangle=140)
        plt.title('Skill Level Distribution')
        plt.axis('equal')
        plt.tight_layout()
        plt.savefig(skill_chart_path)
        plt.close()

        accuracy_chart = 'accuracy_chart.png'
        skill_chart = 'skill_chart.png'
    except Exception as e:
        print("Chart error:", e)
        accuracy_chart = None
        skill_chart = None
    
    cache_bust = random.randint(1, 999999)
    return render_template(
        "admin_analytics.html",
        students=students,
        accuracy_chart=accuracy_chart,
        skill_chart=skill_chart,
        cache_bust=cache_bust
    )


@app.route("/student-dashboard/")
@login_required
def student_dashboard():
    return render_template("student_dashboard.html")


@app.route("/student-puzzles/")
@login_required
def student_puzzles():
    return render_template("student_puzzles.html")


@app.route("/register/", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        Username = request.form.get("Username", "")
        Password = request.form.get("Password", "")
        LastName = request.form.get("LastName", "")
        FirstName = request.form.get("FirstName", "")
        PhoneNumber = request.form.get("PhoneNumber", "")
        Email = request.form.get("Email", "")
        Faculty = request.form.get("Faculty", "")
        Institution = request.form.get("Institution", "")
        Address = request.form.get("Address", "")
        success, message = model.create_user(
            Username=Username,
            Password=Password,
            LastName=LastName,
            FirstName=FirstName,
            PhoneNumber=PhoneNumber,
            Email=Email,
            Faculty=Faculty,
            Institution=Institution,
            Address=Address,
        )
        if success:
            flash(
                "Your account has been created successfully, you can login now.",
                "success",
            )
            return redirect(url_for("login"))
        flash(message, "warning")
    return render_template("register.html")


@app.route("/users/")
@login_required
def user_list():
    success, message, user_list = model.get_user_list()
    if not success:
        flash(message, "warning")
        return redirect(url_for("index"))
    return render_template("user_list.html", user_list=user_list)


@app.route("/profile/<int:ID>/", methods=["GET", "POST"])
@login_required
def profile(ID):
    if request.method == "POST":
        Username = request.form.get("Username", "")
        LastName = request.form.get("LastName", "")
        FirstName = request.form.get("FirstName", "")
        PhoneNumber = request.form.get("PhoneNumber", "")
        Email = request.form.get("Email", "")
        Faculty = request.form.get("Faculty", "")
        Institution = request.form.get("Institution", "")
        Address = request.form.get("Address", "")
        success, message = model.edit_user_profile(
            ID=ID,
            Username=Username,
            LastName=LastName,
            FirstName=FirstName,
            PhoneNumber=PhoneNumber,
            Email=Email,
            Faculty=Faculty,
            Institution=Institution,
            Address=Address,
        )
        if success:
            flash(
                "Profile updated successfully.",
                "success",
            )
            return redirect(url_for("profile", ID=ID))
        flash(message, "warning")
    success, message, raw_user = model.get_user_profile(ID)
    if not success:
        flash(
            "No such user exists, or you don't have access to it's profile.", "warning"
        )
        return redirect(url_for("index"))
    success, message, course_list = model.get_all_course_list()
    if not success:
        flash(message, "warning")
        return redirect(url_for("index"))
    success, message, student_course_list = model.get_student_course_list(ID)
    if not success:
        flash(message, "warning")
        return redirect(url_for("index"))
    success, message, cluster_list = model.get_cluster_list(
        current_user.id, current_user.is_admin()
    )
    if not success:
        flash(message, "warning")
        return redirect(url_for("index"))
    success, message, user_cluster_list = model.get_cluster_list(ID)
    if not success:
        flash(message, "warning")
        return redirect(url_for("index"))
    return render_template(
        "profile.html",
        user=raw_user,
        course_list=course_list,
        student_course_list=student_course_list,
        cluster_list=cluster_list,
        user_cluster_list=user_cluster_list,
    )


@app.route("/clusters/", methods=["GET", "POST"])
@login_required
def cluster_list():
    if request.method == "POST":
        Name = request.form.get("Name", "DEFAULT")
        success, message = model.create_cluster(Name)
        if success:
            flash(message, "success")
            return redirect(url_for("cluster_list"))
        flash(message, "warning")
        return redirect(url_for("cluster_list"))
    success, message, cluster_list = model.get_cluster_list(
        current_user.id, current_user.is_admin()
    )
    if not success:
        flash(message, "warning")
        return redirect(url_for("cluster_list"))
    return render_template("cluster.html", cluster_list=cluster_list)


@app.route("/make_manager/<int:ManagerID>/", methods=["POST"])
@login_required
def make_manager(ManagerID):
    ClusterID = request.form.get("ClusterID", "")
    success, message = model.create_manager_cluster(ManagerID, ClusterID)
    if success:
        flash(message, "success")
    else:
        flash(message, "warning")
    return redirect(url_for("profile", ID=ManagerID))


@app.route("/courses/", methods=["GET", "POST"])
@login_required
def course_list():
    if request.method == "POST":
        Name = request.form.get("Name", "DEFAULT")
        ClusterID = request.form.get("ClusterID", "DEFAULT")
        TeacherID = request.form.get("TeacherID", "DEFAULT")
        success, message = model.create_course(Name, TeacherID, ClusterID)
        if success:
            flash(message, "success")
            return redirect(url_for("course_list"))
        flash(message, "warning")
        return redirect(url_for("course_list"))
    success, message, course_list = model.get_all_course_list()
    if not success:
        flash(message, "warning")
        return redirect(url_for("course_list"))
    success, message, cluster_list = model.get_cluster_list(
        current_user.id, current_user.is_admin()
    )
    if not success:
        flash(message, "warning")
        return redirect(url_for("index"))
    success, message, user_list = model.get_user_list()
    if not success:
        flash(message, "warning")
        return redirect(url_for("index"))
    return render_template(
        "course_list.html",
        course_list=course_list,
        cluster_list=cluster_list,
        user_list=user_list,
    )


@app.route("/participate/<int:StudentID>", methods=["POST"])
@login_required
def participate(StudentID):
    CourseID = request.form.get("CourseID", "")
    success, message = model.create_student_course(StudentID, CourseID)
    if success:
        flash(message, "success")
    else:
        flash(message, "warning")
    return redirect(url_for("profile", ID=StudentID))


@app.route("/students/<int:CourseID>/")
@login_required
def student_list(CourseID):
    success, message, student_list = model.get_course_student_list(CourseID)
    if not success:
        flash(message, "warning")
        return redirect(url_for("course", CourseID=CourseID))
    return render_template("course_student.html", student_list=student_list)


@app.route("/newcontent/<int:CourseID>/", methods=["GET", "POST"])
@login_required
def new_content(CourseID):
    if request.method == "POST":
        Title = request.form.get("Title", "")
        TextContent = request.form.get("TextContent", "")
        success, message = model.create_content(CourseID, Title, TextContent)
        if success:
            flash("Content created successfully.", "success")
            return redirect(url_for("course", CourseID=CourseID))
        flash(message, "warning")
        return redirect(url_for("course", CourseID=CourseID))
    return render_template("new_content.html", CourseID=CourseID)

import os

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
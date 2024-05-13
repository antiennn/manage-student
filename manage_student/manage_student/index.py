from flask import render_template, redirect, url_for, request, jsonify
from flask_login import current_user, login_required, logout_user, login_user
from manage_student import app, login
from manage_student.dao import regulation, notification
from manage_student.decorators import role_only
from manage_student.form import *
from dao import auth, student, group_class, teacher, assignments
from manage_student.api import *
from manage_student.model import UserRole
from manage_student import admin

from manage_student.api.teach import *
from manage_student.api.student_class import *


@login.user_loader
def user_load(user_id):
    return auth.load_user(user_id)


@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.user_role == UserRole.ADMIN:
            return redirect("/admin")
        return redirect(url_for('home'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    mse = ""
    form = LoginForm()
    if request.method == "POST" and form.SubmitFieldLogin():
        username = form.username.data
        password = form.password.data
        user = auth.auth_user(username=username, password=password)
        if user:
            login_user(user)
            return redirect(url_for("index"))
        mse = "Tài khoản hoặc mật khẩu không đúng"
    return render_template('login.html', form=form, mse=mse)


@app.route("/log_out")
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route('/home')
@login_required
@role_only([UserRole.STAFF, UserRole.TEACHER])
def home():
    profile = auth.get_info_by_id(current_user.id)
    notifications = notification.load_all_notifications()
    return render_template("index.html", profile=profile, notifications=notifications)


@app.route('/teacher/assignment', methods=["GET", "POST"])
@login_required
@role_only([UserRole.STAFF])
def teacher_assignment():
    classname = ''
    if request.method.__eq__("POST"):
        classname = request.form.get("class-list")
        grade_value = request.form.get("grade-list")
        return redirect('/teacher/assignment/' + grade_value + '/' + classname)
    return render_template("teacher_assignment.html", classname=classname)


@app.route('/teacher/assignment/<grade>/<string:classname>', methods=["GET", "POST", "DELETE"])
@login_required
@role_only([UserRole.STAFF])
def teacher_assignment_class(grade, classname):
    subject_list = assignments.load_subject_of_class(grade='K' + grade)
    # teacher_list = assignments.load_all_teacher_subject()
    class_id = group_class.get_info_class_by_name(grade=grade, count=classname[-1]).id
    if request.method.__eq__("GET"):
        plan = assignments.load_assignments_of_class(class_id=class_id)
        return render_template("teacher_assignment.html", grade=grade, classname=classname, subjects=subject_list,
                               get_teachers=assignments.load_all_teacher_subject, plan=plan)
    elif request.method.__eq__("POST") and request.form.get("type").__eq__("save"):
        for s in subject_list:
            teacher_id = request.form.get("teacher-assigned-{id}".format(id=s.id))
            total_seme = request.form.get("total-seme-{id}".format(id=s.id))
            seme1 = request.form.get("seme1-{id}".format(id=s.id))
            seme2 = request.form.get("seme2-{id}".format(id=s.id))
            semester_id = None
            if total_seme:
                semester_id = [1, 2]
            elif seme1:
                semester_id = 1
            elif seme2:
                semester_id = 2
            assignments.save_subject_assignment(
                teacher_id=teacher_id,
                class_id=class_id,
                semester_id=semester_id,
                subject_id=s.id
            )
        return redirect("/teacher/assignment/{grade}/{classname}".format(grade=str(grade), classname=classname))
    elif request.method.__eq__("POST") and request.form.get("type").__eq__("delete"):
        assignments.delete_assignments(class_id)
        return render_template("teacher_assignment.html", grade=grade, classname=classname, subjects=subject_list,
                               get_teachers=assignments.load_all_teacher_subject)
    return render_template("teacher_assignment.html", grade=grade, classname=classname, subjects=subject_list,
                           get_teachers=assignments.load_all_teacher_subject)

@app.route('/api/class/', methods=['GET'])
@role_only([UserRole.STAFF])
def get_class():
    q = request.args.get('q')
    res = {}
    if q:
        class_list = assignments.load_class_by_grade(q)
        json_class_list = [
            {
                "grade": c.grade.value,
                "count": c.count,
            }
            for c in class_list
        ]
        return jsonify({"class_list": json_class_list})
    return jsonify({})


@app.route('/class/create', methods=['GET', 'POST'])
def create_class():
    form_create_class = CreateClass()
    form_create_class.teacher.choices = [(temp_teacher.id, temp_teacher.user.profile.name) for temp_teacher in
                                         teacher.get_teacher_not_presidential()]
    if request.method == "POST" and form_create_class.validate_on_submit():
        try:
            temp_class = group_class.create_class(form_create_class)
        except Exception as e:
            redirect("/home")
        redirect(url_for("index"))
    return render_template("create_class.html", form_create_class=form_create_class, list_class=group_class.get_class(),
                           student_no_class=student.student_no_class())


@app.route('/class/edit')
def class_edit():
    classes = group_class.get_class()
    return render_template("list_class.html", classes=classes)


@app.route('/student/register', methods=['GET', 'POST'])
def register():
    form_student = AdmisionStudent()

    if request.method == "POST" and form_student.submit():
        try:
            s = student.create_student(form_student)
        except Exception as e:
            print(e)
            return render_template("register_student.html", form_student=form_student)
        if s:
            return redirect(url_for("index"))
    return render_template("register_student.html", form_student=form_student)


@app.route('/<int:grade>/<int:count>/info')
def info(grade, count):
    class_info = group_class.get_info_class_by_name(grade, count)
    student_no_class = student.student_no_class("K" + str(grade))
    return render_template("class_info.html", class_info=class_info, student_no_class=student_no_class)


@app.route("/regulations")
def view_regulations():
    regulations = regulation.get_regulations()
    return render_template('view_regulations.html', regulations=regulations)


@app.route("/grade")
@login_required
def input_grade():
    profile = auth.get_info_by_id(current_user.id)
    return render_template("input_score.html", teacher_class=teacher.get_class_of_teacher(profile.id),
                           check_deadline_score=teacher.check_deadline_score)


@app.route("/grade/input/<class_id>/score")
@login_required
def input_grade_subject(class_id):
    class_params = int(class_id.split('=')[-1])
    class_obj, semester, subject, profile_students, teacher_planing = teacher.get_teaching_plan_details(class_params)
    return render_template("input_score_subject.html", class_obj=class_obj, semester=semester, subject=subject,
                           profile_students=profile_students, teacher_planing=teacher_planing)


@app.route("/view_score")
def view_grade():
    return render_template("view_score.html")


if __name__ == "__main__":
    with app.app_context():
        app.run(debug=True)

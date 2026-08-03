import csv
import io
import os
import random
import string
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import (
    Flask,
    Response,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
MATERIALS_UPLOAD_DIR = BASE_DIR / "uploads" / "materials"
HONORS_UPLOAD_DIR = BASE_DIR / "uploads" / "honors"
DATABASE_PATH = BASE_DIR / "instance" / "robot_recruit.db"
ALLOWED_EXTENSIONS = {
    "pdf",
    "doc",
    "docx",
    "ppt",
    "pptx",
    "xls",
    "xlsx",
    "zip",
    "rar",
    "7z",
    "txt",
    "md",
    "py",
    "jpg",
    "jpeg",
    "png",
}
HONOR_LEVEL_LABELS = {
    "provincial": "省奖",
    "national": "国奖",
}
CAPTCHA_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CHINA_TZ = timezone(timedelta(hours=8))

db = SQLAlchemy()


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    student_id = db.Column(db.String(30), unique=True)
    full_name = db.Column(db.String(50), nullable=False)
    class_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    qq = db.Column(db.String(20))
    computer_model = db.Column(db.String(100))
    gpu_model = db.Column(db.String(100))
    cpu_model = db.Column(db.String(100))
    memory_size = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    materials = db.relationship("Material", backref="creator", lazy=True)
    honors = db.relationship("Honor", backref="creator", lazy=True)
    study_sessions = db.relationship("StudySession", backref="student", lazy=True)
    created_exams = db.relationship("Exam", backref="creator", lazy=True)
    exam_submissions = db.relationship("ExamSubmission", backref="student", lazy=True)

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text)
    external_link = db.Column(db.String(500))
    stored_filename = db.Column(db.String(255))
    original_filename = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class Honor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    level = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text)
    stored_filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class StudySession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ended_at = db.Column(db.DateTime)
    duration_seconds = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(20), default="active", nullable=False)


class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    duration_minutes = db.Column(db.Integer, default=30, nullable=False)
    start_at = db.Column(db.DateTime)
    end_at = db.Column(db.DateTime)
    is_published = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    questions = db.relationship(
        "ExamQuestion",
        backref="exam",
        lazy=True,
        cascade="all, delete-orphan",
    )
    submissions = db.relationship(
        "ExamSubmission",
        backref="exam",
        lazy=True,
        cascade="all, delete-orphan",
    )


class ExamQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exam.id"), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(255), nullable=False)
    option_b = db.Column(db.String(255), nullable=False)
    option_c = db.Column(db.String(255), nullable=False)
    option_d = db.Column(db.String(255), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)


class ExamSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exam.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    score = db.Column(db.Integer, default=0, nullable=False)
    total_questions = db.Column(db.Integer, default=0, nullable=False)
    duration_seconds = db.Column(db.Integer, default=0, nullable=False)

    answers = db.relationship(
        "ExamAnswer",
        backref="submission",
        lazy=True,
        cascade="all, delete-orphan",
    )


class ExamAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("exam_submission.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("exam_question.id"), nullable=False)
    selected_option = db.Column(db.String(1), nullable=False)
    is_correct = db.Column(db.Boolean, default=False, nullable=False)

    question = db.relationship("ExamQuestion", lazy=True)


def create_app() -> Flask:
    load_env_file(BASE_DIR / ".env")

    app = Flask(__name__)
    database_url = os.environ.get("DATABASE_URL", "").strip()
    database_path = os.environ.get("DATABASE_PATH", "").strip()
    upload_folder = os.environ.get("UPLOAD_FOLDER", "").strip()
    honors_upload_folder = os.environ.get("HONORS_UPLOAD_FOLDER", "").strip()

    if not database_url:
        resolved_database_path = Path(database_path) if database_path else DATABASE_PATH
        resolved_database_path.parent.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite:///{resolved_database_path}"

    resolved_upload_dir = Path(upload_folder) if upload_folder else MATERIALS_UPLOAD_DIR
    if honors_upload_folder:
        resolved_honors_upload_dir = Path(honors_upload_folder)
    elif upload_folder:
        resolved_honors_upload_dir = resolved_upload_dir.parent / "honors"
    else:
        resolved_honors_upload_dir = HONORS_UPLOAD_DIR

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "robot-site-dev-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = str(resolved_upload_dir)
    app.config["HONORS_UPLOAD_FOLDER"] = str(resolved_honors_upload_dir)
    app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

    db.init_app(app)

    with app.app_context():
        Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
        Path(app.config["HONORS_UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
        db.create_all()
        ensure_default_admin()

    register_hooks(app)
    register_routes(app)
    return app


def ensure_default_admin() -> None:
    if User.query.filter_by(role="admin").first():
        return

    username = os.environ.get("DEFAULT_ADMIN_USERNAME", "admin")
    password = os.environ.get("DEFAULT_ADMIN_PASSWORD", "Admin123456")
    full_name = os.environ.get("DEFAULT_ADMIN_NAME", "Robot组管理员")

    admin = User(username=username, full_name=full_name, role="admin")
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    print(
        f"[robot-site] Created default admin account: {username} / {password}. "
        "Please change it after first login."
    )


def register_hooks(app: Flask) -> None:
    @app.before_request
    def load_current_user() -> None:
        user_id = session.get("user_id")
        g.current_user = db.session.get(User, user_id) if user_id else None
        g.active_study_session = None
        if g.current_user:
            g.active_study_session = (
                StudySession.query.filter_by(user_id=g.current_user.id, status="active")
                .order_by(StudySession.started_at.desc())
                .first()
            )

    @app.context_processor
    def inject_user():
        return {
            "current_user": g.get("current_user"),
            "active_study_session": g.get("active_study_session"),
            "now": datetime.utcnow(),
        }

    @app.template_filter("duration_label")
    def duration_label_filter(seconds: int) -> str:
        return format_duration(seconds)

    @app.template_filter("datetime_cn")
    def datetime_cn_filter(value, fmt="%Y-%m-%d %H:%M") -> str:
        if not value:
            return ""
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(CHINA_TZ).strftime(fmt)

    @app.template_filter("utc_iso")
    def utc_iso_filter(value) -> str:
        if not value:
            return ""
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.current_user is None:
            flash("请先登录后再访问该页面。", "warning")
            return redirect(url_for("index"))
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped_view(*args, **kwargs):
        if not g.current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped_view


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_required_fields(form, field_names):
    return [label for key, label in field_names.items() if not form.get(key, "").strip()]


def generate_captcha_text(length: int = 4) -> str:
    return "".join(random.choice(CAPTCHA_ALPHABET) for _ in range(length))


def build_captcha_svg(code: str) -> str:
    random.seed(code)
    pieces = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="56" viewBox="0 0 160 56">',
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="#0d4d8f"/><stop offset="100%" stop-color="#1cc9d5"/>'
        "</linearGradient></defs>",
        '<rect width="160" height="56" rx="14" fill="#f4f9ff"/>',
        '<rect x="1.5" y="1.5" width="157" height="53" rx="12.5" fill="none" stroke="#d3e1f2"/>',
    ]
    for _ in range(7):
        x1 = random.randint(0, 160)
        y1 = random.randint(0, 56)
        x2 = random.randint(0, 160)
        y2 = random.randint(0, 56)
        pieces.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            'stroke="rgba(31, 111, 235, 0.18)" stroke-width="1.2" />'
        )
    for index, char in enumerate(code):
        x = 24 + index * 32
        y = 36 + random.randint(-5, 5)
        rotate = random.randint(-12, 12)
        pieces.append(
            f'<text x="{x}" y="{y}" font-size="28" font-family="Arial, sans-serif" '
            f'font-weight="700" fill="url(#g)" transform="rotate({rotate} {x} {y})">{char}</text>'
        )
    pieces.append("</svg>")
    return "".join(pieces)


def parse_datetime_local(raw_value: str):
    value = (raw_value or "").strip()
    if not value:
        return None
    naive_local = datetime.fromisoformat(value)
    return naive_local.replace(tzinfo=CHINA_TZ).astimezone(timezone.utc).replace(tzinfo=None)


def format_duration(total_seconds: int) -> str:
    seconds = max(0, int(total_seconds or 0))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours and minutes:
        return f"{hours}小时{minutes}分钟"
    if hours:
        return f"{hours}小时"
    if minutes:
        return f"{minutes}分钟"
    return "不足1分钟"


def calculate_session_seconds(study_session: StudySession, reference_time=None) -> int:
    now = reference_time or datetime.utcnow()
    if study_session.status == "completed" and study_session.duration_seconds:
        return study_session.duration_seconds
    if study_session.ended_at:
        return max(0, int((study_session.ended_at - study_session.started_at).total_seconds()))
    return max(0, int((now - study_session.started_at).total_seconds()))


def get_total_study_seconds(user_id: int) -> int:
    sessions = StudySession.query.filter_by(user_id=user_id).all()
    return sum(calculate_session_seconds(item) for item in sessions)


def get_latest_exam_score(user_id: int):
    submission = (
        ExamSubmission.query.filter_by(user_id=user_id)
        .order_by(ExamSubmission.submitted_at.desc())
        .first()
    )
    if submission is None:
        return None
    return f"{submission.score}/{submission.total_questions}"


def is_exam_available(exam: Exam) -> bool:
    now = datetime.utcnow()
    if not exam.is_published:
        return False
    if exam.start_at and exam.start_at > now:
        return False
    if exam.end_at and exam.end_at < now:
        return False
    return True


def get_exam_submission_for_user(exam_id: int, user_id: int):
    return ExamSubmission.query.filter_by(exam_id=exam_id, user_id=user_id).first()


def get_honors_by_level(level: str, limit=None):
    query = Honor.query.filter_by(level=level).order_by(Honor.created_at.desc())
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def parse_exam_questions(raw_text: str):
    normalized = (raw_text or "").replace("\r\n", "\n").strip()
    blocks = [block.strip() for block in normalized.split("\n\n") if block.strip()]
    if not blocks:
        raise ValueError("请至少填写一道题目。")

    questions = []
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        prompt = ""
        answer = ""
        options = {}
        for line in lines:
            normalized_line = line.replace("：", ":")
            if normalized_line.startswith("题目:") or normalized_line.lower().startswith("question:"):
                prompt = normalized_line.split(":", 1)[-1]
            elif line.startswith(("A.", "B.", "C.", "D.")):
                options[line[0]] = line[2:].strip()
            elif line.startswith(("A：", "B：", "C：", "D：")):
                options[line[0]] = line[2:].strip()
            elif normalized_line.startswith("答案:") or normalized_line.lower().startswith("answer:"):
                answer = normalized_line.split(":", 1)[-1]
        if not prompt:
            raise ValueError("每道题都需要以“题目：”开头。")
        if set(options.keys()) != {"A", "B", "C", "D"}:
            raise ValueError("每道题都必须包含 A、B、C、D 四个选项。")
        answer = answer.strip().upper()
        if answer not in {"A", "B", "C", "D"}:
            raise ValueError("每道题都需要填写正确答案，格式如“答案：A”。")
        questions.append(
            {
                "prompt": prompt.strip(),
                "option_a": options["A"],
                "option_b": options["B"],
                "option_c": options["C"],
                "option_d": options["D"],
                "correct_option": answer,
            }
        )
    return questions


def build_student_rows():
    students = User.query.filter_by(role="student").order_by(User.created_at.desc()).all()
    rows = []
    for student in students:
        total_seconds = get_total_study_seconds(student.id)
        rows.append(
            {
                "student": student,
                "total_seconds": total_seconds,
                "total_study": format_duration(total_seconds),
                "exam_count": ExamSubmission.query.filter_by(user_id=student.id).count(),
                "latest_score": get_latest_exam_score(student.id) or "暂无",
            }
        )
    return rows


def delete_user_account(user: User) -> None:
    for submission in ExamSubmission.query.filter_by(user_id=user.id).all():
        db.session.delete(submission)
    for study_session in StudySession.query.filter_by(user_id=user.id).all():
        db.session.delete(study_session)
    db.session.delete(user)


def render_auth_page(mode="login", status_code=200):
    return render_template("index.html", mode=mode), status_code


def register_routes(app: Flask) -> None:
    @app.route("/")
    def index():
        if g.current_user:
            return redirect(url_for("home"))
        mode = request.args.get("mode", "login").lower()
        if mode not in {"login", "register"}:
            mode = "login"
        return render_auth_page(mode=mode)

    @app.route("/captcha.svg")
    def captcha():
        code = generate_captcha_text()
        session["register_captcha"] = code
        response = Response(build_captcha_svg(code), mimetype="image/svg+xml")
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.current_user:
            return redirect(url_for("home"))

        if request.method == "GET":
            return redirect(url_for("index", mode="login"))

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if not username or not password:
            flash("请输入用户名和密码。", "error")
            return render_auth_page(mode="login", status_code=400)

        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            flash("用户名或密码错误。", "error")
            return render_auth_page(mode="login", status_code=400)

        session.clear()
        session["user_id"] = user.id
        flash("登录成功。", "success")
        return redirect(url_for("home"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if g.current_user:
            return redirect(url_for("home"))

        if request.method == "GET":
            return redirect(url_for("index", mode="register"))

        required_fields = {
            "username": "用户名",
            "password": "密码",
            "confirm_password": "确认密码",
            "student_id": "学号",
            "full_name": "姓名",
            "class_name": "班级",
            "phone": "电话",
            "qq": "QQ",
            "computer_model": "电脑型号",
            "gpu_model": "显卡型号",
            "cpu_model": "CPU 型号",
            "memory_size": "内存容量",
            "captcha_code": "验证码",
        }
        missing = validate_required_fields(request.form, required_fields)
        if missing:
            flash(f"以下字段为必填项：{'、'.join(missing)}", "error")
            return render_auth_page(mode="register", status_code=400)

        username = request.form["username"].strip()
        password = request.form["password"].strip()
        confirm_password = request.form["confirm_password"].strip()
        student_id = request.form["student_id"].strip()
        captcha_code = request.form["captcha_code"].strip().upper()

        if password != confirm_password:
            flash("两次输入的密码不一致。", "error")
            return render_auth_page(mode="register", status_code=400)

        if len(password) < 8:
            flash("密码至少需要 8 位。", "error")
            return render_auth_page(mode="register", status_code=400)

        if captcha_code != session.get("register_captcha", ""):
            flash("验证码错误，请重新输入。", "error")
            return render_auth_page(mode="register", status_code=400)

        if User.query.filter_by(username=username).first():
            flash("用户名已存在，请更换一个。", "error")
            return render_auth_page(mode="register", status_code=400)

        if User.query.filter_by(student_id=student_id).first():
            flash("该学号已经注册过。", "error")
            return render_auth_page(mode="register", status_code=400)

        user = User(
            username=username,
            role="student",
            student_id=student_id,
            full_name=request.form["full_name"].strip(),
            class_name=request.form["class_name"].strip(),
            phone=request.form["phone"].strip(),
            qq=request.form["qq"].strip(),
            computer_model=request.form["computer_model"].strip(),
            gpu_model=request.form["gpu_model"].strip(),
            cpu_model=request.form["cpu_model"].strip(),
            memory_size=request.form["memory_size"].strip(),
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        session.pop("register_captcha", None)

        flash("注册成功，请登录。", "success")
        return redirect(url_for("index", mode="login"))

    @app.route("/logout")
    def logout():
        session.clear()
        flash("你已退出登录。", "success")
        return redirect(url_for("index"))

    @app.route("/home")
    @login_required
    def home():
        recent_materials = Material.query.order_by(Material.created_at.desc()).limit(6).all()
        exams = Exam.query.order_by(Exam.created_at.desc()).all()
        provincial_honors = get_honors_by_level("provincial", limit=6)
        national_honors = get_honors_by_level("national", limit=6)
        honors_count = Honor.query.count()

        if g.current_user.is_admin:
            student_rows = build_student_rows()
            student_rows_sorted = sorted(student_rows, key=lambda item: item["total_seconds"], reverse=True)
            recent_submissions = (
                ExamSubmission.query.order_by(ExamSubmission.submitted_at.desc()).limit(8).all()
            )
            overview = {
                "students_count": len(student_rows),
                "materials_count": Material.query.count(),
                "honors_count": honors_count,
                "exams_count": Exam.query.count(),
                "study_total": format_duration(sum(row["total_seconds"] for row in student_rows)),
            }
            return render_template(
                "home.html",
                page_title="数据看板",
                page_hint="Robot组管理总览",
                recent_materials=recent_materials,
                exams=exams[:5],
                student_rows=student_rows_sorted[:8],
                recent_submissions=recent_submissions,
                overview=overview,
                provincial_honors=provincial_honors,
                national_honors=national_honors,
            )

        total_study_seconds = get_total_study_seconds(g.current_user.id)
        available_exams = [
            exam
            for exam in exams
            if is_exam_available(exam) and get_exam_submission_for_user(exam.id, g.current_user.id) is None
        ]
        recent_results = (
            ExamSubmission.query.filter_by(user_id=g.current_user.id)
            .order_by(ExamSubmission.submitted_at.desc())
            .limit(5)
            .all()
        )
        overview = {
            "study_total": format_duration(total_study_seconds),
            "materials_count": Material.query.count(),
            "honors_count": honors_count,
            "available_exams_count": len(available_exams),
            "session_count": StudySession.query.filter_by(user_id=g.current_user.id).count(),
        }
        return render_template(
            "home.html",
            page_title="首页概览",
            page_hint="学习资料、学习时长和考试入口都在这里",
            recent_materials=recent_materials,
            available_exams=available_exams[:5],
            recent_results=recent_results,
            overview=overview,
            provincial_honors=provincial_honors,
            national_honors=national_honors,
            total_study_seconds=total_study_seconds,
        )

    @app.route("/materials")
    @login_required
    def materials():
        all_materials = Material.query.order_by(Material.created_at.desc()).all()
        return render_template(
            "materials.html",
            page_title="学习资料",
            page_hint="管理员上传的课程文档、压缩包和外部资料链接",
            materials=all_materials,
        )

    @app.route("/materials/<int:material_id>/download")
    @login_required
    def download_material(material_id: int):
        material = db.session.get(Material, material_id)
        if material is None or not material.stored_filename:
            abort(404)
        return send_from_directory(
            app.config["UPLOAD_FOLDER"],
            material.stored_filename,
            as_attachment=True,
            download_name=material.original_filename,
        )

    @app.route("/honors/<int:honor_id>/download")
    @login_required
    def download_honor(honor_id: int):
        honor = db.session.get(Honor, honor_id)
        if honor is None or not honor.stored_filename:
            abort(404)
        return send_from_directory(
            app.config["HONORS_UPLOAD_FOLDER"],
            honor.stored_filename,
            as_attachment=True,
            download_name=honor.original_filename,
        )

    @app.route("/study")
    @login_required
    def study_center():
        sessions = (
            StudySession.query.filter_by(user_id=g.current_user.id)
            .order_by(StudySession.started_at.desc())
            .limit(10)
            .all()
        )
        total_study_seconds = get_total_study_seconds(g.current_user.id)
        return render_template(
            "study_center.html",
            page_title="学习时长",
            page_hint="开始学习时点击计时，结束时停止，后台会自动汇总总时长",
            sessions=sessions,
            total_study_seconds=total_study_seconds,
        )

    @app.route("/study/start", methods=["POST"])
    @login_required
    def start_study():
        if g.active_study_session:
            flash("你已经有一条正在进行中的学习记录。", "warning")
            return redirect(url_for("study_center"))

        new_session = StudySession(user_id=g.current_user.id)
        db.session.add(new_session)
        db.session.commit()
        flash("学习计时已开始。", "success")
        return redirect(url_for("study_center"))

    @app.route("/study/end", methods=["POST"])
    @login_required
    def end_study():
        if not g.active_study_session:
            flash("当前没有正在进行中的学习记录。", "warning")
            return redirect(url_for("study_center"))

        g.active_study_session.ended_at = datetime.utcnow()
        g.active_study_session.duration_seconds = calculate_session_seconds(g.active_study_session)
        g.active_study_session.status = "completed"
        db.session.commit()
        flash("学习计时已结束。", "success")
        return redirect(url_for("study_center"))

    @app.route("/exams")
    @login_required
    def exams():
        exam_items = Exam.query.order_by(Exam.created_at.desc()).all()
        if g.current_user.is_admin:
            summaries = []
            for exam in exam_items:
                submissions = ExamSubmission.query.filter_by(exam_id=exam.id).all()
                avg_score = (
                    round(sum(item.score for item in submissions) / len(submissions), 1)
                    if submissions
                    else None
                )
                summaries.append(
                    {
                        "exam": exam,
                        "submissions_count": len(submissions),
                        "average_score": avg_score,
                    }
                )
            return render_template(
                "exams.html",
                page_title="考试中心",
                page_hint="管理员可以在这里发布考核题目，学生可以在线作答",
                exam_summaries=summaries,
            )

        available = [exam for exam in exam_items if is_exam_available(exam)]
        completed = (
            ExamSubmission.query.filter_by(user_id=g.current_user.id)
            .order_by(ExamSubmission.submitted_at.desc())
            .all()
        )
        completed_ids = {item.exam_id for item in completed}
        return render_template(
            "exams.html",
            page_title="考试中心",
            page_hint="查看当前可参加的考核，并查看你的历史成绩",
            available_exams=[exam for exam in available if exam.id not in completed_ids],
            completed_submissions=completed,
        )

    @app.route("/exams/<int:exam_id>")
    @login_required
    def take_exam(exam_id: int):
        exam = db.session.get(Exam, exam_id)
        if exam is None:
            abort(404)

        if g.current_user.is_admin:
            submissions = ExamSubmission.query.filter_by(exam_id=exam.id).order_by(
                ExamSubmission.submitted_at.desc()
            )
            return render_template(
                "exam_take.html",
                page_title=exam.title,
                page_hint="管理员预览试卷与作答情况",
                exam=exam,
                admin_preview=True,
                submissions=submissions,
            )

        if not is_exam_available(exam):
            flash("该考试当前不可参加。", "warning")
            return redirect(url_for("exams"))

        existing_submission = get_exam_submission_for_user(exam.id, g.current_user.id)
        if existing_submission:
            flash("你已经完成过这场考试，可以在考试中心查看成绩。", "warning")
            return redirect(url_for("exams"))

        session[f"exam_{exam.id}_started_at"] = datetime.utcnow().isoformat()
        return render_template(
            "exam_take.html",
            page_title=exam.title,
            page_hint="在线作答并提交，系统会自动判分",
            exam=exam,
            admin_preview=False,
        )

    @app.route("/exams/<int:exam_id>/submit", methods=["POST"])
    @login_required
    def submit_exam(exam_id: int):
        exam = db.session.get(Exam, exam_id)
        if exam is None:
            abort(404)

        if g.current_user.is_admin:
            abort(403)

        if not is_exam_available(exam):
            flash("该考试当前不可提交。", "warning")
            return redirect(url_for("exams"))

        if get_exam_submission_for_user(exam.id, g.current_user.id):
            flash("你已经提交过这场考试。", "warning")
            return redirect(url_for("exams"))

        score = 0
        answers = []
        for question in exam.questions:
            selected = request.form.get(f"question_{question.id}", "").strip().upper()
            if selected not in {"A", "B", "C", "D"}:
                flash("请完成所有题目后再提交。", "error")
                return redirect(url_for("take_exam", exam_id=exam.id))
            is_correct = selected == question.correct_option
            if is_correct:
                score += 1
            answers.append(
                ExamAnswer(
                    question_id=question.id,
                    selected_option=selected,
                    is_correct=is_correct,
                )
            )

        start_key = f"exam_{exam.id}_started_at"
        duration_seconds = 0
        started_raw = session.pop(start_key, "")
        if started_raw:
            try:
                duration_seconds = max(
                    0,
                    int((datetime.utcnow() - datetime.fromisoformat(started_raw)).total_seconds()),
                )
            except ValueError:
                duration_seconds = 0

        submission = ExamSubmission(
            exam_id=exam.id,
            user_id=g.current_user.id,
            score=score,
            total_questions=len(exam.questions),
            duration_seconds=duration_seconds,
        )
        db.session.add(submission)
        db.session.flush()
        for answer in answers:
            answer.submission_id = submission.id
            db.session.add(answer)
        db.session.commit()

        flash(f"考试已提交，你的成绩是 {score}/{len(exam.questions)}。", "success")
        return redirect(url_for("exams"))

    @app.route("/admin")
    @admin_required
    def admin_dashboard():
        student_rows = build_student_rows()
        admins = User.query.filter_by(role="admin").order_by(User.created_at.asc()).all()
        materials = Material.query.order_by(Material.created_at.desc()).all()
        honors = Honor.query.order_by(Honor.created_at.desc()).all()
        exams = Exam.query.order_by(Exam.created_at.desc()).all()
        recent_submissions = (
            ExamSubmission.query.order_by(ExamSubmission.submitted_at.desc()).limit(10).all()
        )
        return render_template(
            "admin_dashboard.html",
            page_title="管理后台",
            page_hint="资料发布、考试创建、管理员协作和学生信息汇总",
            student_rows=student_rows,
            admins=admins,
            materials=materials,
            honors=honors,
            honor_level_labels=HONOR_LEVEL_LABELS,
            exams=exams,
            recent_submissions=recent_submissions,
        )

    @app.route("/admin/materials", methods=["POST"])
    @admin_required
    def create_material():
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        external_link = request.form.get("external_link", "").strip()
        uploaded_file = request.files.get("material_file")

        if not title or not category:
            flash("资料标题和分类不能为空。", "error")
            return redirect(url_for("admin_dashboard"))

        has_file = uploaded_file and uploaded_file.filename
        if not external_link and not has_file:
            flash("请至少填写一个资料链接，或者上传一个资料文件。", "error")
            return redirect(url_for("admin_dashboard"))

        stored_filename = None
        original_filename = None
        if has_file:
            original_filename = uploaded_file.filename
            if not allowed_file(original_filename):
                flash("不支持该文件格式，请上传常见文档或压缩包。", "error")
                return redirect(url_for("admin_dashboard"))

            safe_name = secure_filename(original_filename)
            suffix = Path(safe_name).suffix
            stored_filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid4().hex}{suffix}"
            uploaded_file.save(Path(app.config["UPLOAD_FOLDER"]) / stored_filename)

        material = Material(
            title=title,
            category=category,
            description=description or None,
            external_link=external_link or None,
            stored_filename=stored_filename,
            original_filename=original_filename,
            created_by_id=g.current_user.id,
        )
        db.session.add(material)
        db.session.commit()
        flash("资料已发布。", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/honors", methods=["POST"])
    @admin_required
    def create_honor():
        title = request.form.get("title", "").strip()
        level = request.form.get("level", "").strip()
        description = request.form.get("description", "").strip()
        uploaded_file = request.files.get("honor_file")

        if not title or not level:
            flash("荣誉标题和分类不能为空。", "error")
            return redirect(url_for("admin_dashboard"))

        if level not in HONOR_LEVEL_LABELS:
            flash("荣誉分类不正确，请重新选择。", "error")
            return redirect(url_for("admin_dashboard"))

        if uploaded_file is None or not uploaded_file.filename:
            flash("请上传荣誉文件后再提交。", "error")
            return redirect(url_for("admin_dashboard"))

        original_filename = uploaded_file.filename
        if not allowed_file(original_filename):
            flash("不支持该文件格式，请上传常见文档、图片或压缩包。", "error")
            return redirect(url_for("admin_dashboard"))

        safe_name = secure_filename(original_filename)
        suffix = Path(safe_name).suffix
        stored_filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid4().hex}{suffix}"
        uploaded_file.save(Path(app.config["HONORS_UPLOAD_FOLDER"]) / stored_filename)

        honor = Honor(
            title=title,
            level=level,
            description=description or None,
            stored_filename=stored_filename,
            original_filename=original_filename,
            created_by_id=g.current_user.id,
        )
        db.session.add(honor)
        db.session.commit()
        flash("团队荣誉已发布。", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/materials/<int:material_id>/delete", methods=["POST"])
    @admin_required
    def delete_material(material_id: int):
        material = db.session.get(Material, material_id)
        if material is None:
            abort(404)
        if material.stored_filename:
            file_path = Path(app.config["UPLOAD_FOLDER"]) / material.stored_filename
            if file_path.exists():
                file_path.unlink()
        db.session.delete(material)
        db.session.commit()
        flash("资料已删除。", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/honors/<int:honor_id>/delete", methods=["POST"])
    @admin_required
    def delete_honor(honor_id: int):
        honor = db.session.get(Honor, honor_id)
        if honor is None:
            abort(404)
        file_path = Path(app.config["HONORS_UPLOAD_FOLDER"]) / honor.stored_filename
        if file_path.exists():
            file_path.unlink()
        db.session.delete(honor)
        db.session.commit()
        flash("团队荣誉已删除。", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/add-admin", methods=["POST"])
    @admin_required
    def add_admin():
        required_fields = {
            "username": "管理员用户名",
            "password": "管理员密码",
            "full_name": "管理员姓名",
        }
        missing = validate_required_fields(request.form, required_fields)
        if missing:
            flash(f"以下管理员字段不能为空：{'、'.join(missing)}", "error")
            return redirect(url_for("admin_dashboard"))

        username = request.form["username"].strip()
        password = request.form["password"].strip()
        if len(password) < 8:
            flash("管理员密码至少需要 8 位。", "error")
            return redirect(url_for("admin_dashboard"))

        if User.query.filter_by(username=username).first():
            flash("该管理员用户名已存在。", "error")
            return redirect(url_for("admin_dashboard"))

        admin = User(
            username=username,
            full_name=request.form["full_name"].strip(),
            phone=request.form.get("phone", "").strip() or None,
            role="admin",
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        flash("新管理员已添加。", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
    @admin_required
    def delete_user(user_id: int):
        user = db.session.get(User, user_id)
        if user is None:
            abort(404)

        if user.id == g.current_user.id:
            flash("不能删除当前正在登录的管理员账号。", "error")
            return redirect(url_for("admin_dashboard"))

        if user.is_admin:
            admin_count = User.query.filter_by(role="admin").count()
            if admin_count <= 1:
                flash("至少需要保留一个管理员账号。", "error")
                return redirect(url_for("admin_dashboard"))

            if Material.query.filter_by(created_by_id=user.id).first():
                flash("该管理员名下还有已发布资料，请先删除或转交资料后再剔除。", "error")
                return redirect(url_for("admin_dashboard"))

            if Exam.query.filter_by(created_by_id=user.id).first():
                flash("该管理员名下还有已创建考试，请先删除考试后再剔除。", "error")
                return redirect(url_for("admin_dashboard"))

        delete_user_account(user)
        db.session.commit()
        flash("账号已剔除。", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/exams", methods=["POST"])
    @admin_required
    def create_exam():
        title = request.form.get("title", "").strip()
        if not title:
            flash("考试标题不能为空。", "error")
            return redirect(url_for("admin_dashboard"))

        try:
            questions = parse_exam_questions(request.form.get("questions_text", ""))
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("admin_dashboard"))

        start_at = parse_datetime_local(request.form.get("start_at"))
        end_at = parse_datetime_local(request.form.get("end_at"))
        if start_at and end_at and end_at <= start_at:
            flash("结束时间必须晚于开始时间。", "error")
            return redirect(url_for("admin_dashboard"))

        duration_minutes = int(request.form.get("duration_minutes", "30") or 30)
        exam = Exam(
            title=title,
            description=request.form.get("description", "").strip() or None,
            duration_minutes=max(5, duration_minutes),
            start_at=start_at,
            end_at=end_at,
            is_published=request.form.get("is_published") == "on",
            created_by_id=g.current_user.id,
        )
        db.session.add(exam)
        db.session.flush()
        for question_data in questions:
            db.session.add(ExamQuestion(exam_id=exam.id, **question_data))
        db.session.commit()
        flash("考试已创建。", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/exams/<int:exam_id>/delete", methods=["POST"])
    @admin_required
    def delete_exam(exam_id: int):
        exam = db.session.get(Exam, exam_id)
        if exam is None:
            abort(404)
        db.session.delete(exam)
        db.session.commit()
        flash("考试已删除。", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/export/students.csv")
    @admin_required
    def export_students():
        student_rows = build_student_rows()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "学号",
                "姓名",
                "班级",
                "电话",
                "QQ",
                "用户名",
                "电脑型号",
                "显卡型号",
                "CPU 型号",
                "内存容量",
                "总学习时长",
                "已完成考试数",
                "最近成绩",
                "注册时间",
            ]
        )
        for item in student_rows:
            student = item["student"]
            writer.writerow(
                [
                    student.student_id,
                    student.full_name,
                    student.class_name,
                    student.phone,
                    student.qq,
                    student.username,
                    student.computer_model,
                    student.gpu_model,
                    student.cpu_model,
                    student.memory_size,
                    item["total_study"],
                    item["exam_count"],
                    item["latest_score"],
                    student.created_at.strftime("%Y-%m-%d %H:%M"),
                ]
            )

        csv_content = "\ufeff" + output.getvalue()
        filename = f"robot-students-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
        return Response(
            csv_content,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )


app = create_app()


if __name__ == "__main__":
    debug_enabled = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes", "on"}
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=debug_enabled,
        use_reloader=debug_enabled,
    )

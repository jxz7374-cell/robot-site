import os
import sys


project_home = "/home/yourusername/robot-site"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ.setdefault("SECRET_KEY", "replace-with-a-long-random-secret")
os.environ.setdefault("DATABASE_PATH", f"{project_home}/instance/robot_recruit.db")
os.environ.setdefault("UPLOAD_FOLDER", f"{project_home}/uploads/materials")
os.environ.setdefault("HONORS_UPLOAD_FOLDER", f"{project_home}/uploads/honors")

from wsgi import application

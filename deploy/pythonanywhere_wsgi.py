import os
import sys


project_home = "/home/yourusername/robot-site"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ["SECRET_KEY"] = "replace-with-a-long-random-secret"
os.environ["DATABASE_PATH"] = f"{project_home}/instance/robot_recruit.db"
os.environ["UPLOAD_FOLDER"] = f"{project_home}/uploads/materials"

from wsgi import application

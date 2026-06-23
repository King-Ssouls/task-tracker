# task-tracker
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app run.py db init
.\.venv\Scripts\python.exe -m flask --app run.py db migrate -m "initial migration"
.\.venv\Scripts\python.exe -m flask --app run.py db upgrade
.\.venv\Scripts\python.exe run.py
```

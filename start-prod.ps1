$env:PORT = if ($env:PORT) { $env:PORT } else { "8000" }
& "D:\anaconda\anaconda3\python.exe" -m waitress --host=0.0.0.0 --port=$env:PORT wsgi:application

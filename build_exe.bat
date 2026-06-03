@echo off
call .\.venv\Scripts\python.exe -m PyInstaller ^
  --noconfirm --clean ^
  --onefile --windowed ^
  --name "FuelNCET" ^
  --paths "src" ^
  --icon "assets\app.ico" ^
  --add-data "assets\template.docx;assets" ^
  --add-data "assets\app.ico;assets" ^
  main.py
pause
@echo off
title InsightX Analytics
echo =========================================
echo   InsightX Analytics — Launching...
echo =========================================

if not exist venv\Scripts\activate (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate

echo Installing dependencies...
pip install -r requirements.txt -q

echo.
echo Starting Streamlit...
streamlit run app.py

pause

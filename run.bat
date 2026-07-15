cd "3d heatmap gen" || exit /b
call venv\Scripts\activate.bat

python main.py

call deactivate

cd ..

git add .
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "regular svg update"
    git push origin main
) else (
    echo No changes to commit.
)

pause
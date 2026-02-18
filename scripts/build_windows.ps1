$ErrorActionPreference = "Stop"

Write-Host "Starting Build Process..."

# 1. Install Dependencies
Write-Host "Installing dependencies..."
pip install -r requirements.txt

# 2. Import smoke test
Write-Host "Running import smoke test..."
python .\scripts\smoke_imports.py
if ($LASTEXITCODE -ne 0) { throw "Import smoke test failed" }

# 3. Build with PyInstaller
Write-Host "Building EXE with PyInstaller..."
cd packaging
# Use spec-defined build options
pyinstaller --clean --noconfirm app.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
cd ..

# 4. Done
Write-Host "Build Complete!"
Write-Host "Artifact: packaging\dist\StockLLM.exe"

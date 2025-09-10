@echo off
setlocal

REM Configuration - UPDATE THESE VALUES
set DOCKER_USERNAME=jayanshn
set IMAGE_NAME=mail-wacher
set VERSION=1.0

echo 🐳 Building and Publishing Mail Wacher
echo ==================================================
echo Docker Hub Username: %DOCKER_USERNAME%
echo Image Name: %IMAGE_NAME%
echo Version: %VERSION%
echo.

REM Step 1: Build the CPU-only AI image
echo 📦 Step 1: Building CPU-only AI Docker image...
echo This includes AI summarization but uses CPU-only PyTorch
echo Build time: approximately 5-8 minutes...
echo.

REM Build CPU-only version with AI
docker build --no-cache -t %DOCKER_USERNAME%/%IMAGE_NAME%:latest .
docker tag %DOCKER_USERNAME%/%IMAGE_NAME%:latest %DOCKER_USERNAME%/%IMAGE_NAME%:v%VERSION%

if %ERRORLEVEL% NEQ 0 (
    echo ❌ Build failed!
    pause
    exit /b 1
)

echo ✅ Build successful!
echo.

REM Step 2: Create test directory
echo 🧪 Step 2: Preparing for test...
if not exist "test-attachments" mkdir test-attachments

REM Step 3: Docker Hub Login
echo 🔐 Step 3: Docker Hub Login
echo Please login to Docker Hub:
docker login

if %ERRORLEVEL% NEQ 0 (
    echo ❌ Docker login failed!
    pause
    exit /b 1
)

REM Step 4: Push to Docker Hub
echo.
echo 📤 Step 4: Pushing to Docker Hub...
docker push %DOCKER_USERNAME%/%IMAGE_NAME%:latest
docker push %DOCKER_USERNAME%/%IMAGE_NAME%:v%VERSION%

if %ERRORLEVEL% EQU 0 (
    echo ✅ Successfully published to Docker Hub!
    echo.
    echo 🎉 Your image is now available to everyone!
    echo.
    echo 📋 Users can now run:
    echo    docker run -it --rm -v %%cd%%/attachments:/app/attachments %DOCKER_USERNAME%/%IMAGE_NAME%:latest
    echo.
    echo 🌐 Docker Hub URL:
    echo    https://hub.docker.com/r/%DOCKER_USERNAME%/%IMAGE_NAME%
    echo.
    echo 📖 Share these commands with users:
    echo    # Quick start
    echo    mkdir attachments
    echo    docker run -it --rm -v %%cd%%/attachments:/app/attachments %DOCKER_USERNAME%/%IMAGE_NAME%:latest
) else (
    echo ❌ Push failed!
    pause
    exit /b 1
)

REM Cleanup
rmdir /s /q test-attachments 2>nul

pause

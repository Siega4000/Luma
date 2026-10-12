@echo off
chcp 65001 >nul
setlocal

rem ======================================================================
rem  Luma — сборка портативной версии.
rem  Делает: exe через PyInstaller -> папку Luma-Portable -> ZIP-архив.
rem  Запуск: двойной клик по этому файлу (из папки проекта).
rem ======================================================================

cd /d "%~dp0"

echo.
echo === Luma: сборка портативной версии ===
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [!] Не найдено окружение .venv
    echo     Создайте его командой:  python -m venv .venv
    echo     и установите зависимости: .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo [1/4] Сборка exe...
".venv\Scripts\pyinstaller.exe" --noconsole --onefile --name Luma ^
    --icon=luma.ico --version-file version_info.txt ^
    --add-data "luma.ico;." main.py
if errorlevel 1 (
    echo [!] Сборка не удалась.
    pause
    exit /b 1
)

echo.
echo [2/4] Подготовка папки Luma-Portable...
if exist "Luma-Portable" rmdir /s /q "Luma-Portable"
mkdir "Luma-Portable"
copy /y "dist\Luma.exe" "Luma-Portable\" >nul
copy /y "LICENSE" "Luma-Portable\" >nul 2>&1
copy /y "THIRD-PARTY-LICENSES.md" "Luma-Portable\" >nul 2>&1
xcopy /y /e /i /q "licenses" "Luma-Portable\licenses" >nul 2>&1

if exist "ffmpeg.exe" (
    copy /y "ffmpeg.exe" "Luma-Portable\" >nul
    echo     ffmpeg.exe добавлен — программа готова к работе сразу.
    rem ffmpeg под GPL: фиксируем версию, чтобы приложить исходники этой же сборки
    ffmpeg.exe -version > "Luma-Portable\FFMPEG-BUILD.txt" 2>&1
    echo     [!] ffmpeg распространяется по GPL v3.
    echo         Приложите к архиву исходники его версии (см. licenses\FFMPEG-NOTICE.md)
    echo         или не кладите ffmpeg.exe в раздачу.
) else (
    echo     [!] ffmpeg.exe не найден в папке проекта.
    echo         Без него не будет конвертации в MP3 и обложек.
    echo         Скачайте ffmpeg.exe и положите рядом с этим скриптом,
    echo         затем запустите сборку снова.
)

echo.
echo [3/4] Создание файла-подсказки...
> "Luma-Portable\ПРОЧТИ МЕНЯ.txt" (
    echo Luma — загрузка треков с YouTube, SoundCloud и Bandcamp
    echo.
    echo Установка не нужна: запустите Luma.exe из этой папки.
    echo Файлы Luma.exe и ffmpeg.exe должны лежать вместе.
    echo.
    echo Лицензии: файл LICENSE ^(сама Luma^) и папка licenses.
    echo ffmpeg - отдельная программа под GPL v3, см. licenses\FFMPEG-NOTICE.md
    echo.
    echo Как пользоваться:
    echo   1. Вставьте ссылки в поле — по одной в строке.
    echo   2. При желании выберите папку для музыки.
    echo   3. Нажмите «Начать загрузку».
    echo.
    echo Треки сохраняются в MP3 со встроенными обложками.
    echo Плейлисты попадают в отдельную папку со своим названием.
    echo.
    echo При первом запуске Windows может показать предупреждение
    echo «неизвестный издатель» — нажмите «Подробнее», затем
    echo «Выполнить в любом случае».
)

echo.
echo [4/4] Упаковка в ZIP...
powershell -NoProfile -Command ^
    "Compress-Archive -Path 'Luma-Portable\*' -DestinationPath 'Luma-Portable.zip' -Force"
if errorlevel 1 (
    echo [!] Не удалось создать ZIP. Папка Luma-Portable готова — упакуйте вручную.
) else (
    echo     Готово: Luma-Portable.zip
)

echo.
echo === Сборка завершена ===
echo Папка:  %cd%\Luma-Portable
echo Архив:  %cd%\Luma-Portable.zip
echo.
pause

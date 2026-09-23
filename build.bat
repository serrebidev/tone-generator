@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "APP_NAME=ToneGenerator"
set "EXE_NAME=ToneGenerator.exe"
set "GITHUB_REPO_SLUG=serrebidev/tone-generator"
set "PYTHON_CMD=py -3.14"
set "MODE=%~1"
if "%MODE%"=="" set "MODE=build"

if /I "%MODE%"=="help" goto :usage
if /I not "%MODE%"=="build" if /I not "%MODE%"=="release" if /I not "%MODE%"=="dry-run" goto :usage

pushd "%~dp0"

rem `call` matters here: py may resolve to a .cmd wrapper (for example a py.cmd
rem shim ahead of the real launcher). Running a .cmd from a batch file without
rem call hands over this script's control permanently, so the script would end
rem silently at this line and never reach the python fallback.
call %PYTHON_CMD% --version >nul 2>&1
if errorlevel 1 set "PYTHON_CMD=python"
call %PYTHON_CMD% --version >nul 2>&1
if errorlevel 1 (
    echo [build] No usable Python interpreter found ^(tried py -3.14 and python^).
    popd
    exit /b 1
)

if /I "%MODE%"=="build" (
    call :build_app
    set "RC=!ERRORLEVEL!"
    popd
    exit /b !RC!
)

where git >nul 2>&1 || (echo [release] Git not found in PATH.& goto :error)
where gh >nul 2>&1 || (echo [release] GitHub CLI ^(gh^) not found in PATH.& goto :error)
git fetch --tags >nul 2>&1
call :compute_next_version || goto :error

if /I "%MODE%"=="dry-run" (
    echo [dry-run] Next version: v%NEXT_VERSION%
    echo [dry-run] Would update version files, build, package, commit, tag, push, publish the GitHub release as Latest, and delete draft releases.
    popd
    exit /b 0
)

call :ensure_clean || goto :error
call :update_version_files || goto :error
call :build_app || goto :error
call :stage_assets || goto :error
call :commit_tag_push || goto :error
call :publish_release || goto :error

echo [release] Published v%NEXT_VERSION%.
popd
exit /b 0

:build_app
echo [build] Installing build dependencies...
call %PYTHON_CMD% -m pip install -r requirements-build.txt
if errorlevel 1 exit /b 1
echo [build] Running PyInstaller...
call %PYTHON_CMD% -m PyInstaller --noconfirm --clean tone_generator.spec
if errorlevel 1 exit /b 1
if not exist "dist\%EXE_NAME%" (
    echo [build] Expected output not found: dist\%EXE_NAME%
    exit /b 1
)
exit /b 0

:compute_next_version
set "NEXT_VERSION="
rem usebackq with backticks, so the single quotes inside the PowerShell command
rem do not collide with the for /f delimiter. No caret escapes: cmd does not
rem strip them here and PowerShell would receive a literal ^.
for /f "usebackq delims=" %%V in (`powershell -NoProfile -Command "$best=$null; foreach ($t in (git tag --list 'v*.*.*')) { try { $v=[version]$t.Substring(1) } catch { continue }; if (-not $best -or $v -gt $best) { $best=$v } }; if ($best) { '{0}.{1}.{2}' -f $best.Major, $best.Minor, ($best.Build + 1) } else { '1.0.0' }"`) do set "NEXT_VERSION=%%V"
if "%NEXT_VERSION%"=="" (
    echo [release] Failed to compute next version.
    exit /b 1
)
exit /b 0

:ensure_clean
git diff --quiet
if errorlevel 1 (
    echo [release] Working tree has uncommitted tracked changes. Commit or stash them before release.
    exit /b 1
)
git diff --cached --quiet
if errorlevel 1 (
    echo [release] Index has staged changes. Commit or unstage them before release.
    exit /b 1
)
exit /b 0

:update_version_files
echo [release] Updating version files to %NEXT_VERSION%...
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; $q=[char]34; $v='%NEXT_VERSION%'; $parts=$v.Split('.'); $tuple='{0}, {1}, {2}, 0' -f $parts[0], $parts[1], $parts[2]; $py=Get-Content -LiteralPath 'tone_generator.py' -Raw; $py=$py -replace ('APP_VERSION = ' + $q + '[^' + $q + ']+' + $q), ('APP_VERSION = ' + $q + $v + $q); Set-Content -LiteralPath 'tone_generator.py' -Value $py -Encoding utf8; $info=Get-Content -LiteralPath 'version_info.txt' -Raw; $info=$info -replace 'filevers=\([^)]+\)', ('filevers=(' + $tuple + ')'); $info=$info -replace 'prodvers=\([^)]+\)', ('prodvers=(' + $tuple + ')'); $info=$info -replace ('StringStruct\(' + $q + 'FileVersion' + $q + ', ' + $q + '[^' + $q + ']+' + $q + '\)'), ('StringStruct(' + $q + 'FileVersion' + $q + ', ' + $q + $v + $q + ')'); $info=$info -replace ('StringStruct\(' + $q + 'ProductVersion' + $q + ', ' + $q + '[^' + $q + ']+' + $q + '\)'), ('StringStruct(' + $q + 'ProductVersion' + $q + ', ' + $q + $v + $q + ')'); Set-Content -LiteralPath 'version_info.txt' -Value $info -Encoding utf8"
if errorlevel 1 exit /b 1
exit /b 0

:stage_assets
set "RELEASE_DIR=%CD%\dist\release"
if exist "%RELEASE_DIR%" rd /s /q "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%" || exit /b 1
copy /Y "dist\%EXE_NAME%" "%RELEASE_DIR%\%APP_NAME%-v%NEXT_VERSION%.exe" >nul || exit /b 1
powershell -NoProfile -Command "Compress-Archive -Path '%RELEASE_DIR%\%APP_NAME%-v%NEXT_VERSION%.exe' -DestinationPath '%RELEASE_DIR%\%APP_NAME%-v%NEXT_VERSION%.zip' -Force"
if errorlevel 1 exit /b 1
set "SUMS_PATH=%RELEASE_DIR%\%APP_NAME%-v%NEXT_VERSION%-SHA256SUMS.txt"
rem Hash with .NET rather than Get-FileHash, which is missing from some Windows
rem PowerShell installations.
powershell -NoProfile -Command "$sha=[Security.Cryptography.SHA256]::Create(); $lines=@(); foreach ($p in ([IO.Directory]::GetFiles('%RELEASE_DIR%') | Sort-Object)) { $hash=($sha.ComputeHash([IO.File]::ReadAllBytes($p)) | ForEach-Object { $_.ToString('x2') }) -join ''; $lines += ('{0}  {1}' -f $hash, [IO.Path]::GetFileName($p)) }; [IO.File]::WriteAllLines('%SUMS_PATH%', $lines)"
if errorlevel 1 exit /b 1
set "NOTES_PATH=%RELEASE_DIR%\release-notes-v%NEXT_VERSION%.md"
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; $v='%NEXT_VERSION%'; $lines=Get-Content -LiteralPath 'CHANGELOG.md'; $body=@(); $on=$false; foreach ($line in $lines) { if ($line -like '## *') { if ($on) { break }; if ($line -like ('## ' + $v + '*')) { $on=$true; continue } }; if ($on) { $body += $line } }; $body=($body -join [char]10).Trim(); if (-not $body) { Write-Host ('[release] No CHANGELOG.md section for ' + $v + ', using a generic note.'); $body='- Built with build.bat release.' }; $nl=[char]10; [IO.File]::WriteAllText('%NOTES_PATH%', ('## Tone Generator v' + $v + $nl + $nl + $body))"
if errorlevel 1 exit /b 1
exit /b 0

:commit_tag_push
git add tone_generator.py version_info.txt
git commit -m "chore(release): v%NEXT_VERSION%" || exit /b 1
git tag "v%NEXT_VERSION%" || exit /b 1
git push origin HEAD || exit /b 1
git push origin "v%NEXT_VERSION%" || exit /b 1
exit /b 0

:publish_release
echo [release] Creating GitHub release v%NEXT_VERSION%...
gh release create "v%NEXT_VERSION%" ^
    "%RELEASE_DIR%\%APP_NAME%-v%NEXT_VERSION%.exe" ^
    "%RELEASE_DIR%\%APP_NAME%-v%NEXT_VERSION%.zip" ^
    "%SUMS_PATH%" ^
    --repo "%GITHUB_REPO_SLUG%" ^
    --title "Tone Generator %NEXT_VERSION%" ^
    --notes-file "%NOTES_PATH%" ^
    --latest
if errorlevel 1 exit /b 1
gh release edit "v%NEXT_VERSION%" --repo "%GITHUB_REPO_SLUG%" --draft=false --latest
if errorlevel 1 (
    echo [release] Failed to publish v%NEXT_VERSION% as Latest.
    exit /b 1
)
rem Confirm it really is published before deleting anything: a release that is
rem still seen as a draft would otherwise be destroyed by the cleanup below.
powershell -NoProfile -Command "$state = gh release view 'v%NEXT_VERSION%' --repo '%GITHUB_REPO_SLUG%' --json isDraft,url | ConvertFrom-Json; if ($state.isDraft) { Write-Host ('[release] v%NEXT_VERSION% is still a draft at ' + $state.url); exit 1 }; Write-Host ('[release] v%NEXT_VERSION% is published: ' + $state.url)"
if errorlevel 1 (
    echo [release] v%NEXT_VERSION% is not published. Stopping before draft cleanup.
    exit /b 1
)
call :delete_draft_releases || exit /b 1
rem macOS on a GitHub runner, Linux over SSH (no-op on GitHub Actions).
call %PYTHON_CMD% tools\release_other_platforms.py "v%NEXT_VERSION%"
if errorlevel 1 (
    echo [release] Linux/macOS assets failed. Rerun: python tools\release_other_platforms.py v%NEXT_VERSION%
    exit /b 1
)
exit /b 0

:delete_draft_releases
echo [release] Checking for draft releases in %GITHUB_REPO_SLUG%...
rem Never touch the release just published, so it cannot delete its own work.
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; $repo='%GITHUB_REPO_SLUG%'; $keep='v%NEXT_VERSION%'; $drafts = gh release list --repo $repo --limit 100 --json tagName,isDraft | ConvertFrom-Json | Where-Object { $_.isDraft -eq $true -and $_.tagName -ne $keep }; foreach ($draft in $drafts) { Write-Host ('Deleting draft release ' + $draft.tagName + '...'); gh release delete $draft.tagName --repo $repo --yes }"
if errorlevel 1 (
    echo [release] Failed to remove draft releases.
    exit /b 1
)
exit /b 0

:usage
echo Usage:
echo   build.bat build
echo   build.bat dry-run
echo   build.bat release
exit /b 1

:error
echo [release] Failed.
popd
exit /b 1

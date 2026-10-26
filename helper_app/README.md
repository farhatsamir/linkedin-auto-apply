# LinkedIn Auto Apply Desktop Helper

This desktop helper is **required for the current dashboard's Connect LinkedIn and Reconnect flows**. The dashboard opens it through the `linkedinautoapply://` URL protocol. It launches a local Chromium window, lets the user sign in to LinkedIn, and sends the captured browser session (`storage_state`) to the backend with a short-lived, one-time connection token.

After the dashboard confirms the connection, the helper can be closed. Job application runs execute in the backend Celery worker using the saved session. The helper is needed again if the account must be reconnected; it does not need to stay open during every application run.

## For users

The supplied installer scripts target **Windows**. Packaged macOS/Linux helpers and a downloadable installer are not included in this repository; a developer must build and distribute the Windows installer first.

1. Install the helper supplied by the operator of your Auto Apply backend.
2. Open the dashboard on the same Windows computer, sign in, and select **Connect LinkedIn**.
3. Accept the browser's request to open LinkedIn Auto Apply Helper.
4. Sign in to LinkedIn in the local browser window and complete any verification.
5. Leave the dashboard open until it reports **LinkedIn connected**, then close the helper.

A phone cannot complete this desktop connection step. After connection, the dashboard can be used without keeping the helper open, provided the backend services remain available.

## Run the helper from source

Prerequisites: Windows and Python 3.11. From the project root, use PowerShell:

```powershell
cd helper_app
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Set `BACKEND_URL` in `main.py` to the backend used by the dashboard. Its current value, `http://127.0.0.1:8000`, targets the user's own computer; configure the deployed API address before distributing a helper for a hosted service.

For development, edit `register_protocol_dev.reg` so the protocol command points to the absolute paths of your Python executable and `main.py`. Keep both paths and the `%1` URL argument quoted, then import the edited file into the current user's Windows registry. The checked-in paths refer to the original development machine and will not work unchanged on another computer.

Start a connection from the dashboard to obtain a fresh protocol URL. Launching `main.py` without that URL does not start a connection. The backend and Redis must be available, and login must finish before the backend's connection token expires (currently five minutes).

## Build the Windows installer

In the helper's activated Python environment:

```powershell
python -m pip install pyinstaller
python -m playwright install chromium
python -m PyInstaller build.spec
```

Before running PyInstaller, check `CHROMIUM_SOURCE` and `CHROMIUM_DEST` in `build.spec`. They currently reference the local Playwright browser folder `chromium-1208`; adjust both to the Chromium revision installed for the pinned Playwright version. The specification bundles Chromium so end users do not have to install Python or Playwright separately.

The output is `dist/LinkedInAutoApplyHelper/`. Compile `installer.iss` with Inno Setup after this folder exists. The installer takes that folder as input, writes `installer_output/LinkedInAutoApplyHelper-Setup.exe`, and registers `linkedinautoapply://` for the current Windows user.

Test the complete dashboard-to-helper connection using the intended backend before distributing the installer. Build output, captured sessions, and helper logs are local artifacts and should stay outside Git.

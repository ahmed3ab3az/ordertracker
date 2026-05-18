# Build & release

## Building the Windows installer locally

1. Install dependencies on a Windows 10/11 64-bit host:
   * Python 3.11+ (from python.org)
   * [Inno Setup 6](https://jrsoftware.org/isdl.php) (add `iscc` to PATH)
   * `pip install -e ".[dev,build]"`

2. Run the build script:

   ```powershell
   python scripts\build.py --clean
   ```

   This produces:

   * `dist\OrderTracker\OrderTracker.exe` — the main app.
   * `dist\OrderTracker\updater_runner.exe` — the rollback watchdog.
   * `installer\Output\ordertracker-setup-0.1.0.exe` — the installer.

3. Smoke-test the installer in a fresh VM:
   * Run `ordertracker-setup-0.1.0.exe`.
   * Launch from Start menu, log in with the admin account.
   * Run an Excel import; confirm a few status transitions; close the day.
   * Uninstall and verify `%APPDATA%\OrderTracker` is removed.

## Publishing a release

1. Bump `version` in `pyproject.toml`, `__init__.py`, and `installer/ordertracker.iss`.
2. Build the installer.
3. Compute the SHA-256 of the installer EXE:

   ```powershell
   Get-FileHash -Algorithm SHA256 .\installer\Output\ordertracker-setup-X.Y.Z.exe
   ```

4. Create a GitHub release tagged `vX.Y.Z`. In the release notes include:

   ```
   ## Highlights
   - ...

   SHA256: <full-hex-digest>
   ```

5. Upload the installer EXE as a release asset.

The next time a running client checks for updates it will:

* Hit `GET /repos/ahmed3ab3az/ordertracker/releases/latest`.
* Match the SHA-256 line in the release body.
* Download to `%TEMP%/ordertracker-update/`.
* Verify the digest.
* Hand off to the watchdog EXE which restores the previous install if the
  new one fails to start within 30 seconds.

## CI/CD

A minimal GitHub Actions workflow can wrap this — see the suggested
`.github/workflows/build.yml` (intentionally not committed by default
because Inno Setup runs on Windows runners only and consumes minutes).

## Manual installer fallback

If a customer's PC cannot reach GitHub (firewalled), copy
`ordertracker-setup-X.Y.Z.exe` to a USB drive and run it locally. The
auto-updater simply becomes a no-op for those PCs.

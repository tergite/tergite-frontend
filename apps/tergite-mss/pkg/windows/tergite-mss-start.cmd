@echo off
rem Run by the tergite-mss service. Exits 0 without a config, which stops the service
rem without the restarts a failure gets, so a fresh install does not loop at every boot.
if not exist "%MSS_CONFIG_FILE%" (
  echo %MSS_CONFIG_FILE% does not exist yet
  exit /b 0
)
"%~dp0mss.exe" start --port 8002

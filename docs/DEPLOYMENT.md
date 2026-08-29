# Deployment Guide

## Local Windows launch

Double-click `Launch_Budget_Simulation.bat`. The launcher uses the included portable runtime when present. If no runtime or system Python is available, it invokes `Prepare_Portable_Runtime.ps1`, which downloads the official Python 3.13.5 embeddable package from python.org into the application folder. It does not install Python into Windows.

The browser opens at `http://127.0.0.1:8080`. Other devices on the same network can use `http://<host-computer-IP>:8080` after Windows Firewall permits inbound TCP port 8080.

## Linux/macOS launch

Run:

```bash
chmod +x Launch_Budget_Simulation.sh
./Launch_Budget_Simulation.sh
```

## Internet deployment

The server binds to `0.0.0.0` by default and honors:

- `BUDGET_SIM_HOST`
- `BUDGET_SIM_PORT`
- `BUDGET_SIM_DB`
- `BUDGET_SIM_NO_BROWSER=1`

For Azure App Service, use `python server.py` as the startup command and place the SQLite file on persistent storage. For higher enrollment or production use, place the app behind HTTPS and migrate the local tables to Dataverse, Azure SQL, or another managed relational database.

## Security and operations

- Change the default professor and demonstration student passwords before production use.
- Use HTTPS for internet deployment.
- Back up `data/budget_simulation.db` regularly.
- Configure a reverse proxy or Azure front end for TLS, rate limiting, and centralized authentication.
- The in-memory login sessions are cleared when the server restarts.

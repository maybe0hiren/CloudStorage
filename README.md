# Overcast

Overcast is a private, LAN-based cloud storage system that turns a local computer into a personal file server.

It provides a cross-platform Flutter application for browsing, uploading, downloading, creating, moving, renaming, and managing files stored on the Overcast server.

The system is designed primarily for private home/LAN environments and does not require a public cloud provider.

## Description

Overcast consists of two main components:

1. **Overcast Backend** — runs on the host/server machine and manages storage, metadata, file operations, and API requests.
2. **Overcast Frontend** — a Flutter application that provides the user interface for accessing the backend.

The frontend supports Linux, Windows, and Android from the same Flutter codebase.

### Features

- Browse files and folders
- Upload files
- Upload folders
- Download files
- Rename files
- Move files
- Copy files
- Delete files
- Restore files where supported
- Create text files
- Create folders
- Handle empty folders
- File previews
- Open/view supported media
- Backend health checking
- LAN connectivity detection
- Linux desktop client
- Windows desktop client
- Android client

## Tech Stack

### Backend

- Python
- Gunicorn
- Nginx
- SQLite
- Local filesystem storage
- systemd
- UFW

The Python application is served by Gunicorn. Nginx provides the LAN-facing HTTP endpoint and reverse-proxies requests to the backend. SQLite stores metadata while the filesystem stores the actual file contents.

### Frontend

- Flutter
- Dart
- HTTP API
- `file_picker`

Flutter provides a single application codebase for Linux, Windows, and Android.

## Architecture

```text
                    HOME / LAN NETWORK
                            |
          +-----------------+-----------------+
          |                 |                 |
          v                 v                 v
       Linux             Windows           Android
       Client             Client             Client
          |                 |                 |
          +-----------------+-----------------+
                            |
                            | HTTP
                            v
                   +--------------------+
                   |  Overcast Server   |
                   |                    |
                   |  Linux             |
                   +---------+----------+
                             |
                             v
                         UFW Firewall
                             |
                             v
                           Nginx
                             |
                             v
                         Gunicorn
                             |
                             v
                    Overcast Backend
                       /          \
                      v            v
                  SQLite       File Storage
```

The frontend communicates with the backend through Nginx. The backend itself runs behind Nginx and is not intended to be directly exposed to other devices.

## Project Structure

```text
Overcast/
|
+-- backend/
|   +-- run.py
|   +-- requirements.txt
|   +-- storage/
|   +-- temp/
|   +-- preview/
|   +-- env/
|   `-- ...
|
+-- frontend/
|   +-- lib/
|   |   +-- main.dart
|   |   +-- api.dart
|   |   `-- ...
|   |
|   +-- assets/
|   +-- android/
|   +-- linux/
|   +-- windows/
|   +-- pubspec.yaml
|   `-- ...
|
`-- README.md
```

# Setup Guide

## Backend Setup

The server requires:

- Linux
- Python 3
- Python virtual environment support
- Nginx
- SQLite
- systemd
- UFW

Install the required packages using the package manager appropriate for the server distribution.

### Python Environment

```bash
cd /opt/overcast/backend
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

## Backend Service

Overcast is intended to run as a systemd service.

```bash
sudo systemctl start overcast-backend
sudo systemctl stop overcast-backend
sudo systemctl restart overcast-backend
sudo systemctl status overcast-backend
```

Enable automatic startup:

```bash
sudo systemctl enable overcast-backend
sudo systemctl is-enabled overcast-backend
```

## Nginx

Nginx provides the LAN-facing HTTP endpoint and forwards requests to the Overcast backend.

```bash
sudo systemctl status nginx
sudo systemctl enable nginx
sudo systemctl start nginx
sudo nginx -t
sudo systemctl restart nginx
```

## Firewall

Overcast is intended for LAN use.

Allow HTTP access from the local subnet:

```bash
sudo ufw allow from <LAN_SUBNET> to any port 80 proto tcp
```

Check:

```bash
sudo ufw status
```

The UFW rule persists across reboots.

## Backend Health Check

The backend exposes:

```text
/api/health
```

Test locally:

```bash
curl http://127.0.0.1/api/health
```

From another LAN device:

```bash
curl http://<OVERCAST_SERVER>/api/health
```

A healthy response indicates that the backend, database, and storage are available.

# Frontend Setup

Install Flutter and verify the environment:

```bash
flutter --version
flutter doctor
```

Enter the frontend directory:

```bash
cd frontend
```

Install dependencies:

```bash
flutter pub get
```

Analyze:

```bash
flutter analyze
```

The project should have no analyzer errors before creating a release build.

# Linux

## Development

```bash
flutter run -d linux
```

## Release

```bash
flutter build linux --release
```

The release bundle is:

```text
build/linux/x64/release/bundle/
```

The complete bundle must be distributed. Do not distribute only the executable.

Create an archive:

```bash
tar -czf Overcast-Linux.tar.gz   -C build/linux/x64/release/bundle .
```

Extract:

```bash
mkdir -p ~/Applications/Overcast
tar -xzf Overcast-Linux.tar.gz -C ~/Applications/Overcast
```

Run the executable contained in the extracted bundle.

# Android

Android builds require the Android SDK, platform tools, build tools, platform, and NDK.

Verify:

```bash
flutter doctor
```

Build:

```bash
flutter build apk --release
```

APK location:

```text
build/app/outputs/flutter-apk/app-release.apk
```

Copy to a release directory:

```bash
mkdir -p ~/Documents/Cache/temp/Overcast

cp build/app/outputs/flutter-apk/app-release.apk ~/Documents/Cache/temp/Overcast/Overcast-Android.apk
```

The Android device must be connected to the same LAN as the Overcast server.

# Windows

Windows builds require a Windows development environment with Flutter and the Windows desktop tooling.

```powershell
flutter pub get
flutter analyze
flutter build windows --release
```

The release application is generated under:

```text
build\windows\x64\runner\Release\
```

Distribute the complete release directory, not only the `.exe`.

Create:

```text
Overcast-Windows.zip
```

containing the complete release directory.

# Frontend Server Configuration

The frontend requires the address of the Overcast backend.

Configure it through the application's server/backend setting:

```text
http://<OVERCAST_SERVER>
```

Do not hard-code a machine-specific address in documentation.

The API is accessed through the configured server address, for example:

```text
http://<OVERCAST_SERVER>/api/health
```

# Connectivity

The frontend checks whether the configured Overcast server is reachable.

Connected:

```text
Connected to Overcast
```

Unavailable:

```text
Not connected to Overcast
```

If the client cannot connect, verify:

1. The client is on the same LAN.
2. The server is powered on.
3. `overcast-backend.service` is running.
4. Nginx is running.
5. The firewall allows LAN HTTP traffic.
6. The frontend has the correct server address.

# Logging

## Backend

Live logs:

```bash
sudo journalctl -u overcast-backend -f
```

Last 100 entries:

```bash
sudo journalctl -u overcast-backend -n 100 --no-pager
```

Logs since boot:

```bash
sudo journalctl -u overcast-backend -b
```

## Nginx

Access log:

```bash
sudo tail -f /var/log/nginx/access.log
```

Error log:

```bash
sudo tail -f /var/log/nginx/error.log
```

# Troubleshooting

### Backend

```bash
sudo systemctl status overcast-backend
sudo systemctl restart overcast-backend
sudo journalctl -u overcast-backend -n 100 --no-pager
```

### Nginx

```bash
sudo systemctl status nginx
sudo nginx -t
sudo systemctl restart nginx
```

### Listening Ports

```bash
sudo ss -tulpn
```

### Connectivity

From another LAN device:

```bash
curl -v --connect-timeout 5 http://<OVERCAST_SERVER>/api/health
```

If this succeeds, the network, firewall, Nginx, and backend path are reachable.

# Development Workflow

## Backend

```bash
cd backend
sudo systemctl restart overcast-backend
sudo journalctl -u overcast-backend -f
```

## Frontend

```bash
cd frontend
flutter pub get
flutter analyze
flutter run -d linux
```

Release builds:

```bash
flutter build linux --release
flutter build apk --release
```

Windows:

```powershell
flutter build windows --release
```

# Release Files

A convenient release directory can contain:

```text
Overcast/
|
+-- Overcast-Android.apk
+-- Overcast-Linux.tar.gz
`-- Overcast-Windows.zip
```

All client releases are built from the same Flutter frontend project.

# Design Principles

### LAN First
Overcast is designed around private local-network storage.

### Self Hosted
Files remain on the user's own server instead of a third-party cloud provider.

### Cross Platform
Flutter provides a shared application codebase for Linux, Windows, and Android.

### Simple Infrastructure
The backend uses systemd, Nginx, UFW, SQLite, and Gunicorn.

### Native-Like Experience
The frontend is designed to provide a familiar file-management experience rather than requiring users to interact directly with backend APIs.


**Overcast — Your files. Your network. Your cloud.**

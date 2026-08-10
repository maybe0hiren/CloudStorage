# ☁️ Overcast

LAN-first personal cloud storage for a home lab.

## Backend

The backend is a Flask application. It is configured to listen on `0.0.0.0:8000`, so other devices on the same home network can connect to the Debian laptop.

The backend does **not** require an internet connection.

### Run on the Debian laptop

```bash
cd CloudStorage
./run_backend.sh
```

Or manually:

```bash
cd backend
auto activate env
python run.py
```

The LAN address will be:

```text
http://<DEBIAN-LAPTOP-IP>:8000
```

For example, if the laptop's LAN address is `192.168.1.50`:

```text
http://192.168.1.50:8000/api/health
```

### Important LAN note

Binding to `0.0.0.0` makes the service available on the laptop's network interfaces. Keep the service behind your home LAN and **do not configure router port forwarding** if this is intended to remain a home-only cloud.

## Storage

The backend keeps the real files in `backend/storage/` using the generated UID as the physical filename. The SQLite database stores the user's logical path and filename.

This means moving/renaming a file does not expose the real storage filename.

## Main API

- `GET /api/health`
- `GET /api/files`
- `GET /api/files/<uid>`
- `POST /api/files/upload`
- `POST /api/files/text`
- `GET /api/files/<uid>/download`
- `GET /api/files/<uid>/preview`
- `GET /api/files/<uid>/text`
- `PUT /api/files/<uid>/text`
- `GET /api/files/<uid>/stream`
- `PUT /api/files/<uid>/path`
- `DELETE /api/files/<uid>` — move to trash
- `GET /api/trash`
- `POST /api/trash/<uid>/restore`
- `DELETE /api/trash/<uid>` — permanently delete
- `POST /api/files/<uid>/link`
- `GET /sharing/<encoded>.file`

The frontend can be built against these endpoints later.

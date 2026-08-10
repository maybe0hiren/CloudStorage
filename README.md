# Cloud Storage

A local-first file storage backend with SQLite metadata, atomic uploads,
trash/restore, text-file editing, share links, and HTTP range streaming.

## Backend

```bash
cd backend
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

The default development bind address is `127.0.0.1:8000`.

For LAN deployment, set:

```env
HOST="0.0.0.0"
PORT="8000"
```

The backend creates its runtime directories automatically.

## Runtime data

Do not commit these:

- `.env`
- SQLite database
- `storage/`
- `preview/`
- `temp/`
- logs

The database uses SQLite WAL mode and full synchronous writes.

## Production

For a permanent Linux deployment, run the Flask application behind
Gunicorn and a reverse proxy such as Nginx. Keep the application and
runtime data on separate directories and back up both the database and
stored files.

The system is designed to fail safely where possible, but no storage
software can literally guarantee that hardware, disks, power, or the
operating system will never fail. Keep backups of important data.

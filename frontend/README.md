# Overcast Frontend

Flutter frontend for Overcast LAN Cloud Storage.

## LAN server

Default server:
`http://192.168.1.9`

## Folder support

The backend does not expose a native directory API. The frontend therefore represents
empty folders using a hidden `.overcast-folder.txt` marker uploaded through the normal
file-upload endpoint. The marker is never shown in the UI.

## Text files

Text-file creation uses the normal upload endpoint rather than the backend text-creation
endpoint, because the latter currently returns 409 on the deployed backend.

## Run

```bash
flutter pub get
flutter analyze
flutter run -d linux
```

#!/usr/bin/env bash

set -e

PROJECT="$HOME/Documents/Cache/Overcast/frontend"
OUTPUT="$HOME/Documents/Cache/temp/Overcast"

echo "======================================"
echo "       OVERCAST RELEASE BUILDER"
echo "======================================"

cd "$PROJECT"

mkdir -p "$OUTPUT"

echo
echo "[1/4] Cleaning..."
flutter clean

echo
echo "[2/4] Getting dependencies..."
flutter pub get

echo
echo "[3/4] Checking code..."
flutter analyze

echo
echo "[4/4] Building Android..."
flutter build apk --release

echo
echo "Android build complete."

cp build/app/outputs/flutter-apk/app-release.apk \
   "$OUTPUT/Overcast-Android.apk"

echo
echo "Building Linux..."
flutter build linux --release

echo
echo "Packaging Linux..."

rm -rf "$OUTPUT/linux"
mkdir -p "$OUTPUT/linux"

cp -r build/linux/x64/release/bundle \
   "$OUTPUT/linux/Overcast"

cd "$OUTPUT/linux"

tar -czf "$OUTPUT/Overcast-Linux.tar.gz" Overcast

rm -rf "$OUTPUT/linux"

mkdir -p "$OUTPUT/Windows"

cat > "$OUTPUT/Windows/BUILD_ON_WINDOWS.txt" <<'EOF'
OVERCAST WINDOWS BUILD
======================

Copy the entire Overcast Flutter project to Windows.

From the frontend directory run:

flutter pub get
flutter build windows --release

The Windows application will be located at:

build\windows\x64\runner\Release\

Zip the entire Release folder and rename it:

Overcast-Windows.zip

IMPORTANT:
Do NOT send only the .exe.
The entire Release folder is required because the Flutter application
depends on the DLLs and data files beside the executable.
EOF

echo
echo "======================================"
echo "          BUILD COMPLETE"
echo "======================================"
echo
echo "Output:"
echo
ls -lh "$OUTPUT"
echo
echo "Android:"
echo "  $OUTPUT/Overcast-Android.apk"
echo
echo "Linux:"
echo "  $OUTPUT/Overcast-Linux.tar.gz"
echo
echo "Windows:"
echo "  Build on Windows using the instructions in:"
echo "  $OUTPUT/Windows/BUILD_ON_WINDOWS.txt"
echo

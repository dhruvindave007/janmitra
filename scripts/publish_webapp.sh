#!/bin/bash
# =============================================================================
# JANMITRA WEB APP PUBLISHER
# Builds the Flutter web bundle and publishes it to the website.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="$REPO_ROOT/janmitra_mobile"
PUBLISH_DIR="${WEBAPP_PUBLISH_DIR:-/var/www/html/webapp}"
BASE_HREF="${WEBAPP_BASE_HREF:-/webapp/}"
FLUTTER_IMAGE="${FLUTTER_BUILD_IMAGE:-ghcr.io/cirruslabs/flutter:stable}"

if [ ! -d "$APP_DIR" ]; then
    echo "ERROR: Flutter app directory not found at $APP_DIR"
    exit 1
fi

build_with_local_flutter() {
    echo "Building Flutter web bundle with local Flutter SDK..."
    cd "$APP_DIR"
    flutter pub get
    flutter build web --release --base-href "$BASE_HREF"
}

build_with_docker_flutter() {
    if ! command -v docker >/dev/null 2>&1; then
        echo "ERROR: Docker is required to build the web app when Flutter is not installed."
        exit 1
    fi

    echo "Building Flutter web bundle with Docker image $FLUTTER_IMAGE..."
    docker run --rm \
        --user "$(id -u):$(id -g)" \
        -v "$REPO_ROOT:/workspace" \
        -w /workspace/janmitra_mobile \
        -e PUB_CACHE=/workspace/.pub-cache \
        "$FLUTTER_IMAGE" \
        sh -lc "flutter pub get && flutter build web --release --base-href '$BASE_HREF'"
}

publish_bundle() {
    local build_dir="$APP_DIR/build/web"
    local staging_dir

    if [ ! -f "$build_dir/index.html" ]; then
        echo "ERROR: Flutter web build did not produce index.html"
        exit 1
    fi

    if ! grep -q "<base href=\"$BASE_HREF\">" "$build_dir/index.html"; then
        echo "ERROR: Built web app does not contain expected base href $BASE_HREF"
        exit 1
    fi

    staging_dir="$(mktemp -d)"
    cp -a "$build_dir"/. "$staging_dir"/

    echo "Publishing web bundle to $PUBLISH_DIR..."
    sudo mkdir -p "$(dirname "$PUBLISH_DIR")"
    sudo rm -rf "${PUBLISH_DIR}.new"
    sudo mkdir -p "${PUBLISH_DIR}.new"
    sudo cp -a "$staging_dir"/. "${PUBLISH_DIR}.new"/
    sudo chmod -R a+rX "${PUBLISH_DIR}.new"

    if [ -d "$PUBLISH_DIR" ]; then
        sudo rm -rf "${PUBLISH_DIR}.old"
        sudo mv "$PUBLISH_DIR" "${PUBLISH_DIR}.old"
    fi

    sudo mv "${PUBLISH_DIR}.new" "$PUBLISH_DIR"
    sudo rm -rf "${PUBLISH_DIR}.old"
    rm -rf "$staging_dir"

    echo "Web app published successfully."
}

if command -v flutter >/dev/null 2>&1; then
    build_with_local_flutter
else
    build_with_docker_flutter
fi

publish_bundle

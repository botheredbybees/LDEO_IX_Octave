#!/bin/sh
set -e

if [ "$1" = "serve" ]; then
  exec uvicorn webapp.main:app --host 0.0.0.0 --port 8080
elif [ "$1" = "octave-cli" ]; then
  shift
  exec octave-cli --no-gui "$@"
else
  exec "$@"
fi

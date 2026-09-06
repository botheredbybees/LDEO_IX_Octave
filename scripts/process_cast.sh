#!/usr/bin/env bash
# Drives a single LDEO_IX_Octave cast end-to-end: starts the repo's own
# ldeo-ix-octave image (serve mode) against a staging directory, converts
# CTD/SADCP inputs if the cast config asks for it, creates the cast
# session, generates set_cast_params.m, then runs the real 17-step
# process_cast(...) pipeline (octave-cli mode).
#
# No vessel/organization-specific code belongs in this file -- see
# docs/vessel-data-preparation.md for the input contract and how to write
# your own fetch/prep script that feeds it.
#
# Usage: scripts/process_cast.sh <staging-dir> <cast-config.json> [image-tag]
set -euo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  echo "usage: $0 <staging-dir> <cast-config.json> [image-tag]" >&2
  exit 1
fi

STAGING_DIR=$(cd "$1" && pwd)
CONFIG_DIR=$(cd "$(dirname "$2")" && pwd)
CONFIG_FILE="$CONFIG_DIR/$(basename "$2")"
IMAGE_TAG="${3:-ldeo-ix-octave}"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "error: cast config not found: $CONFIG_FILE" >&2
  exit 1
fi

for required_dir in ctd nav data ladcp; do
  if [ ! -d "$STAGING_DIR/$required_dir" ]; then
    echo "error: staging directory is missing required subdirectory: $required_dir/" >&2
    exit 1
  fi
done

# Pre-flight validation of required config fields
for field in station cast_name ladcpdo ladcpup nav lat lon time_start time_end; do
  if [ "$(jq -e "has(\"$field\")" "$CONFIG_FILE" 2>/dev/null || echo false)" != "true" ]; then
    echo "error: cast config is missing required field: $field" >&2
    exit 1
  fi
done

# Validate CTD source: either (ctd_hex AND ctd_xmlcon) or ctd_cnv
HAS_CTD_HEX=$(jq -r 'has("ctd_hex")' "$CONFIG_FILE")
HAS_CTD_XMLCON=$(jq -r 'has("ctd_xmlcon")' "$CONFIG_FILE")
HAS_CTD_CNV=$(jq -r 'has("ctd_cnv")' "$CONFIG_FILE")
if [ "$HAS_CTD_HEX" = "true" ] && [ "$HAS_CTD_XMLCON" != "true" ]; then
  echo "error: cast config sets ctd_hex but not ctd_xmlcon -- both are required for quick-convert" >&2
  exit 1
fi
if [ "$HAS_CTD_XMLCON" = "true" ] && [ "$HAS_CTD_HEX" != "true" ]; then
  echo "error: cast config sets ctd_xmlcon but not ctd_hex -- both are required for quick-convert" >&2
  exit 1
fi
if [ "$HAS_CTD_HEX" != "true" ] && [ "$HAS_CTD_CNV" != "true" ]; then
  echo "error: cast config must provide either (ctd_hex AND ctd_xmlcon) or ctd_cnv" >&2
  exit 1
fi
if [ "$HAS_CTD_HEX" = "true" ] && [ "$HAS_CTD_XMLCON" = "true" ] && [ "$HAS_CTD_CNV" = "true" ]; then
  echo "error: cast config sets both (ctd_hex AND ctd_xmlcon) and ctd_cnv -- only one CTD source is allowed" >&2
  exit 1
fi

HAS_SADCP_CONTOUR=$(jq -r 'has("sadcp_contour_dir")' "$CONFIG_FILE")
HAS_SADCP_MAT=$(jq -r 'has("sadcp_mat_path")' "$CONFIG_FILE")
if [ "$HAS_SADCP_CONTOUR" = "true" ] && [ "$HAS_SADCP_MAT" = "true" ]; then
  echo "error: cast config sets both sadcp_contour_dir and sadcp_mat_path -- only one is allowed" >&2
  exit 1
fi
if [ "$HAS_SADCP_CONTOUR" = "true" ] && [ ! -d "$STAGING_DIR/codas" ]; then
  echo "error: cast config sets sadcp_contour_dir but staging directory has no codas/ subdirectory" >&2
  exit 1
fi
if [ "$HAS_SADCP_MAT" = "true" ] && [ ! -d "$STAGING_DIR/sadcp" ]; then
  echo "error: cast config sets sadcp_mat_path but staging directory has no sadcp/ subdirectory" >&2
  exit 1
fi

if [ "$(jq -r 'has("drot")' "$CONFIG_FILE")" = "true" ]; then
  echo "error: cast config sets drot -- this script never sets declination manually (real GPS nav means it must be computed by process_cast's own step 3; see docs/vessel-data-preparation.md)" >&2
  exit 1
fi

# A stale session left over from a previous run of this staging directory
# would add a second cast to the same set_cast_params.m instead of
# replacing the first -- every invocation of this script is scoped to
# exactly one cast.
rm -f "$STAGING_DIR/data/.cruise_intake_session.json"

MOUNT_ARGS=(
  -v "$STAGING_DIR/ladcp:/ladcp_data:ro"
  -v "$STAGING_DIR/ctd:/ctd_data:ro"
  -v "$STAGING_DIR/nav:/navigation_data:ro"
)
if [ "$HAS_SADCP_CONTOUR" = "true" ]; then
  MOUNT_ARGS+=(-v "$STAGING_DIR/codas:/codas_data:ro")
fi
if [ "$HAS_SADCP_MAT" = "true" ]; then
  MOUNT_ARGS+=(-v "$STAGING_DIR/sadcp:/sadcp_data:ro")
fi

echo "starting $IMAGE_TAG (serve mode) ..."
CONTAINER_ID=$(docker run -d --rm -p 0:8080 -v "$STAGING_DIR/data:/data" "${MOUNT_ARGS[@]}" "$IMAGE_TAG")
cleanup() {
  docker stop "$CONTAINER_ID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

HOST_PORT=$(docker port "$CONTAINER_ID" 8080/tcp | head -n1 | awk -F: '{print $NF}')
BASE_URL="http://localhost:${HOST_PORT}"

echo "waiting for $BASE_URL/health ..."
HEALTHY=false
for _ in $(seq 1 30); do
  if curl -sf "$BASE_URL/health" >/dev/null 2>&1; then
    HEALTHY=true
    break
  fi
  sleep 1
done
if [ "$HEALTHY" != "true" ]; then
  echo "error: webapp never became healthy at $BASE_URL/health" >&2
  docker logs "$CONTAINER_ID" >&2 || true
  exit 1
fi

echo "mounts available: $(curl -sf "$BASE_URL/api/mounts")"

http_post() {
  local path="$1" body="$2"
  curl -sS -w '\n%{http_code}' -X POST "$BASE_URL$path" \
    -H 'Content-Type: application/json' -d "$body"
}

if [ "$HAS_CTD_HEX" = "true" ]; then
  HEX_PATH=$(jq -r '.ctd_hex' "$CONFIG_FILE")
  XMLCON_PATH=$(jq -r '.ctd_xmlcon' "$CONFIG_FILE")
  echo "quick-converting $HEX_PATH ..."
  BODY=$(jq -n --arg hex "$HEX_PATH" --arg xmlcon "$XMLCON_PATH" '{hex_path: $hex, xmlcon_path: $xmlcon}')
  RAW=$(http_post "/api/quick-convert/ctd" "$BODY")
  HTTP_CODE=$(echo "$RAW" | tail -n1)
  RESPONSE=$(echo "$RAW" | sed '$d')
  if [ "$HTTP_CODE" != "200" ]; then
    echo "error: quick-convert failed ($HTTP_CODE): $RESPONSE" >&2
    exit 1
  fi
  CTD_PATH=$(echo "$RESPONSE" | jq -r '.ctd_path')
else
  CTD_PATH=$(jq -r '.ctd_cnv' "$CONFIG_FILE")
fi

SADCP_PATH=""
if [ "$HAS_SADCP_CONTOUR" = "true" ]; then
  CONTOUR_DIR=$(jq -r '.sadcp_contour_dir' "$CONFIG_FILE")
  echo "converting SADCP contour $CONTOUR_DIR ..."
  BODY=$(jq -n --arg dir "$CONTOUR_DIR" '{contour_dir: $dir}')
  RAW=$(http_post "/api/sadcp/convert" "$BODY")
  HTTP_CODE=$(echo "$RAW" | tail -n1)
  RESPONSE=$(echo "$RAW" | sed '$d')
  if [ "$HTTP_CODE" != "200" ]; then
    echo "error: sadcp-convert failed ($HTTP_CODE): $RESPONSE" >&2
    exit 1
  fi
  SADCP_PATH=$(echo "$RESPONSE" | jq -r '.sadcp_path')
elif [ "$HAS_SADCP_MAT" = "true" ]; then
  SADCP_RELATIVE=$(jq -r '.sadcp_mat_path' "$CONFIG_FILE")
  SADCP_PATH="/sadcp_data/$SADCP_RELATIVE"
fi

PASSTHROUGH_KEYS='["ctd_header_lines","ctd_fields_per_line","ctd_time_field","ctd_pressure_field",
  "ctd_temperature_field","ctd_salinity_field","ctd_badvals","ctd_time_base",
  "nav_header_lines","nav_fields_per_line","nav_time_field","nav_lat_field",
  "nav_lon_field","nav_time_base","nav_error","btrk_mode","btrk_used"]'

CAST_BODY=$(jq --argjson allowed "$PASSTHROUGH_KEYS" '
  {
    cast_name: .cast_name,
    ladcp_station: .station,
    ladcp_cast: .station,
    ladcpdo: .ladcpdo,
    ladcpup: .ladcpup,
    nav: .nav,
    lat: .lat,
    lon: .lon,
    time_start: .time_start,
    time_end: .time_end
  }
  + (to_entries | map(select(.key as $k | $allowed | index($k))) | from_entries)
' "$CONFIG_FILE")

CAST_BODY=$(echo "$CAST_BODY" | jq --arg ctd "$CTD_PATH" '. + {ctd: $ctd}')
if [ -n "$SADCP_PATH" ]; then
  CAST_BODY=$(echo "$CAST_BODY" | jq --arg sadcp "$SADCP_PATH" '. + {sadcp: $sadcp}')
fi

echo "creating cast session entry ..."
RAW=$(http_post "/api/session/casts" "$CAST_BODY")
HTTP_CODE=$(echo "$RAW" | tail -n1)
RESPONSE=$(echo "$RAW" | sed '$d')
if [ "$HTTP_CODE" != "201" ]; then
  echo "error: creating cast failed ($HTTP_CODE): $RESPONSE" >&2
  exit 1
fi

echo "generating set_cast_params.m ..."
RAW=$(http_post "/api/generate" "{}")
HTTP_CODE=$(echo "$RAW" | tail -n1)
RESPONSE=$(echo "$RAW" | sed '$d')
if [ "$HTTP_CODE" != "200" ]; then
  echo "error: /api/generate failed ($HTTP_CODE): $RESPONSE" >&2
  exit 1
fi
echo "$RESPONSE"

STATION=$(jq -r '.station' "$CONFIG_FILE")
CAST_NAME=$(jq -r '.cast_name' "$CONFIG_FILE")

echo "stopping webapp container ..."
docker stop "$CONTAINER_ID" >/dev/null
trap - EXIT

echo "running process_cast($STATION,1,0) ..."
docker run --rm -v "$STAGING_DIR/data:/data" "${MOUNT_ARGS[@]}" "$IMAGE_TAG" octave-cli --eval "process_cast($STATION,1,0)"

echo "done."
OUTPUT_MAT="$STAGING_DIR/data/V7/$CAST_NAME.mat"
if [ -f "$OUTPUT_MAT" ]; then
  echo "output: $STAGING_DIR/data/V7/$CAST_NAME.{mat,log,txt}"
else
  echo "warning: process_cast exited 0 but expected output $OUTPUT_MAT was not found -- check the log above" >&2
fi

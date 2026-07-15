FROM docker.io/gnuoctave/octave:9.2.0

LABEL org.opencontainers.image.title="ldeo-ix-octave" \
      org.opencontainers.image.description="LDEO_IX LADCP processing (Visbeck/Krahmann/Marin/Grelet), patched to run under GNU Octave" \
      org.opencontainers.image.licenses="MIT"

# Third-party LADCP processing code (see NOTICE.md) plus headless plotting
# stubs (real MATLAB/Octave has a display; this image doesn't).
COPY ldeo_ix/ /opt/ldeo_ix/
COPY stubs/   /opt/stubs/

# Function-name resolution prefers the path over builtins, so the stubs
# shadow Octave's real plotting functions without touching ldeo_ix/ itself.
ENV OCTAVE_PATH=/opt/stubs:/opt/ldeo_ix

# Mount your cruise/cast directory (containing set_cast_params.m and the
# raw data -- see examples/ and README.md) here.
WORKDIR /data

ENTRYPOINT ["octave-cli", "--no-gui"]

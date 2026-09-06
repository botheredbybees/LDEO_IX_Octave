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

# Web intake app (forms that generate set_cast_params.m) -- see webapp/.
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*
COPY webapp/requirements.txt /opt/webapp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /opt/webapp/requirements.txt
COPY webapp/ /opt/webapp/
ENV PYTHONPATH=/opt

# Real magdec replacement (ldeo_ix/loadnav.m shells out to a command
# named magdec on $PATH -- see docs/superpowers/specs/
# 2026-09-06-magdec-replacement-design.md for why this is a from-scratch
# tool rather than the original, now-unreachable, distribution).
COPY magdec/requirements.txt /opt/magdec/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /opt/magdec/requirements.txt
COPY magdec/magdec.py /usr/local/bin/magdec
RUN chmod +x /usr/local/bin/magdec

EXPOSE 8080

# Mount your cruise/cast directory (containing set_cast_params.m and the
# raw data -- see examples/ and README.md) here. Optional source-data
# mounts: /ladcp_data, /ctd_data, /sadcp_data, /navigation_data.
WORKDIR /data

ENTRYPOINT ["/opt/webapp/entrypoint.sh"]
CMD ["serve"]

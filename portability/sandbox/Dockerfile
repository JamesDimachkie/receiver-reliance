FROM python:3.14.1-slim-bookworm@sha256:5d17fc066275d26bb2ffe05bc89367dc665310200b5f4cfa8b294e97dc679bff

ENV HOME=/tmp \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0 \
    TMPDIR=/tmp \
    TZ=UTC

WORKDIR /repo
USER 65532:65532
ENTRYPOINT ["python", "-B", "/repo/portability/sandbox/expanded_gate.py"]
CMD []

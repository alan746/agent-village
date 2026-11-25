FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git procps \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir pytest \
    && git config --system safe.directory '*' \
    && git config --system init.defaultBranch main \
    && useradd --create-home --uid 1000 villager

USER villager
ENV PATH="/home/villager/.local/bin:${PATH}" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/repo
WORKDIR /repo
CMD ["sleep", "infinity"]

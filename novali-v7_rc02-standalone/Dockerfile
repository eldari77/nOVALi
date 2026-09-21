FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV NOVALI_OPERATOR_ROOT=/workspace/novali/operator_state
ENV NOVALI_STATE_ROOT=/workspace/novali/runtime_data/state

WORKDIR /workspace/novali

RUN apt-get update \
    && apt-get install -y --no-install-recommends docker-cli \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-simulation.txt /workspace/novali/
RUN pip install --no-cache-dir -r /workspace/novali/requirements.txt \
    && pip install --no-cache-dir -r /workspace/novali/requirements-simulation.txt \
    && python -c "import numpy, torch; assert torch.version.cuda is None"

COPY . /workspace/novali

RUN mkdir -p /workspace/novali/data \
    /workspace/novali/logs \
    /workspace/novali/manual_acceptance_runs \
    /workspace/novali/operator_state \
    /workspace/novali/trusted_sources \
    /workspace/novali/directive_inputs \
    /workspace/novali/runtime_data/state \
    /workspace/novali/runtime_data/logs \
    /workspace/novali/runtime_data/acceptance_evidence

EXPOSE 8787

CMD ["python", "-m", "novali_v5.web_operator", "--host", "0.0.0.0", "--port", "8787"]

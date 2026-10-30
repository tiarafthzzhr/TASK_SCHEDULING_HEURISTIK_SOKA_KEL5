FROM python:3.12-slim
ARG KUBECTL_VERSION=v1.37.0
ARG TARGETARCH=amd64
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl" -o /usr/local/bin/kubectl \
    && curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl.sha256" -o /tmp/kubectl.sha256 \
    && echo "$(cat /tmp/kubectl.sha256)  /usr/local/bin/kubectl" | sha256sum --check \
    && chmod +x /usr/local/bin/kubectl \
    && rm -rf /var/lib/apt/lists/* /tmp/kubectl.sha256
WORKDIR /app
COPY scheduler.py kube_backend.py worker.py results_server.py ./
COPY data ./data
RUN useradd --uid 10001 --create-home runner && mkdir /results && chown runner /results
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 SOKA_CLUSTER_MODE=k3s SOKA_OUTPUT_ROOT=/results
USER 10001:10001
CMD ["python3", "scheduler.py", "run", "--dataset-size", "100"]

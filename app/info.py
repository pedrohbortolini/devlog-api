"""Runtime info endpoint — multi-environment debugging tool.

Credit: suggested by a mentor (echo-server idea). Answers the question
"WHERE is this API running?" — which pod, which namespace, which image.
In Kubernetes, POD_NAMESPACE and IMAGE_TAG are injected via the Deployment
manifest; locally they fall back to defaults.
"""

import os
import socket

from fastapi import Request


def runtime_info(request: Request) -> dict:
    return {
        "hostname": socket.gethostname(),  # = pod name inside Kubernetes
        "namespace": os.environ.get("POD_NAMESPACE", "local"),
        "image_tag": os.environ.get("IMAGE_TAG", "dev"),
        "client": request.client.host if request.client else None,
        "headers": dict(request.headers),
    }

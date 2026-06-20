import shutil
import subprocess
from pathlib import Path

import jsii
from aws_cdk import BundlingOptions, ILocalBundling
from aws_cdk import aws_lambda as lambda_

# Local packages each service needs (installed with --no-deps to avoid
# workspace-resolution that pip doesn't understand)
_LOCAL_PKGS: dict[str, list[str]] = {
    "webhook": ["whatsapp", "data", "common"],
    "agent": ["core", "openclaw", "whatsapp", "data", "common"],
    "scraper": ["data", "common"],
}

# External PyPI deps (covers all transitive deps of the local packages above)
_EXTERNAL_DEPS: dict[str, list[str]] = {
    "webhook": [
        "pyyaml>=6.0",
        "boto3>=1.35",
        "aws-lambda-powertools>=3.0",
        "httpx>=0.27",
    ],
    "agent": [
        "pyyaml>=6.0",
        "boto3>=1.35",
        "aws-lambda-powertools>=3.0",
        "httpx>=0.27",
        "openai>=1.0.0",
    ],
    "scraper": [
        "pyyaml>=6.0",
        "boto3>=1.35",
        "aws-lambda-powertools>=3.0",
        "httpx>=0.27",
    ],
}


@jsii.implements(ILocalBundling)
class _LocalBundler:
    """Bundles a Lambda using the local uv installation (no Docker required)."""

    def __init__(self, repo: Path, service: str) -> None:
        self._repo = repo
        self._service = service

    def try_bundle(self, output_dir: str, options: BundlingOptions) -> bool:
        out = Path(output_dir)
        repo = self._repo

        # Install workspace packages without inter-package deps
        local_paths = [str(repo / "packages" / p) for p in _LOCAL_PKGS[self._service]]
        subprocess.run(
            ["uv", "pip", "install", "--no-deps", *local_paths, "--target", str(out)],
            check=True,
        )

        # Install external PyPI deps targeting Lambda's Amazon Linux platform
        subprocess.run(
            [
                "uv", "pip", "install",
                "--python-platform", "linux",
                "--python-version", "3.12",
                "--only-binary", ":all:",
                *_EXTERNAL_DEPS[self._service],
                "--target", str(out),
            ],
            check=True,
        )

        # Copy handler entry point
        shutil.copy(repo / "services" / self._service / "handler.py", out / "handler.py")

        # Agent Lambda needs the content directories at /var/task/agent and /var/task/shared
        if self._service == "agent":
            shutil.copytree(
                repo / "agent",
                out / "agent",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                dirs_exist_ok=True,
            )
            shutil.copytree(
                repo / "shared",
                out / "shared",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                dirs_exist_ok=True,
            )

        return True


def lambda_code(repo: Path, service: str) -> lambda_.AssetCode:
    """Return Lambda Code asset with local-first bundling, Docker fallback."""
    local_pkgs_str = " ".join(f"/asset-input/packages/{p}" for p in _LOCAL_PKGS[service])
    ext_deps_str = " ".join(_EXTERNAL_DEPS[service])
    agent_copy = (
        " && cp -r /asset-input/agent /asset-output/agent"
        " && cp -r /asset-input/shared /asset-output/shared"
        if service == "agent"
        else ""
    )
    docker_cmd = (
        f"pip install --no-deps {local_pkgs_str} -t /asset-output"
        f" && pip install {ext_deps_str} -t /asset-output"
        f" && cp /asset-input/services/{service}/handler.py /asset-output/handler.py"
        f"{agent_copy}"
    )

    return lambda_.Code.from_asset(
        str(repo),
        bundling=BundlingOptions(
            local=_LocalBundler(repo, service),
            image=lambda_.Runtime.PYTHON_3_12.bundling_image,
            command=["bash", "-c", docker_cmd],
        ),
    )

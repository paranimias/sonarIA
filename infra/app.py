import aws_cdk as cdk

from stack import SonariaStack

app = cdk.App()
stage = app.node.try_get_context("stage") or "dev"

SonariaStack(
    app,
    f"SonarIA-{stage}",
    stage=stage,
    env=cdk.Environment(account="738012852934", region="us-east-1"),
)

app.synth()

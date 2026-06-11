from pathlib import Path

import aws_cdk as cdk
from aws_cdk import (
    CfnDynamicReference,
    CfnDynamicReferenceService,
    Duration,
    RemovalPolicy,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_integrations as integrations,
    aws_dynamodb as ddb,
    aws_lambda as lambda_,
    aws_lambda_event_sources as event_sources,
    aws_sqs as sqs,
)
from constructs import Construct

from bundler import lambda_code

_REPO_ROOT = Path(__file__).parent.parent


class SonariaStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, *, stage: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── DynamoDB single-table ─────────────────────────────────────────
        table = ddb.Table(
            self,
            "Table",
            table_name=f"sonaria-{stage}",
            partition_key=ddb.Attribute(name="PK", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="SK", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            # Keep data in prod; wipe on stack deletion in dev
            removal_policy=RemovalPolicy.RETAIN if stage == "prod" else RemovalPolicy.DESTROY,
        )
        # GSI1: resolve wa_id → user_id (identity lookup)
        table.add_global_secondary_index(
            index_name="GSI1",
            partition_key=ddb.Attribute(name="GSI1PK", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="GSI1SK", type=ddb.AttributeType.STRING),
        )

        # ── SQS FIFO ──────────────────────────────────────────────────────
        dlq = sqs.Queue(
            self,
            "AgentDLQ",
            queue_name=f"sonaria-agent-dlq-{stage}.fifo",
            fifo=True,
            retention_period=Duration.days(14),
        )
        inbound_q = sqs.Queue(
            self,
            "InboundQueue",
            queue_name=f"sonaria-inbound-{stage}.fifo",
            fifo=True,
            content_based_deduplication=False,
            # Visibility timeout must be >= agent Lambda timeout (300s); 1800s gives safe margin
            visibility_timeout=Duration.seconds(1800),
            retention_period=Duration.days(4),
            dead_letter_queue=sqs.DeadLetterQueue(queue=dlq, max_receive_count=3),
        )

        # ── SSM SecureString references (created manually — see README) ───
        # Generates {{resolve:ssm-secure:...}} which CloudFormation resolves at
        # deploy time. The SSM params must exist before running cdk deploy.
        def _ssm(path: str) -> str:
            return CfnDynamicReference(
                CfnDynamicReferenceService.SSM,
                f"/sonaria/{stage}/{path}",
            ).to_string()

        # ── Lambda: webhook ───────────────────────────────────────────────
        webhook_fn = lambda_.Function(
            self,
            "WebhookFn",
            function_name=f"sonaria-webhook-{stage}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_code(_REPO_ROOT, "webhook"),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "SONARIA_TABLE_NAME": table.table_name,
                "SQS_QUEUE_URL": inbound_q.queue_url,
                "META_APP_SECRET": _ssm("meta/app-secret"),
                "META_VERIFY_TOKEN": _ssm("meta/verify-token"),
            },
        )
        table.grant_write_data(webhook_fn)
        inbound_q.grant_send_messages(webhook_fn)

        # ── Lambda: agent ─────────────────────────────────────────────────
        agent_fn = lambda_.Function(
            self,
            "AgentFn",
            function_name=f"sonaria-agent-{stage}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_code(_REPO_ROOT, "agent"),
            timeout=Duration.seconds(300),
            memory_size=512,
            environment={
                "SONARIA_TABLE_NAME": table.table_name,
                "META_ACCESS_TOKEN": _ssm("meta/access-token"),
                "OPENAI_API_KEY": _ssm("openai/api-key"),
                # Content dirs are bundled into /var/task/
                "SHARED_DIR": "/var/task/shared",
                "AGENT_DIR": "/var/task/agent",
            },
        )
        table.grant_read_write_data(agent_fn)
        agent_fn.add_event_source(
            event_sources.SqsEventSource(
                inbound_q,
                batch_size=1,       # process one message at a time
                max_concurrency=5,  # at most 5 parallel agent executions
            )
        )

        # ── API Gateway HTTP API ──────────────────────────────────────────
        http_api = apigw.HttpApi(
            self,
            "HttpApi",
            api_name=f"sonaria-{stage}",
        )
        http_api.add_routes(
            path="/webhook",
            methods=[apigw.HttpMethod.GET, apigw.HttpMethod.POST],
            integration=integrations.HttpLambdaIntegration("WebhookIntegration", webhook_fn),
        )

        # ── Stack outputs ─────────────────────────────────────────────────
        cdk.CfnOutput(
            self,
            "WebhookUrl",
            value=f"{http_api.url}webhook",
            description="Register this URL as the Meta webhook endpoint",
        )
        cdk.CfnOutput(self, "TableName", value=table.table_name)
        cdk.CfnOutput(self, "QueueUrl", value=inbound_q.queue_url)

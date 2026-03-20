"""L3 construct for health check infrastructure.

Bundles the health check Lambda function, EventBridge schedule rule,
and IAM permissions into a reusable construct.
"""

import os
from typing import Any

from aws_cdk import Duration
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct


class HealthChecker(Construct):
    """L3 construct for the Cirrus health check subsystem.

    Creates a Lambda function triggered by an EventBridge schedule rule
    every 60 seconds, with least-privilege IAM permissions for EC2,
    CloudWatch, SSM, and EventBridge operations.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        code_path: str,
        environment: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        env_vars: dict[str, str] = {
            "MONITORED_TAG_KEY": "cirrus:monitored",
            "MONITORED_TAG_VALUE": "true",
            "HEALTH_CHECK_TIMEOUT": "10",
            "CRITICAL_PROCESSES": "httpd,nginx,docker",
        }
        if environment:
            env_vars.update(environment)

        self.function = lambda_.Function(
            self,
            "HealthCheckFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="src.health_checker.handler.handler",
            code=lambda_.Code.from_asset(code_path),
            memory_size=256,
            timeout=Duration.seconds(30),
            environment=env_vars,
            tracing=lambda_.Tracing.ACTIVE,
            description="Cirrus fleet health checker - runs every 60s",
        )

        self.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:DescribeInstances",
                    "ec2:DescribeInstanceStatus",
                ],
                resources=["*"],
            )
        )
        self.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "cloudwatch:GetMetricData",
                    "cloudwatch:PutMetricData",
                ],
                resources=["*"],
            )
        )
        self.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "events:PutEvents",
                ],
                resources=["*"],
            )
        )
        self.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ssm:SendCommand",
                    "ssm:GetCommandInvocation",
                ],
                resources=["*"],
            )
        )
        self.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:GetLogEvents",
                    "logs:FilterLogEvents",
                ],
                resources=["*"],
            )
        )

        self.schedule_rule = events.Rule(
            self,
            "HealthCheckSchedule",
            schedule=events.Schedule.rate(Duration.minutes(1)),
            description="Triggers health check Lambda every 60 seconds",
        )
        self.schedule_rule.add_target(
            targets.LambdaFunction(self.function)
        )

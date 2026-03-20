"""CDK stack for health monitoring infrastructure.

Deploys the health check Lambda function, EventBridge schedule rule,
and related IAM permissions using the HealthChecker L3 construct.
"""

import os
from typing import Any

from aws_cdk import Stack
from constructs import Construct

from infra.constructs.health_checker import HealthChecker


class MonitoringStack(Stack):
    """Stack for the Cirrus fleet health monitoring subsystem.

    Creates the periodic health check Lambda and EventBridge schedule
    for continuous fleet monitoring.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        code_path = os.path.join(os.path.dirname(__file__), "..", "..")

        self.health_checker = HealthChecker(
            self,
            "HealthChecker",
            code_path=code_path,
            environment={
                "MONITORED_TAG_KEY": "cirrus:monitored",
                "MONITORED_TAG_VALUE": "true",
                "HEALTH_CHECK_TIMEOUT": "10",
                "CRITICAL_PROCESSES": "httpd,nginx,docker",
            },
        )

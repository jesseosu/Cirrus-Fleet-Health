"""CDK stack for the remediation pipeline infrastructure.

Deploys the Step Functions state machine, remediation Lambdas,
DynamoDB incidents table, and EventBridge rules.
"""

import os
from typing import Any

from aws_cdk import Stack
from aws_cdk import aws_sns as sns
from constructs import Construct

from infra.constructs.remediation_pipeline import RemediationPipeline


class RemediationStack(Stack):
    """Stack for the Cirrus remediation pipeline.

    Creates the Step Functions orchestrated remediation workflow,
    including diagnostic, remediation, verification, escalation,
    and incident logging Lambda functions.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        escalation_topic: sns.ITopic,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        code_path = os.path.join(os.path.dirname(__file__), "..", "..")

        self.pipeline = RemediationPipeline(
            self,
            "RemediationPipeline",
            code_path=code_path,
            escalation_topic=escalation_topic,
            environment={
                "MONITORED_TAG_KEY": "cirrus:monitored",
                "MONITORED_TAG_VALUE": "true",
            },
        )

        self.incidents_table = self.pipeline.incidents_table
        self.state_machine = self.pipeline.state_machine

"""Integration tests for Step Functions state machine definition.

Validates the CDK-generated state machine structure by synthesizing
the stack and inspecting the resulting CloudFormation template.
"""

import json
from typing import Any

import aws_cdk as cdk
import pytest
from aws_cdk import assertions

from infra.stacks.observability_stack import ObservabilityStack
from infra.stacks.remediation_stack import RemediationStack


@pytest.fixture
def template() -> assertions.Template:
    """Synthesize the remediation stack and return the CF template."""
    app = cdk.App()
    obs_stack = ObservabilityStack(app, "TestObsStack")
    rem_stack = RemediationStack(
        app,
        "TestRemStack",
        escalation_topic=obs_stack.escalation_topic,
    )
    return assertions.Template.from_stack(rem_stack)


class TestStepFunctionsDefinition:
    """Tests for the Step Functions state machine in the remediation stack."""

    def test_state_machine_exists(self, template: assertions.Template) -> None:
        """Test that a Step Functions state machine is created."""
        template.resource_count_is("AWS::StepFunctions::StateMachine", 1)

    def test_dynamodb_table_created(self, template: assertions.Template) -> None:
        """Test that the DynamoDB incidents table is created."""
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "TableName": "cirrus-incidents",
                "KeySchema": [
                    {"AttributeName": "PK", "KeyType": "HASH"},
                    {"AttributeName": "SK", "KeyType": "RANGE"},
                ],
                "BillingMode": "PAY_PER_REQUEST",
                "PointInTimeRecoverySpecification": {
                    "PointInTimeRecoveryEnabled": True,
                },
            },
        )

    def test_lambda_functions_created(self, template: assertions.Template) -> None:
        """Test that all remediation Lambda functions are created."""
        # Should have 5 Lambda functions: diagnostics, remediator, verifier,
        # escalation, incident_logger
        template.resource_count_is("AWS::Lambda::Function", 5)

    def test_eventbridge_rule_created(self, template: assertions.Template) -> None:
        """Test that the EventBridge rule for unhealthy events exists."""
        template.has_resource_properties(
            "AWS::Events::Rule",
            {
                "EventPattern": {
                    "source": ["cirrus.health"],
                    "detail-type": [
                        "cirrus.health.UNHEALTHY",
                        "cirrus.health.CRITICAL",
                    ],
                },
            },
        )

    def test_lambda_runtime_python312(self, template: assertions.Template) -> None:
        """Test that all Lambda functions use Python 3.12."""
        resources = template.find_resources("AWS::Lambda::Function")
        for logical_id, resource in resources.items():
            props = resource.get("Properties", {})
            assert props.get("Runtime") == "python3.12", (
                f"{logical_id} does not use python3.12"
            )

    def test_lambda_tracing_enabled(self, template: assertions.Template) -> None:
        """Test that X-Ray tracing is enabled on all Lambdas."""
        resources = template.find_resources("AWS::Lambda::Function")
        for logical_id, resource in resources.items():
            props = resource.get("Properties", {})
            tracing = props.get("TracingConfig", {})
            assert tracing.get("Mode") == "Active", (
                f"{logical_id} does not have Active tracing"
            )

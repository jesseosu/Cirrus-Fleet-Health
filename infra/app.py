#!/usr/bin/env python3
"""CDK app entry point for the Cirrus fleet health platform.

Instantiates and connects all three stacks: monitoring, remediation,
and observability.
"""

import aws_cdk as cdk

from stacks.monitoring_stack import MonitoringStack
from stacks.observability_stack import ObservabilityStack
from stacks.remediation_stack import RemediationStack

app = cdk.App()

# Get configuration from CDK context
notification_email = app.node.try_get_context("notification_email") or ""

# Observability stack first (provides SNS topics)
observability = ObservabilityStack(
    app,
    "CirrusObservabilityStack",
    notification_email=notification_email,
    description="Cirrus - CloudWatch dashboard, alarms, and SNS topics",
)

# Monitoring stack (health check Lambda + EventBridge schedule)
monitoring = MonitoringStack(
    app,
    "CirrusMonitoringStack",
    description="Cirrus - Fleet health check Lambda and EventBridge schedule",
)

# Remediation stack (Step Functions + Lambdas + DynamoDB)
remediation = RemediationStack(
    app,
    "CirrusRemediationStack",
    escalation_topic=observability.escalation_topic,
    description="Cirrus - Remediation pipeline with Step Functions",
)

app.synth()

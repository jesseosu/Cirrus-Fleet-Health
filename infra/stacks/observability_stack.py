"""CDK stack for observability infrastructure.

Deploys CloudWatch dashboard, alarms, and SNS topics for the Cirrus
fleet health platform.
"""

from typing import Any

from aws_cdk import Stack
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subscriptions
from constructs import Construct

from infra.constructs.fleet_dashboard import FleetDashboard


class ObservabilityStack(Stack):
    """Stack for Cirrus observability components.

    Creates SNS topics for escalation and alarm notifications,
    a CloudWatch dashboard, and critical alarms.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        notification_email: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # SNS topic for escalation alerts
        self.escalation_topic = sns.Topic(
            self,
            "EscalationTopic",
            topic_name="cirrus-escalation-alerts",
            display_name="Cirrus Fleet Health Escalation Alerts",
        )

        # SNS topic for CloudWatch alarm notifications
        self.alarm_topic = sns.Topic(
            self,
            "AlarmTopic",
            topic_name="cirrus-alarm-notifications",
            display_name="Cirrus CloudWatch Alarm Notifications",
        )

        # Email subscription (if provided)
        if notification_email:
            self.escalation_topic.add_subscription(
                subscriptions.EmailSubscription(notification_email)
            )
            self.alarm_topic.add_subscription(
                subscriptions.EmailSubscription(notification_email)
            )

        # Fleet dashboard and alarms
        self.dashboard = FleetDashboard(
            self,
            "FleetDashboard",
            alarm_topic=self.alarm_topic,
        )

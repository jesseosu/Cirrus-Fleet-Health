"""L3 construct for CloudWatch dashboard and alarms.

Creates a comprehensive fleet health dashboard with widgets for
health status, remediation metrics, and incident tracking.
"""

from typing import Any

from aws_cdk import Duration
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_sns as sns
from constructs import Construct


class FleetDashboard(Construct):
    """L3 construct for the Cirrus CloudWatch dashboard and alarms.

    Creates dashboard widgets for fleet health overview, remediation
    success rates, and active incident counts, plus critical alarms.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        alarm_topic: sns.ITopic,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        namespace = "Cirrus/Fleet"

        # Metrics
        healthy_count = cloudwatch.Metric(
            namespace=namespace,
            metric_name="HealthyCount",
            statistic="Average",
            period=Duration.minutes(1),
            label="Healthy Instances",
        )
        unhealthy_count = cloudwatch.Metric(
            namespace=namespace,
            metric_name="UnhealthyCount",
            statistic="Average",
            period=Duration.minutes(1),
            label="Unhealthy Instances",
        )

        # Dashboard
        self.dashboard = cloudwatch.Dashboard(
            self,
            "FleetHealthDashboard",
            dashboard_name="Cirrus-Fleet-Health",
            period_override=cloudwatch.PeriodOverride.AUTO,
        )

        # Fleet health summary widget
        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Fleet Health Summary",
                left=[healthy_count, unhealthy_count],
                width=12,
                height=6,
                left_y_axis=cloudwatch.YAxisProps(label="Count", min=0),
            ),
            cloudwatch.SingleValueWidget(
                title="Current Fleet Status",
                metrics=[healthy_count, unhealthy_count],
                width=12,
                height=6,
            ),
        )

        # Remediation metrics
        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Remediation Success/Failure Rate",
                left=[
                    cloudwatch.Metric(
                        namespace=namespace,
                        metric_name="RemediationSuccess",
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="Successful Remediations",
                    ),
                    cloudwatch.Metric(
                        namespace=namespace,
                        metric_name="RemediationFailure",
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="Failed Remediations",
                    ),
                ],
                width=12,
                height=6,
            ),
            cloudwatch.GraphWidget(
                title="Health Check Latency",
                left=[
                    cloudwatch.Metric(
                        namespace=namespace,
                        metric_name="HealthCheckDuration",
                        statistic="p50",
                        period=Duration.minutes(5),
                        label="p50",
                    ),
                    cloudwatch.Metric(
                        namespace=namespace,
                        metric_name="HealthCheckDuration",
                        statistic="p95",
                        period=Duration.minutes(5),
                        label="p95",
                    ),
                    cloudwatch.Metric(
                        namespace=namespace,
                        metric_name="HealthCheckDuration",
                        statistic="p99",
                        period=Duration.minutes(5),
                        label="p99",
                    ),
                ],
                width=12,
                height=6,
            ),
        )

        # Active incidents widget
        self.dashboard.add_widgets(
            cloudwatch.SingleValueWidget(
                title="Active Incidents",
                metrics=[
                    cloudwatch.Metric(
                        namespace=namespace,
                        metric_name="ActiveIncidents",
                        statistic="Maximum",
                        period=Duration.minutes(1),
                        label="Active Incidents",
                    ),
                ],
                width=8,
                height=4,
            ),
        )

        # Alarms
        self.unhealthy_warning = cloudwatch.Alarm(
            self,
            "UnhealthyWarningAlarm",
            alarm_name="cirrus-unhealthy-instances-warning",
            metric=unhealthy_count,
            threshold=0,
            comparison_operator=(
                cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
            ),
            evaluation_periods=5,
            datapoints_to_alarm=5,
            alarm_description=(
                "WARNING: Unhealthy instances detected for 5+ minutes"
            ),
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        self.unhealthy_warning.add_alarm_action(
            cw_actions.SnsAction(alarm_topic)
        )

        self.unhealthy_critical = cloudwatch.Alarm(
            self,
            "UnhealthyCriticalAlarm",
            alarm_name="cirrus-unhealthy-instances-critical",
            metric=unhealthy_count,
            threshold=3,
            comparison_operator=(
                cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
            ),
            evaluation_periods=5,
            datapoints_to_alarm=5,
            alarm_description=(
                "CRITICAL: More than 3 unhealthy instances for 5+ minutes"
            ),
            treat_missing_data=cloudwatch.TreatMissingData.BREACHING,
        )
        self.unhealthy_critical.add_alarm_action(
            cw_actions.SnsAction(alarm_topic)
        )

        self.health_check_errors = cloudwatch.Alarm(
            self,
            "HealthCheckErrorAlarm",
            alarm_name="cirrus-health-check-errors",
            metric=cloudwatch.Metric(
                namespace="AWS/Lambda",
                metric_name="Errors",
                statistic="Sum",
                period=Duration.minutes(5),
                dimensions_map={
                    "FunctionName": "CirrusHealthChecker",
                },
            ),
            threshold=5,
            comparison_operator=(
                cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
            ),
            evaluation_periods=1,
            alarm_description=(
                "Health check Lambda errors > 5 in 5 minutes"
            ),
        )
        self.health_check_errors.add_alarm_action(
            cw_actions.SnsAction(alarm_topic)
        )

        self.sfn_execution_failures = cloudwatch.Alarm(
            self,
            "SfnExecutionFailureAlarm",
            alarm_name="cirrus-sfn-execution-failures",
            metric=cloudwatch.Metric(
                namespace="AWS/States",
                metric_name="ExecutionsFailed",
                statistic="Sum",
                period=Duration.minutes(5),
                dimensions_map={
                    "StateMachineArn": "cirrus-remediation-pipeline",
                },
            ),
            threshold=0,
            comparison_operator=(
                cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
            ),
            evaluation_periods=1,
            alarm_description=(
                "Step Functions execution failures detected"
            ),
        )
        self.sfn_execution_failures.add_alarm_action(
            cw_actions.SnsAction(alarm_topic)
        )

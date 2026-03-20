"""L3 construct for the Step Functions remediation pipeline.

Bundles the Step Functions state machine, all remediation Lambdas,
EventBridge rule, DynamoDB table, and IAM permissions.
"""

from typing import Any

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_sns as sns
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct


class RemediationPipeline(Construct):
    """L3 construct for the Cirrus remediation pipeline.

    Creates the Step Functions state machine that orchestrates the
    detect → diagnose → remediate → verify → escalate workflow,
    along with all supporting Lambda functions and DynamoDB table.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        code_path: str,
        escalation_topic: sns.ITopic,
        environment: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        env_vars: dict[str, str] = environment or {}

        # DynamoDB incidents table
        self.incidents_table = dynamodb.Table(
            self,
            "IncidentsTable",
            table_name="cirrus-incidents",
            partition_key=dynamodb.Attribute(
                name="PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="SK", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="ttl",
        )

        # Lambda environment with table name and topic ARN
        lambda_env: dict[str, str] = {
            "INCIDENTS_TABLE_NAME": self.incidents_table.table_name,
            "ESCALATION_TOPIC_ARN": escalation_topic.topic_arn,
            **env_vars,
        }

        # Create Lambda functions
        self.diagnostics_fn = self._create_lambda(
            "DiagnosticsFunction",
            "src.diagnostics.handler.handler",
            code_path,
            lambda_env,
            "Collects diagnostic data for unhealthy instances",
        )
        self.remediator_fn = self._create_lambda(
            "RemediatorFunction",
            "src.remediator.handler.handler",
            code_path,
            lambda_env,
            "Executes remediation actions on instances",
        )
        self.verifier_fn = self._create_lambda(
            "VerifierFunction",
            "src.verifier.handler.handler",
            code_path,
            lambda_env,
            "Verifies health post-remediation",
        )
        self.escalation_fn = self._create_lambda(
            "EscalationFunction",
            "src.escalation.handler.handler",
            code_path,
            lambda_env,
            "Formats and publishes escalation alerts",
        )
        self.incident_logger_fn = self._create_lambda(
            "IncidentLoggerFunction",
            "src.incident_logger.handler.handler",
            code_path,
            lambda_env,
            "Records incidents to DynamoDB",
        )

        # Grant DynamoDB access to incident logger
        self.incidents_table.grant_read_write_data(
            self.incident_logger_fn
        )

        # Grant SNS publish to escalation function
        escalation_topic.grant_publish(self.escalation_fn)

        # Grant EC2/SSM/CW access to relevant functions
        for fn in [
            self.diagnostics_fn,
            self.remediator_fn,
            self.verifier_fn,
        ]:
            fn.add_to_role_policy(
                iam.PolicyStatement(
                    actions=[
                        "ec2:DescribeInstances",
                        "ec2:DescribeInstanceStatus",
                        "ec2:RebootInstances",
                        "ec2:TerminateInstances",
                        "ssm:SendCommand",
                        "ssm:GetCommandInvocation",
                        "cloudwatch:GetMetricData",
                        "cloudwatch:GetMetricStatistics",
                        "cloudwatch:PutMetricData",
                        "logs:GetLogEvents",
                        "logs:FilterLogEvents",
                        "autoscaling:DescribeAutoScalingInstances",
                        "events:PutEvents",
                    ],
                    resources=["*"],
                )
            )

        # Build Step Functions state machine
        self.state_machine = self._build_state_machine()

        # EventBridge rule for unhealthy/critical events
        self.event_rule = events.Rule(
            self,
            "UnhealthyEventRule",
            event_pattern=events.EventPattern(
                source=["cirrus.health"],
                detail_type=[
                    "cirrus.health.UNHEALTHY",
                    "cirrus.health.CRITICAL",
                ],
            ),
            description="Routes unhealthy events to remediation pipeline",
        )
        self.event_rule.add_target(
            targets.SfnStateMachine(self.state_machine)
        )

    def _create_lambda(
        self,
        function_id: str,
        handler_path: str,
        code_path: str,
        environment: dict[str, str],
        description: str,
    ) -> lambda_.Function:
        """Create a Lambda function with standard configuration."""
        return lambda_.Function(
            self,
            function_id,
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler=handler_path,
            code=lambda_.Code.from_asset(code_path),
            memory_size=256,
            timeout=Duration.seconds(300),
            environment=environment,
            tracing=lambda_.Tracing.ACTIVE,
            description=f"Cirrus - {description}",
        )

    def _build_state_machine(self) -> sfn.StateMachine:
        """Build the Step Functions state machine for remediation."""
        # Log incident (DETECTED)
        log_detected = tasks.LambdaInvoke(
            self,
            "LogIncidentDetected",
            lambda_function=self.incident_logger_fn,
            payload=sfn.TaskInput.from_object({
                "action": "create",
                "instance_id": sfn.JsonPath.string_at("$.detail.instance_id"),
                "severity": sfn.JsonPath.string_at("$.detail.severity"),
                "checks_failed": sfn.JsonPath.list_at(
                    "$.detail.failed_checks"
                ),
            }),
            result_path="$.incident",
            retry_on_service_exceptions=True,
        )
        log_detected.add_retry(
            errors=["States.TaskFailed"],
            max_attempts=2,
            interval=Duration.seconds(2),
            backoff_rate=2.0,
        )

        # Run diagnostics
        run_diagnostics = tasks.LambdaInvoke(
            self,
            "RunDiagnostics",
            lambda_function=self.diagnostics_fn,
            payload=sfn.TaskInput.from_object({
                "instance_id": sfn.JsonPath.string_at(
                    "$.detail.instance_id"
                ),
            }),
            result_path="$.diagnostics",
            retry_on_service_exceptions=True,
        )
        run_diagnostics.add_retry(
            errors=["States.TaskFailed"],
            max_attempts=2,
            interval=Duration.seconds(5),
            backoff_rate=2.0,
        )

        # Update incident to DIAGNOSED
        log_diagnosed = tasks.LambdaInvoke(
            self,
            "LogIncidentDiagnosed",
            lambda_function=self.incident_logger_fn,
            payload=sfn.TaskInput.from_object({
                "action": "update",
                "instance_id": sfn.JsonPath.string_at(
                    "$.detail.instance_id"
                ),
                "pk": sfn.JsonPath.string_at(
                    "$.incident.Payload.body.pk"
                ) if False else sfn.JsonPath.format(
                    "INSTANCE#{}",
                    sfn.JsonPath.string_at("$.detail.instance_id"),
                ),
                "sk": sfn.JsonPath.string_at(
                    "$.incident.Payload.body.sk"
                ) if False else sfn.JsonPath.format(
                    "INCIDENT#{}",
                    sfn.JsonPath.string_at(
                        "$.incident.Payload.body.detected_at"
                    ),
                ),
                "status": "DIAGNOSED",
            }),
            result_path="$.diagnosed_log",
            retry_on_service_exceptions=True,
        )

        # Check if failure is UNKNOWN (needs immediate escalation)
        is_unknown_failure = sfn.Choice(
            self,
            "IsUnknownFailure",
        )

        # Execute remediation
        execute_remediation = tasks.LambdaInvoke(
            self,
            "ExecuteRemediation",
            lambda_function=self.remediator_fn,
            payload=sfn.TaskInput.from_object({
                "instance_id": sfn.JsonPath.string_at(
                    "$.detail.instance_id"
                ),
                "body": sfn.JsonPath.object_at(
                    "$.diagnostics.Payload.body"
                ),
            }),
            result_path="$.remediation",
            retry_on_service_exceptions=True,
        )
        execute_remediation.add_retry(
            errors=["States.TaskFailed"],
            max_attempts=2,
            interval=Duration.seconds(5),
            backoff_rate=2.0,
        )

        # Update incident to REMEDIATED
        log_remediated = tasks.LambdaInvoke(
            self,
            "LogIncidentRemediated",
            lambda_function=self.incident_logger_fn,
            payload=sfn.TaskInput.from_object({
                "action": "update",
                "instance_id": sfn.JsonPath.string_at(
                    "$.detail.instance_id"
                ),
                "pk": sfn.JsonPath.format(
                    "INSTANCE#{}",
                    sfn.JsonPath.string_at("$.detail.instance_id"),
                ),
                "sk": sfn.JsonPath.format(
                    "INCIDENT#{}",
                    sfn.JsonPath.string_at(
                        "$.incident.Payload.body.detected_at"
                    ),
                ),
                "status": "REMEDIATED",
            }),
            result_path="$.remediated_log",
            retry_on_service_exceptions=True,
        )

        # Wait for stabilization
        wait_for_stabilization = sfn.Wait(
            self,
            "WaitForStabilization",
            time=sfn.WaitTime.duration(Duration.seconds(60)),
        )

        # Verify health
        verify_health = tasks.LambdaInvoke(
            self,
            "VerifyHealth",
            lambda_function=self.verifier_fn,
            payload=sfn.TaskInput.from_object({
                "instance_id": sfn.JsonPath.string_at(
                    "$.detail.instance_id"
                ),
            }),
            result_path="$.verification",
            retry_on_service_exceptions=True,
        )
        verify_health.add_retry(
            errors=["States.TaskFailed"],
            max_attempts=2,
            interval=Duration.seconds(5),
            backoff_rate=2.0,
        )

        # Check verification result
        is_healthy = sfn.Choice(
            self,
            "IsHealthy",
        )

        # Log resolved
        log_resolved = tasks.LambdaInvoke(
            self,
            "LogIncidentResolved",
            lambda_function=self.incident_logger_fn,
            payload=sfn.TaskInput.from_object({
                "action": "update",
                "instance_id": sfn.JsonPath.string_at(
                    "$.detail.instance_id"
                ),
                "pk": sfn.JsonPath.format(
                    "INSTANCE#{}",
                    sfn.JsonPath.string_at("$.detail.instance_id"),
                ),
                "sk": sfn.JsonPath.format(
                    "INCIDENT#{}",
                    sfn.JsonPath.string_at(
                        "$.incident.Payload.body.detected_at"
                    ),
                ),
                "status": "RESOLVED",
            }),
            result_path="$.resolved_log",
            retry_on_service_exceptions=True,
        )

        # Escalate
        escalate = tasks.LambdaInvoke(
            self,
            "Escalate",
            lambda_function=self.escalation_fn,
            payload=sfn.TaskInput.from_object({
                "instance_id": sfn.JsonPath.string_at(
                    "$.detail.instance_id"
                ),
                "severity": sfn.JsonPath.string_at("$.detail.severity"),
            }),
            result_path="$.escalation",
            retry_on_service_exceptions=True,
        )

        # Log escalated
        log_escalated = tasks.LambdaInvoke(
            self,
            "LogIncidentEscalated",
            lambda_function=self.incident_logger_fn,
            payload=sfn.TaskInput.from_object({
                "action": "update",
                "instance_id": sfn.JsonPath.string_at(
                    "$.detail.instance_id"
                ),
                "pk": sfn.JsonPath.format(
                    "INSTANCE#{}",
                    sfn.JsonPath.string_at("$.detail.instance_id"),
                ),
                "sk": sfn.JsonPath.format(
                    "INCIDENT#{}",
                    sfn.JsonPath.string_at(
                        "$.incident.Payload.body.detected_at"
                    ),
                ),
                "status": "ESCALATED",
            }),
            result_path="$.escalated_log",
            retry_on_service_exceptions=True,
        )

        end_state = sfn.Succeed(self, "End")

        # Wire the state machine
        escalation_chain = escalate.next(log_escalated).next(end_state)

        is_healthy.when(
            sfn.Condition.boolean_equals(
                "$.verification.Payload.body.is_healthy", True
            ),
            log_resolved.next(end_state),
        ).otherwise(escalation_chain)

        remediation_chain = (
            execute_remediation
            .next(log_remediated)
            .next(wait_for_stabilization)
            .next(verify_health)
            .next(is_healthy)
        )

        # Add catch for remediation failures
        execute_remediation.add_catch(
            escalation_chain,
            errors=["States.ALL"],
            result_path="$.error",
        )

        is_unknown_failure.when(
            sfn.Condition.string_equals(
                "$.diagnostics.Payload.body.failure_classification.failure_type",
                "UNKNOWN",
            ),
            escalation_chain,
        ).otherwise(remediation_chain)

        # Add catch for diagnostics failures
        run_diagnostics.add_catch(
            escalation_chain,
            errors=["States.ALL"],
            result_path="$.error",
        )

        definition = (
            log_detected
            .next(run_diagnostics)
            .next(log_diagnosed)
            .next(is_unknown_failure)
        )

        return sfn.StateMachine(
            self,
            "RemediationStateMachine",
            state_machine_name="cirrus-remediation-pipeline",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=Duration.minutes(15),
            tracing_enabled=True,
        )

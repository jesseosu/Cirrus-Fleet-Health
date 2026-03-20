"""Seed DynamoDB Local with sample incident data for development.

Populates the cirrus-incidents table with realistic sample incidents
covering various failure types and lifecycle states.
"""

import uuid
from datetime import datetime, timedelta, timezone

import boto3


def create_table(dynamodb: boto3.resource) -> None:
    """Create the cirrus-incidents table if it doesn't exist."""
    try:
        dynamodb.create_table(
            TableName="cirrus-incidents",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        print("Table 'cirrus-incidents' created.")
    except dynamodb.meta.client.exceptions.ResourceInUseException:
        print("Table 'cirrus-incidents' already exists.")


def seed_incidents(table: boto3.resource) -> None:
    """Insert sample incident records."""
    now = datetime.now(timezone.utc)
    sample_incidents = [
        {
            "PK": "INSTANCE#i-0abc123def456",
            "SK": f"INCIDENT#{(now - timedelta(hours=2)).isoformat()}",
            "incident_id": str(uuid.uuid4()),
            "instance_id": "i-0abc123def456",
            "severity": "UNHEALTHY",
            "status": "RESOLVED",
            "failure_type": "DISK_FULL",
            "checks_failed": ["cloudwatch_metrics"],
            "remediation_action": "clear_disk",
            "remediation_result": {
                "action_taken": "clear_disk",
                "success": True,
                "details": {"freed_mb": 2048},
                "duration_ms": 15000,
            },
            "detected_at": (now - timedelta(hours=2)).isoformat(),
            "diagnosed_at": (now - timedelta(hours=2, minutes=-2)).isoformat(),
            "remediated_at": (now - timedelta(hours=2, minutes=-5)).isoformat(),
            "resolved_at": (now - timedelta(hours=2, minutes=-7)).isoformat(),
        },
        {
            "PK": "INSTANCE#i-0def789ghi012",
            "SK": f"INCIDENT#{(now - timedelta(hours=1)).isoformat()}",
            "incident_id": str(uuid.uuid4()),
            "instance_id": "i-0def789ghi012",
            "severity": "CRITICAL",
            "status": "ESCALATED",
            "failure_type": "INSTANCE_UNREACHABLE",
            "checks_failed": ["ec2_status", "process_health", "endpoint_health"],
            "remediation_action": "replace_instance",
            "remediation_result": {
                "action_taken": "replace_instance",
                "success": True,
                "details": {"current_state": "shutting-down"},
                "duration_ms": 5000,
            },
            "detected_at": (now - timedelta(hours=1)).isoformat(),
            "diagnosed_at": (now - timedelta(hours=1, minutes=-2)).isoformat(),
            "remediated_at": (now - timedelta(hours=1, minutes=-4)).isoformat(),
            "escalated_at": (now - timedelta(hours=1, minutes=-6)).isoformat(),
        },
        {
            "PK": "INSTANCE#i-0ghi345jkl678",
            "SK": f"INCIDENT#{(now - timedelta(minutes=30)).isoformat()}",
            "incident_id": str(uuid.uuid4()),
            "instance_id": "i-0ghi345jkl678",
            "severity": "UNHEALTHY",
            "status": "RESOLVED",
            "failure_type": "PROCESS_CRASHED",
            "checks_failed": ["process_health"],
            "remediation_action": "restart_service",
            "remediation_result": {
                "action_taken": "restart_service:httpd",
                "success": True,
                "details": {"service": "httpd", "status": "active"},
                "duration_ms": 8000,
            },
            "detected_at": (now - timedelta(minutes=30)).isoformat(),
            "diagnosed_at": (now - timedelta(minutes=28)).isoformat(),
            "remediated_at": (now - timedelta(minutes=25)).isoformat(),
            "resolved_at": (now - timedelta(minutes=23)).isoformat(),
        },
        {
            "PK": "INSTANCE#i-0mno901pqr234",
            "SK": f"INCIDENT#{(now - timedelta(minutes=10)).isoformat()}",
            "incident_id": str(uuid.uuid4()),
            "instance_id": "i-0mno901pqr234",
            "severity": "UNHEALTHY",
            "status": "DETECTED",
            "failure_type": None,
            "checks_failed": ["cloudwatch_metrics", "endpoint_health"],
            "detected_at": (now - timedelta(minutes=10)).isoformat(),
        },
    ]

    with table.batch_writer() as batch:
        for item in sample_incidents:
            clean_item = {k: v for k, v in item.items() if v is not None}
            batch.put_item(Item=clean_item)
            print(f"Inserted incident for {clean_item['instance_id']}")


def main() -> None:
    """Main entry point for seeding data."""
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-east-1",
        aws_access_key_id="fakekey",
        aws_secret_access_key="fakesecret",
    )
    create_table(dynamodb)
    table = dynamodb.Table("cirrus-incidents")
    seed_incidents(table)
    print("Seeding complete!")


if __name__ == "__main__":
    main()

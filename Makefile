.PHONY: lint typecheck test synth deploy clean seed

lint:
	flake8 src/ tests/ infra/

typecheck:
	mypy src/ infra/ --ignore-missing-imports

test:
	pytest tests/ -v --cov=src --cov-report=term-missing

synth:
	cd infra && cdk synth

deploy:
	cd infra && cdk deploy --all

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

seed:
	docker-compose up -d dynamodb-local
	python scripts/seed_data/seed_incidents.py

# E2E Smoke Test Checklist

## Prerequisites
- [ ] AWS credentials configured
- [ ] CDK CLI installed (`npm i -g aws-cdk`)
- [ ] Node.js 20+ installed

## Infrastructure
- [ ] Run `cd infra && npm i && npx cdk deploy --all`
- [ ] Note stack outputs: ApiUrl, UserPoolId, UserPoolClientId, SpaUrl, OrderQueueUrl

## Frontend
- [ ] Create `frontend/.env` with stack outputs
- [ ] Run `cd frontend && npm i && npm run build`
- [ ] Upload `dist/` to S3 bucket

## User Flow
- [ ] Visit SPA URL
- [ ] Sign up with email + password (min 8 chars, 1 uppercase, 1 digit)
- [ ] Confirm email via verification code
- [ ] Sign in
- [ ] Browse products on home page
- [ ] Use search bar to find products
- [ ] View product detail page
- [ ] Verify AI recommendations appear (or fallback)
- [ ] Add item to cart (verify stock validation)
- [ ] View cart with calculated total
- [ ] Proceed to checkout
- [ ] Place order — verify PENDING status
- [ ] Visit order history page
- [ ] Verify order status transitions to CONFIRMED (async via SQS)
- [ ] View profile page

## Backend Verification
- [ ] Check CloudWatch dashboard (EcommercePlatform)
- [ ] Verify X-Ray traces show full request path
- [ ] Check structured logs in CloudWatch Logs
- [ ] Verify Kinesis stream receives analytics events
- [ ] Verify SQS queue processes orders (check DLQ is empty)
- [ ] Verify EventBridge events published for ORDER_CONFIRMED

## Product Management
- [ ] POST /product with auth header to create product
- [ ] POST /products with array for batch create
- [ ] PATCH /product to update stock/price
- [ ] Verify search returns newly created products

## Cleanup
- [ ] Run `cd infra && npx cdk destroy --all`

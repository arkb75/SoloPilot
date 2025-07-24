# Email Intake Lambda Changelog

## [1.1.0] - 2025-06-29

### Added
- SQS handoff now triggers after every DynamoDB update, not just on completed requirements
- Enhanced SQS message with additional metadata (status, email_count, timestamp)
- Comprehensive logging for SQS operations with queue URL and message ID
- Error handling that fails Lambda invocation if SQS send_message returns non-200 status
- Unit tests for SQS functionality

### Changed
- Modified `_send_to_queue` function to accept conversation object for richer message content
- Updated handler string remains `lambda_function.lambda_handler`

### Fixed
- SQS messages now sent for new conversations and partial requirement updates
- Proper error propagation when SQS operations fail

## [1.0.0] - 2025-06-28

### Added
- Initial implementation of email intake Lambda
- Email parsing with thread tracking
- DynamoDB conversation state management
- Requirement extraction using Bedrock LLM
- SES integration for follow-up emails
- Lambda-specific entry point without relative imports
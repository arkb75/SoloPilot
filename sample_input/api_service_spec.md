# REST API Service with Authentication

## Project Overview
Create a Python REST API service with user authentication, data validation, and database integration. This project will test real-time linting with realistic complexity including async patterns, security concerns, and type safety.

## Core Features

### 1. User Management
- User registration and login endpoints
- JWT token-based authentication
- Password hashing with bcrypt
- Input validation with Pydantic models

### 2. Data API Endpoints
- CRUD operations for user data
- Pagination and filtering
- Request/response validation
- Error handling with proper HTTP status codes

### 3. Database Integration
- SQLAlchemy ORM models
- Database migrations with Alembic
- Connection pooling
- Transaction management

### 4. Security & Validation
- Input sanitization
- SQL injection prevention
- Rate limiting
- CORS configuration

## Technical Requirements

### Architecture
- FastAPI framework for async performance
- Proper dependency injection
- Environment-based configuration
- Structured logging

### Quality Standards
- Comprehensive type hints
- Error handling patterns
- Input validation
- Security best practices

## Expected Linting Challenges
This project will test real-time linting with:
- Async/await patterns
- Security vulnerabilities (SQL injection, XSS)
- Type annotation complexity
- Error handling patterns
- Database connection patterns
- Authentication/authorization flows

## Deliverables
1. FastAPI service with authentication endpoints
2. User data CRUD operations
3. Database models and migrations
4. Comprehensive input validation
5. Security middleware and rate limiting

This represents a realistic small-to-medium API service that should thoroughly test SoloPilot's real-time linting capabilities.
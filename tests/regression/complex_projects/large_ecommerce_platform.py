#!/usr/bin/env python3
"""
Large E-commerce Platform Test Project
Generates a realistic complex project with 500+ files for regression testing.
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict


class LargeEcommercePlatform:
    """Generator for large e-commerce platform test project."""

    def __init__(self, base_dir: Path):
        """Initialize the generator."""
        self.base_dir = base_dir
        self.file_count = 0

    def generate_project(self) -> Dict[str, Any]:
        """Generate a large e-commerce platform project structure."""

        # Create comprehensive planning data
        planning_data = {
            "project_title": "Enterprise E-commerce Platform",
            "summary": "A comprehensive e-commerce platform with microservices architecture, supporting millions of users, complex inventory management, multi-tenant SaaS capabilities, real-time analytics, and AI-powered recommendations.",
            "tech_stack": [
                "React",
                "TypeScript",
                "Node.js",
                "Express",
                "GraphQL",
                "PostgreSQL",
                "Redis",
                "Elasticsearch",
                "Docker",
                "Kubernetes",
                "AWS",
                "Jest",
                "Cypress",
                "Webpack",
                "ESLint",
                "Prettier",
                "Husky",
                "GitHub Actions",
                "Microservices",
                "gRPC",
                "RabbitMQ",
                "Socket.io",
                "JWT",
                "OAuth2",
            ],
            "milestones": [],
        }

        # Generate comprehensive milestones
        milestones = [
            self._create_user_authentication_milestone(),
            self._create_product_catalog_milestone(),
            self._create_shopping_cart_milestone(),
            self._create_order_management_milestone(),
            self._create_payment_processing_milestone(),
            self._create_inventory_management_milestone(),
            self._create_user_dashboard_milestone(),
            self._create_admin_panel_milestone(),
            self._create_analytics_milestone(),
            self._create_notification_system_milestone(),
            self._create_search_engine_milestone(),
            self._create_recommendation_engine_milestone(),
            self._create_review_rating_milestone(),
            self._create_shipping_logistics_milestone(),
            self._create_multi_tenant_milestone(),
            self._create_api_gateway_milestone(),
            self._create_monitoring_logging_milestone(),
            self._create_security_compliance_milestone(),
            self._create_performance_optimization_milestone(),
            self._create_mobile_app_milestone(),
        ]

        planning_data["milestones"] = milestones

        # Create extensive file structure
        self._create_file_structure()

        return planning_data

    def _create_user_authentication_milestone(self) -> Dict[str, Any]:
        """Create user authentication and authorization milestone."""
        return {
            "name": "User Authentication & Authorization System",
            "description": "Implement comprehensive user authentication system with multi-factor authentication, role-based access control, OAuth2 integration, JWT token management, password reset flows, account verification, session management, and security audit logging.",
            "estimated_duration": "3-4 weeks",
            "tasks": [
                {
                    "name": "JWT Authentication Service",
                    "description": "Implement JWT token generation, validation, refresh token rotation, token blacklisting, and secure token storage with configurable expiration policies.",
                    "estimated_hours": 24,
                },
                {
                    "name": "Multi-Factor Authentication",
                    "description": "Implement TOTP-based 2FA, SMS verification, email verification, backup codes, and recovery mechanisms with rate limiting and security monitoring.",
                    "estimated_hours": 32,
                },
                {
                    "name": "OAuth2 Social Login Integration",
                    "description": "Integrate with Google, Facebook, GitHub, Apple OAuth providers with proper scope management, user data mapping, and account linking capabilities.",
                    "estimated_hours": 20,
                },
                {
                    "name": "Role-Based Access Control (RBAC)",
                    "description": "Implement hierarchical role system, permission management, resource-based access control, dynamic permission evaluation, and admin role management interface.",
                    "estimated_hours": 28,
                },
                {
                    "name": "Password Security & Reset System",
                    "description": "Implement secure password hashing with bcrypt, password strength validation, secure reset flows, rate limiting, and account lockout protection.",
                    "estimated_hours": 16,
                },
                {
                    "name": "Session Management & Security",
                    "description": "Implement secure session handling, concurrent session limits, session invalidation, device tracking, and suspicious activity detection.",
                    "estimated_hours": 20,
                },
                {
                    "name": "Authentication API & Middleware",
                    "description": "Create RESTful authentication APIs, GraphQL authentication resolvers, Express middleware for route protection, and comprehensive error handling.",
                    "estimated_hours": 18,
                },
                {
                    "name": "User Profile Management",
                    "description": "Implement user profile CRUD operations, profile image uploads, privacy settings, account deletion, and data export compliance features.",
                    "estimated_hours": 22,
                },
            ],
        }

    def _create_product_catalog_milestone(self) -> Dict[str, Any]:
        """Create product catalog management milestone."""
        return {
            "name": "Advanced Product Catalog Management",
            "description": "Build a sophisticated product catalog system supporting complex product variants, hierarchical categories, advanced search capabilities, bulk operations, multi-language support, and real-time inventory synchronization.",
            "estimated_duration": "4-5 weeks",
            "tasks": [
                {
                    "name": "Product Data Model & Schema",
                    "description": "Design comprehensive product schema supporting variants, attributes, categories, pricing tiers, multi-language content, SEO metadata, and complex relationship mappings.",
                    "estimated_hours": 20,
                },
                {
                    "name": "Category Hierarchy System",
                    "description": "Implement nested category structures, category-specific attributes, dynamic category rules, breadcrumb navigation, and category-based filtering systems.",
                    "estimated_hours": 24,
                },
                {
                    "name": "Product Variant Management",
                    "description": "Build complex variant system supporting size, color, material combinations with inventory tracking, pricing rules, and availability management per variant.",
                    "estimated_hours": 32,
                },
                {
                    "name": "Bulk Product Operations",
                    "description": "Implement CSV import/export, bulk editing interface, batch price updates, mass category assignments, and progress tracking for long-running operations.",
                    "estimated_hours": 28,
                },
                {
                    "name": "Product Image Management",
                    "description": "Build image upload system with multiple resolutions, compression, CDN integration, alt-text management, and image optimization for web performance.",
                    "estimated_hours": 22,
                },
                {
                    "name": "Advanced Search & Filtering",
                    "description": "Implement Elasticsearch-based search with faceted filtering, auto-suggestions, typo tolerance, search analytics, and personalized search results.",
                    "estimated_hours": 30,
                },
                {
                    "name": "Product API & GraphQL Schema",
                    "description": "Create comprehensive product APIs with pagination, sorting, filtering, field selection, batch queries, and real-time updates via subscriptions.",
                    "estimated_hours": 25,
                },
                {
                    "name": "SEO & Marketing Features",
                    "description": "Implement SEO-friendly URLs, meta tags management, schema markup, sitemap generation, and product promotion management systems.",
                    "estimated_hours": 18,
                },
            ],
        }

    def _create_shopping_cart_milestone(self) -> Dict[str, Any]:
        """Create shopping cart and wishlist milestone."""
        return {
            "name": "Smart Shopping Cart & Wishlist System",
            "description": "Develop intelligent shopping cart with real-time pricing, inventory validation, cart persistence across devices, abandoned cart recovery, wishlist management, and promotional code integration.",
            "estimated_duration": "2-3 weeks",
            "tasks": [
                {
                    "name": "Cart State Management",
                    "description": "Implement Redux-based cart state with persistent storage, real-time synchronization across tabs, conflict resolution, and offline support with sync on reconnection.",
                    "estimated_hours": 20,
                },
                {
                    "name": "Real-time Inventory Validation",
                    "description": "Build real-time inventory checking, stock reservation system, quantity limit enforcement, and availability notifications with WebSocket updates.",
                    "estimated_hours": 24,
                },
                {
                    "name": "Dynamic Pricing Engine",
                    "description": "Implement complex pricing rules, volume discounts, time-based pricing, customer-specific pricing, and tax calculation with international support.",
                    "estimated_hours": 28,
                },
                {
                    "name": "Promotional Code System",
                    "description": "Create flexible coupon system supporting percentage/fixed discounts, minimum order requirements, product restrictions, usage limits, and expiration handling.",
                    "estimated_hours": 22,
                },
                {
                    "name": "Abandoned Cart Recovery",
                    "description": "Implement cart abandonment tracking, email reminder sequences, personalized recovery offers, and analytics dashboard for conversion optimization.",
                    "estimated_hours": 18,
                },
                {
                    "name": "Wishlist & Save for Later",
                    "description": "Build wishlist functionality with sharing capabilities, price drop notifications, stock alerts, and seamless cart integration.",
                    "estimated_hours": 16,
                },
                {
                    "name": "Cart API & Real-time Updates",
                    "description": "Create comprehensive cart APIs with optimistic updates, conflict resolution, real-time synchronization, and comprehensive error handling.",
                    "estimated_hours": 20,
                },
            ],
        }

    def _create_order_management_milestone(self) -> Dict[str, Any]:
        """Create comprehensive order management milestone."""
        return {
            "name": "Enterprise Order Management System",
            "description": "Build comprehensive order processing system with workflow automation, multi-fulfillment options, order tracking, returns management, and integration with external fulfillment centers.",
            "estimated_duration": "4-5 weeks",
            "tasks": [
                {
                    "name": "Order Processing Workflow",
                    "description": "Implement order state machine with automated transitions, manual intervention points, approval workflows, and comprehensive audit logging.",
                    "estimated_hours": 30,
                },
                {
                    "name": "Multi-Fulfillment Center Integration",
                    "description": "Build intelligent order routing to multiple fulfillment centers based on inventory, location, and business rules with real-time status updates.",
                    "estimated_hours": 35,
                },
                {
                    "name": "Order Tracking & Notifications",
                    "description": "Implement real-time order tracking with carrier integration, SMS/email notifications, delivery predictions, and customer communication portal.",
                    "estimated_hours": 25,
                },
                {
                    "name": "Returns & Refunds Management",
                    "description": "Build comprehensive returns system with return authorization, quality control workflow, refund processing, and inventory restocking automation.",
                    "estimated_hours": 28,
                },
                {
                    "name": "Order Splitting & Partial Fulfillment",
                    "description": "Implement intelligent order splitting for partial availability, backorder management, and consolidated shipping optimization.",
                    "estimated_hours": 22,
                },
                {
                    "name": "Invoice & Receipt Generation",
                    "description": "Create automated invoice generation, PDF receipt creation, tax compliance documentation, and accounting system integration.",
                    "estimated_hours": 20,
                },
                {
                    "name": "Order Analytics & Reporting",
                    "description": "Build comprehensive order analytics dashboard with fulfillment metrics, customer insights, and operational KPI tracking.",
                    "estimated_hours": 18,
                },
            ],
        }

    def _create_payment_processing_milestone(self) -> Dict[str, Any]:
        """Create secure payment processing milestone."""
        return {
            "name": "Secure Payment Processing & Financial Management",
            "description": "Implement PCI-compliant payment processing with multiple payment methods, fraud detection, subscription billing, marketplace payments, and comprehensive financial reporting.",
            "estimated_duration": "3-4 weeks",
            "tasks": [
                {
                    "name": "Multi-Gateway Payment Integration",
                    "description": "Integrate with Stripe, PayPal, Square payment gateways with failover logic, optimal routing, and comprehensive error handling with retry mechanisms.",
                    "estimated_hours": 32,
                },
                {
                    "name": "PCI Compliance & Security",
                    "description": "Implement PCI DSS compliance measures, secure card tokenization, encrypted data storage, and comprehensive security audit logging.",
                    "estimated_hours": 28,
                },
                {
                    "name": "Fraud Detection System",
                    "description": "Build machine learning-based fraud detection with risk scoring, velocity checks, geographic validation, and manual review workflows.",
                    "estimated_hours": 30,
                },
                {
                    "name": "Subscription & Recurring Billing",
                    "description": "Implement subscription management with plan changes, proration, dunning management, and automated renewal with retry logic.",
                    "estimated_hours": 26,
                },
                {
                    "name": "Marketplace Payment Splitting",
                    "description": "Build marketplace payment splitting for multi-vendor scenarios with commission calculation, delayed transfers, and dispute handling.",
                    "estimated_hours": 24,
                },
                {
                    "name": "International Payment Support",
                    "description": "Implement multi-currency support, exchange rate management, international tax calculation, and regional payment method integration.",
                    "estimated_hours": 22,
                },
                {
                    "name": "Financial Reporting & Reconciliation",
                    "description": "Create comprehensive financial dashboards, transaction reconciliation, settlement reporting, and accounting system integration.",
                    "estimated_hours": 20,
                },
            ],
        }

    def _create_inventory_management_milestone(self) -> Dict[str, Any]:
        """Create advanced inventory management milestone."""
        return {
            "name": "Advanced Inventory Management & Warehouse Operations",
            "description": "Build sophisticated inventory tracking system with real-time updates, multi-location management, automated reordering, demand forecasting, and warehouse management integration.",
            "estimated_duration": "3-4 weeks",
            "tasks": [
                {
                    "name": "Real-time Inventory Tracking",
                    "description": "Implement real-time inventory updates with event sourcing, stock reservation system, and consistency guarantees across distributed systems.",
                    "estimated_hours": 28,
                },
                {
                    "name": "Multi-Location Inventory Management",
                    "description": "Build inventory tracking across multiple warehouses, stores, and fulfillment centers with location-based availability and transfer management.",
                    "estimated_hours": 30,
                },
                {
                    "name": "Automated Reordering System",
                    "description": "Implement intelligent reordering with configurable thresholds, supplier integration, lead time optimization, and seasonal adjustment algorithms.",
                    "estimated_hours": 26,
                },
                {
                    "name": "Demand Forecasting & Analytics",
                    "description": "Build machine learning-based demand forecasting with trend analysis, seasonality detection, and inventory optimization recommendations.",
                    "estimated_hours": 32,
                },
                {
                    "name": "Supplier & Purchase Order Management",
                    "description": "Create supplier portal, automated PO generation, receiving workflows, quality control integration, and supplier performance tracking.",
                    "estimated_hours": 24,
                },
                {
                    "name": "Inventory Audit & Cycle Counting",
                    "description": "Implement inventory audit workflows, cycle counting schedules, variance reporting, and adjustment approval processes.",
                    "estimated_hours": 20,
                },
                {
                    "name": "Warehouse Management Integration",
                    "description": "Build WMS integration for pick lists, packing optimization, barcode scanning, and real-time warehouse floor management.",
                    "estimated_hours": 22,
                },
            ],
        }

    def _create_user_dashboard_milestone(self) -> Dict[str, Any]:
        """Create user dashboard and account management milestone."""
        return {
            "name": "Comprehensive User Dashboard & Account Management",
            "description": "Build feature-rich user dashboard with order history, account management, preferences, loyalty program integration, and personalized recommendations.",
            "estimated_duration": "2-3 weeks",
            "tasks": [
                {
                    "name": "Personalized Dashboard",
                    "description": "Create dynamic dashboard with personalized content, recent orders, recommendations, wishlist items, and customizable widget layout.",
                    "estimated_hours": 22,
                },
                {
                    "name": "Order History & Tracking",
                    "description": "Build comprehensive order history with advanced filtering, detailed tracking, reorder functionality, and download capabilities.",
                    "estimated_hours": 18,
                },
                {
                    "name": "Account Settings & Preferences",
                    "description": "Implement comprehensive account management with communication preferences, privacy settings, and data export/deletion options.",
                    "estimated_hours": 20,
                },
                {
                    "name": "Address Book & Payment Methods",
                    "description": "Build secure address management and payment method storage with encryption, validation, and default selection logic.",
                    "estimated_hours": 16,
                },
                {
                    "name": "Loyalty Program Integration",
                    "description": "Implement points tracking, tier management, reward redemption, and gamification elements to increase engagement.",
                    "estimated_hours": 24,
                },
                {
                    "name": "Notification Center",
                    "description": "Create unified notification system with preference management, delivery options, and notification history tracking.",
                    "estimated_hours": 18,
                },
            ],
        }

    def _create_admin_panel_milestone(self) -> Dict[str, Any]:
        """Create comprehensive admin panel milestone."""
        return {
            "name": "Enterprise Admin Panel & Management Console",
            "description": "Build comprehensive admin interface with role-based access, real-time analytics, system configuration, user management, and operational tools.",
            "estimated_duration": "4-5 weeks",
            "tasks": [
                {
                    "name": "Role-Based Admin Interface",
                    "description": "Create hierarchical admin roles with granular permissions, module-based access control, and audit logging for all admin actions.",
                    "estimated_hours": 28,
                },
                {
                    "name": "Real-time Analytics Dashboard",
                    "description": "Build comprehensive analytics with real-time metrics, customizable charts, KPI tracking, and automated reporting capabilities.",
                    "estimated_hours": 30,
                },
                {
                    "name": "User Management & Support Tools",
                    "description": "Implement user search, account management, impersonation tools, support ticket integration, and customer communication tools.",
                    "estimated_hours": 26,
                },
                {
                    "name": "System Configuration Management",
                    "description": "Create configuration interface for system settings, feature flags, payment configurations, and deployment management.",
                    "estimated_hours": 24,
                },
                {
                    "name": "Content Management System",
                    "description": "Build CMS for static pages, blog posts, promotional banners, email templates, and SEO content management.",
                    "estimated_hours": 22,
                },
                {
                    "name": "Bulk Operations & Data Import",
                    "description": "Implement bulk user operations, data import/export tools, mass communications, and batch processing with progress tracking.",
                    "estimated_hours": 20,
                },
                {
                    "name": "System Monitoring & Health Checks",
                    "description": "Create system health dashboard, service monitoring, error tracking, performance metrics, and alerting configuration.",
                    "estimated_hours": 18,
                },
            ],
        }

    def _create_analytics_milestone(self) -> Dict[str, Any]:
        """Create advanced analytics and reporting milestone."""
        return {
            "name": "Advanced Analytics & Business Intelligence",
            "description": "Build comprehensive analytics platform with real-time data processing, custom reporting, predictive analytics, and business intelligence dashboards.",
            "estimated_duration": "3-4 weeks",
            "tasks": [
                {
                    "name": "Event Tracking & Data Collection",
                    "description": "Implement comprehensive event tracking with user behavior analytics, conversion funnel analysis, and privacy-compliant data collection.",
                    "estimated_hours": 26,
                },
                {
                    "name": "Real-time Analytics Pipeline",
                    "description": "Build real-time data processing pipeline with stream processing, aggregation engines, and low-latency analytics capabilities.",
                    "estimated_hours": 32,
                },
                {
                    "name": "Custom Report Builder",
                    "description": "Create drag-and-drop report builder with custom metrics, filtering, grouping, and scheduled report generation capabilities.",
                    "estimated_hours": 28,
                },
                {
                    "name": "Predictive Analytics & ML Integration",
                    "description": "Implement machine learning models for customer lifetime value, churn prediction, and demand forecasting with model monitoring.",
                    "estimated_hours": 30,
                },
                {
                    "name": "Business Intelligence Dashboards",
                    "description": "Build executive dashboards with KPI tracking, trend analysis, comparative reporting, and drill-down capabilities.",
                    "estimated_hours": 24,
                },
                {
                    "name": "A/B Testing Framework",
                    "description": "Implement comprehensive A/B testing platform with experiment design, statistical analysis, and automated winner selection.",
                    "estimated_hours": 22,
                },
            ],
        }

    def _create_notification_system_milestone(self) -> Dict[str, Any]:
        """Create notification and communication milestone."""
        return {
            "name": "Multi-Channel Notification & Communication System",
            "description": "Build comprehensive notification system supporting email, SMS, push notifications, in-app messaging, and automated communication workflows.",
            "estimated_duration": "2-3 weeks",
            "tasks": [
                {
                    "name": "Multi-Channel Notification Engine",
                    "description": "Implement unified notification system supporting email, SMS, push notifications with delivery tracking and fallback mechanisms.",
                    "estimated_hours": 24,
                },
                {
                    "name": "Template Management System",
                    "description": "Build template engine with dynamic content, multi-language support, A/B testing, and personalization capabilities.",
                    "estimated_hours": 20,
                },
                {
                    "name": "Automated Communication Workflows",
                    "description": "Create workflow engine for automated email sequences, abandoned cart recovery, and lifecycle marketing campaigns.",
                    "estimated_hours": 26,
                },
                {
                    "name": "Push Notification Service",
                    "description": "Implement cross-platform push notifications with segmentation, scheduling, and engagement analytics.",
                    "estimated_hours": 22,
                },
                {
                    "name": "SMS & WhatsApp Integration",
                    "description": "Build SMS and WhatsApp messaging with international support, delivery receipts, and compliance management.",
                    "estimated_hours": 18,
                },
                {
                    "name": "Preference Management & Compliance",
                    "description": "Implement comprehensive preference center with unsubscribe management, GDPR compliance, and consent tracking.",
                    "estimated_hours": 16,
                },
            ],
        }

    def _create_search_engine_milestone(self) -> Dict[str, Any]:
        """Create advanced search engine milestone."""
        return {
            "name": "Intelligent Search Engine & Discovery Platform",
            "description": "Build advanced search capabilities with AI-powered recommendations, faceted search, auto-complete, and personalized results.",
            "estimated_duration": "3-4 weeks",
            "tasks": [
                {
                    "name": "Elasticsearch Integration & Optimization",
                    "description": "Implement advanced Elasticsearch setup with custom analyzers, synonym management, and performance optimization for large catalogs.",
                    "estimated_hours": 28,
                },
                {
                    "name": "AI-Powered Search & NLP",
                    "description": "Integrate natural language processing for semantic search, intent recognition, and intelligent query understanding.",
                    "estimated_hours": 30,
                },
                {
                    "name": "Faceted Search & Filtering",
                    "description": "Build dynamic faceted search with hierarchical filters, range filters, and smart filter suggestions based on search context.",
                    "estimated_hours": 24,
                },
                {
                    "name": "Auto-complete & Search Suggestions",
                    "description": "Implement intelligent auto-complete with typo tolerance, popular searches, and personalized suggestions.",
                    "estimated_hours": 20,
                },
                {
                    "name": "Visual Search Integration",
                    "description": "Build image-based search capabilities with computer vision integration for product discovery through images.",
                    "estimated_hours": 26,
                },
                {
                    "name": "Search Analytics & Optimization",
                    "description": "Create search analytics dashboard with query analysis, zero-result tracking, and search performance optimization tools.",
                    "estimated_hours": 18,
                },
            ],
        }

    def _create_recommendation_engine_milestone(self) -> Dict[str, Any]:
        """Create AI recommendation engine milestone."""
        return {
            "name": "AI-Powered Recommendation Engine",
            "description": "Build sophisticated recommendation system using collaborative filtering, content-based filtering, and deep learning for personalized product suggestions.",
            "estimated_duration": "4-5 weeks",
            "tasks": [
                {
                    "name": "Collaborative Filtering Engine",
                    "description": "Implement user-based and item-based collaborative filtering with matrix factorization and advanced similarity algorithms.",
                    "estimated_hours": 32,
                },
                {
                    "name": "Content-Based Recommendation System",
                    "description": "Build content-based filtering using product attributes, descriptions, and image features with TF-IDF and embedding models.",
                    "estimated_hours": 28,
                },
                {
                    "name": "Deep Learning Recommendation Models",
                    "description": "Implement neural collaborative filtering, autoencoders, and transformer-based models for advanced personalization.",
                    "estimated_hours": 35,
                },
                {
                    "name": "Real-time Recommendation API",
                    "description": "Create high-performance recommendation API with caching, A/B testing, and real-time model serving capabilities.",
                    "estimated_hours": 26,
                },
                {
                    "name": "Recommendation Model Training Pipeline",
                    "description": "Build automated ML pipeline for model training, validation, deployment, and performance monitoring with MLOps practices.",
                    "estimated_hours": 30,
                },
                {
                    "name": "Explainable Recommendations",
                    "description": "Implement recommendation explanations and transparency features to build user trust and improve engagement.",
                    "estimated_hours": 20,
                },
            ],
        }

    def _create_review_rating_milestone(self) -> Dict[str, Any]:
        """Create review and rating system milestone."""
        return {
            "name": "Advanced Review & Rating System",
            "description": "Build comprehensive review platform with verified purchases, moderation workflows, sentiment analysis, and social features.",
            "estimated_duration": "2-3 weeks",
            "tasks": [
                {
                    "name": "Review Collection & Management",
                    "description": "Implement review submission with media uploads, edit capabilities, verification status, and comprehensive moderation tools.",
                    "estimated_hours": 22,
                },
                {
                    "name": "Sentiment Analysis & Classification",
                    "description": "Build automated sentiment analysis with aspect-based sentiment, spam detection, and content quality scoring.",
                    "estimated_hours": 24,
                },
                {
                    "name": "Review Moderation Workflow",
                    "description": "Create moderation pipeline with automated screening, manual review queue, and community reporting mechanisms.",
                    "estimated_hours": 20,
                },
                {
                    "name": "Social Features & Gamification",
                    "description": "Implement helpful votes, reviewer profiles, badges, and social features to encourage quality reviews.",
                    "estimated_hours": 18,
                },
                {
                    "name": "Review Analytics & Insights",
                    "description": "Build review analytics dashboard with sentiment trends, product feedback analysis, and actionable business insights.",
                    "estimated_hours": 16,
                },
                {
                    "name": "Review Integration & Display",
                    "description": "Create flexible review display system with sorting, filtering, and integration across product pages and search results.",
                    "estimated_hours": 14,
                },
            ],
        }

    def _create_shipping_logistics_milestone(self) -> Dict[str, Any]:
        """Create shipping and logistics milestone."""
        return {
            "name": "Advanced Shipping & Logistics Management",
            "description": "Build comprehensive shipping system with carrier integration, rate calculation, label generation, tracking, and logistics optimization.",
            "estimated_duration": "3-4 weeks",
            "tasks": [
                {
                    "name": "Multi-Carrier Integration",
                    "description": "Integrate with major carriers (UPS, FedEx, USPS, DHL) for rate calculation, label generation, and tracking with failover support.",
                    "estimated_hours": 30,
                },
                {
                    "name": "Intelligent Shipping Rate Engine",
                    "description": "Build dynamic rate calculation with carrier comparison, delivery time optimization, and cost-effective shipping recommendations.",
                    "estimated_hours": 26,
                },
                {
                    "name": "Automated Label Generation",
                    "description": "Implement automated shipping label creation with address validation, packaging optimization, and bulk processing capabilities.",
                    "estimated_hours": 22,
                },
                {
                    "name": "Real-time Package Tracking",
                    "description": "Create comprehensive tracking system with carrier webhooks, delivery predictions, and proactive customer notifications.",
                    "estimated_hours": 24,
                },
                {
                    "name": "Logistics Optimization Engine",
                    "description": "Build route optimization, warehouse selection algorithms, and delivery time prediction using machine learning.",
                    "estimated_hours": 28,
                },
                {
                    "name": "International Shipping & Customs",
                    "description": "Implement international shipping with customs documentation, duty calculation, and compliance management for global commerce.",
                    "estimated_hours": 20,
                },
            ],
        }

    def _create_multi_tenant_milestone(self) -> Dict[str, Any]:
        """Create multi-tenant SaaS milestone."""
        return {
            "name": "Multi-Tenant SaaS Architecture & White-Label Solution",
            "description": "Build multi-tenant architecture supporting white-label deployments, tenant isolation, custom branding, and scalable resource management.",
            "estimated_duration": "4-5 weeks",
            "tasks": [
                {
                    "name": "Multi-Tenant Data Architecture",
                    "description": "Implement tenant isolation strategies with shared database, separate schemas, and row-level security for data protection.",
                    "estimated_hours": 32,
                },
                {
                    "name": "White-Label Customization Engine",
                    "description": "Build theme customization system with logo uploads, color schemes, custom CSS, and brand asset management.",
                    "estimated_hours": 28,
                },
                {
                    "name": "Tenant Configuration & Feature Flags",
                    "description": "Create tenant-specific configuration management with feature toggles, subscription plans, and usage-based restrictions.",
                    "estimated_hours": 26,
                },
                {
                    "name": "Scalable Resource Management",
                    "description": "Implement resource quotas, usage tracking, auto-scaling policies, and performance isolation between tenants.",
                    "estimated_hours": 30,
                },
                {
                    "name": "Tenant Onboarding & Provisioning",
                    "description": "Build automated tenant provisioning with setup wizards, data migration tools, and configuration validation.",
                    "estimated_hours": 24,
                },
                {
                    "name": "Multi-Tenant Analytics & Reporting",
                    "description": "Create tenant-specific analytics with cross-tenant insights for platform operators and tenant-isolated reporting.",
                    "estimated_hours": 22,
                },
            ],
        }

    def _create_api_gateway_milestone(self) -> Dict[str, Any]:
        """Create API gateway and microservices milestone."""
        return {
            "name": "Enterprise API Gateway & Microservices Architecture",
            "description": "Build comprehensive API gateway with rate limiting, authentication, service discovery, load balancing, and microservices orchestration.",
            "estimated_duration": "3-4 weeks",
            "tasks": [
                {
                    "name": "API Gateway Implementation",
                    "description": "Build high-performance API gateway with request routing, protocol translation, and comprehensive middleware support.",
                    "estimated_hours": 28,
                },
                {
                    "name": "Rate Limiting & Throttling",
                    "description": "Implement sophisticated rate limiting with multiple algorithms, quota management, and DDoS protection mechanisms.",
                    "estimated_hours": 22,
                },
                {
                    "name": "Service Discovery & Load Balancing",
                    "description": "Create dynamic service discovery with health checks, circuit breakers, and intelligent load balancing algorithms.",
                    "estimated_hours": 26,
                },
                {
                    "name": "API Authentication & Authorization",
                    "description": "Implement comprehensive API security with JWT validation, API keys, OAuth2, and granular permission management.",
                    "estimated_hours": 24,
                },
                {
                    "name": "API Documentation & Developer Portal",
                    "description": "Build interactive API documentation with testing tools, SDK generation, and developer onboarding resources.",
                    "estimated_hours": 20,
                },
                {
                    "name": "Microservices Communication",
                    "description": "Implement service mesh with gRPC, message queues, event sourcing, and distributed transaction management.",
                    "estimated_hours": 30,
                },
            ],
        }

    def _create_monitoring_logging_milestone(self) -> Dict[str, Any]:
        """Create monitoring and logging milestone."""
        return {
            "name": "Comprehensive Monitoring, Logging & Observability",
            "description": "Build enterprise-grade monitoring with distributed tracing, log aggregation, alerting, and observability for complex microservices architecture.",
            "estimated_duration": "2-3 weeks",
            "tasks": [
                {
                    "name": "Distributed Tracing & APM",
                    "description": "Implement distributed tracing with OpenTelemetry, performance monitoring, and application performance insights.",
                    "estimated_hours": 24,
                },
                {
                    "name": "Centralized Logging & Analytics",
                    "description": "Build centralized logging with ELK stack, log parsing, anomaly detection, and comprehensive search capabilities.",
                    "estimated_hours": 22,
                },
                {
                    "name": "Metrics Collection & Visualization",
                    "description": "Create comprehensive metrics collection with Prometheus, custom dashboards, and real-time visualization tools.",
                    "estimated_hours": 20,
                },
                {
                    "name": "Intelligent Alerting System",
                    "description": "Build smart alerting with machine learning-based anomaly detection, escalation policies, and alert correlation.",
                    "estimated_hours": 18,
                },
                {
                    "name": "Health Checks & SLA Monitoring",
                    "description": "Implement comprehensive health checks, SLA tracking, uptime monitoring, and automated recovery mechanisms.",
                    "estimated_hours": 16,
                },
                {
                    "name": "Performance Optimization & Profiling",
                    "description": "Create performance profiling tools, bottleneck detection, and automated optimization recommendations.",
                    "estimated_hours": 20,
                },
            ],
        }

    def _create_security_compliance_milestone(self) -> Dict[str, Any]:
        """Create security and compliance milestone."""
        return {
            "name": "Enterprise Security & Compliance Framework",
            "description": "Implement comprehensive security measures with GDPR/CCPA compliance, penetration testing, security audits, and threat protection.",
            "estimated_duration": "3-4 weeks",
            "tasks": [
                {
                    "name": "Security Audit & Penetration Testing",
                    "description": "Conduct comprehensive security assessment with automated vulnerability scanning, penetration testing, and security remediation.",
                    "estimated_hours": 26,
                },
                {
                    "name": "GDPR & CCPA Compliance Implementation",
                    "description": "Implement data privacy compliance with consent management, data portability, deletion rights, and audit logging.",
                    "estimated_hours": 28,
                },
                {
                    "name": "Threat Detection & Response",
                    "description": "Build threat detection system with behavioral analysis, intrusion detection, and automated incident response workflows.",
                    "estimated_hours": 24,
                },
                {
                    "name": "Data Encryption & Key Management",
                    "description": "Implement end-to-end encryption with key rotation, secure key storage, and data protection at rest and in transit.",
                    "estimated_hours": 22,
                },
                {
                    "name": "Security Monitoring & Incident Management",
                    "description": "Create security operations center with real-time monitoring, incident tracking, and compliance reporting tools.",
                    "estimated_hours": 20,
                },
                {
                    "name": "Secure Development Lifecycle (SDLC)",
                    "description": "Implement security-first development practices with code scanning, dependency checks, and secure deployment pipelines.",
                    "estimated_hours": 18,
                },
            ],
        }

    def _create_performance_optimization_milestone(self) -> Dict[str, Any]:
        """Create performance optimization milestone."""
        return {
            "name": "Performance Optimization & Scalability Engineering",
            "description": "Optimize system performance for millions of users with caching strategies, database optimization, CDN integration, and auto-scaling.",
            "estimated_duration": "2-3 weeks",
            "tasks": [
                {
                    "name": "Advanced Caching Strategy",
                    "description": "Implement multi-layer caching with Redis, CDN optimization, cache invalidation strategies, and edge computing integration.",
                    "estimated_hours": 22,
                },
                {
                    "name": "Database Performance Optimization",
                    "description": "Optimize database performance with query optimization, indexing strategies, connection pooling, and read replica management.",
                    "estimated_hours": 24,
                },
                {
                    "name": "Auto-Scaling & Load Management",
                    "description": "Implement intelligent auto-scaling with predictive scaling, load testing, and resource optimization algorithms.",
                    "estimated_hours": 20,
                },
                {
                    "name": "Frontend Performance Optimization",
                    "description": "Optimize frontend performance with code splitting, lazy loading, image optimization, and progressive web app features.",
                    "estimated_hours": 18,
                },
                {
                    "name": "CDN & Global Distribution",
                    "description": "Implement global CDN strategy with edge caching, geographic optimization, and multi-region deployment.",
                    "estimated_hours": 16,
                },
                {
                    "name": "Performance Monitoring & Benchmarking",
                    "description": "Create performance benchmarking suite with continuous monitoring, regression detection, and optimization recommendations.",
                    "estimated_hours": 20,
                },
            ],
        }

    def _create_mobile_app_milestone(self) -> Dict[str, Any]:
        """Create mobile application milestone."""
        return {
            "name": "Native Mobile Applications (iOS & Android)",
            "description": "Build native mobile applications with offline capabilities, push notifications, mobile payments, and seamless web platform integration.",
            "estimated_duration": "5-6 weeks",
            "tasks": [
                {
                    "name": "React Native Cross-Platform Development",
                    "description": "Build cross-platform mobile app with shared business logic, platform-specific optimizations, and native module integration.",
                    "estimated_hours": 35,
                },
                {
                    "name": "Offline Capabilities & Sync",
                    "description": "Implement offline functionality with local storage, data synchronization, conflict resolution, and seamless online/offline transitions.",
                    "estimated_hours": 30,
                },
                {
                    "name": "Mobile Payment Integration",
                    "description": "Integrate mobile payment solutions (Apple Pay, Google Pay) with biometric authentication and secure transaction processing.",
                    "estimated_hours": 26,
                },
                {
                    "name": "Push Notifications & Deep Linking",
                    "description": "Implement rich push notifications with deep linking, notification categories, and personalized messaging campaigns.",
                    "estimated_hours": 22,
                },
                {
                    "name": "Mobile-Specific Features",
                    "description": "Build mobile-optimized features like camera integration, barcode scanning, location services, and augmented reality previews.",
                    "estimated_hours": 28,
                },
                {
                    "name": "App Store Optimization & Deployment",
                    "description": "Optimize for app stores with ASO strategies, automated deployment pipelines, and comprehensive testing frameworks.",
                    "estimated_hours": 20,
                },
            ],
        }

    def _create_file_structure(self):
        """Create extensive file structure for the complex project."""

        # Frontend structure
        frontend_files = [
            "frontend/src/components/common/Header.tsx",
            "frontend/src/components/common/Footer.tsx",
            "frontend/src/components/common/Navigation.tsx",
            "frontend/src/components/common/SearchBar.tsx",
            "frontend/src/components/common/Button.tsx",
            "frontend/src/components/common/Modal.tsx",
            "frontend/src/components/common/LoadingSpinner.tsx",
            "frontend/src/components/auth/LoginForm.tsx",
            "frontend/src/components/auth/RegisterForm.tsx",
            "frontend/src/components/auth/ForgotPassword.tsx",
            "frontend/src/components/auth/TwoFactorAuth.tsx",
            "frontend/src/components/auth/SocialLogin.tsx",
            "frontend/src/components/product/ProductCard.tsx",
            "frontend/src/components/product/ProductList.tsx",
            "frontend/src/components/product/ProductDetail.tsx",
            "frontend/src/components/product/ProductGallery.tsx",
            "frontend/src/components/product/ProductReviews.tsx",
            "frontend/src/components/product/ProductVariants.tsx",
            "frontend/src/components/cart/CartItem.tsx",
            "frontend/src/components/cart/CartSummary.tsx",
            "frontend/src/components/cart/CartDrawer.tsx",
            "frontend/src/components/cart/CheckoutForm.tsx",
            "frontend/src/components/dashboard/UserDashboard.tsx",
            "frontend/src/components/dashboard/OrderHistory.tsx",
            "frontend/src/components/dashboard/Wishlist.tsx",
            "frontend/src/components/dashboard/AddressBook.tsx",
            "frontend/src/components/dashboard/PaymentMethods.tsx",
            "frontend/src/components/admin/AdminDashboard.tsx",
            "frontend/src/components/admin/UserManagement.tsx",
            "frontend/src/components/admin/ProductManagement.tsx",
            "frontend/src/components/admin/OrderManagement.tsx",
            "frontend/src/components/admin/Analytics.tsx",
            "frontend/src/pages/HomePage.tsx",
            "frontend/src/pages/ProductPage.tsx",
            "frontend/src/pages/CategoryPage.tsx",
            "frontend/src/pages/CartPage.tsx",
            "frontend/src/pages/CheckoutPage.tsx",
            "frontend/src/pages/UserDashboardPage.tsx",
            "frontend/src/pages/AdminPage.tsx",
            "frontend/src/hooks/useAuth.ts",
            "frontend/src/hooks/useCart.ts",
            "frontend/src/hooks/useProducts.ts",
            "frontend/src/hooks/useOrders.ts",
            "frontend/src/hooks/useLocalStorage.ts",
            "frontend/src/store/authSlice.ts",
            "frontend/src/store/cartSlice.ts",
            "frontend/src/store/productSlice.ts",
            "frontend/src/store/uiSlice.ts",
            "frontend/src/store/index.ts",
            "frontend/src/services/api.ts",
            "frontend/src/services/auth.ts",
            "frontend/src/services/products.ts",
            "frontend/src/services/cart.ts",
            "frontend/src/services/orders.ts",
            "frontend/src/services/analytics.ts",
            "frontend/src/utils/validation.ts",
            "frontend/src/utils/formatting.ts",
            "frontend/src/utils/constants.ts",
            "frontend/src/utils/helpers.ts",
            "frontend/src/styles/globals.css",
            "frontend/src/styles/components.css",
            "frontend/src/styles/variables.css",
            "frontend/package.json",
            "frontend/tsconfig.json",
            "frontend/webpack.config.js",
            "frontend/.eslintrc.js",
            "frontend/.prettierrc",
        ]

        # Backend structure
        backend_files = [
            "backend/src/app.ts",
            "backend/src/server.ts",
            "backend/src/config/database.ts",
            "backend/src/config/redis.ts",
            "backend/src/config/env.ts",
            "backend/src/config/aws.ts",
            "backend/src/controllers/authController.ts",
            "backend/src/controllers/userController.ts",
            "backend/src/controllers/productController.ts",
            "backend/src/controllers/cartController.ts",
            "backend/src/controllers/orderController.ts",
            "backend/src/controllers/paymentController.ts",
            "backend/src/controllers/adminController.ts",
            "backend/src/controllers/analyticsController.ts",
            "backend/src/models/User.ts",
            "backend/src/models/Product.ts",
            "backend/src/models/Category.ts",
            "backend/src/models/Order.ts",
            "backend/src/models/Cart.ts",
            "backend/src/models/Payment.ts",
            "backend/src/models/Review.ts",
            "backend/src/models/Inventory.ts",
            "backend/src/middleware/auth.ts",
            "backend/src/middleware/validation.ts",
            "backend/src/middleware/rateLimit.ts",
            "backend/src/middleware/cors.ts",
            "backend/src/middleware/logging.ts",
            "backend/src/middleware/errorHandler.ts",
            "backend/src/services/authService.ts",
            "backend/src/services/userService.ts",
            "backend/src/services/productService.ts",
            "backend/src/services/cartService.ts",
            "backend/src/services/orderService.ts",
            "backend/src/services/paymentService.ts",
            "backend/src/services/inventoryService.ts",
            "backend/src/services/emailService.ts",
            "backend/src/services/smsService.ts",
            "backend/src/services/searchService.ts",
            "backend/src/services/recommendationService.ts",
            "backend/src/services/analyticsService.ts",
            "backend/src/utils/logger.ts",
            "backend/src/utils/encryption.ts",
            "backend/src/utils/jwt.ts",
            "backend/src/utils/validation.ts",
            "backend/src/utils/cache.ts",
            "backend/src/utils/queue.ts",
            "backend/src/routes/auth.ts",
            "backend/src/routes/users.ts",
            "backend/src/routes/products.ts",
            "backend/src/routes/cart.ts",
            "backend/src/routes/orders.ts",
            "backend/src/routes/payments.ts",
            "backend/src/routes/admin.ts",
            "backend/src/routes/analytics.ts",
            "backend/src/routes/webhooks.ts",
            "backend/src/graphql/schema.ts",
            "backend/src/graphql/resolvers/userResolvers.ts",
            "backend/src/graphql/resolvers/productResolvers.ts",
            "backend/src/graphql/resolvers/orderResolvers.ts",
            "backend/package.json",
            "backend/tsconfig.json",
            "backend/.eslintrc.js",
            "backend/jest.config.js",
        ]

        # Database and migration files
        database_files = [
            "database/migrations/001_create_users_table.sql",
            "database/migrations/002_create_products_table.sql",
            "database/migrations/003_create_categories_table.sql",
            "database/migrations/004_create_orders_table.sql",
            "database/migrations/005_create_cart_table.sql",
            "database/migrations/006_create_payments_table.sql",
            "database/migrations/007_create_reviews_table.sql",
            "database/migrations/008_create_inventory_table.sql",
            "database/migrations/009_create_shipping_table.sql",
            "database/migrations/010_create_analytics_table.sql",
            "database/seeds/users_seed.sql",
            "database/seeds/products_seed.sql",
            "database/seeds/categories_seed.sql",
            "database/views/user_analytics_view.sql",
            "database/views/product_analytics_view.sql",
            "database/procedures/update_inventory.sql",
            "database/procedures/process_order.sql",
            "database/procedures/calculate_recommendations.sql",
        ]

        # Test files
        test_files = [
            "tests/unit/auth.test.ts",
            "tests/unit/user.test.ts",
            "tests/unit/product.test.ts",
            "tests/unit/cart.test.ts",
            "tests/unit/order.test.ts",
            "tests/unit/payment.test.ts",
            "tests/integration/auth.integration.test.ts",
            "tests/integration/product.integration.test.ts",
            "tests/integration/order.integration.test.ts",
            "tests/integration/payment.integration.test.ts",
            "tests/e2e/user-journey.e2e.test.ts",
            "tests/e2e/admin-workflow.e2e.test.ts",
            "tests/e2e/checkout-flow.e2e.test.ts",
            "tests/performance/load-test.ts",
            "tests/performance/stress-test.ts",
            "tests/security/auth.security.test.ts",
            "tests/security/injection.security.test.ts",
            "tests/utils/testHelpers.ts",
            "tests/utils/mockData.ts",
            "tests/fixtures/users.json",
            "tests/fixtures/products.json",
            "tests/fixtures/orders.json",
        ]

        # Infrastructure and DevOps files
        infra_files = [
            "infrastructure/docker/Dockerfile.backend",
            "infrastructure/docker/Dockerfile.frontend",
            "infrastructure/docker/docker-compose.yml",
            "infrastructure/docker/docker-compose.prod.yml",
            "infrastructure/kubernetes/namespace.yaml",
            "infrastructure/kubernetes/backend-deployment.yaml",
            "infrastructure/kubernetes/frontend-deployment.yaml",
            "infrastructure/kubernetes/database-deployment.yaml",
            "infrastructure/kubernetes/redis-deployment.yaml",
            "infrastructure/kubernetes/ingress.yaml",
            "infrastructure/kubernetes/configmap.yaml",
            "infrastructure/kubernetes/secrets.yaml",
            "infrastructure/terraform/main.tf",
            "infrastructure/terraform/variables.tf",
            "infrastructure/terraform/outputs.tf",
            "infrastructure/terraform/vpc.tf",
            "infrastructure/terraform/rds.tf",
            "infrastructure/terraform/elasticache.tf",
            "infrastructure/terraform/eks.tf",
            "infrastructure/terraform/s3.tf",
            "infrastructure/terraform/cloudfront.tf",
            "infrastructure/helm/ecommerce-platform/Chart.yaml",
            "infrastructure/helm/ecommerce-platform/values.yaml",
            "infrastructure/helm/ecommerce-platform/values-prod.yaml",
            "infrastructure/helm/ecommerce-platform/templates/backend.yaml",
            "infrastructure/helm/ecommerce-platform/templates/frontend.yaml",
            ".github/workflows/ci.yml",
            ".github/workflows/cd.yml",
            ".github/workflows/security-scan.yml",
            ".github/workflows/performance-test.yml",
        ]

        # Documentation files
        docs_files = [
            "docs/README.md",
            "docs/ARCHITECTURE.md",
            "docs/API.md",
            "docs/DEPLOYMENT.md",
            "docs/SECURITY.md",
            "docs/PERFORMANCE.md",
            "docs/MONITORING.md",
            "docs/TROUBLESHOOTING.md",
            "docs/api/authentication.md",
            "docs/api/users.md",
            "docs/api/products.md",
            "docs/api/orders.md",
            "docs/api/payments.md",
            "docs/api/webhooks.md",
            "docs/guides/getting-started.md",
            "docs/guides/development.md",
            "docs/guides/testing.md",
            "docs/guides/deployment.md",
            "docs/architecture/system-overview.md",
            "docs/architecture/database-design.md",
            "docs/architecture/api-design.md",
            "docs/architecture/security-design.md",
        ]

        # Configuration files
        config_files = [
            "package.json",
            "tsconfig.json",
            ".eslintrc.js",
            ".prettierrc",
            ".gitignore",
            ".env.example",
            ".env.development",
            ".env.staging",
            ".env.production",
            "jest.config.js",
            "cypress.config.js",
            "sonar-project.properties",
            "codecov.yml",
            "renovate.json",
            "lerna.json",
        ]

        # Microservices files
        microservice_files = [
            "microservices/auth-service/src/main.ts",
            "microservices/auth-service/src/controllers/authController.ts",
            "microservices/auth-service/src/services/authService.ts",
            "microservices/auth-service/package.json",
            "microservices/product-service/src/main.ts",
            "microservices/product-service/src/controllers/productController.ts",
            "microservices/product-service/src/services/productService.ts",
            "microservices/product-service/package.json",
            "microservices/order-service/src/main.ts",
            "microservices/order-service/src/controllers/orderController.ts",
            "microservices/order-service/src/services/orderService.ts",
            "microservices/order-service/package.json",
            "microservices/payment-service/src/main.ts",
            "microservices/payment-service/src/controllers/paymentController.ts",
            "microservices/payment-service/src/services/paymentService.ts",
            "microservices/payment-service/package.json",
            "microservices/notification-service/src/main.ts",
            "microservices/notification-service/src/controllers/notificationController.ts",
            "microservices/notification-service/src/services/emailService.ts",
            "microservices/notification-service/src/services/smsService.ts",
            "microservices/notification-service/package.json",
            "microservices/analytics-service/src/main.ts",
            "microservices/analytics-service/src/controllers/analyticsController.ts",
            "microservices/analytics-service/src/services/analyticsService.ts",
            "microservices/analytics-service/package.json",
            "microservices/search-service/src/main.ts",
            "microservices/search-service/src/controllers/searchController.ts",
            "microservices/search-service/src/services/elasticsearchService.ts",
            "microservices/search-service/package.json",
            "microservices/recommendation-service/src/main.ts",
            "microservices/recommendation-service/src/controllers/recommendationController.ts",
            "microservices/recommendation-service/src/services/mlService.ts",
            "microservices/recommendation-service/package.json",
        ]

        # Mobile app files
        mobile_files = [
            "mobile/package.json",
            "mobile/metro.config.js",
            "mobile/react-native.config.js",
            "mobile/src/App.tsx",
            "mobile/src/navigation/AppNavigator.tsx",
            "mobile/src/navigation/AuthNavigator.tsx",
            "mobile/src/screens/HomeScreen.tsx",
            "mobile/src/screens/ProductScreen.tsx",
            "mobile/src/screens/CartScreen.tsx",
            "mobile/src/screens/CheckoutScreen.tsx",
            "mobile/src/screens/ProfileScreen.tsx",
            "mobile/src/screens/OrderHistoryScreen.tsx",
            "mobile/src/components/ProductCard.tsx",
            "mobile/src/components/CartItem.tsx",
            "mobile/src/components/SearchBar.tsx",
            "mobile/src/components/Button.tsx",
            "mobile/src/services/api.ts",
            "mobile/src/services/auth.ts",
            "mobile/src/services/push.ts",
            "mobile/src/utils/storage.ts",
            "mobile/src/utils/permissions.ts",
            "mobile/ios/Podfile",
            "mobile/ios/Info.plist",
            "mobile/android/build.gradle",
            "mobile/android/app/build.gradle",
            "mobile/android/app/src/main/AndroidManifest.xml",
        ]

        # Combine all files
        all_files = (
            frontend_files
            + backend_files
            + database_files
            + test_files
            + infra_files
            + docs_files
            + config_files
            + microservice_files
            + mobile_files
        )

        # Create the files
        for file_path in all_files:
            full_path = self.base_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Create basic content based on file type
            content = self._generate_file_content(file_path)
            with open(full_path, "w") as f:
                f.write(content)

            self.file_count += 1

        print(f"Created {self.file_count} files in complex project structure")

    def _generate_file_content(self, file_path: str) -> str:
        """Generate basic content for different file types."""
        if file_path.endswith(".ts") or file_path.endswith(".tsx"):
            return f"""// {file_path}
// Generated for complex project regression testing

export default class GeneratedClass {{
    constructor() {{
        // TODO: Implement constructor logic
    }}
    
    public async execute(): Promise<void> {{
        // TODO: Implement execution logic
        console.log('Executing {file_path}');
    }}
}}
"""
        elif file_path.endswith(".sql"):
            return f"""-- {file_path}
-- Generated for complex project regression testing

CREATE TABLE IF NOT EXISTS generated_table (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TODO: Add appropriate indexes and constraints
"""
        elif file_path.endswith(".json"):
            return json.dumps(
                {
                    "name": f"generated-{file_path.split('/')[-1]}",
                    "description": f"Generated configuration for {file_path}",
                    "version": "1.0.0",
                    "generated": True,
                },
                indent=2,
            )
        elif file_path.endswith(".md"):
            return f"""# {file_path}

This is a generated documentation file for complex project regression testing.

## Overview

This file represents part of a large-scale e-commerce platform with 500+ files.

## Generated Content

This content is automatically generated for testing purposes.

## TODO

- Add real documentation content
- Update with actual implementation details
- Review and validate information
"""
        elif file_path.endswith(".yaml") or file_path.endswith(".yml"):
            return f"""# {file_path}
# Generated for complex project regression testing

apiVersion: v1
kind: ConfigMap
metadata:
  name: generated-config
  namespace: default
data:
  config.yaml: |
    # TODO: Add configuration values
    generated: true
    file: {file_path}
"""
        else:
            return f"""# {file_path}
# Generated for complex project regression testing

# TODO: Implement actual content for this file
# This is a placeholder for testing large project structures
"""


def create_large_ecommerce_project() -> Path:
    """Create a large e-commerce project for testing."""
    temp_dir = Path(tempfile.mkdtemp(prefix="large_ecommerce_"))
    generator = LargeEcommercePlatform(temp_dir)

    planning_data = generator.generate_project()

    # Save planning data
    planning_file = temp_dir / "planning_output.json"
    with open(planning_file, "w") as f:
        json.dump(planning_data, f, indent=2)

    print(f"✅ Large e-commerce project created at: {temp_dir}")
    print(f"📊 Files created: {generator.file_count}")
    print(f"📄 Planning file: {planning_file}")

    return temp_dir


if __name__ == "__main__":
    create_large_ecommerce_project()

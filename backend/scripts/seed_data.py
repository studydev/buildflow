#!/usr/bin/env python3
"""Seed script to populate development database with sample content."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.content import Content
from app.models.enums import ContentStatus, ContentType


# Sample content data matching the mock data in content_service.py
SAMPLE_CONTENT = [
    {
        "title": "Azure Kubernetes Service (AKS) Workshop",
        "description": "Deploy and manage containerized applications using Azure Kubernetes Service. Learn to create clusters, deploy microservices, and implement DevOps practices.",
        "source_url": "https://github.com/Azure-Samples/aks-workshop",
        "content_type": ContentType.WORKSHOP,
        "categories": ["Azure", "Kubernetes", "Containers", "DevOps"],
        "level": "intermediate",
        "duration_minutes": 120,
        "icon": "🐳",
        "view_count": 1250,
        "bookmark_count": 89,
    },
    {
        "title": "Azure OpenAI GPT Integration",
        "description": "Build intelligent applications with Azure OpenAI GPT models. Explore prompt engineering, RAG patterns, and responsible AI practices.",
        "source_url": "https://github.com/Azure-Samples/openai-gpt",
        "content_type": ContentType.TUTORIAL,
        "categories": ["Azure", "AI", "OpenAI", "GPT"],
        "level": "beginner",
        "duration_minutes": 60,
        "icon": "🤖",
        "view_count": 890,
        "bookmark_count": 67,
    },
    {
        "title": "Azure Functions Serverless Workshop",
        "description": "Build event-driven serverless applications with Azure Functions. Learn triggers, bindings, and Durable Functions patterns.",
        "source_url": "https://github.com/Azure-Samples/functions-workshop",
        "content_type": ContentType.WORKSHOP,
        "categories": ["Azure", "Serverless", "Functions"],
        "level": "beginner",
        "duration_minutes": 90,
        "icon": "⚡",
        "view_count": 720,
        "bookmark_count": 45,
    },
    {
        "title": "Azure Static Web Apps with Vue.js",
        "description": "Deploy modern Vue.js applications to Azure Static Web Apps with automatic CI/CD, custom domains, and API integration.",
        "source_url": "https://github.com/Azure-Samples/swa-vue",
        "content_type": ContentType.TUTORIAL,
        "categories": ["Azure", "Web", "Vue.js", "Frontend"],
        "level": "beginner",
        "duration_minutes": 45,
        "icon": "🌐",
        "view_count": 560,
        "bookmark_count": 32,
    },
    {
        "title": "Azure Cosmos DB NoSQL Workshop",
        "description": "Master Azure Cosmos DB for globally distributed NoSQL databases. Learn partitioning strategies, consistency models, and best practices.",
        "source_url": "https://github.com/Azure-Samples/cosmosdb-workshop",
        "content_type": ContentType.WORKSHOP,
        "categories": ["Azure", "Database", "NoSQL", "Cosmos DB"],
        "level": "intermediate",
        "duration_minutes": 150,
        "icon": "🌍",
        "view_count": 430,
        "bookmark_count": 28,
    },
    {
        "title": "GitHub Actions CI/CD Pipeline",
        "description": "Automate your development workflow with GitHub Actions. Build, test, and deploy to Azure with confidence.",
        "source_url": "https://github.com/Azure-Samples/github-actions-demo",
        "content_type": ContentType.LAB,
        "categories": ["DevOps", "GitHub", "CI/CD"],
        "level": "intermediate",
        "duration_minutes": 75,
        "icon": "🔄",
        "view_count": 380,
        "bookmark_count": 22,
    },
    {
        "title": "Azure Container Apps Microservices",
        "description": "Deploy and scale microservices with Azure Container Apps. Learn Dapr integration, auto-scaling, and traffic management.",
        "source_url": "https://github.com/Azure-Samples/container-apps-microservices",
        "content_type": ContentType.WORKSHOP,
        "categories": ["Azure", "Containers", "Microservices", "Dapr"],
        "level": "advanced",
        "duration_minutes": 180,
        "icon": "📦",
        "view_count": 320,
        "bookmark_count": 25,
    },
    {
        "title": "Azure AI Search with Semantic Ranking",
        "description": "Implement intelligent search experiences with Azure AI Search. Explore semantic ranking, vector search, and hybrid queries.",
        "source_url": "https://github.com/Azure-Samples/azure-search-semantic",
        "content_type": ContentType.TUTORIAL,
        "categories": ["Azure", "AI", "Search"],
        "level": "intermediate",
        "duration_minutes": 60,
        "icon": "🔍",
        "view_count": 290,
        "bookmark_count": 18,
    },
    {
        "title": "Azure Logic Apps Integration Patterns",
        "description": "Design enterprise integration workflows with Azure Logic Apps. Connect SaaS apps, on-premises systems, and custom APIs.",
        "source_url": "https://github.com/Azure-Samples/logic-apps-patterns",
        "content_type": ContentType.TUTORIAL,
        "categories": ["Azure", "Integration", "Logic Apps", "Enterprise"],
        "level": "intermediate",
        "duration_minutes": 90,
        "icon": "🔗",
        "view_count": 210,
        "bookmark_count": 15,
    },
    {
        "title": "Azure DevOps Pipelines Workshop",
        "description": "Master Azure DevOps Pipelines for enterprise CI/CD. Learn multi-stage pipelines, environments, and approval gates.",
        "source_url": "https://github.com/Azure-Samples/azdo-pipelines-workshop",
        "content_type": ContentType.WORKSHOP,
        "categories": ["Azure", "DevOps", "CI/CD", "Pipelines"],
        "level": "intermediate",
        "duration_minutes": 120,
        "icon": "🚀",
        "view_count": 450,
        "bookmark_count": 35,
    },
    {
        "title": "Azure Event Grid Event-Driven Architecture",
        "description": "Build reactive applications with Azure Event Grid. Learn event schemas, filtering, and integration with other Azure services.",
        "source_url": "https://github.com/Azure-Samples/event-grid-workshop",
        "content_type": ContentType.TUTORIAL,
        "categories": ["Azure", "Event-Driven", "Serverless"],
        "level": "intermediate",
        "duration_minutes": 60,
        "icon": "📨",
        "view_count": 180,
        "bookmark_count": 12,
    },
    {
        "title": "Azure Bicep Infrastructure as Code",
        "description": "Define Azure infrastructure with Bicep. Learn modules, parameters, and deployment patterns for reliable IaC.",
        "source_url": "https://github.com/Azure-Samples/bicep-workshop",
        "content_type": ContentType.WORKSHOP,
        "categories": ["Azure", "IaC", "Bicep", "DevOps"],
        "level": "beginner",
        "duration_minutes": 90,
        "icon": "💪",
        "view_count": 340,
        "bookmark_count": 28,
    },
    {
        "title": "Azure Key Vault Secrets Management",
        "description": "Secure your applications with Azure Key Vault. Learn secrets, certificates, and managed identities best practices.",
        "source_url": "https://github.com/Azure-Samples/keyvault-tutorial",
        "content_type": ContentType.TUTORIAL,
        "categories": ["Azure", "Security", "Key Vault"],
        "level": "beginner",
        "duration_minutes": 45,
        "icon": "🔐",
        "view_count": 510,
        "bookmark_count": 42,
    },
    {
        "title": "Azure Monitor Application Insights",
        "description": "Implement observability with Azure Monitor and Application Insights. Learn custom metrics, distributed tracing, and alerts.",
        "source_url": "https://github.com/Azure-Samples/app-insights-workshop",
        "content_type": ContentType.WORKSHOP,
        "categories": ["Azure", "Monitoring", "Observability", "DevOps"],
        "level": "intermediate",
        "duration_minutes": 90,
        "icon": "📊",
        "view_count": 260,
        "bookmark_count": 19,
    },
    {
        "title": "Azure Service Bus Messaging Patterns",
        "description": "Implement reliable messaging with Azure Service Bus. Explore queues, topics, sessions, and dead-letter handling.",
        "source_url": "https://github.com/Azure-Samples/servicebus-patterns",
        "content_type": ContentType.TUTORIAL,
        "categories": ["Azure", "Messaging", "Integration"],
        "level": "intermediate",
        "duration_minutes": 75,
        "icon": "📬",
        "view_count": 195,
        "bookmark_count": 14,
    },
    {
        "title": "Azure SQL Database Best Practices",
        "description": "Optimize Azure SQL Database performance. Learn indexing strategies, query tuning, and high availability patterns.",
        "source_url": "https://github.com/Azure-Samples/sql-best-practices",
        "content_type": ContentType.TUTORIAL,
        "categories": ["Azure", "Database", "SQL"],
        "level": "advanced",
        "duration_minutes": 90,
        "icon": "🗄️",
        "view_count": 280,
        "bookmark_count": 21,
    },
    {
        "title": "Azure App Service Deep Dive",
        "description": "Master Azure App Service for web application hosting. Learn deployment slots, scaling, and hybrid connections.",
        "source_url": "https://github.com/Azure-Samples/app-service-workshop",
        "content_type": ContentType.WORKSHOP,
        "categories": ["Azure", "Web", "App Service"],
        "level": "beginner",
        "duration_minutes": 60,
        "icon": "🌐",
        "view_count": 420,
        "bookmark_count": 31,
    },
    {
        "title": "Azure API Management Gateway",
        "description": "Design and manage APIs with Azure API Management. Learn policies, versioning, and developer portal customization.",
        "source_url": "https://github.com/Azure-Samples/apim-workshop",
        "content_type": ContentType.WORKSHOP,
        "categories": ["Azure", "API", "Gateway"],
        "level": "intermediate",
        "duration_minutes": 120,
        "icon": "🚪",
        "view_count": 175,
        "bookmark_count": 13,
    },
    {
        "title": "Azure Blob Storage Patterns",
        "description": "Implement cloud storage solutions with Azure Blob Storage. Learn tiers, lifecycle policies, and data protection.",
        "source_url": "https://github.com/Azure-Samples/blob-storage-patterns",
        "content_type": ContentType.TUTORIAL,
        "categories": ["Azure", "Storage", "Data"],
        "level": "beginner",
        "duration_minutes": 45,
        "icon": "📦",
        "view_count": 390,
        "bookmark_count": 27,
    },
    {
        "title": "Azure Active Directory B2C Authentication",
        "description": "Implement customer identity with Azure AD B2C. Configure user flows, custom policies, and social identity providers.",
        "source_url": "https://github.com/Azure-Samples/aadb2c-workshop",
        "content_type": ContentType.WORKSHOP,
        "categories": ["Azure", "Identity", "Security", "Authentication"],
        "level": "advanced",
        "duration_minutes": 150,
        "icon": "👤",
        "view_count": 220,
        "bookmark_count": 16,
    },
]


def create_content_items() -> list[Content]:
    """Create Content instances from sample data."""
    contents = []
    base_date = datetime.now() - timedelta(days=90)
    
    for i, data in enumerate(SAMPLE_CONTENT):
        # Stagger published dates
        published_at = base_date + timedelta(days=i * 4)
        
        content = Content(
            id=str(uuid4()),
            contributor_id="system",  # System seed data
            title=data["title"],
            description=data["description"],
            source_url=data["source_url"],
            content_type=data["content_type"],
            status=ContentStatus.PUBLISHED,
            categories=data["categories"],
            level=data.get("level", "beginner"),
            duration_minutes=data.get("duration_minutes"),
            icon=data.get("icon"),
            view_count=data.get("view_count", 0),
            bookmark_count=data.get("bookmark_count", 0),
            published_at=published_at,
        )
        contents.append(content)
    
    return contents


async def seed_content_to_cosmos():
    """Seed content to Cosmos DB."""
    from app.repositories.content_repo import get_content_repo
    
    repo = get_content_repo()
    contents = create_content_items()
    
    print(f"Seeding {len(contents)} content items...")
    
    for content in contents:
        try:
            await repo.create(content)
            print(f"  ✓ Created: {content.title[:50]}...")
        except Exception as e:
            if "Conflict" in str(e) or "409" in str(e):
                print(f"  - Skipped (exists): {content.title[:50]}...")
            else:
                print(f"  ✗ Error: {content.title[:50]}: {e}")
    
    print("\nSeed complete!")


def print_sample_content():
    """Print sample content for verification (no DB required)."""
    contents = create_content_items()
    
    print(f"\n📚 Sample Content ({len(contents)} items)")
    print("=" * 60)
    
    for content in contents:
        print(f"\n{content.icon} {content.title}")
        print(f"   Type: {content.content_type.value}")
        print(f"   Level: {content.level}")
        print(f"   Duration: {content.duration_minutes} min")
        print(f"   Categories: {', '.join(content.categories)}")
    
    print("\n" + "=" * 60)
    print("Run with --cosmos flag to seed to Cosmos DB")


if __name__ == "__main__":
    if "--cosmos" in sys.argv:
        print("🌱 Seeding to Cosmos DB...")
        asyncio.run(seed_content_to_cosmos())
    elif "--json" in sys.argv:
        # Output as JSON for debugging
        import json
        contents = create_content_items()
        items = [c.to_cosmos_item() for c in contents]
        print(json.dumps(items, indent=2, default=str))
    else:
        print_sample_content()

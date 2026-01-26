"""Image Generation Service using Azure OpenAI DALL-E.

Generates professional thumbnail images for Microsoft Azure technical workshops.
"""

import base64
import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Storage container for generated thumbnail images
REPO_IMAGES_CONTAINER = "repo-images"


class ImageGenerationError(Exception):
    """Error during image generation."""
    pass


# Domain configurations for workshop thumbnails
DOMAIN_CONFIGS = {
    "ai_agents": {
        "domain_name": "AI & Agents",
        "primary_color": "Cyan (#00BCF2)",
        "secondary_color": "Neon Blue (#2ED9FF)",
        "business_problems": "Manual decision-making, scattered AI experiments, lack of orchestration between tools",
        "core_workshop_focus": "Building agent-based AI workflows with Azure AI",
        "key_technologies": "Azure AI Studio, Azure OpenAI, Agents, Functions",
        "learning_outcomes": "Autonomous agents, connected AI workflows, faster and smarter decisions",
        "keywords": ["ai", "openai", "gpt", "agent", "copilot", "llm", "ml", "machine learning", "cognitive", "bot"],
    },
    "data_fabric": {
        "domain_name": "Data & Analytics (Fabric)",
        "primary_color": "Indigo (#3B4FB3)",
        "secondary_color": "Violet (#7B83EB)",
        "business_problems": "Data silos, slow analytics, disconnected BI tools",
        "core_workshop_focus": "Unified analytics with Microsoft Fabric",
        "key_technologies": "Microsoft Fabric, OneLake, Synapse, Power BI",
        "learning_outcomes": "Unified data platform, real-time insights, AI-ready analytics foundation",
        "keywords": ["fabric", "synapse", "data", "analytics", "power bi", "warehouse", "lakehouse", "onelake"],
    },
    "security": {
        "domain_name": "Security & Compliance",
        "primary_color": "Red (#E81123)",
        "secondary_color": "Orange (#FF8C00)",
        "business_problems": "Security gaps, compliance risks, fragmented identity management, threat blind spots",
        "core_workshop_focus": "End-to-end security with Microsoft Defender and Entra",
        "key_technologies": "Microsoft Defender, Entra ID, Sentinel, Purview",
        "learning_outcomes": "Zero Trust architecture, unified security operations, proactive threat protection",
        "keywords": ["security", "defender", "sentinel", "entra", "identity", "zero trust", "compliance", "purview"],
    },
    "devops_github": {
        "domain_name": "DevOps & GitHub",
        "primary_color": "GitHub Green (#238636)",
        "secondary_color": "Azure DevOps Blue (#0078D7)",
        "business_problems": "Slow release cycles, manual deployments, inconsistent CI/CD, collaboration gaps",
        "core_workshop_focus": "Modern DevOps with GitHub and Azure DevOps",
        "key_technologies": "GitHub Actions, Azure DevOps, Copilot, Container Apps",
        "learning_outcomes": "Automated pipelines, faster deployments, developer productivity, secure supply chain",
        "keywords": ["github", "devops", "ci/cd", "actions", "pipeline", "container", "docker", "kubernetes", "aks"],
    },
    "cloud_infra": {
        "domain_name": "Cloud Infrastructure",
        "primary_color": "Azure Blue (#0078D4)",
        "secondary_color": "Teal (#008575)",
        "business_problems": "Legacy infrastructure, manual provisioning, scaling challenges, cost management",
        "core_workshop_focus": "Cloud-native infrastructure with Azure",
        "key_technologies": "Azure VMs, AKS, Bicep, Azure Arc, Terraform",
        "learning_outcomes": "Automated infrastructure, scalable architecture, optimized cloud costs",
        "keywords": ["infrastructure", "vm", "network", "bicep", "terraform", "arc", "hybrid", "migration"],
    },
    "low_code": {
        "domain_name": "Low Code & Power Platform",
        "primary_color": "Power Purple (#742774)",
        "secondary_color": "Magenta (#E3008C)",
        "business_problems": "IT bottlenecks, slow app development, manual business processes, citizen developer gaps",
        "core_workshop_focus": "Rapid app development with Power Platform",
        "key_technologies": "Power Apps, Power Automate, Power Pages, Copilot Studio",
        "learning_outcomes": "Citizen developers empowered, automated workflows, rapid prototyping",
        "keywords": ["power apps", "power automate", "power platform", "low code", "no code", "power pages", "copilot studio"],
    },
    "default": {
        "domain_name": "Microsoft Azure Workshop",
        "primary_color": "Azure Blue (#0078D4)",
        "secondary_color": "Microsoft Purple (#5C2D91)",
        "business_problems": "Digital transformation challenges, legacy systems, skill gaps",
        "core_workshop_focus": "Hands-on learning with Microsoft Azure technologies",
        "key_technologies": "Azure, Microsoft 365, GitHub",
        "learning_outcomes": "Cloud expertise, modern development skills, business innovation",
        "keywords": [],
    },
}


class ImageGenerationService:
    """
    Service for generating AI-powered thumbnail images using Azure OpenAI DALL-E.

    Creates professional hero images for Microsoft Azure technical workshops
    that visually represent the workshop content and technologies.
    """

    # Master prompt template for domain-based thumbnail generation
    PROMPT_TEMPLATE = """Create a professional workshop thumbnail image.

Image Purpose:
A representative visual that helps viewers instantly understand
which Microsoft / Azure / GitHub workshop is most suitable
for a specific business problem.

Aspect Ratio: 3:2

Domain / Learning Area: {domain_name}

Primary Theme Color: {primary_color}
Secondary Accent Color: {secondary_color}

Business Problems to Visualize (Left Side):
{business_problems}

Workshop Learning Focus (Center):
{core_workshop_focus}
Key Technologies: {key_technologies}

Transformed Outcome After Learning (Right Side):
{learning_outcomes}

Design Requirements:
- Clean, professional, Microsoft Fluent Design style
- Strong visual consistency across all domains, differentiated mainly by color and core technology focus
- One continuous scene showing a clear left-to-right problem-solving flow
- Allow minimal, clean text labels for key technologies (e.g. Azure AI, Fabric, Copilot, Defender, GitHub)
- Abstract but recognizable representations:
  - Cloud infrastructure, AI brains, agents, data graphs, security shields, pipelines
- No human faces, no logos, no marketing slogans
- Modern 3D isometric or refined flat design
- Light background with domain-specific color accents
- The image should feel like:
  "In this situation, learning this workshop is the right choice."
"""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        deployment: Optional[str] = None,
    ):
        """Initialize image generation service."""
        self.endpoint = endpoint or settings.azure_openai_endpoint
        self.api_key = api_key or settings.azure_openai_api_key
        self.deployment = deployment or getattr(settings, 'azure_dalle_deployment', 'gpt-image-1.5')
        self.api_version = settings.azure_openai_api_version
        self.image_size = getattr(settings, 'azure_dalle_image_size', '1536x1024')
        self._client: Optional[httpx.AsyncClient] = None

        # Log configuration status (without sensitive data)
        logger.info(
            f"ImageGenerationService initialized: "
            f"endpoint={'set' if self.endpoint else 'NOT SET'}, "
            f"api_key={'set' if self.api_key else 'NOT SET'}, "
            f"deployment={self.deployment}, "
            f"image_size={self.image_size}"
        )

    def _is_configured(self) -> bool:
        """Check if service is properly configured."""
        return bool(self.endpoint and self.api_key)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)  # Image generation can take time
        return self._client

    def _detect_domain(
        self,
        title: str,
        description: str,
        technologies: list[str],
        categories: list[str],
    ) -> str:
        """
        Detect the workshop domain based on content.

        Returns the domain key (e.g., 'ai_agents', 'data_fabric', etc.)
        """
        # Combine all text for keyword matching
        all_text = " ".join([
            title.lower(),
            description.lower(),
            " ".join(t.lower() for t in (technologies or [])),
            " ".join(c.lower() for c in (categories or [])),
        ])

        # Score each domain based on keyword matches
        scores = {}
        for domain_key, config in DOMAIN_CONFIGS.items():
            if domain_key == "default":
                continue
            score = sum(1 for kw in config["keywords"] if kw in all_text)
            if score > 0:
                scores[domain_key] = score

        # Return highest scoring domain, or default
        if scores:
            best_domain = max(scores, key=scores.get)
            logger.info(f"Detected domain: {best_domain} (score: {scores[best_domain]})")
            return best_domain

        logger.info("No specific domain detected, using default")
        return "default"

    def _build_prompt(
        self,
        title: str,
        description: str,
        technologies: list[str],
        categories: list[str] = None,
    ) -> str:
        """Build the domain-based image generation prompt."""
        # Detect domain
        domain_key = self._detect_domain(title, description, technologies, categories or [])
        config = DOMAIN_CONFIGS[domain_key]

        # Override key_technologies if provided
        tech_str = ", ".join(technologies[:6]) if technologies else config["key_technologies"]

        prompt = self.PROMPT_TEMPLATE.format(
            domain_name=config["domain_name"],
            primary_color=config["primary_color"],
            secondary_color=config["secondary_color"],
            business_problems=config["business_problems"],
            core_workshop_focus=config["core_workshop_focus"],
            key_technologies=tech_str,
            learning_outcomes=config["learning_outcomes"],
        )

        logger.debug(f"Generated prompt for domain '{domain_key}':\n{prompt[:500]}...")
        return prompt

    async def generate_thumbnail(
        self,
        title: str,
        description: str,
        technologies: list[str],
        categories: list[str] = None,
    ) -> bytes:
        """
        Generate a thumbnail image using DALL-E.

        Args:
            title: Workshop title
            description: Workshop description
            technologies: List of technologies used
            categories: Optional list of categories for domain detection

        Returns:
            Image bytes (PNG format)

        Raises:
            ImageGenerationError: If generation fails
        """
        # Check configuration
        if not self._is_configured():
            raise ImageGenerationError(
                f"Image generation not configured: "
                f"endpoint={'set' if self.endpoint else 'MISSING'}, "
                f"api_key={'set' if self.api_key else 'MISSING'}"
            )

        prompt = self._build_prompt(title, description, technologies, categories)

        logger.info(f"Generating thumbnail for: {title[:50]}...")
        logger.debug(f"DALL-E request URL: {self.endpoint}/openai/deployments/{self.deployment}/images/generations")

        try:
            client = await self._get_client()

            # Build URL
            base_url = self.endpoint.rstrip('/')
            url = f"{base_url}/openai/deployments/{self.deployment}/images/generations"
            params = {"api-version": self.api_version}

            # Use API key auth
            headers = {
                "api-key": self.api_key,
                "Content-Type": "application/json",
            }

            body = {
                "prompt": prompt,
                "n": 1,
                "size": self.image_size,
                "quality": "medium",
                "output_format": "png",
            }

            response = await client.post(
                url,
                params=params,
                headers=headers,
                json=body,
            )

            if response.status_code != 200:
                error_msg = f"DALL-E API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise ImageGenerationError(error_msg)

            result = response.json()

            # Extract base64 image data
            if "data" not in result or not result["data"]:
                raise ImageGenerationError("No image data in response")

            b64_image = result["data"][0].get("b64_json")
            if not b64_image:
                # Try URL-based response
                image_url = result["data"][0].get("url")
                if image_url:
                    img_response = await client.get(image_url)
                    if img_response.status_code == 200:
                        return img_response.content
                    raise ImageGenerationError(f"Failed to download image from URL: {img_response.status_code}")
                raise ImageGenerationError("No image data or URL in response")

            # Decode base64 to bytes
            image_bytes = base64.b64decode(b64_image)
            logger.info(f"Successfully generated thumbnail ({len(image_bytes)} bytes)")

            return image_bytes

        except httpx.TimeoutException as e:
            raise ImageGenerationError(f"Timeout generating image: {e}")
        except httpx.HTTPError as e:
            raise ImageGenerationError(f"HTTP error generating image: {e}")
        except Exception as e:
            if isinstance(e, ImageGenerationError):
                raise
            raise ImageGenerationError(f"Unexpected error: {e}")

    async def generate_and_upload_thumbnail(
        self,
        content_id: str,
        title: str,
        description: str,
        technologies: list[str],
        categories: list[str] = None,
    ) -> str:
        """
        Generate thumbnail and upload to Azure Storage.

        Args:
            content_id: Content ID for blob path
            title: Workshop title
            description: Workshop description
            technologies: List of technologies
            categories: Optional categories

        Returns:
            SAS URL of uploaded image (valid for 1 year)

        Raises:
            ImageGenerationError: If generation or upload fails
        """
        from app.services.storage_service import StorageError, StorageService

        logger.info(f"Starting thumbnail generation for content_id={content_id}")

        # Generate image
        image_bytes = await self.generate_thumbnail(
            title=title,
            description=description,
            technologies=technologies,
            categories=categories,
        )

        logger.info(f"Generated image: {len(image_bytes)} bytes, uploading to storage...")

        # Build blob path
        blob_path = f"{content_id}/thumbnail.png"

        try:
            # Upload to storage
            storage_service = StorageService()
            logger.info(f"StorageService initialized, uploading to {REPO_IMAGES_CONTAINER}/{blob_path}")

            await storage_service.upload_blob(
                container_name=REPO_IMAGES_CONTAINER,
                blob_path=blob_path,
                data=image_bytes,
                content_type="image/png",
                metadata={
                    "content_id": str(content_id),
                    "generated_by": "dalle",
                    "model": self.deployment,
                },
            )

            logger.info("Upload complete, generating SAS URL...")

            # Generate SAS URL (valid for 1 year = 8760 hours)
            sas_url = storage_service.get_sas_url(
                container_name=REPO_IMAGES_CONTAINER,
                blob_path=blob_path,
                expiry_hours=8760,  # 1 year
                permissions="r",
            )

            logger.info(f"Thumbnail uploaded successfully. SAS URL generated for content_id={content_id}")
            return sas_url

        except StorageError as e:
            logger.error(f"Storage error uploading thumbnail: {e}")
            raise ImageGenerationError(f"Storage error: {e}")
        except Exception as e:
            logger.error(f"Failed to upload image: {type(e).__name__}: {e}")
            raise ImageGenerationError(f"Failed to upload image: {e}")

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton instance
_image_generation_service: Optional[ImageGenerationService] = None


def get_image_generation_service() -> ImageGenerationService:
    """Get singleton image generation service instance."""
    global _image_generation_service
    if _image_generation_service is None:
        _image_generation_service = ImageGenerationService()
    return _image_generation_service

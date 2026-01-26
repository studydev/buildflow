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


class ImageGenerationService:
    """
    Service for generating AI-powered thumbnail images using Azure OpenAI DALL-E.

    Creates professional hero images for Microsoft Azure technical workshops
    that visually represent the workshop content and technologies.
    """

    # Microsoft branding prompt template
    PROMPT_TEMPLATE = """Create a professional, modern hero image for a Microsoft Azure technical workshop.

Workshop Title: {title}
Workshop Description: {description}
Technologies: {technologies}

Design Requirements:
- Clean, minimalist style with a professional tech aesthetic
- Use Microsoft's Fluent Design language with subtle gradients
- Feature abstract representations of the core technologies (e.g., cloud shapes for Azure, connected nodes for AI/ML, containers for Kubernetes)
- Color palette: Azure Blue (#0078D4), Microsoft Purple (#5C2D91), with complementary tech colors
- No text, logos, or human faces - focus on abstract technology concepts
- Modern 3D isometric or flat design elements
- Light background with vibrant accent colors
- Convey innovation, learning, and cloud-native technology

The image should intuitively represent the workshop's goal and make viewers curious to learn more about Microsoft and Azure technologies."""

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

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)  # Image generation can take time
        return self._client

    def _build_prompt(
        self,
        title: str,
        description: str,
        technologies: list[str],
    ) -> str:
        """Build the image generation prompt."""
        tech_str = ", ".join(technologies[:10]) if technologies else "Azure, Cloud"

        # Truncate description if too long
        desc = description[:500] + "..." if len(description) > 500 else description

        return self.PROMPT_TEMPLATE.format(
            title=title,
            description=desc,
            technologies=tech_str,
        )

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
            categories: Optional list of categories

        Returns:
            Image bytes (PNG format)

        Raises:
            ImageGenerationError: If generation fails
        """
        prompt = self._build_prompt(title, description, technologies)

        logger.info(f"Generating thumbnail for: {title[:50]}...")

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
        from app.services.storage_service import StorageService

        # Generate image
        image_bytes = await self.generate_thumbnail(
            title=title,
            description=description,
            technologies=technologies,
            categories=categories,
        )

        # Build blob path
        blob_path = f"{content_id}/thumbnail.png"

        try:
            # Upload to storage
            storage_service = StorageService()
            await storage_service.upload_blob(
                container_name=REPO_IMAGES_CONTAINER,
                blob_path=blob_path,
                data=image_bytes,
                content_type="image/png",
                metadata={
                    "content_id": content_id,
                    "generated_by": "dalle",
                    "model": self.deployment,
                },
            )

            # Generate SAS URL (valid for 1 year = 8760 hours)
            sas_url = storage_service.get_sas_url(
                container_name=REPO_IMAGES_CONTAINER,
                blob_path=blob_path,
                expiry_hours=8760,  # 1 year
                permissions="r",
            )

            logger.info("Uploaded thumbnail with SAS URL")
            return sas_url

        except Exception as e:
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

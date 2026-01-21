"""Asset Generation Pipeline for creating thumbnails and OG images.

Per design.md §3.4 Asset Generation Pipeline.
"""

import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from app.config import get_settings
from app.models.enums import PipelineType, AssetType, Visibility
from app.models.generated_asset import GeneratedAsset
from app.pipelines.base import BasePipeline
from app.repositories.content_repo import get_content_repo
from app.repositories.pipeline_repo import get_pipeline_repository
from app.schemas.pipeline import PipelineMessage
from app.services.storage_service import (
    get_storage_service,
    StorageService,
    GENERATED_ASSETS_CONTAINER,
)
from app.services.llm_service import get_llm_service, LLMService

logger = logging.getLogger(__name__)
settings = get_settings()


# Default asset dimensions per asset type
ASSET_DIMENSIONS = {
    AssetType.THUMBNAIL: {"width": 400, "height": 300, "format": "png"},
    AssetType.PREVIEW: {"width": 800, "height": 600, "format": "png"},
    AssetType.OG_IMAGE: {"width": 1200, "height": 630, "format": "png"},
}

# Default assets to generate
DEFAULT_ASSET_TYPES = [AssetType.THUMBNAIL, AssetType.OG_IMAGE]


class AssetGenerationPipeline(BasePipeline):
    """
    Pipeline for generating visual assets (thumbnails, OG images).
    
    Implements design.md §3.4 Asset Generation Pipeline:
    - Generates thumbnails and OG images using templates or AI
    - Uploads to Azure Blob Storage
    - Creates GeneratedAsset records
    - Idempotency via SHA256(content_id + asset_type + enrichment_version)
    
    Input params:
        content_id: UUID - Content to generate assets for
        asset_types: list[str] - Types to generate (thumbnail, preview, og_image)
        force_regenerate: bool - Regenerate even if exists
        
    Output:
        assets: list of generated asset info
        generated_at: datetime
    """
    
    pipeline_type = PipelineType.ASSET_GENERATION
    max_attempts = 2  # Per design.md §3.4 retry_policy
    
    def __init__(self):
        """Initialize AssetGenerationPipeline."""
        super().__init__()
        self._content_repo = None
        self._storage_service = None
        self._llm_service = None
        self._asset_repo = None
    
    @property
    def content_repo(self):
        """Lazy load content repository."""
        if self._content_repo is None:
            self._content_repo = get_content_repo()
        return self._content_repo
    
    @property
    def storage_service(self) -> StorageService:
        """Lazy load storage service."""
        if self._storage_service is None:
            self._storage_service = get_storage_service()
        return self._storage_service
    
    @property
    def llm_service(self) -> LLMService:
        """Lazy load LLM service for AI generation."""
        if self._llm_service is None:
            self._llm_service = get_llm_service()
        return self._llm_service
    
    @property
    def asset_repo(self):
        """Lazy load generated asset repository."""
        if self._asset_repo is None:
            from app.repositories.generated_asset_repo import get_generated_asset_repo
            self._asset_repo = get_generated_asset_repo()
        return self._asset_repo
    
    async def execute(self, message: PipelineMessage) -> Dict[str, Any]:
        """
        Execute asset generation pipeline.
        
        Args:
            message: Pipeline message with input parameters
            
        Returns:
            Output summary with generated asset info
        """
        input_params = message.input_params
        content_id = input_params.get("content_id")
        asset_types_str = input_params.get("asset_types", ["thumbnail", "og_image"])
        force_regenerate = input_params.get("force_regenerate", False)
        
        if not content_id:
            raise ValueError("content_id is required")
        
        # Parse asset types
        asset_types = [
            AssetType(t) if isinstance(t, str) else t 
            for t in asset_types_str
        ]
        
        logger.info(
            f"Starting asset generation for content {content_id}",
            extra={
                "correlation_id": message.correlation_id,
                "run_id": str(message.run_id),
                "asset_types": [t.value for t in asset_types],
            }
        )
        
        # Load content
        content = await self.content_repo.get_by_id_cross_partition(content_id)
        if not content:
            raise ValueError(f"Content not found: {content_id}")
        
        # Generate each asset type
        generated_assets: List[Dict[str, Any]] = []
        
        for asset_type in asset_types:
            # Check idempotency
            idempotency_key = self._generate_idempotency_key(
                content_id, asset_type.value, content.enrichment_version or "1.0.0"
            )
            
            if not force_regenerate:
                existing = await self._check_existing_asset(content_id, asset_type)
                if existing:
                    logger.info(f"Asset {asset_type.value} already exists, skipping")
                    generated_assets.append({
                        "asset_type": asset_type.value,
                        "status": "skipped",
                        "reason": "already_exists",
                        "storage_url": existing.storage_url,
                    })
                    continue
            
            # Generate the asset
            try:
                asset_info = await self._generate_asset(
                    content=content,
                    asset_type=asset_type,
                    run_id=message.run_id,
                )
                generated_assets.append(asset_info)
                
            except Exception as e:
                logger.error(f"Failed to generate {asset_type.value}: {e}")
                generated_assets.append({
                    "asset_type": asset_type.value,
                    "status": "failed",
                    "error": str(e),
                })
        
        # Update content with asset URLs
        await self._update_content_assets(content, generated_assets)
        
        output_summary = {
            "content_id": content_id,
            "assets": generated_assets,
            "total_generated": len([a for a in generated_assets if a.get("status") == "success"]),
            "total_skipped": len([a for a in generated_assets if a.get("status") == "skipped"]),
            "total_failed": len([a for a in generated_assets if a.get("status") == "failed"]),
            "generated_at": datetime.utcnow().isoformat(),
        }
        
        logger.info(
            f"Asset generation completed for content {content_id}",
            extra={"correlation_id": message.correlation_id, "run_id": str(message.run_id)}
        )
        
        return output_summary
    
    def _generate_idempotency_key(
        self,
        content_id: str,
        asset_type: str,
        enrichment_version: str,
    ) -> str:
        """
        Generate idempotency key per design.md §3.4.
        
        Key: SHA256(content_id + asset_type + enrichment_version)
        """
        import hashlib
        data = f"{content_id}:{asset_type}:{enrichment_version}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    async def _check_existing_asset(
        self,
        content_id: str,
        asset_type: AssetType,
    ) -> Optional[GeneratedAsset]:
        """Check if asset already exists for this content."""
        try:
            return await self.asset_repo.get_by_content_and_type(
                content_id=UUID(content_id) if isinstance(content_id, str) else content_id,
                asset_type=asset_type,
            )
        except Exception:
            return None
    
    async def _generate_asset(
        self,
        content,
        asset_type: AssetType,
        run_id: UUID,
    ) -> Dict[str, Any]:
        """
        Generate a single asset.
        
        Uses template-based generation for now.
        TODO: Add DALL-E integration for AI-generated thumbnails.
        """
        dimensions = ASSET_DIMENSIONS.get(asset_type, ASSET_DIMENSIONS[AssetType.THUMBNAIL])
        
        # Generate image using template
        image_data = await self._generate_template_image(
            title=content.title,
            categories=content.categories,
            asset_type=asset_type,
            width=dimensions["width"],
            height=dimensions["height"],
        )
        
        # Build storage path
        blob_path = self.storage_service.build_asset_path(
            content_id=content.id,
            asset_type=asset_type.value,
            format=dimensions["format"],
        )
        
        # Upload to blob storage
        storage_url = await self.storage_service.upload_blob(
            container_name=GENERATED_ASSETS_CONTAINER,
            blob_path=blob_path,
            data=image_data,
            content_type=f"image/{dimensions['format']}",
            metadata={
                "content_id": str(content.id),
                "asset_type": asset_type.value,
                "enrichment_version": content.enrichment_version or "1.0.0",
            },
        )
        
        # Create GeneratedAsset record
        asset = GeneratedAsset(
            id=uuid4(),
            content_id=UUID(content.id) if isinstance(content.id, str) else content.id,
            run_id=run_id,
            asset_type=asset_type,
            storage_url=storage_url,
            cdn_url=self._build_cdn_url(blob_path),
            model_used="template",
            visibility=Visibility.PUBLIC,
            width=dimensions["width"],
            height=dimensions["height"],
            format=dimensions["format"],
            size_bytes=len(image_data),
            enrichment_version=content.enrichment_version or "1.0.0",
        )
        
        await self.asset_repo.create(asset)
        
        return {
            "asset_type": asset_type.value,
            "status": "success",
            "storage_url": storage_url,
            "cdn_url": asset.cdn_url,
            "width": dimensions["width"],
            "height": dimensions["height"],
            "format": dimensions["format"],
            "size_bytes": len(image_data),
        }
    
    async def _generate_template_image(
        self,
        title: str,
        categories: List[str],
        asset_type: AssetType,
        width: int,
        height: int,
    ) -> bytes:
        """
        Generate a template-based image.
        
        Creates a simple branded image with title and categories.
        Uses Pillow for image generation.
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            logger.warning("Pillow not installed, returning placeholder SVG")
            return self._generate_placeholder_svg(title, width, height)
        
        # Brand colors
        bg_color = (0, 120, 212)  # Azure blue
        text_color = (255, 255, 255)
        accent_color = (80, 160, 240)
        
        # Create image
        img = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw gradient overlay (simple vertical bars)
        for i in range(0, width, 20):
            alpha = int(20 + (i / width) * 30)
            draw.rectangle([i, 0, i + 10, height], fill=(0, 100, 180))
        
        # Load font (fallback to default)
        try:
            font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
            font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
        except (OSError, IOError):
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        # Draw title (wrap text if needed)
        max_chars = width // 20
        wrapped_title = title[:max_chars] + "..." if len(title) > max_chars else title
        
        # Center the title
        text_bbox = draw.textbbox((0, 0), wrapped_title, font=font_large)
        text_width = text_bbox[2] - text_bbox[0]
        text_x = (width - text_width) // 2
        text_y = height // 2 - 30
        
        draw.text((text_x, text_y), wrapped_title, fill=text_color, font=font_large)
        
        # Draw categories
        if categories:
            cat_text = " | ".join(categories[:3])
            cat_bbox = draw.textbbox((0, 0), cat_text, font=font_small)
            cat_width = cat_bbox[2] - cat_bbox[0]
            cat_x = (width - cat_width) // 2
            draw.text((cat_x, text_y + 50), cat_text, fill=accent_color, font=font_small)
        
        # Draw "BuildFlow" branding at bottom
        draw.text((20, height - 40), "BuildFlow", fill=(200, 220, 255), font=font_small)
        
        # Save to bytes
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()
    
    def _generate_placeholder_svg(
        self,
        title: str,
        width: int,
        height: int,
    ) -> bytes:
        """Generate a placeholder SVG when Pillow is not available."""
        escaped_title = title[:50].replace('"', '&quot;').replace('<', '&lt;')
        
        svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="#0078D4"/>
  <text x="50%" y="45%" font-family="Arial, sans-serif" font-size="24" fill="white" 
        text-anchor="middle" dominant-baseline="middle">{escaped_title}</text>
  <text x="50%" y="60%" font-family="Arial, sans-serif" font-size="14" fill="#B4D5F0" 
        text-anchor="middle" dominant-baseline="middle">BuildFlow</text>
</svg>'''
        
        return svg.encode('utf-8')
    
    def _build_cdn_url(self, blob_path: str) -> Optional[str]:
        """Build CDN URL if configured."""
        cdn_host = settings.azure_storage_cdn_host
        if cdn_host:
            return f"https://{cdn_host}/assets/{blob_path}"
        return None
    
    async def _update_content_assets(
        self,
        content,
        generated_assets: List[Dict[str, Any]],
    ) -> None:
        """Update content with generated asset URLs."""
        updated = False
        
        for asset in generated_assets:
            if asset.get("status") != "success":
                continue
            
            asset_type = asset.get("asset_type")
            url = asset.get("cdn_url") or asset.get("storage_url")
            
            if asset_type == "thumbnail" and url:
                content.thumbnail_url = url
                updated = True
            # og_image could be stored in a new field if needed
        
        if updated:
            content.updated_at = datetime.utcnow()
            await self.content_repo.update(content)

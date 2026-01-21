"""
Pipeline runner entry point for Azure Container Apps Jobs.

Per tasks.md T117: Create pipeline runner entry point.

This module is the entry point for Container Apps Jobs:
- Reads pipeline message from environment variable
- Dispatches to correct pipeline class
- Handles execution and exit codes
"""

import argparse
import asyncio
import logging
import os
import sys
from typing import Optional

# Configure logging before imports
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s", "module": "%(module)s"}',
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def get_pipeline_class(pipeline_type: str):
    """
    Get the pipeline class for a given type.

    Returns actual pipeline implementations where available,
    falls back to placeholder for unimplemented types.
    """
    from typing import Any

    from app.models.enums import PipelineType
    from app.pipelines.base import BasePipeline
    from app.schemas.pipeline import PipelineMessage

    # Pipeline registry - maps type strings to pipeline classes
    PIPELINE_REGISTRY = {}

    # Import and register implemented pipelines
    try:
        from app.pipelines.analysis import AnalysisPipeline
        PIPELINE_REGISTRY["analysis"] = AnalysisPipeline
    except ImportError:
        pass

    try:
        from app.pipelines.enrichment import EnrichmentPipeline
        PIPELINE_REGISTRY["enrichment"] = EnrichmentPipeline
    except ImportError:
        pass

    try:
        from app.pipelines.indexing import IndexingPipeline
        PIPELINE_REGISTRY["indexing"] = IndexingPipeline
    except ImportError:
        pass

    try:
        from app.pipelines.localization import LocalizationPipeline
        PIPELINE_REGISTRY["localization"] = LocalizationPipeline
    except ImportError:
        pass

    try:
        from app.pipelines.asset_generation import AssetGenerationPipeline
        PIPELINE_REGISTRY["asset_generation"] = AssetGenerationPipeline
    except ImportError:
        pass

    # Check if we have a real implementation
    if pipeline_type in PIPELINE_REGISTRY:
        return PIPELINE_REGISTRY[pipeline_type]()

    # Fallback to placeholder for unimplemented pipelines
    class PlaceholderPipeline(BasePipeline):
        """
        Placeholder pipeline for unimplemented pipeline types.

        Does minimal work to demonstrate the pipeline lifecycle.
        """

        max_attempts = 3

        def __init__(self, pipeline_type: PipelineType):
            super().__init__()
            self.pipeline_type = pipeline_type

        async def execute(self, message: PipelineMessage) -> dict[str, Any]:
            """
            Placeholder execution.
            """
            logger.info(
                f"Executing {self.pipeline_type.value} pipeline (placeholder)",
                extra={
                    "run_id": str(message.run_id),
                    "pipeline_type": self.pipeline_type.value,
                    "correlation_id": message.correlation_id,
                }
            )

            # Simulate some work
            await asyncio.sleep(1)

            return {
                "placeholder": True,
                "message": f"{self.pipeline_type.value} pipeline executed successfully",
                "input_params": message.input_params,
            }

    # Return placeholder for unimplemented types
    pipeline_type_enum = PipelineType(pipeline_type)
    logger.warning(
        f"No implementation for {pipeline_type} pipeline, using placeholder",
        extra={"pipeline_type": pipeline_type}
    )
    return PlaceholderPipeline(pipeline_type_enum)


async def run_pipeline(message_json: str, pipeline_type: Optional[str] = None) -> int:
    """
    Run a pipeline from a Service Bus message.

    Args:
        message_json: JSON string of PipelineMessage
        pipeline_type: Optional override for pipeline type

    Returns:
        Exit code: 0 for success, 1 for failure
    """
    from app.schemas.pipeline import PipelineMessage

    try:
        # Parse message
        message = PipelineMessage.from_service_bus_message(message_json)

        logger.info(
            "Pipeline runner starting",
            extra={
                "run_id": str(message.run_id),
                "pipeline_type": message.pipeline_type.value if hasattr(message.pipeline_type, 'value') else message.pipeline_type,
                "attempt_number": message.attempt_number,
                "correlation_id": message.correlation_id,
            }
        )

        # Get pipeline class
        ptype = pipeline_type or message.pipeline_type
        # Convert enum to string value
        ptype_str = getattr(ptype, 'value', None) or str(ptype)

        pipeline = get_pipeline_class(ptype_str)

        # Execute pipeline
        result = await pipeline.run(message)

        if result.success:
            logger.info(
                "Pipeline completed successfully",
                extra={
                    "run_id": str(message.run_id),
                    "pipeline_type": ptype_str,
                    "output": result.output,
                }
            )
            return 0
        else:
            logger.error(
                "Pipeline failed",
                extra={
                    "run_id": str(message.run_id),
                    "pipeline_type": ptype_str,
                    "error": result.error,
                }
            )
            return 1

    except Exception as e:
        logger.error(
            "Pipeline runner error",
            extra={"error": str(e)},
            exc_info=True,
        )
        return 1


def main():
    """
    Main entry point for pipeline runner.

    Reads message from:
    1. PIPELINE_MESSAGE environment variable (set by Container Apps Jobs)
    2. SERVICEBUS_MESSAGE environment variable (alternative)
    3. --message command line argument (for testing)
    """
    parser = argparse.ArgumentParser(description="BuildFlow Pipeline Runner")
    parser.add_argument(
        "--type",
        choices=["analysis", "enrichment", "localization", "asset_generation", "indexing"],
        help="Pipeline type to run (optional, usually from message)",
    )
    parser.add_argument(
        "--message",
        type=str,
        help="Pipeline message JSON (for testing, usually from env var)",
    )

    args = parser.parse_args()

    # Get message from args or environment
    message_json = args.message
    if not message_json:
        message_json = os.environ.get("PIPELINE_MESSAGE")
    if not message_json:
        message_json = os.environ.get("SERVICEBUS_MESSAGE")

    if not message_json:
        logger.error("No pipeline message provided. Set PIPELINE_MESSAGE env var or use --message")
        sys.exit(1)

    # Run pipeline
    exit_code = asyncio.run(run_pipeline(message_json, args.type))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Script to test LLM extraction with Korean README."""

import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.services.llm_service import LLMService

# Sample Korean README
KOREAN_README = """
# Azure 기반 AI 채팅봇 구축 워크샵

## 소개
이 워크샵에서는 Azure OpenAI와 Azure AI Search를 활용하여
지능형 채팅봇을 구축하는 방법을 배웁니다.

## 학습 목표
- Azure OpenAI 서비스 설정 및 활용
- RAG(Retrieval-Augmented Generation) 패턴 이해
- Azure AI Search로 벡터 검색 구현
- Python과 LangChain을 사용한 채팅봇 개발

## 사전 요구사항
- Azure 구독
- Python 3.9 이상
- Visual Studio Code
- 기본적인 Python 프로그래밍 지식

## 워크샵 모듈
1. Azure OpenAI 리소스 만들기
2. 문서 임베딩 생성하기
3. Azure AI Search 인덱스 설정
4. RAG 파이프라인 구현
5. Streamlit으로 채팅 UI 만들기

## 소요 시간
약 3시간
"""


async def test_korean_extraction():
    """Test extraction from Korean README."""
    settings = get_settings()

    print("=" * 60)
    print("Korean README Extraction Test")
    print("=" * 60)

    if not settings.azure_openai_api_key:
        print("\n❌ Azure OpenAI is not configured.")
        return False

    print("\n📄 Korean README (excerpt):")
    print("-" * 40)
    print(KOREAN_README[:300] + "...")

    try:
        service = LLMService()
        print("\n🔄 Extracting metadata from Korean README...")

        result = await service.extract_metadata(
            readme_content=KOREAN_README,
            repo_description="Azure 기반 AI 채팅봇 구축 워크샵",
            repo_topics=["azure", "openai", "chatbot", "rag"],
            repo_language="Python",
            repo_stars=50,
        )

        print("\n✅ Extraction successful!")
        print("=" * 60)

        print("\n📝 Title (English):")
        print(f"   {result.title}")

        print("\n📝 Title (Korean):")
        print(f"   {result.title_kr}")

        print("\n📝 Description (English):")
        print(f"   {result.description}")

        print("\n📝 Description (Korean):")
        print(f"   {result.description_kr}")

        print("\n📦 Content Type:", result.content_type)
        print("📊 Level:", result.level)
        print("⏱️  Duration:", result.duration_minutes, "minutes")
        print("🏷️  Categories:", result.categories)
        print("🔧 Technologies:", result.technologies)

        # Validate bilingual output
        print("\n" + "=" * 60)
        print("Validation:")
        print("-" * 40)

        # Check if English fields are actually in English
        is_title_english = all(ord(c) < 128 or c in '.,!?()-:;"\'' for c in result.title if c.isalpha())
        is_desc_english = result.description and any(c.isascii() and c.isalpha() for c in result.description[:50])

        # Check if Korean fields contain Korean
        has_korean_title = result.title_kr and any('\uac00' <= c <= '\ud7a3' for c in result.title_kr)
        has_korean_desc = result.description_kr and any('\uac00' <= c <= '\ud7a3' for c in result.description_kr)

        print(f"✓ title is in English: {'✅' if is_title_english else '❌'}")
        print(f"✓ title_kr has Korean: {'✅' if has_korean_title else '❌'}")
        print(f"✓ description is in English: {'✅' if is_desc_english else '❌'}")
        print(f"✓ description_kr has Korean: {'✅' if has_korean_desc else '❌'}")

        all_valid = is_title_english and has_korean_title and is_desc_english and has_korean_desc
        print(f"\n{'✅ All bilingual fields are correct!' if all_valid else '⚠️ Some fields may need review'}")

        return all_valid

    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_korean_extraction())
    sys.exit(0 if success else 1)

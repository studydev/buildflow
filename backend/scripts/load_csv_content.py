"""
CSV 데이터를 백엔드 mock 데이터로 로드하는 스크립트.
extracted_data copy.csv 파일의 LAB 콘텐츠를 Content 형식으로 변환합니다.
"""

import csv
import json
import uuid
from datetime import datetime
from pathlib import Path


def parse_categories(categories_str: str) -> list[str]:
    """세미콜론으로 구분된 카테고리를 리스트로 변환."""
    if not categories_str:
        return []
    return [cat.strip() for cat in categories_str.split(";") if cat.strip()]


def get_icon_for_title(title: str, categories: list[str]) -> str:
    """타이틀과 카테고리 기반으로 적절한 아이콘 반환."""
    title_lower = title.lower()
    
    # LAB 번호 기반 아이콘
    if "lab5" in title_lower:
        if "copilot" in title_lower:
            return "🤖"
        elif "ai search" in title_lower or "rag" in title_lower:
            return "🔍"
        elif "agent" in title_lower:
            return "🤝"
        elif "mcp" in title_lower or "functions" in title_lower:
            return "⚡"
        elif "postgresql" in title_lower or "sql" in title_lower:
            return "🗄️"
        elif "security" in title_lower or "red team" in title_lower:
            return "🛡️"
        elif "kubernetes" in title_lower or "aks" in title_lower:
            return "☸️"
        elif "healthcare" in title_lower:
            return "🏥"
        elif "pizza" in title_lower:
            return "🍕"
        elif "cosmos" in title_lower:
            return "🌐"
        elif "databricks" in title_lower:
            return "📊"
        elif "fabric" in title_lower:
            return "🧵"
        elif "migrate" in title_lower or "migration" in title_lower:
            return "🚀"
        elif "arc" in title_lower:
            return "🔗"
        elif "vmware" in title_lower or "avs" in title_lower:
            return "🖥️"
        elif "sentinel" in title_lower:
            return "🔐"
        elif "defender" in title_lower:
            return "🛡️"
        elif "purview" in title_lower:
            return "📋"
        elif "intune" in title_lower or "entra" in title_lower:
            return "🔑"
        elif "geospatial" in title_lower:
            return "🗺️"
    
    # 카테고리 기반 아이콘
    if "AI" in categories:
        return "🤖"
    elif "Security" in categories:
        return "🛡️"
    elif "Data" in categories:
        return "📊"
    elif "DevOps" in categories:
        return "🔧"
    elif "Healthcare" in categories:
        return "🏥"
    elif "Kubernetes" in categories:
        return "☸️"
    elif "Migration" in categories:
        return "🚀"
    
    return "🔬"  # 기본 LAB 아이콘


def get_level_from_content(description: str, technologies: str) -> str:
    """콘텐츠 설명과 기술 스택 기반으로 난이도 추정."""
    desc_lower = description.lower() if description else ""
    tech_lower = technologies.lower() if technologies else ""
    
    # 고급 키워드
    advanced_keywords = ["advanced", "complex", "multi-agent", "orchestration", "architecture"]
    if any(kw in desc_lower for kw in advanced_keywords):
        return "advanced"
    
    # 초급 키워드
    beginner_keywords = ["beginner", "introduction", "basic", "getting started", "first"]
    if any(kw in desc_lower for kw in beginner_keywords):
        return "beginner"
    
    # 기술 스택 수 기반
    tech_count = len(technologies.split(";")) if technologies else 0
    if tech_count > 8:
        return "advanced"
    elif tech_count > 4:
        return "intermediate"
    
    return "intermediate"


def csv_to_content_list(csv_path: str) -> list[dict]:
    """CSV 파일을 Content 형식의 딕셔너리 리스트로 변환."""
    contents = []
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # 기본 정보 추출
            title = row.get("Title", "")
            title_kr = row.get("Title_kr", "")
            url = row.get("URL", "")
            categories_str = row.get("Categories", "")
            description = row.get("Session_Description", "")
            description_kr = row.get("Session_Description_kr", "")
            technologies = row.get("Technologies_Used", "")
            
            # 빈 행 스킵
            if not title or not url:
                continue
            
            categories = parse_categories(categories_str)
            icon = get_icon_for_title(title_kr or title, categories)
            level = get_level_from_content(description, technologies)
            
            # Content 형식으로 변환
            content = {
                "id": str(uuid.uuid4()),
                "contributor_id": "system",
                "title": title_kr or title,  # 한글 제목 우선
                "description": description_kr or description,  # 한글 설명 우선
                "content_type": "lab",
                "status": "published",
                "source_url": url,
                "source_type": "github",
                "categories": categories,
                "level": level,
                "duration_minutes": 90,  # 기본 LAB 시간
                "thumbnail_url": None,
                "icon": icon,
                "view_count": 0,
                "bookmark_count": 0,
                "analysis_status": "completed",
                "analysis_result": {
                    "title": title,
                    "title_kr": title_kr,
                    "description": description,
                    "description_kr": description_kr,
                    "categories": categories,
                    "technologies": parse_categories(technologies),
                    "learning_objectives": parse_categories(row.get("Learning_Objectives", "")),
                    "lab_modules": row.get("Lab_Modules", ""),
                    "topic": row.get("Topic", ""),
                },
                "published_at": datetime.utcnow().isoformat(),
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
            
            contents.append(content)
    
    return contents


def generate_python_code(contents: list[dict]) -> str:
    """Content 리스트를 Python 코드로 변환."""
    code_lines = []
    
    for i, content in enumerate(contents):
        code_lines.append(f"""
            Content(
                id="{content['id']}",
                contributor_id="system",
                title="{content['title'].replace('"', '\\"')}",
                description="{content['description'][:200].replace('"', '\\"').replace('\n', ' ')}...",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="{content['source_url']}",
                source_type="github",
                categories={content['categories']},
                level="{content['level']}",
                duration_minutes=90,
                icon="{content['icon']}",
                view_count=0,
                bookmark_count=0,
            ),""")
    
    return "\n".join(code_lines)


if __name__ == "__main__":
    # CSV 파일 경로
    csv_path = Path(__file__).parent.parent.parent / "src" / "assets" / "extracted_data copy.csv"
    
    if not csv_path.exists():
        print(f"CSV 파일을 찾을 수 없습니다: {csv_path}")
        exit(1)
    
    # CSV 데이터 로드
    contents = csv_to_content_list(str(csv_path))
    
    print(f"총 {len(contents)}개의 콘텐츠를 로드했습니다.")
    
    # JSON 형식으로 저장 (디버깅용)
    output_path = Path(__file__).parent / "content_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(contents, f, ensure_ascii=False, indent=2)
    
    print(f"JSON 데이터 저장됨: {output_path}")
    
    # Python 코드 생성
    python_code = generate_python_code(contents)
    code_path = Path(__file__).parent / "content_code.py"
    with open(code_path, "w", encoding="utf-8") as f:
        f.write(python_code)
    
    print(f"Python 코드 저장됨: {code_path}")

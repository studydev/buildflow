# Data Model: Azure AI Search 하이브리드 검색

**Feature**: 002-ai-search-hybrid  
**Date**: 2026-01-26  
**Status**: Complete

## 1. Search Index Schema

Azure AI Search 인덱스 `buildflow-content`의 스키마 정의입니다.

### 1.1 Primary Fields

| Field | Type | Searchable | Filterable | Sortable | Facetable | Analyzer |
|-------|------|------------|------------|----------|-----------|----------|
| id | Edm.String (Key) | ❌ | ❌ | ❌ | ❌ | - |
| title | Edm.String | ✅ | ✅ | ✅ | ❌ | en.microsoft |
| title_kr | Edm.String | ✅ | ❌ | ❌ | ❌ | ko.microsoft |
| description | Edm.String | ✅ | ❌ | ❌ | ❌ | - |
| summary | Edm.String | ✅ | ❌ | ❌ | ❌ | - |

### 1.2 Collection Fields

| Field | Type | Searchable | Filterable | Facetable |
|-------|------|------------|------------|-----------|
| categories | Collection(Edm.String) | ✅ | ✅ | ✅ |
| technologies | Collection(Edm.String) | ✅ | ✅ | ✅ |

### 1.3 Filter/Sort Fields

| Field | Type | Filterable | Sortable | Facetable |
|-------|------|------------|----------|-----------|
| difficulty_level | Edm.String | ✅ | ❌ | ✅ |
| visibility | Edm.String | ✅ | ❌ | ❌ |
| content_type | Edm.String | ✅ | ❌ | ✅ |
| popularity_score | Edm.Double | ✅ | ✅ | ❌ |
| stars | Edm.Int32 | ✅ | ✅ | ❌ |
| last_commit_date | Edm.DateTimeOffset | ✅ | ✅ | ❌ |
| created_at | Edm.DateTimeOffset | ✅ | ✅ | ❌ |

### 1.4 Vector Field

| Field | Type | Dimensions | Algorithm | Metric |
|-------|------|------------|-----------|--------|
| content_vector | Collection(Edm.Single) | 1536 | HNSW | cosine |

**Vector Search Configuration**:
```json
{
  "algorithms": [{
    "name": "hnsw-algorithm",
    "kind": "hnsw",
    "hnswParameters": {
      "metric": "cosine",
      "m": 4,
      "efConstruction": 400,
      "efSearch": 500
    }
  }],
  "profiles": [{
    "name": "default-profile",
    "algorithm": "hnsw-algorithm"
  }]
}
```

## 2. Entity Mapping

### 2.1 CosmosDB Content → Search Document

| CosmosDB Field | Search Field | Transform |
|----------------|--------------|-----------|
| id | id | UUID → String |
| title | title | - |
| title_kr | title_kr | - |
| description | description | - |
| summary_short / summary_long | summary | Prefer short |
| categories | categories | - |
| technologies | technologies | - |
| level | difficulty_level | - |
| status | visibility | published → public, else internal |
| content_type | content_type | Enum → String |
| popularity_score | popularity_score | Default 0.0 |
| stars | stars | Default 0 |
| last_commit_date | last_commit_date | ISO8601 |
| created_at | created_at | ISO8601 |
| (generated) | content_vector | 1536-dim float array |

### 2.2 Embedding Generation

**Input Text Formula**:
```
{title} {title_kr} {description} {description_kr} {technologies.join(' ')}
```

**Model**: text-embedding-3-small (Azure OpenAI)  
**Output**: 1536-dimensional float vector

## 3. Search Query Types

### 3.1 Keyword Search

```json
{
  "search": "<query>",
  "searchMode": "any",
  "queryType": "full",
  "select": "id,title,description,summary,categories,technologies,difficulty_level,popularity_score,stars",
  "filter": "<OData filter>",
  "top": 20,
  "skip": 0,
  "count": true,
  "facets": ["categories,count:20", "technologies,count:20", "difficulty_level"]
}
```

### 3.2 Vector Search

```json
{
  "search": "*",
  "vectorQueries": [{
    "kind": "vector",
    "vector": [0.123, ...],
    "fields": "content_vector",
    "k": 20
  }],
  "select": "...",
  "filter": "<OData filter>",
  "top": 20,
  "count": true
}
```

### 3.3 Hybrid Search (Keyword + Vector)

```json
{
  "search": "<query>",
  "searchMode": "any",
  "queryType": "full",
  "vectorQueries": [{
    "kind": "vector",
    "vector": [0.123, ...],
    "fields": "content_vector",
    "k": 20
  }],
  "select": "...",
  "filter": "<OData filter>",
  "top": 20,
  "count": true
}
```

## 4. Filter Expressions (OData)

### 4.1 Category Filter
```
categories/any(c: c eq 'AI')
```

### 4.2 Multiple Categories (OR)
```
(categories/any(c: c eq 'AI') or categories/any(c: c eq 'Azure'))
```

### 4.3 Technology Filter
```
technologies/any(t: t eq 'Python')
```

### 4.4 Difficulty Filter
```
difficulty_level eq 'beginner'
```

### 4.5 Minimum Stars
```
stars ge 100
```

### 4.6 Visibility (Authenticated vs Public)
```
visibility eq 'public'  // Unauthenticated users only
```

### 4.7 Combined Filter
```
(categories/any(c: c eq 'AI')) and difficulty_level eq 'beginner' and stars ge 50
```

## 5. Scoring Profile

### 5.1 popularity-boost (Default)

```json
{
  "name": "popularity-boost",
  "functions": [
    {
      "type": "magnitude",
      "fieldName": "popularity_score",
      "boost": 2.0,
      "interpolation": "linear",
      "magnitude": {
        "boostingRangeStart": 0,
        "boostingRangeEnd": 1
      }
    },
    {
      "type": "freshness",
      "fieldName": "last_commit_date",
      "boost": 1.5,
      "interpolation": "linear",
      "freshness": {
        "boostingDuration": "P180D"
      }
    }
  ]
}
```

**Effect**:
- 인기도 점수가 높을수록 상위 노출
- 최근 커밋된 콘텐츠 우선

## 6. Facet Response Format

```json
{
  "@search.facets": {
    "categories": [
      { "value": "AI", "count": 15 },
      { "value": "Azure", "count": 12 },
      { "value": "Cloud", "count": 8 }
    ],
    "technologies": [
      { "value": "Python", "count": 20 },
      { "value": "Azure OpenAI", "count": 10 }
    ],
    "difficulty_level": [
      { "value": "beginner", "count": 25 },
      { "value": "intermediate", "count": 15 },
      { "value": "advanced", "count": 5 }
    ]
  }
}
```

## 7. State Transitions

### 7.1 Content Lifecycle → Index State

| Content Status | Index Action |
|----------------|--------------|
| draft | Not indexed |
| published | Upsert document |
| archived | Delete document |
| (updated) | Re-upsert with new embedding |
| (deleted) | Delete document |

### 7.2 Indexing Flow

```
[Content Created/Updated]
        ↓
[Generate Embedding via LLM Service]
        ↓
[Build Search Document]
        ↓
[Upsert to Azure AI Search]
        ↓
[Searchable within seconds]
```

## 8. Validation Rules

| Field | Validation |
|-------|------------|
| id | Valid UUID string |
| title | Required, max 200 chars |
| categories | Min 1 item, max 10 items |
| technologies | Max 20 items |
| stars | Non-negative integer |
| popularity_score | 0.0 to 1.0 range |
| content_vector | Exactly 1536 floats |

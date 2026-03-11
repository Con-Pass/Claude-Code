# ConPass AI Assistant — Overall Architecture

This document describes the current design and implementation of the ConPass AI Assistant system architecture, including the Query Pipeline flow and main components.

## System Architecture Diagram

```mermaid
flowchart TB
    subgraph Client [Client Layer]
        User[User]
    end

    subgraph Backend [conpass-agent-backend]
        ChatAPI[Chat API POST /api/v1/chat]
        Engine[Chat Engine]
        Agent[AgentWorkflow]
        Tools[Tools]
        LLM[LLM]
    end

    subgraph ToolsDetail [Tools]
        SemanticSearch[semantic_search]
        MetadataSearch[metadata_search]
        ReadContracts[read_contracts_tool]
        GetFileContent[get_file_content_tool]
        DocumentDiffing[document_diffing_tool]
        CsvGeneration[csv_generation_tool]
        RiskAnalysis[risk_analysis_tool]
        WebSearch[web_search_tool]
    end

    subgraph External [External Services]
        Qdrant[Qdrant Vector DB]
        Redis[Redis]
        ConPassAPI[ConPass API]
    end

    subgraph Ingestion [Ingestion Pipeline]
        MySQL[(MySQL)]
        PubSub[Pub/Sub]
        CloudRun[generate-embeddings Cloud Run]
        QdrantIngest[Qdrant]
        RedisIngest[Redis]
    end

    User --> ChatAPI
    ChatAPI --> Engine
    Engine --> Agent
    Agent --> Tools
    Tools --> SemanticSearch
    Tools --> MetadataSearch
    Tools --> ReadContracts
    Tools --> GetFileContent
    Tools --> DocumentDiffing
    Tools --> CsvGeneration
    SemanticSearch --> Qdrant
    MetadataSearch --> Qdrant
    MetadataSearch --> Redis
    ReadContracts --> Redis
    ReadContracts --> ConPassAPI
    Tools --> LLM
    LLM --> Agent
    Agent --> User

    MySQL --> PubSub
    PubSub --> CloudRun
    CloudRun --> QdrantIngest
    CloudRun --> RedisIngest
```

## Query Pipeline Processing Flow

```mermaid
sequenceDiagram
    participant User
    participant ChatAPI
    participant Engine
    participant Agent
    participant Tools
    participant Qdrant
    participant ConPassAPI
    participant LLM

    User->>ChatAPI: POST /api/v1/chat (message, chat_id)
    ChatAPI->>ChatAPI: JWT validation, extract user_id
    ChatAPI->>ChatAPI: Load chat history if chat_id provided
    ChatAPI->>ChatAPI: Get allowed directory_ids from ConPass API
    ChatAPI->>Engine: get_chat_engine(directory_ids)
    ChatAPI->>Engine: astream_chat(message, chat_history)

    Engine->>Agent: AgentWorkflow.run(user_msg, chat_history)
    Agent->>Agent: LLM decides which tool(s) to call

    alt Content discovery
        Agent->>Tools: semantic_search(query)
        Tools->>Qdrant: Hybrid search (dense + sparse)
        Qdrant-->>Tools: Points with excerpts
        Tools-->>Agent: Sources with contract_id, excerpt, url
    else Metadata filter
        Agent->>Tools: metadata_search(query, filter_used)
        Tools->>Qdrant: Scroll with filter
        Qdrant-->>Tools: Contract metadata
        Tools-->>Agent: Contract list
    else Specific contract
        Agent->>Tools: read_contracts_tool(contract_ids)
        Tools->>ConPassAPI: get_contract_body_text
        ConPassAPI-->>Tools: Full contract text
        Tools-->>Agent: contract_body, url
    else Document diff or CSV
        Agent->>Tools: get_file_content_tool and/or read_contracts_tool
        Tools-->>Agent: File/contract content
        Agent->>Tools: document_diffing_tool(data, instruction) and/or csv_generation_tool(data, instruction)
        Tools-->>Agent: diff_content or csv_content
    end

    Agent->>LLM: Generate answer with tool outputs as context
    LLM-->>Agent: Response text
    Agent-->>Engine: Stream tokens + sources
    Engine-->>ChatAPI: StreamingAgentChatResponse
    ChatAPI-->>User: SSE stream (Vercel format)
```

## Main Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Embedding Model** | OpenAI (e.g. text-embedding-3-small) | Dense vector generation for semantic similarity |
| **Vector DB** | Qdrant | Stores dense + sparse vectors; hybrid search with RRF fusion |
| **Sparse Model** | FastEmbed Qdrant/bm25 | BM25-style keyword matching for hybrid search |
| **LLM** | OpenAI (OpenAIResponses) or Azure OpenAI | Answer generation with tool-calling |
| **OCR** | Tesseract + Google Document AI | Text extraction for File Upload (PDFs/images) and standalone OCR API; not used by Risk Analysis (which uses ConPass API text) |
| **Metadata DB** | Redis | Document metadata + hash for deduplication; contract text fetched from ConPass API |
| **ConPass API** | HTTP | Contract body text, user directories, metadata |

## Execution Mode

| Pipeline | Mode | Trigger | Job Management |
|----------|------|---------|----------------|
| **Query / Chat** | Real-time | HTTP POST | No queue; synchronous request-response with streaming |
| **Ingestion** | Batch | Pub/Sub push | Pub/Sub delivers batches; Cloud Run processes one batch per message |

## Service Decomposition

| Service | Type | Responsibility |
|---------|------|----------------|
| **conpass-agent-backend** | FastAPI | Chat API, agent engine, tool orchestration, streaming response |
| **generate-embeddings** | Cloud Run | Contract ingestion: chunk, embed, store in Qdrant + Redis |

## Key Files

- [app/main.py](../../app/main.py) — FastAPI application entry
- [app/api/v1/chat.py](../../app/api/v1/chat.py) — Chat endpoint, streaming
- [app/services/chatbot/engine.py](../../app/services/chatbot/engine.py) — Chat engine, tool wiring
- [cloud/cloud_run/generate_embeddings/main.py](../../cloud/cloud_run/generate_embeddings/main.py) — Ingestion service entry, Pub/Sub handler

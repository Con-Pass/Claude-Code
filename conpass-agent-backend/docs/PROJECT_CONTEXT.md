# ConPass AI Agent - Project Context

## Overview
ConPass AI Agent is a FastAPI-based backend service providing an AI-powered chat system with document retrieval capabilities using RAG (Retrieval-Augmented Generation) architecture.

## Tech Stack
- **Framework**: FastAPI + Python 3.12
- **Package Manager**: UV (replaces pip/virtualenv)
- **AI/ML**: LlamaIndex for RAG implementation
- **Vector Database**: Qdrant for document embeddings
- **LLM Provider**: Google Gemini/Vertex AI
- **Embeddings**: Google GenAI embeddings

## Architecture

### Core Components
1. **Chat Engine** - AgentRunner-based system with streaming support
2. **Vector Search** - Qdrant integration for document retrieval
3. **Document Ingestion** - Pipeline for processing and indexing files
4. **API Layer** - RESTful endpoints for chat and file operations

### Directory Structure
```
app/
├── api/v1/          # API endpoints (chat, upload, config)
├── core/            # Configuration and settings
├── schemas/         # Pydantic models
└── services/
    └── chatbot/     # Core chat functionality
        ├── tools/   # Query engine tools
        ├── engine.py    # Chat engine setup
        ├── index.py     # Vector index management
        └── vectordb.py  # Qdrant integration

ingestion/           # Document processing pipeline
```

## Key Features
- **Streaming Chat**: Real-time responses via Vercel-style streaming
- **Document Context**: Chat with uploaded files and references
- **Source Citations**: Retrieval with metadata and URLs
- **Document Filtering**: Query specific documents by ID
- **Multi-format Support**: PDF, DOCX, TXT, etc.
- **Agent Architecture**: Extensible tool-based system

## API Endpoints
- `POST /api/v1/chat` - Streaming chat with document context
- `POST /api/v1/chat/request` - Non-streaming chat
- `POST /api/v1/upload` - File upload for indexing
- `GET/POST /api/v1/chat/config` - Chat configuration

## Configuration
Environment variables in `.env`:
- **Qdrant**: `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`
- **LLM**: `MODEL_PROVIDER`, `MODEL`, `OPENAI_API_KEY`
- **Embeddings**: `EMBEDDING_MODEL`, `EMBEDDING_DIM`
- **RAG**: `TOP_K`, `CHUNK_SIZE`, `CHUNK_OVERLAP`
- **Prompts**: `SYSTEM_PROMPT`, `NEXT_QUESTION_PROMPT`

## Development Workflow
1. **Setup**: `uv sync` + `uv run pre-commit install`
2. **Run Dev**: `uv run fastapi dev` (port 8000)
3. **Run Prod**: `uv run fastapi run --workers 4`
4. **Index Data**: `uv run generate` (processes files in `data/`)

## Data Flow
1. Documents uploaded → Ingestion pipeline → Chunked & embedded → Qdrant
2. User query → Chat engine → Vector search → LLM with context → Response
3. Streaming events handled via EventCallbackHandler

## Key Classes
- `ChatData` - Message handling with annotations
- `IndexConfig` - Vector index configuration
- `Settings` - Environment-based configuration
- `AgentRunner` - Core chat engine from LlamaIndex

## Commit Convention
Types: `Feat`, `Fix`, `Refactor`, `Merge`, `Enhance`
Format: `Type: [CAA-123/]Description with uppercase start`
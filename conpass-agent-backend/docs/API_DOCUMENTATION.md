# ConPass AI Agent API Documentation

## Overview

The ConPass AI Agent API provides powerful AI-powered chat capabilities with document retrieval using RAG (Retrieval-Augmented Generation) architecture.

## API Endpoints

### Base URL

- **Development**: `http://localhost:8000`
- **Test**: `https://conpass-agent-backend-test.run.app`
- **Staging**: `https://conpass-agent-backend-staging.run.app`
- **Production**: `https://conpass-agent-backend-prod.run.app`

### Interactive Documentation

- **Swagger UI**: `/docs` - Interactive API documentation with "Try it out" functionality
- **ReDoc**: `/redoc` - Alternative documentation with better readability
- **OpenAPI Schema**: `/openapi.json` - Raw OpenAPI 3.0 schema

---

## Endpoints

### 🏥 Health & Status

#### `GET /`

Root endpoint with API information and links to documentation.

**Response:**

```json
{
  "message": "ConPass AI Agent API",
  "version": "0.1.0",
  "docs": "/docs",
  "redoc": "/redoc",
  "health": "/health"
}
```

#### `GET /health`

Health check endpoint for monitoring and load balancers.

**Response:**

```json
{
  "status": "healthy",
  "environment": "development",
  "version": "0.1.0",
  "service": "conpass-agent-backend"
}
```

---

### 💬 Chat Operations

#### `POST /api/v1/chat`

**Streaming chat endpoint** - Send messages and receive real-time streaming responses.

**Request Body:**

```json
{
  "messages": [
    {
      "role": "user",
      "content": "What is the main topic of the document?"
    }
  ],
  "data": {
    "documentIds": ["doc-123", "doc-456"]
  }
}
```

**Response:**

- Server-Sent Events (SSE) stream
- Real-time token-by-token response
- Source citations with metadata
- Compatible with Vercel AI SDK

**Use Cases:**

- Interactive chat applications
- Real-time user experience
- Progressive response rendering

---

#### `POST /api/v1/chat/request`

**Non-streaming chat endpoint** - Get complete responses in a single request.

**Request Body:**

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Summarize the key points from the document"
    }
  ]
}
```

**Response:**

```json
{
  "result": {
    "role": "assistant",
    "content": "Here are the key points from the document..."
  },
  "nodes": [
    {
      "id": "node-1",
      "text": "Source text excerpt...",
      "score": 0.95,
      "metadata": {
        "file_name": "document.pdf",
        "page": 1
      }
    }
  ]
}
```

**Use Cases:**

- Simple integrations
- Batch processing
- When streaming is not required

---

### ⚙️ Configuration

#### `GET /api/v1/chat/config`

Get chat configuration including conversation starters.

**Response:**

```json
{
  "starter_questions": [
    "What is the main topic of this document?",
    "Can you summarize the key points?",
    "What are the important dates mentioned?"
  ]
}
```

**Use Cases:**

- Initialize chat UI
- Display suggested questions
- Provide user guidance

---

### 📤 File Upload

#### `POST /api/v1/chat/upload`

Upload files for document indexing and retrieval.

**Request Body:**

```json
{
  "name": "document.pdf",
  "base64": "JVBERi0xLjQKJeLjz9MKMSAwIG9iago8PC...",
  "params": {
    "metadata": {
      "category": "research"
    }
  }
}
```

**Response:**

```json
{
  "id": "doc-abc123",
  "name": "document.pdf",
  "size": 1024000,
  "url": "https://storage.example.com/doc-abc123"
}
```

**Supported Formats:**

- PDF (`.pdf`)
- Word Documents (`.docx`)
- Text Files (`.txt`)
- Markdown (`.md`)

---

## Request/Response Examples

### Streaming Chat Example (cURL)

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "What is RAG?"
      }
    ]
  }' \
  --no-buffer
```

### Non-Streaming Chat Example (cURL)

```bash
curl -X POST http://localhost:8000/api/v1/chat/request \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "Explain the concept of vector databases"
      }
    ]
  }'
```

### Python Example

```python
import requests

# Streaming chat
response = requests.post(
    "http://localhost:8000/api/v1/chat",
    json={
        "messages": [
            {"role": "user", "content": "Hello!"}
        ]
    },
    stream=True
)

for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))

# Non-streaming chat
response = requests.post(
    "http://localhost:8000/api/v1/chat/request",
    json={
        "messages": [
            {"role": "user", "content": "Summarize this document"}
        ]
    }
)

result = response.json()
print(result["result"]["content"])
```

### JavaScript/TypeScript Example

```typescript
// Using fetch API for streaming
const response = await fetch("http://localhost:8000/api/v1/chat", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    messages: [{ role: "user", content: "Hello!" }],
  }),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const chunk = decoder.decode(value);
  console.log(chunk);
}

// Using Vercel AI SDK
import { useChat } from "ai/react";

export default function Chat() {
  const { messages, input, handleInputChange, handleSubmit } = useChat({
    api: "http://localhost:8000/api/v1/chat",
  });

  return (
    <div>
      {messages.map((m) => (
        <div key={m.id}>
          {m.role}: {m.content}
        </div>
      ))}
      <form onSubmit={handleSubmit}>
        <input value={input} onChange={handleInputChange} />
      </form>
    </div>
  );
}
```

---

## Authentication

Currently, the API does not require authentication for development and test environments. For production deployments, implement appropriate authentication mechanisms.

---

## Rate Limiting

Rate limiting is not currently enforced but may be added in future versions for production environments.

---

## Error Handling

### Error Response Format

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common HTTP Status Codes

- `200 OK` - Request successful
- `400 Bad Request` - Invalid request parameters
- `404 Not Found` - Endpoint not found
- `500 Internal Server Error` - Server-side error

---

## Data Models

### Message

```typescript
{
  role: "user" | "assistant" | "system",
  content: string
}
```

### ChatData

```typescript
{
  messages: Message[],
  data?: {
    documentIds?: string[],
    [key: string]: any
  }
}
```

### Result

```typescript
{
  result: Message,
  nodes: SourceNode[]
}
```

### SourceNode

```typescript
{
  id: string,
  text: string,
  score: number,
  metadata: {
    file_name?: string,
    page?: number,
    url?: string,
    [key: string]: any
  }
}
```

---

## Support & Contact

For questions, issues, or feature requests:

- **Email**: support@conpass.ai
- **Documentation**: `/docs`
- **GitHub**: [Repository URL]

---

## Version History

### v0.1.0 (Current)

- Initial release
- Streaming and non-streaming chat endpoints
- Document upload and indexing
- Configuration management
- Health check endpoints

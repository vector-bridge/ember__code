# VectorBridge Integration

VectorBridge is the semantic code intelligence engine behind Ember Code. While other tools operate on raw text (grep for patterns, read for file contents), VectorBridge gives agents **pre-processed understanding** of the entire codebase — searchable by meaning, not just keywords.

**VectorBridge is included free with every Ember Code account.** No separate subscription, no extra API keys. When you sign up at [ignite-ember.sh](https://ignite-ember.sh), you get both the AI coding assistant and the code intelligence platform.

## What VectorBridge Does

VectorBridge is a semantic search platform built on Weaviate (vector DB), PostgreSQL (metadata), and Agno readers (intelligent chunking). Ember Code uses it as the backend for code intelligence:

```
Your Codebase
    │
    ▼
┌──────────────────────────────────────────┐
│  Ember Code Analysis Pipeline            │
│                                          │
│  1. Read every file                      │
│  2. Chunk semantically (Agno readers)    │
│  3. Generate summaries per category      │
│     (code, security, testability, ...)   │
│  4. Build hierarchy bottom-up            │
│     function → class → file → module     │
│  5. Index everything in VectorBridge     │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│  VectorBridge                            │
│                                          │
│  Weaviate (vectors + semantic search)    │
│  PostgreSQL (references + metadata)      │
│  Redis (cache + rate limiting)           │
│                                          │
│  API: /v1/vector-query/search/run        │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│  Agents query VectorBridge               │
│                                          │
│  "How does authentication work?"         │
│  → Returns auth module summary with      │
│    flow description, security analysis,  │
│    references to all related files       │
└──────────────────────────────────────────┘
```

---

## Two Layers

It's important to understand the separation:

**VectorBridge** (the platform) provides:
- Semantic chunking via Agno readers (semantic, fixed-size, document-aware, agentic)
- Vector storage and similarity search (Weaviate)
- Hierarchical document structure (parent/child, source/derived)
- Custom references between documents with tags
- Access control, multi-tenancy, per-repository scoping
- REST API for ingestion, search, and management

**Ember Code** (the intelligence layer) provides:
- The analysis pipeline that generates multi-category summaries
- Bottom-up hierarchical summary generation (function → class → file → module → project)
- Category-specific analysis (security, testability, architecture, performance, maintainability)
- The `VectorBridge` tool that agents use to query all of this
- Automatic re-indexing on code changes

Together, they give agents something no other coding assistant has: **pre-computed, semantic understanding of the entire codebase, searchable by meaning.**

---

## Multi-Category Analysis

When Ember Code indexes a codebase, it doesn't just store raw code. For each entity, it generates summaries across **six categories**:

| Category | What It Captures | Example Insight |
|---|---|---|
| **Code** | Purpose, behavior, algorithm, data flow | "JWT-based auth middleware that validates tokens from the Authorization header" |
| **Security** | Vulnerabilities, auth patterns, input validation, secrets | "Refresh token rotation not implemented — stolen tokens have unlimited lifetime" |
| **Testability** | Coverage, mockability, edge cases, testing patterns | "Complex branching in process_payment() — 4 untested edge cases around currency conversion" |
| **Architecture** | Dependencies, coupling, design patterns, boundaries | "Tight coupling between OrderService and PaymentGateway — no interface abstraction" |
| **Performance** | Bottlenecks, complexity, resource usage | "N+1 query in get_user_orders() — loads related items in a loop instead of a join" |
| **Maintainability** | Code quality, readability, tech debt | "500-line function with 12 parameters — candidate for decomposition" |

Each category is a separate summary stored as a tagged document in VectorBridge. This means agents can search within a specific category:

```
search("authentication", categories=["security"])
→ Returns only security-related findings about auth code

search("slow endpoints", categories=["performance"])
→ Returns performance bottleneck analysis for API endpoints
```

---

## Hierarchical Summaries

Summaries are built **bottom-up**. Children are analyzed first, then their summaries feed into the parent's analysis. This is the key differentiator.

```
┌─────────────────────────────────────────────────────────────┐
│  Project: my-api                                            │
│  Summary: "FastAPI REST API with JWT auth, PostgreSQL,      │
│           and Redis caching. 47 endpoints across 8 modules" │
│                                                             │
│  Security: "3 critical findings: SQL injection in search,   │
│            missing rate limiting on auth, exposed debug     │
│            endpoints in production config"                  │
│                                                             │
│  ┌───────────────────────────┐  ┌─────────────────────────┐ │
│  │  Module: src/auth/        │  │  Module: src/api/       │ │
│  │  Summary: "Authentication │  │  Summary: "REST API     │ │
│  │  module with JWT tokens,  │  │  routes for users,      │ │
│  │  session management, and  │  │  orders, and products.  │ │
│  │  OAuth2 providers"        │  │  Uses dependency        │ │
│  │                           │  │  injection for auth"    │ │
│  │  ┌─────────────────────┐  │  │                         │ │
│  │  │ File: middleware.py │  │  │  ...                    │ │
│  │  │ Summary: "Request   │  │  └─────────────────────────┘ │
│  │  │ auth middleware.    │  │                              │
│  │  │ Validates JWT from  │  │                              │
│  │  │ Authorization header│  │                              │
│  │  │                     │  │                              │
│  │  │ ┌─────────────────┐ │  │                              │
│  │  │ │ Class:          │ │  │                              │
│  │  │ │ AuthMiddleware  │ │  │                              │
│  │  │ │ ┌─────────────┐ │ │  │                              │
│  │  │ │ │ validate()  │ │ │  │                              │
│  │  │ │ │ refresh()   │ │ │  │                              │
│  │  │ │ └─────────────┘ │ │  │                              │
│  │  │ └─────────────────┘ │  │                              │
│  │  └─────────────────────┘  │                              │
│  └───────────────────────────┘                              │
└─────────────────────────────────────────────────────────────┘
```

**Why this matters:** When an agent asks about the auth module, VectorBridge doesn't return raw file contents — it returns the module-level summary that already distills knowledge from every function and class inside it. The agent gets multi-resolution understanding: zoom out for architecture, zoom in for implementation.

### How It's Stored

Each level of the hierarchy is a document in VectorBridge with parent-child relationships:

```
Document: src/auth/middleware.py
  ├── parent: src/auth/ (folder)
  ├── children: [] (files don't have children in FS)
  ├── chunks:
  │   ├── chunk[0]: AuthMiddleware class (semantic chunk)
  │   ├── chunk[1]: validate() method (semantic chunk)
  │   └── chunk[2]: refresh() method (semantic chunk)
  ├── derived_documents:
  │   ├── summary_code (code category summary)
  │   ├── summary_security (security category summary)
  │   ├── summary_testability (testability category summary)
  │   └── ...
  └── references:
      ├── → src/auth/jwt.py (imports from)
      ├── → src/api/deps.py (used by)
      └── → src/config/security.py (reads config from)
```

VectorBridge stores the hierarchy natively:
- **Parent/child** relationships via Weaviate references (folder → files)
- **Source/derived** relationships for summary documents (code file → its category summaries)
- **Custom references** with tags in PostgreSQL (cross-file dependencies, imports)
- **Ancestry tracking** via `parent_ids_hierarchy` (full path from root to entity)

---

## Search Capabilities

### Semantic Search

Query by meaning, not keywords. VectorBridge vectorizes all content and summaries using embedding models, then finds results by vector similarity.

```
Agent: search("how does payment processing handle refunds")

VectorBridge returns:
  1. src/payments/refund.py (score: 0.93)
     Code: "Refund processor that reverses charges via the
            payment gateway. Supports partial refunds, handles
            currency conversion, and creates audit records."

  2. src/payments/gateway.py (score: 0.88)
     Code: "Payment gateway adapter. The refund() method calls
            the provider's reversal API and handles idempotency
            via transaction IDs."
```

### Category-Filtered Search

Search within specific analysis categories:

```
Agent: search("authentication", categories=["security"])

Returns only security-focused findings:
  1. src/auth/middleware.py
     Security: "Token validation is solid but refresh token
               rotation is not implemented..."

  2. src/auth/jwt.py
     Security: "RS256 is appropriate. However, the 'none'
               algorithm is not explicitly rejected..."
```

### Entity Lookup

Get the full summary for a specific file, class, or function:

```
Agent: get_entity("src/auth/middleware.py")

Returns:
  Code: "JWT-based authentication middleware..."
  Security: "Refresh token rotation not implemented..."
  Testability: "Well-structured for testing — middleware is
               injected via dependency injection..."
  Architecture: "Central auth dependency — 32 files import
                from this module..."
  Performance: "JWT validation adds ~2ms per request..."
  References: [src/auth/jwt.py, src/api/deps.py, ...]
```

### Reference Traversal

Follow the dependency graph:

```
Agent: get_references("src/auth/middleware.py")

Returns:
  References to (this file depends on):
    → src/auth/jwt.py (token validation)
    → src/config/security.py (key configuration)

  Referenced by (other files depend on this):
    ← src/api/deps.py (dependency injection)
    ← src/api/routes/users.py (auth required)
    ← src/api/routes/orders.py (auth required)
    ... (28 more files)
```

### Similarity Search

Given a file, find similar ones (useful for finding duplicated logic):

```
Agent: find_similar("src/api/routes/users.py")

Returns:
  1. src/api/routes/orders.py (similarity: 0.91)
     — Same CRUD pattern, same auth middleware, same pagination
  2. src/api/routes/products.py (similarity: 0.87)
     — Similar structure but uses different validation
```

---

## The VectorBridge Tool

Agents access VectorBridge through the `VectorBridge` tool (see [Tools](TOOLS.md)):

```python
from ember_code.tools.vectorbridge import VectorBridgeTools

vb = VectorBridgeTools(
    api_url=config.vectorbridge.api_url,
    api_key=config.vectorbridge.api_key,
    project_id=config.project_id,
)
```

**Functions:**

| Function | Description |
|---|---|
| `search(query, categories?, limit?)` | Semantic search across summaries |
| `get_entity(path)` | Full summary for a specific entity |
| `get_children(path)` | Summaries of all children of an entity |
| `get_references(path)` | Entities that reference or are referenced by this entity |
| `get_category(path, category)` | Specific category summary (e.g., security analysis) |
| `find_similar(path, limit?)` | Find entities similar to this one |

### Which Agents Get VectorBridge

| Agent | Has VectorBridge | Why |
|---|---|---|
| Explorer | yes | Primary research tool for understanding code |
| Planner | yes | Needs architectural context to design plans |
| Editor | yes | Needs to understand surrounding code before editing |
| Reviewer | yes | Needs to assess impact across the codebase |
| Git | no | Only runs git commands, doesn't reason about code |
| Conversational | no | General Q&A, no code analysis needed |

---

## Indexing Pipeline

### When Indexing Happens

| Trigger | What Gets Indexed |
|---|---|
| First onboarding | Full codebase |
| `git push` (if configured) | Changed files |
| `/vectorbridge reindex` | Full codebase |
| `/vectorbridge reindex --changed` | Files changed since last index |
| Background (auto-refresh) | Changed files, periodic |

### Pipeline Steps

```
1. Discover files
   └── Walk project tree, respect .gitignore + config ignore patterns

2. Read & chunk (Agno readers)
   ├── Semantic chunking (default) — respects code boundaries
   ├── Section chunking — for files with [SECTION:*] markers
   └── Agentic chunking — AI-powered intelligent splitting

3. Generate category summaries (LLM)
   ├── For each entity (function, class, file, module):
   │   ├── Code summary
   │   ├── Security analysis
   │   ├── Testability assessment
   │   ├── Architecture analysis
   │   ├── Performance analysis
   │   └── Maintainability assessment
   │
   └── Bottom-up: children summarized first,
       then fed into parent summary generation

4. Extract references
   ├── Import/dependency analysis
   ├── Function call graph
   └── Type/class relationships

5. Index in VectorBridge
   ├── Documents → Weaviate (vectorized for semantic search)
   ├── Chunks → Weaviate (fine-grained search)
   ├── References → PostgreSQL (tagged, bidirectional)
   └── Metadata → PostgreSQL (line ranges, commit info)
```

### Chunking Strategies

VectorBridge supports multiple chunking strategies via Agno readers:

| Strategy | When Used | How It Works |
|---|---|---|
| **Semantic** (default) | Most code files | Respects semantic boundaries (functions, classes, blocks) with ~10% overlap between chunks |
| **Fixed-size** | Very large files | Fixed character/token limits per chunk |
| **Document-aware** | Structured files (markdown, notebooks) | Respects document structure (sections, cells) |
| **Agentic** | Complex files | AI-powered chunking that understands code context |
| **Section** | Files with `[SECTION:*]` tags | Custom markers define chunk boundaries |

---

## Graceful Degradation

If VectorBridge is unavailable (no account, offline, API error), Ember Code still works. The Orchestrator is aware of VectorBridge availability and adjusts:

| VectorBridge Status | Agent Behavior |
|---|---|
| **Available** | Agents use VectorBridge for semantic search, summaries, references |
| **Unavailable** | Agents fall back to Grep, Glob, Read for code exploration |
| **Partially indexed** | Agents use VectorBridge where available, fall back for unindexed files |

The experience degrades gracefully — agents are slower and less informed without VectorBridge, but they still function. The Orchestrator may add extra Explorer agents to compensate with broader file reads.

---

## Configuration

```yaml
# .ember/config.yaml

vectorbridge:
  enabled: true
  api_url: "https://api.vectorbridge.io"     # Ember Code hosted (included free)
  # api_key is inherited from EMBER_API_KEY — no separate key needed

  categories:                                  # Categories to generate
    - code
    - security
    - testability
    - architecture
    - performance
    - maintainability

  indexing:
    auto_refresh: true                         # Re-index on significant changes
    refresh_on_git_push: true                  # Trigger after push
    ignore_patterns:                           # Skip these files/dirs
      - "node_modules/"
      - ".git/"
      - "__pycache__/"
      - "*.pyc"
      - ".venv/"
      - "dist/"
      - "build/"
      - "*.min.js"
      - "*.lock"
    max_file_size_kb: 500                      # Skip files larger than this
    chunking_strategy: "semantic"              # semantic | fixed_size | document | agentic
```

### Environment Variables

| Variable | Purpose |
|---|---|
| `EMBER_API_KEY` | Authenticates with both Ember Code and VectorBridge (single key) |
| `VECTORBRIDGE_API_URL` | Override VectorBridge API URL (for self-hosted) |

### Slash Commands

```
/vectorbridge status              — show indexing status
/vectorbridge reindex             — reindex the full project
/vectorbridge reindex --changed   — reindex only changed files
/vectorbridge search <query>      — quick semantic search from the CLI
```

---

## Self-Hosting (Advanced)

VectorBridge is included free with Ember Code accounts. But for teams that need to keep code on-premises, VectorBridge can be self-hosted:

```yaml
# docker-compose.yml (VectorBridge stack)
services:
  weaviate:      # Vector database
  postgres:      # Metadata & references
  redis:         # Cache & rate limiting
  transformers:  # Embedding model
  vectorbridge:  # API server (FastAPI)
```

Point Ember Code to your self-hosted instance:

```yaml
# .ember/config.yaml
vectorbridge:
  api_url: "https://vectorbridge.internal.yourcompany.com"
```

Or via environment variable:
```bash
export VECTORBRIDGE_API_URL=https://vectorbridge.internal.yourcompany.com
```

---

## Why Not Just Use Grep?

| Question | Grep | VectorBridge |
|---|---|---|
| "How does auth work?" | Finds files with "auth" in the name/content | Returns auth module summary with flow description, security analysis, and references |
| "What's vulnerable?" | Can't answer | Returns security-category summaries flagging issues across the codebase |
| "Where should I add rate limiting?" | Can't answer | Returns architecture summaries of request-handling modules with dependency analysis |
| "What needs more tests?" | Can't answer | Returns testability-category summaries ranking under-tested areas |
| "Find code similar to this function" | Can't answer | Vector similarity search finds structurally similar code |
| "What depends on this module?" | Fragile regex on imports | Returns complete reference graph with tags |

Grep finds strings. VectorBridge finds meaning.

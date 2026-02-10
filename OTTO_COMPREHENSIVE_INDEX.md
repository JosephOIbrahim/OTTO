# OTTO OS v0.7.0 - Comprehensive System Index
## For Architecture Review & Targeted Improvement Planning

**Generated:** 2026-02-03
**Purpose:** Complete codebase map for Claude Desktop review sessions
**Focus Areas:** WhatsApp voice integration, system-wide improvements

---

## 1. SYSTEM OVERVIEW

**OTTO OS** is a cognitive operating system for variable attention (ADHD-native design).

| Metric | Value |
|--------|-------|
| Version | 0.7.0 (Alpha) |
| Test Files | 157 files, 4,392+ tests |
| Python | 3.10+ |
| Platforms | Discord, WhatsApp, Telegram, CLI, Web Dashboard |
| Determinism | Determinism (application-level) |
| Encryption | AES-256-GCM at rest |
| Memory | SQLite-backed trail storage (OTTOMemory) |

---

## 2. ARCHITECTURE DIAGRAM

```
+-----------------------------------------------------------------------+
|                           OTTO OS v0.7.0                                |
+-----------------------------------------------------------------------+
|                                                                         |
|  SURFACES (Platform Adapters)                                           |
|  +-----------+-----------+-----------+--------+--------+-------+       |
|  | Discord   | WhatsApp  | Telegram  | CLI    | TUI    | Web   |       |
|  | adapter.py| adapter.py| adapter.py| main.py| app.py | dash  |       |
|  | bot.py    | server.py | bot.py    |        |        |       |       |
|  |           | webhook.py| services  |        |        |       |       |
|  |           | media.py  | approval  |        |        |       |       |
|  |           | session.py|           |        |        |       |       |
|  +-----------+-----------+-----------+--------+--------+-------+       |
|        |           |           |          |        |       |            |
|        v           v           v          v        v       v            |
|  +------------------------------------------------------------------+  |
|  |              COGNITIVE ORCHESTRATOR (NEXUS Pipeline)               |  |
|  |                                                                    |  |
|  |  Phase 0: RETRIEVE  -> Knowledge fast path (O(1))                 |  |
|  |  Phase 1: DETECT    -> PRISM signal extraction                    |  |
|  |  Phase 2: CASCADE   -> Expert routing (7 experts, fixed priority) |  |
|  |  Phase 3: LOCK      -> Parameter locking (MAX3 bounds)            |  |
|  |  Phase 4: EXECUTE   -> Decision engine                            |  |
|  |  Phase 5: UPDATE    -> Convergence tracking (RC^+xi)              |  |
|  |  [FLUSH]: Trail updates applied (BCM, batch-invariant)            |  |
|  +------------------------------------------------------------------+  |
|        |           |           |          |                             |
|        v           v           v          v                             |
|  +----------------+  +----------------+  +-------------------+         |
|  | LLM MODULE     |  | VOICE CORE     |  | MEMORY BACKBONE   |         |
|  | Claude provider |  | STT (Whisper)  |  | OTTOMemory        |         |
|  | Model router   |  | TTS (OpenAI)   |  | TrailStore (SQLite)|        |
|  | Response gen   |  | prepare_speech |  | Knowledge Graph   |         |
|  | Voice-aware    |  | Voice identity |  | Episode recording |         |
|  | Atmosphere     |  | Queue system   |  | Decay worker      |         |
|  +----------------+  | Metrics        |  +-------------------+         |
|                       +----------------+                                |
|                                                                         |
|  +------------------------------------------------------------------+  |
|  |              INFRASTRUCTURE                                        |  |
|  |  Encryption | Resilience | Protocol | Agents | Calibration        |  |
|  |  Security   | Bulkhead   | MCP      | Hooks  | Substrate          |  |
|  +------------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
```

---

## 3. FILE MAP (src/otto/)

### 3.1 Core Cognitive Engine
```
cognitive_orchestrator.py    5-Phase NEXUS pipeline (DETECT->CASCADE->LOCK->EXECUTE->UPDATE)
prism_detector.py            Signal detection (6 categories, fixed priority)
expert_router.py             7 experts (Validator>Scaffolder>Restorer>Refocuser>Celebrator>Socratic>Direct)
parameter_locker.py          MAX3 bounded reflection + safety gating
convergence_tracker.py       RC^+xi epistemic tension tracking
cognitive_state.py           State management (burnout, momentum, energy, mode, altitude)
cognitive_support.py         ADHD support (working memory limits, tangent budget)
cognitive_stage.py           USD-native cognitive stage (prims + attributes)
decision_engine.py           Task routing (work/delegate/protect)
agent_coordinator.py         Agent orchestration
tension_surfacer.py          Conflict detection
determinism.py               utilities (sorted_max, kahan_sum, etc.)
```

### 3.2 WhatsApp Module (src/otto/whatsapp/)
```
__init__.py                  Package exports
schemas.py                   Pydantic models: MessageType, IncomingMessage, WebhookPayload, etc.
api.py                       WhatsApp Cloud API client (async aiohttp)
webhook.py                   FastAPI webhook handler (GET verify, POST messages)
media.py                     Media download/upload with 2-tier cache (memory + disk)
session.py                   Per-phone session management (30min timeout, JSON persistence)
adapter.py                   Main voice pipeline adapter (STT->Process->TTS->Send)
server.py                    FastAPI app with /health, /status, /webhook endpoints
```

### 3.3 Voice Core (src/otto/voice_core/)
```
__init__.py                  65 exports across 8 categories
determinism.py               Fixed seeds, DeterministicRNG, Kahan summation, batch processing
stt.py                       Speech-to-Text via OpenAI Whisper (temp=0.0 for determinism)
tts.py                       Text-to-Speech via OpenAI (6 voices, 2 models, 6 formats)
prepare_for_speech.py        5-phase pipeline: format->abbreviations->numbers->markers->cleanup
voice_identity.py            OTTO persona enforcement (forbidden phrases, word limits)
queue.py                     Async processing queue (3 workers, retry, persistence)
metrics.py                   Latency tracking (per-phase), cost calculation, projections
```

### 3.4 LLM Module (src/otto/llm/)
```
provider.py                  LLMProvider protocol (generate, is_available)
claude_provider.py           Anthropic Claude integration (Sonnet default, Haiku fallback)
response_generator.py        Voice-aware generation (expert prompts, atmosphere, register)
model_router.py              LIVRPS-based model routing (Haiku for simple, Sonnet for complex)
```

### 3.5 Memory Module (src/otto/memory/)
```
interface.py                 OTTOMemory singleton (episodic, procedural, contextual, identity)
                             Episode, EpisodeQuery, Context, ContextDelta, Identity classes
                             KnowledgeGraph with bootstrap prims
                             TrailDecayWorker (7-day half-life)
                             Mock implementations for fallback
```

### 3.6 Trails Module (src/otto/trails/)
```
models.py                    Trail, TrailType (QUALITY/CONTEXT/DECISION/PATTERN/WORK), TrailQuery
store.py                     TrailStore (SQLite backend, encryption, UNIQUE constraint on type+path+signal)
                             Deposit, reinforce, weaken, decay, relationship recording
```

### 3.7 Other Platform Adapters
```
discord/adapter.py           Discord -> OTTO (message history, per-user memory)
discord/bot.py               Discord.py bot implementation
telegram/adapter.py          Telegram -> OTTO (MCP services, inline buttons)
telegram/bot.py              python-telegram-bot wrapper
telegram/approval.py         Approval flow for commands
telegram/services.py         Telegram-specific services
```

### 3.8 Voice Register & Atmosphere
```
voice/adapter.py             Register-aware response adaptation
voice/register.py            Register detection (CASUAL/FORMAL/TERSE/VENTING/NEUTRAL)
voice/inference_params.py    Voice-aware inference parameters
voice/prompts.py             Expert-specific voice prompts
atmosphere/pipeline.py       Supportive language transformation
atmosphere/permissions.py    Permission granting ("Permission granted: rest is productive")
atmosphere/reframes.py       Reframing language
render/human_render.py       Natural language generation
```

### 3.9 Infrastructure
```
protocol/                    Binary (MessagePack) + JSON-RPC messaging layers
agents/                      Base agent, planner, researcher, reflection, memory, progress
services/mcp/                MCP servers (calendar, email, notion, repos, tasks)
integration/                 Calendar (iCal), Tasks (JSON), Notes (Markdown)
crypto/                      AES-256-GCM, Argon2id key derivation, post-quantum ready
security/                    Audit, self-healing, HSM, WebAuthn
storage/                     Platform-agnostic storage provider
sync/                        WebDAV + S3 sync engine
substrate/                   USD cognitive substrate runtime, EWM, knowledge, state manager
api/                         REST + WebSocket API (authentication, rate limiting, TLS)
cli/                         Command-line interface + TUI (textual framework)
hooks/                       Auto-validate, cognitive state, trail context hooks
calibration/                 BCM-style learning, outcome tracking
```

---

## 4. WHATSAPP DEEP DIVE

### 4.1 Current Capabilities
| Feature | Status | File |
|---------|--------|------|
| Text messages (receive/send) | Working | adapter.py, webhook.py |
| Voice messages (receive/transcribe/respond) | Working | adapter.py, voice_core/ |
| Conversation memory (read/write) | Working | adapter.py (memory integration) |
| Real LLM responses | Working | server.py (ResponseGenerator) |
| Voice response synthesis | Working | adapter.py (TTS pipeline) |
| Webhook verification | Working | webhook.py (challenge-response) |
| HMAC signature validation | Working | webhook.py (optional, needs app_secret) |
| Media download/upload | Working | media.py (2-tier cache) |
| Session management | Working | session.py (30min timeout, JSON persistence) |
| Latency tracking (per-phase) | Working | metrics.py |
| Cost projections | Working | metrics.py |
| Health/status endpoints | Working | server.py (/health, /status) |

### 4.2 WhatsApp Cloud API Usage
| API Feature | Used? | Notes |
|-------------|-------|-------|
| Send text | YES | api.send_text() |
| Send audio | YES | api.send_audio() via media_id |
| Send reaction | YES | api.send_reaction() (emoji) |
| Mark as read | YES | api.mark_as_read() |
| Upload media | YES | api.upload_media() |
| Download media | YES | api.download_media() |
| Interactive messages (buttons/lists) | NO | Schema defined but not implemented |
| Template messages | NO | Schema defined but not used |
| Image messages | NO | Schema defined, handler missing |
| Video messages | NO | Schema defined, handler missing |
| Document messages | NO | Schema defined, handler missing |
| Location messages | NO | Schema defined, handler missing |
| Sticker messages | NO | Schema defined, handler missing |
| Contact sharing | NO | Not implemented |
| Delivery status callbacks | NO | Not implemented |
| Typing indicator | NO | Config exists but not wired |
| Group messaging | NO | Not implemented |
| Message templates (for 24h window) | NO | Not implemented |

### 4.3 Voice Pipeline Flow
```
WhatsApp Voice Message Received
  |
  v
1. _on_voice_message()
   - Update session state
   - Mark as read
   - React with microphone emoji
   - Download audio via media handler
   - Enqueue to VoiceProcessingQueue
  |
  v
2. _process_voice_message() [async worker]
   |
   +-- Phase 1: STT (Whisper, temp=0.0)
   |     transcribe_bytes() -> TranscriptionResult
   |
   +-- Phase 2: OTTO Processing
   |     _get_conversation_history() -> List[ConversationTurn]
   |     otto_processor(text, context) -> response_text
   |       -> orchestrator.process_message() -> NexusResult
   |       -> ResponseGenerator.generate() -> LLM response
   |
   +-- Phase 3: prepare_for_speech()
   |     5-phase: format->abbreviations->numbers->markers->cleanup
   |
   +-- Phase 4: TTS (OpenAI, NOVA voice, OPUS format)
   |     tts.synthesize() -> TTSResult
   |
   +-- Phase 5: Upload & Send
   |     media.upload_audio() -> media_id
   |     api.send_audio() -> sent
   |
   +-- Record episode to OTTOMemory
   +-- Record latency + cost metrics
```

### 4.4 WhatsApp Configuration
```
Environment Variables:
  OPENAI_API_KEY           Required  STT (Whisper) + TTS
  WHATSAPP_TOKEN           Required  WhatsApp Cloud API auth
  WHATSAPP_PHONE_NUMBER_ID Required  WhatsApp Business phone
  WHATSAPP_VERIFY_TOKEN    Optional  Webhook verification (default: "otto-voice-webhook")
  WHATSAPP_APP_SECRET      Optional  HMAC signature validation
  ANTHROPIC_API_KEY        Required  LLM response generation

Voice Settings:
  enable_voice_response    True      Send voice or text responses
  send_typing_indicator    True      (NOT WIRED - config only)
  max_response_length      4000      Truncation limit

Queue Settings:
  max_retries              3         Retry failed messages
  retry_delay              1.0s      Base delay (exponential backoff)
  max_queue_size           1000      Maximum pending messages
  processing_timeout       30.0s     Per-message timeout
  workers                  3         Concurrent processors

Session Settings:
  session_timeout_minutes  30        Inactivity timeout
  max_sessions             10000     Maximum concurrent sessions
  cleanup_interval         5 min     Expired session cleanup

Voice Identity:
  Voice                    NOVA      Friendly, approachable (female)
  Model                    TTS-1     Standard quality, low latency
  Format                   OPUS      WhatsApp compatible
  Speed                    1.0x      Normal pace
  MAX_SPOKEN_WORDS         60        ~30 seconds of speech
  MAX_SPOKEN_SENTENCES     4         Breathing room
  VOICE_RESPONSE_MAX_LENGTH 500      Chars - longer responses fall back to text
```

### 4.5 Cost Model
```
Per Voice Interaction (estimated):
  STT (Whisper):    $0.006/minute audio
  TTS (OpenAI):     $0.015/1K chars (tts-1)
  LLM (Claude):     ~$0.01/interaction (Haiku) or ~$0.05 (Sonnet)
  Total:            ~$0.02-0.07 per interaction

Daily Target: $0.22/user (20 interactions)
Monthly Target: ~$6.60/user

Current projection endpoint: GET /health -> adapter_stats.cost_projection
```

---

## 5. COGNITIVE PIPELINE DETAILS

### 5.1 Expert Routing (Fixed Priority - First Match Wins)
```
Priority  Expert      Triggers                         Model Tier
--------  ----------  -------------------------------  ----------
1         Validator   frustrated, RED, caps, negative  Sonnet
2         Scaffolder  overwhelmed, stuck, too_many     Sonnet
3         Restorer    depleted, ORANGE, post-crash     Haiku
4         Refocuser   distracted, tangent_over         Haiku
5         Celebrator  task_complete, milestone          Haiku
6         Socratic    exploring, high_energy, what_if  Sonnet
7         Direct      focused, hyperfocused, flow      Haiku
```

### 5.2 Model Router (LIVRPS Resolution)
```
L (Local):     Safety overrides -> Sonnet for RED/ORANGE/depleted/crashed
I (Inherits):  Complexity -> Sonnet for signal_complexity > 0.7
V (Variants):  Emotional -> Sonnet for emotional_intensity > 0.6
R (References): User preference -> Requested tier
P (Payloads):  Expert needs -> See table above
S (Specializes): Default -> Haiku (cost-optimized)
```

### 5.3 Response Generation Pipeline
```
1. Detect register (CASUAL/FORMAL/TERSE/VENTING/NEUTRAL)
2. Get voice-aware inference params (temp, top_p, max_tokens)
3. Build expert-specific system prompt + voice guidance
4. Route to model (Haiku vs Sonnet via LIVRPS)
5. Build conversation history (ConversationTurn list)
6. Generate via Claude API
7. Adapt response for register (strip forbidden phrases, limit length)
8. Apply atmosphere (supportive language transformation)
9. Return final response
```

---

## 6. MEMORY SYSTEM

### 6.1 Architecture
```
OTTOMemory (Singleton)
  |
  +-- Episodic Memory (What happened)
  |     record_episode() / query_episodes()
  |     -> TrailStore deposits
  |
  +-- Procedural Memory (What works)
  |     deposit_trail() / follow_trail()
  |     -> Trail strength (auto-approve at 0.8)
  |
  +-- Contextual Memory (Where you are)
  |     get_context() / update_context()
  |     -> EWM + LIVRPS layers
  |
  +-- Identity Memory (Who you are)
  |     get_identity() / get_substrate_value()
  |     -> Constitutional + Learned values
  |
  +-- Knowledge Graph (Fast retrieval)
        get(path) / query(trigger)
        -> O(1) lookup, 89 prims, 340+ triggers
```

### 6.2 Episode Flow (WhatsApp)
```
User sends message
  -> adapter._on_text_message() or _process_voice_message()
  -> _get_conversation_history(phone, limit=10)
     -> EpisodeQuery(type="surface.whatsapp.message", service="whatsapp")
     -> Filter by phone_number
     -> Sort oldest first
     -> Build ConversationTurn list
  -> otto_processor(text, {phone, conversation_history})
     -> ResponseGenerator.generate() with history
  -> _record_episode(phone, user_msg, assistant_response)
     -> Episode(type="surface.whatsapp.message.{phone}.{timestamp_ms}")
     -> memory.record_episode() -> TrailStore deposit
```

### 6.3 Trail Storage (SQLite)
```sql
CREATE TABLE trails (
    id INTEGER PRIMARY KEY,
    trail_type TEXT NOT NULL,       -- quality|context|decision|pattern|work
    path TEXT NOT NULL,              -- episode type string
    signal TEXT NOT NULL,            -- serialized episode data
    strength REAL DEFAULT 1.0,       -- 0.0-1.0 with decay
    deposited_by TEXT NOT NULL,      -- "whatsapp_adapter", "discord_adapter", etc.
    deposited_at TEXT NOT NULL,      -- ISO timestamp
    reinforced_count INTEGER DEFAULT 0,
    half_life_days REAL DEFAULT 7.0, -- Decay rate
    metadata TEXT DEFAULT '{}',      -- JSON blob
    UNIQUE(trail_type, path, signal)  -- Dedup + reinforce
);
```

---

## 7. TEST COVERAGE MAP

### 7.1 Coverage by Component
| Component | Test Files | Tests | Determinism | Integration |
|-----------|-----------|-------|-------------|-------------|
| WhatsApp schemas | 1 | 29 | 0 | 0 |
| Voice core | 4 | 99+ | 40+ | 0 |
| Voice adapter | 3 | 39 | 9 | 0 |
| Cognitive engine | 5+ | 100+ | Yes | Yes |
| Memory | 2+ | 50+ | Yes | Yes |
| LLM | 1+ | 20+ | N/A | N/A |
| Protocol | 11 | 100+ | N/A | Yes |
| Encryption | 23 | 200+ | N/A | Yes |
| API | 30 | 300+ | Yes | Yes |

### 7.2 Critical Test Gaps
```
MISSING - WhatsApp Integration:
  - No adapter integration tests (receive -> process -> respond)
  - No voice message end-to-end tests
  - No memory recording tests for WhatsApp context
  - No session persistence tests
  - No webhook signature validation tests
  - No media download/upload tests
  - No error recovery tests (queue retry, API failure)

MISSING - Cross-Surface:
  - No cross-platform memory consistency tests
  - No voice quality consistency across surfaces
  - No session handoff between platforms

MISSING - Production:
  - No load/stress tests for WhatsApp queue
  - No latency regression tests
  - No cost tracking verification
```

---

## 8. IDENTIFIED GAPS & IMPROVEMENT OPPORTUNITIES

### 8.1 HIGH PRIORITY (Production Blockers)

**G1: WhatsApp Typing Indicator Not Wired**
- `send_typing_indicator: bool = True` exists in config
- Never actually called in adapter code
- Users see no feedback while OTTO processes (up to 10s)
- **Fix:** Call `api.send_typing_indicator()` at start of processing

**G2: Response Truncation is Naive**
- `response[:4000] + "..."` cuts mid-word/mid-sentence
- **Fix:** Sentence-boundary-aware truncation

**G3: No Context Window Management**
- Conversation history grows unbounded in LLM context
- Fixed limit=10 episodes, but no token counting
- **Fix:** Token-aware context windowing with summarization

**G4: No Message Delivery Confirmation**
- Send audio/text but never verify delivery
- No handling of WhatsApp delivery status webhooks
- **Fix:** Handle status callbacks, retry on failure

**G5: Missing WhatsApp Integration Tests**
- Only schema validation tests exist
- No end-to-end pipeline tests
- **Fix:** Add adapter, webhook, media, session integration tests

### 8.2 MEDIUM PRIORITY (Quality & Scale)

**G6: No Conversation Summarization**
- Long conversations lose context (only last 10 exchanges)
- **Fix:** Periodic summarization stored as condensed episode

**G7: No Episode Garbage Collection**
- Episodes accumulate forever in TrailStore
- trail decay exists but episodes have unique types (never reinforced)
- **Fix:** Episode-specific pruning by age, count, or user

**G8: Cross-Platform Identity Gap**
- Discord user =/= WhatsApp user, even if same person
- No user linking mechanism
- **Fix:** User identity layer with optional linking

**G9: WhatsApp Interactive Messages Not Used**
- Buttons, lists, quick replies all available in WhatsApp API
- Could reduce cognitive load (ADHD-native: limit choices)
- **Fix:** Interactive message support for key decision points

**G10: No Proactive OTTO**
- OTTO only responds to messages
- Could check in: "Haven't heard from you today. All good?"
- **Fix:** Scheduled proactive messages via WhatsApp templates

**G11: Voice Quality Adaptation Missing**
- TTS always uses same voice/speed regardless of user state
- adjust_for_context() exists but not called in WhatsApp pipeline
- **Fix:** Wire voice identity context adjustment into adapter

### 8.3 FUTURE (Differentiation)

**G12: Multi-Modal WhatsApp**
- Image, document, location messages all have schemas but no handlers
- Could process images (describe, OCR), documents (summarize), locations
- **Fix:** Add handlers for additional message types

**G13: WhatsApp Group Support**
- No group messaging support
- OTTO could be added to family/team groups
- **Fix:** Group message handling with @mention detection

**G14: Voice Emotion Detection**
- STT only returns text, not emotional cues
- Audio analysis could detect stress, energy, mood
- **Fix:** Audio feature extraction before/alongside STT

**G15: Observability Dashboard for WhatsApp**
- Metrics collected but only via /health endpoint
- No real-time dashboard for WhatsApp operations
- **Fix:** Wire WhatsApp metrics to existing TUI/web dashboard

**G16: 24-Hour Messaging Window**
- WhatsApp Business API has 24-hour response window
- After 24h, must use pre-approved templates
- Not handled at all currently
- **Fix:** Template message support + window tracking

**G17: Rate Limiting**
- No rate limiting on WhatsApp API calls
- WhatsApp enforces limits server-side (will get 429s)
- **Fix:** Client-side rate limiting per phone number

**G18: Conversation Export**
- No way to export WhatsApp conversation history
- Users might want their data
- **Fix:** Export endpoint for conversation history

---

## 9. RECOMMENDED ACTION TIERS

### Tier 1: Ship-Ready (Make WhatsApp Production-Grade)
1. Wire typing indicator (G1)
2. Sentence-boundary truncation (G2)
3. Add WhatsApp integration tests (G5)
4. Handle delivery status callbacks (G4)
5. Wire voice identity context adjustment (G11)

### Tier 2: Scale (Handle Real Users)
6. Context window management with token counting (G3)
7. Conversation summarization (G6)
8. Episode garbage collection (G7)
9. 24-hour messaging window + templates (G16)
10. Client-side rate limiting (G17)

### Tier 3: Differentiate (OTTO's Unique Value)
11. Interactive messages for choices (G9)
12. Proactive check-ins (G10)
13. Multi-modal message handling (G12)
14. Voice emotion detection (G14)
15. Cross-platform identity (G8)

---

## 10. KEY CONSTANTS & SEEDS

```python
# Voice Core
WHATSAPP_VOICE_SEED     = 0xDEADBEEF
TTS_VOICE_SEED          = 0xFEEDFACE
STT_NORMALIZATION_SEED  = 0xCAFED00D

# Cognitive
COGNITIVE_TILE_SIZE     = 32           # fixed batch size
DETERMINISM_SEED        = 0xCAFEBABE   # State hashing
HASH_ALGORITHM          = "sha256"

# Memory
MEMORY_SEED             = 0xAE0717E5
AUTO_APPROVE_THRESHOLD  = 0.8          # Trail strength for auto-approval
LEARNING_THRESHOLD      = 0.7          # Confidence for learning proposals
PRUNE_THRESHOLD         = 0.1          # Minimum trail strength

# Voice Identity
MAX_SPOKEN_WORDS        = 60           # ~30 seconds
MAX_SPOKEN_SENTENCES    = 4
VOICE_RESPONSE_MAX_LENGTH = 500        # Chars before text fallback

# Session
SESSION_TIMEOUT         = 30 min
MAX_SESSIONS            = 10000
CLEANUP_INTERVAL        = 5 min

# Queue
MAX_RETRIES             = 3
RETRY_DELAY             = 1.0s (exponential backoff)
MAX_QUEUE_SIZE          = 1000
PROCESSING_TIMEOUT      = 30.0s
WORKERS                 = 3

# Latency Target
VOICE_LATENCY_TARGET    = 10000 ms     # 10 seconds end-to-end

# Cost Target
DAILY_COST_TARGET       = $0.22/user   # 20 interactions
```

---

## 11. ENVIRONMENT VARIABLES

| Variable | Required | Default | Used By |
|----------|----------|---------|---------|
| `ANTHROPIC_API_KEY` | Yes (LLM) | - | ResponseGenerator |
| `OPENAI_API_KEY` | Yes (voice) | - | STT (Whisper), TTS |
| `WHATSAPP_TOKEN` | Yes (WhatsApp) | - | WhatsApp API auth |
| `WHATSAPP_PHONE_NUMBER_ID` | Yes (WhatsApp) | - | WhatsApp Business |
| `WHATSAPP_VERIFY_TOKEN` | No | "otto-voice-webhook" | Webhook verification |
| `WHATSAPP_APP_SECRET` | No | "" | HMAC signature |
| `DISCORD_BOT_TOKEN` | Yes (Discord) | - | Discord bot |
| `TELEGRAM_BOT_TOKEN` | Yes (Telegram) | - | Telegram bot |

---

## 12. QUICK REFERENCE: ENTRY POINTS

```bash
# WhatsApp Voice Server
python -m otto.whatsapp.server --port 8000

# Discord Bot
python -m otto.discord.bot

# CLI
otto              # Interactive
otto status       # Show cognitive state
otto tui          # TUI dashboard

# Tests
pytest tests/test_whatsapp/ -v
pytest tests/test_voice_core/ -v
pytest tests/test_voice/ -v
pytest tests/integration/ -v
pytest -m determinism              # determinism only
pytest --cov=src/otto --cov-report=html

# Health Check (when server running)
curl http://localhost:8000/health
curl http://localhost:8000/status
```

---

## 13. FILE COUNTS BY CATEGORY

| Category | Files | Lines (est.) |
|----------|-------|-------------|
| Core cognitive engine | 12 | 3,000+ |
| WhatsApp module | 8 | 2,500+ |
| Voice core | 8 | 2,000+ |
| Voice register/adapter | 5 | 1,500+ |
| LLM module | 4 | 1,500+ |
| Memory module | 1 (large) | 1,200+ |
| Trails module | 2 | 800+ |
| Atmosphere | 10 | 1,500+ |
| Protocol | 9 | 2,000+ |
| Agents | 11 | 2,500+ |
| API (REST/WS) | 20+ | 4,000+ |
| Security/Crypto | 15+ | 3,000+ |
| Infrastructure | 20+ | 4,000+ |
| Tests | 157 | 30,000+ |
| **Total** | **280+** | **55,000+** |

---

## 14. DETERMINISM COMPLIANCE ([He2025])

| Component | Compliance | Mechanism |
|-----------|-----------|-----------|
| Cognitive routing | Full | Fixed evaluation order, first-match-wins |
| Expert selection | Full | Fixed priority (Validator > ... > Direct) |
| Signal detection | Full | 6 categories, fixed detection order |
| Voice preparation | Full | 5-phase fixed pipeline |
| STT | Partial | temperature=0.0 (Whisper API has some variance) |
| TTS | Partial | Deterministic text prep, API may vary audio |
| Memory queries | Full | Sorted by timestamp, fixed order |
| Episode recording | Full | Unique types with timestamps |
| Trail operations | Full | Sorted aggregation, Kahan summation |
| Batch processing | Full | COGNITIVE_TILE_SIZE=32, fixed |
| Knowledge retrieval | Full | O(1) lookup, sorted results |

---

*End of Comprehensive Index*
*Use this document with Claude Desktop for targeted improvement discussions.*

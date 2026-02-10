#!/usr/bin/env python3
"""
Protocol-Aware Hook for Claude Code
====================================

Enhanced hook that supports both:
- Regular user prompts → NEXUS Pipeline
- JSON-RPC requests → Protocol Router

Usage:
    python -m otto.hooks.protocol_hook < input.json

Input format (regular):
    {"user_prompt": "your message here"}

Input format (JSON-RPC):
    {"user_prompt": {"jsonrpc": "2.0", "method": "otto.status", "id": 1}}

Output format:
    {
        "systemMessage": "...",
        "hookSpecificOutput": {...}
    }

Determinism:
- Format detection is FIXED order (JSON-RPC → regular)
- Same input → same output
"""

import asyncio
import json
import sys
import logging

logger = logging.getLogger(__name__)

# Import cognitive pipeline
try:
    from ..cognitive_orchestrator import create_orchestrator
    from ..dashboard_bridge import create_bridge
except ImportError:
    try:
        from otto.cognitive_orchestrator import create_orchestrator
        from otto.dashboard_bridge import create_bridge
    except ImportError:
        create_orchestrator = None
        create_bridge = None

# Import protocol router
try:
    from ..protocol import create_protocol_router
except ImportError:
    try:
        from otto.protocol import create_protocol_router
    except ImportError:
        create_protocol_router = None


# Singleton instances
_orchestrator = None
_bridge = None
_protocol_router = None


def get_orchestrator():
    """Get or create singleton orchestrator."""
    global _orchestrator
    if _orchestrator is None and create_orchestrator:
        _orchestrator = create_orchestrator()
    return _orchestrator


def get_bridge():
    """Get or create singleton bridge."""
    global _bridge
    if _bridge is None and create_bridge:
        orchestrator = get_orchestrator()
        if orchestrator:
            _bridge = create_bridge(orchestrator)
    return _bridge


def get_protocol_router():
    """Get or create singleton protocol router."""
    global _protocol_router
    if _protocol_router is None and create_protocol_router:
        _protocol_router = create_protocol_router()
    return _protocol_router


def is_jsonrpc_request(data):
    """
    Check if data is a JSON-RPC request.

    Detection (FIXED order):
    1. Dict with "jsonrpc" key
    2. String that parses to dict with "jsonrpc"
    """
    if isinstance(data, dict) and "jsonrpc" in data:
        return True
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            return isinstance(parsed, dict) and "jsonrpc" in parsed
        except json.JSONDecodeError:
            return False
    return False


def build_guidance(result):
    """Build expert-specific guidance from NEXUS result."""
    try:
        expert = result.routing.expert.value
        paradigm = result.lock.params.paradigm

        expert_guidance = {
            "validator": "EMPATHY FIRST. Acknowledge the struggle. Normalize difficulty.",
            "scaffolder": "BREAK DOWN the task. Provide structure. Reduce scope if needed.",
            "restorer": "EASY WINS mode. Suggest simple tasks. Rest is OK.",
            "refocuser": "GENTLE REDIRECT. Acknowledge tangent, guide back to goal.",
            "celebrator": "ACKNOWLEDGE THE WIN. Provide dopamine boost.",
            "socratic": "GUIDE DISCOVERY. Follow threads. Ask questions.",
            "direct": "MINIMAL FRICTION. Stay out of the way. Direct execution."
        }

        guidance = expert_guidance.get(expert, "Proceed with standard response.")

        if not result.routing.safety_gate_pass:
            guidance = f"SAFETY GATE TRIGGERED. " + guidance

        if paradigm == "Mycelium":
            guidance += " Follow associative threads."
        else:
            guidance += " Stay structured and explicit."

        return guidance
    except Exception:
        return "Proceed with standard response."


async def process_jsonrpc(request):
    """Process JSON-RPC request through protocol router."""
    router = get_protocol_router()
    if not router:
        return {
            "systemMessage": "[Protocol router not available]",
            "hookSpecificOutput": {"error": "Protocol router not configured"}
        }

    try:
        # Parse if string
        if isinstance(request, str):
            request = json.loads(request)

        # Route through protocol router
        response = await router.route(request)

        # Format for hook output
        if isinstance(response, dict):
            if "result" in response:
                return {
                    "systemMessage": f"[RPC:{response.get('id', 'n/a')}] Success",
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "rpcResponse": response
                    }
                }
            elif "error" in response:
                return {
                    "systemMessage": f"[RPC:{response.get('id', 'n/a')}] Error: {response['error'].get('message', 'Unknown')}",
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "rpcResponse": response
                    }
                }

        return {
            "systemMessage": "[RPC] Response received",
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "rpcResponse": response
            }
        }

    except Exception as e:
        return {
            "systemMessage": f"[RPC Error: {str(e)[:50]}]",
            "hookSpecificOutput": {"error": str(e)}
        }


def process_prompt(user_prompt, context=None):
    """Process regular prompt through NEXUS pipeline."""
    try:
        bridge = get_bridge()
        if not bridge:
            return {
                "systemMessage": "[NEXUS pipeline not available]"
            }

        result = bridge.process_and_broadcast(user_prompt, context or {})

        # Build system message
        anchor = result.to_anchor()
        guidance = build_guidance(result)

        system_message = f"{anchor}\n\n{guidance}"

        return {
            "systemMessage": system_message,
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": f"Orchestra: expert={result.routing.expert.value}, tension={result.convergence.epistemic_tension:.2f}"
            }
        }

    except Exception as e:
        return {
            "systemMessage": f"[EXEC:error|Direct|Cortex|30000ft|standard] (Error: {str(e)[:50]})"
        }


async def process_input(input_data):
    """
    Process input through appropriate handler.

    Detection order (FIXED):
    1. Check if user_prompt is JSON-RPC request
    2. Otherwise, process as regular prompt
    """
    user_prompt = input_data.get("user_prompt", "")

    if not user_prompt:
        return {}

    # Check for JSON-RPC request
    if is_jsonrpc_request(user_prompt):
        return await process_jsonrpc(user_prompt)

    # Regular prompt - process through NEXUS
    return process_prompt(user_prompt)


def main():
    """Main entry point for protocol-aware hook."""
    try:
        # Read input from stdin
        input_data = json.load(sys.stdin)

        # Process (may be async)
        result = asyncio.run(process_input(input_data))

        # Output result
        print(json.dumps(result))

    except json.JSONDecodeError:
        print(json.dumps({"systemMessage": "[Protocol hook: invalid JSON input]"}))

    except Exception as e:
        print(json.dumps({"systemMessage": f"[Protocol hook error: {str(e)[:100]}]"}))

    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
OTTO OS CLI - Main Entry Point

Commands:
  otto                   # Start interactive mode
  otto status            # Show status line
  otto status -s         # Short status for prompts
  otto set               # Set cognitive state
  otto init              # Initialize shell integration
  otto intake            # Run personality intake
  otto remember [text]   # Store personal knowledge
  otto forget [query]    # Remove knowledge
  otto protect           # Protection controls
  otto config            # Open/set configuration
  otto export            # Export all data
  otto wipe              # Delete all OTTO data
  otto sync              # Cloud sync operations

Your Personal Operating System.
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime


def cmd_interactive(args):
    """Start OTTO interactive mode."""
    from .interactive import run_interactive
    run_interactive()


def cmd_status(args):
    """Show cognitive status."""
    from .status import read_state, format_short, format_prompt, format_full, format_tmux, format_json

    state = read_state()
    use_color = not args.no_color and sys.stdout.isatty()

    if args.json:
        print(format_json(state))
    elif args.tmux:
        print(format_tmux(state))
    elif args.short:
        print(format_short(state, color=use_color))
    elif args.prompt:
        print(format_prompt(state, color=use_color))
    else:
        print(format_full(state, color=use_color))


def cmd_tui(args):
    """Launch TUI dashboard."""
    from .tui import run_tui, run_once

    if args.once:
        run_once()
    else:
        run_tui(watch=args.watch)


def cmd_set(args):
    """Set cognitive state values."""
    from .status import read_state
    import json

    state_file = Path.home() / ".orchestra" / "state" / "cognitive_state.json"
    state = read_state()

    if args.burnout:
        if args.burnout.upper() in ("GREEN", "YELLOW", "ORANGE", "RED"):
            state["burnout_level"] = args.burnout.upper()
        else:
            print(f"Invalid burnout level: {args.burnout}")
            print("Valid: GREEN, YELLOW, ORANGE, RED")
            return 1

    if args.mode:
        if args.mode.lower() in ("work", "delegate", "protect"):
            state["decision_mode"] = args.mode.lower()
        else:
            print(f"Invalid mode: {args.mode}")
            print("Valid: work, delegate, protect")
            return 1

    if args.momentum:
        valid = ("cold_start", "building", "rolling", "peak", "crashed")
        if args.momentum.lower() in valid:
            state["momentum_phase"] = args.momentum.lower()
        else:
            print(f"Invalid momentum: {args.momentum}")
            print(f"Valid: {', '.join(valid)}")
            return 1

    if args.energy:
        valid = ("high", "medium", "low", "depleted")
        if args.energy.lower() in valid:
            state["energy_level"] = args.energy.lower()
        else:
            print(f"Invalid energy: {args.energy}")
            print(f"Valid: {', '.join(valid)}")
            return 1

    if args.task:
        state["current_task"] = args.task

    # Write state
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)

    print("State updated.")
    return 0


def cmd_init(args):
    """Initialize shell integration."""
    shell = args.shell or detect_shell()

    if shell == "bash":
        print(BASH_INTEGRATION)
    elif shell == "zsh":
        print(ZSH_INTEGRATION)
    elif shell == "fish":
        print(FISH_INTEGRATION)
    elif shell == "tmux":
        print(TMUX_INTEGRATION)
    elif shell == "starship":
        print(STARSHIP_INTEGRATION)
    else:
        print(f"Unknown shell: {shell}")
        print("Supported: bash, zsh, fish, tmux, starship")
        return 1

    return 0


def cmd_install_hook(args):
    """Install Claude Code hook for cognitive engine integration."""
    import json
    import shutil

    hooks_dir = Path.home() / ".claude" / "hooks"
    hooks_file = hooks_dir / "hooks.json"

    # Find Python executable
    python_exe = shutil.which("python") or shutil.which("python3") or sys.executable

    # Build the hook command (cross-platform)
    hook_command = f"{python_exe} -m orchestra.hooks"

    # Build the hook configuration
    hook_config = {
        "UserPromptSubmit": [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": hook_command,
                        "timeout": 5
                    }
                ]
            }
        ]
    }

    # Check for existing hooks.json
    existing_hooks = {}
    if hooks_file.exists():
        try:
            with open(hooks_file) as f:
                existing_hooks = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    if args.force or not existing_hooks:
        # Create/overwrite with Orchestra hook
        hooks_dir.mkdir(parents=True, exist_ok=True)
        with open(hooks_file, "w") as f:
            json.dump(hook_config, f, indent=2)
        print(f"Installed Orchestra hook to {hooks_file}")
        print(f"Hook command: {hook_command}")
        print()
        print("Restart Claude Code to activate the cognitive engine.")
        return 0

    # Existing hooks found - check if Orchestra already configured
    existing_prompts = existing_hooks.get("UserPromptSubmit", [])
    orchestra_present = any(
        "orchestra" in str(h.get("hooks", [{}])[0].get("command", "")).lower()
        for h in existing_prompts
        if h.get("hooks")
    )

    if orchestra_present and not args.force:
        print("Orchestra hook already installed.")
        print(f"Location: {hooks_file}")
        print()
        print("Use --force to reinstall.")
        return 0

    # Merge: add Orchestra hook to existing
    if not any(h.get("matcher") == "*" for h in existing_prompts):
        # No wildcard matcher, add one
        existing_prompts.append(hook_config["UserPromptSubmit"][0])
    else:
        # Update existing wildcard matcher
        for h in existing_prompts:
            if h.get("matcher") == "*":
                hooks_list = h.get("hooks", [])
                # Remove old orchestra hook if present
                hooks_list = [
                    hook for hook in hooks_list
                    if "orchestra" not in str(hook.get("command", "")).lower()
                ]
                # Add new orchestra hook
                hooks_list.append({
                    "type": "command",
                    "command": hook_command,
                    "timeout": 5
                })
                h["hooks"] = hooks_list
                break

    existing_hooks["UserPromptSubmit"] = existing_prompts

    # Write merged config
    with open(hooks_file, "w") as f:
        json.dump(existing_hooks, f, indent=2)

    print(f"Added Orchestra hook to {hooks_file}")
    print(f"Hook command: {hook_command}")
    print()
    print("Restart Claude Code to activate the cognitive engine.")
    return 0


def cmd_uninstall_hook(args):
    """Remove Claude Code hook for cognitive engine."""
    import json

    hooks_file = Path.home() / ".claude" / "hooks" / "hooks.json"

    if not hooks_file.exists():
        print("No hooks.json found. Nothing to uninstall.")
        return 0

    try:
        with open(hooks_file) as f:
            hooks = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading hooks.json: {e}")
        return 1

    # Remove Orchestra hooks
    modified = False
    if "UserPromptSubmit" in hooks:
        for matcher in hooks["UserPromptSubmit"]:
            if "hooks" in matcher:
                original_len = len(matcher["hooks"])
                matcher["hooks"] = [
                    h for h in matcher["hooks"]
                    if "orchestra" not in str(h.get("command", "")).lower()
                ]
                if len(matcher["hooks"]) < original_len:
                    modified = True

        # Clean up empty matchers
        hooks["UserPromptSubmit"] = [
            m for m in hooks["UserPromptSubmit"]
            if m.get("hooks")
        ]

        # Clean up empty UserPromptSubmit
        if not hooks["UserPromptSubmit"]:
            del hooks["UserPromptSubmit"]

    if modified:
        if hooks:
            with open(hooks_file, "w") as f:
                json.dump(hooks, f, indent=2)
            print("Removed Orchestra hook from hooks.json")
        else:
            hooks_file.unlink()
            print("Removed hooks.json (was only Orchestra hook)")
        print()
        print("Restart Claude Code to deactivate the cognitive engine.")
    else:
        print("Orchestra hook not found in hooks.json")

    return 0


def detect_shell() -> str:
    """Detect current shell."""
    import os
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        return "zsh"
    elif "fish" in shell:
        return "fish"
    elif "bash" in shell:
        return "bash"
    return "bash"


# =============================================================================
# New Commands: intake, remember, forget, protect, config, export, wipe, sync
# =============================================================================

def cmd_intake(args):
    """Run personality intake game."""
    from ..intake import run_intake, write_profile

    otto_dir = Path.home() / ".otto"
    profile_path = otto_dir / "profile.usda"

    # Check for existing profile
    if profile_path.exists() and not args.reset:
        print(f"Profile already exists at {profile_path}")
        print("Use --reset to re-run intake and overwrite.")
        return 0

    print("Starting OTTO personality intake...")
    print()

    try:
        profile_data = run_intake()
        otto_dir.mkdir(parents=True, exist_ok=True)
        write_profile(profile_data, profile_path)
        print()
        print(f"Profile saved to {profile_path}")
        return 0
    except KeyboardInterrupt:
        print("\nIntake cancelled.")
        return 1


def cmd_remember(args):
    """Store personal knowledge."""
    import json

    otto_dir = Path.home() / ".otto"
    knowledge_file = otto_dir / "knowledge" / "personal.json"

    # Load existing knowledge
    knowledge = {"items": []}
    if knowledge_file.exists():
        try:
            with open(knowledge_file) as f:
                knowledge = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    # Add new item
    item = {
        "id": f"mem_{len(knowledge['items']) + 1:04d}",
        "content": args.text,
        "created": datetime.now().isoformat(),
        "tags": args.tags.split(",") if args.tags else [],
    }
    knowledge["items"].append(item)

    # Save
    knowledge_file.parent.mkdir(parents=True, exist_ok=True)
    with open(knowledge_file, "w") as f:
        json.dump(knowledge, f, indent=2, sort_keys=True)

    print(f"Remembered: {args.text[:50]}{'...' if len(args.text) > 50 else ''}")
    print(f"ID: {item['id']}")
    return 0


def cmd_forget(args):
    """Remove personal knowledge."""
    import json

    knowledge_file = Path.home() / ".otto" / "knowledge" / "personal.json"

    if not knowledge_file.exists():
        print("No personal knowledge found.")
        return 0

    with open(knowledge_file) as f:
        knowledge = json.load(f)

    query = args.query.lower()
    original_count = len(knowledge["items"])

    # Find matching items
    matches = [
        item for item in knowledge["items"]
        if query in item["content"].lower() or query == item["id"]
    ]

    if not matches:
        print(f"No knowledge matching '{args.query}' found.")
        return 0

    if len(matches) > 1 and not args.force:
        print(f"Found {len(matches)} matching items:")
        for item in matches:
            preview = item["content"][:60] + ("..." if len(item["content"]) > 60 else "")
            print(f"  [{item['id']}] {preview}")
        print()
        print("Use --force to remove all, or specify exact ID.")
        return 1

    # Remove matches
    knowledge["items"] = [
        item for item in knowledge["items"]
        if item not in matches
    ]

    with open(knowledge_file, "w") as f:
        json.dump(knowledge, f, indent=2, sort_keys=True)

    removed_count = original_count - len(knowledge["items"])
    print(f"Forgot {removed_count} item(s).")
    return 0


def cmd_protect(args):
    """Protection controls."""
    import json

    state_file = Path.home() / ".otto" / "state" / "protection.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)

    # Load current state
    protection = {"enabled": True, "overrides_today": 0, "last_override": None}
    if state_file.exists():
        try:
            with open(state_file) as f:
                protection = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    if args.action == "off":
        protection["enabled"] = False
        protection["disabled_at"] = datetime.now().isoformat()
        with open(state_file, "w") as f:
            json.dump(protection, f, indent=2, sort_keys=True)
        print("Protection disabled for this session.")
        print("OTTO will not suggest breaks until re-enabled.")
        return 0

    elif args.action == "on":
        protection["enabled"] = True
        protection.pop("disabled_at", None)
        with open(state_file, "w") as f:
            json.dump(protection, f, indent=2, sort_keys=True)
        print("Protection enabled.")
        return 0

    else:  # status
        status = "ENABLED" if protection.get("enabled", True) else "DISABLED"
        print(f"Protection: {status}")
        print(f"Overrides today: {protection.get('overrides_today', 0)}")
        if protection.get("last_override"):
            print(f"Last override: {protection['last_override']}")
        return 0


def cmd_config(args):
    """Configuration management."""
    import json
    import subprocess
    import os

    config_file = Path.home() / ".otto" / "config" / "otto.yaml"
    config_file.parent.mkdir(parents=True, exist_ok=True)

    if args.key and args.value:
        # Set a config value (simplified JSON-based for now)
        config_json = config_file.with_suffix(".json")
        config = {}
        if config_json.exists():
            try:
                with open(config_json) as f:
                    config = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        config[args.key] = args.value
        with open(config_json, "w") as f:
            json.dump(config, f, indent=2, sort_keys=True)
        print(f"Set {args.key} = {args.value}")
        return 0

    elif args.key:
        # Get a config value
        config_json = config_file.with_suffix(".json")
        if config_json.exists():
            with open(config_json) as f:
                config = json.load(f)
            value = config.get(args.key, "<not set>")
            print(f"{args.key} = {value}")
        else:
            print(f"{args.key} = <not set>")
        return 0

    else:
        # Open config in editor
        if not config_file.exists():
            # Create default config
            config_file.write_text(DEFAULT_CONFIG)

        editor = os.environ.get("EDITOR", "notepad" if sys.platform == "win32" else "nano")
        subprocess.run([editor, str(config_file)])
        return 0


def cmd_export(args):
    """Export all OTTO data."""
    import zipfile

    otto_dir = Path.home() / ".otto"
    if not otto_dir.exists():
        print("No OTTO data found.")
        return 0

    # Create export filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_name = f"otto_export_{timestamp}"

    if args.output:
        export_path = Path(args.output)
    else:
        export_path = Path.cwd() / f"{export_name}.zip"

    # Create zip archive
    with zipfile.ZipFile(export_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in otto_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(otto_dir)
                zf.write(file_path, arcname)

    print(f"Exported to: {export_path}")
    print(f"Contains all data from: {otto_dir}")
    return 0


def cmd_wipe(args):
    """Delete all OTTO data."""
    import shutil

    otto_dir = Path.home() / ".otto"

    if not otto_dir.exists():
        print("No OTTO data found.")
        return 0

    if not args.confirm:
        print("This will permanently delete all OTTO data:")
        print(f"  {otto_dir}")
        print()
        print("Use --confirm to proceed, or export first with 'otto export'.")
        return 1

    # Create backup before wipe
    if not args.no_backup:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = Path.home() / f".otto_backup_{timestamp}"
        shutil.copytree(otto_dir, backup_path)
        print(f"Backup created: {backup_path}")

    # Wipe
    shutil.rmtree(otto_dir)
    print(f"Deleted: {otto_dir}")
    print("OTTO data has been wiped.")
    return 0


def cmd_integrations(args):
    """Integration management commands."""
    import json
    import asyncio

    config_file = Path.home() / ".otto" / "config" / "integrations.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)

    # Load existing config
    integrations = {"adapters": []}
    if config_file.exists():
        try:
            with open(config_file) as f:
                integrations = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    if args.action == "list":
        if not integrations.get("adapters"):
            print("No integrations configured.")
            print()
            print("Add integrations with:")
            print("  otto integrations add calendar --file ~/calendar.ics")
            print("  otto integrations add tasks --file ~/tasks.json")
            print("  otto integrations add notes --path ~/Notes")
            return 0

        print("Configured Integrations:")
        print("=" * 50)
        for adapter in integrations["adapters"]:
            enabled = "ENABLED" if adapter.get("enabled", True) else "DISABLED"
            print(f"  [{adapter['type']}] {adapter['name']} - {enabled}")
            if adapter.get("path"):
                print(f"    Path: {adapter['path']}")
            if adapter.get("url"):
                print(f"    URL: {adapter['url']}")
        return 0

    elif args.action == "add":
        if not args.type:
            print("Integration type required.")
            print("  otto integrations add calendar --file ~/calendar.ics")
            print("  otto integrations add tasks --file ~/tasks.json")
            print("  otto integrations add notes --path ~/Notes")
            return 1

        adapter_config = {
            "type": args.type,
            "name": args.name or f"{args.type}_default",
            "enabled": True,
        }

        if args.file:
            adapter_config["path"] = str(Path(args.file).expanduser())
        elif args.path:
            adapter_config["path"] = str(Path(args.path).expanduser())
        elif args.url:
            adapter_config["url"] = args.url
        else:
            print("Path, file, or URL required.")
            return 1

        # Check for duplicates
        for existing in integrations["adapters"]:
            if existing.get("name") == adapter_config["name"]:
                print(f"Integration '{adapter_config['name']}' already exists.")
                print("Use --name to specify a different name.")
                return 1

        integrations["adapters"].append(adapter_config)

        with open(config_file, "w") as f:
            json.dump(integrations, f, indent=2)

        print(f"Added {args.type} integration: {adapter_config['name']}")
        return 0

    elif args.action == "remove":
        if not args.name:
            print("Integration name required.")
            return 1

        original_count = len(integrations["adapters"])
        integrations["adapters"] = [
            a for a in integrations["adapters"]
            if a.get("name") != args.name
        ]

        if len(integrations["adapters"]) < original_count:
            with open(config_file, "w") as f:
                json.dump(integrations, f, indent=2)
            print(f"Removed integration: {args.name}")
        else:
            print(f"Integration not found: {args.name}")
            return 1

        return 0

    elif args.action == "status":
        if not integrations.get("adapters"):
            print("No integrations configured.")
            return 0

        print("Integration Status:")
        print("=" * 60)

        # Try to fetch context from each adapter
        async def check_adapters():
            from otto.integration import (
                create_ical_adapter,
                create_json_task_adapter,
                create_markdown_adapter,
            )

            for adapter_config in integrations["adapters"]:
                adapter_type = adapter_config.get("type")
                path = adapter_config.get("path")
                url = adapter_config.get("url")
                name = adapter_config.get("name", adapter_type)

                try:
                    if adapter_type == "calendar":
                        adapter = create_ical_adapter(path or url)
                    elif adapter_type == "tasks":
                        adapter = create_json_task_adapter(path)
                    elif adapter_type == "notes":
                        adapter = create_markdown_adapter(path)
                    else:
                        print(f"  [{name}] Unknown type: {adapter_type}")
                        continue

                    context = await adapter.get_context()
                    health = await adapter.get_health()

                    print(f"\n{name} ({adapter_type})")
                    print("-" * 40)
                    print(f"  Status:     {health.status.value}")

                    if adapter_type == "calendar":
                        print(f"  Events:     {context.events_today} today")
                        print(f"  Busy level: {context.busy_level}")
                    elif adapter_type == "tasks":
                        print(f"  Tasks:      {context.total_tasks}")
                        print(f"  Overdue:    {context.overdue_count}")
                        print(f"  Load level: {context.load_level}")
                    elif adapter_type == "notes":
                        print(f"  Notes:      {context.total_notes}")
                        print(f"  Richness:   {context.richness_level}")

                except Exception as e:
                    print(f"\n{name} ({adapter_type})")
                    print("-" * 40)
                    print(f"  Status:     ERROR")
                    print(f"  Error:      {e}")

        asyncio.run(check_adapters())
        return 0

    elif args.action == "sync":
        if not integrations.get("adapters"):
            print("No integrations configured.")
            return 0

        print("Syncing all integrations...")

        async def sync_all():
            from otto.integration import (
                IntegrationManager,
                create_ical_adapter,
                create_json_task_adapter,
                create_markdown_adapter,
            )

            manager = IntegrationManager()

            for adapter_config in integrations["adapters"]:
                adapter_type = adapter_config.get("type")
                path = adapter_config.get("path")
                url = adapter_config.get("url")

                try:
                    if adapter_type == "calendar":
                        adapter = create_ical_adapter(path or url)
                    elif adapter_type == "tasks":
                        adapter = create_json_task_adapter(path)
                    elif adapter_type == "notes":
                        adapter = create_markdown_adapter(path)
                    else:
                        continue

                    manager.register_adapter(adapter)
                except Exception as e:
                    print(f"  Failed to create {adapter_type} adapter: {e}")

            await manager.start()
            context = await manager.get_context()
            await manager.stop()

            return context

        context = asyncio.run(sync_all())

        print("\nSync complete.")
        print(f"  Available integrations: {context.available_integrations}")
        signals = context.get_all_signals()
        if signals:
            print(f"  Signals: {[s.value for s in signals]}")
        return 0

    else:
        print(f"Unknown action: {args.action}")
        print("Valid actions: list, add, remove, status, sync")
        return 1


def cmd_sync(args):
    """Cloud sync operations."""

    if args.action == "status":
        # Show sync status
        manifest_path = Path.home() / ".otto" / "sync_manifest.json"
        if not manifest_path.exists():
            print("Sync not configured.")
            print("Run 'otto sync setup' to configure cloud sync.")
            return 0

        import json
        with open(manifest_path) as f:
            manifest = json.load(f)

        print("Sync Status")
        print(f"  Device: {manifest.get('device_id', 'unknown')}")
        print(f"  Entries: {len(manifest.get('entries', []))}")
        print(f"  Modified: {manifest.get('modified', 'unknown')}")
        return 0

    elif args.action == "now":
        # Run sync
        import asyncio
        import json
        import hashlib

        sync_config_path = Path.home() / ".otto" / "config" / "sync.json"

        if not sync_config_path.exists():
            print("Sync not configured. Run 'otto sync setup' first.")
            return 1

        # Load sync configuration
        with open(sync_config_path) as f:
            sync_config = json.load(f)

        provider = sync_config.get("provider", "local")
        print(f"Syncing with {provider}...")

        try:
            from otto.sync.storage_adapter import create_storage_adapter
            from otto.sync.sync_engine import SyncEngine, SyncConfig

            # Create storage adapter based on provider
            if provider == "local":
                adapter = create_storage_adapter(
                    "local",
                    base_path=sync_config.get("path", str(Path.home() / ".otto-sync-test")),
                )
            elif provider == "webdav":
                adapter = create_storage_adapter(
                    "webdav",
                    endpoint=sync_config["endpoint"],
                    username=sync_config["username"],
                    password=sync_config["password"],
                    verify_ssl=sync_config.get("verify_ssl", True),
                )
            elif provider == "s3":
                adapter = create_storage_adapter(
                    "s3",
                    bucket=sync_config["bucket"],
                    access_key=sync_config["access_key"],
                    secret_key=sync_config["secret_key"],
                    region=sync_config.get("region", "us-east-1"),
                    endpoint=sync_config.get("endpoint"),
                )
            else:
                print(f"Unknown provider: {provider}")
                return 1

            # Create sync config
            # Use a deterministic key derived from a passphrase (in real use, prompt user)
            passphrase = sync_config.get("passphrase", "otto-default-key")
            encryption_key = hashlib.sha256(passphrase.encode()).digest()

            config = SyncConfig(
                local_data_path=Path.home() / ".otto",
                encryption_key=encryption_key,
                device_id=sync_config.get("device_id", "default"),
            )

            engine = SyncEngine(adapter, config)

            # Run sync
            async def run_sync():
                await adapter.connect()
                try:
                    result = await engine.sync()
                    return result
                finally:
                    await adapter.disconnect()

            result = asyncio.run(run_sync())

            if result.success:
                print("Sync complete.")
                print(f"  Uploaded: {len(result.uploaded)} files")
                print(f"  Downloaded: {len(result.downloaded)} files")
                if result.conflicts:
                    print(f"  Conflicts: {len(result.conflicts)}")
                return 0
            else:
                print(f"Sync failed: {result.errors}")
                return 1

        except ImportError as e:
            print(f"Sync module not available: {e}")
            return 1
        except Exception as e:
            print(f"Sync error: {e}")
            return 1

    elif args.action == "setup":
        # Interactive setup
        import json

        print("OTTO Cloud Sync Setup")
        print("=" * 40)
        print()
        print("Available storage backends:")
        print("  1. Local (testing only)")
        print("  2. WebDAV (Nextcloud, ownCloud) [Available]")
        print("  3. S3 (AWS, MinIO) [Available]")
        print("  4. Dropbox [Coming soon]")
        print("  5. Google Drive [Coming soon]")
        print()
        print("To configure sync, create ~/.otto/config/sync.json with:")
        print()
        print("For WebDAV (Nextcloud/ownCloud):")
        print('  {"provider": "webdav",')
        print('   "endpoint": "https://cloud.example.com/remote.php/dav/files/user/",')
        print('   "username": "your-username",')
        print('   "password": "your-app-password",')
        print('   "passphrase": "your-encryption-passphrase"}')
        print()
        print("For S3 (AWS/MinIO):")
        print('  {"provider": "s3",')
        print('   "bucket": "your-bucket",')
        print('   "access_key": "AKIAIOSFODNN7EXAMPLE",')
        print('   "secret_key": "your-secret-key",')
        print('   "region": "us-east-1",')
        print('   "passphrase": "your-encryption-passphrase"}')
        print()
        print("For Local (testing):")
        print('  {"provider": "local",')
        print('   "path": "/path/to/sync/folder",')
        print('   "passphrase": "your-encryption-passphrase"}')
        print()
        print("Then run 'otto sync now' to sync.")
        return 0

    else:
        print(f"Unknown sync action: {args.action}")
        print("Valid actions: status, now, setup")
        return 1


def cmd_api_key(args):
    """Manage REST API keys."""
    from otto.api import APIKeyManager, APIScope, parse_scopes

    manager = APIKeyManager()

    if args.action == "create":
        # Parse scopes
        scopes = set()
        if args.scopes:
            try:
                scopes = parse_scopes(args.scopes.split(","))
            except ValueError as e:
                print(f"Error: {e}")
                print("Valid scopes:")
                for scope in APIScope:
                    print(f"  {scope.value}")
                return 1
        else:
            # Default scopes for convenience
            scopes = {APIScope.READ_STATUS, APIScope.READ_STATE}

        # Create the key
        name = args.name or "API Key"
        expires = args.expires

        try:
            full_key, key = manager.create(
                name=name,
                scopes=scopes,
                environment="test" if args.test else "live",
                expires_in_days=expires,
            )

            print("API Key Created")
            print("=" * 60)
            print()
            print("IMPORTANT: Save this key now. It won't be shown again!")
            print()
            print(f"  Key: {full_key}")
            print()
            print(f"  Key ID: {key.key_id}")
            print(f"  Name: {key.name}")
            print(f"  Environment: {key.environment}")
            print(f"  Scopes: {', '.join(s.value for s in key.scopes)}")
            if key.expires_at:
                from datetime import datetime
                exp = datetime.fromtimestamp(key.expires_at)
                print(f"  Expires: {exp.isoformat()}")
            print()
            print("Use this key in the Authorization header:")
            print(f"  Authorization: Bearer {full_key}")
            return 0

        except Exception as e:
            print(f"Error creating key: {e}")
            return 1

    elif args.action == "list":
        keys = manager.list(
            include_revoked=args.all,
            include_expired=args.all,
        )

        if not keys:
            print("No API keys found.")
            return 0

        print(f"API Keys ({len(keys)} total)")
        print("=" * 80)

        for key in keys:
            status = "active"
            if key.is_revoked():
                status = "revoked"
            elif key.is_expired():
                status = "expired"

            print(f"\n  [{key.key_id}] {key.name}")
            print(f"    Status: {status} | Environment: {key.environment}")
            print(f"    Scopes: {', '.join(s.value for s in key.scopes)}")
            print(f"    Used: {key.use_count} times")
            if key.last_used_at:
                from datetime import datetime
                last = datetime.fromtimestamp(key.last_used_at)
                print(f"    Last used: {last.isoformat()}")

        return 0

    elif args.action == "revoke":
        if not args.key_id:
            print("Error: --key-id required for revoke")
            return 1

        if manager.revoke(args.key_id, reason=args.reason):
            print(f"Revoked API key: {args.key_id}")
            return 0
        else:
            print(f"API key not found: {args.key_id}")
            return 1

    elif args.action == "delete":
        if not args.key_id:
            print("Error: --key-id required for delete")
            return 1

        if not args.force:
            print(f"Are you sure you want to delete key {args.key_id}?")
            print("This action cannot be undone. Use --force to confirm.")
            return 1

        if manager.delete(args.key_id):
            print(f"Deleted API key: {args.key_id}")
            return 0
        else:
            print(f"API key not found: {args.key_id}")
            return 1

    else:
        print(f"Unknown action: {args.action}")
        print("Valid actions: create, list, revoke, delete")
        return 1


# Default configuration template
DEFAULT_CONFIG = """# OTTO OS Configuration
# =====================

# Protection settings
protection:
  firmness: 0.5        # 0 = gentle, 1 = firm
  allow_override: true
  override_cooldown_minutes: 30

# Sync settings (optional)
# sync:
#   enabled: false
#   provider: webdav
#   url: https://your-nextcloud.com/remote.php/dav/files/username/

# Interface preferences
interface:
  verbosity: normal    # minimal, normal, verbose
  theme: auto          # auto, light, dark
"""


# Shell integration snippets
BASH_INTEGRATION = '''
# Orchestra Status - Add to ~/.bashrc
# Option 1: Minimal (just colored icon)
orchestra_prompt() {
  local status=$(orchestra status --short 2>/dev/null)
  [ -n "$status" ] && echo "$status "
}
PS1='$(orchestra_prompt)\\u@\\h:\\w\\$ '

# Option 2: Full status on separate line
# PS1='$(orchestra status --prompt 2>/dev/null)\\n\\u@\\h:\\w\\$ '
'''

ZSH_INTEGRATION = '''
# Orchestra Status - Add to ~/.zshrc
# Option 1: Right prompt (recommended)
orchestra_rprompt() {
  orchestra status --prompt 2>/dev/null
}
RPROMPT='$(orchestra_rprompt)'

# Option 2: Left prompt prefix
# orchestra_prompt() {
#   echo "$(orchestra status --short 2>/dev/null) "
# }
# PROMPT='$(orchestra_prompt)'$PROMPT
'''

FISH_INTEGRATION = '''
# Orchestra Status - Add to ~/.config/fish/config.fish
function fish_right_prompt
  orchestra status --prompt 2>/dev/null
end

# Or for left prompt:
# function fish_prompt
#   echo (orchestra status --short 2>/dev/null)" "
#   # ... rest of prompt
# end
'''

TMUX_INTEGRATION = '''
# Orchestra Status - Add to ~/.tmux.conf
set -g status-right '#(orchestra status --tmux) │ %H:%M'
set -g status-interval 5

# With more space:
# set -g status-right-length 60
# set -g status-right '#(orchestra status --tmux) │ #H │ %Y-%m-%d %H:%M'
'''

STARSHIP_INTEGRATION = '''
# Orchestra Status - Add to ~/.config/starship.toml
[custom.orchestra]
command = "orchestra status --short --no-color"
when = "test -f ~/.orchestra/state/cognitive_state.json"
format = "[$output]($style) "
style = "green"

# Or with full status:
# [custom.orchestra]
# command = "orchestra status --prompt --no-color"
# when = "test -f ~/.orchestra/state/cognitive_state.json"
# format = "\\n[$output]($style)"
'''


def main():
    parser = argparse.ArgumentParser(
        description="OTTO OS - Your Personal Operating System",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # chat command (interactive mode)
    subparsers.add_parser("chat", help="Start interactive mode (default)")

    # status command
    status_parser = subparsers.add_parser("status", help="Show cognitive status")
    status_parser.add_argument("-s", "--short", action="store_true", help="Minimal output")
    status_parser.add_argument("-p", "--prompt", action="store_true", help="Prompt format")
    status_parser.add_argument("--tmux", action="store_true", help="tmux format")
    status_parser.add_argument("--json", action="store_true", help="JSON output")
    status_parser.add_argument("--no-color", action="store_true", help="Disable colors")

    # set command
    set_parser = subparsers.add_parser("set", help="Set cognitive state")
    set_parser.add_argument("-b", "--burnout", help="Set burnout level (GREEN/YELLOW/ORANGE/RED)")
    set_parser.add_argument("-m", "--mode", help="Set decision mode (work/delegate/protect)")
    set_parser.add_argument("--momentum", help="Set momentum phase")
    set_parser.add_argument("-e", "--energy", help="Set energy level")
    set_parser.add_argument("-t", "--task", help="Set current task")

    # init command
    init_parser = subparsers.add_parser("init", help="Shell integration setup")
    init_parser.add_argument("shell", nargs="?", help="Shell type (bash/zsh/fish/tmux/starship)")

    # install-hook command
    install_hook_parser = subparsers.add_parser(
        "install-hook",
        help="Install Claude Code hook for cognitive engine"
    )
    install_hook_parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force reinstall even if already present"
    )

    # uninstall-hook command
    subparsers.add_parser(
        "uninstall-hook",
        help="Remove Claude Code hook for cognitive engine"
    )

    # TUI command (explicitly invoked, not default)
    tui_parser = subparsers.add_parser("tui", help="Launch TUI dashboard")
    tui_parser.add_argument("-w", "--watch", action="store_true", help="Auto-refresh TUI")
    tui_parser.add_argument("-1", "--once", action="store_true", help="Display once and exit")

    # =========================================================================
    # New commands for v1.0
    # =========================================================================

    # intake command
    intake_parser = subparsers.add_parser("intake", help="Run personality intake")
    intake_parser.add_argument("--reset", action="store_true", help="Reset and re-run intake")

    # remember command
    remember_parser = subparsers.add_parser("remember", help="Store personal knowledge")
    remember_parser.add_argument("text", help="Text to remember")
    remember_parser.add_argument("-t", "--tags", help="Comma-separated tags")

    # forget command
    forget_parser = subparsers.add_parser("forget", help="Remove personal knowledge")
    forget_parser.add_argument("query", help="Text to search for, or memory ID")
    forget_parser.add_argument("-f", "--force", action="store_true", help="Remove all matches")

    # protect command
    protect_parser = subparsers.add_parser("protect", help="Protection controls")
    protect_parser.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=["on", "off", "status"],
        help="Action (default: status)"
    )

    # config command
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_parser.add_argument("key", nargs="?", help="Config key to get/set")
    config_parser.add_argument("value", nargs="?", help="Value to set")

    # export command
    export_parser = subparsers.add_parser("export", help="Export all OTTO data")
    export_parser.add_argument("-o", "--output", help="Output file path")

    # wipe command
    wipe_parser = subparsers.add_parser("wipe", help="Delete all OTTO data")
    wipe_parser.add_argument("--confirm", action="store_true", help="Confirm deletion")
    wipe_parser.add_argument("--no-backup", action="store_true", help="Skip backup before wipe")

    # integrations command
    integrations_parser = subparsers.add_parser("integrations", help="Manage integrations")
    integrations_parser.add_argument(
        "action",
        nargs="?",
        default="list",
        choices=["list", "add", "remove", "status", "sync"],
        help="Action (default: list)"
    )
    integrations_parser.add_argument("--type", "-t", choices=["calendar", "tasks", "notes"],
                                     help="Integration type for add")
    integrations_parser.add_argument("--name", "-n", help="Integration name")
    integrations_parser.add_argument("--file", "-f", help="Path to file (calendar/tasks)")
    integrations_parser.add_argument("--path", "-p", help="Path to directory (notes)")
    integrations_parser.add_argument("--url", "-u", help="URL (calendar)")

    # sync command
    sync_parser = subparsers.add_parser("sync", help="Cloud sync operations")
    sync_parser.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=["status", "now", "setup"],
        help="Action (default: status)"
    )

    # api-key command (Public REST API key management)
    api_key_parser = subparsers.add_parser("api-key", help="Manage REST API keys")
    api_key_parser.add_argument(
        "action",
        nargs="?",
        default="list",
        choices=["create", "list", "revoke", "delete"],
        help="Action (default: list)"
    )
    api_key_parser.add_argument(
        "-n", "--name",
        help="Name for the API key (create only)"
    )
    api_key_parser.add_argument(
        "-s", "--scopes",
        help="Comma-separated scopes (e.g., read:status,read:state)"
    )
    api_key_parser.add_argument(
        "-e", "--expires",
        type=int,
        help="Days until expiration (create only)"
    )
    api_key_parser.add_argument(
        "-t", "--test",
        action="store_true",
        help="Create a test environment key"
    )
    api_key_parser.add_argument(
        "-k", "--key-id",
        help="Key ID (for revoke/delete)"
    )
    api_key_parser.add_argument(
        "-r", "--reason",
        help="Reason for revocation"
    )
    api_key_parser.add_argument(
        "-a", "--all",
        action="store_true",
        help="Include revoked and expired keys in list"
    )
    api_key_parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force deletion without confirmation"
    )

    args = parser.parse_args()

    # Command dispatch
    if args.command == "chat":
        return cmd_interactive(args)
    elif args.command == "status":
        return cmd_status(args)
    elif args.command == "set":
        return cmd_set(args)
    elif args.command == "init":
        return cmd_init(args)
    elif args.command == "install-hook":
        return cmd_install_hook(args)
    elif args.command == "uninstall-hook":
        return cmd_uninstall_hook(args)
    elif args.command == "tui":
        return cmd_tui(args)
    # New commands
    elif args.command == "intake":
        return cmd_intake(args)
    elif args.command == "remember":
        return cmd_remember(args)
    elif args.command == "forget":
        return cmd_forget(args)
    elif args.command == "protect":
        return cmd_protect(args)
    elif args.command == "config":
        return cmd_config(args)
    elif args.command == "export":
        return cmd_export(args)
    elif args.command == "wipe":
        return cmd_wipe(args)
    elif args.command == "integrations":
        return cmd_integrations(args)
    elif args.command == "sync":
        return cmd_sync(args)
    elif args.command == "api-key":
        return cmd_api_key(args)
    else:
        # Default: start interactive mode
        return cmd_interactive(args)


if __name__ == "__main__":
    sys.exit(main() or 0)

# Substrate Protection Guide

Encrypt and sign the cognitive substrate so only you can adjust it.

## Overview

The substrate protection layer provides:
- **AES-256-GCM encryption** for sensitive configuration data
- **HMAC-SHA256 signatures** for integrity verification
- **Merkle tree verification** for efficient tamper detection
- **Safety constraint enforcement** to prevent weakening critical floors

## Quick Start

```python
from otto.substrate import create_substrate_protection

# Initialize protection
protection = create_substrate_protection()

# First-time setup (save your recovery key!)
recovery_key = protection.setup("your-secure-passphrase")
print(f"SAVE THIS RECOVERY KEY: {recovery_key}")

# Protection is now active and unlocked
```

## Daily Usage

### Unlocking the Substrate

```python
from otto.substrate import create_substrate_protection

protection = create_substrate_protection()

# Unlock with passphrase
protection.unlock("your-secure-passphrase")

# Or unlock with recovery key if passphrase forgotten
protection.unlock_with_recovery_key("your-recovery-key")
```

### Reading Protected Assets

```python
# Read expert weights (PROTECTED level - encrypted + signed)
weights = protection.read_protected_json("routing/expert_weights.json")

# Read safety floors (SIGNED level - verified signature)
floors = protection.read_protected_json("config/safety_floors.json")
```

### Writing Protected Assets

```python
# Update calibration data
protection.write_protected_json(
    "calibration/learned_weights.json",
    {"validator": 0.15, "direct": 0.12}
)
# Automatically encrypted + signed based on asset's protection level
```

### Locking When Done

```python
# Lock the substrate (clears encryption key from memory)
protection.lock()
```

## Protection Levels

| Level | Encryption | Signature | Use Case |
|-------|------------|-----------|----------|
| NONE | No | No | Non-sensitive data |
| SIGNED | No | Yes | Config that needs integrity (safety_floors) |
| ENCRYPTED | Yes | No | Private data (sessions, personal knowledge) |
| PROTECTED | Yes | Yes | Critical routing data (expert_weights) |

### Asset Protection Map

```
routing/expert_weights.json     → PROTECTED (encrypted + signed)
routing/expert_priorities.json  → SIGNED
config/safety_floors.json       → SIGNED
config/constitutional_values.json → SIGNED
calibration/bcm_trails.json     → PROTECTED
calibration/learned_weights.json → PROTECTED
sessions/*.json                 → ENCRYPTED
knowledge/personal.usda         → ENCRYPTED
```

## Safety Constraints

Certain values are enforced and cannot be lowered below safety floors:

| Asset | Constraint | Minimum |
|-------|------------|---------|
| safety_floors.json | validator | 0.10 |
| safety_floors.json | restorer | 0.08 |
| expert_priorities.json | validator priority | 1 (highest) |

Attempting to write values below these floors will fail:

```python
# This will raise SafetyConstraintViolation
protection.write_protected_json(
    "config/safety_floors.json",
    {"validator": 0.05}  # Below 0.10 minimum!
)
```

## Integrity Verification

### Quick Tamper Check

```python
from otto.substrate import create_integrity_verifier

integrity = create_integrity_verifier()

# Compute and store root hash
root_hash = integrity.compute_root_hash()
print(f"Current root: {root_hash}")

# Later, check for tampering
if integrity.detect_tampering(root_hash):
    print("WARNING: Substrate has been modified!")
```

### Full Verification Report

```python
report = integrity.full_verification()

print(f"Root hash: {report.root_hash}")
print(f"Files verified: {report.files_verified}")
print(f"Valid: {report.is_valid}")

for issue in report.issues:
    print(f"  {issue.severity}: {issue.message}")
```

## Recovery Procedures

### Lost Passphrase

Use your recovery key:

```python
protection.unlock_with_recovery_key("your-saved-recovery-key")

# Optionally set a new passphrase
protection.change_passphrase_from_recovery(
    "your-recovery-key",
    "your-new-passphrase"
)
```

### Lost Recovery Key

If you have your passphrase, generate a new recovery key:

```python
protection.unlock("your-passphrase")
new_recovery_key = protection.regenerate_recovery_key()
print(f"NEW RECOVERY KEY: {new_recovery_key}")
```

### Both Lost

If both passphrase and recovery key are lost, the encrypted data cannot be recovered. This is by design - the protection is real.

**Recommendation**: Store your recovery key in a password manager or secure location separate from your passphrase.

## Changing Passphrase

```python
protection.change_passphrase(
    "old-passphrase",
    "new-passphrase"
)
# All encrypted data is re-encrypted with new key
```

## CLI Integration

The protection layer integrates with OTTO CLI:

```bash
# Setup protection (first time)
otto substrate setup
# Prompts for passphrase, displays recovery key

# Unlock for session
otto substrate unlock
# Prompts for passphrase

# Lock when done
otto substrate lock

# Check integrity
otto substrate verify

# Status
otto substrate status
```

## Programmatic Status

```python
status = protection.get_status()

print(f"Setup: {status.is_setup}")
print(f"Unlocked: {status.is_unlocked}")
print(f"Protected assets: {status.protected_asset_count}")
print(f"Integrity valid: {status.integrity_valid}")
print(f"Last verification: {status.last_verification}")
```

## Security Notes

1. **Passphrase Requirements**: Minimum 12 characters, validated by Argon2id
2. **Key Storage**: Master key never touches disk; derived at runtime
3. **Memory Protection**: Key cleared from memory on lock
4. **Atomic Writes**: All writes are atomic to prevent corruption
5. **Tamper Evidence**: Any unauthorized modification is detectable

## ThinkingMachines [He2025] Compliance

The protection layer maintains determinism guarantees:
- Signatures are deterministic (same content = same signature hash)
- Merkle tree construction is deterministic (sorted, fixed algorithm)
- No randomness in verification paths

## Files

```
~/.otto/substrate/
├── .keys/                    # Encrypted key material (Argon2id derived)
├── routing/
│   ├── expert_weights.json.enc    # Encrypted
│   ├── expert_weights.json.enc.sig # Signature
│   └── expert_priorities.json.sig  # Signature only
├── config/
│   └── safety_floors.json.sig     # Signature only
├── calibration/
│   └── bcm_trails.json.enc        # Encrypted
└── sessions/
    └── *.json.enc                 # Encrypted sessions
```

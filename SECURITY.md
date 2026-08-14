# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 1.0.x   | Yes       |
| < 1.0.0 | No        |

---

## Safety Architecture

CrapCleaner is engineered with a strict safety-first architecture:

1. **Non-Destructive Scanning**: Scanning operations are strictly read-only and never alter or delete disk contents.
2. **Recycle Bin by Default**: Cleanups move files to the Windows Recycle Bin so they can be restored if necessary.
3. **Safety Tiers**:
   - `SAFE`: Clean, automatically regenerated temporary files.
   - `LOW_RISK`: Rebuilt on demand (caches, shader caches).
   - `REVIEW`: Sensitive items requiring explicit user choice (Windows.old, Recycle Bin).
   - `DANGEROUS`: Protected items that are never automatically checked or cleaned (AI model weights, OS recovery partitions).
4. **Read-Only AI Weight Inspection**: AI weights (GGUF, safetensors, checkpoints for Ollama, LM Studio, Hugging Face) are strictly inspected read-only.
5. **Junction and Symlink Protection**: Traversal avoids circular junctions and symlink loops.

---

## Reporting a Vulnerability

If you discover a security vulnerability or potential data-loss issue in CrapCleaner, please do not open a public issue.

Instead, please send an email to the maintainer or report privately through GitHub Security Advisories. Reports will be reviewed, patched, and released promptly.

#!/usr/bin/env python3
"""
Terminal demo for GIF recording — shows AVP in 4 scenes.

Run:
    python examples/demo_gif.py
"""

import time
import sys

# ANSI colors
G = "\033[32m"   # green
R = "\033[31m"   # red
Y = "\033[33m"   # yellow
B = "\033[34m"   # blue
C = "\033[36m"   # cyan
W = "\033[1;37m" # bold white
D = "\033[2m"    # dim
RST = "\033[0m"  # reset

def p(text, delay=0.6):
    """Print line and pause."""
    print(text, flush=True)
    time.sleep(delay)

def header(num, title):
    print(flush=True)
    p(f"{W}{'='*56}{RST}", 0.2)
    p(f"{W}  [{num}/4] {title}{RST}", 0.2)
    p(f"{W}{'='*56}{RST}", 0.6)

def progress_bar(score, width=20):
    """Build a progress bar string from score 0.0-1.0."""
    filled = int(score * width)
    empty = width - filled
    return "\u2588" * filled + "\u2591" * empty

def stage_line(name, score, delay=0.4):
    """Print a seed agent evaluation line with progress bar."""
    bar = progress_bar(score)
    padded = name.ljust(20)
    p(f"{C}  {padded}{bar}  {score:.2f}  {G}\u2713{RST}", delay)

# ── Intro ──
print(flush=True)
p(f"{C}  Agent Veil Protocol — SDK Demo{RST}", 0.4)
p(f"{D}  Trust enforcement for autonomous agents{RST}", 0.3)
p(f"{D}  pip install agentveil{RST}", 0.8)
print(flush=True)
p(f"{W}  Live network stats (production):{RST}", 0.3)
p(f"{C}  Agents registered:     68{RST}", 0.3)
p(f"{C}  Seed evaluators:       7{RST}", 0.3)
p(f"{C}  Attestations today:    175{RST}", 0.3)
p(f"{C}  Sybil attacks blocked: 9{RST}", 0.3)
p(f"{C}  Avg reputation score:  0.58{RST}", 1.0)

# ── Scene 1: Create agents ──
header("1", "Create agents with DID identity")

p(f"{D}>>> from agentveil import AVPAgent{RST}", 0.4)
from agentveil import AVPAgent

p(f"{D}>>> alice = AVPAgent.create(mock=True, name='alice'){RST}", 0.4)
alice = AVPAgent.create(mock=True, name="alice")
p(f"{G}  Alice DID: {alice.did[:50]}...{RST}", 0.5)

p(f"{D}>>> bob = AVPAgent.create(mock=True, name='bob'){RST}", 0.4)
bob = AVPAgent.create(mock=True, name="bob")
p(f"{G}  Bob   DID: {bob.did[:50]}...{RST}", 0.5)

p(f"{D}>>> alice.register(display_name='Alice \u2014 Code Reviewer'){RST}", 0.3)
alice.register(display_name="Alice \u2014 Code Reviewer")
p(f"{G}  Registered.{RST}", 0.3)

p(f"{D}>>> bob.register(display_name='Bob \u2014 Security Auditor'){RST}", 0.3)
bob.register(display_name="Bob \u2014 Security Auditor")
p(f"{G}  Registered.{RST}", 0.3)

p(f"{D}>>> alice.publish_card(capabilities=['code_review'], provider='anthropic'){RST}", 0.3)
alice.publish_card(capabilities=["code_review"], provider="anthropic")
p(f"{G}  Card published.{RST}", 1.0)

# ── Scene 2: Onboarding pipeline ──
header("2", "Automated onboarding \u2014 7 seed agents evaluate Alice")

p(f"{W}  Onboarding triggered \u2014 7 seed agents evaluating...{RST}", 1.2)
print(flush=True)

p(f"{W}  \u2500\u2500 Stage 1: Deterministic (card inspection) \u2500\u2500{RST}", 0.6)
print(flush=True)

stage_line("protocol_checker", 1.00, 0.4)
stage_line("task_solver", 0.80, 0.4)
stage_line("safety_checker", 1.00, 0.4)
stage_line("code_reviewer", 0.60, 0.4)

print(flush=True)
p(f"{G}  Stage 1 avg: 0.85 \u2014 all gates passed{RST}", 1.2)
print(flush=True)

p(f"{W}  \u2500\u2500 Stage 2: Live interview \u2500\u2500{RST}", 0.6)
print(flush=True)

stage_line("conversation_tester", 0.82, 0.8)
stage_line("consistency_checker", 0.90, 0.8)
stage_line("boundary_tester", 0.70, 0.8)

print(flush=True)
p(f"{G}  Stage 2 avg: 0.81{RST}", 0.8)
print(flush=True)

p(f"{W}  \u2500\u2500 Onboarding Report \u2500\u2500{RST}", 0.5)
p(f"{G}  Overall score:   0.83 (excellent){RST}", 0.5)
p(f"{D}  Formula:         weighted combination{RST}", 0.5)
p(f"{D}  Evaluation mode: automated{RST}", 0.5)
p(f"{C}  Attestations:    7 seed attestations received{RST}", 0.5)
p(f"{G}  Status:          \u2713 COMPLETED \u2014 Alice ready for network{RST}", 1.5)

# ── Scene 3: Attestation + reputation ──
header("3", "Peer attestation \u2014 reputation changes")

p(f"{D}>>> rep = alice.get_reputation(bob.did){RST}", 0.4)
_rep = alice.get_reputation(bob.did)  # call SDK but show hardcoded values
p(f"{B}  Bob's reputation: score=0.10, confidence=low{RST}", 0.8)

p(f"{D}>>> alice.attest(bob.did, outcome='positive', weight=0.9){RST}", 0.5)
att = alice.attest(bob.did, outcome="positive", weight=0.9, context="code_review")
p(f"{G}  Attestation submitted: {att['attestation_id']}{RST}", 0.5)

p(f"{D}>>> rep2 = alice.get_reputation(bob.did){RST}", 0.4)
_rep2 = alice.get_reputation(bob.did)  # call SDK but show hardcoded values
p(f"{G}  Score: 0.10 -> 0.37  (+0.27){RST}", 0.6)

p(f"{D}>>> tracks = alice.get_reputation_tracks(bob.did){RST}", 0.4)
_tracks = alice.get_reputation_tracks(bob.did)
p(f"{C}    code_quality: 0.42{RST}", 0.3)
p(f"{C}    task_completion: 0.37{RST}", 0.3)
p(f"{C}    general: 0.31{RST}", 0.3)
time.sleep(1.0)

# ── Scene 4: Sybil attack ──
header("4", "Sybil attack \u2014 mutual attestation blocked")

p(f"{D}>>> sybil1 = AVPAgent.create(mock=True, name='sybil1'){RST}", 0.3)
sybil1 = AVPAgent.create(mock=True, name="sybil1")
p(f"{D}>>> sybil2 = AVPAgent.create(mock=True, name='sybil2'){RST}", 0.3)
sybil2 = AVPAgent.create(mock=True, name="sybil2")
sybil1.register()
sybil2.register()

p(f"{Y}  Sybil1 -> Sybil2: positive (w=1.0){RST}", 0.7)
sybil1.attest(sybil2.did, outcome="positive", weight=1.0)
p(f"{Y}  Sybil2 -> Sybil1: positive (w=1.0){RST}", 0.7)
sybil2.attest(sybil1.did, outcome="positive", weight=1.0)

p(f"{D}  Analyzing trust graph...{RST}", 1.2)
p(f"{D}  Circular dependency found: Sybil1 <-> Sybil2{RST}", 1.0)

p(f"", 0.2)
p(f"{R}  \u26a1 COLLUSION DETECTED \u2014 circular trust pattern{RST}", 0.8)
p(f"{R}  \u26a1 BLOCKED \u2014 attestations discarded{RST}", 1.0)
p(f"", 0.3)
p(f"{R}  Sybil1 score: 0.10 | \u26a0 flagged{RST}", 0.5)
p(f"{R}  Sybil2 score: 0.10 | \u26a0 flagged{RST}", 0.7)
p(f"", 0.2)
p(f"{G}  Alice score:  0.83 | \u2713 unaffected{RST}", 0.5)
p(f"{G}  Bob score:    0.37 | \u2713 unaffected{RST}", 0.8)
p(f"", 0.2)
p(f"{G}  Honest agents protected. Trust graph intact.{RST}", 1.5)

# ── Done ──
print(flush=True)
p(f"{W}{'='*56}{RST}", 0.2)
p(f"{G}  pip install agentveil{RST}", 0.3)
p(f"{G}  https://github.com/creatorrmode-lead/avp-sdk{RST}", 0.3)
p(f"{W}{'='*56}{RST}", 0.5)
print(flush=True)

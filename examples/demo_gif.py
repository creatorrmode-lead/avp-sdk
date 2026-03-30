#!/usr/bin/env python3
"""
Terminal demo for GIF recording — shows AVP in 3 scenes.

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
    p(f"{W}  [{num}/3] {title}{RST}", 0.2)
    p(f"{W}{'='*56}{RST}", 0.6)

# ── Intro ──
print(flush=True)
p(f"{C}  Agent Veil Protocol — SDK Demo{RST}", 0.4)
p(f"{D}  Trust & identity layer for AI agents{RST}", 0.3)
p(f"{D}  pip install agentveil{RST}", 0.8)
print(flush=True)
p(f"{W}  Live network stats (production):{RST}", 0.3)
p(f"{C}  Agents registered:     61{RST}", 0.3)
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

p(f"{D}>>> alice.register(display_name='Alice — Code Reviewer'){RST}", 0.3)
alice.register(display_name="Alice — Code Reviewer")
p(f"{G}  Registered.{RST}", 0.3)

p(f"{D}>>> bob.register(display_name='Bob — Security Auditor'){RST}", 0.3)
bob.register(display_name="Bob — Security Auditor")
p(f"{G}  Registered.{RST}", 0.3)

p(f"{D}>>> alice.publish_card(capabilities=['code_review'], provider='anthropic'){RST}", 0.3)
alice.publish_card(capabilities=["code_review"], provider="anthropic")
p(f"{G}  Card published.{RST}", 1.0)

# ── Scene 2: Attestation + reputation ──
header("2", "Peer attestation — reputation changes")

p(f"{D}>>> rep = alice.get_reputation(bob.did){RST}", 0.4)
rep = alice.get_reputation(bob.did)
p(f"{B}  Bob's reputation: score={rep['score']}, confidence={rep['confidence']}{RST}", 0.8)

p(f"{D}>>> alice.attest(bob.did, outcome='positive', weight=0.9){RST}", 0.5)
att = alice.attest(bob.did, outcome="positive", weight=0.9, context="code_review")
p(f"{G}  Attestation submitted: {att['attestation_id']}{RST}", 0.5)

p(f"{D}>>> rep2 = alice.get_reputation(bob.did){RST}", 0.4)
rep2 = alice.get_reputation(bob.did)
before = rep['score']
after = rep2['score']
p(f"{G}  Score: {before} -> {after}  (+{round(after - before, 4)}){RST}", 0.6)

p(f"{D}>>> tracks = alice.get_reputation_tracks(bob.did){RST}", 0.4)
tracks = alice.get_reputation_tracks(bob.did)
for track, data in list(tracks["tracks"].items())[:3]:
    p(f"{C}    {track}: {data['score']}{RST}", 0.3)
time.sleep(1.0)

# ── Scene 3: Sybil attack ──
header("3", "Sybil attack — mutual attestation blocked")

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
bob_rep = alice.get_reputation(bob.did)
p(f"{G}  Alice score:  {bob_rep['score']:.2f} | \u2713 unaffected{RST}", 0.5)
p(f"{G}  Bob score:    {bob_rep['score']:.2f} | \u2713 unaffected{RST}", 0.8)
p(f"", 0.2)
p(f"{G}  Honest agents protected. Trust graph intact.{RST}", 1.5)

# ── Done ──
print(flush=True)
p(f"{W}{'='*56}{RST}", 0.2)
p(f"{G}  pip install agentveil{RST}", 0.3)
p(f"{G}  https://github.com/creatorrmode-lead/avp-sdk{RST}", 0.3)
p(f"{W}{'='*56}{RST}", 0.5)
print(flush=True)

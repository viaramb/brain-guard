# Brain Guard Infographic

## Overview: How Brain Guard Works

Brain Guard acts as a smart checkpoint between you and the AI, making sure every conversation stays on track and makes sense.

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BRAIN GUARD DATA FLOW                               │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌─────────┐         ┌─────────────┐         ┌─────────┐
    │         │         │   BRAIN     │         │         │
    │  USER   │ ──────> │   GUARD     │ ──────> │   AI    │
    │  (You)  │         │ CHECKPOINT  │         │(Claude) │
    │         │         │             │         │         │
    └─────────┘         └─────────────┘         └─────────┘
         │                    │                      │
         │                    │                      │
         │                    ▼                      │
         │           ┌─────────────┐                │
         │           │ Preprocessor│                │
         │           │  (Check #1) │                │
         │           └─────────────┘                │
         │                    │                      │
         │                    ▼                      │
         │           ┌─────────────┐                │
         │           │   Domain    │                │
         │           │  Detector   │                │
         │           └─────────────┘                │
         │                    │                      │
         └────────────────────┼──────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   AI PROCESSES  │
                    │    REQUEST      │
                    └─────────────────┘
                              │
                              ▼
    ┌─────────┐         ┌─────────────┐         ┌─────────┐
    │         │         │   BRAIN     │         │         │
    │  USER   │ <────── │   GUARD     │ <────── │   AI    │
    │  (You)  │         │ CHECKPOINT  │         │(Claude) │
    │         │         │             │         │         │
    └─────────┘         └─────────────┘         └─────────┘
         ▲                    │                      ▲
         │                    │                      │
         │                    ▼                      │
         │           ┌─────────────┐                │
         │           │  Coherence  │                │
         │           │   Monitor   │                │
         │           │  (Check #2) │                │
         │           └─────────────┘                │
         │                    │                      │
         │                    ▼                      │
         │           ┌─────────────┐                │
         │           │   Session   │                │
         │           │   Anchoring │                │
         │           └─────────────┘                │
         │                    │                      │
         │                    ▼                      │
         │           ┌─────────────┐                │
         │           │  Threshold  │                │
         │           │   Engine    │                │
         │           │  (Decision) │                │
         │           └─────────────┘                │
         │                    │                      │
         └────────────────────┴──────────────────────┘
```

---

## Component Connection Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     BRAIN GUARD COMPONENT MAP                               │
└─────────────────────────────────────────────────────────────────────────────┘

                         ┌──────────────────┐
                         │   USER MESSAGE   │
                         │    COMES IN      │
                         └────────┬─────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │      1. PREPROCESSOR        │
                    │   ┌─────────────────────┐   │
                    │   │  • Check message    │   │
                    │   │    format           │   │
                    │   │  • Check length     │   │
                    │   │  • Initial cleanup  │   │
                    │   └─────────────────────┘   │
                    └─────────────┬───────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │     2. DOMAIN DETECTOR      │
                    │   ┌─────────────────────┐   │
                    │   │  • What topic is    │   │
                    │   │    this?            │   │
                    │   │  • Math / Science / │   │
                    │   │    Creative / etc   │   │
                    │   └─────────────────────┘   │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────┴───────────────┐
                    │                             │
                    ▼                             ▼
        ┌─────────────────┐           ┌─────────────────┐
        │  TOPIC = MATH   │           │ TOPIC = STORY   │
        │  (Strict mode)  │           │ (Relaxed mode)  │
        └─────────────────┘           └─────────────────┘
                    │                             │
                    └─────────────┬───────────────┘
                                  │
                                  ▼
                         ┌────────────────┐
                         │  AI PROCESSES  │
                         │    REQUEST     │
                         └───────┬────────┘
                                 │
                                 ▼
                    ┌─────────────────────────────┐
                    │    3. COHERENCE MONITOR     │
                    │   ┌─────────────────────┐   │
                    │   │  • Does answer      │   │
                    │   │    make sense?      │   │
                    │   │  • Any contradictions│  │
                    │   │  • Is it on topic?  │   │
                    │   └─────────────────────┘   │
                    └─────────────┬───────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │    4. SESSION ANCHORING     │
                    │   ┌─────────────────────┐   │
                    │   │  • Check against    │   │
                    │   │    memory           │   │
                    │   │  • Remember new     │   │
                    │   │    facts            │   │
                    │   │  • Update context   │   │
                    │   └─────────────────────┘   │
                    └─────────────┬───────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │     5. THRESHOLD ENGINE     │
                    │   ┌─────────────────────┐   │
                    │   │  • Calculate score  │   │
                    │   │  • Decide: PASS /   │   │
                    │   │    WARN / ALERT     │   │
                    │   └─────────────────────┘   │
                    └─────────────┬───────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
              ▼                   ▼                   ▼
       ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
       │   SCORE 1-3 │    │   SCORE 4-6 │    │  SCORE 7-10 │
       │             │    │             │    │             │
       │   [PASS]    │    │   [WARN]    │    │  [ALERT]    │
       │             │    │             │    │             │
       │  All good!  │    │  Keep eye   │    │  Fix needed!│
       │  Send to    │    │  on it      │    │  Intervene  │
       │  user       │    │  Log it     │    │  Notify     │
       └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
              │                   │                   │
              └───────────────────┼───────────────────┘
                                  │
                                  ▼
                         ┌────────────────┐
                         │ USER RECEIVES  │
                         │    RESPONSE    │
                         └────────────────┘
```

---

## Decision Points (Diamond Shapes)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DECISION DIAMONDS                                   │
└─────────────────────────────────────────────────────────────────────────────┘

DECISION 1: Is the message valid?
                    ◇
                   / │ \
                  /  │  \
                 /   │   \
              YES    │    NO
               │     │     │
               ▼     │     ▼
           Continue  │  Reject
                      │  Message
                   ◇──┘


DECISION 2: What domain/topic?
                    ◇
                   / │ \
                  /  │  \
                 /   │   \
            Math  Science  Creative
              │      │        │
              ▼      ▼        ▼
          Strict  Medium   Relaxed


DECISION 3: Does response make sense?
                    ◇
                   / │ \
                  /  │  \
                 /   │   \
              YES    │    NO
               │     │     │
               ▼     │     ▼
           Continue  │  Flag for
                      │  Review
                   ◇──┘


DECISION 4: Any contradictions?
                    ◇
                   / │ \
                  /  │  \
                 /   │   \
              NONE   │   FOUND
               │     │     │
               ▼     │     ▼
           Continue  │  Alert
                      │  System
                   ◇──┘


DECISION 5: What is the alert level?
                    ◇
                   / │ \
                  /  │  \
                 /   │   \
            1-3     4-6     7-10
             │       │        │
             ▼       ▼        ▼
          [PASS]  [WARN]   [ALERT]
           🟢      🟡        🔴

```

---

## Simple Mermaid-Style Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CONVERSATION LIFECYCLE                                   │
└─────────────────────────────────────────────────────────────────────────────┘

    [START]
       │
       ▼
┌──────────────┐
│ User sends   │
│ message      │
└──────┬───────┘
       │
       ▼
┌──────────────┐     NO     ┌──────────────┐
│ Preprocessor │───────────>│ Reject &     │
│ checks msg   │            │ tell user    │
└──────┬───────┘            └──────────────┘
       │ YES
       ▼
┌──────────────┐
│ Domain       │
│ Detector     │
│ sets rules   │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ AI receives  │
│ message      │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ AI creates   │
│ response     │
└──────┬───────┘
       │
       ▼
┌──────────────┐     NO     ┌──────────────┐
│ Coherence    │───────────>│ Flag & fix   │
│ Monitor      │            │ response     │
│ checks sense │            │              │
└──────┬───────┘            └──────────────┘
       │ YES
       ▼
┌──────────────┐
│ Session      │
│ Anchoring    │
│ updates mem  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Threshold    │
│ Engine       │
│ scores it    │
└──────┬───────┘
       │
   ┌───┴───┐
   ▼       ▼       ▼
  🟢      🟡       🔴
 PASS    WARN    ALERT
  │       │        │
  ▼       ▼        ▼
┌────┐  ┌────┐  ┌────┐
│Send│  │Send│  │Fix │
│to  │  │to  │  │&   │
│user│  │user│  │send│
│    │  │+log│  │    │
└────┘  └────┘  └────┘
   │       │        │
   └───────┴────────┘
           │
           ▼
       [END]
```

---

## Component Icons

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COMPONENT ICONS                                     │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ 1. PREPROCESSOR      🚪                                             │
  │     Like a door that only lets good messages through                │
  │                                                                     │
  │     ┌─────────┐                                                     │
  │     │  MSG    │ ──> [🚪] ──> ✓ or ✗                                │
  │     └─────────┘                                                     │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ 2. COHERENCE MONITOR  🔍                                            │
  │     Like a magnifying glass checking for mistakes                   │
  │                                                                     │
  │     ┌─────────┐                                                     │
  │     │  AI     │ ──> [🔍] ──> "Makes sense!"                         │
  │     │ RESPONSE│                                                     │
  │     └─────────┘                                                     │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ 3. SESSION ANCHORING  📝                                            │
  │     Like a notepad that remembers important facts                   │
  │                                                                     │
  │     Facts: ┌────────────────────┐                                   │
  │            │ • Name: Alex       │                                   │
  │            │ • Likes: Space     │                                   │
  │            │ • Pet: Dog (Max)   │                                   │
  │            └────────────────────┘                                   │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ 4. DOMAIN DETECTOR   🎯                                             │
  │     Like a target that knows what you're aiming for                 │
  │                                                                     │
  │     Topic: Math ──> 🎯 ──> Strict Rules                             │
  │     Topic: Story ─> 🎯 ──> Relaxed Rules                            │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ 5. THRESHOLD ENGINE  🚨                                             │
  │     Like an alarm that goes off when something's wrong              │
  │                                                                     │
  │     Score: 2 ──> 🟢 (Silent)                                        │
  │     Score: 5 ──> 🟡 (Caution)                                       │
  │     Score: 8 ──> 🔴 (ALERT!)                                        │
  └─────────────────────────────────────────────────────────────────────┘

```

---

## Quick Stats Box

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BRAIN GUARD AT A GLANCE                             │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
  │   5 Components  │    │  2 Checkpoints  │    │  3 Alert Levels │
  │                 │    │                 │    │                 │
  │ • Preprocessor  │    │ • User -> AI    │    │ • 🟢 Pass       │
  │ • Coherence     │    │ • AI -> User    │    │ • 🟡 Warn       │
  │ • Anchoring     │    │                 │    │ • 🔴 Alert      │
  │ • Domain        │    │                 │    │                 │
  │ • Threshold     │    │                 │    │                 │
  └─────────────────┘    └─────────────────┘    └─────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │                         POSITION                                    │
  │                                                                     │
  │     YOU  ──>  [ BRAIN GUARD ]  ──>  AI  ──>  [ BRAIN GUARD ]  ──>  YOU
  │                                                                     │
  │              (Middle / Checkpoint / Referee)                        │
  └─────────────────────────────────────────────────────────────────────┘

```

---

*Brain Guard: The Smart Checkpoint for AI Conversations*

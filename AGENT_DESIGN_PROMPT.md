# Comprehensive Prompt: Zoorkhane Fighting Agent Design

## Goal
Design and implement a **winning AI agent** for the Zoorkhane 2D fighting game. The agent must beat the default opponent (`agent.py`) consistently. The agent communicates via `stdin`/`stdout` JSON, is **stateless** (new process each frame), and has a **0.4 second time limit** per call.

---

## 1. Complete Game Mechanics (Exact Values from Source Code)

### 1.1 Environment
| Parameter | Value |
|---|---|
| Screen | 1000 × 540 px |
| FPS | 60 |
| Total frames per round | 3600 (60 seconds) |
| Starting HP | 100 per fighter |
| Fighter 1 start X | 100 (center) |
| Fighter 2 start X | 800 (center) |
| **Move order** | **Alternates each frame** (frame 1: F1→F2, frame 2: F2→F1, ...) |
| Win condition | Higher HP at frame 3600, or KO |

### 1.2 Fighter Physics
| Parameter | Value |
|---|---|
| Walk speed | **5 px/frame** |
| Dash speed | **30 px/frame** |
| Dash duration | **10 frames** (total 300px) |
| Dash cooldown | **50 frames** |
| Jump velocity | -30 (upward) |
| Gravity | 2 px/frame² |
| Fighter rect | 120 × 180 px |
| Left boundary | `rect.left >= 0` |
| Right boundary | `rect.right <= 1000` |
| Ground | `rect.bottom <= 470` |

### 1.3 Attack System
| Attack | Damage | Cooldown | Animation Action |
|---|---|---|---|
| Light (type=1) | **10 HP** | **25 frames** | action 3 |
| Heavy (type=2) | **20 HP** | **100 frames** | action 4 |

- **Attack hitbox**: 120px wide × 180px tall zone in front of the fighter (from `centerx` forward)
- **Attack range**: Two fighters overlap attack zones when `abs(centerx1 - centerx2) < ~180px` (since each attack rect is 120px from center, and fighter rect is 120px wide)
- **Cooldown starts AFTER animation finishes** (not when attack is initiated)
- **During attacking animation**: fighter CANNOT move, CANNOT issue new attacks
- **After being HIT** (hit stun, action 5): when animation finishes, light cooldown is reset to 25

### 1.4 Animation Timing
- Animation frame cooldown: **70ms** between sprite frames
- Different characters have different frame counts per animation (3-11 frames per action)
- Light attack animation: typically ~3-7 frames × 70ms = **210-490ms ≈ 13-29 game frames**
- Heavy attack animation: typically ~4-9 frames × 70ms = **280-630ms ≈ 17-38 game frames**
- Hit stun animation: typically ~3-5 frames × 70ms = **210-350ms ≈ 13-21 game frames**
- Characters are randomly assigned each round, so animation durations vary!

### 1.5 Dash Mechanics
- During dash: `move()` returns early → **NO movement, NO attacks, NO other actions possible**
- Attack cooldowns **DO NOT tick** during dash (the `return` at line 218 skips cooldown tick at line 386-389)
- Dash cooldown **DOES tick** during dash (it's decremented at line 200, BEFORE the `return`)  
- Fighter is rendered as a grey shadow (visual only — rect/hitbox still exists and CAN be hit by attacks)
- Direction locked at dash initiation
- **For opponent**: when they dash, their attack CDs freeze for 10 frames. This DELAYS their attack readiness. Track this in saved_data!

### 1.6 Move Order Implications
Since move order alternates each frame:
- **When we move FIRST**: we attack → opponent processes AFTER (our attack hits at current distance)
- **When we move SECOND**: opponent attacks first → then we process (opponent's attack hits first)
- This creates a ~50% chance mechanic for simultaneous-range combat

### 1.7 Same-Frame Move + Attack Mechanics (CRITICAL)
In `fighter.py move()`, when our agent returns both `move` and `attack`:
```
1. dx is calculated from move (±5)
2. attack() is called → collision check at CURRENT position (before dx applied)
3. dx is applied at the END of move() (line 394: self.rect.x += dx)
```
This means: **attack hits at the position BEFORE movement, then movement happens AFTER.**

**Exploit**: We can attack at dist=175 (in range) AND set move=away, which pushes us to dist=180 AFTER the attack. Next frame, we're at 180px — right at the edge of opponent's attack range. Combined with move-order alternation, ~50% of the time opponent's counter-attack will fire when we're at 180px and might miss (rect collision is tight at 180px).

---

## 2. Agent Input/Output API

### 2.1 Input (JSON via stdin)
```json
{
  "fighter": {
    "x": int,              // rect.centerx (60..940 valid range)
    "y": int,              // rect.centery
    "health": int,         // 0-100
    "attacking": bool,     // currently in attack animation (LOCKED)
    "attack_cooldown": [int, int],  // [light_cd, heavy_cd], 0 = ready
    "jump": bool,          // currently jumping
    "dash_cooldown": int   // 0 = ready, max 50
  },
  "opponent": {
    "x": int,              // rect.centerx
    "y": int,              // rect.centery
    "health": int,         // 0-100
    "attacking": bool      // currently in attack animation (LOCKED!)
  },
  "saved_data": {}         // persistent dict from previous frame
}
```

**CRITICAL**: Opponent info does NOT include `attack_cooldown`, `jump`, or `dash_cooldown`. We must **infer/track** these from observations stored in `saved_data`.

### 2.2 Output (JSON via stdout)
```json
{
  "move": null | "left" | "right",
  "attack": null | 1 | 2,
  "jump": true | false,
  "dash": null | "left" | "right",
  "debug": "string or null",
  "saved_data": {}
}
```
All 6 keys are **required**.

### 2.3 Time Constraint
- **0.4 seconds** per subprocess call (Python process startup + computation)
- Python process startup takes ~50-100ms → effective computation time: **~300ms**
- Must be highly optimized: NO heavy imports, NO file I/O on critical path (or use fast I/O)

### 2.4 When Is Our Agent Called?
**CRITICAL**: The game ONLY calls our agent when `self.attacking == False AND self.alive == True AND round_over == False`. This means:
- `fighter['attacking']` will ALWAYS be `False` when we receive a call
- If we sent `attack` last frame and the animation is still playing, we get NO call — we're skipped
- If we're dashing (10 frames), `move()` returns early → our agent is NOT called during dash either
- We can detect "skipped frames" by tracking frame counts in `saved_data`. If `saved_data['frame']` jumps by more than 1 between calls, we were locked in animation/dash for those frames.

---

## 3. Opponent Analysis (`agent.py` Default AI)

The default opponent is a **simple reactive agent** with predictable behavior:

### 3.1 Decision Logic (Exact)
```
1. Always jumps (every frame)
2. Attack range check: distanceX < 180 AND distanceY < 180 → "in vicinity"
3. If attacks available AND in vicinity → attack (prefers HEAVY = max(available))
4. If attacks available AND NOT in vicinity → move toward us
5. If NO attacks available:
   a. If dash available → dash AWAY
   b. Else → walk AWAY
6. When running away: direction is AWAY from us
   - Wall safety: if fighter_x > 180 (can go left) or fighter_x < 820 (can go right)
```

### 3.2 Opponent Behavior Cycle (Predictable!)
```
Frame 0:    Both attacks ready → approaches us (move toward)
Frame ~70:  In range → fires HEAVY (20 dmg), enters heavy animation (~17-38 game frames)
            During animation: opponent is LOCKED - cannot move, dodge, or counter!
Frame ~100: Heavy animation ends. heavy_cd = 100. light_cd was never used = STILL 0!
            Light available → immediately fires LIGHT (10 dmg), enters light animation (~17-34 frames)
            During BOTH animations back-to-back: ~34-72 game frames of being LOCKED!
            THIS IS A MASSIVE PUNISH WINDOW.
Frame ~130: Light animation ends. light_cd = 25, heavy_cd = ~70.
            NO attacks available → agent checks dash_cd:
              - If dash_cd == 0 → DASHES AWAY (300px, 10 frames, CDs FREEZE during dash!)
              - If dash_cd > 0 → WALKS AWAY at 5px/frame
            After dash: heavy_cd ~= 60 (lost 10 frames of tick), light_cd ~= 15
Frame ~155: light_cd reaches 0 (25 frames after animation end, minus frozen frames)
            → opponent approaches and fires LIGHT (10 dmg)
Frame ~175: light animation ends, light_cd = 25, heavy_cd ≈ 30
            NO attacks → runs away again (dash on CD, so walks)
Frame ~200: light_cd = 0 again → approach + LIGHT
...repeating LIGHT attacks every ~45 frames...
Frame ~230: heavy_cd finally reaches 0 → cycle restarts with HEAVY

FULL CYCLE: ~230 frames (3.8 seconds). Total opponent damage per full cycle:
  1× HEAVY (20) + ~3× LIGHT (30) = 50 damage per cycle
  7.6 cycles max in 3600 frames = ~380 potential dmg (if all hits land)
```

**KEY EXPLOITATION**: The initial HEAVY→LIGHT double-commit is a ~40-70 frame punish window. During this window, we can:
1. Stay in range and wait with CD almost ready
2. Land 1-2 FREE hits during their animation lock
3. Then retreat before their next attack is ready

### 3.3 Exploitable Weaknesses
1. **Predictable attack pattern**: always heavy first, then light
2. **Runs away when no CD** — creates a gap we can exploit
3. **Always jumps** — this is a WEAKNESS we can exploit! (see Section 13.1 Jump Analysis)
4. **No prediction, no memory** — purely reactive
5. **Wall bug**: when running away, direction check uses `fighter_x > 180` / `fighter_x < 820` but doesn't handle corners well
6. **Proximity check ≠ actual hit**: agent decides to attack based on `distX<180 AND distY<180`, but actual damage uses `rect.colliderect()`. When opponent is at peak of jump and we're on ground, their agent may decide NOT to attack even if in horizontal range (see Section 13.2)
7. **Dash wastes CD time**: when opponent dashes away (10 frames), their attack cooldowns FREEZE (move() returns early, cooldown ticks are at bottom). This wastes 10 frames of their CD recovery. We should track and exploit this.
8. **Heavy → Light double-commit**: opponent always fires heavy first (100 CD), then immediately light (0 CD), committing to ~50 frames of animation lock. This is a massive punish window.

---

## 4. Abstract Actions (High-Level Strategic Actions)

Instead of raw `(move, attack, jump, dash)` tuples, define **high-level abstract actions** that encapsulate multi-frame strategic intent. Each abstract action maps to concrete commands based on current state.

### 4.1 Abstract Action Definitions

```python
class AbstractAction(Enum):
    # ═══ OFFENSIVE ACTIONS ═══
    ENGAGE = "engage"
    # Intent: Close distance and prepare for attack
    # Concrete: move=toward, attack=None, jump=True
    # When: out of range, attack ready, want to fight
    
    STRIKE_LIGHT = "strike_light"
    # Intent: Deal 10 damage with fast recovery
    # Concrete: move=None/away, attack=1, jump=True
    # When: in range, light CD=0
    
    STRIKE_HEAVY = "strike_heavy"  
    # Intent: Deal 20 damage, accept long cooldown
    # Concrete: move=None/away, attack=2, jump=True
    # When: in range, heavy CD=0
    
    STRIKE_AND_RETREAT = "strike_retreat"
    # Intent: Attack + immediately retreat to avoid counter
    # Concrete: move=away, attack=best_available, jump=True
    # When: in range, attack ready
    
    DASH_ENGAGE = "dash_engage"
    # Intent: Close large gap instantly (300px dash)
    # Concrete: dash=toward, attack=None, jump=False
    # When: far from opponent, dash ready, attack ready
    
    PUNISH = "punish"
    # Intent: Rush in during opponent's attack animation for free hit
    # Concrete: move=toward, attack=None (then attack when in range)
    # When: opponent.attacking=True, we have attack ready

    # ═══ DEFENSIVE ACTIONS ═══
    RETREAT = "retreat"
    # Intent: Create distance from opponent
    # Concrete: move=away, attack=None, jump=True
    # When: in danger, no attack ready, opponent approaching
    
    DASH_RETREAT = "dash_retreat"
    # Intent: Emergency escape (300px away instantly)
    # Concrete: dash=away, attack=None, jump=False
    # When: low HP, in danger, dash ready
    
    KITE = "kite"
    # Intent: Maintain safe distance (KITE_DIST ~210px) while CD ticks
    # Concrete: move=toward/away to maintain distance, attack=None
    # When: no attack ready, opponent not locked
    
    BAIT = "bait"
    # Intent: Stay just outside range to bait opponent's attack, then punish
    # Concrete: move to dist=185-195 (just outside 180 range), wait
    # When: our attack almost ready, want to bait opponent into attacking first

    # ═══ POSITIONAL ACTIONS ═══
    HOLD = "hold"
    # Intent: Stay in place, wait for conditions to change
    # Concrete: move=None, attack=None, jump=True
    # When: at good distance, CD almost ready
    
    POSITION_LEFT = "position_left"
    # Intent: Get to left side of opponent (exploiting run-away bug)
    # Concrete: move strategically to be LEFT of opponent
    # When: we're on right side, want positional advantage
    
    CORNER_TRAP = "corner_trap"
    # Intent: Push opponent toward wall edge
    # Concrete: move toward, forcing opponent to corner
    # When: opponent near wall, we have positional advantage
    
    # ═══ ENDGAME ACTIONS ═══
    STALL = "stall"
    # Intent: Run out the clock with HP lead
    # Concrete: move=away, dash=away if available
    # When: winning on HP, <350 frames left
    
    DESPERATE_ATTACK = "desperate_attack"
    # Intent: All-in aggressive when losing near end
    # Concrete: rush + attack at every opportunity
    # When: losing on HP, <500 frames left
```

### 4.2 Abstract Action → Concrete Command Mapping

Each abstract action should have a `to_commands(fighter, opponent)` method that outputs the concrete `{move, attack, jump, dash}` based on current positions, cooldowns, etc.

---

## 5. State Representation & Memory (saved_data)

Since the function is **stateless** (new process each frame), all persistent data must go through `saved_data` dict (passed in, returned out). For fast read/write:

### 5.1 Using `saved_data` (Recommended — Zero I/O Overhead)
```python
saved_data = {
    # Frame counter
    "frame": int,
    
    # Opponent tracking (inferred from observations)
    "opp_prev_x": int,           # previous frame x position
    "opp_prev_hp": int,          # previous frame HP
    "opp_prev_attacking": bool,  # previous frame attacking state
    "opp_estimated_light_cd": int,  # our estimate of their light cooldown
    "opp_estimated_heavy_cd": int,  # our estimate of their heavy cooldown
    "opp_estimated_dash_cd": int,   # our estimate of their dash cooldown
    "opp_attack_pattern": list,  # last N attack types observed
    
    # Our state tracking
    "just_attacked": bool,       # did we attack last frame
    "last_action": str,          # last abstract action taken
    "consecutive_same_action": int,  # how many frames same action
    
    # Combat statistics
    "our_hits_landed": int,      # total hits we landed
    "our_hits_taken": int,       # total hits we took
    "opp_attack_intervals": list,  # frames between opponent attacks (predict timing)
    
    # Strategic state
    "current_strategy": str,     # "aggressive" / "defensive" / "kite" / "punish"
    "strategy_score": float,     # running effectiveness score
}
```

### 5.2 Using File I/O (Pickle / JSON) — For Large Data
If you need to store more data than fits comfortably in JSON (e.g., lookup tables, trained weights):

```python
import pickle
import os

SAVE_FILE = os.path.join(os.path.dirname(__file__), '.agent_memory.pkl')

def load_memory():
    """Load persistent memory from file. ~1-2ms overhead."""
    try:
        with open(SAVE_FILE, 'rb') as f:
            return pickle.load(f)
    except:
        return {}

def save_memory(data):
    """Save persistent memory to file. ~1-2ms overhead."""
    with open(SAVE_FILE, 'wb') as f:
        pickle.dump(data, f)
```

### 5.3 Using `saved_data` for Everything (Fastest — Recommended)
- `saved_data` is passed in/out as JSON → no file I/O
- Limit to ~1KB of data to keep JSON parsing fast
- Store only essential tracking info, not full history

---

## 6. Heuristic Function Design

The heuristic evaluates a game state and returns a score. **Higher = better for us.**

### 6.1 State Features to Evaluate
```python
def heuristic(state) -> float:
    """
    state = {
        my_hp, opp_hp, my_x, opp_x,
        my_light_cd, my_heavy_cd, my_dash_cd,
        opp_est_light_cd, opp_est_heavy_cd,
        frame, my_attacking, opp_attacking
    }
    """
    score = 0.0
    
    dist = abs(my_x - opp_x)
    hp_diff = my_hp - opp_hp
    time_left = 3600 - frame
    can_attack = my_light_cd <= 0 or my_heavy_cd <= 0
    opp_can_attack = opp_est_light_cd <= 0 or opp_est_heavy_cd <= 0
```

### 6.2 Scoring Components (Detailed)

#### A. HP Advantage (Most Important)
```python
# Raw HP difference — the fundamental win condition
score += hp_diff * 15.0

# Being alive is critical
if my_hp <= 0: return -100000
if opp_hp <= 0: return +100000

# Low HP penalty (risk of KO)
if my_hp < 20: score -= 50
if my_hp < 10: score -= 100
```

#### B. Positional Score
```python
# When we CAN attack: being in range is valuable
if can_attack:
    if dist < 180:  # in attack range
        score += 150  # very good — can deal damage NOW
        if opp_attacking:
            score += 200  # JACKPOT — opponent locked, free hit!
    elif dist < 220:
        score += 50  # close, approaching
    else:
        score -= (dist - 180) * 0.8  # penalty for being far when ready

# When we CANNOT attack: being at safe distance is valuable
else:
    if dist < 140:
        score -= 80  # too close, will take damage for free
    elif dist < 180:
        score -= 40  # in opponent's range, risky
    elif 200 <= dist <= 230:  # KITE sweet spot
        score += 40
    else:
        score -= abs(dist - 210) * 0.2
```

#### C. Cooldown Advantage
```python
# We can attack, opponent can't → we have tempo
if can_attack and not opp_can_attack:
    score += 80  # tempo advantage
elif not can_attack and opp_can_attack:
    score -= 60  # opponent has tempo

# How soon our attack is ready (urgency)
min_our_cd = min(my_light_cd, my_heavy_cd)
score += max(0, 30 - min_our_cd) * 3  # close to ready = good
```

#### D. Opponent Locked in Animation (CRITICAL)
```python
if opp_attacking:
    # Opponent is LOCKED — this is the biggest opportunity
    if can_attack and dist < 180:
        score += 300  # free damage opportunity!
    elif can_attack and dist < 300:
        score += 150  # can rush in for free hit
    else:
        score += 50   # at least safe from their attack
```

#### E. Wall Position
```python
# Being near wall is bad (limits retreat options)
if my_x < 80 or my_x > 920:
    score -= 60
if my_x < 40 or my_x > 960:
    score -= 100  # cornered!

# Opponent near wall is good (they can't retreat)
if opp_x < 80 or opp_x > 920:
    score += 30  # opponent cornered
```

#### F. Side Advantage
```python
# Being LEFT of opponent exploits the opponent's retreat bug
if my_x < opp_x:
    score += 10  # LEFT side advantage
```

#### G. Time Pressure
```python
if time_left < 900:  # last 15 seconds
    urgency = (900 - time_left) / 900.0
    if hp_diff > 0:
        # Winning: safe distance is more valuable
        score += hp_diff * urgency * 8
        if dist > 250: score += 40 * urgency  # far = safe = good
    else:
        # Losing: aggression is more valuable
        score -= abs(hp_diff) * urgency * 8
        if dist < 180 and can_attack: score += 60 * urgency  # must attack!
```

#### H. DPS Efficiency
```python
# Light attack: 10 dmg / 25 CD = 0.4 dmg/frame (HIGHER DPS!)
# Heavy attack: 20 dmg / 100 CD = 0.2 dmg/frame (LOWER DPS but burst)
# → Prefer LIGHT attacks for DPS, HEAVY only when safe (opponent locked)
if can_attack and dist < 180:
    if my_light_cd <= 0:
        score += 40  # light ready = reliable DPS
    if my_heavy_cd <= 0 and opp_attacking:
        score += 80  # heavy during punish window = best value
```

---

## 7. Search Tree with Abstract Actions

### 7.1 Minimax with Alpha-Beta Pruning

```python
def minimax(state, depth, maximizing, alpha, beta):
    if depth == 0 or state.is_terminal():
        return heuristic(state), None
    
    if maximizing:  # OUR turn
        best_score = -inf
        best_action = None
        for action in get_valid_abstract_actions(state):
            new_state = simulate_abstract_action(state, action)
            score, _ = minimax(new_state, depth-1, False, alpha, beta)
            if score > best_score:
                best_score, best_action = score, action
            alpha = max(alpha, score)
            if beta <= alpha: break  # prune
        return best_score, best_action
    
    else:  # OPPONENT turn (minimize)
        worst_score = +inf
        for opp_action in predict_opponent_actions(state):
            new_state = simulate_opponent_action(state, opp_action)
            score, _ = minimax(new_state, depth-1, True, alpha, beta)
            worst_score = min(worst_score, score)
            beta = min(beta, score)
            if beta <= alpha: break
        return worst_score, None
```

### 7.2 Which Abstract Actions Are Valid in Each State

```python
def get_valid_abstract_actions(state):
    actions = []
    dist = abs(state.my_x - state.opp_x)
    can_light = state.my_light_cd <= 0
    can_heavy = state.my_heavy_cd <= 0
    can_attack = can_light or can_heavy
    can_dash = state.my_dash_cd <= 0
    in_range = dist < 180
    opp_locked = state.opp_attacking
    time_left = 3600 - state.frame
    hp_diff = state.my_hp - state.opp_hp
    
    # Always available
    actions.append(HOLD)
    actions.append(RETREAT)
    
    # Offensive
    if can_attack and in_range:
        if can_light: actions.append(STRIKE_LIGHT)
        if can_heavy: actions.append(STRIKE_HEAVY)
        actions.append(STRIKE_AND_RETREAT)
    if can_attack and not in_range:
        actions.append(ENGAGE)
    if can_dash and not in_range and dist > 250:
        actions.append(DASH_ENGAGE)
    if opp_locked and can_attack:
        actions.append(PUNISH)
    
    # Defensive
    if not can_attack:
        actions.append(KITE)
    if can_dash and in_range and not can_attack:
        actions.append(DASH_RETREAT)
    if not can_attack and dist < 220 and dist > 160:
        actions.append(BAIT)
    
    # Positional
    if state.my_x > state.opp_x:
        actions.append(POSITION_LEFT)
    if (state.opp_x < 120 or state.opp_x > 880):
        actions.append(CORNER_TRAP)
    
    # Endgame
    if time_left < 350 and hp_diff > 15:
        actions.append(STALL)
    if time_left < 500 and hp_diff < -10:
        actions.append(DESPERATE_ATTACK)
    
    return actions
```

### 7.3 Forward Simulation per Abstract Action

Each abstract action simulates N frames forward (e.g., 8-12 frames) to estimate the resulting state:

```python
def simulate_abstract_action(state, action, steps=10):
    """Simulate `steps` game frames of executing `action`."""
    s = state.copy()
    
    for _ in range(steps):
        # Tick cooldowns
        s.my_light_cd = max(0, s.my_light_cd - 1)
        s.my_heavy_cd = max(0, s.my_heavy_cd - 1)
        s.my_dash_cd = max(0, s.my_dash_cd - 1)
        s.opp_est_light_cd = max(0, s.opp_est_light_cd - 1)
        s.opp_est_heavy_cd = max(0, s.opp_est_heavy_cd - 1)
        
        sign = 1 if s.my_x < s.opp_x else -1
        dist = abs(s.my_x - s.opp_x)
        
        # Execute our action
        if action == ENGAGE:
            s.my_x += 5 * sign
        elif action == STRIKE_LIGHT:
            if dist < 180 and s.my_light_cd <= 0:
                s.opp_hp -= 10; s.my_light_cd = 25
        elif action == STRIKE_HEAVY:
            if dist < 180 and s.my_heavy_cd <= 0:
                s.opp_hp -= 20; s.my_heavy_cd = 100
        elif action == STRIKE_AND_RETREAT:
            if dist < 180:
                if s.my_heavy_cd <= 0:
                    s.opp_hp -= 20; s.my_heavy_cd = 100
                elif s.my_light_cd <= 0:
                    s.opp_hp -= 10; s.my_light_cd = 25
            s.my_x -= 5 * sign  # retreat
        elif action == KITE:
            target_dist = 210
            if dist < target_dist - 15: s.my_x -= 5 * sign
            elif dist > target_dist + 15: s.my_x += 5 * sign
        elif action == RETREAT:
            s.my_x -= 5 * sign
        elif action == DASH_ENGAGE:
            if s.my_dash_cd <= 0:
                s.my_x += 300 * sign; s.my_dash_cd = 50
        elif action == DASH_RETREAT:
            if s.my_dash_cd <= 0:
                s.my_x -= 300 * sign; s.my_dash_cd = 50
        elif action == PUNISH:
            if dist >= 180: s.my_x += 5 * sign  # approach
            elif s.my_heavy_cd <= 0:
                s.opp_hp -= 20; s.my_heavy_cd = 100  # free heavy
            elif s.my_light_cd <= 0:
                s.opp_hp -= 10; s.my_light_cd = 25
        elif action == BAIT:
            target_dist = 190
            if dist < target_dist - 5: s.my_x -= 5 * sign
            elif dist > target_dist + 5: s.my_x += 5 * sign
        elif action == STALL:
            s.my_x -= 5 * sign  # run away
        elif action == DESPERATE_ATTACK:
            s.my_x += 5 * sign  # rush in
            if dist < 180:
                if s.my_light_cd <= 0:
                    s.opp_hp -= 10; s.my_light_cd = 25
                elif s.my_heavy_cd <= 0:
                    s.opp_hp -= 20; s.my_heavy_cd = 100
        
        # Simulate opponent response (based on agent.py behavior)
        dist = abs(s.my_x - s.opp_x)
        opp_can_attack = s.opp_est_light_cd <= 0 or s.opp_est_heavy_cd <= 0
        opp_sign = 1 if s.opp_x < s.my_x else -1
        
        if opp_can_attack and dist < 180:
            # Opponent attacks (heavy preferred)
            if s.opp_est_heavy_cd <= 0:
                s.my_hp -= 20; s.opp_est_heavy_cd = 100
            elif s.opp_est_light_cd <= 0:
                s.my_hp -= 10; s.opp_est_light_cd = 25
        elif opp_can_attack and dist >= 180:
            s.opp_x += 5 * opp_sign  # approach
        elif not opp_can_attack:
            s.opp_x -= 5 * opp_sign  # retreat
        
        # Clamp positions
        s.my_x = max(60, min(940, s.my_x))
        s.opp_x = max(60, min(940, s.opp_x))
        
        if s.my_hp <= 0 or s.opp_hp <= 0: break
    
    s.frame += steps
    return s
```

### 7.4 Depth & Time Budget

With 0.4s total (300ms effective):
- **Depth 2**: ~6 actions × 3 opponent responses × 6 actions = ~108 evaluations → **<5ms** ✓
- **Depth 3**: ~108 × 3 × 6 = ~1944 evaluations → **~20ms** ✓
- **Depth 4**: ~1944 × 3 × 6 = ~35000 evaluations → **~200ms** possible but tight
- Recommended: **depth 2-3** with alpha-beta pruning, or **depth 2 with iterative deepening**

---

## 8. Opponent Modeling & Tracking (via saved_data)

Since we don't see opponent cooldowns, we must INFER them:

```python
def track_opponent(saved_data, opponent):
    """Update opponent model based on observations."""
    prev_hp = saved_data.get('opp_prev_hp', opponent['health'])
    prev_atk = saved_data.get('opp_prev_attacking', False)
    
    # Detect attack START (transition from not-attacking to attacking)
    if opponent['attacking'] and not prev_atk:
        # Opponent just started an attack animation
        # We can't distinguish light/heavy from observation alone,
        # but we can infer from damage dealt
        saved_data['opp_attack_start_frame'] = saved_data.get('frame', 0)
    
    # Detect attack END (transition from attacking to not-attacking)
    if not opponent['attacking'] and prev_atk:
        # Attack animation just finished
        # Cooldown starts NOW
        duration = saved_data.get('frame', 0) - saved_data.get('opp_attack_start_frame', 0)
        
        # Check if WE took damage (our HP decreased)
        my_hp_loss = saved_data.get('my_prev_hp', 100) - saved_data.get('my_hp', 100)
        if my_hp_loss >= 15:
            # Heavy attack → set heavy CD to 100
            saved_data['opp_est_heavy_cd'] = 100
        elif my_hp_loss > 0:
            # Light attack → set light CD to 25
            saved_data['opp_est_light_cd'] = 25
        else:
            # Attack missed — estimate from duration
            if duration > 20:
                saved_data['opp_est_heavy_cd'] = 100
            else:
                saved_data['opp_est_light_cd'] = 25
    
    # Tick estimated cooldowns
    if saved_data.get('opp_est_light_cd', 0) > 0:
        saved_data['opp_est_light_cd'] -= 1
    if saved_data.get('opp_est_heavy_cd', 0) > 0:
        saved_data['opp_est_heavy_cd'] -= 1
    
    # Store current state
    saved_data['opp_prev_hp'] = opponent['health']
    saved_data['opp_prev_attacking'] = opponent['attacking']
    saved_data['opp_prev_x'] = opponent['x']
```

---

## 9. Strategy Selection (Meta-Level)

Before running minimax, select a **high-level strategy** that filters and prioritizes abstract actions:

```python
def select_strategy(fighter, opponent, saved_data):
    hp_diff = fighter['health'] - opponent['health']
    frame = saved_data.get('frame', 0)
    time_left = 3600 - frame
    dist = abs(fighter['x'] - opponent['x'])
    opp_locked = opponent['attacking']
    
    if opp_locked:
        return "PUNISH"          # Highest priority: free damage window
    
    if time_left < 350 and hp_diff > 15:
        return "STALL"           # Protect HP lead
    
    if time_left < 500 and hp_diff < -10:
        return "DESPERATE"       # Must attack to catch up
    
    if hp_diff > 25:
        return "DEFENSIVE"       # Protect big lead
    
    if hp_diff < -20:
        return "AGGRESSIVE"      # Must close HP gap
    
    if fighter['attack_cooldown'][0] <= 0 or fighter['attack_cooldown'][1] <= 0:
        return "ATTACK"          # We have attack ready → use it
    
    return "KITE"                # Default: safe distance, wait for CD
```

Each strategy biases which abstract actions are considered and gives bonus scores in the heuristic.

---

## 10. Key Strategic Insights (Why Current Agent Loses)

### 10.1 Problems with Current v13
1. **Heuristic too simple**: doesn't properly value tempo (who has attack ready first)
2. **No opponent CD tracking**: makes blind decisions about when opponent can attack
3. **Heavy attack overvalued**: heavy has 100 CD but only 20 dmg = 0.2 dmg/frame. Light has 25 CD and 10 dmg = 0.4 dmg/frame → **LIGHT is 2x better DPS**
4. **Retreat after attack is inconsistent**: sometimes retreats too far, loses tempo
5. **KITE distance too passive**: staying at 210 wastes frames when light CD is only 25
6. **No baiting**: doesn't try to make opponent whiff attacks

### 10.2 Optimal Strategy
1. **Prioritize LIGHT attacks** (0.4 dmg/frame vs 0.2 for heavy)
2. **Use HEAVY only during PUNISH windows** (opponent locked in animation)
3. **Track opponent CDs** → know exactly when they can/can't attack
4. **Minimal kite distance** (~185-190px) → quick re-engage after our light CD resets (25 frames)
5. **Exploit alternating move order** → attack + retreat on same frame for ~50% dodge
6. **Corner trap**: push opponent to wall, they can't retreat effectively
7. **Late game awareness**: stall with lead, desperate rush when behind

### 10.3 DPS Math
```
Scenario A (Light spam): 10 dmg every 25 frames = 0.4 dmg/frame
  → In 3600 frames: up to 144 light attacks = 1440 potential dmg (limited by range time)
  → Realistic: ~40% time in range = ~576 dmg potential

Scenario B (Heavy spam): 20 dmg every 100 frames = 0.2 dmg/frame
  → In 3600 frames: up to 36 heavy attacks = 720 potential dmg
  → Realistic: ~40% time in range = ~288 dmg potential

Scenario C (Mixed — heavy during punish, light otherwise):
  → Best of both: burst damage on locked opponent + fast DPS otherwise
```

---

## 11. Implementation Constraints & Performance

### 11.1 Time Budget Breakdown (0.4s total)
```
Python process startup:  ~50-100ms
JSON parsing (input):    ~1ms
Agent logic:             ~200-300ms AVAILABLE
JSON output:             ~1ms
Process cleanup:         ~5ms
```

### 11.2 Performance Tips
- **No heavy imports**: avoid numpy, pandas, etc. Only `json`, `math`, `os`
- **Precompute constants**: define all constants at module level
- **Simple data structures**: dicts and lists only, no classes — avoid `from enum import Enum`
- **Limit search depth**: depth 2-3 with pruning fits in budget
- **saved_data**: keep small (<1KB) for fast JSON serialization
- **No file I/O on critical path** unless absolutely necessary
- **Early exit**: if obvious action (e.g., opponent locked + we have attack → PUNISH), skip minimax
- **Avoid process-heavy operations**: Each frame spawns a NEW Python process. Module-level code runs EVERY frame. Keep it minimal.
- **Profile**: `import time; t0=time.perf_counter()` at start, measure elapsed time in debug output

### 11.3 Module-Level Code Budget
Every line at module level runs EVERY FRAME (new process each frame). Example costs:
```python
import json          # ~1ms  ✓ (essential)
import math          # ~1ms  ✓ (useful)
import os            # ~1ms  ✓ (if needed)
import pickle        # ~2ms  ✓ (if file I/O needed)
from enum import Enum # ~8ms ✗ (waste! use strings instead)
import numpy         # ~80ms ✗✗ (kills entire time budget!)
import random        # ~2ms  ⚠️ (only if needed for mixed strategies)
```
Total module import time must stay under **20ms** to leave 280ms for logic.

### 11.3 Fast Path Optimization
```python
def make_move(fighter, opponent, saved_data):
    # FAST PATH: Skip minimax for obvious situations
    
    # 1. We're locked in animation → no action possible
    if fighter['attacking']: return no_op()
    
    # 2. Opponent locked + we have attack + in range → PUNISH (free hit!)
    if opponent['attacking'] and can_attack and in_range:
        return strike_best()  # Don't waste time on minimax
    
    # 3. In range + attack ready → STRIKE (obvious best action)
    if in_range and can_attack:
        return strike_and_retreat()
    
    # 4. Only for non-obvious situations → run minimax
    return minimax_decide(...)
```

---

## 12. Summary: What to Implement

1. **Abstract Action enum** with 14+ high-level actions
2. **`to_commands()` function** mapping each abstract action to concrete `{move, attack, jump, dash}`
3. **Opponent tracking** in `saved_data` (estimated CDs, attack history, movement patterns)
4. **Rich heuristic** with 8+ scoring components (HP, position, CD advantage, tempo, wall, side, time pressure, DPS potential)
5. **Minimax with alpha-beta** at depth 2-3 using abstract actions
6. **Strategy selector** (PUNISH/ATTACK/KITE/STALL/DESPERATE) that filters actions
7. **Fast paths** for obvious decisions (skip minimax when action is clear)
8. **Forward simulation** per abstract action (8-12 frames lookahead)
9. **Light attack priority** (2x DPS of heavy) except during punish windows
10. **Minimal kite distance** (~185px instead of 210px) for faster re-engage

---

## 13. Critical Mechanics Deep-Dive (MUST READ)

### 13.1 Jump Analysis — Why We Should NOT Always Jump

The current agent and opponent both set `jump=True` every frame. This is WRONG for us. Here's why:

**Jump physics**: velocity=-30, gravity=2. Jump arc takes ~30 frames to complete (15 up, 15 down).
- Peak height: at ~15 frames, `vy = -30 + 2*15 = 0`, total vertical displacement = `sum(-30 + 2*i for i=0..14)` ≈ -240 + 210 = -30px centerY shift (but centery is based on rect which extends 180px, so centerY goes from ~380 to ~350).

**Key insight**: `fighter.jump` is checked — if already jumping, jump command is ignored. So `jump=True` every frame effectively means "jump whenever on ground."

**Why NOT jumping is better**:
1. The opponent's decision to attack checks `distanceY < 180`. If WE stay on ground (Y~380) and opponent is at jump peak (Y~350), `distY = 30 < 180` — opponent attacks. OK so far same.
2. BUT: the actual `attack_rect.colliderect(target.rect)` uses the full 180px height rect. Since both rects are 180px tall, vertical overlap is very forgiving.
3. **The real advantage**: When WE don't jump, our position is perfectly predictable → our heuristic distance calculations are exact. Jumping adds noise to our own positioning.
4. **However**: Jumping CAN dodge attacks in rare cases when at peak and opponent at ground. The hit rect check uses `self.rect.y` to `self.rect.y + 180`, so if we're 30px higher, there's still overlap.

**Recommendation**: Use `jump=True` ONLY when tactically useful (dodging, or when opponent is mid-air). For most frames, `jump=False` keeps our Y-position stable and predictable, improving heuristic accuracy.

### 13.2 Attack Collision vs. Distance Check — Critical Difference

The opponent AI checks `distanceX < 180 AND distanceY < 180` to DECIDE to attack.
But actual DAMAGE is checked via `pygame.Rect.colliderect()`:

```python
attack_rect = Rect(centerx - (width * flip), rect.y, 120, 180)
# flip=True → attack_rect starts at centerx-120 (left side)
# flip=False → attack_rect starts at centerx (right side)
```

So the actual hit check is rect-vs-rect collision, NOT center-to-center distance.

**Fighter rect**: `(x, y, 120, 180)` where x=rect.left, NOT centerx.
**Attack rect**: 120px wide from centerx in facing direction.

Two fighters CAN hit each other when `centerx` distance is as low as 0 (overlapping) and as far as 240px (120 attack reach + 120 body width = 240... no wait):
- Fighter A at centerx=200, facing right: attack_rect = (200, y, 120, 180) → covers x=200 to x=320
- Fighter B at centerx=350, body rect = (350-60, y, 120, 180) = (290, y, 120, 180) → covers x=290 to x=410
- Collision? 200-320 vs 290-410 → YES, overlap at 290-320.
- Distance = 150px centerx-to-centerx → HIT.
- But at distance 250px: attack (200,320) vs body (310,430) → overlap at 310-320 → STILL HIT at 250px?! Wait: centerx=200, opponent centerx=450 → attack=(200, y, 120, 180) covers 200-320, body=(390,y,120,180) covers 390-510 → NO overlap. 

**Real max attack range**: `120 (attack width) + 60 (half opponent body) = 180px` from our centerx. This confirms the 180px threshold.

**But at very close range (<60px)**: the attack rect might NOT cover the opponent if they're on the WRONG side. The attack goes forward based on `self.flip`. If opponent crosses to our back... But the code resets flip at end of move: `if target.centerx > self.centerx: flip=False else flip=True`. So we always face opponent → always correct side.

### 13.3 Cooldown Tick Timing — CRITICAL for Simulation

From `fighter.py move()`, the order of operations in each frame is:
```
1. Dash cooldown ticks (always, even during dash)
2. If dashing → apply dash movement → RETURN (skip everything below!)
3. If AI → call agent → apply move/attack/dash
4. If AI → set facing direction
5. Apply gravity
6. Apply boundary clamps
7. Attack cooldowns tick (lines 386-389)
8. Apply dx, dy to position
```

Then `update()` is called AFTER `move()`:
```
9. Update animation action/frame
10. 70ms sprite timer → advance frame
11. If animation finished → reset attacking/hit, SET cooldowns
```

**CRITICAL ORDER**: 
- Step 3: We call attack → `self.attacking = True`, damage applied NOW
- Step 7: Attack cooldowns tick DOWN (existing CDs from previous attacks)
- Step 8: Position changes applied
- Step 9-11: Animation advances; when animation ENDS, cooldown is SET (25 or 100)

This means: **cooldown starts AFTER animation finishes (in update()), and starts ticking DOWN from the NEXT frame's move() step 7.**

### 13.4 Dash During Attack Animation — Impossible

From the code: `if self.is_ai and self.attacking == False and self.alive == True and round_over == False:` — the agent is ONLY called when `attacking == False`. So during our attack animation, we have NO control. The `move()` method does nothing for AI when attacking. Gravity still applies, boundary clamps still apply, cooldowns still tick.

### 13.5 Hit Stun Chain — Can We Stunlock?

When hit: `target.hit = True`, enters action 5 (hit animation, 3-5 frames × 70ms ≈ 13-21 game frames). During hit stun, `self.attacking` is False and `self.hit` is True. The `update()` checks hit BEFORE attacking:
```python
if self.hit == True:
    self.update_action(5)  # hit animation
elif self.attacking == True:
    ...
```

So being hit INTERRUPTS an attack animation. But it does NOT cancel the attack's cooldown — cooldown was never set because animation didn't finish.

When hit animation ends: `self.hit = False`, `self.attack_cooldown[0] = 25` (light CD reset).

**Can we stunlock?** Only if we can hit every ~15-20 frames (duration of hit stun). With light attack CD = 25 frames, we CANNOT chain stun (25 > ~15-20). But: if we alternate light and heavy? Light → 25 frame CD, but heavy → 100 frame CD. No good.

**Conclusion**: Stunlock is NOT possible with single character. But we CAN hit during their hit stun recovery! Their CD gets reset to 25 after hit, so they're temporarily disarmed.

### 13.6 Exact Character Animation Frame Counts

Characters are randomly assigned. Animation format: `[idle, run, jump, light_atk, heavy_atk, hit, death, extra]` 

| Char | ID | Light Atk Frames | Heavy Atk Frames | Hit Stun Frames | Lock Duration Light (×70ms/60fps) | Lock Duration Heavy |
|---|---|---|---|---|---|---|
| Knight | 1 | **7** | **7** | **4** | 7×70/16.67 ≈ **29 game frames** | **29 game frames** |
| Martial1 | 2 | **6** | **6** | **4** | 6×70/16.67 ≈ **25 game frames** | **25 game frames** |
| Martial2 | 3 | **4** | **4** | **3** | 4×70/16.67 ≈ **17 game frames** | **17 game frames** |
| Martial3 | 4 | **7** | **9** | **3** | ≈ **29 game frames** | **38 game frames** |
| Wizard | 5 | **8** | **8** | **5** | ≈ **34 game frames** | **34 game frames** |

**Note**: Animation advances based on real-time `pygame.time.get_ticks()` with 70ms cooldown, and game runs at 60 FPS (16.67ms per game frame). So each animation frame ≈ 70/16.67 ≈ **4.2 game frames**. The lock durations above are animation_frames × 4.2.

**Key takeaway**: Martial2 (ID=3) has the FASTEST animations (17 game frames lock), Knight/Martial3/Wizard are SLOWEST (29-38 game frames lock). Since characters are random, our agent should **detect lock duration from observation** (track how long `attacking=True` lasts) and adapt.

### 13.7 WHY Our Agent Not Being Called Is Free Info

When `fighter.attacking == True`, the game does NOT call our agent at all (see fighter.py line 220). So when we receive a call, we know `fighter.attacking` is `False`. This means:
- We never need to check `fighter['attacking']` — it's ALWAYS `False` when we're called
- The frame where `attacking` transitions from True→False is the frame our CD gets SET (25 or 100)

Wait, looking at the code again: `fighter_info['attacking'] = self.attacking` is set BEFORE the AI check. The AI check is `if self.is_ai and self.attacking == False`. So if attacking is True, agent is NOT called at all. However, the `attacking` field is still sent as part of the info dict... but the whole block is skipped. **Agent is never called when attacking=True.**

### 13.8 Opponent Velocity Tracking — Predict Dash

We can't see opponent's dash_cooldown, but we CAN detect dashing:
- If opponent's X changes by ~30px between frames → they're dashing
- If opponent's X changes by 5px → walking
- If opponent's X changes by 0px → stationary or attacking

Store `opp_prev_x` in saved_data and compute `opp_dx = opponent['x'] - saved_data['opp_prev_x']`. If `abs(opp_dx) > 20`, they're dashing → track remaining dash frames and dash cooldown.

### 13.9 Facing Direction Exploit

After AI move is processed, facing is set: `if target.centerx > self.centerx: flip=False else flip=True`. This happens AFTER dx is applied. So if we dash THROUGH the opponent (dash right past them), we end up on their RIGHT side, our facing direction is reset to LEFT (toward them), but THEIR facing hasn't updated yet (depends on move order that frame). 

This is a micro-edge: if we dash through on a frame where we move SECOND, opponent already processed with old facing → their attack went wrong direction? No — opponent's facing is also set at end of their move. But their attack_rect was already computed. So:
- Frame N (opponent moves first): Opponent attacks toward us (correct), then we dash through them
- Frame N+1 (we move first): We're now behind them, we attack → our attack hits (we face them). Then opponent moves, they face us now.

Not hugely exploitable but worth knowing for corner situations.

---

## 14. Anti-Patterns to Avoid

### 14.1 DO NOT Use Heavy Attack As Default
Current v13 does `best_atk = 2 if can_heavy else 1` — this is WRONG.
- Heavy: 20 dmg, 100 CD = 0.2 dmg/frame
- Light: 10 dmg, 25 CD = 0.4 dmg/frame
- **Light is 2x more efficient**
- ONLY use heavy when opponent is LOCKED in animation (free hit, no counter risk)

### 14.2 DO NOT Kite at 210px
KITE_DIST=210 means 30px to close before attacking. At 5px/frame, that's **6 extra frames** of approach. With light CD of 25 frames, approach is 24% wasted time. Better to kite at 185px (1 frame to close).

### 14.3 DO NOT Retreat Multiple Frames After Attack
Current v13 does `just_attacked → retreat one frame`. But even one retreat frame at 5px pushes distance from ~175 to ~180. Then next frame we need to approach again. The CORRECT play:
- Attack + `move=away` on the same command (attack fires at current position, then dx is applied)
- Next frame: if opponent is locked in THEIR animation → PUNISH (stay close for another hit)
- Next frame: if opponent is NOT locked → kite to 185px and wait for our CD

### 14.4 DO NOT Ignore Opponent's Y Position
Opponent jumps every frame. At jump peak, centerY ≈ 350 vs ground ≈ 380. The distance check uses BOTH X and Y for vicinity check (`distX < 180 AND distY < 180`). Since distY is always < 180 (max ~30px difference), this is not a problem. BUT: rect collision for damage uses full height rects, so Y only matters for the initial jump frames where the opponent might be above the attack zone. **Not jumping ourselves** makes our attack more reliable since our rect stays at consistent Y.

### 14.5 DO NOT Use Minimax for Obvious Decisions
Minimax is expensive. For 80% of frames, the correct action is deterministic:
- In range + attack ready → STRIKE
- Opponent locked + attack ready → PUNISH
- Out of range + attack ready → ENGAGE
- Out of range + no attack → KITE to 185px
- Winning + endgame → STALL

Only use minimax for the remaining 20% ambiguous situations (e.g., in range, no attack, opponent not locked, CD > 5 — should we retreat or wait?).

### 14.6 DO NOT Waste Dash Offensively (Usually)
Dash = 300px movement but **50 frame cooldown** and **10 frames of total lockout** (no attacks, no movement, CDs freeze). The opponent agent uses dash DEFENSIVELY (to flee). We should mostly save dash for:
- Emergency escape when cornered at low HP
- Closing distance when opponent is locked AND far away (>250px) AND we have attack ready
- **Never** dash when opponent has attack ready — we'll arrive locked in dash animation and get hit

### 14.7 DO NOT Use Enum Classes or Complex OOP
`from enum import Enum` adds ~5-10ms import time. In a 300ms budget, that's significant. Use plain string constants:
```python
# BAD: from enum import Enum; class Action(Enum): ...
# GOOD:
ENGAGE = 'engage'
STRIKE_LIGHT = 'strike_light'
# etc.
```

---

## 15. Recommended Agent Architecture

```
make_move(fighter, opponent, saved_data)
│
├── 1. INIT: Parse state, track opponent (update saved_data)
│
├── 2. FAST PATHS (skip search for obvious plays):
│   ├── Locked in own animation? → no_op
│   ├── Opponent locked + in range + attack ready? → PUNISH
│   ├── In range + attack ready? → STRIKE_LIGHT + retreat
│   ├── Endgame + winning? → STALL
│   └── Endgame + losing? → DESPERATE
│
├── 3. STRATEGY SELECTION:
│   ├── Determine phase: OPENING / MID / ENDGAME
│   ├── Select strategy based on HP, distance, CDs
│   └── Filter valid abstract actions
│
├── 4. MINIMAX (only if needed):
│   ├── Depth 2-3 with alpha-beta
│   ├── Abstract actions as moves
│   ├── Opponent model predicts their response
│   └── Heuristic evaluates resulting state
│
├── 5. ACTION → COMMANDS:
│   ├── Map best abstract action to {move, attack, jump, dash}
│   └── Apply wall safety checks
│
└── 6. OUTPUT: Return JSON with saved_data
```

### 15.1 Opponent Model Quality Is KEY

The single most impactful improvement is to **model what the opponent will do next**. Since `agent.py` is deterministic, if we can infer its state, we can predict its exact action:

```python
def predict_opponent_next(opp_x, my_x, opp_est_light_cd, opp_est_heavy_cd, opp_dash_cd, dist):
    """Predict opponent's next action given their estimated state."""
    attacks_available = []
    if opp_est_light_cd <= 0: attacks_available.append(1)
    if opp_est_heavy_cd <= 0: attacks_available.append(2)
    
    in_vicinity = dist < 180  # opponent also checks distY < 180 but this is ~always true
    
    if attacks_available and in_vicinity:
        return 'attack', max(attacks_available)  # opponent prefers heavy
    elif attacks_available:
        return 'approach', None  # walking toward us
    else:
        if opp_dash_cd <= 0:
            return 'dash_away', None  # will dash 300px away!
        else:
            return 'walk_away', None  # walking away at 5px/frame
```

If our opponent model is accurate, minimax becomes extremely effective — we know exactly what they'll do, making our search essentially perfect information.

### 15.2 Tracking Opponent State Precisely

```python
def update_opponent_model(saved_data, fighter, opponent):
    frame = saved_data.get('frame', 0)
    prev_opp_x = saved_data.get('opp_prev_x', opponent['x'])
    prev_opp_atk = saved_data.get('opp_prev_attacking', False)
    prev_opp_hp = saved_data.get('opp_prev_hp', opponent['health'])
    prev_my_hp = saved_data.get('my_prev_hp', fighter['health'])
    
    opp_dx = abs(opponent['x'] - prev_opp_x)
    
    # -- Detect opponent DASHING (speed > 20px/frame)
    if opp_dx > 20:
        saved_data['opp_dashing'] = True
        saved_data['opp_dash_cd'] = 50  # just started
        # During dash, attack CDs FREEZE → don't decrement them
    else:
        if saved_data.get('opp_dashing', False):
            saved_data['opp_dashing'] = False  # dash ended
        # Normal frame: tick down estimated cooldowns
        if saved_data.get('opp_est_lcd', 0) > 0:
            saved_data['opp_est_lcd'] -= 1
        if saved_data.get('opp_est_hcd', 0) > 0:
            saved_data['opp_est_hcd'] -= 1
    
    # Always tick dash CD (it ticks even during dash)
    if saved_data.get('opp_dash_cd', 0) > 0:
        saved_data['opp_dash_cd'] -= 1
    
    # -- Detect opponent ATTACK START
    if opponent['attacking'] and not prev_opp_atk:
        saved_data['opp_atk_start'] = frame
        # Did we take damage this frame?
        my_hp_loss = prev_my_hp - fighter['health']
        if my_hp_loss >= 15:
            saved_data['opp_atk_type'] = 'heavy'
        elif my_hp_loss > 0:
            saved_data['opp_atk_type'] = 'light'
        else:
            saved_data['opp_atk_type'] = 'miss'  # missed us
    
    # -- Detect opponent ATTACK END
    if not opponent['attacking'] and prev_opp_atk:
        # Animation just finished → cooldown is NOW set
        atk_type = saved_data.get('opp_atk_type', 'unknown')
        if atk_type == 'heavy' or atk_type == 'miss':
            # Could be either; use duration to guess
            duration = frame - saved_data.get('opp_atk_start', frame)
            if duration > 22:  # heavy animations are longer
                saved_data['opp_est_hcd'] = 100
            else:
                saved_data['opp_est_lcd'] = 25
        elif atk_type == 'light':
            saved_data['opp_est_lcd'] = 25
    
    # -- Detect HIT on opponent (we damaged them)
    opp_hp_loss = prev_opp_hp - opponent['health']
    if opp_hp_loss > 0:
        # When opponent gets hit, their hit stun resets light CD
        # (after hit animation: attack_cooldown[0] = 25)
        saved_data['opp_got_hit'] = True
        saved_data['opp_hit_frame'] = frame
    
    # After ~20 frames of hit stun, light CD resets to 25
    if saved_data.get('opp_got_hit') and frame - saved_data.get('opp_hit_frame', 0) > 20:
        saved_data['opp_est_lcd'] = max(saved_data.get('opp_est_lcd', 0), 25)
        saved_data['opp_got_hit'] = False
    
    # -- Save for next frame
    saved_data['opp_prev_x'] = opponent['x']
    saved_data['opp_prev_attacking'] = opponent['attacking']
    saved_data['opp_prev_hp'] = opponent['health']
    saved_data['my_prev_hp'] = fighter['health']
    
    return saved_data
```

---

## 16. Concrete Winning Tactics (Decision Flowchart)

```
FRAME START → update_opponent_model()
│
├─ opponent.attacking == True?
│   ├─ YES + in_range + can_attack → PUNISH (heavy if available, else light)  
│   ├─ YES + NOT in_range + can_attack + dist < 250 → RUSH toward (will be in range in ~10 frames, animation lasts 17-38)
│   └─ YES + no attack → HOLD position (safe, opponent can't hit us while locked)
│
├─ in_range (dist < 180)?
│   ├─ can_light → STRIKE_LIGHT + move=away (attack at current pos, then retreat 5px)
│   ├─ can_heavy + opp locked → STRIKE_HEAVY (free heavy during punish)
│   ├─ can_heavy + opp NOT locked → STRIKE_LIGHT preferred (2x DPS, unless light on CD)
│   ├─ no attack + opp_cd almost 0 → RETREAT immediately (they'll attack next frame!)
│   ├─ no attack + opp_cd > 10 → HOLD (safe, wait for our CD)
│   └─ no attack + opp_cd unknown → RETREAT (conservative)
│
├─ NOT in_range?
│   ├─ can_attack → ENGAGE (move toward, attack when in range)
│   ├─ no attack + cd ≤ 8 → approach to dist=185 (almost ready)
│   ├─ no attack + cd > 8 → KITE at dist=185 (close enough for quick engage)
│   └─ no attack + opponent approaching → KITE (maintain distance)
│
├─ ENDGAME (time_left < 500)?
│   ├─ hp_diff > 10 → STALL (run away, dash if needed)
│   └─ hp_diff < -10 → DESPERATE (rush in + spam attacks)
│
└─ DEFAULT → KITE at 185px, wait for CD
```

---

## 17. Testing Methodology

### 17.1 Use headless_battle.py for Batch Testing
Run 50+ battles to get statistical win rate. Target: **>80% win rate** against `agent.py`.

### 17.2 Metrics to Track
- Win rate (target > 80%)
- Average HP difference at game end
- Hits landed vs hits taken
- Attack efficiency (hits landed / attacks attempted)
- Time in range vs time kiting
- Debug reason distribution (which fast paths fire most)

### 17.3 Iterative Improvement
1. Start with fast paths only (no minimax)
2. Measure win rate
3. Add minimax for ambiguous situations
4. Tune heuristic weights based on battle statistics
5. Add opponent model tracking
6. Re-measure and iterate

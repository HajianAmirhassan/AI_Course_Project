"""
Fighting Agent v15 – Never-Miss Aggressor
============================================
PRINCIPLE: Never waste an attack. Only swing when dist_y < 170 (guaranteed hit).

- Jump = True (no-jump has zero advantage; opponent checks dist_y anyway)
- Heavy attack preferred when hit is guaranteed (20 dmg vs 10)
- YHOLD: If in X-range but Y-separated (dist_y >= 170), hold and DON'T attack
- Retreat 2 frames after each hit to break hitstun-exchange loop
  (F1.alive checked first → mutual death = we lose)
- Dash retreat when very close + dash available
- Punish opponent during their attack animation if we can close distance
"""

import json

RANGE = 180           # attack range threshold
SCREEN_W = 1000
TOTAL_FRAMES = 3600
SPEED = 5
KITE_DIST = 195       # closer kite = faster re-engagement
SIM_STEPS = 8         # simulation look-ahead frames


# ═══════════════════════════════════════════════════════════
# HEURISTIC
# ═══════════════════════════════════════════════════════════
def heuristic(fhp, ohp, fx, ox, f_lcd, f_hcd, frame):
    if fhp <= 0: return -10000
    if ohp <= 0: return  10000

    hp_diff = fhp - ohp
    dist = abs(fx - ox)
    can_atk = f_lcd <= 0 or f_hcd <= 0
    min_cd = min(f_lcd, f_hcd)
    time_left = max(TOTAL_FRAMES - frame, 1)

    score = hp_diff * 10.0

    # Distance value depends on whether we can attack
    if can_atk:
        if dist < RANGE:
            score += 120
        elif dist < RANGE + 40:
            score += 60 - (dist - RANGE) * 1.5
        else:
            score -= (dist - RANGE) * 0.5
    else:
        # Kite: want to be at KITE_DIST
        if dist < RANGE - 20:
            score -= 60   # too close, will take damage
        elif dist < RANGE:
            score -= 30
        elif abs(dist - KITE_DIST) < 30:
            score += 25   # sweet spot
        else:
            score -= abs(dist - KITE_DIST) * 0.15

    # Cooldown almost ready = good position
    score += max(0, 25 - min_cd) * 2

    # Wall penalty
    if fx < 70 or fx > SCREEN_W - 70:
        score -= 40

    # Positioning: we want to be to the LEFT of opponent (exploit run bug)
    if fx < ox:
        score += 8   # we're LEFT = good
    else:
        score -= 5   # we're RIGHT = bad

    # Time pressure
    if time_left < 900:
        urgency = (900 - time_left) / 900.0
        score += hp_diff * 5 * urgency

    return score


# ═══════════════════════════════════════════════════════════
# FORWARD SIMULATION (simplified)
# ═══════════════════════════════════════════════════════════
def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

def simulate(action, fx, fhp, ox, ohp, f_lcd, f_hcd, f_dcd, frame):
    hit = False
    for _ in range(SIM_STEPS):
        if f_lcd > 0: f_lcd -= 1
        if f_hcd > 0: f_hcd -= 1
        if f_dcd > 0: f_dcd -= 1
        sign = 1 if fx < ox else -1
        dist = abs(fx - ox)

        if action == 'strike_heavy':
            if dist >= RANGE:
                fx += SPEED * sign
            elif f_hcd <= 0 and not hit:
                ohp -= 20; f_hcd = 100; hit = True
        elif action == 'strike_light':
            if dist >= RANGE:
                fx += SPEED * sign
            elif f_lcd <= 0 and not hit:
                ohp -= 10; f_lcd = 25; hit = True
        elif action == 'approach':
            fx += SPEED * sign
        elif action == 'kite':
            if dist < KITE_DIST - 15:
                fx -= SPEED * sign
            elif dist > KITE_DIST + 15:
                fx += SPEED * sign
        elif action == 'retreat':
            fx -= SPEED * sign
        elif action == 'dash_in':
            if f_dcd <= 0:
                fx += 300 * sign; f_dcd = 50
            else:
                fx += SPEED * sign

        # Opponent approximate response
        dist = abs(fx - ox)
        if dist < RANGE:
            fhp -= 0.7
        elif dist < RANGE + 60:
            ox += SPEED * (-sign) * 0.4

        fx = _clamp(fx, 70, SCREEN_W - 70)
        ox = _clamp(ox, 60, SCREEN_W - 60)
        
        if fhp <= 0 or ohp <= 0:
            break

    return fx, max(0, fhp), ox, max(0, ohp), f_lcd, f_hcd, f_dcd, frame + SIM_STEPS


# ═══════════════════════════════════════════════════════════
# MIN-MAX WITH ALPHA-BETA (depth 2)
# ═══════════════════════════════════════════════════════════
def _valid_actions(f_lcd, f_hcd, f_dcd, dist):
    acts = ['approach', 'kite', 'retreat']
    if f_lcd <= 0 and dist < RANGE + 50:
        acts.append('strike_light')
    if f_hcd <= 0 and dist < RANGE + 50:
        acts.append('strike_heavy')
    if f_dcd <= 0 and dist > RANGE + 60:
        acts.append('dash_in')
    return acts

def minimax(fx, fhp, ox, ohp, f_lcd, f_hcd, f_dcd,
            frame, depth, maximising, alpha, beta):
    if depth == 0 or fhp <= 0 or ohp <= 0:
        return heuristic(fhp, ohp, fx, ox, f_lcd, f_hcd, frame), None
    dist = abs(fx - ox)

    if maximising:
        best = -float('inf')
        best_act = 'approach'
        for act in _valid_actions(f_lcd, f_hcd, f_dcd, dist):
            nfx, nfhp, nox, nohp, nl, nh, nd, nf = simulate(
                act, fx, fhp, ox, ohp, f_lcd, f_hcd, f_dcd, frame)
            sc, _ = minimax(nfx, nfhp, nox, nohp, nl, nh, nd,
                            nf, depth - 1, False, alpha, beta)
            if sc > best:
                best, best_act = sc, act
            alpha = max(alpha, sc)
            if beta <= alpha:
                break
        return best, best_act
    else:
        worst = float('inf')
        sign = 1 if ox < fx else -1
        for dmg in [-12, -5, 0]:
            nfhp = max(0, fhp + dmg)
            nox = _clamp(ox + SPEED * SIM_STEPS * (-sign) * 0.3,
                         60, SCREEN_W - 60)
            sc, _ = minimax(fx, nfhp, nox, ohp, f_lcd, f_hcd, f_dcd,
                            frame + SIM_STEPS, depth - 1, True, alpha, beta)
            if sc < worst:
                worst = sc
            beta = min(beta, sc)
            if beta <= alpha:
                break
        return worst, None


# ═══════════════════════════════════════════════════════════
# ACTION → COMMANDS helper
# ═══════════════════════════════════════════════════════════
def to_commands(action, fighter, opponent):
    fx, ox = fighter['x'], opponent['x']
    dist_x = abs(fx - ox)
    we_left = fx < ox
    toward = 'right' if we_left else 'left'
    away   = 'left'  if we_left else 'right'
    acd    = fighter['attack_cooldown']
    dcd    = fighter['dash_cooldown']
    in_rng = dist_x < RANGE

    move, attack, dash = None, None, None

    if action in ('strike_heavy', 'strike_light'):
        if in_rng:
            if action == 'strike_heavy' and acd[1] == 0:
                attack = 2
            elif acd[0] == 0:
                attack = 1
            elif acd[1] == 0:
                attack = 2
            if dist_x > 160: move = toward
            elif dist_x < 30: move = away
        else:
            move = toward
    elif action == 'approach':
        move = toward
        if in_rng:
            attack = 2 if acd[1] == 0 else (1 if acd[0] == 0 else None)
    elif action == 'kite':
        if dist_x < KITE_DIST - 15:
            move = away
        elif dist_x > KITE_DIST + 15:
            move = toward
        if in_rng:
            attack = 2 if acd[1] == 0 else (1 if acd[0] == 0 else None)
    elif action == 'retreat':
        move = away
        if in_rng:
            attack = 2 if acd[1] == 0 else (1 if acd[0] == 0 else None)
    elif action == 'dash_in':
        if dcd == 0:
            dash = toward
        else:
            move = toward

    # Wall safety
    if fx < 70:
        if move == 'left': move = 'right'
        if dash == 'left': dash = None
    elif fx > SCREEN_W - 70:
        if move == 'right': move = 'left'
        if dash == 'right': dash = None
    if dash == 'left' and fx < 130: dash = None; move = 'right'
    if dash == 'right' and fx > SCREEN_W - 130: dash = None; move = 'left'
    if attack and not in_rng:
        attack = None
    return move, attack, dash


# ═══════════════════════════════════════════════════════════
# MAIN ENTRY POINT  –  v15 Never-Miss Aggressor
# ═══════════════════════════════════════════════════════════
def make_move(fighter, opponent, saved_data):
    if not saved_data or not isinstance(saved_data, dict) or 'frame' not in saved_data:
        saved_data = {'frame': 0, 'retreat': 0, 'last_ohp': 100}

    frame = saved_data.get('frame', 0) + 1
    saved_data['frame'] = frame

    fx, fy = fighter['x'], fighter['y']
    ox, oy = opponent['x'], opponent['y']
    fhp    = fighter['health']
    ohp    = opponent['health']
    dist_x = abs(fx - ox)
    dist_y = abs(fy - oy)
    hp_diff = fhp - ohp
    acd = fighter['attack_cooldown']
    dcd = fighter['dash_cooldown']

    # ── helpers ──
    can_light = acd[0] == 0
    can_heavy = acd[1] == 0
    can_attack = can_light or can_heavy
    min_cd = min(acd[0], acd[1])
    we_left = fx < ox
    toward = 'right' if we_left else 'left'
    away   = 'left'  if we_left else 'right'
    opp_locked = opponent.get('attacking', False)

    HIT_Y = 180  # attack when dist_y < 180 → matches collision rect (fighter height=180)
    in_x_range = dist_x < RANGE
    in_hit_range = in_x_range and dist_y < HIT_Y

    # ── track chase stalemate ──
    prev_dx = saved_data.get('prev_dx', 999)
    chase_count = saved_data.get('chase', 0)
    if can_attack and abs(dist_x - prev_dx) <= 10 and 190 <= dist_x <= 250:
        chase_count += 1
    else:
        chase_count = 0
    saved_data['prev_dx'] = dist_x
    saved_data['chase'] = chase_count

    # ── LOCKED in attack animation → nothing we can do ──
    if fighter.get('attacking', False):
        return _ret(None, None, None, saved_data,
                    f'LK|f{frame}|hp:{fhp}|oh:{ohp}')

    # ── RETREAT PHASE ──
    # After attacking, walk away a few frames to avoid infinite hitstun loop.
    # F1.alive checked first → mutual death = we lose. Must break the loop.
    retreat_left = saved_data.get('retreat', 0)
    if retreat_left > 0:
        saved_data['retreat'] = retreat_left - 1
        # If opponent chases into hit range and we can attack → free punish
        if in_hit_range and can_attack:
            atk = 2 if can_heavy else 1
            saved_data['retreat'] = 2
            return _ret(away, atk, None, saved_data,
                        f'RH!|dx:{dist_x:.0f}|dy:{dist_y:.0f}')
        mv = _wall_safe(away, fx)
        ds = None
        if dcd == 0 and dist_x < 140 and retreat_left >= 2:
            if _can_dash(away, fx):
                ds = away
                saved_data['retreat'] = 0
        return _ret(mv, None, ds, saved_data,
                    f'RET{retreat_left}|dx:{dist_x:.0f}')

    # ══════════════════════════════════════════════════════════
    #  PHASE 1 — IN HIT RANGE (X close + Y close) + CAN ATTACK
    # ══════════════════════════════════════════════════════════
    if in_hit_range and can_attack:
        atk = 2 if can_heavy else 1   # always heavy when hit is guaranteed
        ds = None
        if dcd == 0 and _can_dash(away, fx):
            ds = away
        mv = _wall_safe(away, fx)
        saved_data['retreat'] = 2 if not ds else 0
        tag = 'P!' if opp_locked else ('H!' if atk == 2 else 'L!')
        return _ret(mv, atk, ds, saved_data,
                    f'{tag}|dx:{dist_x:.0f}|dy:{dist_y:.0f}|hp:{hp_diff}')

    # ══════════════════════════════════════════════════════════
    #  PHASE 1b — IN X-RANGE BUT Y-SEPARATED → DON'T ATTACK (would miss!)
    # ══════════════════════════════════════════════════════════
    if in_x_range and can_attack and dist_y >= HIT_Y:
        # Opponent is airborne. If we attack now, it MISSES and we waste
        # heavy CD (100 frames!) for 0 damage. Just hold position.
        mv = None
        if dist_x > 165: mv = toward
        elif dist_x < 40: mv = away
        return _ret(_wall_safe(mv, fx), None, None, saved_data,
                    f'YHOLD|dy:{dist_y:.0f}|dx:{dist_x:.0f}|cd:{min_cd}')

    # ══════════════════════════════════════════════════════════
    #  PHASE 2 — IN X-RANGE + NO ATTACK (on cooldown)
    # ══════════════════════════════════════════════════════════
    if in_x_range and not can_attack:
        # Opponent locked + our CD almost done → wait for him to finish animation
        if opp_locked and min_cd <= 25:
            mv = None
            if dist_x > 165: mv = toward
            elif dist_x < 40: mv = away
            return _ret(_wall_safe(mv, fx), None, None, saved_data,
                        f'PW|cd:{min_cd}|dx:{dist_x:.0f}')
        # CD almost ready → hold position
        if min_cd <= 8:
            mv = None
            if dist_x > 165: mv = toward
            elif dist_x < 40: mv = away
            return _ret(_wall_safe(mv, fx), None, None, saved_data,
                        f'WAIT|cd:{min_cd}|dx:{dist_x:.0f}')
        # On long CD → back off (dash if very close)
        mv = away
        ds = None
        if dcd == 0 and min_cd > 25 and dist_x < 60:
            if _can_dash(away, fx):
                ds = away
        return _ret(_wall_safe(mv, fx), None, ds, saved_data,
                    f'KOUT|cd:{min_cd}|dx:{dist_x:.0f}')

    # ══════════════════════════════════════════════════════════
    #  PHASE 3 — OUT OF RANGE
    # ══════════════════════════════════════════════════════════

    # 3a — Opponent locked in animation + we can attack → rush for free punish
    if opp_locked and can_attack and dist_x < 350:
        return _ret(_wall_safe(toward, fx), None, None, saved_data,
                    f'PUN|dx:{dist_x:.0f}')

    # 3b — We can attack → approach to get in range
    if can_attack:
        ds = None
        # Dash in if far enough away OR stuck in chase stalemate for 6+ frames
        if dcd == 0 and (dist_x > 350 or chase_count >= 6):
            if _can_dash(toward, fx):
                ds = toward
                saved_data['chase'] = 0
        return _ret(_wall_safe(toward, fx), None, ds, saved_data,
                    f'RUSH|dx:{dist_x:.0f}|hp:{hp_diff}|ch:{chase_count}')

    # 3c — On cooldown → kite at safe distance, approach when CD almost done
    if min_cd <= 10:
        mv = toward
        tag = f'APPR|cd:{min_cd}|dx:{dist_x:.0f}'
    elif opp_locked and dist_x < 350:
        mv = toward
        tag = f'PAPP|cd:{min_cd}|dx:{dist_x:.0f}'
    else:
        if dist_x < KITE_DIST - 15:
            mv = away
        elif dist_x > KITE_DIST + 40:
            mv = toward
        else:
            mv = None
        tag = f'KITE|cd:{min_cd}|dx:{dist_x:.0f}'

    # Behind in HP → don't retreat, stay aggressive
    if hp_diff < -10 and mv == away:
        mv = None
        tag = f'HOLD|cd:{min_cd}|dx:{dist_x:.0f}|hp:{hp_diff}'

    return _ret(_wall_safe(mv, fx), None, None, saved_data, tag)


# ── tiny helpers ──────────────────────────────────────────
def _ret(move, attack, dash, saved_data, debug):
    """ALL returns go through here. Jump = True (no advantage to staying grounded)."""
    return {'move': move, 'attack': attack, 'jump': True, 'dash': dash,
            'debug': debug, 'saved_data': saved_data}

def _wall_safe(mv, fx):
    if mv == 'left' and fx < 70: return 'right'
    if mv == 'right' and fx > SCREEN_W - 70: return 'left'
    return mv

def _can_dash(direction, fx):
    if direction == 'left':  return fx > 130
    if direction == 'right': return fx < SCREEN_W - 130
    return False


if __name__ == "__main__":
    input_data = input()
    json_data = json.loads(input_data)
    result = make_move(json_data['fighter'], json_data['opponent'],
                       json_data.get('saved_data', {}))
    print(json.dumps(result))
	
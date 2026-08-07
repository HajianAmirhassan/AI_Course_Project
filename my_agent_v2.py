"""
Fighting Agent v2 – Advanced AI with Opponent Tracking & Minimax
================================================================
Key improvements over v13:
  - Light attack priority (0.4 dmg/frame vs 0.2 for heavy)
  - Heavy ONLY during punish windows (opponent locked)
  - Opponent CD tracking via saved_data
  - Rich heuristic (8 scoring components)
  - Kite at 185px (1 frame to engage) instead of 210px
  - jump=False for stable positioning
  - Minimax depth 2 with accurate opponent model
"""

import json
import math

# ═══════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════
SCREEN_W = 1000
TOTAL_FRAMES = 3600
SPEED = 5
RANGE = 180
KITE_DIST = 185
SIM_STEPS = 10
WALL_INNER = 70
WALL_DANGER = 40
INF = float('inf')

# Abstract Actions (plain strings, no Enum)
ENGAGE = 'en'
STRIKE_LIGHT = 'sl'
STRIKE_HEAVY = 'sh'
STRIKE_RETREAT = 'sr'
DASH_ENGAGE = 'de'
PUNISH = 'pu'
RETREAT = 're'
DASH_RETREAT = 'dr'
KITE = 'ki'
BAIT = 'ba'
HOLD = 'ho'
CORNER_TRAP = 'ct'
STALL = 'st'
DESPERATE = 'da'


# ═══════════════════════════════════════════════════════════
# OPPONENT MODEL TRACKING
# ═══════════════════════════════════════════════════════════
def update_opponent_model(sd, fighter, opponent):
    """Track opponent state across frames via saved_data."""
    ox = opponent['x']
    opp_atk = opponent['attacking']
    ohp = opponent['health']
    mhp = fighter['health']

    prev_ox = sd.get('pox', ox)
    prev_opp_atk = sd.get('poa', False)
    prev_ohp = sd.get('poh', ohp)
    prev_mhp = sd.get('pmh', mhp)

    opp_dx = abs(ox - prev_ox)

    # Detect opponent dashing (speed > 20px/frame)
    if opp_dx > 20:
        sd['od'] = 1  # opp is dashing this frame
        sd['odc'] = 50
        # During dash, attack CDs FREEZE - don't decrement
    else:
        was_dashing = sd.get('od', 0)
        sd['od'] = 0
        if not was_dashing:
            # Normal frame: tick estimated cooldowns
            if sd.get('olc', 0) > 0:
                sd['olc'] = sd['olc'] - 1
            if sd.get('ohc', 0) > 0:
                sd['ohc'] = sd['ohc'] - 1

    # Dash CD always ticks (even during dash)
    if sd.get('odc', 0) > 0:
        sd['odc'] = sd['odc'] - 1

    # Detect opponent ATTACK START
    if opp_atk and not prev_opp_atk:
        sd['oas'] = sd.get('f', 0)  # attack start frame
        my_hp_loss = prev_mhp - mhp
        if my_hp_loss >= 15:
            sd['oat'] = 'h'
        elif my_hp_loss > 0:
            sd['oat'] = 'l'
        else:
            sd['oat'] = 'm'  # miss

    # Detect opponent ATTACK END
    if not opp_atk and prev_opp_atk:
        atk_type = sd.get('oat', 'm')
        duration = sd.get('f', 0) - sd.get('oas', 0)
        if atk_type == 'h':
            sd['ohc'] = 100
        elif atk_type == 'l':
            sd['olc'] = 25
        else:
            # Miss - guess from duration
            if duration > 22:
                sd['ohc'] = 100
            else:
                sd['olc'] = 25

    # Detect HIT on opponent (we damaged them)
    opp_hp_loss = prev_ohp - ohp
    if opp_hp_loss > 0:
        sd['ogh'] = 1
        sd['ohf'] = sd.get('f', 0)

    # After hit stun (~15 frames), opponent light CD resets to 25
    if sd.get('ogh', 0) and sd.get('f', 0) - sd.get('ohf', 0) > 15:
        sd['olc'] = max(sd.get('olc', 0), 25)
        sd['ogh'] = 0

    # Save for next frame
    sd['pox'] = ox
    sd['poa'] = opp_atk
    sd['poh'] = ohp
    sd['pmh'] = mhp
    return sd


# ═══════════════════════════════════════════════════════════
# HEURISTIC (8 scoring components)
# ═══════════════════════════════════════════════════════════
def heuristic(fhp, ohp, fx, ox, f_lcd, f_hcd, opp_lcd, opp_hcd, frame, opp_atk):
    # Terminal
    if fhp <= 0: return -100000
    if ohp <= 0: return 100000

    hp_diff = fhp - ohp
    dist = abs(fx - ox)
    can_atk = f_lcd <= 0 or f_hcd <= 0
    opp_can_atk = opp_lcd <= 0 or opp_hcd <= 0
    min_cd = min(f_lcd, f_hcd)
    time_left = max(TOTAL_FRAMES - frame, 1)

    score = 0.0

    # A. HP advantage
    score += hp_diff * 15.0
    if fhp < 20: score -= 50
    if fhp < 10: score -= 100

    # B. Positional score
    if can_atk:
        if dist < RANGE:
            score += 150
            if opp_atk:
                score += 200  # free hit on locked opponent
        elif dist < 220:
            score += 50
        else:
            score -= (dist - RANGE) * 0.8
    else:
        if dist < 140:
            score -= 80
        elif dist < RANGE:
            score -= 40
        elif 175 <= dist <= 200:
            score += 40  # kite sweet spot
        else:
            score -= abs(dist - KITE_DIST) * 0.2

    # C. Cooldown / tempo advantage
    if can_atk and not opp_can_atk:
        score += 80
    elif not can_atk and opp_can_atk:
        score -= 60
    score += max(0, 30 - min_cd) * 3

    # D. Opponent locked
    if opp_atk:
        if can_atk and dist < RANGE:
            score += 300
        elif can_atk and dist < 300:
            score += 150
        else:
            score += 50

    # E. Wall position
    if fx < 80 or fx > SCREEN_W - 80:
        score -= 60
    if fx < 40 or fx > SCREEN_W - 40:
        score -= 100
    if ox < 80 or ox > SCREEN_W - 80:
        score += 30

    # F. Side advantage (LEFT exploits opponent retreat bug)
    if fx < ox:
        score += 10

    # G. Time pressure
    if time_left < 900:
        urgency = (900 - time_left) / 900.0
        if hp_diff > 0:
            score += hp_diff * urgency * 8
            if dist > 250:
                score += 40 * urgency
        else:
            score -= abs(hp_diff) * urgency * 8
            if dist < RANGE and can_atk:
                score += 60 * urgency

    # H. DPS efficiency
    if can_atk and dist < RANGE:
        if f_lcd <= 0:
            score += 40
        if f_hcd <= 0 and opp_atk:
            score += 80

    return score


# ═══════════════════════════════════════════════════════════
# FORWARD SIMULATION
# ═══════════════════════════════════════════════════════════
def _clamp(v, lo, hi):
    if v < lo: return lo
    if v > hi: return hi
    return v


def simulate_action(action, fx, fhp, ox, ohp, f_lcd, f_hcd, f_dcd,
                     opp_lcd, opp_hcd, opp_dcd, frame, opp_atk):
    """Simulate SIM_STEPS frames of executing action."""
    hit = False
    opp_lock_frames = 0
    if opp_atk:
        opp_lock_frames = 15  # estimate remaining lock

    for _ in range(SIM_STEPS):
        # Tick CDs
        if f_lcd > 0: f_lcd -= 1
        if f_hcd > 0: f_hcd -= 1
        if f_dcd > 0: f_dcd -= 1
        if opp_lcd > 0: opp_lcd -= 1
        if opp_hcd > 0: opp_hcd -= 1
        if opp_dcd > 0: opp_dcd -= 1

        sign = 1 if fx < ox else -1
        dist = abs(fx - ox)

        # Execute our action
        if action == ENGAGE:
            fx += SPEED * sign
        elif action == STRIKE_LIGHT:
            if dist < RANGE and f_lcd <= 0 and not hit:
                ohp -= 10; f_lcd = 25; hit = True
            fx -= SPEED * sign * 0.5  # micro retreat
        elif action == STRIKE_HEAVY:
            if dist < RANGE and f_hcd <= 0 and not hit:
                ohp -= 20; f_hcd = 100; hit = True
        elif action == STRIKE_RETREAT:
            if dist < RANGE and not hit:
                if f_lcd <= 0:
                    ohp -= 10; f_lcd = 25; hit = True
                elif f_hcd <= 0:
                    ohp -= 20; f_hcd = 100; hit = True
            fx -= SPEED * sign
        elif action == DASH_ENGAGE:
            if f_dcd <= 0:
                fx += 300 * sign; f_dcd = 50
            else:
                fx += SPEED * sign
        elif action == PUNISH:
            if dist >= RANGE:
                fx += SPEED * sign
            elif not hit:
                if f_hcd <= 0:
                    ohp -= 20; f_hcd = 100; hit = True
                elif f_lcd <= 0:
                    ohp -= 10; f_lcd = 25; hit = True
        elif action == RETREAT:
            fx -= SPEED * sign
        elif action == DASH_RETREAT:
            if f_dcd <= 0:
                fx -= 300 * sign; f_dcd = 50
            else:
                fx -= SPEED * sign
        elif action == KITE:
            if dist < KITE_DIST - 10:
                fx -= SPEED * sign
            elif dist > KITE_DIST + 20:
                fx += SPEED * sign
        elif action == BAIT:
            target = 190
            if dist < target - 5:
                fx -= SPEED * sign
            elif dist > target + 5:
                fx += SPEED * sign
        elif action == HOLD:
            pass
        elif action == CORNER_TRAP:
            fx += SPEED * sign
        elif action == STALL:
            fx -= SPEED * sign
        elif action == DESPERATE:
            fx += SPEED * sign
            if dist < RANGE and not hit:
                if f_lcd <= 0:
                    ohp -= 10; f_lcd = 25; hit = True
                elif f_hcd <= 0:
                    ohp -= 20; f_hcd = 100; hit = True

        # Simulate opponent response (model agent.py behavior)
        dist = abs(fx - ox)
        if opp_lock_frames > 0:
            opp_lock_frames -= 1
        else:
            opp_can = opp_lcd <= 0 or opp_hcd <= 0
            opp_sign = 1 if ox < fx else -1
            if opp_can and dist < RANGE:
                if opp_hcd <= 0:
                    fhp -= 20; opp_hcd = 100
                elif opp_lcd <= 0:
                    fhp -= 10; opp_lcd = 25
            elif opp_can and dist >= RANGE:
                ox += SPEED * opp_sign
            elif not opp_can:
                if opp_dcd <= 0 and dist < RANGE + 50:
                    ox -= 300 * opp_sign
                    opp_dcd = 50
                else:
                    ox -= SPEED * opp_sign

        fx = _clamp(fx, 60, SCREEN_W - 60)
        ox = _clamp(ox, 60, SCREEN_W - 60)
        if fhp <= 0 or ohp <= 0:
            break

    return (fx, max(0, fhp), ox, max(0, ohp),
            f_lcd, f_hcd, f_dcd, opp_lcd, opp_hcd, opp_dcd,
            frame + SIM_STEPS, opp_lock_frames > 0)


# ═══════════════════════════════════════════════════════════
# VALID ACTION FILTERING
# ═══════════════════════════════════════════════════════════
def get_valid_actions(f_lcd, f_hcd, f_dcd, dist, opp_atk, fx, ox, hp_diff, frame):
    actions = [HOLD, RETREAT]

    can_light = f_lcd <= 0
    can_heavy = f_hcd <= 0
    can_atk = can_light or can_heavy
    can_dash = f_dcd <= 0
    in_range = dist < RANGE
    time_left = TOTAL_FRAMES - frame

    if can_atk and in_range:
        if can_light: actions.append(STRIKE_LIGHT)
        if can_heavy: actions.append(STRIKE_HEAVY)
        actions.append(STRIKE_RETREAT)
    if can_atk and not in_range:
        actions.append(ENGAGE)
    if can_dash and not in_range and dist > 250:
        actions.append(DASH_ENGAGE)
    if opp_atk and can_atk:
        actions.append(PUNISH)

    if not can_atk:
        actions.append(KITE)
    if can_dash and in_range and not can_atk:
        actions.append(DASH_RETREAT)
    if not can_atk and 160 < dist < 220:
        actions.append(BAIT)

    if ox < 120 or ox > SCREEN_W - 120:
        actions.append(CORNER_TRAP)

    if time_left < 350 and hp_diff > 15:
        actions.append(STALL)
    if time_left < 500 and hp_diff < -10:
        actions.append(DESPERATE)

    return actions


# ═══════════════════════════════════════════════════════════
# MINIMAX WITH ALPHA-BETA (depth 2)
# ═══════════════════════════════════════════════════════════
def minimax(fx, fhp, ox, ohp, f_lcd, f_hcd, f_dcd,
            opp_lcd, opp_hcd, opp_dcd, frame, opp_atk,
            depth, maximising, alpha, beta):
    if depth == 0 or fhp <= 0 or ohp <= 0:
        return heuristic(fhp, ohp, fx, ox, f_lcd, f_hcd, opp_lcd, opp_hcd, frame, opp_atk), None

    dist = abs(fx - ox)

    if maximising:
        best = -INF
        best_act = KITE
        for act in get_valid_actions(f_lcd, f_hcd, f_dcd, dist, opp_atk, fx, ox, fhp - ohp, frame):
            nfx, nfhp, nox, nohp, nl, nh, nd, nol, noh, nod, nf, noa = simulate_action(
                act, fx, fhp, ox, ohp, f_lcd, f_hcd, f_dcd,
                opp_lcd, opp_hcd, opp_dcd, frame, opp_atk)
            sc, _ = minimax(nfx, nfhp, nox, nohp, nl, nh, nd,
                            nol, noh, nod, nf, noa,
                            depth - 1, False, alpha, beta)
            if sc > best:
                best, best_act = sc, act
            alpha = max(alpha, sc)
            if beta <= alpha:
                break
        return best, best_act
    else:
        worst = INF
        # Model opponent's possible responses
        opp_can = opp_lcd <= 0 or opp_hcd <= 0
        scenarios = []
        if opp_can and dist < RANGE:
            if opp_hcd <= 0:
                scenarios.append((-20, opp_lcd, 100, opp_dcd))
            if opp_lcd <= 0:
                scenarios.append((-10, 25, opp_hcd, opp_dcd))
        if not scenarios:
            # Opponent retreats or approaches
            scenarios.append((0, opp_lcd, opp_hcd, opp_dcd))

        opp_sign = 1 if ox < fx else -1
        for dmg, s_olc, s_ohc, s_odc in scenarios:
            n_fhp = max(0, fhp + dmg)
            n_ox = _clamp(ox + SPEED * SIM_STEPS * opp_sign * (1 if opp_can else -1) * 0.3,
                          60, SCREEN_W - 60)
            sc, _ = minimax(fx, n_fhp, n_ox, ohp, f_lcd, f_hcd, f_dcd,
                            s_olc, s_ohc, s_odc,
                            frame + SIM_STEPS, False,
                            depth - 1, True, alpha, beta)
            if sc < worst:
                worst = sc
            beta = min(beta, sc)
            if beta <= alpha:
                break
        return worst, None


# ═══════════════════════════════════════════════════════════
# ACTION -> COMMANDS MAPPING
# ═══════════════════════════════════════════════════════════
def to_commands(action, fighter, opponent):
    fx, ox = fighter['x'], opponent['x']
    dist = abs(fx - ox)
    we_left = fx < ox
    toward = 'right' if we_left else 'left'
    away = 'left' if we_left else 'right'
    acd = fighter['attack_cooldown']
    dcd = fighter['dash_cooldown']
    in_rng = dist < RANGE

    move, attack, jump, dash = None, None, False, None

    if action == ENGAGE:
        move = toward
    elif action == STRIKE_LIGHT:
        move = away
        if in_rng and acd[0] == 0:
            attack = 1
    elif action == STRIKE_HEAVY:
        move = None
        if in_rng and acd[1] == 0:
            attack = 2
    elif action == STRIKE_RETREAT:
        move = away
        if in_rng:
            if acd[0] == 0:
                attack = 1
            elif acd[1] == 0:
                attack = 2
    elif action == DASH_ENGAGE:
        if dcd == 0:
            dash = toward
        else:
            move = toward
    elif action == PUNISH:
        if in_rng:
            if acd[1] == 0:
                attack = 2
            elif acd[0] == 0:
                attack = 1
            move = None
        else:
            move = toward
    elif action == RETREAT:
        move = away
    elif action == DASH_RETREAT:
        if dcd == 0:
            dash = away
        else:
            move = away
    elif action == KITE:
        if dist < KITE_DIST - 10:
            move = away
        elif dist > KITE_DIST + 20:
            move = toward
    elif action == BAIT:
        target = 190
        if dist < target - 5:
            move = away
        elif dist > target + 5:
            move = toward
    elif action == HOLD:
        pass
    elif action == CORNER_TRAP:
        move = toward
        if in_rng:
            if acd[0] == 0: attack = 1
            elif acd[1] == 0: attack = 2
    elif action == STALL:
        move = away
        if dcd == 0 and dist < 250:
            if (away == 'left' and fx > 130) or (away == 'right' and fx < SCREEN_W - 130):
                dash = away
    elif action == DESPERATE:
        move = toward
        if in_rng:
            if acd[0] == 0: attack = 1
            elif acd[1] == 0: attack = 2
        if dcd == 0 and dist > 250:
            if (toward == 'left' and fx > 130) or (toward == 'right' and fx < SCREEN_W - 130):
                dash = toward

    # Wall safety
    if fx < WALL_INNER:
        if move == 'left': move = 'right'
        if dash == 'left': dash = None
    if fx > SCREEN_W - WALL_INNER:
        if move == 'right': move = 'left'
        if dash == 'right': dash = None
    if dash == 'left' and fx < 130:
        dash = None; move = 'right'
    if dash == 'right' and fx > SCREEN_W - 130:
        dash = None; move = 'left'
    if attack and not in_rng:
        attack = None

    return move, attack, jump, dash


# ═══════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════
def make_move(fighter, opponent, saved_data):
    # 1. INIT
    if not saved_data or not isinstance(saved_data, dict) or 'f' not in saved_data:
        saved_data = {'f': 0, 'olc': 0, 'ohc': 0, 'odc': 0}

    sd = saved_data
    sd['f'] = sd.get('f', 0) + 1
    frame = sd['f']

    # 2. UPDATE OPPONENT MODEL
    sd = update_opponent_model(sd, fighter, opponent)

    # 3. PARSE STATE
    fx, fy = fighter['x'], fighter['y']
    ox, oy = opponent['x'], opponent['y']
    dist_x = abs(fx - ox)
    dist_y = abs(fy - oy)
    hp_diff = fighter['health'] - opponent['health']
    acd = fighter['attack_cooldown']
    dcd = fighter['dash_cooldown']
    can_light = acd[0] == 0
    can_heavy = acd[1] == 0
    can_attack = can_light or can_heavy
    min_cd = min(acd[0], acd[1])
    in_range = dist_x < RANGE and dist_y < RANGE
    opp_locked = opponent.get('attacking', False)
    time_left = max(TOTAL_FRAMES - frame, 0)
    we_left = fx < ox
    toward = 'right' if we_left else 'left'
    away = 'left' if we_left else 'right'

    opp_lcd = sd.get('olc', 0)
    opp_hcd = sd.get('ohc', 0)
    opp_dcd = sd.get('odc', 0)
    opp_can_atk = opp_lcd <= 0 or opp_hcd <= 0

    def _out(mv, atk, jmp, ds, tag):
        if atk:
            sd['ja'] = 1
        return {'move': mv, 'attack': atk, 'jump': jmp, 'dash': ds,
                'debug': tag, 'saved_data': sd}

    # 4. LOCKED IN OWN ANIMATION (headless sim may call us)
    if fighter.get('attacking', False):
        return _out(None, None, False, None, f'LK|f{frame}')

    # 5. POST-ATTACK MICRO-RETREAT (one frame)
    if sd.get('ja') and not fighter.get('attacking', False):
        sd['ja'] = 0
        # If opponent is locked, DON'T retreat - stay for more free hits
        if opp_locked and dist_x < RANGE + 30:
            mv = None
            if dist_x > 170: mv = toward
            return _out(mv, None, False, None, f'PSTAY|dx:{dist_x:.0f}')
        mv = away
        if away == 'left' and fx < WALL_INNER: mv = None
        if away == 'right' and fx > SCREEN_W - WALL_INNER: mv = None
        return _out(mv, None, False, None, f'RSET|dx:{dist_x:.0f}')

    # ═══════════════════════════════════════════════════════
    # FAST PATHS (~80% of frames)
    # ═══════════════════════════════════════════════════════

    # FP1: PUNISH – opponent locked + in range + attack ready
    if opp_locked and in_range and can_attack:
        # Use HEAVY for free 20 dmg if available, else LIGHT
        atk = 2 if can_heavy else 1
        return _out(None, atk, False, None, f'P!|dx:{dist_x:.0f}|hp:{hp_diff}')

    # FP2: PUNISH RUSH – opponent locked + out of range + close enough
    if opp_locked and not in_range and can_attack and dist_x < 300:
        mv = toward
        if fx < WALL_INNER: mv = 'right'
        if fx > SCREEN_W - WALL_INNER: mv = 'left'
        return _out(mv, None, False, None, f'PUN|dx:{dist_x:.0f}')

    # FP3: STRIKE LIGHT – in range + light ready (2x DPS priority!)
    if in_range and can_light:
        mv = away
        if away == 'left' and fx < WALL_INNER: mv = None
        if away == 'right' and fx > SCREEN_W - WALL_INNER: mv = None
        return _out(mv, 1, False, None, f'SL|dx:{dist_x:.0f}|hp:{hp_diff}')

    # FP4: STRIKE HEAVY – in range + only heavy + opponent locked
    if in_range and can_heavy and not can_light and opp_locked:
        return _out(None, 2, False, None, f'SH|dx:{dist_x:.0f}|hp:{hp_diff}')

    # FP5: STRIKE HEAVY fallback – in range + only heavy available + no light
    if in_range and can_heavy and not can_light:
        mv = away
        if away == 'left' and fx < WALL_INNER: mv = None
        if away == 'right' and fx > SCREEN_W - WALL_INNER: mv = None
        return _out(mv, 2, False, None, f'SHf|dx:{dist_x:.0f}|hp:{hp_diff}')

    # FP6: PUNISH WAIT – in range + no atk + opponent locked + cd <= 20
    if in_range and not can_attack and opp_locked and min_cd <= 20:
        mv = None
        if dist_x > 165: mv = toward
        return _out(mv, None, False, None, f'PW|cd:{min_cd}|dx:{dist_x:.0f}')

    # FP7: WAIT – in range + no attack + cd <= 5
    if in_range and not can_attack and min_cd <= 5:
        mv = None
        if dist_x > 165: mv = toward
        return _out(mv, None, False, None, f'WAIT|cd:{min_cd}|dx:{dist_x:.0f}')

    # FP8: RETREAT – in range + no attack + cd > 5 + opponent not locked
    if in_range and not can_attack and not opp_locked:
        mv = away
        ds = None
        # Emergency dash if very close and long CD
        if dcd == 0 and min_cd > 30 and dist_x < 50:
            if (away == 'left' and fx > 130) or (away == 'right' and fx < SCREEN_W - 130):
                ds = away
        if fx < WALL_INNER: mv = 'right'; ds = None if ds == 'left' else ds
        if fx > SCREEN_W - WALL_INNER: mv = 'left'; ds = None if ds == 'right' else ds
        return _out(mv, None, False, ds, f'KOUT|cd:{min_cd}|dx:{dist_x:.0f}')

    # FP9: IN RANGE + no attack + opponent locked + cd > 20
    # Stay close but safe
    if in_range and not can_attack and opp_locked:
        mv = None
        if dist_x > 170: mv = toward
        return _out(mv, None, False, None, f'PW2|cd:{min_cd}|dx:{dist_x:.0f}')

    # FP10: STALL – endgame + winning
    if time_left < 600 and hp_diff > 10:
        mv = away
        ds = None
        if dcd == 0 and dist_x < 250:
            if (away == 'left' and fx > 130) or (away == 'right' and fx < SCREEN_W - 130):
                ds = away
        if fx < WALL_INNER: mv = 'right'
        if fx > SCREEN_W - WALL_INNER: mv = 'left'
        return _out(mv, None, False, ds, f'FLEE|hp:{hp_diff}|dx:{dist_x:.0f}')

    # FP11: DESPERATE – endgame + losing
    if time_left < 400 and hp_diff < -10 and not in_range:
        mv = toward
        ds = None
        if dcd == 0 and dist_x > 250:
            if (toward == 'left' and fx > 130) or (toward == 'right' and fx < SCREEN_W - 130):
                ds = toward
        if fx < WALL_INNER: mv = 'right'
        if fx > SCREEN_W - WALL_INNER: mv = 'left'
        return _out(mv, None, False, ds, f'CLUTCH|hp:{hp_diff}|dx:{dist_x:.0f}')

    # FP12: RUSH – out of range + attack ready
    if not in_range and can_attack:
        mv = toward
        # If big HP lead, kite instead of rushing
        if hp_diff > 20:
            if dist_x < KITE_DIST - 10:
                mv = away
            elif dist_x > KITE_DIST + 20:
                mv = toward
            else:
                mv = None
            tag = f'DEF|dx:{dist_x:.0f}|hp:{hp_diff}'
        else:
            tag = f'RUSH|dx:{dist_x:.0f}|hp:{hp_diff}'
        if fx < WALL_INNER: mv = 'right'
        if fx > SCREEN_W - WALL_INNER: mv = 'left'
        return _out(mv, None, False, None, tag)

    # ═══════════════════════════════════════════════════════
    # MINIMAX for remaining ~20% ambiguous cases
    # (out of range + no attack + opponent not locked)
    # ═══════════════════════════════════════════════════════
    score, best_action = minimax(
        fx, fighter['health'], ox, opponent['health'],
        acd[0], acd[1], dcd,
        opp_lcd, opp_hcd, opp_dcd,
        frame, opp_locked,
        depth=2, maximising=True,
        alpha=-INF, beta=INF
    )

    if best_action is None:
        best_action = KITE

    move, attack, jump, dash = to_commands(best_action, fighter, opponent)

    if attack:
        sd['ja'] = 1
    sd['la'] = best_action

    return {'move': move, 'attack': attack, 'jump': jump, 'dash': dash,
            'debug': f'{best_action}|s:{score:.0f}|dx:{dist_x:.0f}|hp:{hp_diff}',
            'saved_data': sd}


if __name__ == "__main__":
    input_data = input()
    json_data = json.loads(input_data)
    result = make_move(json_data['fighter'], json_data['opponent'],
                       json_data.get('saved_data', {}))
    print(json.dumps(result))

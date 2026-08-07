"""
Fighting Agent v10 – Min-Max Aggressive Recovery
=================================================
Key insight: RETREATING WHEN BEHIND = GUARANTEED LOSS BY TIMEOUT.
When health is behind, we MUST be more aggressive to recover.

Uses Min-Max with alpha-beta pruning + heuristic.
Fast-paths for obvious situations, Min-Max for strategy.

Fixes over v9:
  - When behind: heuristic REWARDS being close (aggression, not retreat)
  - Retreat loop breaker: forced approach after consecutive retreats
  - Time-deficit urgency: less time + behind = approach at all costs
  - Better cooldown tracking: approach when attack is about to be ready
"""

import json

RANGE = 180
SCREEN_W = 1000
TOTAL_FRAMES = 3600
SPEED = 5
DASH_TOTAL = 300
SIM_FRAMES = 8

W_HEALTH   = 10.0
W_DIST     = 1.5
W_COOLDOWN = 3.0
W_POSITION = 0.8
W_TIME     = 1.0


def heuristic(fhp, ohp, fx, ox, f_lcd, f_hcd, f_dcd, frame):
    if fhp <= 0: return -10000
    if ohp <= 0: return  10000

    health_diff = fhp - ohp
    dist = abs(fx - ox)
    can_light = f_lcd <= 0
    can_heavy = f_hcd <= 0
    can_attack = can_light or can_heavy
    min_cd = min(f_lcd, f_hcd)
    time_left = max(TOTAL_FRAMES - frame, 1)

    # ── Distance score: context-dependent ──
    if health_diff >= 0:
        # WINNING: be smart about distance
        if can_attack:
            if dist < RANGE:
                dist_score = 100
            elif dist < RANGE + 60:
                dist_score = 60 - (dist - RANGE)
            else:
                dist_score = -(dist - RANGE) * 0.2
        else:
            if dist < RANGE:
                dist_score = -60          # retreat from danger
            elif dist < RANGE + 50:
                dist_score = 15
            else:
                dist_score = 20
    else:
        # LOSING: MUST BE AGGRESSIVE - distance is the enemy!
        if can_attack:
            if dist < RANGE:
                dist_score = 150          # maximum reward for being in strike range
            elif dist < RANGE + 60:
                dist_score = 80 - (dist - RANGE)
            else:
                dist_score = -(dist - RANGE) * 0.5   # heavy penalty for being far
        else:
            if dist < RANGE:
                dist_score = -30          # still uncomfortable but don't panic
            elif dist < RANGE + 50:
                dist_score = 0            # neutral - attack coming soon
            else:
                dist_score = -(dist - RANGE) * 0.3    # still penalize far distance!

    # ── Cooldown advantage ──
    cd_score = max(0, 25 - min_cd) * 2.5   # reward having attacks ready

    # ── Position safety ──
    if fx < 60 or fx > SCREEN_W - 60:
        pos_score = -40
    elif fx < 130 or fx > SCREEN_W - 130:
        pos_score = -10
    else:
        pos_score = 3

    # ── Time pressure: amplifies health diff as time runs out ──
    if time_left < 900:                       # last 15 seconds
        urgency = (900 - time_left) / 900.0   # 0→1 as time runs out
        if health_diff > 0:
            time_score = health_diff * 3 * urgency   # protect lead
        else:
            time_score = health_diff * 5 * urgency   # urgent to recover!
            # Extra penalty for being far when behind + low time
            if dist > RANGE + 50:
                time_score -= (dist - RANGE) * urgency * 0.5
    else:
        time_score = 0

    return (W_HEALTH * health_diff + W_DIST * dist_score
          + W_COOLDOWN * cd_score + W_POSITION * pos_score
          + W_TIME * time_score)


# ═══════════════════════════════════════════════════════════
# FORWARD SIMULATION
# ═══════════════════════════════════════════════════════════
def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

def simulate(action, fx, fhp, ox, ohp, f_lcd, f_hcd, f_dcd, frame,
             steps=SIM_FRAMES):
    hit_opp = False
    for _ in range(steps):
        if f_lcd > 0: f_lcd -= 1
        if f_hcd > 0: f_hcd -= 1
        if f_dcd > 0: f_dcd -= 1
        dist = abs(fx - ox)
        sign = 1 if fx < ox else -1

        if action == 'attack_heavy':
            if dist >= RANGE:
                fx += SPEED * sign
            elif f_hcd <= 0 and not hit_opp:
                ohp -= 20; f_hcd = 100; hit_opp = True
            elif f_lcd <= 0 and not hit_opp:
                ohp -= 10; f_lcd = 25;  hit_opp = True
        elif action == 'attack_light':
            if dist >= RANGE:
                fx += SPEED * sign
            elif f_lcd <= 0 and not hit_opp:
                ohp -= 10; f_lcd = 25;  hit_opp = True
        elif action == 'approach':
            fx += SPEED * sign
            if abs(fx - ox) < RANGE:
                if f_hcd <= 0 and not hit_opp:
                    ohp -= 20; f_hcd = 100; hit_opp = True
                elif f_lcd <= 0 and not hit_opp:
                    ohp -= 10; f_lcd = 25;  hit_opp = True
        elif action == 'retreat':
            fx -= SPEED * sign
        elif action == 'dash_in':
            if f_dcd <= 0:
                fx += DASH_TOTAL * sign; f_dcd = 50
            else:
                fx += SPEED * sign
        elif action == 'dash_out':
            if f_dcd <= 0:
                fx -= DASH_TOTAL * sign; f_dcd = 50
            else:
                fx -= SPEED * sign

        dist = abs(fx - ox)
        if dist < RANGE:
            fhp -= 1.5
        elif dist < RANGE + 100:
            ox += SPEED * (-sign)

        fx = _clamp(fx, 60, SCREEN_W - 60)
        ox = _clamp(ox, 60, SCREEN_W - 60)
        if fhp <= 0 or ohp <= 0:
            break
    return fx, max(0, fhp), ox, max(0, ohp), f_lcd, f_hcd, f_dcd, frame + steps


# ═══════════════════════════════════════════════════════════
# MIN-MAX WITH ALPHA-BETA
# ═══════════════════════════════════════════════════════════
def _valid_actions(f_lcd, f_hcd, f_dcd, dist):
    acts = ['approach', 'retreat', 'hold']
    if f_lcd <= 0 and dist < RANGE + 60:
        acts.append('attack_light')
    if f_hcd <= 0 and dist < RANGE + 60:
        acts.append('attack_heavy')
    if f_dcd <= 0:
        acts.append('dash_in')
        if dist < 350:
            acts.append('dash_out')
    return acts

def minimax(fx, fhp, ox, ohp, f_lcd, f_hcd, f_dcd,
            frame, depth, maximising, alpha, beta):
    if depth == 0 or fhp <= 0 or ohp <= 0:
        return heuristic(fhp, ohp, fx, ox, f_lcd, f_hcd, f_dcd, frame), None

    dist = abs(fx - ox)

    if maximising:
        best = -float('inf')
        best_act = 'hold'
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
        for _, dmg in [('h', -20), ('l', -10), ('m', 0)]:
            nfhp = max(0, fhp + dmg)
            nox = _clamp(ox + SPEED * SIM_FRAMES * (-sign), 60, SCREEN_W - 60)
            sc, _ = minimax(fx, nfhp, nox, ohp, f_lcd, f_hcd, f_dcd,
                            frame + SIM_FRAMES, depth - 1, True, alpha, beta)
            if sc < worst:
                worst = sc
            beta = min(beta, sc)
            if beta <= alpha:
                break
        return worst, None


# ═══════════════════════════════════════════════════════════
# ACTION → LOW-LEVEL COMMANDS
# ═══════════════════════════════════════════════════════════
def to_commands(action, fighter, opponent):
    fx, ox = fighter['x'], opponent['x']
    dist_x = abs(fx - ox)
    we_left = fx < ox
    toward = 'right' if we_left else 'left'
    away   = 'left'  if we_left else 'right'
    acd, dcd = fighter['attack_cooldown'], fighter['dash_cooldown']

    move, attack, jump, dash = None, None, True, None
    in_range = dist_x < RANGE

    if action == 'attack_heavy':
        if in_range:
            attack = 2 if acd[1] == 0 else (1 if acd[0] == 0 else None)
            if dist_x > 155:   move = toward
            elif dist_x < 30:  move = away
        else:
            move = toward
    elif action == 'attack_light':
        if in_range:
            attack = 1 if acd[0] == 0 else (2 if acd[1] == 0 else None)
            if dist_x > 155:   move = toward
            elif dist_x < 30:  move = away
        else:
            move = toward
    elif action == 'approach':
        move = toward
        if in_range:
            attack = 2 if acd[1] == 0 else (1 if acd[0] == 0 else None)
    elif action == 'retreat':
        move = away
        if in_range:
            attack = 2 if acd[1] == 0 else (1 if acd[0] == 0 else None)
    elif action == 'dash_in':
        if dcd == 0:
            dash = toward
        else:
            move = toward
        if in_range:
            attack = 2 if acd[1] == 0 else (1 if acd[0] == 0 else None)
    elif action == 'dash_out':
        if dcd == 0 and dist_x < 350:
            dash = away
        else:
            move = away
    elif action == 'hold':
        if in_range:
            attack = 2 if acd[1] == 0 else (1 if acd[0] == 0 else None)

    # Wall safety
    if fx < 60:
        move = 'right'
        if dash == 'left': dash = None
    elif fx > SCREEN_W - 60:
        move = 'left'
        if dash == 'right': dash = None
    if dash == 'left'  and fx < 130:  dash = None; move = 'right'
    if dash == 'right' and fx > SCREEN_W - 130: dash = None; move = 'left'
    if attack and not in_range:
        attack = None
    return move, attack, jump, dash


# ═══════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════
def make_move(fighter, opponent, saved_data):
    if not saved_data or not isinstance(saved_data, dict) or 'frame' not in saved_data:
        saved_data = {'frame': 0, 'retreats': 0}

    frame = saved_data.get('frame', 0) + 1
    consec_retreats = saved_data.get('retreats', 0)
    fx, fy = fighter['x'], fighter['y']
    ox, oy = opponent['x'], opponent['y']
    dist_x = abs(fx - ox)
    dist_y = abs(fy - oy)
    hp_diff = fighter['health'] - opponent['health']
    acd = fighter['attack_cooldown']
    dcd = fighter['dash_cooldown']
    time_left = max(TOTAL_FRAMES - frame, 0)

    if fighter.get('attacking', False):
        saved_data['frame'] = frame
        return {'move': None, 'attack': None, 'jump': True, 'dash': None,
                'debug': f'LK|f{frame}', 'saved_data': saved_data}

    in_range = dist_x < RANGE and dist_y < RANGE
    can_light = acd[0] == 0
    can_heavy = acd[1] == 0
    can_attack = can_light or can_heavy
    we_left = fx < ox
    toward = 'right' if we_left else 'left'
    away   = 'left'  if we_left else 'right'
    min_cd = min(acd[0], acd[1])

    # ── FAST PATH 1: In range WITH attack → hit now ──
    if in_range and can_attack:
        best_atk = 2 if can_heavy else 1
        mv = None
        if dist_x > 155:   mv = toward
        elif dist_x < 30:  mv = away
        elif fx < 60:      mv = 'right'
        elif fx > SCREEN_W - 60: mv = 'left'
        saved_data['frame'] = frame
        saved_data['retreats'] = 0
        return {'move': mv, 'attack': best_atk, 'jump': True, 'dash': None,
                'debug': f'{"H!" if best_atk==2 else "L!"}|dx:{dist_x}|hp:{hp_diff}',
                'saved_data': saved_data}

    # ── FAST PATH 2: In range WITHOUT attack ──
    if in_range and not can_attack:
        # If attack is almost ready (< 8 frames), STAY and wait
        if min_cd <= 8:
            mv = None
            if dist_x > 160: mv = toward
            if fx < 60:  mv = 'right'
            if fx > SCREEN_W - 60: mv = 'left'
            saved_data['frame'] = frame
            saved_data['retreats'] = 0
            return {'move': mv, 'attack': None, 'jump': True, 'dash': None,
                    'debug': f'WAIT|dx:{dist_x}|cd:{min_cd}|hp:{hp_diff}',
                    'saved_data': saved_data}
        # Otherwise retreat briefly
        mv = away
        ds = None
        if dcd == 0 and dist_x < 100:
            if (away == 'left' and fx > 130) or (away == 'right' and fx < SCREEN_W - 130):
                ds = away
        if fx < 60:  mv = 'right'; ds = None if ds == 'left' else ds
        if fx > SCREEN_W - 60: mv = 'left'; ds = None if ds == 'right' else ds
        saved_data['frame'] = frame
        saved_data['retreats'] = consec_retreats + 1
        return {'move': mv, 'attack': None, 'jump': True, 'dash': ds,
                'debug': f'RET|dx:{dist_x}|cd:{min_cd}|hp:{hp_diff}',
                'saved_data': saved_data}

    # ── FAST PATH 3: Endgame with comfortable lead → flee ──
    if time_left < 400 and hp_diff > 20:
        mv = away
        ds = None
        if dcd == 0 and dist_x < 250:
            if (away == 'left' and fx > 130) or (away == 'right' and fx < SCREEN_W - 130):
                ds = away
        if fx < 60:  mv = 'right'
        if fx > SCREEN_W - 60: mv = 'left'
        saved_data['frame'] = frame
        saved_data['retreats'] = 0
        return {'move': mv, 'attack': None, 'jump': True, 'dash': ds,
                'debug': f'DF|dx:{dist_x}|hp:{hp_diff}|t:{time_left}',
                'saved_data': saved_data}

    # ── FAST PATH 4: BEHIND + attack ready → charge in! ──
    if hp_diff < 0 and can_attack and dist_x > RANGE:
        mv = toward
        ds = None
        if dcd == 0 and dist_x > RANGE + 80:
            if (toward == 'left' and fx > 130) or (toward == 'right' and fx < SCREEN_W - 130):
                ds = toward
        if fx < 60:  mv = 'right'
        if fx > SCREEN_W - 60: mv = 'left'
        saved_data['frame'] = frame
        saved_data['retreats'] = 0
        return {'move': mv, 'attack': None, 'jump': True, 'dash': ds,
                'debug': f'CHARG|dx:{dist_x}|hp:{hp_diff}',
                'saved_data': saved_data}

    # ── FAST PATH 5: Retreat loop breaker ──
    # If retreated > 20 consecutive frames, FORCE approach
    if consec_retreats > 20 and dist_x > RANGE:
        mv = toward
        ds = None
        if dcd == 0 and dist_x > RANGE + 100:
            if (toward == 'left' and fx > 130) or (toward == 'right' and fx < SCREEN_W - 130):
                ds = toward
        saved_data['frame'] = frame
        saved_data['retreats'] = 0
        return {'move': mv, 'attack': None, 'jump': True, 'dash': ds,
                'debug': f'BREAK|dx:{dist_x}|hp:{hp_diff}|rt:{consec_retreats}',
                'saved_data': saved_data}

    # ── MIN-MAX DECISION ──
    score, best_action = minimax(
        fx, fighter['health'], ox, opponent['health'],
        acd[0], acd[1], dcd,
        frame, depth=2, maximising=True,
        alpha=-float('inf'), beta=float('inf'))

    if best_action is None:
        best_action = 'approach'

    # Track retreat streaks
    if best_action in ('retreat', 'dash_out', 'hold'):
        saved_data['retreats'] = consec_retreats + 1
    else:
        saved_data['retreats'] = 0

    move, attack, jump, dash = to_commands(best_action, fighter, opponent)
    saved_data['frame'] = frame

    return {
        'move': move, 'attack': attack, 'jump': jump, 'dash': dash,
        'debug': f'{best_action}|s:{score:.0f}|dx:{dist_x}|hp:{hp_diff}',
        'saved_data': saved_data
    }


if __name__ == "__main__":
    input_data = input()
    json_data = json.loads(input_data)
    result = make_move(json_data['fighter'], json_data['opponent'],
                       json_data.get('saved_data', {}))
    print(json.dumps(result))
	
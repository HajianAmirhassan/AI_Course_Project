"""
Headless battle simulator - runs my_agent vs agent without pygame.
Simulates the exact game mechanics from fighter.py to analyze performance.
"""
import json
import importlib.util
import os
import sys
import types

def load_agent_safe(path):
    """Load agent module, handling files with input() at module level."""
    with open(path, 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Create a module with the make_move function only
    mod = types.ModuleType(os.path.basename(path).replace('.py', ''))
    mod.__file__ = path
    
    # Add required imports to module namespace
    import json as _json
    import random as _random
    mod.json = _json
    mod.random = _random
    mod.sys = sys
    mod.directions = ["left", "right"]
    
    # Extract and compile only function definitions + top-level assignments (not input())
    safe_lines = []
    skip_rest = False
    for line in source.split('\n'):
        stripped = line.strip()
        # Stop at if __name__ guard or module-level input/print
        if stripped.startswith('if __name__'):
            skip_rest = True
        if skip_rest:
            continue
        if 'input(' in stripped:
            continue
        if 'json.loads(' in stripped and 'input' in stripped:
            continue
        if 'print(json.dumps' in stripped:
            continue
        if stripped.startswith('result = make_move(') and ('json_data' in stripped or 'fighter_info' in stripped):
            continue
        if stripped.startswith('opponent_info = json_data') or stripped.startswith('fighter_info = json_data') or stripped.startswith('saved_data = json_data'):
            continue
        safe_lines.append(line)
    
    safe_source = '\n'.join(safe_lines)
    exec(compile(safe_source, path, 'exec'), mod.__dict__)
    return mod

my_agent = load_agent_safe(os.path.join(os.path.dirname(__file__), 'my_agent_v2.py'))
opp_agent = load_agent_safe(os.path.join(os.path.dirname(__file__), 'agent.py'))

SC_WIDTH = 1000
SC_HEIGHT = 540
SPEED = 5
DASH_SPEED = 30
GRAVITY = 2
GROUND_Y = SC_HEIGHT - 70  # bottom boundary

class SimFighter:
    def __init__(self, x, player):
        self.x = x
        self.y = 290
        self.width = 120
        self.height = 180
        self.vely = 0
        self.health = 100
        self.attack_cooldown = [0, 0]
        self.dash_cooldown = 0
        self.attacking = False
        self.attack_type = 0
        self.attack_frames_left = 0
        self.jump = False
        self.dashing = False
        self.dash_timer = 0
        self.dash_dir = None
        self.alive = True
        self.hit = False
        self.hit_frames = 0
        self.player = player
        self.saved_data = {}
        self.flip = player == 2

    @property
    def centerx(self):
        return self.x + self.width // 2

    @property
    def centery(self):
        return self.y + self.height // 2

    @property
    def left(self):
        return self.x

    @property
    def right(self):
        return self.x + self.width

    @property
    def bottom(self):
        return self.y + self.height

    def get_fighter_info(self):
        return {
            'x': self.centerx,
            'y': self.centery,
            'health': self.health,
            'attacking': self.attacking,
            'attack_cooldown': [self.attack_cooldown[0], self.attack_cooldown[1]],
            'jump': self.jump,
            'dash_cooldown': self.dash_cooldown
        }

    def get_opponent_info(self):
        return {
            'x': self.centerx,
            'y': self.centery,
            'health': self.health,
            'attacking': self.attacking
        }

    def try_attack(self, target, attack_type):
        if attack_type == 1 and self.attack_cooldown[0] == 0:
            self.attacking = True
            self.attack_type = 1
            self.attack_frames_left = 20  # light attack animation
            # Check collision
            if self.flip:
                attack_left = self.centerx - self.width
            else:
                attack_left = self.centerx
            attack_rect_left = attack_left
            attack_rect_right = attack_left + self.width
            attack_rect_top = self.y
            attack_rect_bottom = self.y + self.height
            # colliderect check
            if (attack_rect_left < target.right and attack_rect_right > target.left and
                attack_rect_top < target.bottom and attack_rect_bottom > target.y):
                target.health -= 10
                target.hit = True
                target.hit_frames = 10
                return True
            return False
        elif attack_type == 2 and self.attack_cooldown[1] == 0:
            self.attacking = True
            self.attack_type = 2
            self.attack_frames_left = 25  # heavy attack animation
            if self.flip:
                attack_left = self.centerx - self.width
            else:
                attack_left = self.centerx
            attack_rect_left = attack_left
            attack_rect_right = attack_left + self.width
            attack_rect_top = self.y
            attack_rect_bottom = self.y + self.height
            if (attack_rect_left < target.right and attack_rect_right > target.left and
                attack_rect_top < target.bottom and attack_rect_bottom > target.y):
                target.health -= 20
                target.hit = True
                target.hit_frames = 10
                return True
            return False
        return False

    def update(self):
        # Attack cooldowns tick here (matching real game move() order)
        # But NOT during dashing (real game returns early from move() during dash)
        if not self.dashing:
            if self.attack_cooldown[0] > 0:
                self.attack_cooldown[0] -= 1
            if self.attack_cooldown[1] > 0:
                self.attack_cooldown[1] -= 1

        # Dash cooldown always ticks (before early return in real game)
        if self.dash_cooldown > 0:
            self.dash_cooldown -= 1

        # Attack animation
        if self.attacking:
            self.attack_frames_left -= 1
            if self.attack_frames_left <= 0:
                self.attacking = False
                if self.attack_type == 1:
                    self.attack_cooldown[0] = 25
                elif self.attack_type == 2:
                    self.attack_cooldown[1] = 100

        # Hit stun
        if self.hit:
            self.hit_frames -= 1
            if self.hit_frames <= 0:
                self.hit = False
                self.attack_cooldown[0] = 25

        # Health check
        if self.health <= 0:
            self.health = 0
            self.alive = False

def simulate_frame(f, move_data, target):
    """Apply one frame of movement for fighter f."""
    if f.dashing:
        f.dash_timer -= 1
        if f.dash_dir == 'right':
            f.x += DASH_SPEED
        else:
            f.x -= DASH_SPEED
        if f.dash_timer <= 0:
            f.dashing = False
        # Boundary
        if f.left < 0:
            f.x = 0
        if f.right > SC_WIDTH:
            f.x = SC_WIDTH - f.width
        return

    if f.attacking:
        return

    dx = 0
    if move_data.get('move') == 'right':
        dx = SPEED
    elif move_data.get('move') == 'left':
        dx = -SPEED

    if move_data.get('jump') and not f.jump:
        f.vely = -30
        f.jump = True

    if move_data.get('attack') is not None and not f.attacking:
        f.try_attack(target, move_data['attack'])

    if move_data.get('dash') == 'right' and f.dash_cooldown == 0:
        f.dashing = True
        f.dash_cooldown = 50
        f.dash_timer = 10
        f.dash_dir = 'right'
    elif move_data.get('dash') == 'left' and f.dash_cooldown == 0:
        f.dashing = True
        f.dash_cooldown = 50
        f.dash_timer = 10
        f.dash_dir = 'left'

    # Gravity
    f.vely += GRAVITY
    dy = f.vely

    # Boundaries
    if f.left + dx < 0:
        dx = -f.left
    if f.right + dx > SC_WIDTH:
        dx = SC_WIDTH - f.right
    if f.bottom + dy > GROUND_Y:
        f.vely = 0
        f.jump = False
        dy = GROUND_Y - f.bottom

    f.x += dx
    f.y += dy

    # Face opponent
    if target.centerx > f.centerx:
        f.flip = False
    else:
        f.flip = True


def run_battle(verbose=False):
    f1 = SimFighter(100, 1)  # my_agent
    f2 = SimFighter(800, 2)  # opponent agent

    stats = {
        'my_hits': 0, 'opp_hits': 0,
        'my_heavy': 0, 'my_light': 0,
        'opp_heavy': 0, 'opp_light': 0,
        'my_dashes': 0, 'opp_dashes': 0,
        'frames_in_range': 0,
        'frames_attacking_in_range': 0,
        'debug_reasons': {},
        'distance_samples': [],
    }

    flag = True
    for frame in range(3600):
        if not f1.alive or not f2.alive:
            break

        fi1 = f1.get_fighter_info()
        oi1 = f2.get_opponent_info()
        fi2 = f2.get_fighter_info()
        oi2 = f1.get_opponent_info()

        # Get moves
        try:
            m1 = my_agent.make_move(fi1, oi1, f1.saved_data)
            f1.saved_data = m1.get('saved_data', f1.saved_data)
        except Exception as e:
            m1 = {'move': None, 'attack': None, 'jump': False, 'dash': None}

        try:
            m2 = opp_agent.make_move(fi2, oi2, f2.saved_data)
            f2.saved_data = m2.get('saved_data', f2.saved_data)
        except Exception as e:
            m2 = {'move': None, 'attack': None, 'jump': False, 'dash': None}

        # Track debug
        reason = m1.get('debug', '?').split('|')[0] if m1.get('debug') else '?'
        stats['debug_reasons'][reason] = stats['debug_reasons'].get(reason, 0) + 1

        dist_x = abs(f1.centerx - f2.centerx)
        dist_y = abs(f1.centery - f2.centery)

        if frame % 60 == 0:
            stats['distance_samples'].append(dist_x)

        if dist_x < 180 and dist_y < 180:
            stats['frames_in_range'] += 1
            if m1.get('attack') is not None:
                stats['frames_attacking_in_range'] += 1

        # Simulate
        old_h2 = f2.health
        old_h1 = f1.health

        if flag:
            simulate_frame(f1, m1, f2)
            simulate_frame(f2, m2, f1)
        else:
            simulate_frame(f2, m2, f1)
            simulate_frame(f1, m1, f2)
        flag = not flag

        f1.update()
        f2.update()

        if f2.health < old_h2:
            dmg = old_h2 - f2.health
            stats['my_hits'] += 1
            if dmg >= 20:
                stats['my_heavy'] += 1
            else:
                stats['my_light'] += 1

        if f1.health < old_h1:
            dmg = old_h1 - f1.health
            stats['opp_hits'] += 1
            if dmg >= 20:
                stats['opp_heavy'] += 1
            else:
                stats['opp_light'] += 1

        if m1.get('dash'):
            stats['my_dashes'] += 1
        if m2.get('dash'):
            stats['opp_dashes'] += 1

        if verbose and frame % 300 == 0:
            print(f"  Frame {frame}: HP {f1.health}-{f2.health}, dist={dist_x}, reason={reason}")

    winner = None
    if not f1.alive:
        winner = 'opponent'
    elif not f2.alive:
        winner = 'my_agent'
    elif f1.health > f2.health:
        winner = 'my_agent'
    elif f2.health > f1.health:
        winner = 'opponent'
    else:
        winner = 'draw'

    return {
        'winner': winner,
        'my_hp': f1.health,
        'opp_hp': f2.health,
        'frames': frame + 1,
        **stats
    }


if __name__ == '__main__':
    N = 50
    print(f"Running {N} simulated battles: my_agent (P1) vs agent.py (P2)\n")

    wins = {'my_agent': 0, 'opponent': 0, 'draw': 0}
    total_my_hp = 0
    total_opp_hp = 0
    all_reasons = {}
    total_in_range = 0
    total_atk_in_range = 0
    total_my_hits = 0
    total_opp_hits = 0
    total_my_heavy = 0
    total_opp_heavy = 0

    for i in range(N):
        r = run_battle(verbose=(i == 0))
        wins[r['winner']] += 1
        total_my_hp += r['my_hp']
        total_opp_hp += r['opp_hp']
        total_in_range += r['frames_in_range']
        total_atk_in_range += r['frames_attacking_in_range']
        total_my_hits += r['my_hits']
        total_opp_hits += r['opp_hits']
        total_my_heavy += r['my_heavy']
        total_opp_heavy += r['opp_heavy']
        for k, v in r['debug_reasons'].items():
            all_reasons[k] = all_reasons.get(k, 0) + v

        if (i + 1) % 10 == 0:
            print(f"  Battle {i+1}: {r['winner']} (HP: {r['my_hp']}-{r['opp_hp']})")

    print(f"\n{'='*60}")
    print(f"RESULTS ({N} battles):")
    print(f"  My Agent Wins: {wins['my_agent']} ({100*wins['my_agent']/N:.0f}%)")
    print(f"  Opponent Wins: {wins['opponent']} ({100*wins['opponent']/N:.0f}%)")
    print(f"  Draws:         {wins['draw']} ({100*wins['draw']/N:.0f}%)")
    print(f"\n  Avg HP remaining: My={total_my_hp/N:.1f}  Opp={total_opp_hp/N:.1f}")
    print(f"  Avg hits landed:  My={total_my_hits/N:.1f}  Opp={total_opp_hits/N:.1f}")
    print(f"  Avg heavy hits:   My={total_my_heavy/N:.1f}  Opp={total_opp_heavy/N:.1f}")
    print(f"  Avg frames in range: {total_in_range/N:.0f}")
    print(f"  Avg attacking while in range: {total_atk_in_range/N:.0f}")
    if total_in_range > 0:
        print(f"  Attack efficiency: {100*total_atk_in_range/total_in_range:.0f}%")
    print(f"\n  Decision distribution:")
    sorted_reasons = sorted(all_reasons.items(), key=lambda x: -x[1])
    total_decisions = sum(v for _, v in sorted_reasons)
    for reason, count in sorted_reasons:
        print(f"    {reason}: {count} ({100*count/total_decisions:.1f}%)")
    print(f"{'='*60}")

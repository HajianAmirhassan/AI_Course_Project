import json
import random
import sys
import time

directions = ["left", "right"]


def make_move(fighter_info, opponent_info, saved_data) -> dict:
    action = {
        "move": None,
        "attack": None,
        "jump": False,
        "dash": None,
        "debug": None,
        "saved_data": saved_data,
    }  # Added 'roll' key

    distanceX = abs(fighter_info["x"] - opponent_info["x"])

    # Get our attack cooldowns
    fighter_attack_cooldown = fighter_info["attack_cooldown"]

    light_attack_cooldown = fighter_attack_cooldown[0]

    heavy_attack_cooldown = fighter_attack_cooldown[1]

    # are we attacking right now
    is_attacking = fighter_info["attacking"]

    # Get current health
    health = fighter_info["health"]

    # are we jumping right now
    is_jumping = fighter_info["jump"]

    # Get our coordinates
    fighter_x = fighter_info["x"]
    fighter_y = fighter_info["y"]

    opponent_x = opponent_info["x"]
    opponent_y = opponent_info["y"]

    opponent_health = opponent_info["health"]

    opponent_attacking = opponent_info["attacking"]

    enemy_direction = False if fighter_x > opponent_x else True
    distanceY = abs(fighter_y - opponent_y)

    enemy_inhorizontal = distanceX < 180
    enemy_invertical = distanceY < 180

    enemy_invicinity = enemy_inhorizontal and enemy_invertical

    attacks_available = []
    if light_attack_cooldown <= 0:
        attacks_available.append(1)
    if heavy_attack_cooldown <= 0:
        attacks_available.append(2)

    if_attacks_available = bool(attacks_available)

    should_we_attack = if_attacks_available and enemy_invicinity
    move_towards = if_attacks_available and (not enemy_invicinity)
    should_run = not if_attacks_available

    is_jumping = True

    action["jump"] = is_jumping
    action["dash"] = None
    action["move"] = None

    if should_run:
        running_direction = not enemy_direction
        if enemy_invicinity:
            if enemy_direction:
                if fighter_x > 180:
                    running_direction = not enemy_direction
                else:
                    running_direction = enemy_direction
            else:
                if fighter_x < 820:
                    running_direction = enemy_direction
                else:
                    running_direction = not enemy_direction

        if fighter_info["dash_cooldown"] > 0:
            action["move"] = directions[running_direction]
        else:
            action["dash"] = directions[running_direction]
    elif should_we_attack or move_towards:
        if not enemy_invicinity:
            action["move"] = directions[enemy_direction]

    action["saved_data"] = opponent_info

    # action["debug"] = {
    #     "enemy_direction": directions[enemy_direction],
    #     "should_we_attack": should_we_attack,
    #     "move_towards": move_towards,
    #     "should_run": should_run,
    #     "attacks_available": attacks_available,
    #     "if_attacks_available": if_attacks_available,
    #     # "figher_info": fighter_info,
    #     "dash": action["dash"],
    #     "move": action["move"],
    # }

    # attack with 1 (light) or 2 (heavy), or not attack
    action["attack"] = None
    if should_we_attack and (not is_attacking):
        action["attack"] = max(attacks_available)

    return action


input_data = input()
json_data = json.loads(input_data)
opponent_info = json_data["opponent"]
fighter_info = json_data["fighter"]
saved_data = json_data["saved_data"]
result = make_move(fighter_info, opponent_info, saved_data)
print(json.dumps(result))

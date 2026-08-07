# AI_Course_Project
A rule-based Python combat agent developed as part of a university Artificial Intelligence project. It processes real-time fighter and opponent states, manages attack cooldowns, movement, jumping, and dashing, and returns JSON actions for a 2D fighting game.

[![Language](https://img.shields.io/badge/Language-Python%203.x-blue.svg)](https://www.python.org/)
[![Project Type](https://img.shields.io/badge/Project-University%20AI-red.svg)](#)

A robust, rule-based autonomous combat agent developed as part of a **University Artificial Intelligence & Expert Systems** course. This agent is designed to compete in the "Zoorkhane" 2D fighting game environment by processing real-time game states and executing optimal combat strategies.

## 📝 Description
This project implements a Python-based agent that interacts with the Zoorkhane game engine via standard I/O (JSON). It evaluates the relative positions, health, and cooldowns of both the controlled fighter and the opponent to make split-second tactical decisions.

## 🚀 Key Features
- **JSON Standard Communication:** Seamless integration with the game runner using `stdin` and `stdout`.
- **Dynamic Proximity Logic:** Automated hitbox detection based on a 180-unit distance threshold (per project specs).
- **Combat Resource Management:** Tracks Light and Heavy attack cooldowns to maximize damage output.
- **Adaptive Movement:** Features automatic approaching, retreating (spacing), dashing, and jumping.
- **Persistent State:** Supports `saved_data` to maintain context between game frames.

## 🧠 Decision Policy
The agent follows a deterministic expert system logic:
1. **Distance Calculation:** Calculates $\Delta X$ and $\Delta Y$ between fighters.
2. **Vicinity Check:** Determines if the opponent is within the effective attack range (< 180 units).
3. **Attack Selection:** Priority is given to the strongest available attack (Heavy > Light) if cooldowns permit.
4. **Strategic Maneuvering:** 
   - **Engage:** Moves toward the opponent if an attack is ready but out of range.
   - **Spacing:** Retreats and uses **Dash** if attacks are on cooldown to avoid taking damage.
5. **State Maintenance:** Updates and passes `saved_data` to ensure continuity.

## 📥 Input & 📤 Output Format

### Input JSON (Sample)
```json
{
  "fighter": {
"x": 100, "y": 200, "health": 100,
"attacking": false, "attack_cooldown": [0, 0],
"jump": false, "dash_cooldown": 0
  },
  "opponent": {
"x": 250, "y": 200, "health": 100, "attacking": false
  },
  "saved_data": {}
}
Output JSON (Sample)
json
{
  "move": "left",
  "attack": 2,
  "jump": true,
  "dash": null,
  "debug": "Target in range, executing Heavy Attack",
  "saved_data": { ... }
}
🛠 Installation & Usage
Ensure you have Python 3.x installed.
Clone the repository:
bash
   git clone https://github.com/your-username/zoorkhane-agent.git
   cd zoorkhane-agent
   
Run the agent (typically handled by the game runner):
bash
   python agent.py
   
📂 Project Structure
agent.py: Core logic, JSON parser, and decision-making functions.
Zoorkhane.pdf: Official project specifications and game environment rules.
Developed for the University AI Course Project.

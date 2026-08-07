# Fighter Agent 🥋

[![Language](https://img.shields.io/badge/Language-Python%203.x-blue.svg)](https://www.python.org/)
[![Project Type](https://img.shields.io/badge/Project-University%20AI-red.svg)](#)

A rule-based Python combat agent developed as part of a university Artificial Intelligence project. It processes real-time fighter and opponent states, manages attack cooldowns, movement, jumping, and dashing, and returns JSON actions for a 2D fighting game.

## 📝 Description
This project implements an autonomous agent designed to compete in the **Zoorkhane** 2D fighting environment. Developed for a **University Artificial Intelligence & Expert Systems** course, the agent acts as an expert system, evaluating game frames via standard I/O (JSON) to execute tactical combat maneuvers in real-time.

## 🚀 Key Features
- **JSON Communication:** Robust integration using `stdin` for state perception and `stdout` for action execution.
- **Hitbox Logic:** Precise movement control based on a **180-unit** proximity threshold.
- **Resource Management:** Real-time tracking of Light/Heavy attack and Dash cooldowns.
- **Adaptive Spacing:** Automatically switches between "Engage" (approaching) and "Defensive" (retreating) modes.
- **Stateless/Persistent Support:** Utilizes `saved_data` to track information across frames.

## 🧠 Decision Policy
The agent functions using a deterministic state-machine logic:
1. **Perception:** Calculates Euclidean distance and relative positioning ($\Delta X, \Delta Y$).
2. **Vicinity Analysis:** Identifies if the opponent is within the striking range (Distance < 180).
3. **Attack Selection:** Prioritizes the strongest available move (Heavy > Light) only when not already in an attacking state.
4. **Tactical Movement:**
   - **Engage:** If an attack is ready but the target is far, the agent moves toward the opponent.
   - **Spacing/Escape:** If attacks are on cooldown, the agent retreats and utilizes **Dash** for rapid repositioning.
   - **Constant Pressure:** Jump actions are triggered to maintain unpredictable movement.

## 📥 Input & 📤 Output Format

### Input State (Sample)
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
```

### Output Action (Sample)
```json
{
  "move": "left",
  "attack": 2,
  "jump": true,
  "dash": null,
  "debug": "Target in range, executing Heavy Attack",
  "saved_data": { ... }
}
```

## 🛠 Installation & Usage

1. **Prerequisites:** Ensure you have **Python 3.x** installed.
2. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/AI_Course_Project.git
   cd AI_Course_Project
   ```
3. **Run the agent:**
   The agent is designed to be called by the game runner, but you can test it manually:
   ```bash
   python agent.py
   ```

## 📂 Project Structure
- `agent.py`: The core Python script containing the state parsing and decision logic.
- `Zoorkhane.pdf`: Official documentation specifying Hitbox rules, I/O contracts, and environment constraints.

---
*Developed as a University AI Course Project.*

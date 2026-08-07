"""Run N games and report results"""
import subprocess, sys, re

N = int(sys.argv[1]) if len(sys.argv) > 1 else 4
wins = draws = losses = 0
for i in range(N):
    r = subprocess.run(['python', 'GAMECODE-python.py'],
                       capture_output=True, text=True, timeout=180)
    out = r.stdout
    # Find final result line
    for line in reversed(out.splitlines()):
        line = line.strip()
        if 'F1 wins' in line:
            wins += 1
            print(f"Game {i+1}: {line}")
            break
        elif 'F2 wins' in line:
            losses += 1
            print(f"Game {i+1}: {line}")
            break
        elif line == 'Draw':
            # Check round scores
            scores = [l.strip() for l in out.splitlines() if l.strip().startswith('[')]
            last_score = scores[-1] if scores else '?'
            draws += 1
            print(f"Game {i+1}: Draw (last score: {last_score})")
            break

print(f"\n=== RESULTS: {wins}W / {draws}D / {losses}L out of {N} games ===")

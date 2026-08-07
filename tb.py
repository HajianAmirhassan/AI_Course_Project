import subprocess, sys
N = int(sys.argv[1]) if len(sys.argv) > 1 else 5
wins = draws = losses = 0
for i in range(N):
    try:
        r = subprocess.run(['python', 'GAMECODE-python.py'], capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        print(f'Game {i+1}: TIMEOUT', flush=True)
        continue
    out = r.stdout
    found = False
    for line in reversed(out.splitlines()):
        line = line.strip()
        if 'F1 wins' in line:
            wins += 1; print(f'Game {i+1}: {line}', flush=True); found=True; break
        elif 'F2 wins' in line:
            losses += 1; print(f'Game {i+1}: {line}', flush=True); found=True; break
        elif 'Draw' in line:
            draws += 1; print(f'Game {i+1}: {line}', flush=True); found=True; break
    if not found:
        err = r.stderr[-100:] if r.stderr else ''
        print(f'Game {i+1}: NO RESULT ({err})', flush=True)
print(f'\n=== RESULTS: {wins}W / {draws}D / {losses}L out of {N} ===', flush=True)

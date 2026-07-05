import json
from cube import solved_cube, scramble, solve_cube, apply_move, fast_copy, is_solved

cube = solved_cube()
log = scramble(cube, n_moves=8)
print('scramble log:', log)

solution = solve_cube(cube, max_total_moves=10)
print('solution:', solution)

states = [fast_copy(cube)]
state = fast_copy(cube)
if solution:
    for m in solution:
        apply_move(state, m)
        states.append(fast_copy(state))

assert is_solved(states[-1]) if solution else True

data = {
    'scramble_log': log,
    'moves': solution or [],
    'states': states,  # states[0] = scrambled, states[i] = 상태 after moves[0..i-1]
}

with open('/workspaces/cube/cube.py', 'w') as f:
    json.dump(data, f)

print('states:', len(states))
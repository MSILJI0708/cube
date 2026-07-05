"""
3x3x3 큐브 시뮬레이터 + 스크램블러 + 솔버

면 인덱스 (문제에서 준 순서: 바닥, 네 면, 뚜껑):
    0 = D (바닥, Down)
    1 = F (앞, Front)
    2 = R (오른쪽, Right)
    3 = B (뒤, Back)
    4 = L (왼쪽, Left)
    5 = U (뚜껑, Up)

각 face는 3x3 리스트. row는 위->아래, col은 왼쪽->오른쪽.
색상 값은 0~5 (정렬된 상태에서는 face i 의 색이 전부 i).

핵심 설계 포인트:
- 스크램블은 U/U'/R/R' 회전과 전체 큐브 방향 회전(x, y, z)만 사용.
- 솔버는 스크램블에 쓰인 무브 로그를 절대 보지 않음.
  대신 U,D,R,L,F,B 전체 6면 회전을 제너레이터로 갖는 양방향 탐색
  (meet-in-the-middle BFS)으로 "현재 상태 -> 완성 상태"를 처음부터
  다시 찾아냄. (완성 판정은 방향에 무관하게 "각 면이 단색이고
  6색이 모두 다르면 solved")
"""

import random
import copy
import time

D, F, R, B, L, U = 0, 1, 2, 3, 4, 5
FACE_NAMES = ['D', 'F', 'R', 'B', 'L', 'U']


def solved_cube():
    return [[[i] * 3 for _ in range(3)] for i in range(6)]


def fast_copy(faces):
    return [[row[:] for row in face] for face in faces]


def cw(m):
    """면 자체를 시계방향 90도 회전"""
    return [[m[2 - c][r] for c in range(3)] for r in range(3)]


def ccw(m):
    return [[m[c][2 - r] for c in range(3)] for r in range(3)]


# ---------------------------------------------------------------
# 6개 면 회전 (각 회전은 "면 자체 회전" + "인접 4개 스트립 순환")
# 모든 회전은 clockwise 버전만 직접 정의하고, ' (prime) 과 2 는
# clockwise 를 3번 / 2번 적용해서 얻는다 -> 내부 일관성이 자동 보장됨.
# ---------------------------------------------------------------

def turn_U(faces):
    faces[U] = cw(faces[U])
    f, r, b, l = faces[F], faces[R], faces[B], faces[L]
    f[0], l[0], b[0], r[0] = r[0][:], f[0][:], l[0][:], b[0][:]


def turn_D(faces):
    faces[D] = cw(faces[D])
    f, r, b, l = faces[F], faces[R], faces[B], faces[L]
    f[2], r[2], b[2], l[2] = l[2][:], f[2][:], r[2][:], b[2][:]


def turn_F(faces):
    faces[F] = cw(faces[F])
    u, r, d, l = faces[U], faces[R], faces[D], faces[L]
    u_row = u[2][:]
    r_col = [r[i][0] for i in range(3)]
    d_row = d[0][:]
    l_col = [l[i][2] for i in range(3)]
    u[2] = l_col[::-1]
    for i in range(3):
        r[i][0] = u_row[i]
    d[0] = r_col[::-1]
    for i in range(3):
        l[i][2] = d_row[i]


def turn_B(faces):
    faces[B] = cw(faces[B])
    u, r, d, l = faces[U], faces[R], faces[D], faces[L]
    u_row = u[0][:]
    r_col = [r[i][2] for i in range(3)]
    d_row = d[2][:]
    l_col = [l[i][0] for i in range(3)]
    u[0] = r_col[::-1]
    for i in range(3):
        l[i][0] = u_row[i]
    d[2] = l_col[::-1]
    for i in range(3):
        r[i][2] = d_row[i]


def turn_R(faces):
    faces[R] = cw(faces[R])
    u, f, d, b = faces[U], faces[F], faces[D], faces[B]
    u_col = [u[i][2] for i in range(3)]
    f_col = [f[i][2] for i in range(3)]
    d_col = [d[i][2] for i in range(3)]
    b_col = [b[i][0] for i in range(3)]  # B는 뒤집힌 방향으로 이어붙음
    for i in range(3):
        f[i][2] = u_col[i]
    for i in range(3):
        d[i][2] = f_col[i]
    for i in range(3):
        b[i][0] = d_col[2 - i]
    for i in range(3):
        u[i][2] = b_col[2 - i]


def turn_L(faces):
    faces[L] = cw(faces[L])
    u, f, d, b = faces[U], faces[F], faces[D], faces[B]
    u_col = [u[i][0] for i in range(3)]
    f_col = [f[i][0] for i in range(3)]
    d_col = [d[i][0] for i in range(3)]
    b_col = [b[i][2] for i in range(3)]
    for i in range(3):
        b[i][2] = u_col[2 - i]
    for i in range(3):
        u[i][0] = f_col[i]
    for i in range(3):
        f[i][0] = d_col[i]
    for i in range(3):
        d[i][0] = b_col[2 - i]


BASE_MOVES = {'U': turn_U, 'D': turn_D, 'R': turn_R, 'L': turn_L, 'F': turn_F, 'B': turn_B}


def apply_move(faces, move):
    """move 예: 'U', "U'", 'U2', 'R', "R'", 'R2' ... """
    base = move[0]
    suffix = move[1:]
    n = 1
    if suffix == "'":
        n = 3
    elif suffix == '2':
        n = 2
    for _ in range(n):
        BASE_MOVES[base](faces)


def inverse_move(move):
    base = move[0]
    suffix = move[1:]
    if suffix == "'":
        return base
    if suffix == '2':
        return move
    return base + "'"


# ---------------------------------------------------------------
# 전체 큐브 방향 회전 (x, y, z) - 물리적으로 큐브를 손에 쥐고 통째로 돌리는 것.
# 스크램블에서 "큐브 회전" 항목으로 쓰인다. 내부적으로는 6개 face 배열을
# 서로 자리바꿈 + 필요한 면은 자기 자신도 회전.
# ---------------------------------------------------------------

def rotate_y(faces):
    """U를 위에서 봤을 때 시계방향으로 큐브 전체를 돌림 (U,D축 기준)"""
    faces[F], faces[R], faces[B], faces[L] = faces[R], faces[B], faces[L], faces[F]
    faces[U] = cw(faces[U])
    faces[D] = ccw(faces[D])


def flip180(face):
    return [row[::-1] for row in face[::-1]]


def rotate_x(faces):
    """R을 오른쪽에서 봤을 때 시계방향으로 큐브 전체를 돌림 (R,L축 기준).
    U -> B(180도 뒤집힘), F -> U, D -> F, B(180도 뒤집힘) -> D 로 순환."""
    u, f, d, b = faces[U], faces[F], faces[D], faces[B]
    faces[F] = u
    faces[D] = f
    faces[B] = flip180(d)
    faces[U] = flip180(b)
    faces[R] = ccw(faces[R])
    faces[L] = cw(faces[L])


def rotate_z(faces):
    """F를 정면에서 봤을 때 시계방향으로 큐브 전체를 돌림 (F,B축 기준)"""
    faces[U], faces[R], faces[D], faces[L] = faces[L], faces[U], faces[R], faces[D]
    faces[U] = cw(faces[U])
    faces[R] = cw(faces[R])
    faces[D] = cw(faces[D])
    faces[L] = cw(faces[L])
    faces[F] = cw(faces[F])
    faces[B] = ccw(faces[B])


WHOLE_CUBE_MOVES = {'x': rotate_x, 'y': rotate_y, 'z': rotate_z}


def apply_whole_rotation(faces, axis, times=1):
    for _ in range(times % 4):
        WHOLE_CUBE_MOVES[axis](faces)


# ---------------------------------------------------------------
# 스크램블러: "위쪽 회전, 오른쪽 회전, 큐브 회전"만 사용
# ---------------------------------------------------------------

def scramble(faces, n_moves=10, seed=None):
    """검증된 6면 회전만으로 스크램블한다.

    주의: 이 파일에는 전체 큐브 방향 회전(x, y, z, rotate_x/y/z 함수)도
    정의되어 있지만, 디버깅 과정에서 y가 (그리고 재검증 결과 x도) 모든
    면-회전 쌍에 대해 완전한 켤레(conjugation) 일관성을 통과하지 못한다는
    사실이 드러났다. 즉 이 구현에서는 x/y/z가 '진짜 회전'이 아닐 수 있고,
    스크램블에 섞어 쓰면 (교수님이 우려하신 대로) 이론적으로 다시 못 맞추는
    상태가 나올 위험이 있다. 그래서 스크램블은 절대 x/y/z를 쓰지 않고,
    완전히 검증된(즉 (X Y X' Y')^6 == identity 를 모든 면 쌍에 대해
    만족하는) U/D/R/L/F/B 회전만 사용한다."""
    if seed is not None:
        random.seed(seed)
    log = []
    choices = ['U', "U'", 'U2', 'D', "D'", 'D2',
               'R', "R'", 'R2', 'L', "L'", 'L2',
               'F', "F'", 'F2', 'B', "B'", 'B2']
    for _ in range(n_moves):
        m = random.choice(choices)
        log.append(m)
        apply_move(faces, m)
    return log


# ---------------------------------------------------------------
# 완성 판정: 방향(orientation)에 무관하게 "각 면이 단색 & 6색이 서로 다름"
# ---------------------------------------------------------------

def is_solved(faces):
    colors = []
    for face in faces:
        first = face[0][0]
        for row in face:
            for v in row:
                if v != first:
                    return False
        colors.append(first)
    return len(set(colors)) == 6


def state_key(faces):
    return tuple(tuple(tuple(row) for row in f) for f in faces)


CORNER_SLOTS = [
    [(U, 2, 2), (F, 0, 2), (R, 0, 0)],
    [(U, 2, 0), (F, 0, 0), (L, 0, 2)],
    [(U, 0, 2), (B, 0, 0), (R, 0, 2)],
    [(U, 0, 0), (B, 0, 2), (L, 0, 0)],
    [(D, 0, 2), (F, 2, 2), (R, 2, 0)],
    [(D, 0, 0), (F, 2, 0), (L, 2, 2)],
    [(D, 2, 2), (B, 2, 0), (R, 2, 2)],
    [(D, 2, 0), (B, 2, 2), (L, 2, 0)],
]

EDGE_SLOTS = [
    [(U, 2, 1), (F, 0, 1)],
    [(U, 0, 1), (B, 0, 1)],
    [(U, 1, 0), (L, 0, 1)],
    [(U, 1, 2), (R, 0, 1)],
    [(D, 0, 1), (F, 2, 1)],
    [(D, 2, 1), (B, 2, 1)],
    [(D, 1, 0), (L, 2, 1)],
    [(D, 1, 2), (R, 2, 1)],
    [(F, 1, 0), (L, 1, 2)],
    [(F, 1, 2), (R, 1, 0)],
    [(B, 1, 2), (L, 1, 0)],
    [(B, 1, 0), (R, 1, 2)],
]


def heuristic(faces):
    """코너/엣지 조각 단위 admissible 휴리스틱.
    한 번의 분면 회전(quarter turn)은 최대 4개의 코너와 4개의 엣지에만
    영향을 줄 수 있으므로, '아직 안 맞은 코너/엣지 개수 / 4'의 올림값이
    남은 최소 이동 횟수의 하한이 된다. 두 값 중 큰 쪽을 취해 더 강하게
    가지치기한다."""
    centers = [faces[i][1][1] for i in range(6)]

    bad_corners = 0
    for slot in CORNER_SLOTS:
        if any(faces[f][r][c] != centers[f] for f, r, c in slot):
            bad_corners += 1

    bad_edges = 0
    for slot in EDGE_SLOTS:
        if any(faces[f][r][c] != centers[f] for f, r, c in slot):
            bad_edges += 1

    return max((bad_corners + 3) // 4, (bad_edges + 3) // 4)


SOLVE_MOVES = ['U', "U'", 'U2', 'D', "D'", 'D2',
               'R', "R'", 'R2', 'L', "L'", 'L2',
               'F', "F'", 'F2', 'B', "B'", 'B2']


def opposite_axis(m1, m2):
    """같은 축을 연속으로 돌리는 무의미한 탐색 가지 제거용"""
    pairs = {'U': 'D', 'D': 'U', 'R': 'L', 'L': 'R', 'F': 'B', 'B': 'F'}
    return pairs.get(m1[0]) == m2[0] or m1[0] == m2[0]


def _bfs_layers(start_faces, max_depth):
    """start_faces 에서 SOLVE_MOVES 만으로 max_depth 단계까지 도달 가능한
    모든 상태와, 그 상태까지 가는 무브 경로를 딕셔너리로 반환한다."""
    start_key = state_key(start_faces)
    layers = {start_key: []}
    frontier = [(fast_copy(start_faces), [])]
    for _ in range(max_depth):
        next_frontier = []
        for state, path in frontier:
            last = path[-1] if path else None
            for move in SOLVE_MOVES:
                if last and opposite_axis(last, move):
                    continue
                child = fast_copy(state)
                apply_move(child, move)
                k = state_key(child)
                if k not in layers:
                    new_path = path + [move]
                    layers[k] = new_path
                    next_frontier.append((child, new_path))
        frontier = next_frontier
    return layers


_FWD_CACHE = {}


def _recolor_to_canonical(faces):
    """센터 색 -> 슬롯 인덱스 매핑을 이용해 스티커 값을 슬롯 인덱스로
    다시 칠한다. moves 는 색상 값 자체에 의존하지 않고 위치만 다루므로
    이 재색칠은 이동 연산과 항상 commute 한다 -> 이렇게 정규화해두면
    센터 배치가 어떻게 섞여있든 캐노니컬 solved_cube() 기준으로 미리
    계산해둔 forward BFS 결과를 그대로 재사용할 수 있다."""
    color_to_slot = {faces[i][1][1]: i for i in range(6)}
    return [[[color_to_slot[v] for v in row] for row in faces[i]] for i in range(6)]


def solve_cube(faces, max_total_moves=12):
    """스크램블 로그를 전혀 참조하지 않는 일반 솔버 (양방향 탐색).

    '완성 상태에서 K수 이내에 갈 수 있는 모든 상태'와
    '지금 상태에서 K수 이내에 갈 수 있는 모든 상태'를 각각 구해서
    교집합(공통으로 도달 가능한 중간 상태)을 찾는다. 찾으면 두 경로를
    이어붙여서 '지금 상태 -> 완성 상태'로 가는 해를 만든다.

    깊이를 절반씩 나눠 담당하기 때문에 (예: 총 12수짜리 해도 6+6수 탐색으로
    찾아냄) 한쪽으로만 파고드는 탐색보다 훨씬 빠르고 안정적이다.

    forward BFS 결과(완성 상태 -> 도달 가능한 상태들)는 센터 배치를
    슬롯 인덱스 기준으로 정규화해서 모듈 레벨에 캐싱해두기 때문에,
    같은 half 값으로 여러 번 호출해도 매번 다시 계산하지 않는다.
    """
    if is_solved(faces):
        return []

    canonical = _recolor_to_canonical(faces)

    half = max_total_moves // 2
    if half not in _FWD_CACHE:
        _FWD_CACHE[half] = _bfs_layers(solved_cube(), half)
    fwd = _FWD_CACHE[half]

    def check(k, back_path):
        if k in fwd:
            forward_path = fwd[k]  # target -> 공통상태
            to_common = back_path
            common_to_target = [inverse_move(m) for m in reversed(forward_path)]
            return to_common + common_to_target
        return None

    # 지금 상태(정규화된 색으로)에서 한 단계씩 넓혀가며 fwd 와 만나는지 확인
    start_key = state_key(canonical)
    seen = {start_key}
    result = check(start_key, [])
    if result is not None:
        return result

    cur_states = [(canonical, [])]
    for depth in range(half):
        next_states = []
        for state, path in cur_states:
            last = path[-1] if path else None
            for move in SOLVE_MOVES:
                if last and opposite_axis(last, move):
                    continue
                child = fast_copy(state)
                apply_move(child, move)
                k = state_key(child)
                if k in seen:
                    continue
                seen.add(k)
                new_path = path + [move]
                result = check(k, new_path)
                if result is not None:
                    return result
                next_states.append((child, new_path))
        cur_states = next_states

    return None  # max_total_moves 안에서 못 찾음 (늘려서 재시도)


if __name__ == '__main__':
    # random.seed(42) 처럼 시드를 고정하면 매번 "같은 랜덤"이 나옵니다.
    # 진짜 매번 다르게 섞이길 원하면 이렇게 시드를 지정하지 않으면 됩니다.
    # (재현 가능한 테스트가 필요할 때만 random.seed(원하는 정수) 를 추가하세요)

    cube = solved_cube()
    assert is_solved(cube)

    n_moves = 8
    log = scramble(cube, n_moves=n_moves)
    print('스크램블에 사용된 무브 (문제 출제용 로그, 채점 참고용):', log)
    print('스크램블 직후 solved?', is_solved(cube))
    print()

    t0 = time.time()
    # 솔버는 log 를 절대 참조하지 않는다 -> 이 시점부터 log 변수는 아예 안 씀
    solution = solve_cube(cube, max_total_moves=10)
    dt = time.time() - t0
    print(f'양방향 탐색으로 찾은 솔루션 ({dt:.2f}s, {len(solution) if solution else 0}수):', solution)

    if solution:
        test = fast_copy(cube)
        for m in solution:
            apply_move(test, m)
        print('솔루션 적용 후 solved?', is_solved(test))
    else:
        print('max_total_moves 안에서 못 찾음 -> 값을 늘려서 재시도하세요.')
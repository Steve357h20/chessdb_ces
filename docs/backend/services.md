# 业务服务层（Services）

> 业务逻辑封装。路由层只做参数解析和响应包装，重活都在 Service 层。
>
> 文件位置：`backend/app/services/`

## 总览

| 服务 | 文件 | 职责 |
|------|------|------|
| `StockfishAnalyzer` | [stockfish_analyzer.py](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/services/stockfish_analyzer.py) | UCI 引擎封装、逐着分析、复盘评价 |
| `AIPlayer` | [ai_player.py](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/services/ai_player.py) | 5 档 AI 对弈对手 |
| `PGNParser` | [pgn_parser.py](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/services/pgn_parser.py) | PGN 文本解析、批量导入 |
| `OpeningRecognizer` | [opening_recognizer.py](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/services/opening_recognizer.py) | ECO 编码识别、开局树 |
| `fen_utils` | [fen_utils.py](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/services/fen_utils.py) | FEN 校验、转换、序列化 |
| `PuzzleLibrary` | [puzzle_library.py](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/services/puzzle_library.py) | 10 道预设残局题 |

## 1. StockfishAnalyzer 引擎封装

### 1.1 核心 API

```python
class StockfishAnalyzer:
    def __init__(self, stockfish_path=None, depth=20, threads=1, hash_mb=256):
        self.stockfish_path = stockfish_path or current_app.config['STOCKFISH_PATH']
        self.depth = depth
        self.threads = threads
        self.hash_mb = hash_mb

    async def analyze_game(self, pgn_content, depth=None, threads=None) -> dict:
        """分析整局棋谱，返回完整结果"""

    async def analyze_position(self, fen, depth=None) -> dict:
        """分析单个局面"""

    async def review_game(self, moves_json, user_color) -> dict:
        """复盘玩家对局，返回评价"""

    def is_available(self) -> bool:
        """引擎是否可用"""
```

### 1.2 `analyze_game` 实现

```python
async def analyze_game(self, pgn_content, depth=None, threads=None):
    """分析整局棋谱"""
    depth = depth or self.depth
    threads = threads or self.threads

    async with chess.engine.SimpleEngine.popen_uci(self.stockfish_path) as engine:
        engine.configure({
            "Threads": threads,
            "Hash": self.hash_mb,
        })

        board = chess.pgn.read_game(io.StringIO(pgn_content))
        board = board.board()  # 回到初始

        result = {
            'moves': [],
            'win_rate_curve': [],
            'key_moves': [],
        }

        prev_score = 0
        for move_number, move in enumerate(board.all_chess_moves(), 1):
            info = await engine.analyse(board, chess.engine.Limit(depth=depth))

            score = info['score'].white().score(mate_score=10000) or 0
            win_rate = self._score_to_winrate(score, board.turn)

            # 检测关键着法（胜率变化 > 20%）
            if abs(win_rate - prev_score / 100) > 0.20:
                result['key_moves'].append(move_number)
            prev_score = score

            result['moves'].append({
                'ply': move_number,
                'move': board.san(move),
                'fen_after': board.fen(),
                'score_cp': score,
                'win_rate': win_rate,
                'pv': [board.san(m) for m in info.get('pv', [])[:5]],
                'depth': info.get('depth', 0),
            })
            result['win_rate_curve'].append({'ply': move_number, 'win_rate': win_rate})
            board.push(move)

        return result
```

### 1.3 Mock 降级

```python
class StockfishAnalyzer:
    def __init__(self, ...):
        if not self.stockfish_path or not os.path.isfile(self.stockfish_path):
            self._mock_mode = True

    def is_available(self):
        return not getattr(self, '_mock_mode', False)

    async def analyze_game(self, pgn_content, depth=None, threads=None):
        if self._mock_mode:
            return self._mock_analysis(pgn_content)
        return await self._real_analysis(pgn_content, depth, threads)

    def _mock_analysis(self, pgn_content):
        """Mock 模式：随机生成评分"""
        board = chess.pgn.read_game(io.StringIO(pgn_content))
        board = board.board()
        moves = []
        for i, move in enumerate(board.all_chess_moves(), 1):
            score = random.randint(-300, 300)
            board.push(move)
            moves.append({
                'ply': i,
                'move': board.san(move),
                'score_cp': score,
                'win_rate': 0.5 + score / 1000,
                'mock': True,  # 标记
            })
        return {'moves': moves, 'mock_mode': True, 'win_rate_curve': [...], 'key_moves': []}
```

**前端兼容**：分析结果带 `mock: true` 标记，前端用淡黄色显示"模拟数据"。

### 1.4 复盘评价算法

```python
async def review_game(self, moves_json, user_color):
    """复盘玩家对局"""
    result = []
    board = chess.Board()
    prev_winrate = 0.5

    for ply, mv in enumerate(moves_json, 1):
        user_move = mv.get('user', {})
        move = board.parse_san(user_move['san'])

        info = await engine.analyse(board, chess.engine.Limit(depth=15))
        score = info['score'].white().score(mate_score=10000) or 0
        win_rate = self._score_to_winrate(score, board.turn)
        win_rate_delta = win_rate - prev_winrate
        prev_winrate = win_rate

        label, label_text = self._label_move(win_rate_delta)
        result.append({
            'ply': ply,
            'move': user_move['san'],
            'evaluation': score,
            'win_rate': win_rate,
            'win_rate_delta': win_rate_delta,
            'label': label,
            'label_text': label_text,
        })
        board.push(move)

    return {'moves': result, 'summary': self._summary(result)}
```

## 2. AIPlayer AI 对弈

### 2.1 难度定义

```python
DIFFICULTY_CONFIG = {
    'beginner':    {'skill_level': 3,  'time': 0.1, 'randomness': 0.30},
    'elementary':  {'skill_level': 7,  'time': 0.3, 'randomness': 0.10},
    'intermediate':{'skill_level': 12, 'time': 0.5, 'randomness': 0.0},
    'advanced':    {'skill_level': 18, 'time': 1.0, 'randomness': 0.0},
    'expert':      {'skill_level': 20, 'time': 3.0, 'randomness': 0.0},
}

class AIPlayer:
    def __init__(self, difficulty='intermediate', stockfish_path=None):
        config = DIFFICULTY_CONFIG.get(difficulty, DIFFICULTY_CONFIG['intermediate'])
        self.skill_level = config['skill_level']
        self.time = config['time']
        self.randomness = config['randomness']
        self.stockfish_path = stockfish_path or current_app.config['STOCKFISH_PATH']

    def get_move(self, board) -> Tuple[chess.Move, int]:
        """获取 AI 走法（同步接口）"""
        return asyncio.run(self._get_move_async(board))

    async def _get_move_async(self, board):
        async with chess.engine.SimpleEngine.popen_uci(self.stockfish_path) as engine:
            engine.configure({
                "Skill Level": self.skill_level,
                "Threads": 1,
                "Hash": 64,
            })

            # 主选择
            result = await engine.play(
                board,
                chess.engine.Limit(time=self.time),
                info=chess.engine.INFO_SCORE,
            )
            score = result.info.get('score', chess.engine.Cp(0))
            eval_cp = score.white().score() or 0

            # 一定概率走次优解
            if random.random() < self.randomness:
                multipv_result = await engine.analyse(
                    board,
                    chess.engine.Limit(time=self.time, depth=5),
                    multipv=3,
                )
                if len(multipv_result) > 1:
                    result = chess.engine.PlayResult(
                        multipv_result[1]['pv'][0], None
                    )
                    eval_cp = multipv_result[1]['score'].white().score() or 0

            return result.move, eval_cp
```

### 2.2 走法随机性

为了"入门"和"初级"档有"人味"，AI 偶尔走次优解：
- `random.random() < 0.30` → 30% 概率走第二选择

实现思路：用 `multipv=3` 让引擎输出前 3 选择，按概率切换。

## 3. PGNParser 解析

```python
class PGNParser:
    def parse_multiple(self, text: str) -> Tuple[List[dict], List[str]]:
        """解析多局 PGN"""
        games, errors = [], []
        pgn_text = io.StringIO(text)
        while True:
            try:
                game = chess.pgn.read_game(pgn_text)
                if game is None:
                    break
                games.append(self._extract(game))
            except Exception as e:
                errors.append(f"第 {len(games)+len(errors)+1} 局解析失败: {e}")
        return games, errors

    def _extract(self, game) -> dict:
        board = game.board()
        return {
            'white_player': game.headers.get('White', 'Unknown').strip(),
            'black_player': game.headers.get('Black', 'Unknown').strip(),
            'event': game.headers.get('Event', '').strip(),
            'site': game.headers.get('Site', '').strip(),
            'date': self._parse_date(game.headers.get('Date', '')),
            'round': game.headers.get('Round', ''),
            'result': game.headers.get('Result', '*'),
            'eco_code': game.headers.get('ECO', ''),
            'opening': game.headers.get('Opening', ''),
            'pgn_content': str(game),
            'moves_count': board.fullmove_number,
        }
```

**支持特性**：
- 单文件多 PGN 解析
- 错误隔离（单局失败不影响其他）
- 棋手自动去重

## 4. OpeningRecognizer 开局识别

```python
class OpeningRecognizer:
    def __init__(self):
        with app.app_context():
            self.openings = Opening.query.all()
            self._build_trie()

    def recognize(self, san_moves: List[str]) -> Opening:
        """识别开局（最长前缀匹配）"""
        best_match = None
        for opening in self.openings:
            opening_moves = opening.moves
            if self._is_prefix(opening_moves, san_moves):
                if best_match is None or len(opening_moves) > len(best_match.moves):
                    best_match = opening
        return best_match

    def _is_prefix(self, opening_moves, user_moves) -> bool:
        """opening_moves 是否是 user_moves 的前缀"""
        if len(opening_moves) > len(user_moves):
            return False
        return opening_moves == user_moves[:len(opening_moves)]

    def build_tree(self, max_depth=6) -> dict:
        """构建开局树（前 N 步）"""
        # 每个 ECO 作为一个节点
        # 子节点 = moves 长度 +1 的 ECO
        root = {'name': 'Start', 'children': []}
        for op in self.openings:
            if len(op.moves) <= max_depth:
                self._insert_tree(root, op)
        return root
```

## 5. fen_utils FEN 工具

```python
def validate_fen(fen: str) -> bool:
    """验证 FEN 是否合法"""
    try:
        chess.Board(fen)
        return True
    except (chess.InvalidFenError, ValueError):
        return False

def starting_position() -> str:
    """返回起始 FEN"""
    return chess.STARTING_FEN

def to_dict(fen: str) -> dict:
    """FEN 转字典（piece placement, side, castling, etc.）"""
    board = chess.Board(fen)
    return {
        'turn': 'white' if board.turn else 'black',
        'castling': board.castling_xfen(),
        'is_check': board.is_check(),
        'is_checkmate': board.is_checkmate(),
        'is_stalemate': board.is_stalemate(),
        'is_game_over': board.is_game_over(),
        'legal_moves_count': board.legal_moves.count(),
    }
```

## 6. PuzzleLibrary 残局库

```python
PRESET_PUZZLES = [
    {
        'puzzle_number': 1,
        'name': 'K+Q vs K',
        'fen': '8/8/8/4k3/8/8/4K3/4Q3 w - - 0 1',
        'category': 'king_pawn',
        'difficulty': 'easy',
        'description': '用后和王将杀孤王',
        'solution': ['Qe1+', 'Kd5', 'Qd2+', 'Kc5', 'Qc3+', 'Kb5', 'Qb3+'],
    },
    {
        'puzzle_number': 2,
        'name': 'K+R vs K',
        'fen': '8/8/8/4k3/8/8/4K3/4R3 w - - 0 1',
        'category': 'king_pawn',
        'difficulty': 'easy',
        'description': '用车和王将杀孤王',
        'solution': ['Re5+', 'Kd4', 'Rd5+', 'Kc3', 'Rc5+', 'Kb2', 'Rb5+', 'Ka2', 'Rc2'],
    },
    # ... 10 道
]
```

**导入流程**（`init_db.py::seed_puzzles`）：

```python
def seed_puzzles():
    """灌入 10 道预设题"""
    for p in PRESET_PUZZLES:
        if not Puzzle.query.filter_by(puzzle_number=p['puzzle_number']).first():
            puzzle = Puzzle(is_preset=True, created_by=None, **p)
            db.session.add(puzzle)
    db.session.commit()
```

## 调用关系

```
路由层 (routes/)
    ↓ 调用
服务层 (services/)
    ↓ 调用
数据层 (models/) + Stockfish 子进程
```

**示例**：

```python
# routes/games.py
from app.services.stockfish_analyzer import StockfishAnalyzer

@games_bp.route('/<int:id>/analyze', methods=['POST'])
@jwt_required()
def analyze_game(id):
    game = Game.query.get_or_404(id)
    analyzer = StockfishAnalyzer()
    result = asyncio.run(analyzer.analyze_game(game.pgn_content))
    # 存库
    return jsonify(result)
```

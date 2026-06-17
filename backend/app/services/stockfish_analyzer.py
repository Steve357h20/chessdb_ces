import logging
import os
import random
import time
from io import StringIO
from typing import Callable, Optional

import chess
import chess.engine
import chess.pgn

logger = logging.getLogger(__name__)


class StockfishAnalyzer:
    def __init__(
        self,
        stockfish_path: str = "stockfish",
        depth: int = 20,
        threads: int = 4,
        hash_size: int = 256,
    ):
        self._stockfish_path = stockfish_path
        self._depth = depth
        self._threads = threads
        self._hash_size = hash_size
        self._engine: Optional[chess.engine.SimpleEngine] = None
        self._is_mock = False
        self._init_error: Optional[str] = None

        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
            self._engine.configure({
                "Threads": threads,
                "Hash": hash_size,
            })
            logger.info(
                "Stockfish engine initialized: path=%s, depth=%d, threads=%d, hash=%dMB",
                stockfish_path, depth, threads, hash_size,
            )
        except Exception as e:
            import traceback
            self._init_error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
            logger.warning(
                "Failed to initialize Stockfish (%s): %s, falling back to mock analyzer. Path=%s, CWD=%s",
                type(e).__name__, e, stockfish_path, os.getcwd(),
            )
            self._engine = None
            self._is_mock = True

    def analyze_game(
        self,
        game_id: Optional[int] = None,
        pgn_moves: Optional[str] = None,
        callback: Optional[Callable] = None,
    ) -> dict:
        if pgn_moves is None:
            raise ValueError("pgn_moves is required")

        logger.info("Analyzing game (id=%s)", game_id)

        try:
            game = chess.pgn.read_game(StringIO(pgn_moves))
        except Exception as e:
            logger.error("Failed to parse PGN: %s", e)
            raise AnalysisError(f"Failed to parse PGN: {e}") from e

        if game is None:
            raise AnalysisError("No valid game found in PGN")

        board = game.board()
        moves_data = []
        total_plies = sum(1 for _ in game.mainline_moves())
        if total_plies == 0:
            raise AnalysisError("No moves found in PGN")
        current_ply = 0

        node = game
        while node.variations:
            next_node = node.variation(0)
            move = next_node.move
            san = board.san(move)
            fen_before = board.fen()
            current_ply += 1

            move_number = (current_ply + 1) // 2
            is_white = board.turn

            if self._is_mock:
                analysis = self._mock_analyze_position(fen_before)
            else:
                analysis = self._analyze_single_position(fen_before, move=move)

            actual_eval = self._evaluate_actual_move(
                fen_before, move, analysis.get("best_moves", [])
            )

            white_perspective_score = analysis.get("score", 0.0)

            move_data = {
                "move_number": move_number,
                "color": "w" if is_white else "b",
                "san": san,
                "fen": fen_before,
                "white_win_rate": actual_eval.get("white_win_rate", analysis.get("white_win_rate", 50.0)),
                "score": round(actual_eval.get("actual_score", white_perspective_score), 2),
                "mate_in": actual_eval.get("mate_in"),
                "best_moves": analysis.get("best_moves", []),
                "evaluation": actual_eval["evaluation"],
                "nag": actual_eval["nag"],
                "score_diff": actual_eval["score_diff"],
                "delta": actual_eval["delta"],
            }

            moves_data.append(move_data)

            if callback:
                progress = current_ply / total_plies if total_plies > 0 else 1.0
                try:
                    callback(progress, move_data)
                except Exception as e:
                    logger.warning("Callback error: %s", e)

            board.push(move)
            node = next_node

        result = {
            "game_id": game_id,
            "total_moves": len(moves_data),
            "moves": moves_data,
            "final_fen": board.fen(),
            "engine_info": self.get_engine_info(),
        }

        logger.info("Game analysis complete: %d moves analyzed", len(moves_data))
        return result

    def analyze_position(self, fen: str, multi_pv: int = 3) -> dict:
        if not self._is_mock:
            try:
                board = chess.Board(fen)
            except ValueError as e:
                raise AnalysisError(f"Invalid FEN: {e}") from e

            try:
                infos = self._engine.analyse(
                    board,
                    chess.engine.Limit(depth=self._depth),
                    multipv=multi_pv,
                )
            except chess.engine.EngineTerminatedError:
                logger.error("Stockfish engine terminated unexpectedly")
                self._restart_engine()
                infos = self._engine.analyse(
                    board,
                    chess.engine.Limit(depth=self._depth),
                    multipv=multi_pv,
                )

            return self._parse_analysis_result(infos, board)
        else:
            return self._mock_analyze_position(fen, multi_pv)

    def get_engine_info(self) -> dict:
        if self._is_mock:
            return {
                "name": "Mock Analyzer",
                "version": "1.0",
                "is_mock": True,
                "depth": self._depth,
                "threads": self._threads,
                "hash_size": self._hash_size,
            }

        try:
            info = self._engine.analyse(chess.Board(), chess.engine.Limit(depth=1))
            return {
                "name": "Stockfish",
                "version": self._engine.id.get("name", "Unknown"),
                "is_mock": False,
                "depth": self._depth,
                "threads": self._threads,
                "hash_size": self._hash_size,
            }
        except Exception:
            return {
                "name": "Stockfish (error)",
                "is_mock": False,
                "depth": self._depth,
                "threads": self._threads,
                "hash_size": self._hash_size,
            }

    def close(self):
        if self._engine and not self._is_mock:
            try:
                self._engine.quit()
            except Exception:
                pass
            self._engine = None
            logger.info("Stockfish engine closed")

    def _analyze_single_position(self, fen: str, move: Optional[chess.Move] = None) -> dict:
        board = chess.Board(fen)
        try:
            infos = self._engine.analyse(
                board,
                chess.engine.Limit(depth=self._depth),
                multipv=3,
            )
        except chess.engine.EngineTerminatedError:
            self._restart_engine()
            infos = self._engine.analyse(
                board,
                chess.engine.Limit(depth=self._depth),
                multipv=3,
            )

        return self._parse_analysis_result(infos, board)

    def _parse_analysis_result(self, infos: list, board: chess.Board) -> dict:
        best_moves = []
        score = 0.0
        mate_in = None
        white_win_rate = 50.0

        is_white_turn = board.turn

        for info in infos:
            pv_moves = info.get("pv", [])
            pv_san = []
            temp_board = board.copy()
            for m in pv_moves[:8]:
                try:
                    pv_san.append(temp_board.san(m))
                    temp_board.push(m)
                except Exception:
                    break

            raw_score = info.get("score")
            move_score = 0.0
            move_mate = None
            move_win_rate = 50.0

            if raw_score is not None:
                if raw_score.is_mate():
                    move_mate = raw_score.relative.mate()
                    if move_mate is not None:
                        if not is_white_turn:
                            move_mate = -move_mate
                        if move_mate == 0:
                            move_mate = 1 if is_white_turn else -1
                        move_score = 100.0 + abs(move_mate) if move_mate > 0 else -(100.0 + abs(move_mate))
                        move_win_rate = 99.9 if move_mate > 0 else 0.1
                else:
                    cp = raw_score.relative.score()
                    if cp is not None:
                        if not is_white_turn:
                            cp = -cp
                        move_score = cp / 100.0
                        move_win_rate = self._cp_to_win_rate(cp)

            best_moves.append({
                "move": pv_san[0] if pv_san else "",
                "score": round(move_score, 2),
                "win_rate": round(move_win_rate, 1),
                "pv": pv_san,
                "depth": info.get("depth", self._depth),
                "mate_in": move_mate,
            })

            if not best_moves or info.get("multipv", 1) == 1:
                score = move_score
                mate_in = move_mate
                white_win_rate = move_win_rate

        if best_moves:
            score = best_moves[0]["score"]
            white_win_rate = best_moves[0]["win_rate"]
            mate_in = best_moves[0].get("mate_in")

        return {
            "white_win_rate": round(white_win_rate, 1),
            "score": round(score, 2),
            "mate_in": mate_in,
            "best_moves": best_moves,
        }

    def _evaluate_actual_move(self, fen: str, move: chess.Move, best_moves: list) -> dict:
        if not best_moves:
            return {"evaluation": "", "nag": None, "score_diff": 0.0, "delta": 0.0, "actual_score": 0.0, "white_win_rate": 50.0, "mate_in": None}

        board = chess.Board(fen)
        is_white = board.turn
        best_score = best_moves[0]["score"]
        best_move = best_moves[0]["move"] if best_moves else ""

        actual_win_rate = None
        actual_mate_in = None

        try:
            if self._is_mock:
                actual_score = best_score - random.uniform(0, 0.5)
            else:
                temp_board = board.copy()
                temp_board.push(move)
                next_is_white = temp_board.turn
                info = self._engine.analyse(
                    temp_board,
                    chess.engine.Limit(depth=max(self._depth - 4, 10)),
                )
                raw_score = info.get("score")
                if raw_score is not None:
                    if raw_score.is_mate():
                        mate_val = raw_score.relative.mate()
                        if mate_val is not None and not next_is_white:
                            mate_val = -mate_val
                        if mate_val is not None and mate_val == 0:
                            mate_val = 1 if next_is_white else -1
                        if mate_val is not None:
                            actual_mate_in = mate_val
                            actual_score = 100.0 + abs(mate_val) if mate_val > 0 else -(100.0 + abs(mate_val))
                            actual_win_rate = 99.9 if mate_val > 0 else 0.1
                        else:
                            actual_score = 0.0
                    else:
                        cp = raw_score.relative.score()
                        if cp is not None:
                            if not next_is_white:
                                cp = -cp
                            actual_score = cp / 100.0
                            actual_win_rate = self._cp_to_win_rate(cp)
                        else:
                            actual_score = best_score
                else:
                    actual_score = best_score
        except Exception:
            actual_score = best_score

        if actual_win_rate is None:
            actual_win_rate = self._cp_to_win_rate(int(actual_score * 100))

        best_is_mate = abs(best_score) >= 100
        actual_is_mate = abs(actual_score) >= 100

        def _mate_to_effective(score):
            if abs(score) >= 100:
                sign = 1 if score > 0 else -1
                dist = abs(score) - 100
                if dist == 0:
                    dist = 0.5
                return sign * (100.0 + 3.0 / dist)
            return score

        best_eff = _mate_to_effective(best_score)
        actual_eff = _mate_to_effective(actual_score)

        if is_white:
            delta = best_eff - actual_eff
        else:
            delta = -(best_eff - actual_eff)

        score_diff = abs(delta)

        # 检查是否为最佳着法
        actual_san = board.san(move)
        is_best_move = (actual_san == best_move)

        # 修复后的评价逻辑
        if score_diff < 0.05:           # 差距极小 (< 0.05兵)
            if is_best_move:
                evaluation = "!!"        # 妙手！精准找到最佳着法
                nag = 3
            else:
                evaluation = ""          # 正常着法
                nag = None
        elif score_diff < 0.20:         # 小差距 (0.05-0.2兵)
            evaluation = "!"             # 好着
            nag = 1
        elif score_diff < 0.50:         # 中等差距 (0.2-0.5兵)
            evaluation = "!?"            # 有趣尝试
            nag = 5
        elif score_diff < 1.00:         # 较大差距 (0.5-1.0兵)
            evaluation = "?!"            # 不精确
            nag = 6
        elif score_diff < 2.00:         # 大差距 (1.0-2.0兵)
            evaluation = "?"             # 失误
            nag = 2
        else:                           # 极大差距 (> 2.0兵)
            evaluation = "??"            # 严重失误
            nag = 4

        return {
            "evaluation": evaluation,
            "nag": nag,
            "score_diff": round(score_diff, 2),
            "delta": round(delta, 2),
            "actual_score": round(actual_score, 2),
            "white_win_rate": round(actual_win_rate, 1),
            "mate_in": actual_mate_in,
        }

    def _cp_to_win_rate(self, cp: int) -> float:
        k = 0.004
        win_prob = 1.0 / (1.0 + pow(10, -cp * k))
        return win_prob * 100.0

    def _mock_analyze_position(self, fen: str, multi_pv: int = 3) -> dict:
        board = chess.Board(fen)
        best_moves = []
        legal = list(board.legal_moves)

        for i in range(min(multi_pv, len(legal))):
            move = legal[i] if i < len(legal) else legal[0]
            san = board.san(move)
            base_score = random.uniform(-1.5, 1.5)
            base_wr = self._cp_to_win_rate(int(base_score * 100))

            pv_san = [san]
            temp = board.copy()
            temp.push(move)
            for _ in range(min(4, len(list(temp.legal_moves)))):
                if temp.legal_moves:
                    m = list(temp.legal_moves)[0]
                    pv_san.append(temp.san(m))
                    temp.push(m)

            best_moves.append({
                "move": san,
                "score": round(base_score - i * 0.2, 2),
                "win_rate": round(base_wr - i * 3, 1),
                "pv": pv_san,
                "depth": self._depth,
            })

        return {
            "white_win_rate": best_moves[0]["win_rate"] if best_moves else 50.0,
            "score": best_moves[0]["score"] if best_moves else 0.0,
            "mate_in": None,
            "best_moves": best_moves,
        }

    def _restart_engine(self):
        logger.warning("Restarting Stockfish engine")
        try:
            if self._engine:
                self._engine.quit()
        except Exception:
            pass

        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(self._stockfish_path)
            self._engine.configure({
                "Threads": self._threads,
                "Hash": self._hash_size,
            })
            logger.info("Stockfish engine restarted successfully")
        except Exception as e:
            logger.error("Failed to restart Stockfish: %s", e)
            self._is_mock = True
            self._engine = None

    def __del__(self):
        self.close()


class AnalysisError(Exception):
    pass

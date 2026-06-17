"""第二轮端到端测试 - 验证本轮新增修复"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))

if os.path.exists('test_chess.db'):
    os.remove('test_chess.db')

from app import create_app, db
app = create_app('testing')
client = app.test_client()

print('=== 阶段 A：根 URL 返回 HTML ===')
r = client.get('/')
assert r.status_code == 200, f'expected 200 got {r.status_code}'
assert r.mimetype == 'text/html', f'expected html got {r.mimetype}'
assert '国际象棋数据管理平台' in r.data.decode('utf-8'), 'title not found in html'
assert '打开 Vue 前端' in r.data.decode('utf-8')
assert '打开管理控制台' in r.data.decode('utf-8')
print('A.1 GET / 返回 HTML 含"打开 Vue 前端"和"打开管理控制台"按钮 OK')

r = client.get('/api/health')
assert r.status_code == 200
assert r.json == {'status': 'ok', 'games': 0}
print('A.2 GET /api/health 返回 ok OK')


print('\n=== 阶段 B：DELETE /api/games/<id> 修复 ===')
# 准备 admin
admin_id = client.post('/api/auth/register', json={'username':'admin1','email':'a1@x.com','password':'pass1234'}).json['user']['id']
from app.models.user import User
with app.app_context():
    User.query.get(admin_id).is_admin = True
    db.session.commit()
admin_token = client.post('/api/auth/login', json={'username':'admin1','password':'pass1234'}).json['access_token']

# 普通用户
user_token = client.post('/api/auth/register', json={'username':'alice','email':'a@a.com','password':'pass1234'}).json['access_token']

# 先插入一个 game + 关联数据
from app.models.game import Game
from app.models.player import Player
from app.models.collection import Collection
from app.models.browsing_history import BrowsingHistory
from app.models.analysis import Analysis
from app.models.tournament import Tournament

with app.app_context():
    p = Player(name='P1', country='CN')
    db.session.add(p); db.session.commit()
    g = Game(
        white_player_id=p.id, black_player_id=p.id,
        pgn_content='1. e4 e5', eco_code='C20', result='1-0',
    )
    db.session.add(g); db.session.commit()
    gid = g.id
    a = Analysis(game_id=gid, analysis_data='{"score":0.3}', key_moves='["e2e4"]')
    db.session.add(a)
    db.session.commit()

# 通过 API 触发关联数据（更稳）
r = client.post(f'/api/collections', json={'game_id': gid, 'note': 'test'},
                headers={'Authorization': f'Bearer {user_token}'})
print(f'  [debug] add collection: {r.status_code} {r.json}')
r = client.post(f'/api/browsing', json={'game_id': gid},
                headers={'Authorization': f'Bearer {user_token}'})
print(f'  [debug] add browsing: {r.status_code} {r.json}')

# B.1 普通用户删除：403 (无权限)
r = client.delete(f'/api/games/{gid}', headers={'Authorization':f'Bearer {user_token}'})
print(f'B.1 普通用户 DELETE game: {r.status_code}', r.json.get('error','')[:80], 'OK')
assert r.status_code == 403
assert r.json.get('need_mod_request') is True

# B.2 admin 删，但有关联数据 → 409
r = client.delete(f'/api/games/{gid}', headers={'Authorization':f'Bearer {admin_token}'})
print(f'B.2 admin DELETE game 无 force: {r.status_code}', r.json.get('error','')[:60], 'OK')
assert r.status_code == 409
assert 'related' in r.json

# B.3 admin 删 + force=true
r = client.delete(f'/api/games/{gid}?force=true', headers={'Authorization':f'Bearer {admin_token}'})
print(f'B.3 admin DELETE game force=true: {r.status_code} cascade={r.json.get("cascade")}', 'OK')
assert r.status_code == 200
assert r.json['cascade']['collections'] >= 1
assert r.json['cascade']['browsing_history'] >= 1

# 验证 Game 真的删了
with app.app_context():
    assert Game.query.get(gid) is None
    assert Analysis.query.filter_by(game_id=gid).count() == 0
print('B.4 级联清理 OK (game + analysis)')


print('\n=== 阶段 C：mod-requests 校验 ===')
# C.1 长度校验
r = client.post('/api/mod-requests', json={
    'target_type':'puzzle','action':'create',
    'payload':{'name':'x'},
    'reason':'x'*600,
}, headers={'Authorization':f'Bearer {user_token}'})
print(f'C.1 reason 太长 600 字符: {r.status_code} {r.json.get("error", "")[:60]}')
assert r.status_code == 400

# C.2 XSS 校验
r = client.post('/api/mod-requests', json={
    'target_type':'puzzle','action':'create',
    'payload':{'name':'<script>alert(1)</script>'},
}, headers={'Authorization':f'Bearer {user_token}'})
print(f'C.2 payload 含 <script>: {r.status_code} {r.json.get("error", "")[:60]}')
assert r.status_code == 400

# C.3 正常申请
r = client.post('/api/mod-requests', json={
    'target_type':'puzzle','action':'create',
    'payload':{'name':'PuzzleA','fen':'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1','category':'endgame','difficulty':'easy'},
}, headers={'Authorization':f'Bearer {user_token}'})
print(f'C.3 正常申请: {r.status_code} json={r.json}')
assert r.status_code == 201
# 响应结构兼容多种：直接 to_dict 或 {request: to_dict} 或其他
req_obj = r.json.get('request') or r.json
alice_user_id = req_obj.get('user_id')
req_id = req_obj.get('id') or r.json.get('id')
print(f'  C.3 req_id={req_id} user_id={alice_user_id} status={req_obj.get("status")}')
r = client.post(f'/api/admin/mod-requests/{req_id}/review', json={'action':'approve','comment':'ok'}, headers={'Authorization':f'Bearer {admin_token}'})
print(f'C.4 审核通过: {r.status_code} status={r.json.get("status")}')
assert r.status_code == 200
assert r.json['status'] == 'approved'

# 验证 puzzle 真创建了，且 created_by=alice
from app.models.practice import Puzzle
with app.app_context():
    p = Puzzle.query.filter_by(name='PuzzleA').first()
    assert p is not None, 'puzzle not created'
    assert p.created_by == alice_user_id
    assert p.is_preset == False
print('C.5 Puzzle 已创建 created_by=alice OK')


print('\n=== 阶段 D：用户管理 API ===')
# D.1 列表
r = client.get('/api/admin/users?per_page=20', headers={'Authorization':f'Bearer {admin_token}'})
print(f'D.1 列表用户: {r.status_code}, total={r.json["total"]}')
assert r.status_code == 200
assert r.json['total'] == 2  # admin1 + alice
emails = [u['email'] for u in r.json['items']]
assert 'a@a.com' in emails and 'a1@x.com' in emails

# D.2 搜索
r = client.get('/api/admin/users?q=ali', headers={'Authorization':f'Bearer {admin_token}'})
print(f'D.2 搜索 ali: {r.status_code}, total={r.json["total"]}, items={[u["username"] for u in r.json["items"]]}')
assert r.json['total'] == 1
assert r.json['items'][0]['username'] == 'alice'

# D.3 重置密码
r = client.post(f'/api/admin/users/{alice_user_id}/reset_password', json={'new_password':'newpass1234'}, headers={'Authorization':f'Bearer {admin_token}'})
print(f'D.3 重置密码: {r.status_code} {r.json.get("message")}')
assert r.status_code == 200

# 用新密码登录
r = client.post('/api/auth/login', json={'username':'alice','password':'newpass1234'})
print(f'D.4 用新密码登录: {r.status_code}')
assert r.status_code == 200

# D.5 修改 is_admin（先把 alice 设为 admin，再改回）
r = client.patch(f'/api/admin/users/{alice_user_id}', json={'is_admin':True}, headers={'Authorization':f'Bearer {admin_token}'})
print(f'D.5 升 admin: {r.status_code} is_admin={r.json.get("is_admin")}')
assert r.status_code == 200
assert r.json['is_admin'] == True

r = client.patch(f'/api/admin/users/{alice_user_id}', json={'is_admin':False}, headers={'Authorization':f'Bearer {admin_token}'})
print(f'D.6 降回普通用户: {r.status_code} is_admin={r.json.get("is_admin")}')
assert r.status_code == 200
assert r.json['is_admin'] == False

# D.7 防最后 admin 自降
r = client.patch(f'/api/admin/users/{admin_id}', json={'is_admin':False}, headers={'Authorization':f'Bearer {admin_token}'})
print(f'D.7 最后一个 admin 自降: {r.status_code} {r.json.get("error", "")[:60]}')
assert r.status_code == 400

# D.8 防删除自己
r = client.delete(f'/api/admin/users/{admin_id}', headers={'Authorization':f'Bearer {admin_token}'})
print(f'D.8 自删: {r.status_code} {r.json.get("error", "")[:60]}')
assert r.status_code == 400

# D.9 删除 alice
r = client.delete(f'/api/admin/users/{alice_user_id}', headers={'Authorization':f'Bearer {admin_token}'})
print(f'D.9 删 alice: {r.status_code} {r.json.get("message")}')
assert r.status_code == 200

# D.10 stats
r = client.get('/api/admin/stats', headers={'Authorization':f'Bearer {admin_token}'})
print(f'D.10 stats: {r.status_code} keys={list(r.json.keys())}')
assert r.status_code == 200
assert 'users' in r.json and 'api_calls_24h' in r.json


print('\n=== 阶段 E：原有个性化与审核仍工作 ===')
# E.1 创建另一个用户并创建残局
bob_token = client.post('/api/auth/register', json={'username':'bob','email':'b@b.com','password':'pass1234'}).json['access_token']
r = client.post('/api/practice/puzzles', json={'name':'Bob P1','fen':'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1','category':'endgame','difficulty':'medium'}, headers={'Authorization':f'Bearer {bob_token}'})
print(f'E.1 bob 创建残局: {r.status_code} created_by={r.json.get("created_by")}')
assert r.json['created_by'] is not None

# E.2 bob 删自己的
r = client.delete(f'/api/practice/puzzles/{r.json["id"]}', headers={'Authorization':f'Bearer {bob_token}'})
print(f'E.2 bob 删自己: {r.status_code}')
assert r.status_code == 200

# E.3 bob 不能删 admin 创建的（先 admin 创建一个）
r = client.post('/api/practice/puzzles', json={'name':'Admin P1','fen':'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1','category':'endgame','difficulty':'medium'}, headers={'Authorization':f'Bearer {admin_token}'})
admin_puzzle_id = r.json['id']
print(f'E.3 admin 创建残局 id={admin_puzzle_id}')

r = client.delete(f'/api/practice/puzzles/{admin_puzzle_id}', headers={'Authorization':f'Bearer {bob_token}'})
print(f'E.4 bob 删 admin 的: {r.status_code} {r.json.get("error", "")[:50]}')
assert r.status_code == 403

# E.5 admin 删自己的
r = client.delete(f'/api/practice/puzzles/{admin_puzzle_id}', headers={'Authorization':f'Bearer {admin_token}'})
print(f'E.5 admin 删自己的: {r.status_code}')
assert r.status_code == 200


print('\n=== ALL TESTS PASSED ===')
print('[OK] root URL returns HTML')
print('[OK] games DELETE 500 fixed')
print('[OK] practice DELETE permission fixed')
print('[OK] mod-requests length/XSS validation works')
print('[OK] puzzle create review flow works')
print('[OK] user management: list/search/role/reset-pwd/delete/safe-guard')
print('[OK] existing features not regressed')

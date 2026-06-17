"""端到端集成测试 - 验证修复后功能"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))

if os.path.exists('test_chess.db'):
    os.remove('test_chess.db')

from app import create_app, db
app = create_app('testing')
client = app.test_client()

print('=== 阶段 1：用户注册 ===')
alice_token = client.post('/api/auth/register', json={'username':'alice','email':'a@a.com','password':'pass1234'}).json['access_token']
bob_token = client.post('/api/auth/register', json={'username':'bob','email':'b@b.com','password':'pass1234'}).json['access_token']
print('1. register alice & bob: OK')

print('\n=== 阶段 2：个性化残局 ===')
p1 = client.post('/api/practice/puzzles', json={'name':'Alice P1','fen':'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1','category':'endgame','difficulty':'medium'}, headers={'Authorization':f'Bearer {alice_token}'}).json
p2 = client.post('/api/practice/puzzles', json={'name':'Bob P1','fen':'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1','category':'endgame','difficulty':'medium'}, headers={'Authorization':f'Bearer {bob_token}'}).json
assert p1['created_by'] == 1, f"Expected created_by=1, got {p1['created_by']}"
assert p2['created_by'] == 2, f"Expected created_by=2, got {p2['created_by']}"
print('2.1 alice created puzzle id=', p1['id'], 'created_by=', p1['created_by'], 'OK')
print('2.2 bob created puzzle id=', p2['id'], 'created_by=', p2['created_by'], 'OK')

a_mine = client.get('/api/practice/puzzles?only_mine=1', headers={'Authorization':f'Bearer {alice_token}'}).json['puzzles']
b_mine = client.get('/api/practice/puzzles?only_mine=1', headers={'Authorization':f'Bearer {bob_token}'}).json['puzzles']
print('2.3 alice only_mine:', [p['name'] for p in a_mine], 'OK')
print('2.4 bob only_mine:', [p['name'] for p in b_mine], 'OK')
assert len(a_mine) == 1 and a_mine[0]['name'] == 'Alice P1'
assert len(b_mine) == 1 and b_mine[0]['name'] == 'Bob P1'

a_all = client.get('/api/practice/puzzles', headers={'Authorization':f'Bearer {alice_token}'}).json['puzzles']
print('2.5 alice default view (preset + mine):', len(a_all), 'puzzles, all named:', [p['name'] for p in a_all[:3]], '... OK')
guest = client.get('/api/practice/puzzles').json['puzzles']
print('2.6 guest view (preset only):', len(guest), 'puzzles OK')
assert all(p['is_preset'] for p in guest)

print('\n=== 阶段 3：修改申请审核 ===')
r = client.post('/api/mod-requests', json={'target_type':'puzzle','action':'delete','target_id':p1['id'],'reason':'test delete'}, headers={'Authorization':f'Bearer {alice_token}'})
print('3.1 submit mod-request:', r.status_code, r.json.get('message'), 'OK')

admin_id = client.post('/api/auth/register', json={'username':'admin2','email':'a2@x.com','password':'pass1234'}).json['user']['id']
from app.models.user import User
with app.app_context():
    User.query.get(admin_id).is_admin = True
    db.session.commit()
admin_token = client.post('/api/auth/login', json={'username':'admin2','password':'pass1234'}).json['access_token']

r = client.get('/api/admin/mod-requests', headers={'Authorization':f'Bearer {admin_token}'})
print('3.2 admin list requests:', r.status_code, 'count=', r.json['total'], 'OK')
assert r.json['total'] >= 1

r = client.post(f'/api/admin/mod-requests/1/review', json={'action':'approve','comment':'ok'}, headers={'Authorization':f'Bearer {admin_token}'})
print('3.3 admin approve #1:', r.status_code, '-> status=', r.json and r.json.get('status'), 'OK')
assert r.json['status'] == 'approved'

r = client.get('/api/practice/puzzles?only_mine=1', headers={'Authorization':f'Bearer {alice_token}'})
print('3.4 after approve, alice only_mine:', [p['name'] for p in r.json['puzzles']], 'OK')
assert len(r.json['puzzles']) == 0  # 已被删除

print('\n=== 阶段 4：流量监测 ===')
r = client.get('/api/admin/traffic/summary', headers={'Authorization':f'Bearer {admin_token}'})
print('4.1 traffic summary:', r.status_code, r.json['summary'], 'OK')
assert r.json['summary']['total_requests'] > 0

r = client.get('/api/admin/traffic/recent?limit=10', headers={'Authorization':f'Bearer {admin_token}'})
print('4.2 traffic recent:', r.status_code, 'logs count=', len(r.json['logs']), 'OK')

print('\n=== 全部测试通过！===')

from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random
from collections import Counter

app = Flask(__name__)
app.secret_key = "big2_secret_key_2024"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///big2.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------- 隨機名字庫 ----------
AI_NAMES = [
    '陳珈銘', '陳德楨', '陳賢峰', '陈星羽', '徐健強', '林奧深', '劉夢桐', '羅威', 
    '梁駿豪', '李栢濂', '吳錕洋', '彭昊琛', '蘇炳杰', '戴卓宏', '鄧騏瑋', '鄧偉圖',
    '丁家俊', '蔡繼晟', '黃詠濠', '楊一', '殷杰輝', '袁景軒','陳卓文','','陳賢峰', '鄧騏瑋','kitson','Harry'
]

def get_random_names():
    """隨機選取3個不同的AI名字"""
    return random.sample(AI_NAMES, 3)

# ---------- 撲克牌設定 ----------
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2']
RANK_VALUE = {r: i for i, r in enumerate(RANKS)}
SUIT_VALUE = {'♠': 3, '♥': 2, '♦': 1, '♣': 0}

class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
    
    def __repr__(self):
        return f"{self.suit}{self.rank}"
    
    def __eq__(self, other):
        return self.suit == other.suit and self.rank == other.rank
    
    def get_value(self):
        return (RANK_VALUE[self.rank], SUIT_VALUE[self.suit])

def create_deck():
    return [Card(s, r) for s in SUITS for r in RANKS]

def sort_cards(cards):
    return sorted(cards, key=lambda c: c.get_value())

def deal_cards():
    deck = create_deck()
    random.shuffle(deck)
    hands = [sort_cards(deck[i::4]) for i in range(4)]
    return hands

# ---------- 牌型判斷 ----------
def is_valid_card_combination(cards):
    if not cards:
        return False, None, None
    
    n = len(cards)
    
    if n == 1:
        return True, 'single', cards[0].get_value()
    
    if n == 2 and cards[0].rank == cards[1].rank:
        return True, 'pair', (RANK_VALUE[cards[0].rank],)
    
    if n == 3 and cards[0].rank == cards[1].rank == cards[2].rank:
        return True, 'triple', (RANK_VALUE[cards[0].rank],)
    
    if n == 5:
        is_flush = len(set(c.suit for c in cards)) == 1
        ranks = sorted([RANK_VALUE[c.rank] for c in cards])
        
        is_straight = False
        if ranks == list(range(ranks[0], ranks[0] + 5)):
            is_straight = True
        elif ranks == [0, 1, 2, 12, 13]:
            is_straight = True
            ranks = [0, 1, 2, 3, 12]
        
        if is_flush and is_straight:
            max_rank = max(ranks)
            return True, 'straight_flush', (max_rank,)
        
        rank_counts = Counter(c.rank for c in cards)
        if 4 in rank_counts.values():
            four_rank = [r for r, cnt in rank_counts.items() if cnt == 4][0]
            return True, 'four', (RANK_VALUE[four_rank],)
        
        if sorted(rank_counts.values()) == [2, 3]:
            three_rank = [r for r, cnt in rank_counts.items() if cnt == 3][0]
            return True, 'full_house', (RANK_VALUE[three_rank],)
        
        if is_flush:
            rank_values = sorted([RANK_VALUE[c.rank] for c in cards], reverse=True)
            return True, 'flush', tuple(rank_values)
        
        if is_straight:
            max_rank = max(ranks)
            return True, 'straight', (max_rank,)
    
    return False, None, None

def can_beat(prev_type, prev_key, curr_type, curr_key):
    if prev_type is None:
        return True
    if curr_type is None:
        return False
    if curr_type != prev_type:
        return False
    return curr_key > prev_key

# ---------- AI 邏輯 ----------
def find_best_move(hand, prev_cards):
    if prev_cards is None:
        if hand:
            return [hand[0]]
        return None
    
    prev_valid, prev_type, prev_key = is_valid_card_combination(prev_cards)
    if not prev_valid:
        return None
    
    hand_sorted = sort_cards(hand)
    
    if prev_type == 'single':
        for card in hand_sorted:
            if card.get_value() > prev_key:
                return [card]
    
    elif prev_type == 'pair':
        for i in range(len(hand_sorted) - 1):
            if hand_sorted[i].rank == hand_sorted[i + 1].rank:
                pair_key = (RANK_VALUE[hand_sorted[i].rank],)
                if pair_key > prev_key:
                    return [hand_sorted[i], hand_sorted[i + 1]]
    
    elif prev_type == 'triple':
        for i in range(len(hand_sorted) - 2):
            if hand_sorted[i].rank == hand_sorted[i + 1].rank == hand_sorted[i + 2].rank:
                triple_key = (RANK_VALUE[hand_sorted[i].rank],)
                if triple_key > prev_key:
                    return [hand_sorted[i], hand_sorted[i + 1], hand_sorted[i + 2]]
    
    elif prev_type == 'full_house':
        rank_counts = Counter(c.rank for c in hand_sorted)
        for rank, cnt in rank_counts.items():
            if cnt >= 3:
                triple_key = (RANK_VALUE[rank],)
                if triple_key > prev_key:
                    triple = [c for c in hand_sorted if c.rank == rank][:3]
                    remaining = [c for c in hand_sorted if c not in triple]
                    for r2, cnt2 in Counter(c.rank for c in remaining).items():
                        if cnt2 >= 2:
                            pair = [c for c in remaining if c.rank == r2][:2]
                            return triple + pair
    
    elif prev_type == 'four':
        rank_counts = Counter(c.rank for c in hand_sorted)
        for rank, cnt in rank_counts.items():
            if cnt >= 4:
                four_key = (RANK_VALUE[rank],)
                if four_key > prev_key:
                    four = [c for c in hand_sorted if c.rank == rank][:4]
                    remaining = [c for c in hand_sorted if c not in four]
                    if remaining:
                        return four + [remaining[0]]
    
    elif prev_type in ['straight', 'flush', 'straight_flush']:
        from itertools import combinations
        for comb in combinations(hand_sorted, 5):
            valid, c_type, c_key = is_valid_card_combination(list(comb))
            if valid and c_type == prev_type and c_key > prev_key:
                return list(comb)
    
    return None

class GameRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    winner = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# ---------- Flask 路由 ----------
@app.route('/')
def index():
    return render_template('game.html')

@app.route('/start_game', methods=['POST'])
def start_game():
    hands = deal_cards()
    ai_names = get_random_names()
    
    session.clear()
    session['hands'] = [[str(c) for c in h] for h in hands]
    session['ai_names'] = ai_names
    session['current_player'] = 0
    session['last_cards'] = None
    session['last_player'] = None
    session['pass_count'] = 0
    session['game_over'] = False
    session['winner'] = None
    session.modified = True
    
    return jsonify({'success': True, 'ai_names': ai_names})

@app.route('/reset')
def reset():
    session.clear()
    return redirect('/')

@app.route('/state')
def get_state():
    if session.get('game_over'):
        return jsonify({
            'game_over': True,
            'winner': session.get('winner'),
            'hands': session.get('hands'),
            'current_player': session.get('current_player'),
            'last_cards': session.get('last_cards'),
            'cards_count': [len(h) for h in session.get('hands', [[],[],[],[]])],
            'ai_names': session.get('ai_names', ['AI 1', 'AI 2', 'AI 3'])
        })
    
    if session.get('hands') and session['hands'][0] == []:
        session['game_over'] = True
        session['winner'] = '玩家'
        db.session.add(GameRecord(winner='玩家'))
        db.session.commit()
    
    return jsonify({
        'game_over': session.get('game_over', False),
        'winner': session.get('winner'),
        'hands': session.get('hands'),
        'current_player': session.get('current_player'),
        'last_cards': session.get('last_cards'),
        'last_player': session.get('last_player'),
        'cards_count': [len(h) for h in session.get('hands', [[],[],[],[]])],
        'ai_names': session.get('ai_names', ['AI 1', 'AI 2', 'AI 3'])
    })

@app.route('/play', methods=['POST'])
def play_cards():
    if session.get('game_over'):
        return jsonify({'success': False, 'message': '遊戲已結束'})
    
    if session['current_player'] != 0:
        return jsonify({'success': False, 'message': '不是你的回合'})
    
    data = request.json
    indices = data.get('indices', [])
    
    if not indices:
        return jsonify({'success': False, 'message': '請選擇要出的牌'})
    
    hand = [Card(s[0], s[1:]) for s in session['hands'][0]]
    selected = [hand[i] for i in indices if i < len(hand)]
    
    if len(selected) != len(indices):
        return jsonify({'success': False, 'message': '選擇的牌無效'})
    
    valid, card_type, card_key = is_valid_card_combination(selected)
    if not valid:
        return jsonify({'success': False, 'message': '無效的牌型'})
    
    last_cards = None
    if session['last_cards']:
        last_cards = [Card(s[0], s[1:]) for s in session['last_cards']]
        last_valid, last_type, last_key = is_valid_card_combination(last_cards)
        if not can_beat(last_type, last_key, card_type, card_key):
            return jsonify({'success': False, 'message': '牌太小，無法壓過上一手'})
    
    new_hand = [c for c in hand if c not in selected]
    session['hands'][0] = [str(c) for c in sort_cards(new_hand)]
    session['last_cards'] = [str(c) for c in selected]
    session['last_player'] = 0
    session['pass_count'] = 0
    
    if len(new_hand) == 0:
        session['game_over'] = True
        session['winner'] = '玩家'
        db.session.add(GameRecord(winner='玩家'))
        db.session.commit()
        return jsonify({'success': True, 'game_over': True, 'winner': '玩家'})
    
    session['current_player'] = 1
    session.modified = True
    
    return jsonify({'success': True, 'next_player': 1, 'cards': [str(c) for c in selected]})

@app.route('/pass')
def pass_turn():
    if session.get('game_over'):
        return jsonify({'success': False, 'message': '遊戲已結束'})
    
    current = session['current_player']
    
    if current == 0:
        session['pass_count'] += 1
        
        if session['pass_count'] >= 3:
            session['last_cards'] = None
            session['pass_count'] = 0
            if session['last_player'] is not None:
                session['current_player'] = session['last_player']
            else:
                session['current_player'] = 0
        else:
            session['current_player'] = (current + 1) % 4
        
        session.modified = True
        return jsonify({'success': True, 'next_player': session['current_player']})
    
    return jsonify({'success': False, 'message': '不是你的回合'})

@app.route('/ai')
def ai_move():
    if session.get('game_over'):
        return jsonify({'success': False, 'game_over': True})
    
    current = session['current_player']
    if current == 0:
        return jsonify({'success': False, 'message': '玩家的回合'})
    
    # 獲取AI名字
    ai_names = session.get('ai_names', ['AI 1', 'AI 2', 'AI 3'])
    ai_name = ai_names[current - 1]
    
    hand = [Card(s[0], s[1:]) for s in session['hands'][current]]
    last_cards = None
    if session['last_cards']:
        last_cards = [Card(s[0], s[1:]) for s in session['last_cards']]
    
    move = find_best_move(hand, last_cards)
    
    if move is None:
        session['pass_count'] += 1
        
        if session['pass_count'] >= 3:
            session['last_cards'] = None
            session['pass_count'] = 0
            if session['last_player'] is not None:
                session['current_player'] = session['last_player']
            else:
                session['current_player'] = 0
        else:
            session['current_player'] = (current + 1) % 4
        
        session.modified = True
        return jsonify({'success': True, 'action': 'pass', 'next_player': session['current_player'], 'ai_name': ai_name})
    else:
        new_hand = [c for c in hand if c not in move]
        session['hands'][current] = [str(c) for c in sort_cards(new_hand)]
        session['last_cards'] = [str(c) for c in move]
        session['last_player'] = current
        session['pass_count'] = 0
        
        if len(new_hand) == 0:
            winner_name = ai_name
            session['game_over'] = True
            session['winner'] = winner_name
            db.session.add(GameRecord(winner=winner_name))
            db.session.commit()
            return jsonify({'success': True, 'action': 'win', 'winner': winner_name, 'ai_name': ai_name})
        
        session['current_player'] = (current + 1) % 4
        session.modified = True
        return jsonify({'success': True, 'action': 'play', 'cards': [str(c) for c in move], 'next_player': session['current_player'], 'ai_name': ai_name})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
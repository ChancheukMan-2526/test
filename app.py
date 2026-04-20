from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random
import itertools
from collections import Counter

app = Flask(__name__)
app.secret_key = "big2_advanced_secret"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///big2_game.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------- 資料庫 ----------
class GameRecord(db.Model):
    __tablename__ = "game_records"
    id = db.Column(db.Integer, primary_key=True)
    winner = db.Column(db.String(20), nullable=False)
    create_time = db.Column(db.DateTime, default=datetime.now)

# ---------- 撲克牌 ----------
SUITS = ['♣', '♦', '♥', '♠']
RANKS = ['3','4','5','6','7','8','9','10','J','Q','K','A','2']
RANK_VALUE = {r:i for i,r in enumerate(RANKS)}
SUIT_VALUE = {'♣':0, '♦':1, '♥':2, '♠':3}

class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
    def __repr__(self):
        return f"{self.suit}{self.rank}"
    def key(self):
        return (RANK_VALUE[self.rank], SUIT_VALUE[self.suit])
    def __eq__(self, other):
        return self.rank == other.rank and self.suit == other.suit

def sort_hand(hand):
    return sorted(hand, key=lambda c: (RANK_VALUE[c.rank], SUIT_VALUE[c.suit]))

def create_deck():
    return [Card(s, r) for s in SUITS for r in RANKS]

def shuffle_and_deal():
    deck = create_deck()
    random.shuffle(deck)
    hands = [deck[i::4] for i in range(4)]
    return [sort_hand(h) for h in hands]

def get_card_key(card):
    return (RANK_VALUE[card.rank], SUIT_VALUE[card.suit])

def is_straight(cards):
    if len(cards) != 5:
        return False
    rank_indices = sorted([RANK_VALUE[c.rank] for c in cards])
    if rank_indices == list(range(rank_indices[0], rank_indices[0]+5)):
        return True
    if set(rank_indices) == {0,1,2,12,13}:
        return True
    return False

def is_flush(cards):
    return len(set(c.suit for c in cards)) == 1

def is_straight_flush(cards):
    return is_straight(cards) and is_flush(cards)

def is_four_of_kind(cards):
    if len(cards) != 5:
        return False
    counts = Counter(c.rank for c in cards)
    return 4 in counts.values()

def is_full_house(cards):
    if len(cards) != 5:
        return False
    counts = Counter(c.rank for c in cards)
    return sorted(counts.values()) == [2,3]

def is_three(cards):
    return len(cards) == 3 and len(set(c.rank for c in cards)) == 1

def is_pair(cards):
    return len(cards) == 2 and cards[0].rank == cards[1].rank

def get_hand_type(cards):
    if not cards:
        return None, None
    if len(cards) == 1:
        return 'single', get_card_key(cards[0])
    if len(cards) == 2 and is_pair(cards):
        return 'pair', (RANK_VALUE[cards[0].rank],)
    if len(cards) == 3 and is_three(cards):
        return 'three', (RANK_VALUE[cards[0].rank],)
    if len(cards) == 5:
        if is_straight_flush(cards):
            ranks = sorted([RANK_VALUE[c.rank] for c in cards])
            if set(ranks) == {0,1,2,12,13}:
                max_rank = 2
            else:
                max_rank = max(ranks)
            return 'straight_flush', (max_rank,)
        if is_four_of_kind(cards):
            cnt = Counter(c.rank for c in cards)
            four_rank = [r for r,count in cnt.items() if count==4][0]
            return 'four', (RANK_VALUE[four_rank],)
        if is_full_house(cards):
            cnt = Counter(c.rank for c in cards)
            three_rank = [r for r,count in cnt.items() if count==3][0]
            return 'full_house', (RANK_VALUE[three_rank],)
        if is_flush(cards):
            rank_values = sorted([RANK_VALUE[c.rank] for c in cards], reverse=True)
            return 'flush', tuple(rank_values)
        if is_straight(cards):
            ranks = sorted([RANK_VALUE[c.rank] for c in cards])
            if set(ranks) == {0,1,2,12,13}:
                max_rank = 2
            else:
                max_rank = max(ranks)
            return 'straight', (max_rank,)
    return None, None

def can_beat(current_type, current_key, last_type, last_key):
    if current_type is None:
        return False
    if last_type is None:
        return True
    if current_type != last_type:
        return False
    return current_key > last_key

def find_smallest_beating_cards(hand, last_cards):
    if last_cards is None:
        if hand:
            smallest = min(hand, key=get_card_key)
            return [smallest], 'single', get_card_key(smallest)
        return None, None, None

    last_type, last_key = get_hand_type(last_cards)
    if last_type is None:
        return None, None, None

    hand_sorted = sort_hand(hand)

    if last_type == 'single':
        for card in hand_sorted:
            if get_card_key(card) > last_key:
                return [card], 'single', get_card_key(card)
    elif last_type == 'pair':
        rank_counts = Counter(c.rank for c in hand)
        for rank in sorted(rank_counts.keys(), key=lambda r: RANK_VALUE[r]):
            if rank_counts[rank] >= 2 and (RANK_VALUE[rank],) > last_key:
                pair = [c for c in hand if c.rank == rank][:2]
                return pair, 'pair', (RANK_VALUE[rank],)
    elif last_type == 'three':
        rank_counts = Counter(c.rank for c in hand)
        for rank in sorted(rank_counts.keys(), key=lambda r: RANK_VALUE[r]):
            if rank_counts[rank] >= 3 and (RANK_VALUE[rank],) > last_key:
                triple = [c for c in hand if c.rank == rank][:3]
                return triple, 'three', (RANK_VALUE[rank],)
    elif last_type in ('straight', 'straight_flush', 'flush'):
        best = None
        best_key = None
        for comb in itertools.combinations(hand_sorted, 5):
            comb_list = list(comb)
            t, k = get_hand_type(comb_list)
            if t == last_type and can_beat(t, k, last_type, last_key):
                if best_key is None or k < best_key:
                    best_key = k
                    best = comb_list
        if best:
            return best, last_type, best_key
    elif last_type == 'four':
        rank_counts = Counter(c.rank for c in hand)
        for rank, cnt in rank_counts.items():
            if cnt >= 4 and (RANK_VALUE[rank],) > last_key:
                four_cards = [c for c in hand if c.rank == rank][:4]
                remaining = [c for c in hand if c not in four_cards]
                if remaining:
                    kicker = min(remaining, key=get_card_key)
                    full = four_cards + [kicker]
                    return full, 'four', (RANK_VALUE[rank],)
    elif last_type == 'full_house':
        rank_counts = Counter(c.rank for c in hand)
        for rank, cnt in rank_counts.items():
            if cnt >= 3 and (RANK_VALUE[rank],) > last_key:
                three_cards = [c for c in hand if c.rank == rank][:3]
                remaining = [c for c in hand if c not in three_cards]
                for r2, cnt2 in Counter(c.rank for c in remaining).items():
                    if cnt2 >= 2:
                        pair = [c for c in remaining if c.rank == r2][:2]
                        return three_cards+pair, 'full_house', (RANK_VALUE[rank],)
    return None, None, None

def ai_choose_move(hand, last_cards):
    cards, _, _ = find_smallest_beating_cards(hand, last_cards)
    return cards

# ---------- 初始化 ----------
def init_game_session():
    hands = shuffle_and_deal()
    session.clear()
    session['hands'] = [[c.__repr__() for c in h] for h in hands]
    session['current_player'] = 0
    session['last_play'] = None
    session['last_player'] = None
    session['winner'] = None
    session['game_over'] = False
    session['pass_count'] = 0
    session['round_owner'] = None
    session.modified = True

@app.route('/')
def index():
    if 'hands' not in session or session.get('game_over', True):
        init_game_session()
    return render_template('game.html', user="訪客")

@app.route('/reset')
def reset():
    session.clear()
    return redirect('/')

@app.route('/get_state')
def get_state():
    if not session.get('game_over') and session.get('hands') and len(session['hands'][0]) == 0:
        session['winner'] = "玩家"
        session['game_over'] = True
        db.session.add(GameRecord(winner="玩家"))
        db.session.commit()
    if session.get('game_over'):
        return jsonify({
            'hands': session.get('hands'),
            'current_player': session.get('current_player'),
            'last_play': session.get('last_play'),
            'winner': session.get('winner'),
            'game_over': True
        })
    return jsonify({
        'hands': session.get('hands'),
        'current_player': session.get('current_player'),
        'last_play': session.get('last_play'),
        'last_player': session.get('last_player'),
        'winner': session.get('winner'),
        'game_over': False
    })

@app.route('/play', methods=['POST'])
def play():
    if session.get('game_over'):
        return jsonify({'status': 'game_over', 'winner': session['winner']})
    
    data = request.get_json()
    indices = data.get('indices', [])
    print("收到出牌請求, indices =", indices)
    
    current_hand_str = session['hands'][session['current_player']]
    selected_strs = [current_hand_str[i] for i in indices if i < len(current_hand_str)]
    if not selected_strs:
        return jsonify({'status': 'error', 'msg': '請選取手牌中的牌'})
    
    selected = [Card(s[0], s[1:]) for s in selected_strs]
    
    last_cards = None
    if session['last_play']:
        last_cards = [Card(s[0], s[1:]) for s in session['last_play']]
    
    current_type, current_key = get_hand_type(selected)
    last_type, last_key = get_hand_type(last_cards) if last_cards else (None, None)
    if current_type is None:
        return jsonify({'status': 'error', 'msg': '無效牌型'})
    if not can_beat(current_type, current_key, last_type, last_key):
        return jsonify({'status': 'error', 'msg': '牌型不符或點數太小'})
    
    new_hand_str = [card for i, card in enumerate(current_hand_str) if i not in indices]
    new_hand = [Card(s[0], s[1:]) for s in new_hand_str]
    new_hand_sorted = sort_hand(new_hand)
    session['hands'][session['current_player']] = [c.__repr__() for c in new_hand_sorted]
    session['last_play'] = selected_strs
    session['last_player'] = session['current_player']
    session['pass_count'] = 0
    session['round_owner'] = session['current_player']
    
    if len(new_hand) == 0:
        session['winner'] = "玩家"
        session['game_over'] = True
        db.session.add(GameRecord(winner="玩家"))
        db.session.commit()
        return jsonify({'status': 'win', 'winner': "玩家"})
    
    next_player = (session['current_player'] + 1) % 4
    session['current_player'] = next_player
    session.modified = True
    return jsonify({'status': 'ok', 'next_player': next_player, 'is_ai': next_player != 0})

@app.route('/pass', methods=['POST'])
def pass_turn():
    if session.get('game_over'):
        return jsonify({'status': 'game_over'})
    current = session['current_player']
    if current != 0:
        return jsonify({'status': 'error', 'msg': '不是你的回合'})
    
    session['pass_count'] += 1
    if session['pass_count'] >= 3:
        session['last_play'] = None
        session['last_player'] = None
        session['pass_count'] = 0
        if session['round_owner'] is not None:
            session['current_player'] = session['round_owner']
        else:
            session['current_player'] = 0
    else:
        session['current_player'] = (current + 1) % 4
    session.modified = True
    return jsonify({'status': 'ok', 'next_player': session['current_player']})

@app.route('/ai_move', methods=['GET'])
def ai_move():
    if session.get('game_over'):
        return jsonify({'status': 'game_over'})
    
    player = session['current_player']
    if player == 0:
        return jsonify({'status': 'player_turn'})
    
    hand_str = session['hands'][player]
    hand = [Card(s[0], s[1:]) for s in hand_str]
    last_cards = None
    if session['last_play']:
        last_cards = [Card(s[0], s[1:]) for s in session['last_play']]
    
    played = ai_choose_move(hand, last_cards)
    if played is None:
        session['pass_count'] += 1
        if session['pass_count'] >= 3:
            session['last_play'] = None
            session['last_player'] = None
            session['pass_count'] = 0
            if session['round_owner'] is not None:
                session['current_player'] = session['round_owner']
            else:
                session['current_player'] = 0
        else:
            session['current_player'] = (player + 1) % 4
        session.modified = True
        return jsonify({'status': 'pass', 'next_player': session['current_player']})
    else:
        new_hand = [c for c in hand if c not in played]
        new_hand_sorted = sort_hand(new_hand)
        session['hands'][player] = [c.__repr__() for c in new_hand_sorted]
        session['last_play'] = [c.__repr__() for c in played]
        session['last_player'] = player
        session['pass_count'] = 0
        session['round_owner'] = player
        if len(new_hand) == 0:
            winner_name = f"AI {player}"
            session['winner'] = winner_name
            session['game_over'] = True
            db.session.add(GameRecord(winner=winner_name))
            db.session.commit()
            return jsonify({'status': 'win', 'winner': winner_name})
        session['current_player'] = (player + 1) % 4
        session.modified = True
        return jsonify({'status': 'play', 'cards': [c.__repr__() for c in played], 'next_player': session['current_player']})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
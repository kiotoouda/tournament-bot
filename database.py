import sqlite3
import json
from datetime import datetime

class Database:
    def __init__(self, db_path='tournament.db'):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tournaments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tournaments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                max_teams INTEGER NOT NULL,
                current_teams INTEGER DEFAULT 0,
                status TEXT DEFAULT 'registration',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                bracket_data TEXT
            )
        ''')
        
        # Teams table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER,
                name TEXT NOT NULL,
                leader_username TEXT NOT NULL,
                roster TEXT NOT NULL,  # JSON string of roster data
                photos TEXT NOT NULL,   # JSON string of photo file_ids
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tournament_id) REFERENCES tournaments (id)
            )
        ''')
        
        # Matches table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER,
                round_number INTEGER,
                match_number INTEGER,
                team_a_id INTEGER,
                team_b_id INTEGER,
                winner_id INTEGER,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (tournament_id) REFERENCES tournaments (id),
                FOREIGN KEY (team_a_id) REFERENCES teams (id),
                FOREIGN KEY (team_b_id) REFERENCES teams (id),
                FOREIGN KEY (winner_id) REFERENCES teams (id)
            )
        ''')
        
        conn.commit()
        conn.close()

    def create_tournament(self, name, max_teams):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO tournaments (name, max_teams) VALUES (?, ?)',
            (name, max_teams)
        )
        tournament_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return tournament_id

    def get_tournament(self, tournament_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tournaments WHERE id = ?', (tournament_id,))
        result = cursor.fetchone()
        conn.close()
        return result

    def get_active_tournaments(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tournaments WHERE status = "registration"')
        results = cursor.fetchall()
        conn.close()
        return results

    def register_team(self, tournament_id, name, leader_username, roster, photos):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if team name already exists in tournament
        cursor.execute(
            'SELECT id FROM teams WHERE tournament_id = ? AND name = ?',
            (tournament_id, name)
        )
        if cursor.fetchone():
            conn.close()
            return False, "Team name already exists in this tournament"
        
        # Check if tournament is full
        cursor.execute(
            'SELECT current_teams, max_teams FROM tournaments WHERE id = ?',
            (tournament_id,)
        )
        tournament = cursor.fetchone()
        if tournament[0] >= tournament[1]:
            conn.close()
            return False, "Tournament is full"
        
        # Register team
        cursor.execute(
            'INSERT INTO teams (tournament_id, name, leader_username, roster, photos) VALUES (?, ?, ?, ?, ?)',
            (tournament_id, name, leader_username, json.dumps(roster), json.dumps(photos))
        )
        
        # Update team count
        cursor.execute(
            'UPDATE tournaments SET current_teams = current_teams + 1 WHERE id = ?',
            (tournament_id,)
        )
        
        # Check if tournament is now full
        cursor.execute(
            'SELECT current_teams, max_teams FROM tournaments WHERE id = ?',
            (tournament_id,)
        )
        updated_tournament = cursor.fetchone()
        
        conn.commit()
        conn.close()
        
        is_full = updated_tournament[0] == updated_tournament[1]
        return True, "Team registered successfully", is_full

    def get_tournament_teams(self, tournament_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM teams WHERE tournament_id = ?', (tournament_id,))
        results = cursor.fetchall()
        conn.close()
        return results

    def get_team_details(self, team_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM teams WHERE id = ?', (team_id,))
        result = cursor.fetchone()
        conn.close()
        return result

    def create_bracket(self, tournament_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Update tournament status
        cursor.execute(
            'UPDATE tournaments SET status = "ongoing" WHERE id = ?',
            (tournament_id,)
        )
        
        # Get all teams for the tournament
        teams = self.get_tournament_teams(tournament_id)
        
        # Create first round matches
        round_number = 1
        for i in range(0, len(teams), 2):
            if i + 1 < len(teams):
                cursor.execute(
                    'INSERT INTO matches (tournament_id, round_number, match_number, team_a_id, team_b_id) VALUES (?, ?, ?, ?, ?)',
                    (tournament_id, round_number, (i//2)+1, teams[i][0], teams[i+1][0])
                )
        
        conn.commit()
        conn.close()

    def get_current_matches(self, tournament_id, round_number=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if round_number:
            cursor.execute(
                'SELECT * FROM matches WHERE tournament_id = ? AND round_number = ? AND status = "pending"',
                (tournament_id, round_number)
            )
        else:
            cursor.execute(
                'SELECT * FROM matches WHERE tournament_id = ? AND status = "pending"',
                (tournament_id,)
            )
        
        results = cursor.fetchall()
        conn.close()
        return results

    def set_match_winner(self, match_id, winner_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'UPDATE matches SET winner_id = ?, status = "completed" WHERE id = ?',
            (winner_id, match_id)
        )
        
        conn.commit()
        conn.close()

    def create_next_round(self, tournament_id, current_round):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get winners from current round
        cursor.execute(
            'SELECT winner_id FROM matches WHERE tournament_id = ? AND round_number = ? AND status = "completed"',
            (tournament_id, current_round)
        )
        winners = [row[0] for row in cursor.fetchall()]
        
        # Create next round matches
        next_round = current_round + 1
        for i in range(0, len(winners), 2):
            if i + 1 < len(winners):
                cursor.execute(
                    'INSERT INTO matches (tournament_id, round_number, match_number, team_a_id, team_b_id) VALUES (?, ?, ?, ?, ?)',
                    (tournament_id, next_round, (i//2)+1, winners[i], winners[i+1])
                )
        
        conn.commit()
        conn.close()

    def delete_tournament(self, tournament_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Delete matches
        cursor.execute('DELETE FROM matches WHERE tournament_id = ?', (tournament_id,))
        # Delete teams
        cursor.execute('DELETE FROM teams WHERE tournament_id = ?', (tournament_id,))
        # Delete tournament
        cursor.execute('DELETE FROM tournaments WHERE id = ?', (tournament_id,))
        
        conn.commit()
        conn.close()

    def delete_team(self, team_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get tournament_id before deletion
        cursor.execute('SELECT tournament_id FROM teams WHERE id = ?', (team_id,))
        result = cursor.fetchone()
        tournament_id = result[0] if result else None
        
        # Delete team
        cursor.execute('DELETE FROM teams WHERE id = ?', (team_id,))
        
        # Update team count
        if tournament_id:
            cursor.execute(
                'UPDATE tournaments SET current_teams = current_teams - 1 WHERE id = ?',
                (tournament_id,)
            )
        
        conn.commit()
        conn.close()

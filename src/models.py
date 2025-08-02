from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=True)  # Nullable für OAuth users
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    profile_image = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_premium = db.Column(db.Boolean, default=False)
    total_rolls = db.Column(db.Integer, default=0)
    
    # Relationship
    rolls = db.relationship('DiceRoll', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        if self.password_hash is None:
            return False
        return check_password_hash(self.password_hash, password)
    
    def get_stats(self):
        """Benutzer-Statistiken berechnen"""
        return {
            'total_rolls': len(self.rolls),
            'favorite_dice': self.get_favorite_dice(),
            'lucky_number': self.get_lucky_number(),
            'avg_roll': self.get_average_roll()
        }
    
    def get_favorite_dice(self):
        """Meist verwendeten Würfel ermitteln"""
        if not self.rolls:
            return 'D6'
        
        dice_counts = {}
        for roll in self.rolls:
            dice_type = f"D{roll.dice_sides}"
            dice_counts[dice_type] = dice_counts.get(dice_type, 0) + 1
        
        return max(dice_counts.items(), key=lambda x: x[1])[0] if dice_counts else 'D6'
    
    def get_lucky_number(self):
        """Häufigstes Würfelergebnis"""
        if not self.rolls:
            return 6
        
        results = {}
        for roll in self.rolls:
            for result in roll.results:
                results[result] = results.get(result, 0) + 1
        
        return max(results.items(), key=lambda x: x[1])[0] if results else 6
    
    def get_average_roll(self):
        """Durchschnittliches Würfelergebnis"""
        if not self.rolls:
            return 0
        
        total = sum(sum(roll.results) for roll in self.rolls)
        count = sum(len(roll.results) for roll in self.rolls)
        return round(total / count, 2) if count > 0 else 0

class DiceRoll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Nullable für Gäste
    guest_session = db.Column(db.String(100), nullable=True)  # Für Gast-Sessions
    dice_sides = db.Column(db.Integer, nullable=False)
    dice_count = db.Column(db.Integer, default=1)
    results = db.Column(db.JSON, nullable=False)  # Liste der Würfelergebnisse
    total = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<DiceRoll {self.dice_count}x D{self.dice_sides}: {self.results}>'

class GuestSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), unique=True, nullable=False)
    roll_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    
    @staticmethod
    def create_guest_session():
        """Neue Gast-Session erstellen"""
        session_id = secrets.token_urlsafe(16)
        guest_session = GuestSession(session_id=session_id)
        db.session.add(guest_session)
        db.session.commit()
        return session_id
    
    @staticmethod
    def get_or_create_guest_session(session_id):
        """Gast-Session abrufen oder erstellen"""
        if not session_id:
            return GuestSession.create_guest_session()
        
        guest_session = GuestSession.query.filter_by(session_id=session_id).first()
        if not guest_session:
            return GuestSession.create_guest_session()
        
        # Letzte Aktivität aktualisieren
        guest_session.last_activity = datetime.utcnow()
        db.session.commit()
        return session_id

def init_db(app):
    """Datenbank initialisieren"""
    db.init_app(app)
    with app.app_context():
        db.create_all()
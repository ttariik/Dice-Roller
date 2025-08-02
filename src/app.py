from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_login import LoginManager, login_required, current_user
from models import db, init_db, User, DiceRoll, GuestSession
from auth import auth_bp
import random
import secrets
import os
from datetime import datetime

app = Flask(__name__)

# Konfiguration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(16))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dice_roller.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Bitte melde dich an, um diese Seite zu besuchen.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Blueprints registrieren
app.register_blueprint(auth_bp, url_prefix='/auth')

# Datenbank initialisieren
init_db(app)

@app.route("/")
def home() -> str:
    """Hauptseite der Anwendung"""
    return render_template("home.html")

@app.route("/dice-roller")
def dice_roller() -> str:
    """Dice-Roller Seite"""
    return render_template("dice_roller.html")

@app.route("/about")
def about() -> str:
    """Über uns Seite"""
    return render_template("about.html")

@app.route("/dashboard")
@login_required
def dashboard() -> str:
    """Benutzer-Dashboard"""
    user_stats = current_user.get_stats()
    recent_rolls = DiceRoll.query.filter_by(user_id=current_user.id)\
                                .order_by(DiceRoll.timestamp.desc())\
                                .limit(20).all()
    
    return render_template("dashboard.html", 
                         user_stats=user_stats, 
                         recent_rolls=recent_rolls)

@app.route("/leaderboard")
def leaderboard() -> str:
    """Leaderboard Seite"""
    return render_template("leaderboard.html")

@app.route("/tournaments")
def tournaments() -> str:
    """Turniere Seite"""
    return render_template("tournament.html")

@app.route("/share/<int:roll_id>")
def share_roll(roll_id: int) -> str:
    """Geteilten Würfelwurf anzeigen"""
    roll = DiceRoll.query.get_or_404(roll_id)
    return render_template("share_roll.html", roll=roll)

@app.route("/api/share-roll", methods=['POST'])
def api_share_roll():
    """API zum Teilen eines Würfelwurfs"""
    data = request.get_json()
    
    # Temporäres Sharing ohne Authentifizierung
    share_data = {
        'id': 'temp_' + secrets.token_urlsafe(8),
        'dice_sides': data.get('dice_sides'),
        'dice_count': data.get('dice_count'),
        'results': data.get('results'),
        'total': data.get('total'),
        'timestamp': datetime.now().isoformat(),
        'share_url': f"/share/temp_{secrets.token_urlsafe(8)}"
    }
    
    return jsonify(share_data)

@app.route("/api/roll", methods=['POST'])
def api_roll():
    """API-Endpunkt für Würfelwürfe"""
    data = request.get_json()
    
    dice_sides = data.get('sides', 6)
    dice_count = data.get('count', 1)
    
    # Validierung
    if dice_sides not in [4, 6, 8, 10, 12, 20]:
        return jsonify({'error': 'Ungültige Würfelseiten'}), 400
    
    if dice_count < 1 or dice_count > 10:
        return jsonify({'error': 'Ungültige Würfelanzahl (1-10)'}), 400
    
    # Für Gäste: Limit prüfen
    if not current_user.is_authenticated:
        guest_session_id = session.get('guest_session_id')
        if not guest_session_id:
            guest_session_id = GuestSession.create_guest_session()
            session['guest_session_id'] = guest_session_id
        
        guest_session = GuestSession.query.filter_by(session_id=guest_session_id).first()
        if guest_session and guest_session.roll_count >= 10:
            return jsonify({
                'error': 'Gast-Limit erreicht',
                'limit_reached': True,
                'message': 'Du hast dein Limit von 10 kostenlosen Würfen erreicht. Registriere dich für unbegrenzte Würfe!'
            }), 403
    
    # Würfeln
    results = [random.randint(1, dice_sides) for _ in range(dice_count)]
    total = sum(results)
    
    # Würfel in Datenbank speichern
    dice_roll = DiceRoll(
        user_id=current_user.id if current_user.is_authenticated else None,
        guest_session=session.get('guest_session_id') if not current_user.is_authenticated else None,
        dice_sides=dice_sides,
        dice_count=dice_count,
        results=results,
        total=total
    )
    
    db.session.add(dice_roll)
    
    # Zähler für Gäste erhöhen
    if not current_user.is_authenticated:
        guest_session = GuestSession.query.filter_by(session_id=session.get('guest_session_id')).first()
        if guest_session:
            guest_session.roll_count += 1
            guest_session.last_activity = datetime.utcnow()
    
    db.session.commit()
    
    # Antwort
    response_data = {
        'results': results,
        'total': total,
        'dice_sides': dice_sides,
        'dice_count': dice_count,
        'timestamp': dice_roll.timestamp.isoformat()
    }
    
    # Für Gäste: verbleibende Würfe hinzufügen
    if not current_user.is_authenticated:
        guest_session = GuestSession.query.filter_by(session_id=session.get('guest_session_id')).first()
        rolls_left = max(0, 10 - guest_session.roll_count) if guest_session else 10
        response_data['guest_info'] = {
            'is_guest': True,
            'rolls_left': rolls_left,
            'limit_reached': rolls_left <= 0
        }
    
    return jsonify(response_data)

@app.route("/api/history")
def api_history():
    """API-Endpunkt für Würfel-Historie"""
    if current_user.is_authenticated:
        rolls = DiceRoll.query.filter_by(user_id=current_user.id)\
                            .order_by(DiceRoll.timestamp.desc())\
                            .limit(50).all()
    else:
        guest_session_id = session.get('guest_session_id')
        if not guest_session_id:
            return jsonify([])
        
        rolls = DiceRoll.query.filter_by(guest_session=guest_session_id)\
                            .order_by(DiceRoll.timestamp.desc())\
                            .limit(20).all()
    
    history_data = []
    for roll in rolls:
        history_data.append({
            'id': roll.id,
            'dice_sides': roll.dice_sides,
            'dice_count': roll.dice_count,
            'results': roll.results,
            'total': roll.total,
            'timestamp': roll.timestamp.isoformat()
        })
    
    return jsonify(history_data)

# Legacy route für Rückwärtskompatibilität
@app.route("/dices")
def show_dices() -> str:
    """Legacy Route - weiterleitung zum neuen Dice-Roller"""
    return render_template("dice_roller.html")

@app.route("/<string:name>")
def hello_world(name: str) -> str:
    """Personalisierte Begrüßung - jetzt auf der Index-Seite"""
    return render_template("index.html", _name=name)

if __name__ == "__main__":
    app.run(debug=True, port=5001)

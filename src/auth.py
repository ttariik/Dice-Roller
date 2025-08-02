from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from models import db, User, GuestSession
import re
import secrets
from datetime import datetime
from authlib.integrations.flask_client import OAuth

auth_bp = Blueprint('auth', __name__)

def is_valid_email(email):
    """Email-Validierung"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def is_valid_phone(phone):
    """Telefonnummer-Validierung (einfach)"""
    pattern = r'^[\+]?[1-9][\d]{0,15}$'
    return re.match(pattern, phone.replace(' ', '').replace('-', '')) is not None

@auth_bp.route('/register')
def register():
    """Registrierungsseite"""
    return render_template('auth/register.html')

@auth_bp.route('/register', methods=['POST'])
def register_post():
    """Registrierung verarbeiten"""
    data = request.get_json()
    
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    # Validierung
    errors = []
    
    if not email or not is_valid_email(email):
        errors.append('Gültige E-Mail-Adresse erforderlich')
    
    if not username or len(username) < 3:
        errors.append('Benutzername muss mindestens 3 Zeichen lang sein')
    
    if not password or len(password) < 6:
        errors.append('Passwort muss mindestens 6 Zeichen lang sein')
    
    if phone and not is_valid_phone(phone):
        errors.append('Ungültige Telefonnummer')
    
    # Prüfen ob Email/Username bereits existiert
    if User.query.filter_by(email=email).first():
        errors.append('E-Mail-Adresse bereits registriert')
    
    if User.query.filter_by(username=username).first():
        errors.append('Benutzername bereits vergeben')
    
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400
    
    # Benutzer erstellen
    user = User(
        email=email,
        phone=phone if phone else None,
        username=username
    )
    user.set_password(password)
    
    db.session.add(user)
    db.session.commit()
    
    # Automatisch einloggen
    login_user(user)
    
    return jsonify({'success': True, 'redirect': url_for('dice_roller')})

@auth_bp.route('/login')
def login():
    """Login-Seite"""
    return render_template('auth/login.html')

@auth_bp.route('/login', methods=['POST'])
def login_post():
    """Login verarbeiten"""
    data = request.get_json()
    
    email_or_username = data.get('email_or_username', '').strip()
    password = data.get('password', '')
    
    if not email_or_username or not password:
        return jsonify({'success': False, 'error': 'E-Mail/Benutzername und Passwort erforderlich'}), 400
    
    # Benutzer finden (Email oder Username)
    user = User.query.filter(
        (User.email == email_or_username) | (User.username == email_or_username)
    ).first()
    
    if not user or not user.check_password(password):
        return jsonify({'success': False, 'error': 'Ungültige Anmeldedaten'}), 400
    
    login_user(user, remember=data.get('remember', False))
    
    return jsonify({'success': True, 'redirect': url_for('dice_roller')})

@auth_bp.route('/logout')
@login_required
def logout():
    """Benutzer ausloggen"""
    logout_user()
    return redirect(url_for('home'))

@auth_bp.route('/google')
def google_auth():
    """Google OAuth initialisieren"""
    # TODO: Google OAuth implementieren
    flash('Google-Anmeldung wird bald verfügbar sein!', 'info')
    return redirect(url_for('auth.register'))

@auth_bp.route('/check-guest-limit')
def check_guest_limit():
    """Prüfen ob Gast-Limit erreicht wurde"""
    if current_user.is_authenticated:
        return jsonify({'is_guest': False, 'rolls_left': -1})
    
    guest_session_id = session.get('guest_session_id')
    if not guest_session_id:
        # Neue Gast-Session erstellen
        guest_session_id = GuestSession.create_guest_session()
        session['guest_session_id'] = guest_session_id
        return jsonify({'is_guest': True, 'rolls_left': 10})
    
    guest_session = GuestSession.query.filter_by(session_id=guest_session_id).first()
    if not guest_session:
        # Session nicht gefunden, neue erstellen
        guest_session_id = GuestSession.create_guest_session()
        session['guest_session_id'] = guest_session_id
        return jsonify({'is_guest': True, 'rolls_left': 10})
    
    rolls_left = max(0, 10 - guest_session.roll_count)
    
    return jsonify({
        'is_guest': True, 
        'rolls_left': rolls_left,
        'limit_reached': rolls_left <= 0
    })

@auth_bp.route('/increment-guest-roll', methods=['POST'])
def increment_guest_roll():
    """Gast-Würfe zählen"""
    if current_user.is_authenticated:
        return jsonify({'success': True})
    
    guest_session_id = session.get('guest_session_id')
    if not guest_session_id:
        return jsonify({'success': False, 'error': 'Keine Gast-Session'})
    
    guest_session = GuestSession.query.filter_by(session_id=guest_session_id).first()
    if guest_session:
        guest_session.roll_count += 1
        guest_session.last_activity = datetime.utcnow()
        db.session.commit()
    
    return jsonify({'success': True})
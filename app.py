from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_mysqldb import MySQL
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from openai import OpenAI, RateLimitError
from dotenv import load_dotenv
import os
import time
from functools import lru_cache


# --- Flask Setup ---
app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# --- Load environment variables ---
load_dotenv()

# --- MySQL Configuration ---
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''  # Update if needed
app.config['MYSQL_DB'] = 'campus_chronicles'
mysql = MySQL(app)

# --- OpenAI Setup ---
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Security: Limit Upload Size ---
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1 MB limit


# ============================
# 🔒 SESSION & CACHE HANDLING
# ============================


@app.after_request
def clear_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response



# ============================
# 🧠 AI MODERATION FUNCTION
# ============================


# Cache moderation results to avoid repeated API calls
moderation_cache = {}

def basic_safety_check(message):
    """Fallback safety filter in case moderation API fails"""
    banned = [
        # --- Violence / threats ---
        "kill", "murder", "bomb", "shoot", "stab", "hang", "terror", "attack",
        "destroy", "suicide", "die", "death", "hurt", "fight", "explode",

        # --- Hate / harassment ---
        "hate", "racist", "slur", "nazi", "slave", "stupid", "idiot",
        "fool", "retard", "bitch", "bastard", "ugly", "pig", "moron",

        # --- Drugs / illegal activity ---
        "cocaine", "heroin", "weed", "marijuana", "meth", "drug", "smuggle",
        "gun", "weapon", "knife", "shooting",

        # --- Extremism / criminal ---
        "isis", "terrorist", "extremist", "kill all", "massacre", "war",

        # --- Self-harm / depression ---
        "i want to die", "kill myself", "no reason to live", "cut myself"
    ]
    return not any(word in message.lower() for word in banned)
@lru_cache(maxsize=5000)
def check_message_safe(message):
    """
    Real-time AI moderation with caching and rate limit handling.
    Returns True if safe, False if unsafe.
    """
    try:
        response = client.moderations.create(
            model="omni-moderation-latest",
            input=message
        )
        return not response.results[0].flagged

    except RateLimitError:
        print("⚠️ Rate limit reached. Using local fallback.")
        return basic_safety_check(message)
    except Exception as e:
        print("Moderation failed:", e)
        return basic_safety_check(message)


# ============================
# 🏠 ROUTES
# ============================

@app.route('/')
def home():
    return render_template('home.html')


# ----------------------------
# 🧍 LOGIN ROUTE
# ----------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash("⚠️ Username and password are required.")
            return redirect(url_for('login'))

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cur.fetchone()
        cur.close()

        if not user:
            flash("❌ User not found. Please register first.")
            return redirect(url_for('register'))

        # Assuming columns: id(0), username(1), email(2), password(3)
        stored_password = user[3]

        if check_password_hash(stored_password, password):
            session['user'] = username
            flash("✅ Login successful!")
            return redirect(url_for('index'))
        else:
            flash("❌ Incorrect password. Try again.")
            return redirect(url_for('login'))

    return render_template('login.html')


# # ----------------------------
# # 📝 REGISTER ROUTE
# # ----------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm = request.form['confirm_password']

        if password != confirm:
            flash("❌ Passwords do not match!")
            return redirect(url_for('register'))

        # Check if username or email already exists
        cur.execute("SELECT * FROM users WHERE username=%s OR email=%s", (username, email))
        existing = cur.fetchone()
        if existing:
            flash("⚠️ Username or email already exists!")
            return redirect(url_for('register'))

        # ✅ Hash the password before storing
        hashed_password = generate_password_hash(password)

        cur.execute(
            "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
            (username, email, hashed_password)
        )
        mysql.connection.commit()
        cur.close()

        flash("✅ Registration successful! Please log in.")
        return redirect(url_for('login'))

    return render_template('register.html')





# ----------------------------
# 🧭 INDEX (Main Page)
# ----------------------------
@app.route('/index')
def index():
    if 'user' not in session:
        flash("Please log in first.")
        return redirect(url_for('login'))
    return render_template('index.html', username=session['user'])


# ----------------------------
# 🚪 LOGOUT ROUTE
# ----------------------------
@app.route('/logout')
def logout():
    session.clear()
    flash("✅ You have been logged out successfully.")
    response = redirect(url_for('home'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.set_cookie('session', '', expires=0)
    return response


# ============================
# 📰 POSTS API
# ============================



@app.route('/api/posts', methods=['GET'])
def get_posts():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT p.id, p.title, p.message, p.category, p.likes, p.created_at
        FROM posts p ORDER BY p.created_at DESC LIMIT 100
    """)
    posts = cur.fetchall()

    post_list = []
    for p in posts:
        cur.execute("SELECT text FROM comments WHERE post_id=%s", (p[0],))
        comments = [{'text': c[0]} for c in cur.fetchall()]
        post_list.append({
            'id': p[0],
            'title': p[1],
            'message': p[2],
            'category': p[3],
            'likes': p[4],
            'created_at': p[5].strftime("%Y-%m-%d %H:%M:%S"),
            'comments': comments
        })
    cur.close()
    return jsonify({'posts': post_list})


# --- Create Post (AI moderation enabled)

@app.route('/api/posts', methods=['POST'])
def create_post():
    """Handles new post creation with AI moderation"""
    data = request.get_json()
    category = data.get('category')
    title = data.get('title')
    message = data.get('message')

    if not message:
        return jsonify({'error': 'Message cannot be empty'}), 400

    # AI moderation check
    if not check_message_safe(message):
        return jsonify({'error': 'Message contains inappropriate or unsafe content'}), 400

    # Save to MySQL
    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO posts (category, title, message, likes, created_at) VALUES (%s, %s, %s, 0, NOW())",
        (category, title, message)
    )
    mysql.connection.commit()
    cur.close()

    return jsonify({'success': True, 'message': 'Post created successfully'}), 201



@app.route('/add_post', methods=['POST'])
def add_post():
    data = request.get_json()
    category = data.get('category')
    title = data.get('title')
    message = data.get('message')

    # ✅ AI moderation check
    if not check_message_safe(message):
        return jsonify({'error': 'Message contains inappropriate or unsafe content'}), 400

    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO posts (category, title, message, likes, created_at) VALUES (%s, %s, %s, 0, NOW())",
        (category, title, message)
    )
    mysql.connection.commit()
    cur.close()
    return jsonify({'success': True}), 201


# --- Like a post
@app.route('/api/posts/<int:post_id>/like', methods=['POST'])
def like_post(post_id):
    if 'user' not in session:
        return jsonify({'error': 'Please log in to like posts'}), 401

    username = session['user']
    cur = mysql.connection.cursor()

    # 🧩 Check if the user already liked this post
    cur.execute("SELECT * FROM likes WHERE user=%s AND post_id=%s", (username, post_id))
    already_liked = cur.fetchone()

    if already_liked:
        cur.close()
        return jsonify({'error': 'You have already liked this post'}), 400

    try:
        # ✅ Add like record
        cur.execute("INSERT INTO likes (user, post_id) VALUES (%s, %s)", (username, post_id))

        # ✅ Update like count in posts table
        cur.execute("UPDATE posts SET likes = likes + 1 WHERE id = %s", (post_id,))
        mysql.connection.commit()

        # ✅ Fetch updated like count
        cur.execute("SELECT likes FROM posts WHERE id = %s", (post_id,))
        likes = cur.fetchone()[0]
        cur.close()

        return jsonify({'likes': likes, 'message': 'Post liked successfully'}), 200

    except Exception as e:
        print("Like error:", e)
        mysql.connection.rollback()
        cur.close()
        return jsonify({'error': 'Failed to like post'}), 500




@app.route('/api/posts/<int:post_id>/comment', methods=['POST'])
def add_comment(post_id):
    if 'user' not in session:
        return jsonify({'error': 'Please log in to comment'}), 401

    data = request.get_json()
    text = data.get('text')
    username = session['user']

    if not text:
        return jsonify({'error': 'Empty comment'}), 400

    # ✅ AI moderation
    if not check_message_safe(text):
        return jsonify({'error': 'Comment contains inappropriate or unsafe content'}), 400

    try:
        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO comments (post_id, username, text) VALUES (%s, %s, %s)",
            (post_id, username, text)
        )
        mysql.connection.commit()
        cur.close()
        return jsonify({'text': text, 'username': username}), 201

    except Exception as e:
        print("Comment error:", e)
        mysql.connection.rollback()
        cur.close()
        return jsonify({'error': 'Failed to add comment'}), 500




# --- Stats API
@app.route('/api/stats', methods=['GET'])
def get_stats():
    cur = mysql.connection.cursor()
    week_ago = datetime.now() - timedelta(days=7)
    cur.execute("SELECT COUNT(*) FROM posts WHERE created_at >= %s", (week_ago,))
    posts_this_week = cur.fetchone()[0]

    cur.execute("SELECT SUM(likes) FROM posts")
    total_likes = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM comments")
    total_comments = cur.fetchone()[0]

    cur.close()
    return jsonify({
        'posts_this_week': posts_this_week,
        'total_likes': total_likes,
        'total_comments': total_comments
    })


# --- Trending categories
@app.route('/api/trending', methods=['GET'])
def get_trending():
    cur = mysql.connection.cursor()
    cur.execute("SELECT category, COUNT(*) FROM posts GROUP BY category ORDER BY COUNT(*) DESC LIMIT 5")
    cats = [{'category': c[0], 'count': c[1]} for c in cur.fetchall()]

    cur.execute("SELECT title, message FROM posts ORDER BY likes DESC LIMIT 3")
    top_posts = [{'title': t[0], 'message': t[1]} for t in cur.fetchall()]
    cur.close()

    return jsonify({'categories': cats, 'top_posts': top_posts})


# ============================
# 🚀 RUN SERVER
# ============================
if __name__ == '__main__':
    app.run(debug=True)


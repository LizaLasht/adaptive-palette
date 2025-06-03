from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
import os, random
from werkzeug.utils import secure_filename
import numpy as np
import cv2
from sklearn.linear_model import LogisticRegression
from sklearn.cluster import KMeans

app = Flask(__name__)
os.makedirs('instance', exist_ok=True)

absolute_db_path = os.path.abspath("instance/palettes.db")
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{absolute_db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)

# Глобальная модель и данные
model = None
X_data = []
y_data = []

# Модель палитры
class Palette(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    color1 = db.Column(db.String(7))
    color2 = db.Column(db.String(7))
    color3 = db.Column(db.String(7))
    color4 = db.Column(db.String(7))
    color5 = db.Column(db.String(7))
    method = db.Column(db.String(10))
    image_path = db.Column(db.String(100), nullable=True)
    likes = db.Column(db.Integer, default=0)
    dislikes = db.Column(db.Integer, default=0)

# Модель обратной связи

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    palette_id = db.Column(db.Integer, db.ForeignKey('palette.id'))
    liked = db.Column(db.Integer)  # 1 – лайк, 0 – дизлайк
    features = db.Column(db.PickleType)  # сохраняем признаки для отладки

# Генерация случайной палитры
def generate_random_palette(n=5):
    return ['#{:02X}{:02X}{:02X}'.format(random.randint(0,255), random.randint(0,255), random.randint(0,255)) for _ in range(n)]

# Преобразование палитры в признаки (нормализованные)
def palette_to_features(colors):
    features = []
    for hex_color in colors:
        r = int(hex_color[1:3], 16) / 255
        g = int(hex_color[3:5], 16) / 255
        b = int(hex_color[5:7], 16) / 255
        features.extend([r, g, b])
    return features

# Обновление модели
def update_model():
    global model, X_data, y_data
    feedbacks = Feedback.query.all()
    X_data = [f.features for f in feedbacks]
    y_data = [f.liked for f in feedbacks]
    if len(set(y_data)) >= 2:
        model = LogisticRegression()
        model.fit(X_data, y_data)
        print("✅ Модель обучена")
    else:
        model = None
        print("⚠️ Недостаточно данных для обучения модели.")

# Палитра из изображения
def extract_palette_from_image(image_path, n_colors=5):
    img = cv2.imread(image_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (100, 100))
    pixels = img.reshape(-1, 3)
    kmeans = KMeans(n_clusters=n_colors, random_state=42, n_init='auto')
    kmeans.fit(pixels)
    colors = kmeans.cluster_centers_.astype(int)
    return ['#{:02X}{:02X}{:02X}'.format(*c) for c in colors]

@app.route("/")
def index():
    palette = generate_random_palette()
    pal = Palette(color1=palette[0], color2=palette[1], color3=palette[2],
                  color4=palette[3], color5=palette[4], method='random')
    db.session.add(pal)
    db.session.commit()
    return render_template("index.html", initial_palette=palette, initial_id=pal.id)

@app.route("/generate")
def api_generate():
    best_palette = None
    best_proba = None

    enough_feedback = len(X_data) >= 15

    for _ in range(15):
        palette = generate_random_palette()
        if model and enough_feedback:
            features = np.array([palette_to_features(palette)])
            proba = model.predict_proba(features)[0][1]
            if best_proba is None or proba > best_proba:
                best_proba = proba
                best_palette = palette
        else:
            best_palette = palette
            break

    pal = Palette(color1=best_palette[0], color2=best_palette[1], color3=best_palette[2],
                  color4=best_palette[3], color5=best_palette[4], method='random')
    db.session.add(pal)
    db.session.commit()

    return jsonify({
        "palette_id": pal.id,
        "colors": best_palette,
        "proba": best_proba if enough_feedback else None
    })

@app.route("/feedback", methods=["POST"])
def feedback():
    data = request.json
    palette_id = data.get("palette_id")
    feedback_type = data.get("feedback")
    palette = db.session.get(Palette, palette_id)
    if not palette:
        return jsonify({"error": "Palette not found"}), 404

    liked = 1 if feedback_type == "like" else 0
    features = palette_to_features([palette.color1, palette.color2, palette.color3, palette.color4, palette.color5])

    if liked:
        palette.likes += 1
    else:
        palette.dislikes += 1

    db.session.add(Feedback(palette_id=palette.id, liked=liked, features=features))
    db.session.commit()
    update_model()
    return jsonify({"message": "Feedback received"})

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("image")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    try:
        palette = extract_palette_from_image(filepath)
        pal = Palette(
            color1=palette[0], color2=palette[1], color3=palette[2],
            color4=palette[3], color5=palette[4],
            method='image', image_path=filename
        )
        db.session.add(pal)
        db.session.commit()

        proba = None
        if model and len(X_data) >= 15:
            features = np.array([palette_to_features(palette)])
            proba = model.predict_proba(features)[0][1]
        else:
            proba = "need_feedback"

        return jsonify({
            "palette_id": pal.id,
            "colors": palette,
            "image": f"/uploads/{filename}",
            "proba": proba
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/uploads/<filename>")
def serve_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/liked_palettes")
def liked_palettes():
    liked_ids = [f.palette_id for f in Feedback.query.filter_by(liked=1).all()]
    palettes = Palette.query.filter(Palette.id.in_(liked_ids)).all()
    result = [{
        "id": p.id,
        "colors": [p.color1, p.color2, p.color3, p.color4, p.color5],
        "likes": p.likes,
        "dislikes": p.dislikes,
        "image": f"/uploads/{p.image_path}" if p.image_path else None
    } for p in palettes]
    return jsonify(result)

if __name__ == "__main__":
    db_path = os.path.abspath("instance/palettes.db")
    if os.path.exists(db_path):
        os.remove(db_path)
        print("🗑️ База удалена")

    # Очистка папки uploads
    for filename in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                print(f"🧹 Удален файл: {file_path}")
        except Exception as e:
            print(f"❌ Ошибка при удалении {file_path}: {e}")

    with app.app_context():
        db.create_all()
        update_model()
        print("✅ База данных заново создана и модель обновлена")

    app.run(debug=True, use_reloader=False)









    
from flask import Flask, request, render_template, jsonify
from PIL import Image, ExifTags
import piexif
import os

app = Flask(__name__)

# Папка для сохранения обработанных фотографий
SAVE_FOLDER = "/storage/emulated/0/ExifCopy"
if not os.path.exists(SAVE_FOLDER):
    os.makedirs(SAVE_FOLDER)

def get_orientation(exif):
    """Получить ориентацию изображения из EXIF-данных."""
    for orientation in ExifTags.TAGS.keys():
        if ExifTags.TAGS[orientation] == "Orientation":
            return exif.get(orientation)
    return None

def adjust_orientation(image, orientation):
    """Подстроить ориентацию изображения."""
    if orientation == 3:  # 180 градусов
        return image.rotate(180, expand=True)
    elif orientation == 6:  # 90 градусов по часовой
        return image.rotate(270, expand=True)
    elif orientation == 8:  # 90 градусов против часовой
        return image.rotate(90, expand=True)
    return image

def crop_to_aspect(target_img, src_size):
    """Обрезать изображение под размеры исходного."""
    target_width, target_height = target_img.size
    src_width, src_height = src_size

    # Рассчитать соотношение сторон
    src_aspect = src_width / src_height
    tgt_aspect = target_width / target_height

    if tgt_aspect > src_aspect:  # Если целевое изображение шире
        new_width = int(target_height * src_aspect)
        offset = (target_width - new_width) // 2
        return target_img.crop((offset, 0, offset + new_width, target_height))
    else:  # Если целевое изображение выше
        new_height = int(target_width / src_aspect)
        offset = (target_height - new_height) // 2
        return target_img.crop((0, offset, target_width, offset + new_height))

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Проверяем наличие файлов
        if "source" not in request.files or "target" not in request.files:
            return jsonify({"error": "Не выбраны файлы для загрузки"}), 400

        # Получаем файлы
        source_files = request.files.getlist("source")
        target_files = request.files.getlist("target")

        if len(source_files) != len(target_files):
            return jsonify({"error": "Количество исходных и целевых файлов должно совпадать"}), 400

        processed_files = []
        for source_file, target_file in zip(source_files, target_files):
            try:
                with Image.open(source_file) as src_img:
                    exif_data = piexif.load(src_img.info.get("exif", b""))

                    with Image.open(target_file) as tgt_img:
                        # Настройка ориентации
                        tgt_img = adjust_orientation(tgt_img, get_orientation(src_img._getexif()))
                        # Обрезка под размеры исходного
                        tgt_img = crop_to_aspect(tgt_img, src_img.size)

                        # Сохраняем нижнее фото с данными верхнего
                        result_filename = source_file.filename
                        result_path = os.path.join(SAVE_FOLDER, result_filename)

                        if os.path.exists(result_path):
                            os.remove(result_path)  # Удаляем старую версию файла

                        exif_bytes = piexif.dump(exif_data)
                        tgt_img.save(result_path, exif=exif_bytes, quality=95)
                        processed_files.append(result_path)
            except Exception as e:
                print(f"Ошибка обработки файлов {source_file.filename} и {target_file.filename}: {e}")
                continue

        return jsonify({
            "message": "Успешно",
            "path": SAVE_FOLDER,
            "processed_files": [os.path.basename(f) for f in processed_files],
        })

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
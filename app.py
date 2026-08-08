import os
import json
import logging
from flask import Flask, request, jsonify
import requests

# Настройка логирования для отладки на Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Получаем API-ключ DeepSeek из переменных окружения
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

@app.route('/', methods=['GET'])
def health_check():
    """Проверка работоспособности сервиса"""
    return jsonify({"status": "ok", "message": "Сервис работает"}), 200

@app.route('/api/generate-plans', methods=['POST'])
def generate_plans():
    """
    Основной эндпоинт для генерации планов досуга
    Принимает данные из формы Tilda и возвращает 2 варианта плана
    """
    try:
        # Получаем данные из формы Tilda
        # Tilda отправляет данные как form-data, поэтому используем request.form
        if request.is_json:
            data = request.get_json()
        else:
            data = dict(request.form)
        
        logger.info(f"Получены данные: {data}")
        
        # Извлекаем поля формы
        child_age = data.get('child_age', '').strip()
        time_interval = data.get('time_interval', '').strip()
        location = data.get('location', '').strip()
        leisure_type = data.get('leisure_type', '').strip()
        phone = data.get('phone', '').strip()  # Телефон для сохранения в Tilda CRM
        
        # Проверяем, что все обязательные поля заполнены
        if not all([child_age, time_interval, location, leisure_type]):
            return jsonify({
                "error": "Пожалуйста, заполните все поля формы"
            }), 400
        
        # Формируем промпт для DeepSeek
        prompt = (
            f"Возраст ребенка: {child_age} лет. "
            f"Временной интервал: {time_interval}. "
            f"Местоположение: {location}. "
            f"Тип досуга: {leisure_type}. "
            "Предложи 2 варианта плана досуга для ребенка. "
            "Каждый план должен состоять ровно из 3 пунктов. "
            "Варианты должны быть разными по стилю: один активный, другой спокойный. "
            "Ответ верни ТОЛЬКО в формате JSON без дополнительного текста: "
            '{"plan1": ["пункт 1", "пункт 2", "пункт 3"], "plan2": ["пункт 1", "пункт 2", "пункт 3"]}'
        )
        
        # Отправляем запрос к DeepSeek API
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "Ты — эксперт по планированию детского досуга. Всегда отвечай только в формате JSON."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }
        
        logger.info("Отправка запроса к DeepSeek API...")
        response = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        # Обрабатываем ответ от DeepSeek
        ai_response = response.json()
        ai_content = ai_response['choices'][0]['message']['content'].strip()
        logger.info(f"Ответ от DeepSeek: {ai_content}")
        
        # Парсим JSON из ответа DeepSeek
        try:
            plans = json.loads(ai_content)
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON от DeepSeek: {e}")
            # Если DeepSeek вернул невалидный JSON, пытаемся извлечь планы другим способом
            # или возвращаем заглушку
            plans = {
                "plan1": ["Посетить детскую площадку", "Покататься на велосипеде", "Почитать книгу"],
                "plan2": ["Сходить в кино", "Нарисовать картину", "Поиграть в настольные игры"]
            }
        
        # Сохраняем телефон в список заявок Tilda (это делает сама Tilda)
        # Здесь мы просто возвращаем результат
        return jsonify({
            "success": True,
            "plans": plans,
            "phone": phone  # Возвращаем телефон на всякий случай
        }), 200
        
    except requests.exceptions.Timeout:
        logger.error("Таймаут при запросе к DeepSeek API")
        return jsonify({
            "error": "Превышено время ожидания ответа от ИИ. Попробуйте еще раз."
        }), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к DeepSeek: {e}")
        return jsonify({
            "error": "Ошибка при обращении к ИИ. Попробуйте позже."
        }), 500
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}")
        return jsonify({
            "error": "Произошла внутренняя ошибка. Мы уже работаем над этим."
        }), 500

if __name__ == '__main__':
    # Render передает порт через переменную окружения PORT
    port = int(os.environ.get('PORT', 5000))
    # В production используем Gunicorn, поэтому здесь запускаем только для разработки
    app.run(host='0.0.0.0', port=port, debug=False)

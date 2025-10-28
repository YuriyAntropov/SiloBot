# SiloBot — AI Phone Assistant

Телефонный бот для SiloService AB. Принимает звонки через Twilio, распознаёт речь (Google STT), понимает намерения (Dialogflow), сохраняет лиды в Firestore и отправляет SMS менеджеру.

## Функции
- Приём входящих звонков
- Запись голоса
- Распознавание речи (шведский)
- Извлечение: имя, регион, проблема, номер телефона
- Сохранение в Firestore
- Отправка SMS через Twilio

## Технологии
- Google Cloud Functions
- Twilio
- Dialogflow CX
- Firebase Firestore
- Google Speech-to-Text
- Google Text-to-Speech

## Деплой
```bash
firebase deploy --only functions

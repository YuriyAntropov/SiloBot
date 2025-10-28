from firebase_functions import https_fn
from firebase_admin import initialize_app, firestore, storage, credentials
from google.cloud import texttospeech
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from twilio.twiml.voice_response import VoiceResponse, Gather
from google.cloud import dialogflow
from flask import Response
from twilio.rest import Client
from google.cloud import speech_v1p1beta1 as speech
import os
import requests
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_TOKEN")
DIALOGFLOW_PROJECT_ID = "silobot-468218"
TWILIO_PHONE_NUMBER = "+16606535902"
MANAGER_PHONE_NUMBER = "+46704325707"
SERVICE_ACCOUNT_PATH = os.getenv("SERVICE_ACCOUNT_PATH", "silobot-468218-4f925fc0b4ba.json")

HINTS = [
    "namn", "region", "problem", "silo", "reparation",
    "Stockholm", "Göteborg", "Malmö", "Skåne", "Uppsala", "Sweden",
    "Anna", "Anne", "Erik", "Lars", "Sofia", "Johan",
    "rost", "målning", "smutsig", "skador", "reparera", "måla", "silon", "behövs",
    "från", "jag heter", "mitt namn är", "behöver",
    "silo behöver reparation", "silo har skador", "målning av silo", "rost på silo", "smutsig silo",
    "Anna från Stockholm", "Lars från Göteborg", "Johan från Uppsala",
    "jag heter Lars från Göteborg silo behöver reparation",
    "mitt namn är Anna från Stockholm silo har skador", "mitt namn är Erik jag bor i Göteborg", "problem med målning silo",
    "mitt namn är Erik jag bor i Göteborg", "problem med målning silo",
    "hej mitt namn är Lars jag ringa fron Göteborg och jag har en problemen målning silo",
    "silo behövs för reparation", "kontaktera med", "Malmö", "eller?", "eller så?", "är det rätt?", "jag undrar", "kanske"
]

logging.info("Инициализация Firebase credentials")
cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
initialize_app(cred)
db = firestore.client()
logging.info("Firestore клиент инициализирован успешно")

bucket = storage.bucket("silobot-468218.firebasestorage.app")
logging.info("Storage bucket инициализирован успешно")

logging.info("Инициализация Dialogflow и Text-to-Speech credentials")
dialogflow_credentials = Credentials.from_service_account_file(
    SERVICE_ACCOUNT_PATH,
    scopes=[
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/dialogflow"
    ]
)
logging.info("Dialogflow и Text-to-Speech credentials инициализированы успешно")

tts_client = texttospeech.TextToSpeechClient(credentials=dialogflow_credentials)
logging.info("Text-to-Speech клиент инициализирован успешно")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
logging.info("Twilio клиент для SMS инициализирован успешно")

@https_fn.on_request()
def twilliowebhook(req: https_fn.Request) -> https_fn.Response:
    logging.info("twilliowebhook: Запрос получен")
    logging.info(f"twilliowebhook: Заголовки запроса: {dict(req.headers)}")
    logging.info(f"twilliowebhook: Метод запроса: {req.method}")
    logging.info(f"twilliowebhook: Данные формы запроса: {req.form}")
    logging.info(f"twilliowebhook: Полный запрос: {req.data}")
    caller_phone = req.form.get("From")
    logging.info(f"twilliowebhook: Извлечённый номер телефона (From): {caller_phone}")

    if req.method != "POST":
        logging.error("twilliowebhook: Неправильный метод запроса (ожидается POST)")
        return Response("Method Not Allowed", status=405, mimetype="text/plain")

    try:
        response = VoiceResponse()
        response.say("Hej, du har ringt till SiloService AB. Vänligen ange ditt namn, regionen du befinner dig i och ditt problem.", language="sv-SE")
        logging.info("twilliowebhook: Добавлено приветствие в ответ")
       
        response.record(
            action="https://us-central1-silobot-468218.cloudfunctions.net/handle_recording", 
            recording_status_callback="https://us-central1-silobot-468218.cloudfunctions.net/recording_status",
            max_length=15,
            timeout=10,
        )
        logging.info("twilliowebhook: Добавлено Record в ответ")
        
        xml_response = str(response)
        logging.info(f"twilliowebhook: Сгенерированный XML ответ: {xml_response}")
        return Response(xml_response, mimetype="text/xml")
    except Exception as e:
        logging.error(f"twilliowebhook: Ошибка при генерации ответа: {str(e)}", exc_info=True)
        return Response(f"Server Error: {str(e)}", status=500, mimetype="text/plain")

@https_fn.on_request()
def handle_speech(req: https_fn.Request) -> https_fn.Response:
    logging.info("handle_speech: Запрос получен")
    logging.info(f"handle_speech: Заголовки запроса: {dict(req.headers)}")
    logging.info(f"handle_speech: Метод запроса: {req.method}")
    logging.info(f"handle_speech: Данные формы запроса: {req.form}")
    logging.info(f"handle_speech: Полный запрос: {req.data}")
    caller_phone = req.form.get("From")
    logging.info(f"handle_speech: Извлечённый номер телефона (From): {caller_phone}")

    if req.method != "POST":
        logging.error("handle_speech: Неправильный метод запроса (ожидается POST)")
        return Response("Method Not Allowed", status=405, mimetype="text/plain")

    try:
        speech_result = req.form.get("SpeechResult")
        confidence = req.form.get("Confidence")
        logging.info(f"handle_speech: SpeechResult: {speech_result}, Confidence: {confidence}")
        if not speech_result:
            logging.warning("handle_speech: Отсутствует SpeechResult, возвращаем fallback ответ")
            response = VoiceResponse()
            response.say("Jag förstod inte. Kan du upprepa ditt namn, region och problem?", language="sv-SE")
            gather = Gather(
                input="speech",
                language="sv-SE",
                hints=HINTS,
                action="https://us-central1-silobot-468218.cloudfunctions.net/handle_speech",
                timeout=10,
                speechTimeout=10,
                interimResults=False,
                enhanced=True
            )
            response.append(gather)
            xml_response = str(response)
            logging.info(f"handle_speech: Fallback XML ответ: {xml_response}")
            return Response(xml_response, mimetype="text/xml")

        logging.info(f"handle_speech: SpeechResult: {speech_result}")
        session_id = req.form.get("CallSid")
        logging.info(f"handle_speech: Session ID (CallSid): {session_id}")

        dialogflow_credentials.refresh(Request())
        logging.info("handle_speech: Токен Dialogflow обновлен")

        dialogflow_url = f"https://dialogflow.googleapis.com/v2/projects/{DIALOGFLOW_PROJECT_ID}/agent/sessions/{session_id}:detectIntent"
        headers = {"Authorization": f"Bearer {dialogflow_credentials.token}"}
        logging.info(f"handle_speech: Dialogflow URL: {dialogflow_url}")

        payload = {
            "queryInput": {
                "text": {
                    "text": speech_result,
                    "languageCode": "sv-SE"
                }
            }
        }
        logging.info(f"handle_speech: Payload для Dialogflow: {json.dumps(payload)}")

        dialogflow_response = requests.post(dialogflow_url, headers=headers, json=payload).json()
        logging.info(f"handle_speech: Dialogflow ответ: {json.dumps(dialogflow_response)}")

        response_text = dialogflow_response.get("queryResult", {}).get("fulfillmentText", "Ingen matchande intent.")
        logging.info(f"handle_speech: Response text от Dialogflow: {response_text}")

        synthesis_input = texttospeech.SynthesisInput(text=response_text)
        voice = texttospeech.VoiceSelectionParams(language_code="sv-SE", name="sv-SE-Wavenet-A")
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3, speaking_rate=1.0, pitch=+2.0)
        logging.info("handle_speech: TTS параметры: language_code=sv-SE, name=sv-SE-Wavenet-A, encoding=MP3")
        tts_response = tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
        logging.info("handle_speech: TTS ответ получен")

        file_name = f"response_{session_id}.mp3"
        file = bucket.blob(file_name)
        file.upload_from_string(tts_response.audio_content, content_type="audio/mp3")
        logging.info(f"handle_speech: Файл загружен: {file_name}")
        file.make_public()
        logging.info("handle_speech: Файл сделан публичным")
        audio_url = f"https://storage.googleapis.com/{bucket.name}/{file_name}"
        logging.info(f"handle_speech: Audio URL: {audio_url}")

        response = VoiceResponse()
        response.play(audio_url)
        response.pause(length=2)
        response.hangup()
        logging.info("handle_speech: Добавлена пауза 2 секунды и завершение звонка")
        xml_response = str(response)
        logging.info(f"handle_speech: Сгенерированный XML ответ: {xml_response}")
        return Response(xml_response, mimetype="text/xml")
    except Exception as e:
        logging.error(f"handle_speech: Ошибка при обработке запроса: {str(e)}", exc_info=True)
        return Response(f"Server Error: {str(e)}", status=500, mimetype="text/plain")

@https_fn.on_request()
def handle_recording(req: https_fn.Request) -> https_fn.Response:
    logging.info("handle_recording: Запрос получен")
    logging.info(f"handle_recording: Заголовки запроса: {dict(req.headers)}")
    logging.info(f"handle_recording: Метод запроса: {req.method}")
    logging.info(f"handle_recording: Данные формы запроса: {req.form}")
    logging.info(f"handle_recording: Полный запрос: {req.data}")
    caller_phone = req.form.get("From")
    logging.info(f"handle_recording: Извлечённый номер телефона (From): {caller_phone}")

    if req.method != "POST":
        logging.error("handle_recording: Неправильный метод запроса (ожидается POST)")
        return Response("Method Not Allowed", status=405, mimetype="text/plain")
    
    try: 
        recording_url = req.form.get("RecordingUrl")
        session_id = req.form.get("CallSid")
        logging.info(f"handle_recording: RecordingUrl: {recording_url}, Session ID (CallSid): {session_id}")

        if not recording_url:
            logging.warning("handle_recording: Отсутствует RecordingUrl")
            response = VoiceResponse()
            response.say("Jag förstod inte. Kan du upprepa snalla?", language="sv-SE")
            response.record(
                action="https://us-central1-silobot-468218.cloudfunctions.net/handle_recording", 
                recording_status_callback="https://us-central1-silobot-468218.cloudfunctions.net/recording_status",
                max_length=15,
                timeout=5,
            )
            xml_response = str(response)
            logging.info(f"handle_recording: Fallback XML ответ: {xml_response}")
            return Response(xml_response, mimetype="text/xml")
        
        response = requests.get(recording_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
        response.raise_for_status()
        audio_content = response.content
        logging.info(f"handle_recording: Аудиофайл успешно загружен, размер: {len(audio_content)} байт")
        
        temp_audio_path = f"/tmp/recording_{session_id}.wav"
        with open(temp_audio_path, "wb") as f:
            f.write(audio_content)

        import subprocess
        converted_audio_path = f"/tmp/converted_{session_id}.wav"
        subprocess.run(["ffmpeg", "-i", temp_audio_path, "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", converted_audio_path], check=True)

        with open(converted_audio_path, "rb") as f:
            audio_content_converted = f.read()
        
        audio_file_name = f"recording_{session_id}.mp3"
        audio_file = bucket.blob(audio_file_name)
        audio_file.upload_from_string(audio_content, content_type="audio/mp3")
        audio_file.make_public()
        logging.info(f"handle_recording: Аудиофайл сохранен: https://storage.googleapis.com/{bucket.name}/{audio_file_name}")
        
        speech_client = speech.SpeechClient(credentials=dialogflow_credentials)
        audio = speech.RecognitionAudio(content=audio_content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.MP3,
            sample_rate_hertz=16000,
            language_code="sv-SE",
            enable_automatic_punctuation=True,
            speech_contexts=[{
                "phrases": HINTS + ["rost", "rost på silo", "rostproblem", "rostig", "problem med rost", "rostig silo", "jag har rost på silo"],
                "boost": 90.0
            }],
            model="default",
            use_enhanced=True,
            enable_word_time_offsets=True
        )
        
        speech_response = speech_client.recognize(config=config, audio=audio)
        logging.info(f"handle_recording: Полный ответ Speech-to-Text: {speech_response}")
        speech_result = speech_response.results[0].alternatives[0].transcript if speech_response.results else ""
        confidence = speech_response.results[0].alternatives[0].confidence if speech_response.results else 0.0
        logging.info(f"handle_recording: Распознанный текст: {speech_result}, Confidence: {confidence}")
        
        if not speech_result:
            logging.warning("handle_recording: Speech-to-Text не вернул результат")
            response = VoiceResponse()
            response.say("Jag förstod inte. Kan du upprepa snalla?", language="sv-SE")
            response.record(
                action="https://us-central1-silobot-468218.cloudfunctions.net/handle_recording", 
                recording_status_callback="https://us-central1-silobot-468218.cloudfunctions.net/recording_status",
                max_length=15,
                timeout=15,
            )
            xml_response = str(response)
            logging.info(f"handle_recording: Fallback XML ответ: {xml_response}")
            return Response(xml_response, mimetype="text/xml")
        
        dialogflow_credentials.refresh(Request())
        logging.info("handle_recording: Токен Dialogflow обновлен")
        
        dialogflow_url = f"https://dialogflow.googleapis.com/v2/projects/{DIALOGFLOW_PROJECT_ID}/agent/sessions/{session_id}:detectIntent"
        payload = {
            "queryInput": {
                "text": {
                    "text": speech_result,
                    "languageCode": "sv-SE"
                }
            },
            "queryParams": {
                "payload": {
                    "caller_phone": caller_phone if caller_phone else "Unknown",
                    "original_text": speech_result
                }
            },
            "queryParams": {
                "contexts": [
                    {
                        "name": f"projects/{DIALOGFLOW_PROJECT_ID}/agent/sessions/{session_id}/contexts/caller-info",
                        "parameters": {
                            "caller_phone": caller_phone if caller_phone else "Unknown"
                        }
                    }
                ]
            }
        }
        logging.info(f"handle_recording: Проверка перед отправкой в Dialogflow - caller_phone: {caller_phone if caller_phone else 'Unknown'}, payload: {json.dumps(payload)}")
        logging.info(f"handle_recording: Передаваемый caller_phone: {caller_phone if caller_phone else 'Unknown'}")
        logging.info(f"handle_recording: Полный payload для Dialogflow: {json.dumps(payload)}")

        dialogflow_response = requests.post(dialogflow_url, headers={"Authorization": f"Bearer {dialogflow_credentials.token}"}, json=payload).json()
        logging.info(f"handle_recording: Dialogflow ответ: {json.dumps(dialogflow_response)}")

        response_text = dialogflow_response.get("queryResult", {}).get("fulfillmentText", "Ingen matchande intent.")
        logging.info(f"handle_recording: Response text от Dialogflow: {response_text}")
        
        synthesis_input = texttospeech.SynthesisInput(text=response_text)
        voice = texttospeech.VoiceSelectionParams(language_code="sv-SE", name="sv-SE-Wavenet-A")
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3, speaking_rate=1.0, pitch=+2.0)
        logging.info("handle_recording: TTS параметры: language_code=sv-SE, name=sv-SE-Wavenet-A, encoding=MP3")
        tts_response = tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
        logging.info("handle_recording: TTS ответ получен")

        file_name = f"response_{session_id}.mp3"
        file = bucket.blob(file_name)
        file.upload_from_string(tts_response.audio_content, content_type="audio/mp3")
        logging.info(f"handle_recording: Файл загружен: {file_name}")
        file.make_public()
        logging.info("handle_recording: Файл сделан публичным")
        audio_url = f"https://storage.googleapis.com/{bucket.name}/{file_name}"
        logging.info(f"handle_recording: Audio URL: {audio_url}")

        response = VoiceResponse()
        response.play(audio_url)
        response.pause(length=2)
        response.hangup()
        logging.info("handle_recording: Добавлена пауза 2 секунды и завершение звонка")
        xml_response = str(response)
        logging.info(f"handle_recording: Сгенерированный XML ответ: {xml_response}")
        return Response(xml_response, mimetype="text/xml")
    except Exception as e:
        logging.error(f"handle_recording: Ошибка при обработке запроса: {str(e)}", exc_info=True)
        return Response(f"Server Error: {str(e)}", status=500, mimetype="text/plain")
        
@https_fn.on_request()
def recording_status(req: https_fn.Request) -> https_fn.Response:    
    logging.info("recording_status: Запрос получен: {req.form}")
    caller_phone = req.form.get("From")
    logging.info(f"recording_status: Извлечённый номер телефона (From): {caller_phone}")
    return Response("OK", status=200, mimetype="text/plain")
        
@https_fn.on_request()
def dialogflowWebhook(req: https_fn.Request) -> https_fn.Response:
    logging.info("dialogflowWebhook: Запрос получен")
    logging.info(f"dialogflowWebhook: Заголовки запроса: {dict(req.headers)}")
    logging.info(f"dialogflowWebhook: Метод запроса: {req.method}")
    logging.info(f"dialogflowWebhook: JSON запроса: {req.json}")
    logging.info(f"dialogflowWebhook: Полный запрос: {req.data}")
    logging.info(f"dialogflowWebhook: Полный JSON запрос: {json.dumps(req.json, indent=2)}")

    session_id = req.json.get("session", "").split("/")[-1] or "unknown_session"
    caller_phone = None
    contexts = req.json.get("queryResult", {}).get("outputContexts", [])
    for context in contexts:
        if context.get("name").endswith("/contexts/caller-info"):
            caller_phone = context.get("parameters", {}).get("caller_phone")
            break

    if not caller_phone:
        caller_phone = req.json.get("queryParams", {}).get("payload", {}).get("caller_phone")

    logging.info(f"dialogflowWebhook: Номер телефона из контекста или payload: {caller_phone}")

    if not caller_phone:
        logging.warning("dialogflowWebhook: Номер телефона не найден, используем Unknown")
        caller_phone = "Unknown"

    logging.info(f"dialogflowWebhook: Извлечённый номер телефона: {caller_phone}")

    if req.method != "POST":
        logging.error("dialogflowWebhook: Неправильный метод запроса (ожидается POST)")
        return Response("Method Not Allowed", status=405, mimetype="text/plain")

    try:
        if not req.json or "session" not in req.json:
            logging.error("dialogflowWebhook: Отсутствует поле session в запросе")
            return Response("Server Error: Missing session field", status=400, mimetype="text/plain")

        intent_name = req.json.get("queryResult", {}).get("intent", {}).get("displayName", "unknown_intent")
        logging.info(f"dialogflowWebhook: Session ID: {session_id}, Intent: {intent_name}")

        if intent_name == "UserInfoIntent":
            parameters = req.json.get("queryResult", {}).get("parameters", {})
            logging.info(f"dialogflowWebhook: Параметры: {parameters}")

            name_param = parameters.get("name", "Okänd")
            if isinstance(name_param, list):
                name = name_param[0] if name_param else "Okänd"
            elif isinstance(name_param, dict):
                name = next(iter(name_param.values()), "Okänd") if name_param else "Okänd"
            else:
                name = str(name_param) if name_param else "Okänd"

            region_param = parameters.get("region", "Okänd")
            if isinstance(region_param, list):
                region = region_param[0] if region_param else "Okänd"
            elif isinstance(region_param, dict):
                region = next(iter(region_param.values()), "Okänd") if region_param else "Okänd"
            else:
                region = str(region_param) if region_param else "Okänd"

            problem_param = parameters.get("problem", "Okänd")
            if isinstance(problem_param, list):
                problem = problem_param[0] if problem_param else "Okänd"
            else:
                problem = str(problem_param) if problem_param else "Okänd"

            logging.info(f"dialogflowWebhook: Name: {name}, Region: {region}, Problem: {problem}")

            lead_data = {
                "name": name,
                "region": region,
                "problem": problem,
                "phone": caller_phone,
                "timestamp": firestore.SERVER_TIMESTAMP
            }
            try:
                db.collection("leads").document(f"lead_{session_id}").set(lead_data)
                logging.info("dialogflowWebhook: Данные записаны в Firestore")
            except Exception as firestore_error:
                logging.error(f"dialogflowWebhook: Ошибка записи в Firestore: {str(firestore_error)}", exc_info=True)

            message_body = f"Ny lead: Namn: {name}, Region: {region}, Problem: {problem}, Telefon: {caller_phone}"
            try:
                message = twilio_client.messages.create(
                    body=message_body,
                    from_=TWILIO_PHONE_NUMBER,
                    to=MANAGER_PHONE_NUMBER
                )
                logging.info(f"dialogflowWebhook: SMS отправлен менеджеру: {message.sid}")
            except Exception as sms_error:
                logging.error(f"dialogflowWebhook: Ошибка отправки SMS: {str(sms_error)}", exc_info=True)

            response_text = f"Tack, jag har vidarebefordrat informationen till chefen, vi hjälper dig att lösa problemet med {problem}. Vi kontaktar dig inom 30 minuter för att klargöra detaljerna. Ha en bra dag, {name}."
        else:
            response_text = "Jag förstod inte. Kan du upprepa ditt namn, region och problem?"
            logging.info(f"dialogflowWebhook: Fallback response: {response_text}")

        fulfillment_response = {"fulfillmentText": response_text}
        logging.info(f"dialogflowWebhook: Сгенерированный ответ: {json.dumps(fulfillment_response)}")
        return Response(json.dumps(fulfillment_response), mimetype="application/json")
    except Exception as e:
        logging.error(f"dialogflowWebhook: Ошибка при обработке запроса: {str(e)}", exc_info=True)
        return Response(f"Server Error: {str(e)}", status=500, mimetype="text/plain")
import io
import os
import speech_recognition as sr
import openai
from datetime import datetime, timedelta
from queue import Queue
from tempfile import NamedTemporaryFile
from time import sleep, time
from flask import Flask, Response, render_template

app = Flask(__name__)

# Global variables to control recording state
keep_recording = False
transcription = ['']

PARAMS = {

}
openai.api_key = os.environ.get('OPENAI_API_KEY')

def transcribe(phrase_complete=True):
    temp_file = PARAMS["temp_file"]
    print("TEMP FILE", temp_file)
    text = ""
    if temp_file and os.path.exists(temp_file):
        try:
            if phrase_complete:
                with open(temp_file, "rb") as audio_file:
                    text = openai.Audio.transcribe(
                        "whisper-1", audio_file, language="en"
                    )['text'].strip()
                    print("TEXTTTTTTTTTTTT --->", time(),  text)
        except Exception as ex:
            print("RATE LIMIT EXCEEDED", ex)
            PARAMS.get("stop_listening")()
    return text


def record_audio():
    print("Transcription Started...")
    keep_recording = True
     # The last time a recording was retreived from the queue.
    phrase_time = None
    # Current raw audio bytes.
    last_sample = bytes()
    # Thread safe Queue for passing data from the threaded recording callback.
    data_queue = Queue()
    # We use SpeechRecognizer to record our audio because it has a nice feauture where it can detect when speech ends.
    recorder = sr.Recognizer()
    # recorder.energy_threshold = 1000#args.energy_threshold
    # Definitely do this, dynamic energy compensation lowers the energy threshold dramtically to a point where the SpeechRecognizer never stops recording.
    # recorder.dynamic_energy_threshold = False
    # source = sr.Microphone(sample_rate=16000)
    source = sr.Microphone()
    phrase_timeout = 20#args.phrase_timeout
    

    with source:
        recorder.adjust_for_ambient_noise(source)

    def record_callback(_, audio:sr.AudioData) -> None:
        """
        Threaded callback function to recieve audio data when recordings finish.
        audio: An AudioData containing the recorded bytes.
        """
        # Grab the raw bytes and push it into the thread safe queue.
        data = audio.get_raw_data()
        data_queue.put(data)

    global stop_listening, transcripion
    # transcription = ['']
    stop_listening = recorder.listen_in_background(source, record_callback)
    PARAMS["stop_listening"] = stop_listening
    PARAMS["phrase_complete"] = False
    # stop_listening(wait_for_stop=False) - stop listening thread
    temp_file = NamedTemporaryFile().name + ".wav"
    print("here", temp_file)
    phrase_time = None
    while True:
        try:
            now = time()
            # Pull raw recorded audio from the queue.
            if not data_queue.empty():
                if not phrase_time:
                    print("PHRASE TIME ", phrase_time)
                    phrase_time = now
                phrase_complete = False
                # If enough time has passed between recordings, consider the phrase complete.
                # Clear the current working audio buffer to start over with the new data.
                if phrase_time and now - phrase_time > 10:
                    print("PHRASE DIFF", now-phrase_time)
                    last_sample = bytes()
                    phrase_complete = True
                # This is the last time we received new audio data from the queue.

                # Concatenate our current audio data with the latest audio data.
                while not data_queue.empty():
                    data = data_queue.get()
                    last_sample += data

                # Concatenate our current audio data with the latest audio data.

                # Use AudioData to convert the raw data to wav data.
                audio_data = sr.AudioData(last_sample, source.SAMPLE_RATE, source.SAMPLE_WIDTH)
                wav_data = io.BytesIO(audio_data.get_wav_data())

                # Write wav data to the temporary file as bytes.

                with open(temp_file, 'w+b') as f:
                    f.write(wav_data.read())
                # Call OpenAI API to get transcriptions
                PARAMS["phrase_complete"] = phrase_complete
                PARAMS["temp_file"] = temp_file
                text = transcribe()

                # Read the transcription.
                # result = audio_model.transcribe(temp_file, fp16=torch.cuda.is_available())
                # text = result['text'].strip()

                # If we detected a pause between recordings, add a new item to our transcripion.
                # Otherwise edit the existing one.
                if phrase_complete:
                    transcription.append(text)
                else:
                    transcription[-1] = text
                # Clear the console to reprint the updated transcription.
                # os.system('cls' if os.name=='nt' else 'clear')
                print ("*"*50)
                for line in transcription:
                    print("LINE -->",line)
                # Flush stdout.
                print('', end='', flush=True)

                # Infinite loops are bad for processors, must sleep.
                sleep(1)
                if PARAMS.get("STOP_RECORDING"):
                    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                    break
                
        except KeyboardInterrupt:
            break
    else:
        print("222222222222")


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_recording():
    record_audio()
    return Response(status=200)

@app.route('/stop', methods=['POST'])
def stop_recording():
    print("Transcription")
    
    PARAMS.get("stop_listening")()
    PARAMS["STOP_RECORDING"] = True
    # stop_listening(wait_for_stop=True)
    global transcription
    try:
        text = transcribe(phrase_complete=True)
        transcription.append(text)
        print("STOP TEXT", text)
    except Exception as ex:
        print(ex)
    sleep(2)
    for line in transcription:
        print("transcript -->", line)
    return render_template('transcription.html', transcription=transcription)

@app.route('/transcribe', methods=['POST'])
def transcribe_audio_endpoint():
    global transcription
    return Response(status=200)

if __name__ == '__main__':
    app.run(debug=True)

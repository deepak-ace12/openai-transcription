import io
import os
import speech_recognition as sr
import openai
from datetime import datetime, timedelta
from queue import Queue
from tempfile import NamedTemporaryFile
from time import sleep

openai.api_key = os.environ.get('OPENAI_API_KEY')

def main():
     # The last time a recording was retreived from the queue.
    phrase_time = None
    # Current raw audio bytes.
    last_sample = bytes()
    # Thread safe Queue for passing data from the threaded recording callback.
    data_queue = Queue()
    # We use SpeechRecognizer to record our audio because it has a nice feauture where it can detect when speech ends.
    recorder = sr.Recognizer()
    recorder.energy_threshold = 1000#args.energy_threshold
    # Definitely do this, dynamic energy compensation lowers the energy threshold dramtically to a point where the SpeechRecognizer never stops recording.
    recorder.dynamic_energy_threshold = False
    source = sr.Microphone(sample_rate=16000)
    record_timeout = 2#args.record_timeout
    phrase_timeout = 60#args.phrase_timeout
    transcription = ['']

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

    stop_listening = recorder.listen_in_background(source, record_callback, phrase_time_limit=60)
    # stop_listening(wait_for_stop=False) - stop listening thread
    while True:
        try:
            now = datetime.utcnow()
            # Pull raw recorded audio from the queue.
            if not data_queue.empty():
                phrase_complete = False
                # If enough time has passed between recordings, consider the phrase complete.
                # Clear the current working audio buffer to start over with the new data.
                if phrase_time and now - phrase_time > timedelta(seconds=phrase_timeout):
                    last_sample = bytes()
                    phrase_complete = True
                # This is the last time we received new audio data from the queue.
                phrase_time = now

                # Concatenate our current audio data with the latest audio data.
                while not data_queue.empty():
                    data = data_queue.get()
                    last_sample += data

                # Use AudioData to convert the raw data to wav data.
                audio_data = sr.AudioData(last_sample, source.SAMPLE_RATE, source.SAMPLE_WIDTH)
                wav_data = io.BytesIO(audio_data.get_wav_data())

                # Write wav data to the temporary file as bytes.
                temp_file = NamedTemporaryFile().name + ".wav"
                with open(temp_file, 'w+b') as f:
                    f.write(wav_data.read())
                # Call OpenAI API to get transcriptions
                try:
                    with open(temp_file, "rb") as audio_file:
                        text = openai.Audio.transcribe(
                            "whisper-1", audio_file, language="en"
                        )['text'].strip()
                        print("TEXT", text)
                    os.remove(temp_file)
                except Exception as ex:
                    print("RATE LIMIT EXCEEDED", ex)
                    os.remove(temp_file)
                    break

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
                os.system('cls' if os.name=='nt' else 'clear')
                for line in transcription:
                    print(line)
                # Flush stdout.
                print('', end='', flush=True)

                # Infinite loops are bad for processors, must sleep.
                sleep(0.25)
                
        except KeyboardInterrupt:
            break

    print("\n\nTranscription:")
    for line in transcription:
        print(line)


if __name__ == "__main__":
    main()
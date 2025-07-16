#!/usr/bin/env python3
import os
import subprocess
import tempfile
import time
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import boto3
from botocore.exceptions import ClientError
import threading
import json
import requests
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
import shutil
import io

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2GB max file size

# AWS 설정
S3_BUCKET = 'video-converter-storage-2025'
AWS_REGION = 'ap-northeast-2'

# 전역 변수로 작업 상태 추적
job_status = {}
completed_jobs = {}  # 완료된 작업의 텍스트 및 영상 저장

class FastVideoProcessor:
    def __init__(self):
        self.s3_client = boto3.client('s3', region_name=AWS_REGION)
        self.transcribe_client = boto3.client('transcribe', region_name=AWS_REGION)
        self.cpu_count = multiprocessing.cpu_count()
    
    def convert_video_fast(self, input_path, output_path, target_resolution="720"):
        """초고속 영상 변환"""
        try:
            cmd = [
                '/usr/local/bin/ffmpeg',
                '-i', input_path,
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-crf', '28',
                '-vf', f'scale=-2:{target_resolution}',
                '-c:a', 'aac',
                '-b:a', '96k',
                '-ac', '1',
                '-threads', str(self.cpu_count),
                '-y',
                output_path
            ]
            
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            if process.returncode != 0:
                raise Exception(f"FFmpeg error: {process.stderr}")
            
            if not os.path.exists(output_path):
                raise Exception("변환된 파일이 생성되지 않았습니다")
            
            return output_path
            
        except subprocess.TimeoutExpired:
            raise Exception("영상 변환 시간이 초과되었습니다")
        except Exception as e:
            raise Exception(f"영상 변환 오류: {str(e)}")
    
    def extract_audio_fast(self, video_path, audio_path):
        """초고속 오디오 추출"""
        try:
            cmd = [
                '/usr/local/bin/ffmpeg',
                '-i', video_path,
                '-vn',
                '-acodec', 'pcm_s16le',
                '-ar', '16000',
                '-ac', '1',
                '-threads', str(self.cpu_count),
                '-y',
                audio_path
            ]
            
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if process.returncode != 0:
                raise Exception(f"Audio extraction error: {process.stderr}")
            
            if not os.path.exists(audio_path):
                raise Exception("오디오 파일이 생성되지 않았습니다")
            
            return audio_path
            
        except subprocess.TimeoutExpired:
            raise Exception("오디오 추출 시간이 초과되었습니다")
        except Exception as e:
            raise Exception(f"오디오 추출 오류: {str(e)}")
    
    def upload_to_s3_fast(self, file_path, s3_key):
        """안전한 S3 업로드"""
        try:
            if not os.path.exists(file_path):
                raise Exception(f"업로드할 파일이 존재하지 않습니다: {file_path}")
            
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                raise Exception("업로드할 파일이 비어있습니다")
            
            # 큰 파일은 멀티파트 업로드 사용
            if file_size > 100 * 1024 * 1024:  # 100MB 이상
                config = boto3.s3.transfer.TransferConfig(
                    multipart_threshold=1024 * 25,  # 25MB
                    max_concurrency=10,
                    multipart_chunksize=1024 * 25,
                    use_threads=True
                )
                self.s3_client.upload_file(
                    file_path, S3_BUCKET, s3_key,
                    Config=config
                )
            else:
                self.s3_client.upload_file(file_path, S3_BUCKET, s3_key)
            
            return f"s3://{S3_BUCKET}/{s3_key}"
            
        except ClientError as e:
            raise Exception(f"S3 업로드 오류: {e}")
        except Exception as e:
            raise Exception(f"파일 업로드 오류: {str(e)}")
    
    def transcribe_audio_fast(self, s3_audio_uri, job_name):
        """Amazon Transcribe로 고속 음성 인식"""
        try:
            # 기존 작업이 있다면 삭제
            try:
                self.transcribe_client.delete_transcription_job(
                    TranscriptionJobName=job_name
                )
                time.sleep(2)
            except:
                pass
            
            # Transcribe 작업 시작
            response = self.transcribe_client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={'MediaFileUri': s3_audio_uri},
                MediaFormat='wav',
                LanguageCode='ko-KR',
                Settings={
                    'ShowSpeakerLabels': True,
                    'MaxSpeakerLabels': 10,
                    'ShowAlternatives': False,
                }
            )
            
            # 작업 완료 대기
            max_wait_time = 1800  # 30분 최대 대기
            start_time = time.time()
            
            while True:
                if time.time() - start_time > max_wait_time:
                    raise Exception("음성 인식 시간이 초과되었습니다")
                
                status = self.transcribe_client.get_transcription_job(
                    TranscriptionJobName=job_name
                )
                
                job_status_name = status['TranscriptionJob']['TranscriptionJobStatus']
                if job_status_name in ['COMPLETED', 'FAILED']:
                    break
                
                time.sleep(3)
            
            if job_status_name == 'COMPLETED':
                transcript_uri = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
                
                response = requests.get(transcript_uri, timeout=30)
                response.raise_for_status()
                transcript_data = response.json()
                
                transcript_text = transcript_data['results']['transcripts'][0]['transcript']
                if not transcript_text.strip():
                    return "음성을 인식할 수 없습니다. 오디오 품질을 확인해주세요."
                
                return transcript_text
            else:
                failure_reason = status['TranscriptionJob'].get('FailureReason', '알 수 없는 오류')
                raise Exception(f"음성 인식 실패: {failure_reason}")
                
        except ClientError as e:
            raise Exception(f"Transcribe 오류: {e}")
        except requests.RequestException as e:
            raise Exception(f"결과 다운로드 오류: {e}")
        except Exception as e:
            raise Exception(f"음성 인식 오류: {str(e)}")

processor = FastVideoProcessor()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_video():
    try:
        if 'video_file' not in request.files:
            return jsonify({'error': '파일을 선택해주세요.'}), 400
        
        file = request.files['video_file']
        if file.filename == '':
            return jsonify({'error': '파일을 선택해주세요.'}), 400
        
        job_id = str(uuid.uuid4())
        
        # 파일을 메모리에 읽어서 크기 확인 (스트림 문제 해결)
        file_content = file.read()
        file_size = len(file_content)
        
        if file_size == 0:
            return jsonify({'error': '빈 파일입니다.'}), 400
        
        if file_size > 2 * 1024 * 1024 * 1024:  # 2GB
            return jsonify({'error': '파일 크기가 2GB를 초과합니다.'}), 400
        
        job_status[job_id] = {
            'status': 'starting',
            'progress': 0,
            'message': '고속 처리를 시작합니다...',
            'start_time': time.time(),
            'file_size': file_size
        }
        
        # 백그라운드에서 고속 처리 (파일 내용을 직접 전달)
        thread = threading.Thread(
            target=process_video_fast,
            args=(job_id, file_content, file.filename),
            daemon=True
        )
        thread.start()
        
        return jsonify({'job_id': job_id})
        
    except Exception as e:
        return jsonify({'error': f'업로드 오류: {str(e)}'}), 500

@app.route('/status/<job_id>')
def get_status(job_id):
    if job_id in job_status:
        status = job_status[job_id].copy()
        if 'start_time' in status:
            status['elapsed_time'] = time.time() - status['start_time']
        return jsonify(status)
    else:
        return jsonify({'error': '작업을 찾을 수 없습니다.'}), 404

@app.route('/download/txt/<job_id>')
def download_transcript(job_id):
    """텍스트 파일 다운로드"""
    if job_id not in completed_jobs:
        return jsonify({'error': '완료된 작업을 찾을 수 없습니다.'}), 404
    
    try:
        job_data = completed_jobs[job_id]
        transcript = job_data.get('transcript', '')
        title = job_data.get('title', 'transcript')
        
        # 안전한 파일명 생성
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        if not safe_title:
            safe_title = "transcript"
        
        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(f"영상 제목: {title}\n")
            f.write(f"변환 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")
            f.write(transcript)
            temp_path = f.name
        
        return send_file(
            temp_path,
            as_attachment=True,
            download_name=f"{safe_title}_transcript.txt",
            mimetype='text/plain'
        )
        
    except Exception as e:
        return jsonify({'error': f'다운로드 오류: {str(e)}'}), 500

@app.route('/download/video/<job_id>')
def download_video(job_id):
    """720p 변환된 영상 파일 다운로드"""
    if job_id not in completed_jobs:
        return jsonify({'error': '완료된 작업을 찾을 수 없습니다.'}), 404
    
    try:
        job_data = completed_jobs[job_id]
        video_s3_key = job_data.get('video_s3_key')
        title = job_data.get('title', 'video')
        
        if not video_s3_key:
            return jsonify({'error': '영상 파일을 찾을 수 없습니다.'}), 404
        
        # 안전한 파일명 생성
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        if not safe_title:
            safe_title = "video"
        
        # S3에서 임시 파일로 다운로드
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            processor.s3_client.download_file(S3_BUCKET, video_s3_key, temp_file.name)
            
            return send_file(
                temp_file.name,
                as_attachment=True,
                download_name=f"{safe_title}_720p.mp4",
                mimetype='video/mp4'
            )
        
    except Exception as e:
        return jsonify({'error': f'영상 다운로드 오류: {str(e)}'}), 500

def process_video_fast(job_id, file_content, original_filename):
    """고속 영상 처리 - 영상 다운로드 기능 추가"""
    temp_dir = None
    try:
        # 임시 디렉토리 생성
        temp_dir = tempfile.mkdtemp()
        
        # 1. 파일 저장 (5%)
        job_status[job_id].update({
            'status': 'processing',
            'progress': 5,
            'message': '파일을 저장하고 있습니다...'
        })
        
        filename = secure_filename(original_filename)
        if not filename:
            filename = f"video_{job_id}.mp4"
        
        input_path = os.path.join(temp_dir, filename)
        
        # 파일 내용을 직접 디스크에 저장
        with open(input_path, 'wb') as f:
            f.write(file_content)
        
        # 파일 저장 확인
        if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
            raise Exception("파일 저장에 실패했습니다")
        
        print(f"파일 저장 완료: {input_path}, 크기: {os.path.getsize(input_path)} bytes")
        
        # 2. 고속 720p 변환 (30%)
        job_status[job_id].update({
            'status': 'processing',
            'progress': 15,
            'message': '초고속 720p 변환 중... (멀티코어 활용)'
        })
        
        converted_path = os.path.join(temp_dir, f"fast_converted_{filename}")
        processor.convert_video_fast(input_path, converted_path)
        
        # 3. 변환된 영상을 S3에 업로드 (40%)
        job_status[job_id].update({
            'status': 'processing',
            'progress': 25,
            'message': '720p 영상을 업로드 중...'
        })
        
        s3_video_key = f"videos/{job_id}_720p.mp4"
        processor.upload_to_s3_fast(converted_path, s3_video_key)
        
        # 4. 고속 오디오 추출 (60%)
        job_status[job_id].update({
            'status': 'processing',
            'progress': 45,
            'message': '초고속 오디오 추출 중...'
        })
        
        audio_path = os.path.join(temp_dir, f"audio_{job_id}.wav")
        processor.extract_audio_fast(converted_path, audio_path)
        
        # 5. 오디오를 S3에 업로드 (75%)
        job_status[job_id].update({
            'status': 'processing',
            'progress': 65,
            'message': '오디오 파일 업로드 중...'
        })
        
        s3_audio_key = f"audio/{job_id}.wav"
        s3_audio_uri = processor.upload_to_s3_fast(audio_path, s3_audio_key)
        
        # 6. AI 음성 인식 (90%)
        job_status[job_id].update({
            'status': 'processing',
            'progress': 80,
            'message': 'AI 음성 인식 중... (고속 모드)'
        })
        
        transcript = processor.transcribe_audio_fast(s3_audio_uri, f"fast-job-{job_id}")
        
        # 7. 완료 (100%)
        job_status[job_id].update({
            'status': 'completed',
            'progress': 100,
            'message': '고속 변환 완료! 파일들을 다운로드하세요.',
            'transcript': transcript,
            'title': filename.split('.')[0],
            'end_time': time.time(),
            'download_ready': True,
            'video_ready': True
        })
        
        # 완료된 작업 저장
        completed_jobs[job_id] = {
            'transcript': transcript,
            'title': filename.split('.')[0],
            'video_s3_key': s3_video_key,
            'completed_at': time.time()
        }
        
        print(f"작업 완료: {job_id}")
        
    except Exception as e:
        print(f"작업 오류: {job_id}, {str(e)}")
        job_status[job_id].update({
            'status': 'error',
            'message': f'오류 발생: {str(e)}'
        })
    finally:
        # 임시 파일 정리
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                print(f"임시 디렉토리 정리 완료: {temp_dir}")
            except Exception as e:
                print(f"임시 디렉토리 정리 실패: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)

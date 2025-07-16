# AI-Agent: 초고속 영상 음성 변환 서비스

AWS 클라우드 기반의 고성능 영상 음성 변환 서비스입니다. 영상 파일을 업로드하면 자동으로 720p로 변환하고 AI 음성 인식을 통해 텍스트를 추출합니다.

## 주요 기능

### 핵심 기능
- **영상 업로드**: 최대 2GB 크기의 영상 파일 지원
- **720p 자동 변환**: FFmpeg를 활용한 고속 영상 변환
- **AI 음성 인식**: Amazon Transcribe를 통한 한국어 음성-텍스트 변환
- **이중 다운로드**: 변환된 720p 영상 파일과 텍스트 파일 모두 다운로드 가능

### 성능 최적화
- **멀티코어 CPU 활용**: 모든 CPU 코어를 동시 사용하여 처리 속도 극대화
- **병렬 처리**: 영상 변환과 오디오 추출을 최적화된 순서로 처리
- **멀티파트 업로드**: 대용량 파일의 빠른 클라우드 업로드
- **실시간 진행률**: 처리 상황을 실시간으로 모니터링

## 시스템 요구사항

### 서버 환경
- **운영체제**: Amazon Linux 2
- **인스턴스 타입**: t3.medium 이상 권장
- **스토리지**: 30GB 이상
- **메모리**: 4GB 이상

### AWS 서비스
- **EC2**: 웹 서버 및 영상 처리
- **S3**: 파일 저장소
- **Amazon Transcribe**: AI 음성 인식
- **IAM**: 권한 관리

### 소프트웨어 의존성
- Python 3.7+
- Flask 2.2.5
- boto3 (AWS SDK)
- FFmpeg (영상 처리)
- yt-dlp (제거됨)

## 설치 및 배포

### 1. EC2 인스턴스 생성
```bash
# AWS CLI를 통한 인스턴스 생성
aws ec2 run-instances \
    --image-id ami-02f550d567803aae7 \
    --instance-type t3.medium \
    --count 1 \
    --key-name your-key-name \
    --security-group-ids sg-xxxxxxxxx \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=video-converter-server}]'
```

### 2. 보안 그룹 설정
```bash
# HTTP 포트 8080 허용
aws ec2 authorize-security-group-ingress \
    --group-id sg-xxxxxxxxx \
    --protocol tcp \
    --port 8080 \
    --cidr 0.0.0.0/0

# SSH 포트 22 허용
aws ec2 authorize-security-group-ingress \
    --group-id sg-xxxxxxxxx \
    --protocol tcp \
    --port 22 \
    --cidr 0.0.0.0/0
```

### 3. 서버 환경 설정
```bash
# 시스템 업데이트
sudo yum update -y

# Python 및 필수 패키지 설치
sudo yum install -y python3 python3-pip

# FFmpeg 설치 (정적 빌드)
sudo wget -O /usr/local/bin/ffmpeg https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
cd /tmp
sudo wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
sudo tar -xf ffmpeg-release-amd64-static.tar.xz
sudo cp ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/
sudo cp ffmpeg-*-amd64-static/ffprobe /usr/local/bin/
sudo chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe

# Python 패키지 설치
sudo pip3 install flask boto3 requests "urllib3<2.0"
```

### 4. 애플리케이션 배포
```bash
# 애플리케이션 디렉토리 생성
sudo mkdir -p /opt/video-converter/templates

# 파일 복사
sudo cp app.py /opt/video-converter/
sudo cp templates/index.html /opt/video-converter/templates/

# 권한 설정
sudo chown -R root:root /opt/video-converter
sudo chmod +x /opt/video-converter/app.py
```

### 5. 시스템 서비스 설정
```bash
# 서비스 파일 복사
sudo cp video-converter.service /etc/systemd/system/

# 서비스 활성화 및 시작
sudo systemctl daemon-reload
sudo systemctl enable video-converter
sudo systemctl start video-converter
```

## AWS 자격 증명 설정

### 방법 1: AWS CLI 설정
```bash
aws configure set aws_access_key_id YOUR_ACCESS_KEY
aws configure set aws_secret_access_key YOUR_SECRET_KEY
aws configure set aws_session_token YOUR_SESSION_TOKEN
aws configure set region ap-northeast-2
```

### 방법 2: 환경 변수 (서비스 파일에 포함됨)
```bash
Environment=AWS_ACCESS_KEY_ID=YOUR_ACCESS_KEY
Environment=AWS_SECRET_ACCESS_KEY=YOUR_SECRET_KEY
Environment=AWS_SESSION_TOKEN=YOUR_SESSION_TOKEN
Environment=AWS_DEFAULT_REGION=ap-northeast-2
```

## 사용법

### 웹 인터페이스 접근
```
http://YOUR_EC2_PUBLIC_IP:8080
```

### 파일 업로드 과정
1. 웹 페이지에서 영상 파일 선택 또는 드래그 앤 드롭
2. 업로드 시작 후 실시간 진행률 확인
3. 처리 완료 후 두 가지 파일 다운로드:
   - 텍스트 파일 (TXT): 음성 인식 결과
   - 영상 파일 (MP4): 720p 변환된 영상

### 지원 파일 형식
- **입력**: MP4, AVI, MOV, MKV, WMV
- **출력**: MP4 (720p), TXT (UTF-8)
- **최대 크기**: 2GB

## API 엔드포인트

### POST /upload
영상 파일 업로드
```json
{
  "job_id": "uuid-string"
}
```

### GET /status/{job_id}
작업 상태 확인
```json
{
  "status": "processing|completed|error",
  "progress": 75,
  "message": "처리 중...",
  "elapsed_time": 120.5
}
```

### GET /download/txt/{job_id}
텍스트 파일 다운로드

### GET /download/video/{job_id}
720p 영상 파일 다운로드

## 성능 및 비용

### 처리 성능
- **영상 변환 속도**: 실시간의 2-3배 (720p 기준)
- **음성 인식 속도**: 실시간의 5-10배
- **동시 처리**: 멀티스레딩 지원

### 예상 비용 (10분 영상 기준)
- **Amazon Transcribe**: 약 $0.24 (320원)
- **EC2 t3.medium**: 약 $0.007 (9원)
- **S3 스토리지**: 약 $0.001 (1원)
- **데이터 전송**: 약 $0.09 (120원)
- **총 예상 비용**: 약 $0.34 (450원)

## 문제 해결

### 일반적인 문제

#### 1. "Unable to locate credentials" 오류
```bash
# AWS 자격 증명 확인
aws sts get-caller-identity

# 자격 증명 재설정
aws configure set aws_access_key_id YOUR_ACCESS_KEY
aws configure set aws_secret_access_key YOUR_SECRET_KEY
```

#### 2. "seek of closed file" 오류
- 파일 스트림 처리 문제로, 현재 버전에서 해결됨
- 파일을 메모리에 완전히 로드한 후 처리

#### 3. FFmpeg 오류
```bash
# FFmpeg 설치 확인
/usr/local/bin/ffmpeg -version

# 권한 확인
sudo chmod +x /usr/local/bin/ffmpeg
```

#### 4. 서비스 시작 실패
```bash
# 서비스 상태 확인
sudo systemctl status video-converter

# 로그 확인
sudo journalctl -u video-converter -n 20
```

### 로그 모니터링
```bash
# 실시간 로그 확인
sudo journalctl -u video-converter -f

# 최근 로그 확인
sudo journalctl -u video-converter -n 50 --no-pager
```

## 보안 고려사항

### 네트워크 보안
- 필요한 포트만 개방 (22, 8080)
- SSH 키 기반 인증 사용
- 정기적인 보안 업데이트

### 데이터 보안
- S3 버킷 암호화 설정
- IAM 역할 기반 최소 권한 원칙
- 임시 파일 자동 정리

### 애플리케이션 보안
- 파일 크기 제한 (2GB)
- 안전한 파일명 처리
- 입력 검증 및 예외 처리

## 확장성

### 수평 확장
- 로드 밸런서를 통한 다중 인스턴스 운영
- Auto Scaling Group 설정
- 세션 상태 외부 저장소 활용

### 수직 확장
- 더 큰 인스턴스 타입 사용 (c5.xlarge, c5.2xlarge)
- GPU 인스턴스 활용 (p3, g4 시리즈)
- 메모리 최적화 인스턴스 (r5 시리즈)

## 개발 환경

### 로컬 개발
```bash
# 가상 환경 생성
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install flask boto3 requests

# 개발 서버 실행
python app.py
```

### 테스트
```bash
# 서비스 연결 테스트
curl -I http://localhost:8080

# 파일 업로드 테스트
curl -X POST -F "video_file=@test.mp4" http://localhost:8080/upload
```

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 기여

버그 리포트, 기능 요청, 풀 리퀘스트를 환영합니다.

## 연락처

프로젝트 관련 문의사항이 있으시면 GitHub Issues를 통해 연락해 주세요.

---

**주의사항**: 이 서비스는 AWS 리소스를 사용하므로 비용이 발생할 수 있습니다. 사용 후에는 불필요한 리소스를 정리해 주세요.

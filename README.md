# team9-server
## API 문서
http://3.34.188.255/swagger/

## 스크럼 일정

**매주 월요일 오후 9시**

❗ 12월 6일 (월), 12월 13일 (월) 스크럼은 기말고사 기간으로 쉽니다.  

❗ 12월 8일 (수) 오후 9시에 대체 회의가 예정되어 있습니다.


## Branch 컨벤션

☝ `your-branch-name`은 lowercase, dash-separated, 간결하게.

- `feat/your-branch-name`: 기능 추가
- `refact/your-branch-name`: 리팩토링
- `fix/your-branch-name`: 버그 수정
- `test/your-branch-name`: 실험, 테스트 공간
- `others/your-branch-name`: 위 4가지 분류에 넣기 애매한 것들. 예를 들면 CI/CD 관련 파일이나 AWS 관련 파일들.

## Commit 규칙

[https://richone.tistory.com/26](https://richone.tistory.com/26)

## 기술 스택
- Python 3.8
- Django 3.2.6
- MySQL Client 2.1.0
- gunicorn 20.1.0
- nginx 1.20.0
- AWS EC2, RDS, S3
- [requirements.txt](https://github.com/wafflestudio19-5/team9-server/blob/master/project/requirements.txt)

## EC2 서버 주소

- `public ipv4`: 3.34.188.255
- `public dns`: [ec2-3-34-188-255.ap-northeast-2.compute.amazonaws.com](http://ec2-3-34-188-255.ap-northeast-2.compute.amazonaws.com/)

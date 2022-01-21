from datetime import datetime, timedelta


def format_time(time):
    now = datetime.now()
    time_elapsed = now - time
    if time_elapsed < timedelta(minutes=1):
        return "방금"
    elif time_elapsed < timedelta(hours=1):
        return f"{int(time_elapsed.seconds / 60)}분"
    elif time_elapsed < timedelta(days=1):
        return f"{int(time_elapsed.seconds / (60 * 60))}시간"
    elif time_elapsed < timedelta(days=7):
        return f"{time_elapsed.days}일"
    elif time.year == now.year:
        return f"{time.month}월 {time.day}일"
    else:
        return f"{time.year}년 {time.month}월 {time.day}일"


def get_directory_path(instance, filename):
    return (
        f"user/{instance.author}/posts/{instance.mainpost.id}/{instance.id}/{filename}"
    )


def comment_directory_path(instance, filename):
    return f"user/{instance.author}/comments/{instance.id}/{filename}"
